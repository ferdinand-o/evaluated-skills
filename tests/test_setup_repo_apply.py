"""Tests für skills/setup-repo/scripts/apply_repo.py (Spec 22, Abschnitt B).

Mini-Repos mit git in tmp_path. Pläne entstehen mit plan_repo.py wie im echten Ablauf;
apply schreibt in jedem Fall apply.md und committet nie."""

import json
import subprocess
import sys

from conftest import REPO_ROOT, load_script

detect_mod = load_script("skills/setup-repo/scripts/detect_repo.py")
harvest_mod = load_script("skills/setup-repo/scripts/harvest_rules.py")
plan_mod = load_script("skills/setup-repo/scripts/plan_repo.py")
apply_mod = load_script("skills/setup-repo/scripts/apply_repo.py")
SCRIPTS = REPO_ROOT / "skills" / "setup-repo" / "scripts"
CACHE = ".skills/cache/setup-repo"


def write(root, rel, text=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, check=True,
                          capture_output=True, text=True).stdout


def committed_repo(tmp_path, files, name="repo"):
    repo = tmp_path / name
    for rel, text in files.items():
        write(repo, rel, text)
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "start")
    return repo


def make_plan(repo, cfg, **options):
    detect = detect_mod.detect(repo, cfg)
    block = plan_mod.build_plan(repo, detect, harvest_mod.harvest(repo, detect), options)
    path = repo / CACHE / "plan.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan_mod.render_plan(block), encoding="utf-8", newline="\n")
    return path, block


def report(repo):
    return (repo / CACHE / "apply.md").read_text(encoding="utf-8")


def files_outside_cache(repo):
    return {p.relative_to(repo).as_posix(): p.read_bytes() for p in repo.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(repo).parts
            and not p.relative_to(repo).as_posix().startswith(".skills/")}


def test_hash_functions_agree(tmp_path):
    cfg = tmp_path / "cfg"
    for i, files in enumerate([{"Makefile": "check:\n\ttrue\n"}, {"README.md": "ä ö ü — x\n"},
                               {"AGENTS.md": "# A\n", "pyproject.toml": "[tool.ruff]\nline-length = 90\n"}]):
        repo = committed_repo(tmp_path, files, name=f"r{i}")
        _, block = make_plan(repo, cfg, verify_hook=True, deny_secrets=True)
        assert apply_mod.canonical_hash(block) == plan_mod.plan_hash(block) == block["hash"]


def test_apply_refuses_dirty_target_and_changed_plan(tmp_path):
    cfg = tmp_path / "cfg"
    repo = committed_repo(tmp_path, {"CLAUDE.md": "# Alt\n", "Makefile": "check:\n\ttrue\n"})
    write(repo, "CLAUDE.md", "# Alt, ungespeichert geändert\n")
    plan, _ = make_plan(repo, cfg)
    before = files_outside_cache(repo)
    result = apply_mod.apply_plan(repo, plan)
    assert result["ok"] is False
    assert "uncommittete Änderungen" in report(repo) and "CLAUDE.md" in report(repo)
    assert files_outside_cache(repo) == before

    clean = committed_repo(tmp_path, {"Makefile": "check:\n\ttrue\n"}, name="clean")
    plan, _ = make_plan(clean, cfg)
    tampered = plan.read_text(encoding="utf-8")
    block_start = tampered.index("```json setup-repo-plan")
    plan.write_text(tampered[:block_start] + tampered[block_start:].replace("make check", "make chek", 1),
                    encoding="utf-8")
    before = files_outside_cache(clean)
    assert apply_mod.apply_plan(clean, plan)["ok"] is False
    assert "Hash passt nicht" in report(clean)
    assert files_outside_cache(clean) == before and not (clean / "CLAUDE.md").exists()

    skills = committed_repo(tmp_path, {"Makefile": "check:\n\ttrue\n"}, name="skills")
    write(skills, ".claude/skills/setup-repo/SKILL.md", "---\nname: setup-repo\n---\n")
    plan, _ = make_plan(skills, cfg)
    assert apply_mod.apply_plan(skills, plan)["ok"] is True, report(skills)


def test_apply_refuses_changed_state(tmp_path):
    repo = committed_repo(tmp_path, {"Makefile": "check:\n\ttrue\n"})
    plan, _ = make_plan(repo, tmp_path / "cfg")
    write(repo, "CLAUDE.md", "# inzwischen angelegt\n")
    assert apply_mod.apply_plan(repo, plan)["ok"] is False
    assert "Bestand geändert" in report(repo)
    assert (repo / "CLAUDE.md").read_text(encoding="utf-8") == "# inzwischen angelegt\n"


