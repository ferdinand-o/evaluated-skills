import os
import stat
from pathlib import Path

from evalkit.dispatch import run_agent


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
