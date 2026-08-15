import json
import subprocess

import pytest
from evalkit.workspace import WorkspaceError, dump_changed_files, prepare, snapshot


def make_skill(tmp_path, name="handoff"):
    skill = tmp_path / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n", encoding="utf-8")
    return skill


def make_fixture(tmp_path, *, git=True, name="dirty-worktree"):
    fixture = tmp_path / "fixtures" / name
    fixture.mkdir(parents=True)
    (fixture / "fixture.json").write_text(json.dumps({"git": git, "description": "test"}), encoding="utf-8")
    (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
    (fixture / "CLAUDE.md").write_text("# Konventionen\n", encoding="utf-8")
    return fixture


def test_copies_fixture_content(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    assert (ws.root / "README.md").is_file()
    assert (ws.root / "CLAUDE.md").is_file()


def test_installs_skill_as_project_skill(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    installed = ws.root / ".claude" / "skills" / "handoff" / "SKILL.md"
    assert installed.is_file()
    assert "name: handoff" in installed.read_text(encoding="utf-8")


def test_fixture_json_is_not_copied_into_workspace(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    assert not (ws.root / "fixture.json").exists()


def test_git_fixture_gets_repo_with_one_commit(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path, git=True))
    assert (ws.root / ".git").is_dir()
    assert ws.baseline["__git_head__"]


def test_non_git_fixture_has_no_repo(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path, git=False))
    assert not (ws.root / ".git").exists()
    assert ws.baseline["__git_head__"] is None


def test_baseline_hashes_fixture_files_but_not_dot_git(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    assert "CLAUDE.md" in ws.baseline
    assert not any(key.startswith(".git/") for key in ws.baseline)


def test_baseline_excludes_installed_skill(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    assert not any(key.startswith(".claude/") for key in ws.baseline)


def test_prepare_without_fixture_creates_empty_workspace(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), None)
    assert ws.root.is_dir()
    assert list(ws.root.iterdir()) == [ws.root / ".claude"]


def test_missing_skill_dir_raises(tmp_path):
    with pytest.raises(WorkspaceError, match="Skill"):
        prepare(tmp_path / "ws", tmp_path / "nope", None)


def test_snapshot_is_stable_for_unchanged_tree(tmp_path):
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    assert snapshot(tmp_path) == snapshot(tmp_path)


def test_snapshot_skips_symlinks(tmp_path):
    """is_file() folgt Symlinks — ein Symlink aus dem Workspace nach außen darf nicht
    dazu führen, dass der Inhalt des externen Ziels gehasht (und später über
    dump_changed_files in den Judge-Prompt gegeben) wird."""
    secret = tmp_path / "outside-secret.txt"
    secret.write_text("geheim", encoding="utf-8")
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "escape.txt").symlink_to(secret)
    result = snapshot(root)
    assert "escape.txt" not in result


def test_dump_changed_files_ignores_symlinks(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    secret = tmp_path / "outside-secret.txt"
    secret.write_text("geheim", encoding="utf-8")
    (ws.root / "escape.txt").symlink_to(secret)
    dump = dump_changed_files(ws.root, ws.baseline)
    assert "geheim" not in dump
    assert "escape.txt" not in dump


def test_dump_changed_files_shows_only_new_and_changed(tmp_path):
    """Der Judge urteilt über Artefakte — er braucht deren Inhalt, nicht das ganze Repo."""
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    (ws.root / "handoff.md").write_text("# Handoff\n## Status\nfoo\n", encoding="utf-8")
    dump = dump_changed_files(ws.root, ws.baseline)
    assert "handoff.md" in dump
    assert "## Status" in dump
    assert "CLAUDE.md" not in dump


def test_dump_changed_files_reports_when_nothing_changed(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    assert "keine Datei" in dump_changed_files(ws.root, ws.baseline)


def test_missing_git_binary_raises_workspace_error(tmp_path, monkeypatch):
    """Fehlt `git` im PATH, muss prepare() eine verständliche WorkspaceError werfen statt
    den rohen FileNotFoundError von subprocess.run durchzureichen."""
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    with pytest.raises(WorkspaceError, match="git"):
        prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path, git=True))


def test_broken_fixture_json_raises_workspace_error(tmp_path):
    fixture = tmp_path / "fixtures" / "broken"
    fixture.mkdir(parents=True)
    (fixture / "fixture.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="fixture.json"):
        prepare(tmp_path / "ws", make_skill(tmp_path), fixture)


def test_git_baseline_commit_excludes_installed_skill(tmp_path):
    """Die Skill wird erst nach dem Baseline-Commit installiert. Landete sie im Commit
    "fixture baseline", würde ein Agent, der sich per `git log`/`git status` erdet, die
    Installationsspuren des Harness für Projektinhalt halten (Punkt 4 des
    Schluss-Reviews)."""
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path, git=True))
    tracked = subprocess.run(
        ["git", "ls-tree", "-r", "HEAD", "--name-only"],
        cwd=ws.root, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    assert not any(path.startswith(".claude/") for path in tracked)
    # Die Skill ist trotzdem installiert, nur eben ungetrackt.
    assert (ws.root / ".claude" / "skills" / "handoff" / "SKILL.md").is_file()


def test_prepare_warns_when_fixture_brings_its_own_skill_dir(tmp_path, capsys):
    """Bringt eine Fixture selbst schon .claude/skills/<name>/ mit, überschreibt die
    echte Skill sie stillschweigend — das verdient eine Warnzeile statt eines lautlosen
    Verlusts (Punkt 5)."""
    fixture = make_fixture(tmp_path)
    fixture_skill = fixture / ".claude" / "skills" / "handoff"
    fixture_skill.mkdir(parents=True)
    (fixture_skill / "SKILL.md").write_text("fixture-fake", encoding="utf-8")

    ws = prepare(tmp_path / "ws", make_skill(tmp_path, name="handoff"), fixture)

    captured = capsys.readouterr()
    assert "Warnung" in captured.out
    assert ".claude/skills/handoff" in captured.out
    installed = ws.root / ".claude" / "skills" / "handoff" / "SKILL.md"
    assert "fixture-fake" not in installed.read_text(encoding="utf-8")
    assert "name: handoff" in installed.read_text(encoding="utf-8")


def test_broken_symlink_in_fixture_raises_workspace_error(tmp_path):
    """Ein toter Symlink lässt shutil.copytree mit shutil.Error scheitern — prepare()
    muss das in eine WorkspaceError übersetzen statt den rohen Fehler durchzureichen."""
    fixture = tmp_path / "fixtures" / "broken-symlink"
    fixture.mkdir(parents=True)
    (fixture / "fixture.json").write_text(json.dumps({"git": False}), encoding="utf-8")
    (fixture / "dangling.md").symlink_to(fixture / "does-not-exist.md")
    with pytest.raises(WorkspaceError, match="kopiert"):
        prepare(tmp_path / "ws", make_skill(tmp_path), fixture)


def make_history_fixture(tmp_path, commits, name="history"):
    fixture = tmp_path / "fixtures" / name
    fixture.mkdir(parents=True)
    (fixture / "fixture.json").write_text(
        json.dumps({"git": True, "description": "test", "commits": commits}), encoding="utf-8"
    )
    (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
    return fixture


def git_log(root):
    import subprocess
    done = subprocess.run(
        ["git", "log", "--format=%s"], cwd=root, capture_output=True, text=True, check=True
    )
    return done.stdout.split()


def test_commits_field_creates_one_commit_per_entry(tmp_path):
    fixture = make_history_fixture(tmp_path, [
        {"message": "erst", "touch": {"a.py": "x = 1\n"}},
        {"message": "dann", "touch": {"b.py": "y = 2\n"}},
    ])
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), fixture)
    assert git_log(ws.root) == ["dann", "erst", "fixture", "baseline"]
    assert (ws.root / "a.py").read_text(encoding="utf-8") == "x = 1\n"
    assert (ws.root / "b.py").read_text(encoding="utf-8") == "y = 2\n"


def test_commits_field_supports_delete_and_tag(tmp_path):
    import subprocess
    fixture = make_history_fixture(tmp_path, [
        {"message": "anlegen", "touch": {"weg.py": "tot\n"}, "tag": "v1.0"},
        {"message": "entfernen", "delete": ["weg.py"]},
    ])
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), fixture)
    assert not (ws.root / "weg.py").exists()
    tags = subprocess.run(["git", "tag"], cwd=ws.root, capture_output=True, text=True, check=True)
    assert tags.stdout.split() == ["v1.0"]


