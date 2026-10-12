"""Tests für skills/setup-repo/scripts/plan_repo.py (Spec 22, Abschnitt B).

Mini-Repos in tmp_path, leeres Fake-Config-Verzeichnis, außer wo Plugin-IDs gebraucht
werden. Der Plan schreibt nur unter .skills/cache/setup-repo/."""

import json
import re
import shutil
import subprocess
import sys

from conftest import REPO_ROOT, load_script

detect_mod = load_script("skills/setup-repo/scripts/detect_repo.py")
harvest_mod = load_script("skills/setup-repo/scripts/harvest_rules.py")
plan_mod = load_script("skills/setup-repo/scripts/plan_repo.py")
SCRIPTS = REPO_ROOT / "skills" / "setup-repo" / "scripts"
ASSETS = REPO_ROOT / "skills" / "setup-repo" / "assets"


def write(root, rel, text=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def git(root, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, check=True,
                   capture_output=True)


def plan_for(repo, cfg, **options):
    detect = detect_mod.detect(repo, cfg)
    return plan_mod.build_plan(repo, detect, harvest_mod.harvest(repo, detect), options)


def ops(block):
    return {op["path"]: op for op in block["operations"]}


def test_budget_counts_unscoped_rules_and_imports(tmp_path):
    repo = tmp_path / "repo"
    write(repo, "AGENTS.md", "".join(f"Zeile {i}\n" for i in range(10)))
    write(repo, ".claude/rules/allgemein.md", "a\nb\nc\nd\ne\n")
    write(repo, ".claude/rules/nur-src.md", '---\npaths:\n  - "src/**"\n---\nx\ny\nz\n')
    block = plan_for(repo, tmp_path / "cfg")
    claude = ops(block)["CLAUDE.md"]["content"]
    assert block["budget"] == {"lines": len(claude.splitlines()) + 10 + 5, "limit": 150}
    assert "überschritten" not in plan_mod.render_plan(block)

    write(repo, "AGENTS.md", "".join(f"Zeile {i}\n" for i in range(200)))
    block = plan_for(repo, tmp_path / "cfg")
    assert block["budget"]["lines"] > 150
    assert "Budget überschritten" in plan_mod.render_plan(block)


def test_plan_hash_is_path_head_and_eol_neutral(tmp_path):
    a = tmp_path / "ort-a" / "repo"
    write(a, "Makefile", "check:\n\ttrue\nlint:\n\ttrue\n")
    write(a, "pyproject.toml", "[tool.ruff]\nline-length = 100\n")
    write(a, "CLAUDE.md", "# Bestehend\n\nText.\n")
    write(a, ".claude/settings.json", '{\n  "permissions": {"allow": ["Bash(ls)"]}\n}\n')
    git(a, "init", "-q")
    git(a, "add", "-A")
    git(a, "commit", "-q", "-m", "erster Stand")

    b = tmp_path / "anderer-ort" / "kopie"
    shutil.copytree(a, b)
    write(b, "notiz.txt", "x")
    git(b, "add", "-A")
    git(b, "commit", "-q", "-m", "noch einer")
    (b / "notiz.txt").unlink()
    write(b, "CLAUDE.md", "# Bestehend\r\n\r\nText.\r\n")
    write(b, ".claude/settings.json", '{\r\n  "permissions": {"allow": ["Bash(ls)"]}\r\n}\r\n')
    write(b, ".claude/skills/setup-repo/SKILL.md", "---\nname: setup-repo\n---\n")

    classes = {"c1": "werkzeug"}
    block_a = plan_for(a, tmp_path / "cfg", classes=classes)
    block_b = plan_for(b, tmp_path / "cfg", classes=classes)
    assert block_a["hash"] == block_b["hash"]
    assert block_a == block_b
    assert block_a["hash"] == plan_mod.plan_hash(block_a)
    assert not any(p.startswith(".claude/skills/") for p in block_a["base"])
    assert str(tmp_path) not in json.dumps(block_a)


def test_agents_md_is_imported(tmp_path):
    repo = tmp_path / "repo"
    write(repo, "AGENTS.md", "# Agents\n")
    content = ops(plan_for(repo, tmp_path / "cfg"))["CLAUDE.md"]["content"]
    lines = content.splitlines()
    assert lines[0].startswith("<!-- skill: setup-repo | schema: 1 |") and lines[1] == "@AGENTS.md"

    write(repo, "CLAUDE.md", "# Eigene\n")
    op = ops(plan_for(repo, tmp_path / "cfg"))["CLAUDE.md"]
    assert op["action"] == "append" and "@AGENTS.md" not in op["content"]

    alone = tmp_path / "ohne"
    write(alone, "README.md", "x\n")
    assert "{{" not in ops(plan_for(alone, tmp_path / "cfg"))["CLAUDE.md"]["content"]
    assert "@AGENTS.md" not in ops(plan_for(alone, tmp_path / "cfg"))["CLAUDE.md"]["content"]


def test_choose_verification(tmp_path):
    cfg = tmp_path / "cfg"

    def choose(name, files):
        repo = tmp_path / name
        for rel, text in files.items():
            write(repo, rel, text)
        return plan_mod.choose_verification(detect_mod.detect(repo, cfg)), repo

    v, _ = choose("make-check", {"Makefile": "check:\n\ttrue\nlint:\n\ttrue\ntest:\n\ttrue\n"})
    assert v == {"command": "make check", "source": "Makefile: check", "derived": False}
    v, _ = choose("make-parts", {"Makefile": "lint:\n\ttrue\ntest:\n\ttrue\nbuild:\n\ttrue\n"})
    assert v["command"] == "make lint && make test" and v["source"] == "Makefile: lint, test"
    v, _ = choose("pnpm", {"package.json": json.dumps({"scripts": {"lint": "eslint .", "test": "vitest"}}),
                           "pnpm-lock.yaml": ""})
    assert v["command"] == "pnpm run lint && pnpm run test"
    v, _ = choose("pytest", {"pyproject.toml": "[tool.pytest.ini_options]\ntestpaths = ['tests']\n",
                             "tests/test_a.py": ""})
    assert v["command"] == "python -m pytest"
    v, repo = choose("delphi", {"App/App.dproj": "<Project/>", "App/Main.pas": ""})
    assert v == {"command": "msbuild App/App.dproj", "source": "App/App.dproj (abgeleitet)", "derived": True}
    block = plan_for(repo, cfg)
    settings = ops(block).get(".claude/settings.json")
    assert settings is None or "msbuild" not in json.dumps(settings["patch"])
    assert "abgeleitet" in plan_mod.render_plan(block)
    v, repo = choose("leer", {"README.md": "x\n"})
    assert v == {"command": None, "source": None, "derived": False}
    view = plan_mod.render_plan(plan_for(repo, cfg))
    assert "Verifikation: keine — ungeprüft" in view and "testing-strategy" in view
    assert "Verifikation: keine — ungeprüft" in ops(plan_for(repo, cfg))["CLAUDE.md"]["content"]


def test_plan_allows_verification_and_runner_parts(tmp_path):
    repo = tmp_path / "repo"
    write(repo, "Makefile", "check:\n\ttrue\nlint:\n\ttrue\ntest:\n\ttrue\nbuild:\n\ttrue\n")
    block = plan_for(repo, tmp_path / "cfg", deny_secrets=True)
    patch = ops(block)[".claude/settings.json"]["patch"]
    assert patch["permissions"]["allow"] == ["Bash(make check)", "Bash(make lint)", "Bash(make test)"]
    assert "Read(./.env)" in patch["permissions"]["deny"]
    assert "hooks" not in patch and ".claude/hooks/verify_stop.py" not in ops(block)
    assert "Verifikation: `make check`" in ops(block)["CLAUDE.md"]["content"]
    assert ops(block)[".gitignore"]["lines"] == [".skills/cache/", ".claude/settings.local.json"]


def test_plan_verify_hook_option(tmp_path):
    repo = tmp_path / "repo"
    write(repo, "Makefile", "check:\n\ttrue\n")
    block = plan_for(repo, tmp_path / "cfg", verify_hook=True)
    copy = ops(block)[".claude/hooks/verify_stop.py"]
    assert copy["action"] == "copy"
    assert copy["content"] == (ASSETS / "runtime" / "verify_stop.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    fragment = json.loads((ASSETS / "hooks" / "verify-stop.json").read_text(encoding="utf-8"))
    assert ops(block)[".claude/settings.json"]["patch"]["hooks"] == fragment["hooks"]
    assert block["options"]["verify_hook"] is True

    none = tmp_path / "ohne"
    write(none, "README.md", "x\n")
    block = plan_for(none, tmp_path / "cfg", verify_hook=True)
    assert ".claude/hooks/verify_stop.py" not in ops(block) and block["options"]["verify_hook"] is False
    assert "nicht angeboten" in plan_mod.render_plan(block)


def test_plan_enables_plugins_per_repo(tmp_path):
    cfg = tmp_path / "cfg"
    install = cfg / "plugins" / "cache" / "cc-skills" / "abc"
    write(install, ".claude-plugin/marketplace.json", json.dumps({"plugins": [
        {"name": "cc-dev", "skills": ["./skills/handoff"]}, {"name": "cc-ui", "skills": ["./skills/enterprise-ui"]},
        {"name": "cc-knowledge", "skills": ["./skills/explain"]}]}))
    write(cfg, "plugins/installed_plugins.json", json.dumps({"version": 2, "plugins": {
        f"{n}@cc-skills": [{"installPath": str(install)}] for n in ("cc-dev", "cc-ui", "cc-knowledge")}}))
    repo = tmp_path / "web"
    write(repo, "package.json", json.dumps({"dependencies": {"react": "18"}}))
    write(repo, ".claude/skills/handoff/SKILL.md", "---\nname: handoff\n---\n")
    block = plan_for(repo, cfg)
    assert block["plugins"] == {"cc-dev@cc-skills": False, "cc-ui@cc-skills": True}
    assert ops(block)[".claude/settings.local.json"]["patch"] == {"enabledPlugins": block["plugins"]}

    plain = tmp_path / "plain"
    write(plain, "README.md", "x\n")
    block = plan_for(plain, tmp_path / "leer")
    assert block["plugins"] == {} and ".claude/settings.local.json" not in ops(block)
    assert "ungeprüft — Plugin-ID nicht gefunden" in plan_mod.render_plan(block)


def test_plan_classes_make_rules(tmp_path):
    repo = tmp_path / "repo"
    write(repo, "CONTRIBUTING.md", "- Neue Funktionen bekommen einen Test.\n- Migrationen nur über alembic.\n"
                                   "- Kommentare auf Deutsch.\n")
    block = plan_for(repo, tmp_path / "cfg", classes={
        "c1": "regel", "c2": {"class": "regel", "paths": ["db/**/*.py"]}})
    claude = ops(block)["CLAUDE.md"]["content"]
    assert "- Neue Funktionen bekommen einen Test. (Quelle: CONTRIBUTING.md)" in claude
    assert "alembic" not in claude
    (rule_path,) = [p for p in ops(block) if p.startswith(".claude/rules/")]
    assert re.fullmatch(r"\.claude/rules/c2-[a-z0-9-]+\.md", rule_path)
    rule = ops(block)[rule_path]["content"].splitlines()
    assert rule[:4] == ["---", "paths:", '  - "db/**/*.py"', "---"]
    assert rule[4].startswith("<!-- skill: setup-repo | schema: 1 |")
    view = plan_mod.render_plan(block)
    assert re.search(r"Kommentare auf Deutsch\. · CONTRIBUTING\.md · offen", view)
    assert [c["class"] for c in block["candidates"]] == ["regel", "regel", "offen"]


def run(script, repo, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / script), "--repo", str(repo), *args],
                          capture_output=True, text=True, timeout=60)


