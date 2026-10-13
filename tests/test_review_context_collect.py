import argparse
import json
import subprocess
from pathlib import Path

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
    git(repo, "commit", "--quiet", "--allow-empty", "-m", message)


def commit_with_body(repo, subject, body):
    git(repo, "add", "-A")
    git(repo, "commit", "--quiet", "--allow-empty", "-m", f"{subject}\n\n{body}")


@pytest.fixture
def repo(tmp_path):
    """Zwei Commits: eine Datei angelegt, dann geändert."""
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    write(tmp_path, "src/calc.py", "def add(a, b):\n    return a + b\n")
    commit_all(tmp_path, "feat: add")
    write(tmp_path, "src/calc.py", "def add(a, b):\n    return a + b + 0\n")
    commit_all(tmp_path, "wip")  # bewusst generisch: kein inhaltliches Soll (Fix-Runde)
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
    write(
        repo, "docs/specs/wip/feature-y.md",
        "# Feature Y\n\n"
        "Diese Spec beschreibt das Feature in Prosa, ohne Given/When/Then-Struktur, "
        "aber mit ausreichend Substanz, um als Soll zu gelten.\n",
    )
    specs = cc.find_feature_spec(repo)
    assert specs[0]["criteria"] == []
    assert "Prosa" in specs[0]["excerpt"]


def test_find_feature_spec_empty_file_does_not_count(repo):
    write(repo, "docs/specs/wip/feature-empty.md", "")
    assert cc.find_feature_spec(repo) is None


def test_find_feature_spec_whitespace_only_file_does_not_count(repo):
    write(repo, "docs/specs/wip/feature-blank.md", "   \n\n\t\n   \n")
    assert cc.find_feature_spec(repo) is None


def test_find_feature_spec_heading_only_file_does_not_count(repo):
    write(repo, "docs/specs/wip/feature-heading.md", "# Feature Z\n\n## Noch ein Titel\n")
    assert cc.find_feature_spec(repo) is None


def test_find_feature_spec_mixes_meaningful_and_empty_files(repo):
    write(repo, "docs/specs/wip/feature-empty.md", "# Nur Titel\n")
    write(repo, "docs/specs/wip/feature-x.md", GWT_SAMPLE)
    specs = cc.find_feature_spec(repo)
    assert [s["path"] for s in specs] == ["docs/specs/wip/feature-x.md"]


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
#
# Fix-Runde: Nicht mehr die Anzahl der Commits im Range entscheidet, sondern
# der Inhalt jeder einzelnen Message (Body vorhanden, oder Betreffzeile
# hinreichend lang und kein reiner Platzhalter wie "wip"/"fix").

def test_find_commit_message_soll_none_for_uncommitted_mode(repo):
    assert cc.find_commit_message_soll(repo, "uncommitted", "HEAD", None) is None


def test_find_commit_message_soll_none_for_zero_commits_in_range(repo):
    assert cc.find_commit_message_soll(repo, "range", "HEAD", "HEAD") is None


def test_find_commit_message_soll_none_for_generic_single_commit(repo):
    """Der letzte Commit der `repo`-Fixture heißt bewusst 'wip'."""
    assert cc.find_commit_message_soll(repo, "range", "HEAD~1", "HEAD") is None


def test_find_commit_message_soll_true_for_descriptive_single_commit(repo):
    commit_all(repo, "feat: CSV-Export für den Monatsabschluss ergänzt")
    result = cc.find_commit_message_soll(repo, "range", "HEAD~1", "HEAD")
    assert result is not None
    assert result["count"] == 1


def test_find_commit_message_soll_true_when_body_present(repo):
    commit_with_body(repo, "fix", "Behebt den KeyError bei leerem Dict im Cache-Layer.")
    result = cc.find_commit_message_soll(repo, "range", "HEAD~1", "HEAD")
    assert result is not None
    assert "KeyError" in result["text"]


def test_find_commit_message_soll_generic_subject_without_body_is_none(repo):
    commit_all(repo, "fix")
    assert cc.find_commit_message_soll(repo, "range", "HEAD~1", "HEAD") is None


