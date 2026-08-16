"""Mechanische Assertions — falsifizierbar, ohne Judge, ohne Kosten. Tier 1: nur Stdlib."""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from evalkit.schema import Assertion, JUDGE_TYPE

# Kopfzeilen-Format aus Spec 00 §1, hier verbindlich gemacht.
ARTIFACT_HEADER_RE = re.compile(
    r"^(?:<!--|#)\s*skill:\s*(?P<skill>[a-z0-9][a-z0-9-]*)\s*\|"
    r"\s*schema:\s*(?P<schema>\d+)\s*\|"
    r"\s*generated:\s*(?P<cmd>.+?)\s*(?:-->)?\s*$"
)

GIT_HEAD_KEY = "__git_head__"

# Pfade, die evalkit.workspace.snapshot() grundsätzlich nie beobachtet (.git/ die
# eigene Fixture-Historie, .claude/ die installierte Skill). Hier definiert statt in
# evalkit.workspace, damit check() unten dieselbe Grenze kennt, ohne einen Zyklus
# workspace -> assertions -> workspace einzugehen (workspace importiert von hier).
EXCLUDED_PREFIXES = (".git/", ".claude/")


class MechanicalCheckError(RuntimeError):
    """Eine Assertion, die hier nicht mechanisch prüfbar ist (z. B. judge)."""


@dataclass(frozen=True)
class AssertionResult:
    ok: bool
    detail: str


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_git_head(root: Path) -> str | None:
    """SHA von HEAD, oder None wenn kein Repo / kein Commit.

    Der Testpfad .git/HEAD_SHA existiert, damit Unit-Tests ohne echtes Repo
    auskommen; im echten Lauf gewinnt immer `git rev-parse`.
    """
    probe = root / ".git" / "HEAD_SHA"
    if probe.is_file():
        return probe.read_text(encoding="utf-8").strip()
    try:
        done = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def check(assertion: Assertion, root: Path, baseline: dict[str, str], output: str = "") -> AssertionResult:
    """Prüfe eine mechanische Assertion gegen den Workspace.

    `baseline` ist der Snapshot aus evalkit.workspace.prepare(): relpath -> sha256,
    plus der Sonderschlüssel `__git_head__`. `output` ist die Agent-Ausgabe — nötig,
    weil manche Contracts sich auf das Gesagte beziehen ("fragt nach, statt anzulegen").

    Ein Pfad unter EXCLUDED_PREFIXES (.git/, .claude/) wirft MechanicalCheckError statt
    ein Urteil zu fällen: der Workspace-Snapshot beobachtet diesen Bereich grundsätzlich
    nicht, eine Assertion darauf wäre sonst still falsch (z. B. `file_unchanged` auf
    einer unveränderten Datei unter .claude/, die fälschlich "nicht in der Baseline"
    meldet, weil die Baseline diesen Bereich nie enthielt).
    """
    if assertion.type == JUDGE_TYPE:
        raise MechanicalCheckError("judge-Assertions gehören zu evalkit.judge, nicht hierher")

    if assertion.type == "output_matches":
        hit = re.search(assertion.pattern, output, re.MULTILINE)
        return AssertionResult(bool(hit), f"Agent-Ausgabe: Muster {assertion.pattern!r} {'gefunden' if hit else 'nicht gefunden'}")

    if assertion.type == "git_head_unchanged":
        before = baseline.get(GIT_HEAD_KEY)
        after = current_git_head(root)
        if before is None:
            return AssertionResult(False, "kein Git-HEAD in der Baseline — Fixture ohne Repo?")
        if before == after:
            return AssertionResult(True, f"HEAD unverändert ({before[:8]})")
        return AssertionResult(False, f"HEAD verändert: {before[:8]} → {(after or 'None')[:8]}")

    for prefix in EXCLUDED_PREFIXES:
        if assertion.path.startswith(prefix):
            raise MechanicalCheckError(
                f"{assertion.path}: liegt unter {prefix!r} — dieser Bereich wird vom "
                f"Workspace-Snapshot grundsätzlich nicht beobachtet (siehe "
                f"evalkit.assertions.EXCLUDED_PREFIXES), eine Assertion darauf ist "
                f"ungeeignet und nicht bloß unerfüllt"
            )

    target = root / assertion.path
    exists = target.is_file()

    if assertion.type == "file_exists":
        return AssertionResult(exists, f"{assertion.path} {'existiert' if exists else 'existiert nicht'}")

    if assertion.type == "file_absent":
        return AssertionResult(not exists, f"{assertion.path} {'existiert (unerwünscht)' if exists else 'fehlt wie erwartet'}")

    if not exists:
        return AssertionResult(False, f"{assertion.path} existiert nicht")

    if assertion.type == "file_matches":
        text = target.read_text(encoding="utf-8", errors="replace")
        hit = re.search(assertion.pattern, text, re.MULTILINE)
        return AssertionResult(bool(hit), f"{assertion.path}: Muster {assertion.pattern!r} {'gefunden' if hit else 'nicht gefunden'}")

    if assertion.type == "file_max_lines":
        count = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
        return AssertionResult(count <= assertion.max_lines, f"{assertion.path}: {count} Zeilen (erlaubt {assertion.max_lines})")

    if assertion.type == "file_unchanged":
        before = baseline.get(assertion.path)
        if before is None:
            return AssertionResult(False, f"{assertion.path}: nicht in der Baseline — vor dem Lauf existierte die Datei nicht")
        after = file_sha256(target)
        return AssertionResult(before == after, f"{assertion.path}: {'unverändert' if before == after else 'verändert'}")

    if assertion.type == "artifact_header":
        for line in target.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                ok = bool(ARTIFACT_HEADER_RE.match(line.strip()))
                return AssertionResult(ok, f"{assertion.path}: Kopfzeile {'korrekt' if ok else 'fehlt oder falsch formatiert'} ({line.strip()[:60]!r})")
        return AssertionResult(False, f"{assertion.path}: leer, keine Kopfzeile")

    raise MechanicalCheckError(f"kein Prüfpfad für Typ {assertion.type!r}")
