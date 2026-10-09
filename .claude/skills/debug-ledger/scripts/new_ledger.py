#!/usr/bin/env python3
"""Ledger anlegen, eskalieren und auflösen. Tier 1: nur Stdlib.

Drei Aktionen über Flags statt Subcommands, damit ein Aufruf so aussieht wie sein
eigenes Kopfzeilen-Kommando (`docs/artifact-header.md`):

    new_ledger.py --symptom S --repro R --expected E --observed O   (anlegen)
    new_ledger.py --escalate PFAD                                    (volles Schema anhängen)
    new_ledger.py --resolve PFAD --cause TEXT                        (INDEX.md-Zeile schreiben)
"""

from __future__ import annotations

import argparse
import re
import shlex
import sys
from datetime import date
from pathlib import Path

SCHEMA_VERSION = 1
SKILL_NAME = "debug-ledger"
PLACEHOLDER = "_(noch offen)_"
FULL_MARKER = "<!-- full-schema-below -->"
INDEX_ENTRY_RE = re.compile(r"^- .+ → .+$", re.MULTILINE)
SYMPTOM_SECTION_RE = re.compile(r"^##\s*Symptom\s*$", re.MULTILINE)

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "ledger-template.md"
SCRIPT_LABEL = "skills/debug-ledger/scripts/new_ledger.py"


class LedgerError(RuntimeError):
    """Anlegen, Eskalieren oder Auflösen ist an einer verständlichen Ursache gescheitert."""


def header_line(generated: str) -> str:
    return f"<!-- skill: {SKILL_NAME} | schema: {SCHEMA_VERSION} | generated: {generated} -->"


_UMLAUT_MAP = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def slugify(text: str, *, max_len: int = 40) -> str:
    """Symptom-Text in einen Dateinamen-Slug übersetzen: nie leer, immer ASCII."""
    lowered = text.lower().translate(_UMLAUT_MAP)
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    slug = slug[:max_len].strip("-")
    return slug or "fall"