def test_find_commit_message_soll_short_subject_without_body_is_none(repo):
    commit_all(repo, "fix: typo")
    assert cc.find_commit_message_soll(repo, "range", "HEAD~1", "HEAD") is None


def test_find_commit_message_soll_present_for_two_commits_if_one_is_meaningful(repo):
    write(repo, "src/extra.py", "y = 2\n")
    commit_all(repo, "feat: CSV-Export für den Monatsabschluss ergänzt")
    result = cc.find_commit_message_soll(repo, "range", "HEAD~2", "HEAD")
    assert result is not None
    assert result["count"] == 2
    assert "CSV-Export" in result["text"]
    assert "wip" in result["text"]  # die schwache Message bleibt Teil des Texts


def test_find_commit_message_soll_none_when_no_commit_is_meaningful(repo):
    """Zwei generische Commits hintereinander bleiben trotzdem kein Soll."""
    commit_all(repo, "fix")
    result = cc.find_commit_message_soll(repo, "range", "HEAD~2", "HEAD")
    assert result is None


# --- resolve_soll --------------------------------------------------------------

def test_resolve_soll_prefers_spec_over_pr_and_commits(repo):
    write(repo, "docs/specs/wip/feature-x.md", GWT_SAMPLE)
    soll = cc.resolve_soll(repo, "range", "HEAD~1", "HEAD", "PR-Text", None)
    assert soll["source"] == "feature_spec"
    assert soll["weak"] is False


def test_resolve_soll_prefers_pr_over_commits(repo):
    write(repo, "src/extra.py", "y = 2\n")
    commit_all(repo, "feat: CSV-Export für den Monatsabschluss ergänzt")
    soll = cc.resolve_soll(repo, "range", "HEAD~2", "HEAD", "PR-Text", None)
    assert soll["source"] == "pr_description"
    assert soll["weak"] is True


def test_resolve_soll_falls_back_to_commit_messages(repo):
    write(repo, "src/extra.py", "y = 2\n")
    commit_all(repo, "feat: CSV-Export für den Monatsabschluss ergänzt")
    soll = cc.resolve_soll(repo, "range", "HEAD~2", "HEAD", None, None)
    assert soll["source"] == "commit_messages"
    assert soll["weak"] is True


def test_resolve_soll_none_when_nothing_found(repo):
    soll = cc.resolve_soll(repo, "range", "HEAD~1", "HEAD", None, None)
    assert soll["source"] == "none"
    assert soll["weak"] is None


# --- read_decisions ------------------------------------------------------------

def test_read_decisions_missing_file(repo):
    assert cc.read_decisions(repo) == {"status": "missing", "entries": []}


def test_read_decisions_without_header_is_skipped_visibly(repo):
    write(repo, "docs/decisions.md", "- 2026-08-01: Fehlerformat ist JSON (Spec-Anlass: X)\n")
    result = cc.read_decisions(repo)
    assert result["status"] == "no_header"
    assert result["entries"] == []


def test_read_decisions_schema_mismatch_is_skipped_visibly(repo):
    write(repo, "docs/decisions.md",
          "<!-- skill: feature-spec | schema: 99 | generated: x -->\n- Entscheidung\n")
    result = cc.read_decisions(repo)
    assert result["status"] == "schema_mismatch"
    assert result["schema"] == 99


def test_read_decisions_reads_matching_schema(repo):
    write(repo, "docs/decisions.md",
          "<!-- skill: feature-spec | schema: 1 | generated: x -->\n"
          "- 2026-08-01: Fehlerformat ist JSON (Spec-Anlass: 03)\n")
    result = cc.read_decisions(repo)
    assert result["status"] == "read"
    assert result["entries"] == ["- 2026-08-01: Fehlerformat ist JSON (Spec-Anlass: 03)"]


# --- Symbol-Erkennung ------------------------------------------------------------

PY_SOURCE = (
    "def helper():\n"
    "    return 1\n"
    "\n"
    "\n"
    "def add(a, b):\n"
    "    total = a + b\n"
    "    return total + 0\n"
)


