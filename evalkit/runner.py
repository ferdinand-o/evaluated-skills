"""Orchestrierung: Workspace bauen, Agent laufen lassen, bewerten, berichten."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from evalkit.assertions import check
from evalkit.dispatch import DEFAULT_TIMEOUT, run_agent
from evalkit.judge import JudgeError, judge
from evalkit.report import EvalResult, exit_code, format_report
from evalkit.schema import JUDGE_TYPE, Eval, EvalSchemaError, load_evals
from evalkit.workspace import WorkspaceError, dump_changed_files, prepare

REPO_ROOT = Path(__file__).resolve().parent.parent


def grade(ev: Eval, root: Path, baseline: dict[str, str], verdicts: dict[str, bool], output: str = "") -> EvalResult:
    """Bestanden = alle must erfüllt und kein must_not verletzt (Spec 00 §2)."""
    failures: list[str] = []

    for assertion in ev.must:
        if assertion.type == JUDGE_TYPE:
            if assertion.claim not in verdicts:
                failures.append(f"must: kein Urteil zu {assertion.claim!r}")
            elif not verdicts[assertion.claim]:
                failures.append(f"must: Judge verneint {assertion.claim!r}")
            continue
        result = check(assertion, root, baseline, output)
        if not result.ok:
            failures.append(f"must: {result.detail}")

    for assertion in ev.must_not:
        if assertion.type == JUDGE_TYPE:
            # Achtung auf die Polung: Der Judge urteilt im Zweifel false, und false
            # lässt ein must_not bestehen. Behauptungen für must_not deshalb so
            # formulieren, dass der Zweifel gegen den Verstoß spricht.
            if assertion.claim not in verdicts:
                failures.append(f"must_not: kein Urteil zu {assertion.claim!r}")
            elif verdicts[assertion.claim]:
                failures.append(f"must_not: Judge bejaht {assertion.claim!r}")
            continue
        result = check(assertion, root, baseline, output)
        if result.ok:
            failures.append(f"must_not: {result.detail}")

    return EvalResult(eval_id=ev.id, passed=not failures, failures=tuple(failures))


def _claims(ev: Eval) -> list[str]:
    return [a.claim for a in (*ev.must, *ev.must_not) if a.type == JUDGE_TYPE]


# Spec 00 verlangt für Artefakte außerhalb eines Repos die Ablage unter
# ~/.skills/<skill>/. Der Harness isoliert HOME nicht (siehe docs/known-limits.md),
# also schreibt eine Skill, deren Fixture kein .git mitbringt, regelkonform ins
# echte Home-Verzeichnis des Aufrufers — außerhalb jeder Assertion. Genau das ist
# real passiert und fiel nur zufällig auf: sechs Evals fielen mit "Datei existiert
# nicht" durch, während die Dateien einwandfrei erzeugt worden waren, nur woanders.
HOME_SKILLS = Path.home() / ".skills"


def _home_skills_state() -> dict[str, tuple[int, int]]:
    """relpath -> (Größe, mtime_ns) für alles unter ~/.skills. Leer, wenn es fehlt."""
    state: dict[str, tuple[int, int]] = {}
    if not HOME_SKILLS.is_dir():
        return state
    for path in HOME_SKILLS.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            info = path.stat()
        except OSError:
            continue
        state[str(path.relative_to(HOME_SKILLS))] = (info.st_size, info.st_mtime_ns)
    return state


def _report_escapes(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]], eval_id: str) -> None:
    touched = sorted(rel for rel, meta in after.items() if before.get(rel) != meta)
    if not touched:
        return
    print(
        f"  WARNUNG [{eval_id}]: der Lauf hat {len(touched)} Datei(en) außerhalb des "
        f"Workspace geschrieben, unter {HOME_SKILLS}:"
    )
    for rel in touched[:10]:
        print(f"    {rel}")
    if len(touched) > 10:
        print(f"    … und {len(touched) - 10} weitere")
    print("    Diese Dateien sieht keine Assertion. Braucht die Fixture ein \"git\": true?")


UNCHECKED_VISIBILITY = "Sichtbarkeit ungeprüft (kein skills-Feld im init-Ereignis)"


def _visibility_verdict(skill_name: str, visible: frozenset[str] | None, without_skill: bool) -> tuple[str, str] | None:
    """(Grund für failures, Note) wenn der Lauf kein Ergebnis sein darf, sonst None.

    Spec 18: Ein Lauf ohne Skill, in dem sie trotzdem sichtbar war (Profil, Plugin,
    Fixture), ist keine Baseline; ein Lauf mit Skill, in dem sie fehlte (Frontmatter,
    das die CLI nicht parst; fehlgeschlagene Installation), wäre falsch rot oder
    falsch grün. Beides ist ein Harness-Fehler, nie PASS oder FAIL. `visible=None`
    heißt ungeprüft — dann bleibt das Verdikt wie ohne diese Prüfung.
    """
    if visible is None:
        return None
    if without_skill and skill_name in visible:
        return (
            f"harness: Baseline unmöglich: {skill_name} ist ohne Installation sichtbar "
            f"(Profil, Plugin oder Fixture) — der Lauf misst nicht ohne Skill",
            "Baseline unmöglich",
        )
    if not without_skill and skill_name not in visible:
        return (
            f"harness: Skill {skill_name} nicht sichtbar (Installation oder Frontmatter?) — "
            f"der Agent sah {len(visible)} Skills, diese nicht",
            "Skill nicht sichtbar",
        )
    return None


def run_one(
    ev: Eval,
    *,
    skill_dir: Path,
    fixtures_dir: Path,
    cli: str,
    timeout: int,
    keep: bool,
    skill_name: str | None = None,
    without_skill: bool = False,
) -> EvalResult:
    """Ein Eval in einem frischen Workspace. `without_skill` ist der Baseline-Lauf
    (Spec 18): dieselbe Fixture, derselbe Prompt, derselbe Judge, aber nichts
    installiert — grün heißt dann, der Eval misst nichts, was die Skill beiträgt.
    `skill_name` ist der Name, den die CLI im `skills`-Feld listet (Ordnername)."""
    skill_dir = Path(skill_dir)
    name = skill_name or skill_dir.name
    fixture_dir = fixtures_dir / ev.fixture if ev.fixture else None
    workdir = Path(tempfile.mkdtemp(prefix=f"eval-{ev.id}-"))
    home_before = _home_skills_state()
    try:
        workspace = prepare(workdir / "ws", None if without_skill else skill_dir, fixture_dir)
        transcript = run_agent(ev.prompt, workspace.root, cli=cli, timeout=timeout)
        _report_escapes(home_before, _home_skills_state(), ev.id)
        if transcript.exit_code != 0:
            note = "Timeout" if transcript.timed_out else f"Agent exit {transcript.exit_code}"
            return EvalResult(ev.id, False, (f"harness: {note}: {transcript.stderr.strip()[:200]}",), True, note, baseline=without_skill)

        # Sichtbarkeit nur am Transcript des Eval-Agenten — der Judge unten läuft in
        # einem leeren Verzeichnis und sieht naturgemäß nichts installiert.
        verdict = _visibility_verdict(name, transcript.skills, without_skill)
        if verdict is not None:
            reason, note = verdict
            return EvalResult(ev.id, False, (reason,), True, note, baseline=without_skill)
        note = "" if transcript.skills is not None else UNCHECKED_VISIBILITY

        verdicts: dict[str, bool] = {}
        claims = _claims(ev)
        if claims:
            # Der Judge läuft in einem eigenen leeren Verzeichnis, nicht im Workspace:
            # Er ist selbst ein Agent mit Schreibrechten und würde sonst genau die
            # Beobachtung verändern, die anschließend bewertet wird.
            judge_dir = workdir / "judge"
            judge_dir.mkdir(exist_ok=True)
            dump = dump_changed_files(workspace.root, workspace.baseline)
            verdicts = judge(claims, transcript.text, dump, judge_dir, cli=cli, timeout=timeout)
        result = grade(ev, workspace.root, workspace.baseline, verdicts, transcript.text)
        return replace(result, note=note, baseline=without_skill)
    except (WorkspaceError, JudgeError) as exc:
        return EvalResult(ev.id, False, (f"harness: {exc}",), True, "Harness-Fehler", baseline=without_skill)
    except Exception as exc:
        # Sicherheitsnetz: eine einzelne kaputte Fixture oder ein unerwarteter Fehler
        # darf den ganzen Batch nicht mit einem unbehandelten Traceback beenden. Der
        # Ausnahmetyp bleibt in der Meldung sichtbar, damit ein echter Harness-Bug
        # nicht als banaler Fehlschlag stillschweigend durchgewunken wird.
        return EvalResult(
            ev.id, False,
            (f"harness: unerwartete {type(exc).__name__} bei Eval {ev.id!r}: {exc}",),
            True, "Harness-Fehler", baseline=without_skill,
        )
    finally:
        if keep:
            print(f"  Workspace behalten: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval-Runner für die Skill-Sammlung (Spec 00 §2)")
    parser.add_argument("--skill", action="append", dest="skills", help="nur diese Skill (wiederholbar)")
    parser.add_argument("--class", dest="eval_class", choices=["contract", "behavior"], help="nur diese Eval-Klasse")
    parser.add_argument("--evals-dir", type=Path, default=REPO_ROOT / "evals")
    parser.add_argument("--skills-dir", type=Path, default=REPO_ROOT / "skills")
    parser.add_argument("--cli", default="claude")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--keep-workspace", action="store_true", help="Workspaces zur Diagnose behalten")
    parser.add_argument(
        "--without-skill", action="store_true",
        help="Baseline: dieselben Evals ohne installierte Skill fahren — ein Eval, der dort grün ist, "
             "misst nichts (Exit 1); Exit 0, wenn alle rot sind (Spec 18)",
    )
    args = parser.parse_args(argv)

    fixtures_dir = args.evals_dir / "fixtures"
    results: list[EvalResult] = []
    if args.without_skill:
        print("Baseline ohne Skill — grün heißt: der Eval misst nichts, was die Skill beiträgt")

    for evals_file in sorted(args.evals_dir.glob("*/evals.json")):
        skill_name = evals_file.parent.name
        if args.skills and skill_name not in args.skills:
            continue
        skill_dir = args.skills_dir / skill_name
        try:
            evals = load_evals(evals_file)
        except EvalSchemaError as exc:
            results.append(EvalResult(f"{skill_name}/evals.json", False, (f"harness: {exc}",), True, "Schema-Fehler"))
            continue

        for ev in evals:
            if args.eval_class and ev.eval_class != args.eval_class:
                continue
            print(f"→ {skill_name}/{ev.id} ({ev.eval_class})")
            results.append(run_one(
                ev, skill_dir=skill_dir, fixtures_dir=fixtures_dir,
                cli=args.cli, timeout=args.timeout, keep=args.keep_workspace,
                skill_name=skill_name, without_skill=args.without_skill,
            ))

    if not results:
        print("Keine Evals gefunden — Filter zu eng oder evals/ leer.")
        return 2

    print()
    print(format_report(results))
    return exit_code(results)
