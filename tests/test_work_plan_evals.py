"""Strukturprüfung der work-plan-evals.json. Läuft keine Evals — kein Agentenlauf.

work-plan ist Tier 1 ohne eigenes Skript: Die Evals sind neben dem Lint von subagent-dev
das einzige Messinstrument. Die Tests hier fangen den Fehler, der die Evals lautlos
entwerten würde — dass ihre Regexe an einem Plan vorbeigreifen, der dem Template folgt,
oder dass ein Kriterien-Titel nicht mehr zu seiner Fixture passt.
"""

import re

from conftest import REPO_ROOT, load_script
from evalkit.assertions import ARTIFACT_HEADER_RE
from evalkit.schema import load_evals

ptt = load_script("skills/subagent-dev/scripts/plan_to_tasks.py")

EVALS_PATH = REPO_ROOT / "evals" / "work-plan" / "evals.json"
FIXTURES = REPO_ROOT / "evals" / "fixtures"
TEMPLATE = REPO_ROOT / "skills" / "work-plan" / "assets" / "plan-template.md"
PLAN_GLOB = "docs/plans/*.md"
FOUR_IDS = (
    "anti-ceremony-one-file-change-gets-no-plan",
    "plan-from-feature-spec-covers-criteria",
    "verification-task-uses-repo-command",
    "plan-from-finding-records-assignment",
)


def _evals():
    return {ev.id: ev for ev in load_evals(EVALS_PATH)}


def _file_patterns(ev) -> list[str]:
    return [a.pattern for a in ev.must if a.type == "file_matches"]


def _template_plan(source: str, *, criteria=(), command="make ci") -> str:
    """Ein Plan, wie die Skill ihn aus dem Template schreibt: Quelle ersetzt, ein
    Code-Task je Kriterium, Verifikations-Task mit dem Befehl des Repos zuletzt."""
    text = TEMPLATE.read_text(encoding="utf-8")
    text = re.sub(r"(?ms)^\*\*Auftrag:\*\*.*?(?=\n\n)", source, text)
    text = text.replace("laufen\n      lassen", f"laufen\n      lassen: `{command}`")
    tasks = []
    for n, title in enumerate(criteria, start=3):
        tasks.append(f"""### Task {n}: {title}

**Files:**
- Modify: `src/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `fn:write_csv(rows, path)`
- Produces: (nichts Neues)

- [ ] **Step 1: Test schreiben** — das Kriterium als Test.
- [ ] **Step 2: Commit.**

""")
    final = 3 + len(tasks)
    text = text.replace("### Task 3: Verifikation", "".join(tasks) + f"### Task {final}: Verifikation")
    return text


def test_evals_file_loads_with_four_contract_evals():
    evals = load_evals(EVALS_PATH)
    assert tuple(ev.id for ev in evals) == FOUR_IDS
    assert all(ev.eval_class == "contract" for ev in evals)


def test_anti_ceremony_eval_writes_no_plan_and_names_the_threshold():
    """Spec 00 §2 Pflicht. Das Fehlen der Datei allein diskriminiert nicht — der
    Wortlaut der Schwelle schon."""
    anti = _evals()["anti-ceremony-one-file-change-gets-no-plan"]
    by_type = {a.type: a for a in anti.must}
    assert by_type["file_absent"].path == PLAN_GLOB
    assert by_type["output_matches"].pattern == "Kein Plan nötig"
    assert "git_head_unchanged" in by_type


def test_fixtures_carry_git_and_no_plans_dir():
    for ev in load_evals(EVALS_PATH):
        fixture = FIXTURES / ev.fixture
        assert (fixture / "fixture.json").is_file(), ev.fixture
        assert '"git": true' in (fixture / "fixture.json").read_text(encoding="utf-8"), ev.fixture
        assert not (fixture / "docs" / "plans").exists(), ev.fixture


def test_criteria_titles_of_wp_spec_are_asserted_verbatim():
    """Die drei Titel stehen in der Fixture-Spec und als wörtliches Muster in Eval 2 —
    benennt jemand ein Kriterium um, fällt dieser Test, nicht der Agentenlauf."""
    spec = (FIXTURES / "wp-spec" / "docs" / "specs" / "wip" / "export.md").read_text(encoding="utf-8")
    titles = ptt.feature_spec_criteria(spec)
    assert titles is not None and len(titles) == 3
    patterns = _file_patterns(_evals()["plan-from-feature-spec-covers-criteria"])
    for title in titles:
        assert title in patterns, title


def test_template_header_satisfies_the_artifact_header_primitive():
    first = TEMPLATE.read_text(encoding="utf-8").splitlines()[0]
    match = ARTIFACT_HEADER_RE.match(first)
    assert match and match.group("skill") == "work-plan"


def test_must_patterns_grip_template_shaped_plans():
    """Die Muster der Evals 2 bis 4 greifen an Plänen nach dem Template, und diese
    Pläne sind lint-sauber — Eval 2 einschließlich der Coverage gegen die Fixture-Spec."""
    evals = _evals()
    spec_path = FIXTURES / "wp-spec" / "docs" / "specs" / "wip" / "export.md"
    titles = ptt.feature_spec_criteria(spec_path.read_text(encoding="utf-8"))
    plans = {
        "plan-from-feature-spec-covers-criteria": _template_plan(
            "**Spec:** `docs/specs/wip/export.md`", criteria=titles),
        "verification-task-uses-repo-command": _template_plan(
            "**Auftrag:** „CSV-Export der Berichte mit CLI-Option `--csv`.“"),
        "plan-from-finding-records-assignment": _template_plan(
            "**Auftrag:** Zyklus aus `ARCHITECTURE.md`, Abschnitt Befunde."),
    }
    for eval_id, plan in plans.items():
        for pattern in _file_patterns(evals[eval_id]):
            assert re.search(pattern, plan, re.MULTILINE), f"{eval_id}: {pattern!r}"
        assert ptt.plan_kind(plan) == "work-plan"


def test_spec_shaped_plan_is_lint_clean_with_coverage(tmp_path):
    spec_dir = tmp_path / "docs" / "specs" / "wip"
    spec_dir.mkdir(parents=True)
    spec = FIXTURES / "wp-spec" / "docs" / "specs" / "wip" / "export.md"
    (spec_dir / "export.md").write_text(spec.read_text(encoding="utf-8"), encoding="utf-8")
    titles = ptt.feature_spec_criteria(spec.read_text(encoding="utf-8"))
    plan = tmp_path / "docs" / "plans" / "2026-10-13-export.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(_template_plan("**Spec:** `docs/specs/wip/export.md`", criteria=titles), encoding="utf-8")
    report = ptt.lint_report(plan.read_text(encoding="utf-8"), plan)
    assert [f.message for f in report.findings] == []
    assert report.coverage["status"] == "checked"


def test_every_plan_path_is_the_plans_glob():
    for ev in load_evals(EVALS_PATH):
        for a in list(ev.must) + list(ev.must_not):
            if a.type not in ("output_matches", "git_head_unchanged", "file_unchanged"):
                assert a.path == PLAN_GLOB, f"{ev.id}: {a.path}"