def test_detect_python_symbols_finds_touched_function():
    symbols = cc.detect_python_symbols(PY_SOURCE, [(6, 6)])
    assert len(symbols) == 1
    assert symbols[0]["name"] == "add"
    assert symbols[0]["signature"] == "def add(a, b):"


def test_detect_python_symbols_ignores_untouched_function():
    symbols = cc.detect_python_symbols(PY_SOURCE, [(1, 2)])
    assert symbols[0]["name"] == "helper"


def test_detect_python_symbols_multiline_signature():
    source = "def add(\n    a,\n    b,\n):\n    return a + b\n"
    symbols = cc.detect_python_symbols(source, [(5, 5)])
    assert symbols[0]["signature"] == "def add(\n    a,\n    b,\n):"


def test_detect_python_symbols_no_ranges_is_empty():
    assert cc.detect_python_symbols(PY_SOURCE, []) == []


def test_detect_python_symbols_syntax_error_is_empty():
    assert cc.detect_python_symbols("def broken(:\n", [(1, 1)]) == []


TS_SOURCE = (
    "export function add(a: number, b: number): number {\n"
    "  return a + b;\n"
    "}\n"
)


def test_detect_ts_symbols_finds_declaration_line():
    symbols = cc.detect_ts_symbols(TS_SOURCE, [(1, 1)])
    assert symbols[0]["name"] == "add"
    assert symbols[0]["kind"] == "function"


def test_detect_ts_symbols_ignores_body_only_change():
    """Benannte Grenze: TS-Erkennung sieht nur die Deklarationszeile, nicht den Body."""
    symbols = cc.detect_ts_symbols(TS_SOURCE, [(2, 2)])
    assert symbols == []


def test_detect_symbols_dispatches_by_suffix():
    assert cc.detect_symbols("src/add.py", PY_SOURCE, [(6, 6)])[0]["name"] == "add"
    assert cc.detect_symbols("src/add.ts", TS_SOURCE, [(1, 1)])[0]["name"] == "add"
    assert cc.detect_symbols("assets/logo.png", None, [(1, 1)]) == []
    assert cc.detect_symbols("README.md", "egal", [(1, 1)]) == []


# --- find_callers ------------------------------------------------------------

def test_find_callers_finds_caller_with_enclosing_signature(repo):
    write(repo, "src/calc.py", "def add(a, b):\n    return a + b\n")
    write(repo, "src/user.py", "from src.calc import add\n\n\ndef use_add(x, y):\n    return add(x, y) + 1\n")
    commit_all(repo, "feat: Nutzer von add")

    result = cc.find_callers(repo, "add", "src/calc.py", definition_lineno=1)
    assert result["total"] == 1
    entry = result["shown"][0]
    assert entry["file"] == "src/user.py"
    assert entry["caller_signature"] == "def use_add(x, y):"


def test_find_callers_excludes_the_definition_line(repo):
    write(repo, "src/calc.py", "def add(a, b):\n    return a + b\n")
    commit_all(repo, "feat: add")
    result = cc.find_callers(repo, "add", "src/calc.py", definition_lineno=1)
    assert result["total"] == 0


def test_find_callers_caps_with_named_limit(repo):
    for i in range(25):
        write(repo, f"src/caller_{i}.py", f"from src.calc import add\nresult_{i} = add({i}, {i})\n")
    write(repo, "src/calc.py", "def add(a, b):\n    return a + b\n")
    commit_all(repo, "feat: viele Aufrufer")

    result = cc.find_callers(repo, "add", "src/calc.py", definition_lineno=1, cap=20)
    assert result["total"] == 25
    assert len(result["shown"]) == 20
    assert "5 weitere" in result["note"]


# --- gather_conventions ---------------------------------------------------------

def test_gather_conventions_lists_siblings_excluding_changed_file(repo):
    write(repo, "src/other.py", "z = 1\n")
    commit_all(repo, "feat: other")
    conventions = cc.gather_conventions(repo, ["src/calc.py"])
    assert "other.py" in conventions["sibling_files"]["src"]["files"]
    assert "calc.py" not in conventions["sibling_files"]["src"]["files"]


