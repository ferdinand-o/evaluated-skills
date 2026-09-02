"""Strukturprüfung der impl-plan-evals.json. Läuft keine Evals — kein Agentenlauf.

impl-plan ist Tier 1 ohne eigenes Skript: Die Evals sind neben dem Repo-Test
(`tests/test_plans_lint.py`) das einzige Messinstrument. Die Tests hier fangen den
einen Fehler, der die Evals lautlos entwerten würde — dass ihre Regexe an einem
Plan vorbeigreifen, der dem Template folgt, oder dass ein Eval-Symbol (ID, Token,
Titel) nicht mehr zu seiner Fixture passt.
"""

import re
from pathlib import Path

from conftest import REPO_ROOT, load_script
from evalkit.assertions import ARTIFACT_HEADER_RE
from evalkit.schema import load_evals

ptt = load_script("skills/subagent-dev/scripts/plan_to_tasks.py")

EVALS_PATH = REPO_ROOT / "evals" / "impl-plan" / "evals.json"
FIXTURES = REPO_ROOT / "evals" / "fixtures"
TEMPLATE = REPO_ROOT / "skills" / "impl-plan" / "assets" / "plan-template.md"
PLAN_GLOB = "docs/superpowers/plans/*.md"
CANONICAL_TITLES = ("Evals", "Nachbarn", "known-limits", "Report")

# Ein Plan, wie ihn die Skill für die Fixture ip-tier0 schreiben soll — mit dem Kopf
# aus dem Template. Was die Evals mechanisch fordern, muss an diesem Plan greifen.
SAMPLE_PLAN = TEMPLATE.read_text(encoding="utf-8").splitlines()[0] + """
# checkpoint Implementation Plan

**Goal:** Zwischenstand im Gespräch in zwei Blöcken, sonst nichts.

**Architecture:** Tier 0, keine Skripte; Evals vor SKILL.md.

**Spec:** `specs/Spec 23 – checkpoint.md`

### Task 1: Evals

**Files:**
- Create: `evals/checkpoint/evals.json`

**Interfaces:**
- Consumes: `token:Recap:`, `token:Open:`
- Produces: `evals_json`

- [ ] **Step 1: Drei Evals** — `anti-ceremony-nothing-open-stays-two-blocks`,
      `recap-and-open-both-present`, `recap-stays-under-four-sentences`.
- [ ] **Step 2: Commit.**

### Task 2: SKILL.md

**Files:**
- Create: `skills/checkpoint/SKILL.md`

**Interfaces:**
- Consumes: `evals_json`
- Produces: `token:Recap:`, `token:Open:`

- [ ] **Step 1: Frontmatter und Contract.**
- [ ] **Step 2: Commit.**

### Task 3: Nachbarn

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: (nichts Neues)

- [ ] **Step 1: Routing-Zeile.** Commit.

### Task 4: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: (nichts Neues)

- [ ] **Step 1: Ungemessenes.** Commit.

### Task 5: Report

**Files:**
- Create: `docs/superpowers/reports/checkpoint-report.md`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: (nichts Neues)

- [ ] **Step 1: Sektion „Was nicht gemessen wurde".** Commit.
"""

FIVE_IDS = (
    "anti-ceremony-one-line-note-stays-bare",
    "note-carries-header",
    "note-lists-open-items",
    "stale-note-is-replaced",
    "note-names-next-owner",
)


def _evals():
    return {ev.id: ev for ev in load_evals(EVALS_PATH)}


def _file_patterns(ev) -> list[str]:
    return [a.pattern for a in ev.must if a.type == "file_matches"]


def test_evals_file_loads_with_five_contract_evals():
    evals = load_evals(EVALS_PATH)
    assert len(evals) == 5
    assert all(ev.eval_class == "contract" for ev in evals)


def test_anti_ceremony_eval_exists_and_binds_to_the_header():
    """Spec 00 §2 Pflicht. Kürze allein diskriminiert nicht — die Kopfzeile schon."""
    anti = next(ev for ev in load_evals(EVALS_PATH) if "anti-ceremony" in ev.id)
    types = {a.type for a in anti.must}
    assert "artifact_header" in types and "file_max_lines" in types


