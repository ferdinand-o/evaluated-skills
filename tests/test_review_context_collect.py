import json
import subprocess

import pytest

from conftest import load_script

cc = load_script("skills/review-context/scripts/collect_context.py")


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def write(repo, path, text):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def commit_all(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "--quiet", "-m", message)


@pytest.fixture
def repo(tmp_path):
    """Zwei Commits: eine Datei angelegt, dann geändert."""
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    write(tmp_path, "src/calc.py", "def add(a, b):\n    return a + b\n")
    commit_all(tmp_path, "feat: add")
    write(tmp_path, "src/calc.py", "def add(a, b):\n    return a + b + 0\n")
    commit_all(tmp_path, "fix: add ist jetzt expliziter")
    return tmp_path


# --- resolve_range ---------------------------------------------------------

def test_resolve_range_without_arg_is_uncommitted():
    mode, base, head, raw = cc.resolve_range(None)
    assert (mode, base, head, raw) == ("uncommitted", "HEAD", None, None)


def test_resolve_range_parses_two_dot():
    mode, base, head, raw = cc.resolve_range("HEAD~1..HEAD")
    assert mode == "range"
    assert base == "HEAD~1"
    assert head == "HEAD"
    assert raw == "HEAD~1..HEAD"


def test_resolve_range_rejects_three_dot():
    with pytest.raises(cc.CollectError, match="Drei-Punkt"):
        cc.resolve_range("main...feature/x")


def test_resolve_range_rejects_missing_dotdot():
    with pytest.raises(cc.CollectError, match="BASIS..ZIEL"):
        cc.resolve_range("HEAD")


def test_resolve_range_rejects_empty_side():
    with pytest.raises(cc.CollectError):
        cc.resolve_range("..HEAD")


# --- list_changed_files -----------------------------------------------------

def test_empty_diff_returns_empty_list(repo):
    files = cc.list_changed_files(repo, "range", "HEAD", "HEAD")
    assert files == []


def test_modified_file_has_before_and_after(repo):
    files = cc.list_changed_files(repo, "range", "HEAD~1", "HEAD")
    assert len(files) == 1
    f = files[0]
    assert f["path"] == "src/calc.py"
    assert f["status"] == "modified"
    assert "a + b\n" in f["before"]
    assert "a + b + 0\n" in f["after"]
    assert f["before_note"] is None
    assert f["after_note"] is None
    assert f["insertions"] >= 1


def test_new_file_has_no_before(repo):
    write(repo, "src/new.py", "x = 1\n")
    commit_all(repo, "feat: neue Datei")
    files = cc.list_changed_files(repo, "range", "HEAD~1", "HEAD")
    f = next(f for f in files if f["path"] == "src/new.py")
    assert f["status"] == "added"
    assert f["before"] is None
    assert f["before_note"] == "neu, kein Vorher-Stand"
    assert f["after"] is not None


def test_deleted_file_has_no_after(repo):
    (repo / "src/calc.py").unlink()
    commit_all(repo, "chore: calc entfernt")
    files = cc.list_changed_files(repo, "range", "HEAD~1", "HEAD")
    f = next(f for f in files if f["path"] == "src/calc.py")
    assert f["status"] == "deleted"
    assert f["after"] is None
    assert f["after_note"] == "gelöscht"
    assert f["before"] is not None


def test_binary_file_has_no_content_or_patch(repo):
    (repo / "assets").mkdir()
    (repo / "assets/logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00binaerdaten")
    commit_all(repo, "chore: logo")
    files = cc.list_changed_files(repo, "range", "HEAD~1", "HEAD")
    f = next(f for f in files if f["path"] == "assets/logo.png")
    assert f["status"] == "binary"
    assert f["before"] is None
    assert f["after"] is None
    assert f["patch"] is None
    assert "Binärdatei" in f["before_note"]


def test_renamed_file_carries_old_path(repo):
    git(repo, "mv", "src/calc.py", "src/calculator.py")
    commit_all(repo, "refactor: umbenannt")
    files = cc.list_changed_files(repo, "range", "HEAD~1", "HEAD")
    f = next(f for f in files if f["path"] == "src/calculator.py")
    assert f["status"] == "renamed"
    assert f["old_path"] == "src/calc.py"


def test_uncommitted_mode_reads_worktree(repo):
    write(repo, "src/calc.py", "def add(a, b):\n    return a + b + 1\n")
    files = cc.list_changed_files(repo, "uncommitted", "HEAD", None)
    assert len(files) == 1
    assert "a + b + 1" in files[0]["after"]


def test_content_truncation_is_named(repo, monkeypatch):
    monkeypatch.setattr(cc, "MAX_FILE_CHARS", 10)
    write(repo, "src/big.py", "x = 1\n" * 20)
    commit_all(repo, "feat: gross")
    files = cc.list_changed_files(repo, "range", "HEAD~1", "HEAD")
    f = next(f for f in files if f["path"] == "src/big.py")
    assert f["after_truncated"] is True
    assert "gekürzt" in f["after"]


def test_no_git_repo_raises(tmp_path):
    with pytest.raises(cc.CollectError):
        cc.list_changed_files(tmp_path, "range", "HEAD~1", "HEAD")


def test_changed_ranges_after_covers_modified_lines(repo):
    files = cc.list_changed_files(repo, "range", "HEAD~1", "HEAD")
    f = files[0]
    assert f["changed_ranges_after"]
    start, end = f["changed_ranges_after"][0]
    assert start <= 2 <= end