def test_fixture_content_is_committed_before_declared_commits(tmp_path):
    """Mitgelieferte Dateien bilden weiterhin den Baseline-Commit."""
    fixture = make_history_fixture(tmp_path, [{"message": "spaeter", "touch": {"a.py": "x\n"}}])
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), fixture)
    assert git_log(ws.root) == ["spaeter", "fixture", "baseline"]


def test_without_commits_field_behaviour_is_unchanged(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path, git=True))
    assert git_log(ws.root) == ["fixture", "baseline"]


def test_commit_without_message_is_rejected(tmp_path):
    fixture = make_history_fixture(tmp_path, [{"touch": {"a.py": "x\n"}}])
    with pytest.raises(WorkspaceError, match="message"):
        prepare(tmp_path / "ws", make_skill(tmp_path), fixture)


def test_commit_with_unsafe_path_is_rejected(tmp_path):
    fixture = make_history_fixture(tmp_path, [{"message": "boese", "touch": {"../draussen.py": "x\n"}}])
    with pytest.raises(WorkspaceError, match="Pfad"):
        prepare(tmp_path / "ws", make_skill(tmp_path), fixture)


def test_commits_field_without_git_is_rejected(tmp_path):
    fixture = tmp_path / "fixtures" / "nogit"
    fixture.mkdir(parents=True)
    (fixture / "fixture.json").write_text(
        json.dumps({"git": False, "commits": [{"message": "x"}]}), encoding="utf-8"
    )
    with pytest.raises(WorkspaceError, match="git"):
        prepare(tmp_path / "ws", make_skill(tmp_path), fixture)
