"""Spec 25 (skill-dir): Skriptpfade, die in jedem Repo laufen.

Die Hook-Vorlagen werden hier so ausgeführt, wie Claude Code sie ausführt: das Kommando
aus dem Fragment über `bash -c`, mit `CLAUDE_PROJECT_DIR` auf einem Temp-Repo und der
Hook-Payload auf stdin."""

import json
import os
import shutil
import subprocess
import sys

import pytest
from conftest import REPO_ROOT, git

HOOKS = {
    "debug-ledger": ("check-ledger.json", "check_ledger.py"),
    "sql-schema-architect": ("migration-gate.json", "migration_gate.py"),
}


def _hook_command(skill):
    fragment, _ = HOOKS[skill]
    data = json.loads((REPO_ROOT / "skills" / skill / "assets" / "hooks" / fragment).read_text(encoding="utf-8"))
    return data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]


def _run_hook(skill, repo, command_text):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command_text}})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    return subprocess.run(["bash", "-c", _hook_command(skill)], cwd=repo, input=payload, capture_output=True,
                          text=True, env=env, timeout=60)


def _install(skill, repo):
    _, script = HOOKS[skill]
    (repo / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "skills" / skill / "scripts" / script, repo / ".claude" / "hooks" / script)


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    return repo


@pytest.mark.skipif(shutil.which("bash") is None, reason="Hooks laufen über bash")
def test_hook_templates_report_missing_script_and_still_block(tmp_path):
    for skill in HOOKS:
        assert f"skills/{skill}/scripts/" not in _hook_command(skill)
        command = _hook_command(skill)
        assert "CLAUDE_PROJECT_DIR" in command and HOOKS[skill][1] in command and "hooks" in command

    # debug-ledger: fehlendes Skript → ungeprüft, Exit 0; Verstoß → Exit 2; sauber → Exit 0
    repo = _repo(tmp_path / "dl")
    ledger = repo / "docs" / "debugging" / "2026-10-14-x.md"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("kein Ledger\n", encoding="utf-8")
    git(repo, "add", "-A")
    done = _run_hook("debug-ledger", repo, "git commit -m x")
    assert done.returncode == 0 and "ungeprüft" in json.loads(done.stdout)["systemMessage"]
    _install("debug-ledger", repo)
    done = _run_hook("debug-ledger", repo, "git commit -m x")
    assert done.returncode == 2, done
    assert _run_hook("debug-ledger", repo, "ls -la").returncode == 0
    git(repo, "rm", "-q", "--cached", "docs/debugging/2026-10-14-x.md")
    done = _run_hook("debug-ledger", repo, "git commit -m x")
    assert done.returncode == 0 and done.stdout.strip() in ("", "OK: keine gestagten Ledger-Dateien")

    # sql-schema-architect: dasselbe für alembic upgrade
    repo = _repo(tmp_path / "sql")
    rev = repo / "alembic" / "versions" / "0001.py"
    rev.parent.mkdir(parents=True)
    rev.write_text("def upgrade():\n    op.drop_table('t')\n\ndef downgrade():\n    raise NotImplementedError('x')\n",
                   encoding="utf-8")
    done = _run_hook("sql-schema-architect", repo, "alembic upgrade head")
    assert done.returncode == 0 and "ungeprüft" in json.loads(done.stdout)["systemMessage"]
    _install("sql-schema-architect", repo)
    assert _run_hook("sql-schema-architect", repo, "alembic upgrade head").returncode == 2
    assert _run_hook("sql-schema-architect", repo, "ls -la").returncode == 0
    rev.write_text("def upgrade():\n    op.create_table('t')\n\ndef downgrade():\n    op.drop_table('t')\n",
                   encoding="utf-8")
    assert _run_hook("sql-schema-architect", repo, "alembic upgrade head").returncode == 0


def test_hook_scripts_are_standalone():
    """Die Vorlagen kopieren genau eine Datei — sie darf nichts aus ihrem Skill-Ordner importieren."""
    for skill, (_, script) in HOOKS.items():
        text = (REPO_ROOT / "skills" / skill / "scripts" / script).read_text(encoding="utf-8")
        siblings = {p.stem for p in (REPO_ROOT / "skills" / skill / "scripts").glob("*.py")} - {script[:-3]}
        imports = {line.split()[1].split(".")[0] for line in text.splitlines()
                   if line.startswith(("import ", "from "))}
        assert not imports & siblings, (skill, imports & siblings)
    assert sys.version_info >= (3, 8)