def test_gather_conventions_caps_siblings_with_named_limit(repo, monkeypatch):
    monkeypatch.setattr(cc, "MAX_SIBLING_FILES", 2)
    for i in range(5):
        write(repo, f"src/sibling_{i}.py", "x = 1\n")
    commit_all(repo, "feat: viele Geschwisterdateien")
    conventions = cc.gather_conventions(repo, ["src/calc.py"])
    entry = conventions["sibling_files"]["src"]
    assert len(entry["files"]) == 2
    assert "weitere" in entry["note"]


def test_gather_conventions_detects_marker_files(repo):
    write(repo, "pyproject.toml", "[tool.ruff]\n")
    commit_all(repo, "chore: pyproject")
    conventions = cc.gather_conventions(repo, ["src/calc.py"])
    assert "pyproject.toml" in conventions["convention_markers"]


def test_gather_conventions_no_marker_files(repo):
    conventions = cc.gather_conventions(repo, ["src/calc.py"])
    assert conventions["convention_markers"] == []


# --- build_context / main -------------------------------------------------------

def make_args(range_=None, pr_description=None, pr_description_file=None, repo=None):
    return argparse.Namespace(
        range=range_, pr_description=pr_description, pr_description_file=pr_description_file,
        repo=repo or Path("."),
    )


def test_build_context_meta_and_schema(repo):
    context = cc.build_context(repo, make_args(range_="HEAD~1..HEAD", repo=repo))
    assert context["_meta"]["skill"] == "review-context"
    assert context["_meta"]["schema"] == 1
    assert context["_meta"]["generated"].startswith("python skills/review-context/scripts/collect_context.py")


def test_build_context_empty_diff_has_exactly_one_finding(repo):
    context = cc.build_context(repo, make_args(range_="HEAD..HEAD", repo=repo))
    assert context["diff"]["empty"] is True
    assert [f["id"] for f in context["findings"]] == ["empty_diff"]


def test_build_context_no_soll_finding_has_exact_wording(repo):
    context = cc.build_context(repo, make_args(range_="HEAD~1..HEAD", repo=repo))
    assert context["packages"]["spec_compliance"]["soll"]["source"] == "none"
    assert {"id": "no_soll", "message": cc.NO_SOLL_MESSAGE} in context["findings"]


def test_build_context_with_spec_has_no_no_soll_finding(repo):
    write(repo, "docs/specs/wip/feature-x.md", GWT_SAMPLE)
    context = cc.build_context(repo, make_args(range_="HEAD~1..HEAD", repo=repo))
    assert all(f["id"] != "no_soll" for f in context["findings"])
    assert context["packages"]["spec_compliance"]["soll"]["source"] == "feature_spec"


def test_build_context_correctness_package_carries_caller_signature(repo):
    write(repo, "src/calc.py", "def add(a, b):\n    return a + b\n")
    write(repo, "src/user.py", "def use_add(x, y):\n    return add(x, y)\n")
    commit_all(repo, "feat: user von add")
    write(repo, "src/calc.py", "def add(a, b):\n    return a + b + 0\n")
    commit_all(repo, "fix: add expliziter")

    context = cc.build_context(repo, make_args(range_="HEAD~1..HEAD", repo=repo))
    symbols = context["packages"]["correctness"]["symbols"]
    assert symbols[0]["name"] == "add"
    caller = symbols[0]["callers"]["shown"][0]
    assert caller["caller_signature"] == "def use_add(x, y):"


def test_main_writes_cache_file(repo, monkeypatch):
    monkeypatch.chdir(repo)
    rc = cc.main(["--range", "HEAD~1..HEAD"])
    assert rc == 0
    written = json.loads((repo / ".skills" / "cache" / "review-context.json").read_text(encoding="utf-8"))
    assert written["_meta"]["skill"] == "review-context"


def test_main_returns_1_on_collect_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = cc.main(["--range", "HEAD~1..HEAD"])
    assert rc == 1
