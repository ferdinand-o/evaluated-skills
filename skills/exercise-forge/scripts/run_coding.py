#!/usr/bin/env python3
"""Mechanischer Testlauf für Coding-Aufgaben in exercise-forge.

Tier 2: braucht pytest im aufgerufenen Python-Interpreter. Im Eval-Workspace
ist das nicht garantiert (Rulings D1) — fehlt pytest, meldet dieses Skript
das benannt und markiert die Aufgabe als 'unverified', nie als 'bestanden'
(Rulings A4, Spec 00 §3 Sichtbarkeits-Regel).

Führt Musterlösung und Blind-Lösung nie per `import` aus (Rulings A3) —
beide laufen als eigener `python -m pytest`-Subprozess in einem
Wegwerf-Verzeichnis.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_TIMEOUT = 60


def pytest_available(python: str = sys.executable) -> bool:
    try:
        done = subprocess.run(
            [python, "-m", "pytest", "--version"],
            capture_output=True, text=True, timeout=DEFAULT_TIMEOUT, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def run_pytest_against(solution_code: str, test_code: str, workdir: Path, *, python: str = sys.executable) -> dict:
    """Schreibe `solution.py` + `test_solution.py` nach `workdir` und führe
    `python -m pytest -q` darauf aus. `test_code` muss `from solution import …`
    verwenden (Konvention aus `references/task-schemas.md`)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "solution.py").write_text(solution_code, encoding="utf-8")
    (workdir / "test_solution.py").write_text(test_code, encoding="utf-8")

    try:
        done = subprocess.run(
            [python, "-m", "pytest", "-q", "test_solution.py"],
            cwd=str(workdir), capture_output=True, text=True, timeout=DEFAULT_TIMEOUT, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"passed": False, "detail": f"Timeout nach {DEFAULT_TIMEOUT}s"}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"passed": False, "detail": f"pytest nicht startbar: {exc}"}

    tail = "\n".join((done.stdout + done.stderr).strip().splitlines()[-15:])
    return {"passed": done.returncode == 0, "detail": tail}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _verdict(status: str, detail: str) -> dict:
    return {"status": status, "method": "blind_solve_coding", "detail": detail, "checked_at": _now_iso()}


def verify_coding(exercise: dict, blind_solution: str | None, *, python: str = sys.executable) -> dict:
    """Wahrheitstabelle aus Spec 13: Musterlösung muss bestehen, sonst ist die
    Aufgabe fehlerhaft. Erst danach entscheidet die Blind-Lösung — scheitert
    sie an bestehender Musterlösung, sind die Tests verdächtig überspezifiziert,
    nicht automatisch die Blind-Lösung falsch."""
    if not pytest_available(python=python):
        return _verdict("unverified", "pytest nicht verfügbar - Testlauf übersprungen")

    with tempfile.TemporaryDirectory() as td:
        model_result = run_pytest_against(exercise["model_solution"], exercise["test_suite"], Path(td) / "model", python=python)
    if not model_result["passed"]:
        return _verdict("unverified", f"Musterlösung fällt durch eigene Tests - Aufgabe fehlerhaft: {model_result['detail']}")

    if blind_solution is None:
        return _verdict("unverified", "Musterlösung besteht die Tests, aber keine Blind-Lösung übergeben - Blind-Gate unvollständig")

    with tempfile.TemporaryDirectory() as td:
        blind_result = run_pytest_against(blind_solution, exercise["test_suite"], Path(td) / "blind", python=python)
    if blind_result["passed"]:
        return _verdict("verified", "Musterlösung und Blind-Lösung bestehen beide die Tests.")
    return _verdict(
        "suspicious",
        f"Blind-Lösung fällt durch, obwohl Musterlösung besteht - Tests könnten überspezifiziert sein: {blind_result['detail']}",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Testet Muster- und Blind-Lösung einer Coding-Aufgabe")
    parser.add_argument("--exercises", type=Path, required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--blind-file", type=Path, help="Datei mit der Blind-Lösung")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--update", action="store_true", help="Ergebnis in die exercises.json zurückschreiben")
    args = parser.parse_args(argv)

    if not args.exercises.is_file():
        print(f"Aufgaben-JSON nicht gefunden: {args.exercises}", file=sys.stderr)
        return 2

    data = json.loads(args.exercises.read_text(encoding="utf-8"))
    exercises = data.get("exercises", [])
    match = next((e for e in exercises if e.get("id") == args.id), None)
    if match is None:
        print(f"Aufgabe {args.id!r} nicht gefunden in {args.exercises}", file=sys.stderr)
        return 2

    blind_solution = args.blind_file.read_text(encoding="utf-8") if args.blind_file else None
    verification = verify_coding(match, blind_solution, python=args.python)

    if args.update:
        match["verification"] = verification
        args.exercises.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({"id": args.id, "verification": verification}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
