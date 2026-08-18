"""Strukturprüfung der exercise-forge-evals.json. Läuft keine Evals — kein
Agentenlauf, keine claude-CLI-Aufrufe. Prüft nur, dass evalkit.schema.load_evals()
die Datei fehlerfrei akzeptiert (Rulings: Evals werden geschrieben, nicht
ausgeführt)."""

from pathlib import Path

from evalkit.schema import load_evals

EVALS_PATH = Path(__file__).resolve().parent.parent / "evals" / "exercise-forge" / "evals.json"


def test_evals_file_loads_without_schema_error():
    evals = load_evals(EVALS_PATH)
    assert len(evals) == 6


def test_at_least_one_contract_level_anti_ceremony_eval_exists():
    """Spec 00 §2 Pflicht: mindestens ein Anti-Zeremonie-Eval."""
    evals = load_evals(EVALS_PATH)
    contract_evals = [e for e in evals if e.eval_class == "contract"]
    assert contract_evals
    assert any("anti" in e.id.lower() or "single" in e.id.lower() or "stays" in e.id.lower() for e in contract_evals)


def test_every_eval_has_a_fixture():
    """Jeder exercise-forge-Eval hängt an einem eigenen Fixture-Workspace,
    nicht am leeren Standard-Workspace ohne Projektüberschreibung."""
    evals = load_evals(EVALS_PATH)
    assert all(e.fixture for e in evals)


def test_fixtures_referenced_by_evals_exist_on_disk():
    evals = load_evals(EVALS_PATH)
    fixtures_root = EVALS_PATH.parent.parent / "fixtures"
    for ev in evals:
        assert (fixtures_root / ev.fixture / "fixture.json").is_file(), ev.fixture


def test_all_five_spec13_scenarios_are_covered():
    """Regression L3: Plan und Bericht behaupteten 'fünf Evals aus Spec 13
    §Approach', tatsächlich fehlte Szenario 4 (Karten-Atomarität bei '20
    Karten zu X') ersatzlos. Diese fünf Stichworte müssen je einen Eval haben,
    zusätzlich zum verpflichtenden Anti-Zeremonie-Eval aus Spec 00 §2 — macht
    sechs Evals insgesamt (siehe test_evals_file_loads_without_schema_error)."""
    evals = load_evals(EVALS_PATH)
    haystacks = []
    for ev in evals:
        claims = " ".join(a.claim or "" for a in (*ev.must, *ev.must_not))
        haystacks.append(f"{ev.prompt} {ev.notes} {claims}".lower())
    text = " ".join(haystacks)
    for keyword in ("distraktor", "überspezifiziert", "kriterien", "atomar", "schwerer"):
        assert keyword in text, f"kein Eval erwähnt {keyword!r}"


# Die drei "Gate findet ein Problem"-Evals: ihr Judge-Claim wurde je einmal
# zusammengesetzt formuliert und fiel dadurch bei identischem Commit/Fixture
# abwechselnd rot/grün (siehe docs/known-limits.md, Abschnitt Judge). Fix:
# "Gate lief" (method-Feld) und "nicht verified" (status-Feld) stehen als
# eigene mechanische Assertionen da, nur "Konflikt benannt" bleibt Judge —
# und genau das erst deckte auf, dass status trotz gefundenem Konflikt
# 'verified' blieb (ein echter Defekt, kein Eval-Rauschen mehr). Dieser Test
# hält die Zerlegung fest, damit sie nicht unbemerkt wieder zu einer
# Drei-Bedingungen-Kette zusammenwächst.
PROBLEM_FOUND_EVAL_IDS = (
    "mc-distractor-trap-is-caught",
    "narrow-criteria-on-open-question-are-flagged",
    "overspecified-coding-tests-are-flagged",
)


def test_problem_found_evals_check_gate_ran_mechanically():
    evals = {e.id: e for e in load_evals(EVALS_PATH)}
    for eval_id in PROBLEM_FOUND_EVAL_IDS:
        method_checks = [
            a for a in evals[eval_id].must
            if a.type == "file_matches" and a.pattern and "\"method\":" in a.pattern
        ]
        assert method_checks, f"{eval_id}: 'Gate lief' ist nicht mechanisch geprüft"


def test_problem_found_evals_check_not_verified_mechanically():
    evals = {e.id: e for e in load_evals(EVALS_PATH)}
    for eval_id in PROBLEM_FOUND_EVAL_IDS:
        verified_checks = [
            a for a in evals[eval_id].must_not
            if a.type == "file_matches" and a.pattern and "\"status\": \"verified\"" in a.pattern
        ]
        assert verified_checks, f"{eval_id}: 'nicht verified' ist nicht mechanisch geprüft"


def test_problem_found_evals_carry_exactly_one_judge_claim():
    """Genau eine einzeln entscheidbare Bedingung beim Judge — keine
    zusammengesetzte Kette mehr."""
    evals = {e.id: e for e in load_evals(EVALS_PATH)}
    for eval_id in PROBLEM_FOUND_EVAL_IDS:
        judge_claims = [a for a in evals[eval_id].must if a.type == "judge"]
        assert len(judge_claims) == 1, f"{eval_id}: erwartet genau einen Judge-Claim, gefunden {len(judge_claims)}"
