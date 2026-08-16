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


# --- parse_given_when_then --------------------------------------------------

GWT_SAMPLE = """\
### Kriterium: Leerzeilen ergeben None

- **Given** eine Zeile
- **When** sie nur Leerzeichen enthält
- **Then** liefert parse() None

### Kriterium: Normale Zeile

- Given eine Zeile mit Inhalt
- When sie geparst wird
- Then liefert parse() das Tupel
- And der Trenner ist ein Doppelpunkt
"""


def test_parse_given_when_then_extracts_two_complete_blocks():
    criteria = cc.parse_given_when_then(GWT_SAMPLE)
    assert len(criteria) == 2
    assert criteria[0]["title"] == "Kriterium: Leerzeilen ergeben None"
    assert criteria[0]["given"] == "eine Zeile"
    assert criteria[0]["when"] == "sie nur Leerzeichen enthält"
    assert criteria[0]["then"] == "liefert parse() None"


def test_parse_given_when_then_collects_and_lines():
    criteria = cc.parse_given_when_then(GWT_SAMPLE)
    assert criteria[1]["and_"] == ["der Trenner ist ein Doppelpunkt"]


def test_parse_given_when_then_incomplete_block_is_dropped():
    text = "### Nur Given\n- Given etwas\n"
    assert cc.parse_given_when_then(text) == []


def test_parse_given_when_then_prose_only_is_empty():
    assert cc.parse_given_when_then("Das ist nur Fließtext ohne Struktur.\n") == []


# --- find_feature_spec -------------------------------------------------------

def test_find_feature_spec_missing_dir_returns_none(repo):
    assert cc.find_feature_spec(repo) is None


def test_find_feature_spec_empty_dir_returns_none(repo):
    (repo / "docs/specs/wip").mkdir(parents=True)
    assert cc.find_feature_spec(repo) is None


def test_find_feature_spec_parses_criteria(repo):
    write(repo, "docs/specs/wip/feature-x.md", GWT_SAMPLE)
    specs = cc.find_feature_spec(repo)
    assert len(specs) == 1
    assert specs[0]["path"] == "docs/specs/wip/feature-x.md"
    assert len(specs[0]["criteria"]) == 2
    assert "excerpt" not in specs[0]


def test_find_feature_spec_without_gwt_still_counts_with_excerpt(repo):
    write(repo, "docs/specs/wip/feature-y.md", "# Feature Y\n\nNur Prosa, keine Kriterien.\n")
    specs = cc.find_feature_spec(repo)
    assert specs[0]["criteria"] == []
    assert "Prosa" in specs[0]["excerpt"]


# --- find_pr_description -----------------------------------------------------

def test_find_pr_description_from_text(repo):
    result = cc.find_pr_description("Fügt CSV-Export hinzu", None, repo)
    assert result == {"text": "Fügt CSV-Export hinzu"}


def test_find_pr_description_from_file(repo):
    write(repo, "pr.txt", "Aus Datei gelesen\n")
    result = cc.find_pr_description(None, "pr.txt", repo)
    assert result["text"] == "Aus Datei gelesen"


def test_find_pr_description_rejects_both(repo):
    with pytest.raises(cc.CollectError, match="schließen sich aus"):
        cc.find_pr_description("a", "b.txt", repo)


def test_find_pr_description_none_when_neither(repo):
    assert cc.find_pr_description(None, None, repo) is None


def test_find_pr_description_file_missing_raises(repo):
    with pytest.raises(cc.CollectError, match="nicht gefunden"):
        cc.find_pr_description(None, "missing.txt", repo)


# --- find_commit_message_soll -------------------------------------------------

def test_find_commit_message_soll_none_for_uncommitted_mode(repo):
    assert cc.find_commit_message_soll(repo, "uncommitted", "HEAD", None) is None


def test_find_commit_message_soll_none_for_single_commit_range(repo):
    assert cc.find_commit_message_soll(repo, "range", "HEAD~1", "HEAD") is None


def test_find_commit_message_soll_present_for_two_commits(repo):
    write(repo, "src/extra.py", "y = 2\n")
    commit_all(repo, "feat: extra Modul")
    result = cc.find_commit_message_soll(repo, "range", "HEAD~2", "HEAD")
    assert result is not None
    assert result["count"] == 2
    assert "extra Modul" in result["text"]


# --- resolve_soll --------------------------------------------------------------

def test_resolve_soll_prefers_spec_over_pr_and_commits(repo):
    write(repo, "docs/specs/wip/feature-x.md", GWT_SAMPLE)
    soll = cc.resolve_soll(repo, "range", "HEAD~1", "HEAD", "PR-Text", None)
    assert soll["source"] == "feature_spec"
    assert soll["weak"] is False


def test_resolve_soll_prefers_pr_over_commits(repo):
    write(repo, "src/extra.py", "y = 2\n")
    commit_all(repo, "feat: extra Modul")
    soll = cc.resolve_soll(repo, "range", "HEAD~2", "HEAD", "PR-Text", None)
    assert soll["source"] == "pr_description"
    assert soll["weak"] is True


def test_resolve_soll_falls_back_to_commit_messages(repo):
    write(repo, "src/extra.py", "y = 2\n")
    commit_all(repo, "feat: extra Modul")
    soll = cc.resolve_soll(repo, "range", "HEAD~2", "HEAD", None, None)
    assert soll["source"] == "commit_messages"
    assert soll["weak"] is True


def test_resolve_soll_none_when_nothing_found(repo):
    soll = cc.resolve_soll(repo, "range", "HEAD~1", "HEAD", None, None)
    assert soll["source"] == "none"
    assert soll["weak"] is None
