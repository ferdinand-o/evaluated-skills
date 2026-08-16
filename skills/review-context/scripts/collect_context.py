#!/usr/bin/env python3
"""Kontextpaket für /code-review sammeln. Tier 1: nur Stdlib.

Diese Skill baut nicht die Linsen-Engine (Spec 04) — die liefert Claude Code
bereits als `/code-review` mit. Additiv ist ausschließlich dieses Skript:
Es baut aus einem Git-Diff drei gewichtete Kontextpakete (Spec-Compliance,
Korrektheit, Vereinfachung) und schreibt sie deterministisch, damit der
generische Reviewer nicht raten muss, was eine Änderung erreichen sollte.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = 1
CACHE_PATH = Path(".skills") / "cache" / "review-context.json"

MAX_FILE_CHARS = 4000
MAX_PATCH_CHARS = 4000
MAX_CALLERS = 20
MAX_SIBLING_FILES = 15

# Minimalbar für "zählt als Soll" (Fix-Runde, s. docs/known-limits.md und
# docs/superpowers/reports/review-context-report.md): reine Existenz reicht
# nicht. Eine Feature-Spec-Datei ohne Given/When/Then braucht mindestens so
# viel Prosa jenseits von Überschriften und Leerzeilen; eine Commit-Message
# zählt inhaltlich, nicht nach Anzahl der Commits im Range.
MIN_SPEC_CONTENT_CHARS = 40
MIN_SUBJECT_CHARS = 20
GENERIC_COMMIT_SUBJECTS = frozenset({
    "wip", "fix", "tmp", "temp", "misc", "update", "updates",
    "changes", "stuff", "asdf", "test", "wip commit", "fixup",
})

NO_SOLL_MESSAGE = "Änderung ohne benanntes Soll ist nicht reviewbar."
EMPTY_DIFF_MESSAGE = "Diff ist leer — kein Review-Gegenstand."

CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx")
EXCLUDED_DIR_NAMES = {
    ".git", ".skills", ".claude", "node_modules", "__pycache__",
    ".venv", "venv", "dist", "build", ".pytest_cache",
}


class CollectError(RuntimeError):
    """Das Sammeln ist gescheitert — mit einer Ursache, die der Nutzer versteht."""


# --- Git-Hilfsfunktionen -----------------------------------------------

def _git(repo: Path, *args: str) -> str:
    """git-Aufruf, der bei Fehlschlag hart wirft — für Aufrufe, die gelingen müssen."""
    try:
        done = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, timeout=120, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CollectError(f"git {' '.join(args)} konnte nicht gestartet werden: {exc}") from exc
    if done.returncode != 0:
        raise CollectError(f"git {' '.join(args)} fehlgeschlagen: {done.stderr.strip()}")
    return done.stdout


def _git_try(repo: Path, *args: str) -> tuple[bool, str]:
    """git-Aufruf, dessen Fehlschlag erwartet und bedeutungstragend ist (z. B. `git show`
    auf einer Datei, die an diesem Ref noch nicht existierte). Wirft nie."""
    try:
        done = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, timeout=120, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CollectError(f"git {' '.join(args)} konnte nicht gestartet werden: {exc}") from exc
    return done.returncode == 0, done.stdout


def _require_git_repo(repo: Path) -> None:
    ok, _ = _git_try(repo, "rev-parse", "--is-inside-work-tree")
    if not ok:
        raise CollectError(
            "kein Git-Repository unter diesem Pfad — review-context braucht git für den Diff"
        )


# --- Range-Auflösung -----------------------------------------------------

def resolve_range(range_arg: str | None) -> tuple[str, str, str | None, str | None]:
    """Bestimme Vergleichsmodus aus `--range`.

    Ohne Angabe: `("uncommitted", "HEAD", None, None)` — der Diff ist das
    Arbeitsverzeichnis gegen HEAD (`git diff HEAD`), also die typische
    "review meine gerade gemachte, noch nicht committete Änderung"-Situation.

    Mit `--range BASIS..ZIEL`: `("range", BASIS, ZIEL, "BASIS..ZIEL")`. Nur
    Zwei-Punkt-Syntax — Drei-Punkt (`...`) bräuchte eine Merge-Base-Auflösung,
    zusätzliche Komplexität, die dieses Tier-1-Skript nicht rechtfertigt.
    """
    if range_arg is None:
        return "uncommitted", "HEAD", None, None
    if "..." in range_arg:
        raise CollectError(
            "--range: Drei-Punkt-Syntax ('...') wird nicht unterstützt — "
            "gib BASIS..ZIEL an (Zwei-Punkt, z. B. HEAD~1..HEAD oder main..feature/x)"
        )
    if ".." not in range_arg:
        raise CollectError(
            f"--range muss die Form BASIS..ZIEL haben, war: {range_arg!r}"
        )
    base, _, head = range_arg.partition("..")
    if not base or not head:
        raise CollectError(
            f"--range: BASIS und ZIEL dürfen nicht leer sein, war: {range_arg!r}"
        )
    return "range", base, head, range_arg


def _diff_refs(mode: str, base: str, head: str | None) -> list[str]:
    """Ref-Argumente für `git diff`: ein Ref (gegen Arbeitsverzeichnis) oder zwei."""
    if mode == "uncommitted":
        return [base]
    return [base, head]  # type: ignore[list-item]


# --- Diff-Dateien und ihr Ist-Stand ---------------------------------------

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _changed_ranges_after(patch: str) -> list[tuple[int, int]]:
    """Geänderte Zeilenbereiche auf der "Nachher"-Seite, aus den Hunk-Headern.

    `@@ -a,b +c,d @@` — `c` ist die Startzeile, `d` die Länge auf der neuen
    Seite (fehlt `d`, ist es 1). Reine Löschungen (`d == 0`) markieren den
    Einfügepunkt als einzeiligen Bereich, sonst ginge die Änderung als
    Symbol-Trigger verloren.
    """
    ranges: list[tuple[int, int]] = []
    for line in patch.splitlines():
        match = _HUNK_RE.match(line)
        if not match:
            continue
        start = int(match.group(1))
        length = int(match.group(2)) if match.group(2) is not None else 1
        if length == 0:
            ranges.append((start, start))
        else:
            ranges.append((start, start + length - 1))
    return ranges


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + f"\n… (gekürzt, Obergrenze {limit} Zeichen)", True


def _content_at_ref(repo: Path, ref: str, path: str) -> str | None:
    ok, out = _git_try(repo, "show", f"{ref}:{path}")
    return out if ok else None


def _content_in_worktree(repo: Path, path: str) -> str | None:
    target = repo / path
    if not target.is_file():
        return None
    try:
        return target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _numstat(repo: Path, refs: list[str], path: str) -> tuple[bool, int, int]:
    """(ist_binaer, insertions, deletions) — ein einziger `git diff --numstat`-Aufruf.

    Binärdateien meldet git als `-\\t-\\tpfad` statt Zahlen.
    """
    out = _git(repo, "diff", "--numstat", *refs, "--", path)
    line = out.strip()
    if not line:
        return False, 0, 0
    parts = line.split("\t")
    if len(parts) < 2:
        return False, 0, 0
    added, removed = parts[0], parts[1]
    if added == "-" and removed == "-":
        return True, 0, 0
    return False, (int(added) if added.isdigit() else 0), (int(removed) if removed.isdigit() else 0)


def list_changed_files(repo: Path, mode: str, base: str, head: str | None) -> list[dict]:
    """Je geänderter Datei: Status, Ist-Stand vorher/nachher, Patch, Zeilenbereiche.

    Ränder, die hier bewusst behandelt werden: leerer Diff (leere Liste), neue
    Datei (kein Vorher-Stand), gelöschte Datei (kein Nachher-Stand), Binärdatei
    (kein Inhalt, kein Patch), Umbenennung (`old_path` gesetzt).
    """
    refs = _diff_refs(mode, base, head)
    raw = _git(repo, "diff", "--name-status", "-M", *refs)

    results: list[dict] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        code = fields[0]
        if code.startswith("R") or code.startswith("C"):
            old_path, path = fields[1], fields[2]
            status = "renamed"
        else:
            old_path, path = None, fields[1]
            status = {"A": "added", "M": "modified", "D": "deleted"}.get(code[:1], "modified")

        is_binary, insertions, deletions = _numstat(repo, refs, path)
        if is_binary:
            results.append({
                "path": path, "old_path": old_path, "status": "binary",
                "insertions": 0, "deletions": 0,
                "before": None, "before_truncated": False, "before_note": "Binärdatei, Inhalt nicht extrahiert",
                "after": None, "after_truncated": False, "after_note": "Binärdatei, Inhalt nicht extrahiert",
                "patch": None, "patch_truncated": False,
                "changed_ranges_after": [],
            })
            continue

        patch_raw = _git(repo, "diff", "-M", *refs, "--", path)
        patch, patch_truncated = _truncate(patch_raw, MAX_PATCH_CHARS)

        before_note = None
        before_raw = _content_at_ref(repo, base, old_path or path)
        if before_raw is None:
            before_note = "neu, kein Vorher-Stand"
        before, before_truncated = (_truncate(before_raw, MAX_FILE_CHARS) if before_raw is not None else (None, False))

        after_note = None
        if mode == "uncommitted":
            after_raw = _content_in_worktree(repo, path)
        else:
            after_raw = _content_at_ref(repo, head, path)  # type: ignore[arg-type]
        if after_raw is None:
            after_note = "gelöscht"
        after, after_truncated = (_truncate(after_raw, MAX_FILE_CHARS) if after_raw is not None else (None, False))

        changed_ranges_after = _changed_ranges_after(patch_raw) if after_raw is not None else []

        results.append({
            "path": path, "old_path": old_path, "status": status,
            "insertions": insertions, "deletions": deletions,
            "before": before, "before_truncated": before_truncated, "before_note": before_note,
            "after": after, "after_truncated": after_truncated, "after_note": after_note,
            "patch": patch, "patch_truncated": patch_truncated,
            "changed_ranges_after": changed_ranges_after,
        })
    return results


# --- Soll-Auflösung --------------------------------------------------------
#
# Reihenfolge (R13 des Auftrags): Feature-Spec unter docs/specs/wip/ (ideal
# mit Given/When/Then aus Spec 03), sonst PR-Beschreibung (zählt als Soll,
# aber als schwächere Quelle markiert), sonst Commit-Messages des Bereichs.
# Fehlt alles, ist das ein Befund ("nicht reviewbar"), keine Notlage — das
# Paket wird trotzdem geschrieben.

_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
_GWT_RE = re.compile(r"^\s*[-*]?\s*\**\s*(Given|When|Then|And)\**\s*:?\s*(.*)$")


def parse_given_when_then(text: str) -> list[dict]:
    """Given/When/Then-Blöcke aus Markdown extrahieren.

    Erwartetes Format (Spec 03s ideales Format): pro Kriterium eine Given-,
    When- und Then-Zeile, optional mit vorangestelltem Listenzeichen oder
    Fett-Markierung ("- **Given:** ..."). And-Zeilen hängen sich als
    Zusatzbedingung an das laufende Kriterium. Eine vorausgehende Überschrift
    wird als Kriterien-Titel übernommen. Ein Kriterium zählt erst als
    vollständig, wenn Given, When und Then alle gesetzt sind — sonst wird es
    verworfen, nicht raten-ergänzt.
    """
    criteria: list[dict] = []
    title: str | None = None
    block: dict | None = None

    def flush() -> None:
        nonlocal block
        if block and block["given"] and block["when"] and block["then"]:
            criteria.append(block)
        block = None

    def ensure_block() -> dict:
        nonlocal block
        if block is None:
            block = {"title": title, "given": "", "when": "", "then": "", "and_": []}
        return block

    for raw_line in text.splitlines():
        heading = _HEADING_RE.match(raw_line)
        if heading:
            flush()
            title = heading.group(1).strip()
            continue
        match = _GWT_RE.match(raw_line)
        if not match:
            continue
        keyword, rest = match.group(1), match.group(2).strip()
        if not rest:
            continue
        if keyword == "Given":
            current = ensure_block()
            if current["given"] and current["when"] and current["then"]:
                flush()
                current = ensure_block()
            current["given"] = rest
        elif keyword == "When":
            ensure_block()["when"] = rest
        elif keyword == "Then":
            ensure_block()["then"] = rest
        elif keyword == "And":
            ensure_block()["and_"].append(rest)
    flush()
    return criteria


def _spec_body_without_headings(text: str) -> str:
    """Text ohne Überschriftenzeilen und ohne Leerzeilen — die Prosa, die zählt.

    Eine Datei, die nur aus `# Titel` besteht, hat hier eine leere Ausbeute —
    genau der Fall, den die Fix-Runde als „zählt fälschlich als Soll" gemeldet
    hat (docs/known-limits.md).
    """
    return "\n".join(
        line.strip() for line in text.splitlines()
        if line.strip() and not _HEADING_RE.match(line)
    )


def _has_meaningful_spec_content(text: str, criteria: list[dict]) -> bool:
    """Minimalbar für „zählt als Soll": ein vollständiges Given/When/Then-
    Kriterium reicht immer. Sonst muss genug Prosa jenseits von Überschriften
    und Leerraum übrig bleiben — eine leere Datei, eine mit nur Leerraum oder
    eine mit nur einer Überschrift zählt nicht (Fix-Runde: vorher prüfte
    `find_feature_spec` nur Existenz, nicht Inhalt, und unterdrückte damit den
    `no_soll`-Befund fälschlich).
    """
    if criteria:
        return True
    return len(_spec_body_without_headings(text)) >= MIN_SPEC_CONTENT_CHARS


def find_feature_spec(repo: Path) -> list[dict] | None:
    """Feature-Spezifikationen unter `docs/specs/wip/` (Spec 03), falls vorhanden
    **und inhaltlich tragfähig**.

    Fehlt der Ordner, enthält er keine Markdown-Datei, oder ist keine der
    gefundenen Dateien inhaltlich tragfähig (`_has_meaningful_spec_content`):
    `None` — kein Fehler, nur „hier gibt es kein benanntes Soll". Eine
    gefundene, inhaltlich tragfähige Spec zählt als Soll auch ohne geparste
    Given/When/Then-Blöcke (dann trägt sie einen Excerpt statt struktierter
    Kriterien — R13 verlangt nur „gar nichts" als Trigger für den Befund,
    nicht „nicht ideal formatiert").
    """
    spec_dir = repo / "docs" / "specs" / "wip"
    if not spec_dir.is_dir():
        return None
    md_files = sorted(p for p in spec_dir.glob("*.md") if p.is_file())
    if not md_files:
        return None

    specs: list[dict] = []
    for path in md_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        criteria = parse_given_when_then(text)
        if not _has_meaningful_spec_content(text, criteria):
            continue
        entry: dict = {"path": path.relative_to(repo).as_posix(), "criteria": criteria}
        if not criteria:
            excerpt, _ = _truncate(text, MAX_FILE_CHARS)
            entry["excerpt"] = excerpt
        specs.append(entry)
    return specs or None


def find_pr_description(
    pr_description: str | None, pr_description_file: str | None, repo: Path,
) -> dict | None:
    """PR-Beschreibung aus `--pr-description` oder `--pr-description-file`.

    Ein lokales Skript kann keine PR-API abfragen — der Aufrufer (Agent oder
    Mensch, der z. B. `gh pr view` gelesen hat) reicht den Text explizit rein.
    """
    if pr_description and pr_description_file:
        raise CollectError("--pr-description und --pr-description-file schließen sich aus")
    if pr_description:
        return {"text": pr_description.strip()}
    if pr_description_file:
        path = Path(pr_description_file)
        if not path.is_absolute():
            path = repo / path
        if not path.is_file():
            raise CollectError(f"--pr-description-file nicht gefunden: {pr_description_file}")
        return {"text": path.read_text(encoding="utf-8", errors="replace").strip()}
    return None


_CONVENTIONAL_PREFIX_RE = re.compile(r"^[a-z]+(\([^)]*\))?!?:\s*", re.IGNORECASE)


def _is_meaningful_commit_message(subject: str, body: str) -> bool:
    """Zählt eine einzelne Commit-Message inhaltlich als Soll?

    Fix-Runde: Die Anzahl der Commits im Range sagt nichts über die
    Aussagekraft ihrer Messages — eine ausführliche, klar zielbeschreibende
    Message, die allein steht, ist ein gültiges Soll. Gemessen wird stattdessen
    am Inhalt: Ein Body jenseits der Betreffzeile zählt immer. Ohne Body muss
    die Betreffzeile (nach Abzug eines Conventional-Commit-Präfixes wie
    "fix: "/"feat(x): ") hinreichend lang sein und darf kein reiner Platzhalter
    ("wip", "fix", "tmp", …) sein.
    """
    if body.strip():
        return True
    normalized = _CONVENTIONAL_PREFIX_RE.sub("", subject.strip()).strip().lower()
    if not normalized or normalized in GENERIC_COMMIT_SUBJECTS:
        return False
    return len(normalized) >= MIN_SUBJECT_CHARS


def find_commit_message_soll(repo: Path, mode: str, base: str, head: str | None) -> dict | None:
    """Commit-Messages des Bereichs als letzte, schwache Soll-Quelle (R13).

    Zählt, sobald mindestens eine Message im Bereich inhaltlich trägt
    (`_is_meaningful_commit_message`) — unabhängig davon, wie viele Commits im
    Range liegen. Uncommitted-Diffs haben keine zugehörige Commit-Message und
    liefern deshalb immer `None`; ein Range ohne Commits ebenso.
    """
    if mode != "range":
        return None
    raw = _git(repo, "log", f"{base}..{head}", "--format=%s%x1f%b%x1e")
    blocks = [b for b in raw.split("\x1e") if b.strip("\n")]
    if not blocks:
        return None

    messages: list[str] = []
    any_meaningful = False
    for block in blocks:
        subject, _, body = block.strip("\n").partition("\x1f")
        subject, body = subject.strip(), body.strip()
        if _is_meaningful_commit_message(subject, body):
            any_meaningful = True
        text = subject + (f"\n{body}" if body else "")
        messages.append(text)

    if not any_meaningful:
        return None
    return {"text": "\n\n".join(messages), "count": len(messages)}


def resolve_soll(
    repo: Path, mode: str, base: str, head: str | None,
    pr_description: str | None, pr_description_file: str | None,
) -> dict:
    """Soll-Quelle in Prioritätsreihenfolge auflösen (R13)."""
    spec = find_feature_spec(repo)
    if spec:
        return {"source": "feature_spec", "weak": False, "spec": spec}
    pr = find_pr_description(pr_description, pr_description_file, repo)
    if pr:
        return {"source": "pr_description", "weak": True, **pr}
    commit_soll = find_commit_message_soll(repo, mode, base, head)
    if commit_soll:
        return {"source": "commit_messages", "weak": True, **commit_soll}
    return {"source": "none", "weak": None}


# --- docs/decisions.md — Konsumenten-Regel wie dev-report's Harvest --------

_DECISIONS_HEADER_RE = re.compile(
    r"^(?:<!--|#)\s*skill:\s*(?P<skill>[a-z0-9][a-z0-9-]*)\s*\|"
    r"\s*schema:\s*(?P<schema>\d+)\s*\|"
    r"\s*generated:\s*(?P<cmd>.+?)\s*(?:-->)?\s*$"
)
DECISIONS_SCHEMA_EXPECTED = 1


def read_decisions(repo: Path) -> dict:
    """`docs/decisions.md` nach der Konsumenten-Regel lesen (Spec 00 §1).

    Dieselbe Regel, die `dev-report`s Harvest schon anwendet: Kopfzeile fehlt
    oder Schema passt nicht → sichtbar überspringen, nie raten. Die Skill,
    die diese Datei erzeugt (feature-spec, Spec 03), ist noch nicht gebaut —
    der Regelfall ist deshalb aktuell `missing` oder `no_header`.
    """
    path = repo / "docs" / "decisions.md"
    if not path.is_file():
        return {"status": "missing", "entries": []}
    text = path.read_text(encoding="utf-8", errors="replace")

    header = None
    for line in text.splitlines():
        if not line.strip():
            continue
        match = _DECISIONS_HEADER_RE.match(line.strip())
        header = {"schema": int(match.group("schema"))} if match else None
        break

    if header is None:
        return {"status": "no_header", "entries": []}
    if header["schema"] != DECISIONS_SCHEMA_EXPECTED:
        return {"status": "schema_mismatch", "schema": header["schema"], "entries": []}

    entries = [line.strip() for line in text.splitlines() if line.strip().startswith("- ")]
    return {"status": "read", "entries": entries}


# --- Symbol-Erkennung -------------------------------------------------------
#
# Python: exakt über `ast` (Signaturen, Zeilenbereiche). TypeScript/JS: eine
# ehrliche grep-Regex ohne Scope-Analyse (R16) — sie erkennt ein Symbol nur,
# wenn seine Deklarationszeile selbst im geänderten Bereich liegt, verfolgt
# also anders als die Python-Variante keine reinen Body-Änderungen. Benannte
# Grenze, kein stiller Kompromiss.

_TS_FUNC_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\(")
_TS_CONST_ARROW_RE = re.compile(r"^\s*(?:export\s+)?const\s+(\w+)\s*(?::[^=]+)?=\s*(?:async\s*)?\(")
_TS_CLASS_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+(\w+)")


def _extract_signature(source_lines: list[str], node: ast.AST) -> str:
    """Signatur eines `ast`-Knotens als Quelltext, auch bei mehrzeiligen Headern.

    Zählt Klammertiefe zeilenweise und stoppt an der ersten Zeile, die wieder
    auf Tiefe 0 ist und einen Doppelpunkt enthält — eine Heuristik, die an
    Default-Strings mit Klammern scheitern kann (dokumentierte Grenze), für
    normale Funktions- und Klassenköpfe aber zuverlässig ist.
    """
    start = node.lineno
    depth = 0
    header_lines: list[str] = []
    for i in range(start - 1, len(source_lines)):
        line = source_lines[i]
        header_lines.append(line)
        code_part = line.split("#", 1)[0]
        depth += code_part.count("(") - code_part.count(")")
        if depth <= 0 and ":" in code_part:
            break
    return "\n".join(header_lines).rstrip()


def detect_python_symbols(after_text: str, changed_ranges: list[tuple[int, int]]) -> list[dict]:
    """Funktionen/Klassen, deren Zeilenbereich einen geänderten Bereich überlappt."""
    if not changed_ranges or not after_text:
        return []
    try:
        tree = ast.parse(after_text)
    except SyntaxError:
        return []
    lines = after_text.splitlines()
    symbols: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        node_end = getattr(node, "end_lineno", node.lineno)
        overlaps = any(not (node_end < start or node.lineno > end) for start, end in changed_ranges)
        if not overlaps:
            continue
        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        symbols.append({
            "name": node.name, "kind": kind,
            "signature": _extract_signature(lines, node), "lineno": node.lineno,
        })
    return symbols


def detect_ts_symbols(after_text: str, changed_ranges: list[tuple[int, int]]) -> list[dict]:
    """Grep-basierte Symbolsuche für TS/JS — nur Deklarationszeilen, keine Scope-Analyse."""
    if not changed_ranges or not after_text:
        return []
    lines = after_text.splitlines()
    symbols: list[dict] = []
    for lineno, line in enumerate(lines, start=1):
        if not any(start <= lineno <= end for start, end in changed_ranges):
            continue
        for regex, kind in ((_TS_FUNC_RE, "function"), (_TS_CONST_ARROW_RE, "function"), (_TS_CLASS_RE, "class")):
            match = regex.match(line)
            if match:
                symbols.append({"name": match.group(1), "kind": kind, "signature": line.strip(), "lineno": lineno})
                break
    return symbols


def detect_symbols(path: str, after_text: str | None, changed_ranges: list[tuple[int, int]]) -> list[dict]:
    if after_text is None:
        return []
    if path.endswith(".py"):
        return detect_python_symbols(after_text, changed_ranges)
    if path.endswith((".ts", ".tsx", ".js", ".jsx")):
        return detect_ts_symbols(after_text, changed_ranges)
    return []


# --- Aufrufer-Suche ----------------------------------------------------------

def _call_regex(name: str) -> re.Pattern:
    return re.compile(rf"\b{re.escape(name)}\s*\(")


def _iter_code_files(repo: Path):
    for path in sorted(repo.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in CODE_SUFFIXES:
            continue
        rel_parts = path.relative_to(repo).parts[:-1]
        if any(part in EXCLUDED_DIR_NAMES for part in rel_parts):
            continue
        yield path


def _resolve_caller_signature(repo: Path, rel_path: str, lineno: int) -> str | None:
    """Signatur der Funktion, die eine Aufrufstelle umschließt — bestmöglich."""
    path = repo / rel_path
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    if rel_path.endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return None
        lines = text.splitlines()
        best: ast.AST | None = None
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            end = getattr(node, "end_lineno", node.lineno)
            if node.lineno <= lineno <= end and (best is None or node.lineno > best.lineno):
                best = node
        return _extract_signature(lines, best) if best is not None else None

    if rel_path.endswith((".ts", ".tsx", ".js", ".jsx")):
        lines = text.splitlines()
        for i in range(min(lineno, len(lines)) - 1, -1, -1):
            for regex in (_TS_FUNC_RE, _TS_CONST_ARROW_RE):
                if regex.match(lines[i]):
                    return lines[i].strip()
        return None
    return None


def find_callers(
    repo: Path, symbol_name: str, definition_path: str,
    definition_lineno: int | None = None, cap: int = MAX_CALLERS,
) -> dict:
    """Aufrufer eines Symbols repoweit finden — grep-basiert für beide Sprachen
    (R16), gedeckelt mit einer benannten Grenze statt stillem Abschneiden.
    """
    pattern = _call_regex(symbol_name)
    matches: list[dict] = []
    for path in _iter_code_files(repo):
        rel = path.relative_to(repo).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if rel == definition_path and definition_lineno is not None and lineno == definition_lineno:
                continue  # die Definition selbst ist kein Aufrufer
            if pattern.search(line):
                matches.append({"file": rel, "line": lineno, "text": line.strip()})

    total = len(matches)
    shown = matches[:cap]
    for entry in shown:
        entry["caller_signature"] = _resolve_caller_signature(repo, entry["file"], entry["line"])

    note = f"{total - cap} weitere Aufrufer nicht gezeigt (Obergrenze {cap})." if total > cap else None
    return {"total": total, "shown": shown, "note": note}


# --- Vereinfachungslinse: Projekt-Konventionen und Umgebungscode -----------

CONVENTION_MARKER_FILES = (
    "pyproject.toml", "ruff.toml", ".ruff.toml", "setup.cfg",
    "tsconfig.json", ".eslintrc.json", ".eslintrc.js", ".eslintrc.cjs",
)


def gather_conventions(repo: Path, changed_paths: list[str]) -> dict:
    """Umgebungscode als Zeiger (Dateinamen, nicht Inhalt) plus vorhandene
    Konventions-Marker — womit sich die Änderung messen lassen muss.
    """
    changed_set = set(changed_paths)
    sibling_files: dict[str, dict] = {}
    seen_dirs: set[str] = set()
    for rel in changed_paths:
        dir_rel = str(PurePosixPath(rel).parent)
        if dir_rel in seen_dirs:
            continue
        seen_dirs.add(dir_rel)
        dir_path = repo if dir_rel == "." else repo / dir_rel
        if not dir_path.is_dir():
            continue
        names = sorted(
            p.name for p in dir_path.iterdir()
            if p.is_file() and (p.name if dir_rel == "." else f"{dir_rel}/{p.name}") not in changed_set
        )
        capped = names[:MAX_SIBLING_FILES]
        note = None
        if len(names) > MAX_SIBLING_FILES:
            note = f"{len(names) - MAX_SIBLING_FILES} weitere Dateien nicht gezeigt (Obergrenze {MAX_SIBLING_FILES})."
        sibling_files[dir_rel] = {"files": capped, "note": note}

    markers = [name for name in CONVENTION_MARKER_FILES if (repo / name).is_file()]
    return {"sibling_files": sibling_files, "convention_markers": markers}


# --- Paket-Zusammenbau -------------------------------------------------------

def _full_after_content(repo: Path, mode: str, head: str | None, path: str) -> str | None:
    """Ungekürzter Nachher-Inhalt für die Symbolerkennung — nicht der ggf.
    gekappte `after`-Wert aus `list_changed_files`, sonst würde `ast.parse`
    auf abgeschnittenem Quelltext scheitern oder Symbole jenseits der
    Kappungsgrenze übersehen."""
    if mode == "uncommitted":
        return _content_in_worktree(repo, path)
    return _content_at_ref(repo, head, path)  # type: ignore[arg-type]


def build_context(repo: Path, args: argparse.Namespace) -> dict:
    _require_git_repo(repo)
    mode, base, head, raw_range = resolve_range(args.range)
    files = list_changed_files(repo, mode, base, head)

    diff_files = [
        {
            "path": f["path"], "old_path": f["old_path"], "status": f["status"],
            "insertions": f["insertions"], "deletions": f["deletions"],
        }
        for f in files
    ]
    diff_summary = {
        "files": diff_files,
        "total_files": len(files),
        "total_insertions": sum(f["insertions"] for f in files),
        "total_deletions": sum(f["deletions"] for f in files),
        "empty": len(files) == 0,
    }

    findings: list[dict] = []
    if diff_summary["empty"]:
        findings.append({"id": "empty_diff", "message": EMPTY_DIFF_MESSAGE})

    soll = resolve_soll(repo, mode, base, head, args.pr_description, args.pr_description_file)
    if not diff_summary["empty"] and soll["source"] == "none":
        findings.append({"id": "no_soll", "message": NO_SOLL_MESSAGE})

    decisions = read_decisions(repo)

    correctness_files = []
    symbols: list[dict] = []
    for f in files:
        correctness_files.append({
            "path": f["path"], "status": f["status"],
            "before": f["before"], "before_truncated": f["before_truncated"], "before_note": f["before_note"],
            "after": f["after"], "after_truncated": f["after_truncated"], "after_note": f["after_note"],
            "patch": f["patch"], "patch_truncated": f["patch_truncated"],
        })
        if f["status"] in ("deleted", "binary"):
            # Kein Nachher-Zustand, aus dem sich Symbolgrenzen ableiten
            # ließen — bekannte Grenze, siehe docs/known-limits.md.
            continue
        full_after = _full_after_content(repo, mode, head, f["path"])
        touched = detect_symbols(f["path"], full_after, f["changed_ranges_after"])
        for sym in touched:
            callers = find_callers(repo, sym["name"], f["path"], definition_lineno=sym["lineno"])
            symbols.append({**sym, "file": f["path"], "callers": callers})

    conventions = gather_conventions(repo, [f["path"] for f in files])

    packages = {
        "spec_compliance": {
            "soll": soll,
            "decisions": decisions,
            "diff_files": [f["path"] for f in files],
        },
        "correctness": {
            "files": correctness_files,
            "symbols": symbols,
        },
        "simplification": {
            "conventions": conventions,
            "diff_files": [f["path"] for f in files],
        },
    }

    generated_cmd = "python skills/review-context/scripts/collect_context.py"
    if raw_range:
        generated_cmd += f" --range {raw_range}"

    return {
        "_meta": {"skill": "review-context", "schema": SCHEMA_VERSION, "generated": generated_cmd},
        "range": {"mode": mode, "base": base, "head": head, "raw": raw_range},
        "diff": diff_summary,
        "findings": findings,
        "packages": packages,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kontextpaket für /code-review sammeln")
    parser.add_argument(
        "--range",
        help="Git-Range BASIS..ZIEL (z. B. HEAD~1..HEAD, main..feature/x). "
             "Ohne Angabe: Arbeitsverzeichnis gegen HEAD (uncommitted).",
    )
    parser.add_argument("--pr-description", help="PR-Beschreibung als Text — Soll-Quelle im Fremd-Modus")
    parser.add_argument("--pr-description-file", help="Datei mit der PR-Beschreibung")
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    try:
        context = build_context(args.repo, args)
    except CollectError as exc:
        print(f"Sammeln gescheitert: {exc}", file=sys.stderr)
        return 1

    target = args.repo / CACHE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(context, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Kontextpaket für {context['diff']['total_files']} Datei(en) -> {CACHE_PATH}")
    for finding in context["findings"]:
        print(f"Befund: {finding['message']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
