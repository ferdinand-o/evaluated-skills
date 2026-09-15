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
    # Baseline-Lauf ohne installierte Skill (`--without-skill`, Spec 18): dieselben
    # Assertions, umgekehrte Bedeutung — ein grünes Ergebnis heißt, der Eval misst
    # nichts, was die Skill beiträgt. Die Markierung und der Exit-Code lesen das Feld;
    # bestehende Aufrufer, die es nicht setzen, merken nichts.
    baseline: bool = False


def _mark(result: EvalResult) -> str:
    if result.skipped:
        return "[SKIP]"
    if result.baseline:
        return "[GRÜN OHNE SKILL]" if result.passed else "[ROT OHNE SKILL]"
    return "[PASS]" if result.passed else "[FAIL]"


def format_report(results: Sequence[EvalResult]) -> str:
    lines: list[str] = []
    for result in results:
        suffix = f" — {result.note}" if result.note else ""
        if result.baseline and result.passed and not result.skipped:
            suffix = " — misst nichts" + (f" ({result.note})" if result.note else "")
        lines.append(f"{_mark(result)} {result.eval_id}{suffix}")
        for failure in result.failures:
            lines.append(f"       {failure}")

    skipped = sum(1 for r in results if r.skipped)
    lines.append("")
    if any(r.baseline for r in results):
        green = sum(1 for r in results if r.baseline and r.passed and not r.skipped)
        red = sum(1 for r in results if r.baseline and not r.passed and not r.skipped)
        lines.append(f"{green} grün ohne Skill — messen nichts, {red} rot ohne Skill, {skipped} übersprungen")
    else:
        passed = sum(1 for r in results if r.passed and not r.skipped)
        failed = sum(1 for r in results if not r.passed and not r.skipped)
        lines.append(f"{passed} bestanden, {failed} gefallen, {skipped} übersprungen")
    return "\n".join(lines)


def exit_code(results: Sequence[EvalResult]) -> int:
    """0 = alles grün, 1 = mindestens ein Eval gefallen, 2 = Harness-Fehler.

    Im Baseline-Modus (`baseline=True`) ist die Bedeutung umgekehrt: 1, sobald ein
    Eval ohne Skill grün war (er misst nichts), 0, wenn alle rot waren. Ein
    übersprungener Lauf mit Grund in `failures` gibt in beiden Modi 2 — ein Grund nur
    in `note` gäbe 0, deshalb legt der Runner ihn in `failures`.
    """
    if any(r.skipped and r.failures for r in results):
        return 2
    if any(r.baseline and r.passed and not r.skipped for r in results):
        return 1
    if any(not r.baseline and not r.passed and not r.skipped for r in results):
        return 1
    return 0
