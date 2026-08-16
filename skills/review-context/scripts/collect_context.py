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
from pathlib import Path

SCHEMA_VERSION = 1
CACHE_PATH = Path(".skills") / "cache" / "review-context.json"

MAX_FILE_CHARS = 4000
MAX_PATCH_CHARS = 4000
MAX_CALLERS = 20
MIN_COMMITS_FOR_MESSAGE_SOLL = 2
MAX_SIBLING_FILES = 15

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
