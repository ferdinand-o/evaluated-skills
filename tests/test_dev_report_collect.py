import json
import subprocess

import pytest

from conftest import load_script

collect = load_script("skills/dev-report/scripts/collect.py")


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """Kleines Repo mit drei Commits über zwei Module."""
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    for i, (path, text, message) in enumerate([
        ("src/parser.py", "def parse():\n    return 1\n", "feat: parser"),
        ("src/cli.py", "import sys\n", "feat: cli"),
        ("docs/note.md", "hallo\n", "docs: notiz"),
    ]):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        git(tmp_path, "add", "-A")
        git(tmp_path, "commit", "--quiet", "-m", message)
    return tmp_path


def test_collect_commits_returns_newest_first(repo):
    commits = collect.collect_commits(repo, "HEAD")
    assert [c["subject"] for c in commits] == ["docs: notiz", "feat: cli", "feat: parser"]


def test_collect_commits_carries_files_and_churn(repo):
    commits = collect.collect_commits(repo, "HEAD")
    first = commits[-1]
    assert first["files"] == ["src/parser.py"]
    assert first["insertions"] == 2
    assert first["deletions"] == 0
    assert len(first["hash"]) >= 7


def test_aggregate_modules_groups_by_top_level_prefix(repo):
    modules = collect.aggregate_modules(collect.collect_commits(repo, "HEAD"))
    by_prefix = {m["prefix"]: m for m in modules}
    assert by_prefix["src/"]["commits"] == 2
    assert by_prefix["docs/"]["commits"] == 1
    assert by_prefix["src/"]["insertions"] == 3


def test_resolve_range_since(repo):
    git_range, end_label = collect.resolve_range("weekly", "2026-08-01", None, None)
    assert "--since=2026-08-01" in git_range
    assert end_label == "2026-08-01"


def test_resolve_range_explicit_range(repo):
    git_range, end_label = collect.resolve_range("release", None, "v1.0..HEAD", None)
    assert git_range == "v1.0..HEAD"
    assert end_label == "HEAD"


def test_resolve_range_rejects_two_selectors(repo):
    with pytest.raises(collect.CollectError, match="genau eine"):
        collect.resolve_range("weekly", "2026-08-01", "v1.0..HEAD", None)


def test_report_path_is_deterministic():
    assert collect.report_path("weekly", "2026-08-07") == "docs/reports/weekly-2026-08-07.md"


def test_build_facts_has_meta_and_report_path(repo):
    facts = collect.build_facts(repo, mode="weekly", since=None, rev_range="HEAD", branch=None)
    assert facts["_meta"]["skill"] == "dev-report"
    assert facts["_meta"]["schema"] == 1
    assert facts["_meta"]["generated"].startswith("python skills/dev-report/scripts/collect.py")
    assert facts["report_path"].startswith("docs/reports/")
    assert facts["mode"] == "weekly"
    assert len(facts["commits"]) == 3


def test_main_writes_facts_to_cache(repo, monkeypatch):
    monkeypatch.chdir(repo)
    rc = collect.main(["--mode", "weekly", "--range", "HEAD"])
    assert rc == 0
    written = json.loads((repo / ".skills" / "cache" / "facts.json").read_text(encoding="utf-8"))
    assert written["mode"] == "weekly"
    assert len(written["commits"]) == 3


def test_main_rejects_unknown_mode(repo, monkeypatch):
    monkeypatch.chdir(repo)
    with pytest.raises(SystemExit):
        collect.main(["--mode", "quartalsbericht", "--range", "HEAD"])