def test_plan_writes_only_cache(tmp_path):
    repo = tmp_path / "repo"
    write(repo, "Makefile", "check:\n\ttrue\n")
    write(repo, "CONTRIBUTING.md", "- Tests zuerst.\n")
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    assert run("detect_repo.py", repo, "--config-dir", str(cfg)).returncode == 0
    assert run("harvest_rules.py", repo).returncode == 0
    before = {p.relative_to(repo).as_posix(): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    proc = run("plan_repo.py", repo, "--classes", '{"c1": "regel"}')
    assert proc.returncode == 0, proc.stderr
    after = {p.relative_to(repo).as_posix(): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    assert set(after) - set(before) == {".skills/cache/setup-repo/plan.md"}
    assert all(after[k] == v for k, v in before.items())
    text = after[".skills/cache/setup-repo/plan.md"].decode("utf-8")
    assert text.splitlines()[0].startswith("<!-- skill: setup-repo | schema: 1 | generated: python")
    assert text.count("```json setup-repo-plan") == 1
    assert proc.stdout.splitlines()[0].startswith("Repo: ")

    proc = run("plan_repo.py", repo, "--with-verify-hook")
    assert proc.returncode == 0, proc.stderr
    text = (repo / ".skills/cache/setup-repo/plan.md").read_text(encoding="utf-8")
    assert "Tests zuerst. · CONTRIBUTING.md · Regel" in text, "Klassen des letzten Plans bleiben"

    fresh = tmp_path / "fresh"
    fresh.mkdir()
    proc = run("plan_repo.py", fresh)
    assert proc.returncode == 2 and "detect_repo.py" in proc.stderr and not (fresh / ".skills").exists()
