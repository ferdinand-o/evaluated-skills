#!/usr/bin/env python3
"""Ledger-Pflichtfelder mechanisch prüfen. Tier 1: nur Stdlib.

G2 nach Spec 00 §4: Das Urteil ist maschinell (dieses Skript entscheidet), der
Aufruf bleibt freiwillig — "meldet Verstoß", nicht "blockiert". G3 entsteht nur,
wenn der Nutzer `assets/hooks/check-ledger.json` selbst einrichtet; dieses Skript
installiert nie sich selbst als Hook.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1
SKILL_NAME = "debug-ledger"
PLACEHOLDER = "_(noch offen)_"

HEADER_RE = re.compile(
    r"^(?:<!--|#)\s*skill:\s*(?P<skill>[a-z0-9][a-z0-9-]*)\s*\|"
    r"\s*schema:\s*(?P<schema>\d+)\s*\|"
    r"\s*generated:\s*(?P<cmd>.+?)\s*(?:-->)?\s*$"
)
SECTION_RE = re.compile(r"^##\s*(?P<heading>.+?)\s*$", re.MULTILINE)

# Die drei Pflichtfelder des Mini-Ledgers — immer geprüft, ob mini oder voll.
MINI_FIELDS = ("Symptom", "Repro-Kommando", "Erwartung vs. Beobachtung")


def read_header(text: str) -> dict | None:
    for line in text.splitlines():
        if not line.strip():
            continue
        match = HEADER_RE.match(line.strip())
        if not match:
            return None
        return {
            "skill": match.group("skill"),
            "schema": int(match.group("schema")),
            "generated": match.group("cmd"),
        }
    return None


def parse_sections(text: str) -> dict[str, str]:
    """`## Überschrift` -> Text bis zur nächsten `##`-Überschrift."""
    matches = list(SECTION_RE.finditer(text))
    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[match.group("heading")] = text[start:end]
    return sections


def _strip_fences(body: str) -> str:
    """Code-Fence-Zeilen (```) entfernen, damit der Inhalt darin geprüft wird."""
    lines = [line for line in body.strip("\n").splitlines() if not line.strip().startswith("```")]
    return "\n".join(lines).strip()


def is_unfilled(body: str) -> bool:
    content = _strip_fences(body)
    return content == "" or content == PLACEHOLDER


_SEPARATOR_CELL_RE = re.compile(r"^-+$")

# Reviewer-Fund: "nicht leer, nicht der exakte Platzhalter" laesst Fuellwoerter
# wie "-" oder "Unklar" als Testevidenz durchgehen. Eine Zeile zaehlt nur als
# getestet, wenn Test/Ergebnis echten Inhalt tragen (kein reiner Fuellwort- oder
# Satzzeichen-Text, Mindestlaenge) UND Verdict aus der geschlossenen Menge
# {Bestaetigt, Verworfen} stammt -- Freitext wie "Unklar" zaehlt nicht. Dieselbe
# Anforderung steht in references/ledger-schema.md, damit Vorschrift und
# Pruefung uebereinstimmen.
_FILLER_WORDS = frozenset({
    "-", "--", "?", "n/a", "na", "k.a.", "ka", "tbd", "unklar", "unbekannt",
    "offen", "unsicher", "vielleicht", "keine ahnung", "weiss nicht", "weiß nicht",
})
_MIN_EVIDENCE_LEN = 8
_VALID_VERDICTS = frozenset({"bestätigt", "bestaetigt", "verworfen"})


def _is_filler(cell: str) -> bool:
    """Zelle traegt keine belastbare Testevidenz."""
    stripped = cell.strip()
    if not stripped or stripped == PLACEHOLDER:
        return True
    if stripped.lower() in _FILLER_WORDS:
        return True
    if len(stripped) < _MIN_EVIDENCE_LEN:
        return True
    if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", stripped):  # nur Satzzeichen/Symbole
        return True
    return False


def parse_hypothesis_rows(body: str) -> list[list[str]]:
    """Datenzeilen der Hypothesen-Tabelle, ohne Kopf- und Trennzeile."""
    rows: list[list[str]] = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and all(_SEPARATOR_CELL_RE.match(c) for c in cells):
            continue  # Trennzeile ("| --- | --- | ... |")
        if cells and cells[0] == "Hypothese":
            continue  # Kopfzeile
        rows.append(cells)
    return rows


def is_tested_row(cells: list[str]) -> bool:
    """Eine Zeile zaehlt nur als getestet, wenn sie echte Testevidenz traegt.

    Hypothese darf frei formuliert sein (das ist die Vermutung selbst) -- Test
    und Ergebnis muessen aber konkreten Inhalt haben, und Verdict muss aus der
    geschlossenen Menge {Bestaetigt, Verworfen} stammen.
    """
    if len(cells) < 4:
        return False
    hypothese, test, ergebnis, verdict = (c.strip() for c in cells[:4])
    if not hypothese or hypothese == PLACEHOLDER:
        return False
    if _is_filler(test) or _is_filler(ergebnis):
        return False
    if verdict.lower() not in _VALID_VERDICTS:
        return False
    return True


def count_tested_hypotheses(body: str) -> int:
    return sum(1 for cells in parse_hypothesis_rows(body) if is_tested_row(cells))


def check(path: Path) -> list[str]:
    """Liefert die Liste der Verstöße; leer heißt sauber."""
    text = path.read_text(encoding="utf-8")
    violations: list[str] = []

    header = read_header(text)
    if header is None:
        violations.append("Kopfzeile fehlt oder ist falsch formatiert")
    else:
        if header["skill"] != SKILL_NAME:
            violations.append(f"Kopfzeile nennt Skill {header['skill']!r}, erwartet {SKILL_NAME!r}")
        if header["schema"] != SCHEMA_VERSION:
            violations.append(f"Kopfzeile nennt schema {header['schema']}, erwartet {SCHEMA_VERSION}")

    sections = parse_sections(text)
    for field in MINI_FIELDS:
        body = sections.get(field)
        if body is None:
            violations.append(f"Pflichtfeld fehlt: {field}")
        elif is_unfilled(body):
            violations.append(f"Pflichtfeld leer: {field}")

    full_mode = "Hypothesen" in sections
    if full_mode:
        fix_filled = not is_unfilled(sections.get("Fix", ""))
        tested = count_tested_hypotheses(sections.get("Hypothesen", ""))
        if fix_filled and tested == 0:
            violations.append(
                "Fix vorgeschlagen ohne mindestens eine getestete Zeile in der Hypothesen-Tabelle"
            )

    return violations


def _is_git_repo(repo: Path) -> bool:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo, capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0 and done.stdout.strip() == "true"


def staged_ledgers(repo: Path) -> list[str]:
    """Gestagte Ledger-Dateien unter docs/debugging/, ohne INDEX.md.

    Grundlage für den optionalen G3-Hook (`assets/hooks/check-ledger.json`): Der
    Hook ruft `check_ledger.py --staged` statt einer festen Ledger-Datei, weil er
    zum Zeitpunkt des Commits nicht weiß, welche Datei gemeint ist.
    """
    done = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo, capture_output=True, text=True, timeout=30, check=False,
    )
    paths = [p.strip() for p in done.stdout.splitlines() if p.strip()]
    return [p for p in paths if p.startswith("docs/debugging/") and p.endswith(".md") and not p.endswith("INDEX.md")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="debug-ledger: Ledger-Pflichtfelder prüfen (G2)")
    parser.add_argument("ledger", type=Path, nargs="?", help="Pfad zu einer Ledger-Datei")
    parser.add_argument("--staged", action="store_true", help="alle gestagten Ledger prüfen (für den G3-Hook)")
    parser.add_argument("--repo", type=Path, default=Path("."), help="nur mit --staged relevant")
    args = parser.parse_args(argv)

    if args.staged and args.ledger:
        parser.error("--staged und ein Ledger-Pfad schließen sich aus")
    if not args.staged and not args.ledger:
        parser.error("Ledger-Pfad oder --staged angeben")

    if args.staged:
        if not _is_git_repo(args.repo):
            print(f"debug-ledger: kein Git-Repository unter {args.repo} — --staged nicht verfügbar", file=sys.stderr)
            return 2
        ledgers = staged_ledgers(args.repo)
        if not ledgers:
            print("OK: keine gestagten Ledger-Dateien")
            return 0
        any_violation = False
        for rel in ledgers:
            violations = check(args.repo / rel)
            if violations:
                any_violation = True
                print(f"Verstoß gemeldet in {rel} ({len(violations)}):")
                for violation in violations:
                    print(f"  - {violation}")
            else:
                print(f"OK: {rel}")
        return 1 if any_violation else 0

    if not args.ledger.is_file():
        print(f"debug-ledger: Ledger nicht gefunden: {args.ledger}", file=sys.stderr)
        return 2

    violations = check(args.ledger)
    if not violations:
        print(f"OK: {args.ledger}")
        return 0

    print(f"Verstoß gemeldet ({len(violations)}):")
    for violation in violations:
        print(f"  - {violation}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
