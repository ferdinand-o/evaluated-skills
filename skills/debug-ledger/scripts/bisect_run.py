#!/usr/bin/env python3
"""`git bisect run` um ein Repro-Kommando kapseln. Tier 1: nur Stdlib + git-CLI.

Automatisiert die komplette Bisektion zwischen einer bekannt guten Referenz und
einer bekannt schlechten. Das Repro-Kommando entscheidet über den Exit-Code
(0 = gut, != 0 = schlecht) — dieselbe Konvention wie `git bisect run` selbst.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path

FIRST_BAD_RE = re.compile(r"^(?P<hash>[0-9a-f]{7,40}) is the first bad commit$", re.MULTILINE)


class BisectError(RuntimeError):
    """Ein git-bisect-Schritt ist an einer verständlichen Ursache gescheitert."""


def is_git_repo(repo: Path) -> bool:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo, capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0 and done.stdout.strip() == "true"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    try:
        done = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, timeout=300, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BisectError(f"git {' '.join(args)} konnte nicht gestartet werden: {exc}") from exc
    if done.returncode != 0:
        raise BisectError(f"git {' '.join(args)} fehlgeschlagen: {done.stderr.strip()}")
    return done


def _reset_quietly(repo: Path) -> None:
    """Best-effort `git bisect reset` — kein Fehler, falls keine Bisektion läuft."""
    subprocess.run(["git", "bisect", "reset"], cwd=repo, capture_output=True, text=True, timeout=60, check=False)


def run_bisect(repo: Path, good: str, bad: str, command: str) -> tuple[str | None, str]:
    """Führt die Bisektion aus. Liefert (Culprit-Hash oder None, roher Output)."""
    _reset_quietly(repo)  # eine hängengebliebene Bisektion aus einem Vorlauf beenden

    _git(repo, "bisect", "start")
    _git(repo, "bisect", "bad", bad)
    good_result = _git(repo, "bisect", "good", good)

    args = shlex.split(command)
    run_result = subprocess.run(
        ["git", "bisect", "run", *args], cwd=repo, capture_output=True, text=True, timeout=1800, check=False,
    )
    full_output = "\n".join(c for c in (good_result.stdout, run_result.stdout, run_result.stderr) if c)

    match = FIRST_BAD_RE.search(full_output)
    culprit = match.group("hash") if match else None
    return culprit, full_output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="debug-ledger: git bisect um ein Repro-Kommando kapseln")
    parser.add_argument("--good", required=True, help="bekannt guter Commit/Tag/Ref")
    parser.add_argument("--bad", required=True, help="bekannt schlechter Commit/Tag/Ref, z. B. HEAD")
    parser.add_argument("--command", required=True, help="Repro-Kommando; Exit 0 = gut, != 0 = schlecht")
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    if not is_git_repo(args.repo):
        print(f"debug-ledger: kein Git-Repository unter {args.repo} — bisect nicht verfügbar", file=sys.stderr)
        return 2

    try:
        culprit, output = run_bisect(args.repo, args.good, args.bad, args.command)
    except BisectError as exc:
        print(f"debug-ledger: {exc}", file=sys.stderr)
        return 1
    finally:
        # Repo verlässt diese Funktion immer im Ausgangszustand, egal ob die
        # Bisektion einen Culprit fand, scheiterte oder eine Exception warf.
        _reset_quietly(args.repo)

    if culprit is None:
        print("Kein eindeutiger Culprit gefunden. Roh-Output von `git bisect run`:")
        print(output)
        return 1

    print(f"Erster schlechter Commit: {culprit}")
    print("Ins Evidenz-Log des Ledgers übernehmen (Kommando + Ergebnis).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