def test_apply_backs_up_local_settings_and_ignores_them(tmp_path):
    cfg = tmp_path / "cfg"
    install = cfg / "plugins" / "cache" / "m" / "x"
    write(install, ".claude-plugin/marketplace.json", json.dumps({"plugins": [{"name": "cc-ui", "skills": ["./skills/ui"]}]}))
    write(cfg, "plugins/installed_plugins.json",
          json.dumps({"plugins": {"cc-ui@cc-skills": [{"installPath": str(install)}]}}))
    repo = committed_repo(tmp_path, {"package.json": json.dumps({"dependencies": {"react": "18"}}),
                                     ".gitignore": "node_modules/\n"})
    old = '{\n  "enabledPlugins": {"a@b": true},\n  "x": 1\n}\n'
    write(repo, ".claude/settings.local.json", old)
    plan, _ = make_plan(repo, cfg)
    result = apply_mod.apply_plan(repo, plan)
    assert result["ok"] is True, report(repo)
    merged = json.loads((repo / ".claude/settings.local.json").read_text(encoding="utf-8"))
    assert merged == {"enabledPlugins": {"a@b": True, "cc-ui@cc-skills": True}, "x": 1}
    (backup,) = (repo / CACHE / "backups").glob("*/.claude/settings.local.json")
    assert backup.read_text(encoding="utf-8") == old
    assert (repo / ".gitignore").read_text(encoding="utf-8") == \
        "node_modules/\n.skills/cache/\n.claude/settings.local.json\n"
    assert "settings.local.json" not in git(repo, "status", "--porcelain")


def test_apply_merges_existing_settings(tmp_path):
    foreign = {"type": "command", "command": "echo fremd"}
    settings = {"model": "x", "permissions": {"allow": ["Bash(ls)", "Bash(make check)"]},
                "hooks": {"Stop": [{"hooks": [foreign]}]}}
    repo = committed_repo(tmp_path, {"Makefile": "check:\n\ttrue\nlint:\n\ttrue\n",
                                     ".claude/settings.json": json.dumps(settings, indent=2) + "\n"})
    cfg = tmp_path / "cfg"
    plan, _ = make_plan(repo, cfg, verify_hook=True, deny_secrets=True)
    assert apply_mod.apply_plan(repo, plan)["ok"] is True, report(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "eingerichtet")
    plan, _ = make_plan(repo, cfg, verify_hook=True, deny_secrets=True)
    assert apply_mod.apply_plan(repo, plan)["ok"] is True, report(repo)

    data = json.loads((repo / ".claude/settings.json").read_text(encoding="utf-8"))
    assert list(data) == ["model", "permissions", "hooks"] and data["model"] == "x"
    assert data["permissions"]["allow"] == ["Bash(ls)", "Bash(make check)", "Bash(make lint)"]
    assert "Read(./.env)" in data["permissions"]["deny"]
    stop = [h for entry in data["hooks"]["Stop"] for h in entry["hooks"]]
    assert stop[0] == foreign
    assert sum(".claude/hooks/verify_stop.py" in h["command"] for h in stop) == 1
    assert (repo / ".claude/hooks/verify_stop.py").is_file()


def test_apply_is_idempotent(tmp_path):
    repo = committed_repo(tmp_path, {"Makefile": "check:\n\ttrue\n", "CONTRIBUTING.md": "- Tests zuerst.\n"})
    cfg = tmp_path / "cfg"
    plan, _ = make_plan(repo, cfg, classes={"c1": "regel"})
    assert apply_mod.apply_plan(repo, plan)["ok"] is True
    first = files_outside_cache(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "eingerichtet")
    plan, block = make_plan(repo, cfg, classes={"c1": "regel"})
    assert {op["path"] for op in block["operations"]} == {".claude/settings.json"}
    assert apply_mod.apply_plan(repo, plan)["ok"] is True
    assert files_outside_cache(repo) == first


