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
