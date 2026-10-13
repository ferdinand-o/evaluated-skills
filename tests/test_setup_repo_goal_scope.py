"""Tests für skills/setup-repo/assets/runtime/goal_scope.py (Spec 22, Abschnitt C).

Mini-Repos mit git in tmp_path; der Hook läuft als Unterprozess wie in Claude Code,
mit der Payload auf stdin. Der Zustand liegt in SETUP_REPO_GOAL_STATE, damit jeder
Test seinen eigenen hat."""

import json
import os
import subprocess
import sys

import pytest
from conftest import REPO_ROOT, load_script

SCRIPT = REPO_ROOT / "skills" / "setup-repo" / "assets" / "runtime" / "goal_scope.py"
LEDGER = (REPO_ROOT / "skills" / "setup-repo" / "assets" / "goals.md").read_text(encoding="utf-8")
gs = load_script("skills/setup-repo/assets/runtime/goal_scope.py")


def write(root, rel, text=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, check=True,
                          capture_output=True, text=True).stdout


def ledger(active_rows=(), header=None):
    text = LEDGER
    if header is not None:
        text = header + "\n" + text.split("\n", 1)[1]
    row_anchor = "| id | Ziel | Fertig wenn | Bereich | seit |\n| --- | --- | --- | --- | --- |\n"
    rows = "".join(f"| {gid} | Ziel {gid} | `make check` grün | {scope} | 2026-10-12 |\n" for gid, scope in active_rows)
    return text.replace(row_anchor, row_anchor + rows)


def make_repo(tmp_path, rows=(("G1", "src/greet.py"),), name="repo", commit=True):
    repo = tmp_path / name
    write(repo, "src/greet.py", "def greet():\n    return 'Helo'\n")
    write(repo, "src/dates.py", "def leap(y):\n    return y % 4 == 0\n")
    write(repo, "lib/a.py", "a = 1\n")
    write(repo, "lib/b.py", "b = 1\n")
    write(repo, "lib/c.py", "c = 1\n")
    write(repo, "lib/d.py", "d = 1\n")
    write(repo, "README.md", "# Repo\n")
    if rows is not None:
        write(repo, "docs/goals.md", ledger(rows))
    git(repo, "init", "-q")
    if commit:
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "start")
    return repo


class Hook:
    def __init__(self, repo, tmp_path):
        self.repo, self.state = repo, tmp_path / f"state-{repo.name}.json"

    def run(self, event, sid="s1", cwd=None, project_dir=True, env=None, raw=None):
        payload = raw if raw is not None else json.dumps(
            {"session_id": sid, "hook_event_name": event, "cwd": str(cwd or self.repo)}).encode("utf-8")
        e = {**os.environ, "SETUP_REPO_GOAL_STATE": str(self.state), **(env or {})}
        e.pop("CLAUDE_PROJECT_DIR", None)
        if project_dir:
            e["CLAUDE_PROJECT_DIR"] = str(self.repo)
        proc = subprocess.run([sys.executable, str(SCRIPT)], input=payload, cwd=cwd or self.repo,
                              capture_output=True, env=e, timeout=60)
        assert proc.returncode == 0, proc.stderr
        out = proc.stdout.decode("utf-8").strip()
        return json.loads(out) if out else {}

    def prompt(self, **kw):
        return self.run("UserPromptSubmit", **kw)

    def stop(self, **kw):
        return self.run("Stop", **kw)


def message(out):
    return out.get("systemMessage", "")


def test_goal_scope_turn_baseline(tmp_path):
    repo = make_repo(tmp_path)
    hook = Hook(repo, tmp_path)
    write(repo, "src/dates.py", "def leap(y):\n    return y % 4 == 0  # schon vorher geändert\n")
    hook.prompt()
    assert hook.stop() == {}, "vorher uncommittet und im Turn unverändert: keine Meldung"

    hook.prompt()
    write(repo, "lib/a.py", "a = 2\n")
    git(repo, "commit", "-q", "-am", "im Turn committet")
    write(repo, "lib/b.py", "b = 2\n")
    git(repo, "add", "lib/b.py")
    write(repo, "lib/c.py", "c = 2\n")
    (repo / "lib" / "d.py").unlink()
    write(repo, "lib/grüße.py", "x = 1\n")
    write(repo, "src/greet.py", "def greet():\n    return 'Hello'\n")
    msg = message(hook.stop())
    assert msg.startswith("[setup-repo] Geändert außerhalb des Bereichs von G1:")
    for path in ("lib/a.py", "lib/b.py", "lib/c.py", "lib/d.py", "lib/grüße.py"):
        assert path in msg, path
    assert "src/greet.py" not in msg and "src/dates.py" not in msg

    sub = make_repo(tmp_path, name="sub")
    hook = Hook(sub, tmp_path)
    hook.prompt(cwd=sub / "src", project_dir=False)
    write(sub, "lib/a.py", "a = 3\n")
    msg = message(hook.stop(cwd=sub / "src", project_dir=False))
    assert "lib/a.py" in msg and "../lib" not in msg


def test_goal_scope_reports_each_file_once_and_defers_context(tmp_path):
    repo = make_repo(tmp_path)
    hook = Hook(repo, tmp_path)
    hook.prompt()
    write(repo, "lib/a.py", "a = 2\n")
    first = message(hook.stop())
    assert "lib/a.py" in first
    out = hook.prompt()
    assert out["hookSpecificOutput"]["additionalContext"] == first
    write(repo, "lib/a.py", "a = 3\n")
    assert hook.stop() == {}, "dieselbe Datei wird je Session nur einmal gemeldet"
    assert hook.prompt() == {}, "die offene Meldung erscheint genau einmal"
    hook.prompt(sid="s2")
    write(repo, "lib/a.py", "a = 4\n")
    assert "lib/a.py" in message(hook.stop(sid="s2")), "andere Session, eigene Meldung"
    assert hook.stop(sid="s3") == {}, "ohne Basis aus einem Prompt schweigt der Hook"