def load_template() -> tuple[str, str]:
    """Mini- und Voll-Schema-Teil aus assets/ledger-template.md laden."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    if FULL_MARKER not in text:
        raise LedgerError(f"Template ohne Marker {FULL_MARKER!r}: {TEMPLATE_PATH}")
    mini, _, full = text.partition(FULL_MARKER)
    return mini.rstrip("\n") + "\n", full.strip("\n") + "\n"


def index_path(repo: Path) -> Path:
    return repo / "docs" / "debugging" / "INDEX.md"


def bootstrap_index(repo: Path, generated: str) -> bool:
    """Archiv anlegen, falls es noch nicht existiert. Meldet die Anlage (Bootstrap-Regel).

    `generated` ist das tatsächlich laufende Kommando (der Aufruf, der den
    Bootstrap gerade auslöst) — nie ein festes `--resolve`-Template. Reviewer-Fund:
    Ein Bootstrap über `--symptom` trug vorher eine `--resolve`-Kopfzeile mit
    literalen Platzhaltern, die nie lief und nicht re-eintippbar war
    (`docs/artifact-header.md`: "so wie man es erneut eintippen würde").
    """
    idx = index_path(repo)
    if idx.is_file():
        return False
    idx.parent.mkdir(parents=True, exist_ok=True)
    content = (
        header_line(generated) + "\n\n"
        "# Debugging-Archiv\n\n"
        "Eine Zeile pro gelöstem Fall: Symptom → Ursache. Wird nie automatisch "
        "umgegliedert oder geprunt (siehe SKILL.md).\n\n"
    )
    idx.write_text(content, encoding="utf-8")
    print(f"Archiv neu angelegt: {idx.relative_to(repo)}")
    return True


def find_free_path(repo: Path, date_str: str, slug: str) -> Path:
    base_dir = repo / "docs" / "debugging"
    candidate = base_dir / f"{date_str}-{slug}.md"
    n = 2
    while candidate.exists():
        candidate = base_dir / f"{date_str}-{slug}-{n}.md"
        n += 1
    return candidate


def action_new(
    repo: Path, *, symptom: str, repro: str, expected: str, observed: str,
    slug: str | None, date_str: str | None,
) -> Path:
    generated = (
        f"python {SCRIPT_LABEL} --symptom {shlex.quote(symptom)} "
        f"--repro {shlex.quote(repro)} --expected {shlex.quote(expected)} "
        f"--observed {shlex.quote(observed)}"
    )

    created_dir = not (repo / "docs" / "debugging").is_dir()
    bootstrap_index(repo, generated)
    if created_dir:
        print(f"Archiv-Verzeichnis neu angelegt: {(repo / 'docs' / 'debugging').relative_to(repo)}")

    date_str = date_str or date.today().isoformat()
    slug = slug or slugify(symptom)
    target = find_free_path(repo, date_str, slug)

    mini_template, _ = load_template()
    body = mini_template.format(symptom=symptom, repro=repro, expected=expected, observed=observed)
    target.write_text(header_line(generated) + "\n\n" + body, encoding="utf-8")
    print(f"Mini-Ledger angelegt: {target.relative_to(repo)}")
    return target


def action_escalate(repo: Path, ledger_rel: str) -> Path:
    target = repo / ledger_rel
    if not target.is_file():
        raise LedgerError(f"Ledger nicht gefunden: {ledger_rel}")
    text = target.read_text(encoding="utf-8")
    if "## Hypothesen" in text:
        print(f"Bereits im vollen Modus, nichts geändert: {ledger_rel}")
        return target
    _, full_template = load_template()
    if not text.endswith("\n"):
        text += "\n"
    target.write_text(text + "\n" + full_template, encoding="utf-8")
    print(f"Auf volles Schema eskaliert: {ledger_rel}")
    return target


def _extract_symptom(text: str) -> str:
    match = SYMPTOM_SECTION_RE.search(text)
    if not match:
        return "(Symptom unbekannt)"
    rest = text[match.end():]
    for line in rest.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("##"):
            return stripped
    return "(Symptom unbekannt)"


def action_resolve(repo: Path, ledger_rel: str, cause: str) -> None:
    target = repo / ledger_rel
    if not target.is_file():
        raise LedgerError(f"Ledger nicht gefunden: {ledger_rel}")
    symptom = _extract_symptom(target.read_text(encoding="utf-8"))

    generated = f"python {SCRIPT_LABEL} --resolve {shlex.quote(ledger_rel)} --cause {shlex.quote(cause)}"
    bootstrap_index(repo, generated)
    idx = index_path(repo)
    content = idx.read_text(encoding="utf-8")

    # Link-Ziel relativ zu INDEX.md, nicht zum Repo-Wurzelverzeichnis: INDEX.md liegt
    # selbst in docs/debugging/, ein repo-relativer Pfad löste zu docs/debugging/docs/
    # debugging/<datei>.md auf und zeigte ins Leere.
    link_target = Path(ledger_rel).name
    if f"]({link_target})" in content:
        print(f"INDEX.md verweist bereits auf {ledger_rel}, nichts geändert.")
        return

    entry = f"- {symptom} → {cause} ([{link_target}]({link_target}))\n"
    if not content.endswith("\n"):
        content += "\n"
    content += entry
    idx.write_text(content, encoding="utf-8")
    print(f"INDEX.md aktualisiert: {ledger_rel}")

    entry_count = len(INDEX_ENTRY_RE.findall(content))
    if entry_count >= 50:
        print(
            f"WARNUNG: docs/debugging/INDEX.md hat {entry_count} Einträge. Die Datei bleibt "
            "flach und wird nicht automatisch umgegliedert oder geprunt (siehe SKILL.md)."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="debug-ledger: Ledger anlegen, eskalieren, auflösen")
    parser.add_argument("--symptom")
    parser.add_argument("--repro")
    parser.add_argument("--expected")
    parser.add_argument("--observed")
    parser.add_argument("--escalate", metavar="LEDGER")
    parser.add_argument("--resolve", metavar="LEDGER")
    parser.add_argument("--cause")
    parser.add_argument("--slug", help="Dateiname-Slug erzwingen statt aus --symptom abzuleiten")
    parser.add_argument("--date", dest="date_str", help="Datum im Dateinamen erzwingen (YYYY-MM-DD)")
    parser.add_argument("--repo", type=Path, default=Path("."))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    actions = [bool(args.symptom), bool(args.escalate), bool(args.resolve)]
    if sum(actions) != 1:
        parser.error("genau eine Aktion angeben: --symptom (anlegen), --escalate PFAD, oder --resolve PFAD --cause TEXT")

    try:
        if args.symptom:
            for field in ("repro", "expected", "observed"):
                if not getattr(args, field):
                    parser.error(f"--symptom braucht auch --{field}")
            action_new(
                args.repo, symptom=args.symptom, repro=args.repro,
                expected=args.expected, observed=args.observed,
                slug=args.slug, date_str=args.date_str,
            )
        elif args.escalate:
            action_escalate(args.repo, args.escalate)
        else:
            if not args.cause:
                parser.error("--resolve braucht auch --cause")
            action_resolve(args.repo, args.resolve, args.cause)
    except LedgerError as exc:
        print(f"debug-ledger: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
