"""Tests für skills/setup-repo/assets/runtime/verify_stop.py und den Starter im Fragment
assets/hooks/verify-stop.json (Spec 22, Abschnitt B).

Alle Läufe als Unterprozess mit CLAUDE_PROJECT_DIR auf einem Mini-Repo in tmp_path."""

import json
import os
import shutil
import subprocess
import sys

import pytest
from conftest import REPO_ROOT

SKILL = REPO_ROOT / "skills" / "setup-repo"
SCRIPT = SKILL / "assets" / "runtime" / "verify_stop.py"
FRAGMENT = SKILL / "assets" / "hooks" / "verify-stop.json"


def mini_repo(tmp_path, command: str | None):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    line = f"Verifikation: `{command}`" if command else "Verifikation: keine — ungeprüft"
    (repo / "CLAUDE.md").write_text(f"<!-- skill: setup-repo | schema: 1 | generated: x -->\n# Repo\n\n{line}\n",
                                    encoding="utf-8")
    return repo


def stop(repo, session="s1", *args):
    payload = json.dumps({"session_id": session, "hook_event_name": "Stop", "stop_hook_active": False})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=payload.encode("utf-8"), cwd=repo,
                          capture_output=True, env=env, timeout=60)


def message(proc) -> str:
    out = proc.stdout.decode("utf-8").strip()
    return json.loads(out)["systemMessage"] if out else ""


def test_verify_stop_counts_and_missing_tool(tmp_path):
    flag = tmp_path / "flag"
    flag.write_text("1", encoding="utf-8")
    cmd = f'"{sys.executable}" -c "import sys; sys.exit(int(open(r\'{flag}\').read()))"'
    repo = mini_repo(tmp_path, cmd)

    for attempt in (1, 2, 3):
        proc = stop(repo)
        assert proc.returncode == 2, (attempt, proc.stderr)
        assert f"Versuch {attempt} von 3" in proc.stderr.decode("utf-8") and not proc.stdout.strip()
    proc = stop(repo)
    assert proc.returncode == 0 and "rot nach drei Versuchen" in message(proc)
    assert stop(repo).returncode == 2, "nach dem Zulassen beginnt die Zählung neu"
    assert stop(repo, session="s2").returncode == 2 and "Versuch 1 von 3" in stop(repo, "s3").stderr.decode()

    flag.write_text("0", encoding="utf-8")
    proc = stop(repo)
    assert proc.returncode == 0 and not proc.stdout.strip() and not proc.stderr.strip()
    flag.write_text("1", encoding="utf-8")
    assert "Versuch 1 von 3" in stop(repo).stderr.decode("utf-8"), "grün setzt den Zähler zurück"
    state = json.loads((repo / ".skills/cache/setup-repo/verify-stop.json").read_text(encoding="utf-8"))
    assert state["_meta"]["skill"] == "setup-repo"

    missing = mini_repo(tmp_path / "m", "gibtsnicht-xyz check")
    proc = stop(missing)
    assert proc.returncode == 0 and "ungeprüft — gibtsnicht-xyz fehlt" in message(proc)
    assert stop(missing).stdout.strip() == b"", "dieselbe Meldung nur einmal je Session"

    none = mini_repo(tmp_path / "n", None)
    proc = stop(none)
    assert proc.returncode == 0 and "ungeprüft — kein Verifikationsbefehl" in message(proc)


def test_verify_stop_selftest_does_not_run_command(tmp_path):
    marker = tmp_path / "ran"
    cmd = f'"{sys.executable}" -c "open(r\'{marker}\', \'w\').write(\'x\')"'
    repo = mini_repo(tmp_path, cmd)
    proc = stop(repo, "s1", "--selftest")
    assert proc.returncode == 0 and json.loads(proc.stdout)["ok"] is True
    assert not marker.exists()
    proc = stop(mini_repo(tmp_path / "m", "gibtsnicht-xyz"), "s1", "--selftest")
    result = json.loads(proc.stdout)
    assert result["ok"] is False and "gibtsnicht-xyz fehlt" in result["detail"]


@pytest.mark.parametrize("raw", [b"", b"{kaputt", b"[1]", b'{"session_id": null}'])
def test_verify_stop_survives_bad_input(tmp_path, raw):
    repo = mini_repo(tmp_path, f'"{sys.executable}" -c "pass"')
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    proc = subprocess.run([sys.executable, str(SCRIPT)], input=raw, cwd=repo, capture_output=True, env=env,
                          timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert b"Traceback" not in proc.stderr


def _launcher() -> str:
    data = json.loads(FRAGMENT.read_text(encoding="utf-8"))
    (entry,) = data["hooks"]["Stop"]
    (hook,) = entry["hooks"]
    assert hook["type"] == "command"
    return hook["command"]


@pytest.mark.skipif(shutil.which("bash") is None, reason="Starter braucht bash")
@pytest.mark.parametrize("interpreter", ["python3", "python"])
def test_launcher_command_runs(tmp_path, interpreter):
    command = _launcher()
    assert "$CLAUDE_PROJECT_DIR/.claude/hooks/verify_stop.py" in command
    bindir = tmp_path / "bin"
    bindir.mkdir()
    os.symlink(sys.executable, bindir / interpreter)
    fail = bindir / "checkfail"
    fail.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    fail.chmod(0o755)
    repo = mini_repo(tmp_path, "checkfail")
    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy(SCRIPT, hooks / "verify_stop.py")
    env = {"PATH": str(bindir), "CLAUDE_PROJECT_DIR": str(repo), "HOME": str(tmp_path)}
    payload = json.dumps({"session_id": "s1", "hook_event_name": "Stop"}).encode("utf-8")
    proc = subprocess.run([shutil.which("bash"), "-c", command], input=payload, cwd=repo, capture_output=True,
                          env=env, timeout=60)
    assert proc.returncode == 2, proc.stderr
    assert "[setup-repo] Verifikation rot (Versuch 1 von 3)" in proc.stderr.decode("utf-8")
