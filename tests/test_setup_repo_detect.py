"""Tests für skills/setup-repo/scripts/detect_repo.py (Spec 22, Abschnitt B).

Mini-Repos in tmp_path, ein Fake-Config-Verzeichnis für Plugin-IDs; kein Test liest das
echte Home."""

import json
import subprocess
import sys

from conftest import REPO_ROOT, load_script

detect_mod = load_script("skills/setup-repo/scripts/detect_repo.py")
SCRIPT = REPO_ROOT / "skills" / "setup-repo" / "scripts" / "detect_repo.py"


def write(root, rel, text=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_detect_python_ts_delphi_frontend_none(tmp_path):
    cfg = tmp_path / "cfg"
    cfg.mkdir()

    py = tmp_path / "py"
    write(py, "pyproject.toml", '[tool.ruff]\nline-length = 100\n\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    write(py, "Makefile", ".PHONY: check\ncheck: lint test\nlint:\n\truff check .\ntest:\n\tpytest\nVAR := 1\n")
    write(py, "src/app.py", "x = 1\n")
    write(py, "tests/test_app.py", "def test_x(): pass\n")
    write(py, "CLAUDE.md", "# x\n")
    write(py, ".claude/CLAUDE.md", "# y\n")
    write(py, "CLAUDE.local.md", "# z\n")
    write(py, ".claude/skills/handoff/SKILL.md", "---\nname: handoff\n---\n")
    write(py, ".github/workflows/ci.yml", "on: push\n")
    d = detect_mod.detect(py, cfg)
    assert d["languages"] == ["python"] and d["frontend"] is None
    assert d["runners"]["make"] == ["check", "lint", "test"]
    assert d["tests"] is True and d["pytest_config"] is True
    assert {"tool": "ruff", "config": "pyproject.toml"} in d["linters"]
    assert d["claude_files"] == [".claude/CLAUDE.md", "CLAUDE.local.md", "CLAUDE.md"]
    assert d["agents_md"] is False and d["project_skills"] == ["handoff"]
    assert d["ci"] == [".github/workflows/ci.yml"]

    ts = tmp_path / "ts"
    write(ts, "package.json", json.dumps({"scripts": {"lint": "eslint .", "test": "vitest", "build": "vite build"},
                                          "dependencies": {"react": "^18.0.0"}}))
    write(ts, "pnpm-lock.yaml", "")
    write(ts, "tsconfig.json", '{"compilerOptions": {"strict": true}}')
    write(ts, "src/App.tsx", "export {}\n")
    write(ts, "src/App.test.tsx", "export {}\n")
    write(ts, "AGENTS.md", "# Agents\n")
    write(ts, "node_modules/x/index.ts", "export {}\n")
    d = detect_mod.detect(ts, cfg)
    assert d["languages"] == ["typescript"] and d["frontend"] == "react"
    assert d["runners"]["npm"] == {"build": "vite build", "lint": "eslint .", "test": "vitest"}
    assert d["runners"]["package_manager"] == "pnpm"
    assert d["tests"] is True and d["agents_md"] is True and d["claude_files"] == []
    assert {"tool": "tsc", "config": "tsconfig.json"} in d["linters"]

    delphi = tmp_path / "delphi"
    write(delphi, "App/App.dproj", "<Project/>")
    write(delphi, "App/Main.pas", "unit Main;\n")
    d = detect_mod.detect(delphi, cfg)
    assert d["languages"] == ["delphi"] and d["delphi_projects"] == ["App/App.dproj"]
    assert d["tests"] is False and d["frontend"] is None

    empty = tmp_path / "empty"
    empty.mkdir()
    d = detect_mod.detect(empty, cfg)
    assert d["languages"] == [] and d["runners"]["make"] == [] and d["tests"] is False
    assert d["plugins"] == [] and d["project_skills"] == []


def test_detect_plugin_ids(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = tmp_path / "cfg"
    install = cfg / "plugins" / "cache" / "cc-skills" / "abc"
    write(install, ".claude-plugin/marketplace.json", json.dumps({"plugins": [
        {"name": "cc-dev", "source": "./", "skills": ["./skills/handoff", "./skills/debug-ledger"]},
        {"name": "cc-ui", "source": "./", "skills": ["./skills/enterprise-ui"]}]}))
    other = cfg / "plugins" / "cache" / "market" / "tool"
    write(other, "skills/lint-help/SKILL.md", "---\nname: lint-help\n---\n")
    write(cfg, "plugins/installed_plugins.json", json.dumps({"version": 2, "plugins": {
        "cc-dev@cc-skills": [{"scope": "user", "installPath": str(install)}],
        "cc-ui@cc-skills": [{"scope": "user", "installPath": str(install)}],
        "tool@market": [{"scope": "user", "installPath": str(other)}]}}))
    write(cfg, "plugins/synced/notes/.claude-plugin/plugin.json", json.dumps({"name": "notes"}))
    write(cfg, "plugins/synced/notes/skills/note-tag/SKILL.md", "---\nname: note-tag\n---\n")
    write(cfg, "plugins/synced/loose-skill/SKILL.md", "---\nname: loose-skill\n---\n")

    plugins = {p["id"]: p for p in detect_mod.detect(repo, cfg)["plugins"]}
    assert set(plugins) == {"cc-dev@cc-skills", "cc-ui@cc-skills", "tool@market", "notes@synced"}
    assert plugins["cc-dev@cc-skills"]["skills"] == ["debug-ledger", "handoff"]
    assert plugins["cc-ui@cc-skills"]["skills"] == ["enterprise-ui"]
    assert plugins["tool@market"]["skills"] == ["lint-help"]
    assert plugins["notes@synced"] == {"id": "notes@synced", "name": "notes", "marketplace": "synced",
                                       "skills": ["note-tag"]}

    assert detect_mod.detect(repo, tmp_path / "missing")["plugins"] == []
    write(tmp_path, "broken/plugins/installed_plugins.json", "{kaputt")
    assert detect_mod.detect(repo, tmp_path / "broken")["plugins"] == []


def test_detect_main_writes_detect_json_with_meta(tmp_path):
    repo = tmp_path / "repo"
    write(repo, "Makefile", "check:\n\ttrue\n")
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    proc = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo), "--config-dir", str(cfg)],
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    data = json.loads((repo / ".skills" / "cache" / "setup-repo" / "detect.json").read_text(encoding="utf-8"))
    assert data["_meta"]["skill"] == "setup-repo" and data["_meta"]["schema"] == 1
    assert data["runners"]["make"] == ["check"]
    assert sorted(p.name for p in repo.iterdir()) == [".skills", "Makefile"]
