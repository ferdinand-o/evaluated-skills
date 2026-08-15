import pytest
from evalkit.judge import JudgeError, build_prompt, parse_verdict


def test_prompt_contains_every_claim_and_the_transcript():
    prompt = build_prompt(["Claim A", "Claim B"], "AGENT SAGTE X", "(nichts)")
    assert "Claim A" in prompt
    assert "Claim B" in prompt
    assert "AGENT SAGTE X" in prompt


def test_prompt_contains_the_workspace_dump():
    """Ohne Dateiinhalt könnte der Judge inhaltliche Behauptungen nie bejahen."""
    prompt = build_prompt(["A"], "kurze Bestätigung", "--- DATEI: handoff.md ---\n## Status\nfoo")
    assert "handoff.md" in prompt
    assert "## Status" in prompt


def test_prompt_demands_bare_json_and_default_false():
    prompt = build_prompt(["A"], "t", "d")
    assert "JSON" in prompt
    assert "holds" in prompt
    # Im Zweifel gilt eine Behauptung als nicht erfüllt — sonst besteht alles.
    assert "false" in prompt


def test_parse_plain_verdict():
    raw = '{"verdicts": [{"claim": "A", "holds": true, "why": "steht da"}]}'
    assert parse_verdict(raw) == {"A": True}


def test_parse_verdict_wrapped_in_prose():
    raw = 'Hier mein Urteil:\n\n{"verdicts": [{"claim": "A", "holds": false, "why": "fehlt"}]}\n\nEnde.'
    assert parse_verdict(raw) == {"A": False}


def test_parse_verdict_ignores_earlier_json_objects():
    raw = '{"note": "ignoriere mich"}\n{"verdicts": [{"claim": "A", "holds": true}]}'
    assert parse_verdict(raw) == {"A": True}


def test_parse_verdict_survives_braces_inside_strings():
    """Eine Klammer in der Begründung darf das Parsing nicht aus dem Tritt bringen."""
    raw = '{"verdicts": [{"claim": "A", "holds": true, "why": "der Code sagt def main() { ..."}]}'
    assert parse_verdict(raw) == {"A": True}


def test_parse_verdict_without_json_raises():
    with pytest.raises(JudgeError, match="kein JSON"):
        parse_verdict("Ich finde das alles ganz gut.")


def test_parse_verdict_with_missing_holds_raises():
    with pytest.raises(JudgeError, match="holds"):
        parse_verdict('{"verdicts": [{"claim": "A"}]}')


def test_parse_verdict_with_non_boolean_holds_raises():
    with pytest.raises(JudgeError, match="holds"):
        parse_verdict('{"verdicts": [{"claim": "A", "holds": "ja"}]}')
