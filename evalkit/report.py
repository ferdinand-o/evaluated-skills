"""Ergebnisse formatieren und in einen Exit-Code übersetzen."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class EvalResult:
    eval_id: str
    passed: bool
    failures: tuple[str, ...]
    skipped: bool = False
    note: str = ""


def format_report(results: Sequence[EvalResult]) -> str:
    lines: list[str] = []
    for result in results:
        if result.skipped:
            mark = "SKIP"
        elif result.passed:
            mark = "PASS"
        else:
            mark = "FAIL"
        suffix = f" — {result.note}" if result.note else ""
        lines.append(f"[{mark}] {result.eval_id}{suffix}")
        for failure in result.failures:
            lines.append(f"       {failure}")

    passed = sum(1 for r in results if r.passed and not r.skipped)
    failed = sum(1 for r in results if not r.passed and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    lines.append("")
    lines.append(f"{passed} bestanden, {failed} gefallen, {skipped} übersprungen")
    return "\n".join(lines)


def exit_code(results: Sequence[EvalResult]) -> int:
    """0 = alles grün, 1 = mindestens ein Eval gefallen, 2 = Harness-Fehler."""
    if any(r.skipped and r.failures for r in results):
        return 2
    if any(not r.passed and not r.skipped for r in results):
        return 1
    return 0