def test_apply_never_commits(tmp_path):
    repo = committed_repo(tmp_path, {"Makefile": "check:\n\ttrue\n"})
    head = git(repo, "rev-parse", "HEAD")
    plan, _ = make_plan(repo, tmp_path / "cfg")
    proc = subprocess.run([sys.executable, str(SCRIPTS / "apply_repo.py"), "--repo", str(repo)],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert git(repo, "rev-parse", "HEAD") == head
    text = report(repo)
    assert text.splitlines()[0].startswith("<!-- skill: setup-repo | schema: 1 | generated: python")
    assert "angewendet" in text and "CLAUDE.md" in text
    assert "Verifikation: `make check`" in (repo / "CLAUDE.md").read_text(encoding="utf-8")


# --- check (Task 8) ----------------------------------------------------------------

def check_text(repo):
    return (repo / CACHE / "check.md").read_text(encoding="utf-8")


def applied_repo(tmp_path, files, name="repo", **options):
    repo = committed_repo(tmp_path, files, name=name)
    plan, _ = make_plan(repo, tmp_path / "cfg", **options)
    assert apply_mod.apply_plan(repo, plan)["ok"] is True, report(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "eingerichtet")
    return repo


def test_check_aligned_reports_no_deviation(tmp_path):
    repo = applied_repo(tmp_path, {"Makefile": "check:\n\ttrue\n"}, verify_hook=True)
    before = files_outside_cache(repo)
    cache_before = {p.name for p in (repo / CACHE).iterdir()}
    head = git(repo, "rev-parse", "HEAD")
    proc = subprocess.run([sys.executable, str(SCRIPTS / "apply_repo.py"), "--repo", str(repo), "--check"],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = check_text(repo)
    assert text.splitlines()[0].startswith("<!-- skill: setup-repo | schema: 1 | generated: python")
    assert "keine Abweichung" in text
    assert files_outside_cache(repo) == before and git(repo, "rev-parse", "HEAD") == head
    assert {p.name for p in (repo / CACHE).iterdir()} - cache_before == {"check.md"}


def test_check_reports_drift(tmp_path):
    repo = applied_repo(tmp_path, {"Makefile": "check:\n\ttrue\n"}, verify_hook=True)
    write(repo, "CLAUDE.md", (repo / "CLAUDE.md").read_text(encoding="utf-8") + "Noch eine Zeile.\n")
    (repo / ".claude/hooks/verify_stop.py").unlink()
    write(repo, ".claude/rules/lang.md", "".join(f"Regel {i}\n" for i in range(200)))
    result = apply_mod.check_repo(repo)
    assert result["ok"] is False
    text = check_text(repo)
    assert "keine Abweichung" not in text
    assert "`CLAUDE.md`" in text and "`.claude/hooks/verify_stop.py`" in text and "Budget" in text
    assert len(result["deviations"]) == 3


def test_check_without_plan_is_unverified(tmp_path):
    repo = committed_repo(tmp_path, {"CLAUDE.md": "# x\n"})
    result = apply_mod.check_repo(repo)
    text = check_text(repo)
    assert "ungeprüft — kein Plan" in text and result["deviations"] == []
    assert "Budget" in text


def test_check_keeps_cc_skills_switch(tmp_path):
    settings = {"enabledPlugins": {"cc-dev@cc-skills": False}}
    repo = applied_repo(tmp_path, {"Makefile": "check:\n\ttrue\n",
                                   ".claude/settings.json": json.dumps(settings, indent=2) + "\n"})
    data = json.loads((repo / ".claude/settings.json").read_text(encoding="utf-8"))
    assert data["enabledPlugins"] == {"cc-dev@cc-skills": False}
    assert apply_mod.check_repo(repo)["ok"] is True
    assert "keine Abweichung" in check_text(repo)


def test_check_flags_tampered_plan(tmp_path):
    repo = applied_repo(tmp_path, {"Makefile": "check:\n\ttrue\n"})
    plan = repo / CACHE / "plan.md"
    text = plan.read_text(encoding="utf-8")
    start = text.index("```json setup-repo-plan")
    plan.write_text(text[:start] + text[start:].replace("make check", "make chek", 1), encoding="utf-8")
    assert apply_mod.check_repo(repo)["ok"] is False
    assert "Hash passt nicht" in check_text(repo)


# --- Ziele (Abschnitt C) -----------------------------------------------------------

def test_apply_probes_goal_hook_without_touching_state(tmp_path):
    repo = committed_repo(tmp_path, {"Makefile": "check:\n\ttrue\n"})
    plan, _ = make_plan(repo, tmp_path / "cfg")
    result = apply_mod.apply_plan(repo, plan)
    assert result["ok"] is True and result["status"] == "angewendet und geprüft", report(repo)
    assert "goal_scope.py" in report(repo) and "Probe" in report(repo)
    assert not (repo / CACHE / "goal-scope.json").exists()
    assert (repo / "docs/goals.md").is_file() and (repo / ".claude/rules/goals.md").is_file()


def test_apply_merges_goal_hook_once(tmp_path):
    foreign = {"type": "command", "command": "echo fremd"}
    settings = {"hooks": {"UserPromptSubmit": [{"hooks": [foreign]}]}}
    repo = committed_repo(tmp_path, {"Makefile": "check:\n\ttrue\n",
                                     ".claude/settings.json": json.dumps(settings, indent=2) + "\n"})
    for _ in range(2):
        plan, _ = make_plan(repo, tmp_path / "cfg")
        assert apply_mod.apply_plan(repo, plan)["ok"] is True, report(repo)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "--allow-empty", "-m", "eingerichtet")
    hooks = json.loads((repo / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]
    for event in ("UserPromptSubmit", "Stop"):
        commands = [h["command"] for entry in hooks[event] for h in entry["hooks"]]
        assert sum("goal_scope.py" in c for c in commands) == 1, event
    assert hooks["UserPromptSubmit"][0]["hooks"][0] == foreign


def test_check_reads_ledger_header(tmp_path):
    repo = applied_repo(tmp_path, {"Makefile": "check:\n\ttrue\n"})
    assert apply_mod.check_repo(repo)["ok"] is True
    ledger = repo / "docs/goals.md"
    ledger.write_text("# Ziele ohne Kopfzeile\n", encoding="utf-8")
    result = apply_mod.check_repo(repo)
    assert any(d.startswith("`docs/goals.md`") and "Kopfzeile" in d for d in result["deviations"])