@pytest.mark.parametrize("pattern,path,expected", [
    ("src/**", "src/a/b/c.py", True),
    ("src/**", "srcx/a.py", False),
    ("src/*.py", "src/a.py", True),
    ("src/*.py", "src/sub/a.py", False),
    ("**/test_*.py", "test_a.py", True),
    ("**/test_*.py", "x/y/test_a.py", True),
    ("src/?.py", "src/a.py", True),
    ("src/?.py", "src/ab.py", False),
    ("Src/a.py", "src/a.py", False),
    ("src/", "src/deep/a.py", True),
    ("src/{a,b}.py", "src/a.py", False),
])
def test_goal_scope_globs(pattern, path, expected):
    assert gs.glob_match(pattern, path) is expected


def test_goal_scope_globs_in_ledger(tmp_path):
    repo = make_repo(tmp_path, rows=(("G1", "src/*.py, lib/a.py"), ("G2", ""), ("G3", "docs/**")))
    hook = Hook(repo, tmp_path)
    hook.prompt()
    write(repo, "src/dates.py", "x = 2\n")
    write(repo, "lib/a.py", "a = 2\n")
    write(repo, "lib/b.py", "b = 2\n")
    msg = message(hook.stop())
    assert "von G1, G3:" in msg and "lib/b.py" in msg and "lib/a.py" not in msg and "src/dates.py" not in msg

    empty = make_repo(tmp_path, rows=(("G1", ""),), name="leer")
    hook = Hook(empty, tmp_path)
    hook.prompt()
    write(empty, "lib/b.py", "b = 2\n")
    assert hook.stop() == {}, "nur Ziele ohne Bereich: der Hook übergeht sie"


def test_goal_scope_ignores_house_artifacts(tmp_path):
    repo = make_repo(tmp_path)
    hook = Hook(repo, tmp_path)
    hook.prompt()
    write(repo, "docs/goals.md", (repo / "docs/goals.md").read_text(encoding="utf-8") + "\n")
    for rel in ("handoff.md", ".claude/rules/x.md", ".skills/cache/x.json", "CLAUDE.md", ".gitignore",
                "docs/debugging/2026-10-12-x.md", "docs/decisions.md", "docs/specs/wip/x.md"):
        write(repo, rel, "x\n")
    assert hook.stop() == {}


def test_goal_scope_silent_or_visible(tmp_path):
    no_ledger = make_repo(tmp_path, rows=None, name="ohne-ledger")
    hook = Hook(no_ledger, tmp_path)
    assert hook.prompt() == {}
    write(no_ledger, "lib/a.py", "a = 2\n")
    assert hook.stop() == {}

    idle = make_repo(tmp_path, rows=(), name="ohne-ziel")
    hook = Hook(idle, tmp_path)
    hook.prompt()
    write(idle, "lib/a.py", "a = 2\n")
    assert hook.stop() == {}

    fresh = make_repo(tmp_path, name="ohne-commit", commit=False)
    hook = Hook(fresh, tmp_path)
    assert hook.prompt() == {}
    write(fresh, "lib/a.py", "a = 2\n")
    assert hook.stop() == {}

    foreign = make_repo(tmp_path, name="fremd")
    write(foreign, "docs/goals.md", ledger((("G1", "src/greet.py"),), header="<!-- skill: other | schema: 9 | generated: x -->"))
    git(foreign, "commit", "-q", "-am", "fremde Kopfzeile")
    hook = Hook(foreign, tmp_path)
    hook.prompt()
    write(foreign, "lib/a.py", "a = 2\n")
    msg = message(hook.stop())
    assert msg.startswith("[setup-repo]") and "Kopfzeile" in msg
    write(foreign, "lib/b.py", "b = 2\n")
    assert hook.stop() == {}, "derselbe Grund nur einmal je Session"

    nogit = make_repo(tmp_path, name="ohne-git")
    hook = Hook(nogit, tmp_path)
    bindir = tmp_path / "bin-ohne-git"
    bindir.mkdir()
    env = {"PATH": str(bindir)}
    hook.prompt(env=env)
    msg = message(hook.stop(env=env))
    assert msg.startswith("[setup-repo]") and "git" in msg
    assert hook.stop(env=env) == {}

    broken = make_repo(tmp_path, name="kaputt")
    hook = Hook(broken, tmp_path)
    hook.state.write_text("{kaputt", encoding="utf-8")
    hook.prompt()
    write(broken, "lib/a.py", "a = 2\n")
    assert "lib/a.py" in message(hook.stop())
    state = json.loads(hook.state.read_text(encoding="utf-8"))
    assert state["_meta"]["skill"] == "setup-repo" and "s1" in state["sessions"]


def test_goal_scope_output_shape(tmp_path):
    repo = make_repo(tmp_path)
    hook = Hook(repo, tmp_path)
    hook.prompt()
    write(repo, "lib/a.py", "a = 2\n")
    stop = hook.stop()
    assert set(stop) == {"systemMessage"} and "decision" not in stop
    prompt = hook.prompt()
    assert set(prompt) == {"hookSpecificOutput"}
    assert prompt["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert prompt["hookSpecificOutput"]["additionalContext"].startswith("[setup-repo]")
    for raw in (b"", b"{kaputt", b"[1]", b'{"hook_event_name": "Stop", "session_id": null}'):
        hook.run("Stop", raw=raw)
    default_state = repo / ".skills" / "cache" / "setup-repo" / "goal-scope.json"
    assert not default_state.exists(), "mit SETUP_REPO_GOAL_STATE kein Zustand im Repo"