@pytest.fixture
def repo_with_empty_commit(tmp_path):
    """Repo mit regulärem Commit, leerem Commit und dann wieder regulärem Commit.

    Regression-Test für: Commits ohne Numstat-Output (z.B. --allow-empty)
    sollten nicht übersehen werden, und ihre Stats sollten nicht dem
    vorherigen Commit zugeordnet werden.
    """
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")

    # Commit 1: mit Änderungen
    (tmp_path / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "feat: main work")

    # Commit 2: leer (kein Numstat)
    git(tmp_path, "commit", "--quiet", "--allow-empty", "-m", "chore: empty commit")

    # Commit 3: mit anderen Änderungen
    (tmp_path / "util.py").write_text("def helper():\n    return True\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "feat: utils")

    return tmp_path


def test_collect_commits_handles_empty_commits(repo_with_empty_commit):
    """Alle drei Commits sollten da sein, Stats richtig zugeordnet."""
    commits = collect.collect_commits(repo_with_empty_commit, "HEAD")

    # Neuste zuerst
    subjects = [c["subject"] for c in commits]
    assert subjects == ["feat: utils", "chore: empty commit", "feat: main work"]

    # Commit 1 (feat: main work) sollte main.py mit 2 insertions haben
    feat_main = commits[2]
    assert feat_main["subject"] == "feat: main work"
    assert "main.py" in feat_main["files"]
    assert feat_main["insertions"] == 2

    # Commit 2 (chore: empty commit) sollte keine files haben
    empty_commit = commits[1]
    assert empty_commit["subject"] == "chore: empty commit"
    assert empty_commit["files"] == []
    assert empty_commit["insertions"] == 0
    assert empty_commit["deletions"] == 0

    # Commit 3 (feat: utils) sollte util.py mit 2 insertions haben
    feat_utils = commits[0]
    assert feat_utils["subject"] == "feat: utils"
    assert "util.py" in feat_utils["files"]
    assert feat_utils["insertions"] == 2


def commit_stub(subject, files=("src/a.py",)):
    return {"hash": "abc1234", "subject": subject, "date": "2026-08-07",
            "files": list(files), "insertions": 1, "deletions": 0}


def test_detects_revert_commits():
    patterns = collect.detect_patterns([
        commit_stub('Revert "feat: parser"'),
        commit_stub("feat: parser"),
    ])
    assert len(patterns["reverts"]) == 1
    assert patterns["reverts"][0]["subject"].startswith("Revert")


def test_detects_fix_chain_on_same_file():
    patterns = collect.detect_patterns([
        commit_stub("fix: immer noch kaputt", files=["src/a.py"]),
        commit_stub("fix: parser", files=["src/a.py"]),
        commit_stub("feat: parser", files=["src/a.py"]),
    ])
    assert patterns["fix_chains"]
    assert patterns["fix_chains"][0]["path"] == "src/a.py"
    assert patterns["fix_chains"][0]["count"] == 2


def test_single_fix_is_no_chain():
    patterns = collect.detect_patterns([
        commit_stub("fix: parser", files=["src/a.py"]),
        commit_stub("feat: parser", files=["src/a.py"]),
    ])
    assert patterns["fix_chains"] == []


def test_quiet_period_is_flagged():
    assert collect.detect_patterns([commit_stub("feat: x")] * 3)["quiet"] is True


def test_busy_period_is_not_quiet():
    assert collect.detect_patterns([commit_stub("feat: x")] * 12)["quiet"] is False


def test_build_facts_includes_patterns(repo):
    facts = collect.build_facts(repo, mode="weekly", since=None, rev_range="HEAD", branch=None)
    assert facts["patterns"]["quiet"] is True
    assert facts["patterns"]["reverts"] == []


def test_fix_commits_counts_and_chains_disambiguate():
    """Zwei Fix-Commits über dieselben mehreren Dateien.

    Der mehrdeutige Fall: zehn Ketten bei zwei Fix-Commits ist ein breiter Fix,
    zehn Ketten bei zwölf Fix-Commits ist echte Zähigkeit.
    """
    patterns = collect.detect_patterns([
        commit_stub("fix: second pass", files=["a.py", "b.py", "c.py"]),
        commit_stub("fix: first pass", files=["a.py", "b.py", "c.py"]),
    ])
    # Jede Datei wurde von zwei Fix-Commits berührt
    assert len(patterns["fix_chains"]) == 3
    for chain in patterns["fix_chains"]:
        assert chain["count"] == 2
    # Beide Commits sind Fix-Commits
    assert patterns["fix_commits"] == 2


def test_fix_commits_counts_only_fix_commits():
    """fix_commits zählt nur Commits mit Fix-Präfix, nicht alle Commits."""
    patterns = collect.detect_patterns([
        commit_stub("fix: parser", files=["src/a.py"]),
        commit_stub("feat: unrelated", files=["src/a.py"]),
        commit_stub("hotfix: urgent", files=["src/a.py"]),
        commit_stub("docs: note", files=["src/a.py"]),
    ])
    # Nur die zwei Fix-Commits sollten gezählt werden
    assert patterns["fix_commits"] == 2


HEADER = "<!-- skill: debug-ledger | schema: 1 | generated: python scripts/new_ledger.py -->"


def write_source(repo, relpath, text):
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_read_header_parses_the_three_fields(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(HEADER + "\n# Titel\n", encoding="utf-8")
    header = collect.read_header(path)
    assert header["skill"] == "debug-ledger"
    assert header["schema"] == 1


def test_read_header_returns_none_without_header(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Nur ein Titel\n", encoding="utf-8")
    assert collect.read_header(path) is None


def test_harvest_reads_matching_schema(repo):
    write_source(repo, "docs/debugging/INDEX.md", HEADER + "\nLogin haengt -> Cache-Key kollidiert\n")
    entries = {e["path"]: e for e in collect.harvest(repo)}
    entry = entries["docs/debugging/INDEX.md"]
    assert entry["status"] == "read"
    assert "Cache-Key" in entry["excerpt"]


def test_harvest_marks_missing_source_without_failing(repo):
    entries = {e["path"]: e for e in collect.harvest(repo)}
    assert entries["docs/decisions.md"]["status"] == "missing"


def test_harvest_skips_unknown_schema_visibly(repo):
    write_source(repo, "docs/decisions.md",
                 "<!-- skill: feature-spec | schema: 99 | generated: x -->\nEntscheidung\n")
    entry = {e["path"]: e for e in collect.harvest(repo)}["docs/decisions.md"]
    assert entry["status"] == "schema_mismatch"
    assert entry["schema"] == 99
    assert "Entscheidung" not in entry["excerpt"]


def test_harvest_skips_source_without_header_visibly(repo):
    write_source(repo, "CHANGELOG.md", "## 1.0\n- irgendwas\n")
    entry = {e["path"]: e for e in collect.harvest(repo)}["CHANGELOG.md"]
    assert entry["status"] == "no_header"
    assert entry["excerpt"] == ""


def test_build_facts_includes_harvest(repo):
    facts = collect.build_facts(repo, mode="weekly", since=None, rev_range="HEAD", branch=None)
    assert any(e["path"] == "docs/decisions.md" for e in facts["harvest"])


def test_harvest_directory_with_multiple_files_reads_first_alphabetically(repo):
    """Verzeichnis mit mehreren .md-Dateien: nimmt alphabetisch erste."""
    # Zwei Dateien anlegen, nicht in alphabetischer Reihenfolge
    write_source(repo, "docs/specs/wip/z_second.md", HEADER + "\nZweite Datei\n")
    write_source(repo, "docs/specs/wip/a_first.md", HEADER + "\nErste Datei\n")
    entries = {e["path"]: e for e in collect.harvest(repo)}
    entry = entries["docs/specs/wip"]
    assert entry["status"] == "read"
    # Der excerpt muss aus der alphabetisch ersten Datei (a_first.md) stammen
    assert "Erste Datei" in entry["excerpt"]
    assert "Zweite Datei" not in entry["excerpt"]


def test_harvest_empty_directory_returns_missing(repo):
    """Leeres Verzeichnis: status ist missing, kein Crash."""
    # Verzeichnis anlegen, aber ohne .md-Dateien
    (repo / "docs/specs/wip").mkdir(parents=True, exist_ok=True)
    entries = {e["path"]: e for e in collect.harvest(repo)}
    entry = entries["docs/specs/wip"]
    assert entry["status"] == "missing"
    assert entry["excerpt"] == ""