def test_every_eval_asserts_header_or_a_canonical_title():
    """Jeder Eval hängt an etwas, das nur impl-plan schreibt: der Kopfzeile oder
    einem kanonischen Task-Titel aus references/task-patterns.md."""
    for ev in load_evals(EVALS_PATH):
        has_header = any(a.type == "artifact_header" for a in ev.must)
        has_title = any(f"### Task \\d+: {t}" in p for p in _file_patterns(ev) for t in CANONICAL_TITLES)
        assert has_header or has_title, ev.id


def test_every_path_is_the_plan_glob():
    """Die Fixtures bringen nichts unter docs/superpowers/plans/ mit — der Glob
    trifft die eine Datei, die die Skill schreibt (Spec 16, Evals)."""
    for ev in load_evals(EVALS_PATH):
        for a in list(ev.must) + list(ev.must_not):
            assert a.path == PLAN_GLOB, f"{ev.id}: {a.path}"
    for fixture in ("ip-tiny", "ip-five", "ip-tier0"):
        assert not (FIXTURES / fixture / "docs" / "superpowers" / "plans").exists()


def test_template_header_satisfies_the_artifact_header_primitive():
    first = TEMPLATE.read_text(encoding="utf-8").splitlines()[0]
    match = ARTIFACT_HEADER_RE.match(first)
    assert match and match.group("skill") == "impl-plan"


def test_must_patterns_grip_a_template_shaped_plan():
    """Die Regexe der Evals 3 und 4 greifen an einem Plan, der dem Template folgt.
    Eval 2 prüft IDs der ip-five-Spec und ist gegen den Tier-0-Beispielplan
    absichtlich nicht gebunden."""
    evals = _evals()
    for eval_id in ("mandatory-tasks-carry-canonical-titles", "doctrine-task-interfaces-carry-tokens"):
        for pattern in _file_patterns(evals[eval_id]):
            assert re.search(pattern, SAMPLE_PLAN, re.MULTILINE), f"{eval_id}: {pattern}"
    for a in evals["routing-house-header-not-superpowers"].must_not:
        assert not re.search(a.pattern, SAMPLE_PLAN, re.MULTILINE)


def test_sample_plan_is_lint_clean():
    """Was die Evals akzeptieren, muss auch der Lint akzeptieren — sonst schreibt
    die Skill Pläne, die subagent-dev nicht lesen kann."""
    # plan_path liegt in der Fixture, damit der **Spec:**-Verweis dort aufgelöst
    # wird — so, wie er im Eval-Workspace läge. Die Datei selbst muss nicht existieren.
    where = FIXTURES / "ip-tier0" / "docs" / "superpowers" / "plans" / "2026-09-02-checkpoint.md"
    findings = ptt.lint_plan(SAMPLE_PLAN, plan_path=where)
    assert findings == [], [f.render() for f in findings]


def test_asserted_ids_are_exactly_the_ids_of_the_ip_five_spec():
    """Verdrahtung Eval ↔ Fixture: Ändert jemand die Tabelle der Fixture-Spec,
    ohne die Evals mitzuziehen, prüfen die Evals IDs, die kein Plan haben kann."""
    spec_text = (FIXTURES / "ip-five" / "specs" / "Spec 22 – handoff-note.md").read_text(encoding="utf-8")
    spec_ids = ptt.spec_eval_ids(spec_text)
    assert spec_ids == list(FIVE_IDS)
    patterns = _file_patterns(_evals()["spec-eval-ids-each-have-a-task"])
    asserted = [p.rsplit("*", 1)[-1] for p in patterns]
    assert asserted == list(FIVE_IDS)


def test_tier0_spec_mandates_two_tokens():
    spec_text = (FIXTURES / "ip-tier0" / "specs" / "Spec 23 – checkpoint.md").read_text(encoding="utf-8")
    assert "`Recap:`" in spec_text and "`Open:`" in spec_text
    assert re.search(r"(?i)tier 0", spec_text)


def test_no_contract_eval_relies_on_a_judge():
    for ev in load_evals(EVALS_PATH):
        assert all(a.type != "judge" for a in list(ev.must) + list(ev.must_not)), ev.id


def test_every_eval_answers_the_discriminator_question():
    for ev in load_evals(EVALS_PATH):
        assert re.search(r"(?i)diskriminator", ev.notes or ""), ev.id


def test_every_fixture_exists_with_manifest():
    for ev in load_evals(EVALS_PATH):
        assert (FIXTURES / ev.fixture / "fixture.json").is_file(), ev.id
