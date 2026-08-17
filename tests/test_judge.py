import json
import stat
import pytest
from evalkit.judge import JudgeError, build_prompt, judge, parse_verdict


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


def fake_judge_cli(tmp_path, verdicts: dict) -> str:
    """Ein CLI, das wie `claude -p --output-format stream-json` antwortet."""
    event = json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": json.dumps({"verdicts": [
            {"claim": c, "holds": h} for c, h in verdicts.items()
        ]}, ensure_ascii=False)}]},
    })
    script = tmp_path / "fake-judge"
    script.write_text("#!/bin/bash\ncat <<'EOF'\n" + event + "\nEOF\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_judge_reads_the_assistant_answer_not_the_raw_stream(tmp_path):
    """Regressionstest: judge() muss die Assistant-Antwort auswerten, nicht das Roh-Transcript.

    Diese Verdrahtung war ungetestet -- test_judge.py prüfte nur build_prompt und
    parse_verdict, beides reine Funktionen. Als der Dispatch auf stream-json umgestellt
    wurde, las judge() weiter das rohe Ereignis-Transcript, fand darin kein 'verdicts'
    und liess jede behavior-Eval als Harness-Fehler aus dem PASS/FAIL-Bild verschwinden.
    Aufgefallen ist das erst in einem echten Eval-Lauf.
    """
    cwd = tmp_path / "judge"
    cwd.mkdir()
    cli = fake_judge_cli(tmp_path, {"Behauptung A": True, "Behauptung B": False})

    verdicts = judge(["Behauptung A", "Behauptung B"], "transcript", "dump", cwd, cli=cli)

    assert verdicts == {"Behauptung A": True, "Behauptung B": False}


def test_judge_raises_when_a_claim_is_unjudged(tmp_path):
    cwd = tmp_path / "judge"
    cwd.mkdir()
    cli = fake_judge_cli(tmp_path, {"Behauptung A": True})

    with pytest.raises(JudgeError, match="nicht beurteilt"):
        judge(["Behauptung A", "Behauptung B"], "transcript", "dump", cwd, cli=cli)


def test_judge_without_claims_starts_no_process(tmp_path):
    assert judge([], "transcript", "dump", tmp_path, cli="gibt-es-nicht") == {}
