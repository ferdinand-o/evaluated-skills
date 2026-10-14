import json
import os
import stat
from pathlib import Path

from evalkit.dispatch import assistant_text, run_agent, visible_skills


def fake_cli(tmp_path: Path, body: str) -> str:
    # bash, nicht sh: ${@: -1} ist ein Bashismus und bricht unter dash.
    script = tmp_path / "fake-claude"
    script.write_text("#!/bin/bash\n" + body, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_captures_stdout_and_exit_code(tmp_path):
    cli = fake_cli(tmp_path, 'echo "hallo"\nexit 0\n')
    result = run_agent("prompt", tmp_path, cli=cli)
    assert result.stdout.strip() == "hallo"
    assert result.exit_code == 0
    assert not result.timed_out


def test_passes_prompt_as_last_argument(tmp_path):
    cli = fake_cli(tmp_path, 'echo "$#" "${@: -1}"\n')
    result = run_agent("mein prompt", tmp_path, cli=cli)
    assert "mein prompt" in result.stdout


def test_passes_print_and_permission_flags(tmp_path):
    cli = fake_cli(tmp_path, 'echo "$@"\n')
    result = run_agent("p", tmp_path, cli=cli, permission_mode="acceptEdits")
    assert "-p" in result.stdout
    assert "--permission-mode acceptEdits" in result.stdout


def test_isolates_from_user_configuration(tmp_path):
    """Ohne diese Flags testet der Eval die global installierte Skill, nicht die im Workspace."""
    cli = fake_cli(tmp_path, 'echo "$@"\n')
    result = run_agent("p", tmp_path, cli=cli)
    assert "--setting-sources project" in result.stdout
    assert "--strict-mcp-config" in result.stdout


def test_runs_in_given_working_directory(tmp_path):
    workdir = tmp_path / "ws"
    workdir.mkdir()
    cli = fake_cli(tmp_path, "pwd\n")
    result = run_agent("p", workdir, cli=cli)
    assert os.path.realpath(result.stdout.strip()) == os.path.realpath(str(workdir))


def test_timeout_is_reported_not_raised(tmp_path):
    cli = fake_cli(tmp_path, "sleep 5\n")
    result = run_agent("p", tmp_path, cli=cli, timeout=1)
    assert result.timed_out
    assert result.exit_code != 0


def test_missing_cli_is_reported_not_raised(tmp_path):
    result = run_agent("p", tmp_path, cli=str(tmp_path / "does-not-exist"))
    assert result.exit_code != 0
    assert "nicht gefunden" in result.stderr


def test_missing_cwd_is_reported_accurately_not_as_missing_cli(tmp_path):
    """subprocess.run wirft FileNotFoundError sowohl wenn das CLI als auch wenn cwd
    fehlt. Die Meldung darf ein fehlendes cwd nicht als "CLI nicht gefunden"
    ausgeben — das CLI ist da, nur das Arbeitsverzeichnis nicht."""
    missing_cwd = tmp_path / "does-not-exist"
    cli = fake_cli(tmp_path, "pwd\n")
    result = run_agent("p", missing_cwd, cli=cli)
    assert result.exit_code != 0
    assert "Arbeitsverzeichnis" in result.stderr
    assert "CLI" not in result.stderr


def test_process_environment_is_inherited_unmodified(tmp_path, monkeypatch):
    """Dokumentiert die tatsächliche (nicht die zugesagte) Isolation: HOME und der
    Rest von os.environ gehen unverändert an den Subprozess. Ein Versuch, HOME auf
    ein Unterverzeichnis von cwd umzubiegen, ließ die CLI ihre Anmeldedaten nicht
    mehr finden (Smoke-Test scheiterte) — siehe docs/known-limits.md und den
    korrigierten Docstring von run_agent."""
    monkeypatch.setenv("HOME", "/this/is/the/callers/home")
    cli = fake_cli(tmp_path, 'echo "$HOME"\n')
    result = run_agent("p", tmp_path, cli=cli)
    assert result.stdout.strip() == "/this/is/the/callers/home"


def test_assistant_text_collects_every_turn_in_order():
    """Frühere Züge müssen sichtbar bleiben, nicht nur der letzte.

    Mit --output-format text liefert `claude -p` auf stdout nur die letzte
    Assistant-Nachricht. Ein Judge-Claim der Form "X, bevor Y geschieht" prüfte damit
    einen Ausschnitt, den er für das Ganze hielt: Ein motion-landing-Eval fiel durch,
    obwohl das geforderte Storyboard korrekt erzeugt worden war -- nur eine Runde zu früh.
    """
    raw = "\n".join([
        json.dumps({"type": "system", "subtype": "init", "skills": []}),
        json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Storyboard zuerst"}]}}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Write", "input": {}},
            {"type": "text", "text": "dann gebaut"},
        ]}}),
        json.dumps({"type": "result", "result": "dann gebaut"}),
    ])
    assert assistant_text(raw) == "Storyboard zuerst\ndann gebaut"


def test_assistant_text_survives_a_truncated_last_line():
    """Ein Timeout schneidet die letzte Zeile mitten im JSON ab -- der Rest bleibt gültig."""
    raw = (
        json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "brauchbar"}]}})
        + '\n{"type": "assistant", "message": {"content": [{"type": "te'
    )
    assert assistant_text(raw) == "brauchbar"


def test_assistant_text_ignores_foreign_events_and_empty_text():
    raw = "\n".join([
        "",
        json.dumps({"type": "user", "message": {"content": [{"type": "text", "text": "der Prompt"}]}}),
        json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": ""}]}}),
        json.dumps({"type": "assistant", "message": "kein Objekt"}),
    ])
    assert assistant_text(raw) == ""


