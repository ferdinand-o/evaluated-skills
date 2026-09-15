from evalkit.report import EvalResult, exit_code, format_report


def test_exit_code_all_green():
    assert exit_code([EvalResult("a", True, (), False, "")]) == 0


def test_exit_code_one_failure():
    assert exit_code([EvalResult("a", True, (), False, ""), EvalResult("b", False, ("x",), False, "")]) == 1


def test_exit_code_harness_error_wins_over_failure():
    results = [EvalResult("a", False, ("x",), False, ""), EvalResult("b", False, ("boom",), True, "Harness-Fehler")]
    assert exit_code(results) == 2


def test_report_lists_failures_verbatim():
    text = format_report([EvalResult("handoff-creates-file", False, ("handoff.md existiert nicht",), False, "")])
    assert "handoff-creates-file" in text
    assert "handoff.md existiert nicht" in text
    assert "1 gefallen" in text


# --- Baseline-Modus (Spec 18): grün ohne Skill heißt „misst nichts" -------------------

def _base(eval_id, passed, *, skipped=False, failures=(), note=""):
    return EvalResult(eval_id, passed, tuple(failures), skipped, note, baseline=True)


def test_baseline_results_are_marked_not_passed_or_failed():
    text = format_report([_base("a", True), _base("b", False, failures=("must: x fehlt",))])
    assert "[GRÜN OHNE SKILL] a — misst nichts" in text
    assert "[ROT OHNE SKILL] b" in text
    assert "must: x fehlt" in text
    assert "[PASS]" not in text and "[FAIL]" not in text


def test_baseline_summary_line_counts_both_sides():
    text = format_report([
        _base("a", True), _base("b", False), _base("c", False),
        _base("d", False, skipped=True, failures=("harness: Baseline unmöglich",), note="Harness-Fehler"),
    ])
    assert "1 grün ohne Skill — messen nichts, 2 rot ohne Skill, 1 übersprungen" in text
    assert "[SKIP] d — Harness-Fehler" in text


def test_baseline_exit_code_is_one_when_any_eval_is_green_without_skill():
    assert exit_code([_base("a", True), _base("b", False)]) == 1


def test_baseline_exit_code_is_zero_when_all_are_red_without_skill():
    assert exit_code([_base("a", False), _base("b", False)]) == 0


def test_baseline_exit_code_two_for_harness_error_wins():
    results = [_base("a", True), _base("b", False, skipped=True, failures=("harness: Baseline unmöglich",), note="Harness-Fehler")]
    assert exit_code(results) == 2


def test_results_without_baseline_flag_behave_as_before():
    """Das Feld hat einen Default — bestehende Aufrufer merken nichts (Spec 18, E6)."""
    plain = EvalResult("a", True, (), False, "")
    assert plain.baseline is False
    assert "[PASS] a" in format_report([plain])
    assert exit_code([plain]) == 0