def test_run_agent_fills_text_from_the_stream(tmp_path):
    """run_agent liefert die Assistant-Sicht in `text`, das Rohe bleibt in `stdout`."""
    event = json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "hallo"}]}})
    cli = fake_cli(tmp_path, f"echo '{event}'\n")
    result = run_agent("prompt", tmp_path, cli=cli)
    assert result.text == "hallo"
    assert "assistant" in result.stdout


# --- visible_skills: das skills-Feld des init-Ereignisses (Spec 18) -------------------

def _init_event(skills=None, **extra):
    event = {"type": "system", "subtype": "init", **extra}
    if skills is not None:
        event["skills"] = skills
    return json.dumps(event)


def test_visible_skills_reads_init_event_behind_leading_foreign_events():
    """Das init-Ereignis ist nicht die erste Zeile: ein echter Lauf (CLI 2.1.272) schickt
    `active_goal` und `autocompact_state` davor. Der Parser sucht, statt zu erwarten."""
    raw = "\n".join([
        json.dumps({"type": "active_goal", "value": None}),
        json.dumps({"type": "autocompact_state", "value": {"enabled": True}}),
        _init_event(skills=["deep-research", "handoff", "verify"]),
        json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "OK"}]}}),
    ])
    assert visible_skills(raw) == frozenset({"deep-research", "handoff", "verify"})


def test_visible_skills_is_none_without_init_event():
    """Kein init-Ereignis (Klartext-CLI, abgeschnittener Stream) heißt „ungeprüft",
    nie „nicht sichtbar" — None, nicht die leere Menge."""
    raw = json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "OK"}]}})
    assert visible_skills(raw) is None
    assert visible_skills("nur Klartext\n") is None
    assert visible_skills("") is None


def test_visible_skills_is_none_when_init_has_no_skills_field():
    """Eine CLI-Version ohne das Feld ändert kein Verdikt (Spec 18, Constraints)."""
    assert visible_skills(_init_event()) is None
    assert visible_skills(_init_event(skills="kein Array")) is None


def test_visible_skills_empty_list_is_an_empty_set_not_none():
    """Ein Agent, der ausdrücklich keine Skill sah, ist geprüft — die Menge ist leer."""
    assert visible_skills(_init_event(skills=[])) == frozenset()


def test_visible_skills_skips_broken_lines_and_non_strings():
    raw = "\n".join([
        '{"type": "system", "subtype": "in',
        _init_event(skills=["a", 3, None, "b"]),
    ])
    assert visible_skills(raw) == frozenset({"a", "b"})


def test_run_agent_fills_skills_from_the_stream(tmp_path):
    event = _init_event(skills=["probe", "verify"])
    cli = fake_cli(tmp_path, f"echo '{event}'\n")
    result = run_agent("prompt", tmp_path, cli=cli)
    assert result.skills == frozenset({"probe", "verify"})


def test_run_agent_leaves_skills_none_for_plaintext_cli(tmp_path):
    """Die bestehenden Fake-CLIs schreiben Klartext — sie dürfen kein Urteil über
    Sichtbarkeit erzeugen (Spec 18, „Abwärtskompatibel")."""
    cli = fake_cli(tmp_path, 'echo "hallo"\nexit 0\n')
    assert run_agent("prompt", tmp_path, cli=cli).skills is None


def test_run_agent_fills_skills_on_timeout(tmp_path):
    """Auch ein abgebrochener Lauf trägt sein init-Ereignis — die Prüfung darf nicht
    daran hängen, ob der Agent fertig wurde."""
    event = _init_event(skills=["probe"])
    cli = fake_cli(tmp_path, f"echo '{event}'\nsleep 5\n")
    result = run_agent("prompt", tmp_path, cli=cli, timeout=1)
    assert result.timed_out
    assert result.skills == frozenset({"probe"})


# --- Rechte-Modus: bypass oder --allowedTools ------------------------------------------

def test_auto_uses_allowed_tools_under_root(tmp_path, monkeypatch):
    """Die CLI verweigert bypassPermissions unter uid 0 (known-limits). Unter root nimmt
    `auto` deshalb --allowedTools mit acceptEdits — gemessen: so läuft claude -p als root."""
    import evalkit.dispatch as dispatch
    cli = fake_cli(tmp_path, 'echo "$@"\n')
    monkeypatch.setattr(dispatch, "_is_root", lambda: True)
    out = run_agent("p", tmp_path, cli=cli).stdout
    assert "--permission-mode acceptEdits" in out and "bypassPermissions" not in out
    assert f"--allowedTools {dispatch.ALLOWED_TOOLS}" in out
    assert {"Bash", "Skill", "Write", "Edit", "Read"} <= set(dispatch.ALLOWED_TOOLS.split(","))
    monkeypatch.setattr(dispatch, "_is_root", lambda: False)
    out = run_agent("p", tmp_path, cli=cli).stdout
    assert "--permission-mode bypassPermissions" in out and "--allowedTools" not in out


def test_explicit_permission_profiles(tmp_path, monkeypatch):
    import evalkit.dispatch as dispatch
    cli = fake_cli(tmp_path, 'echo "$@"\n')
    monkeypatch.setattr(dispatch, "_is_root", lambda: True)
    assert "--permission-mode bypassPermissions" in run_agent("p", tmp_path, cli=cli, permissions="bypass").stdout
    monkeypatch.setattr(dispatch, "_is_root", lambda: False)
    assert "--allowedTools" in run_agent("p", tmp_path, cli=cli, permissions="allowed-tools").stdout
    assert dispatch.resolve_permissions("auto") in ("bypass", "allowed-tools")
    try:
        dispatch.resolve_permissions("alles")
    except ValueError:
        pass
    else:
        raise AssertionError("unbekannter Modus muss ValueError werfen")
