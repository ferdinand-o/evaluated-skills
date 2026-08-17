import subprocess

import pytest
from evalkit.assertions import ARTIFACT_HEADER_RE, MechanicalCheckError, check, current_git_head
from evalkit.schema import Assertion

BASELINE = {"stable.md": "abc123", "__git_head__": "deadbeef"}


def test_file_exists_true(tmp_path):
    (tmp_path / "handoff.md").write_text("x", encoding="utf-8")
    result = check(Assertion(type="file_exists", path="handoff.md"), tmp_path, BASELINE)
    assert result.ok


def test_file_exists_false(tmp_path):
    result = check(Assertion(type="file_exists", path="handoff.md"), tmp_path, BASELINE)
    assert not result.ok
    assert "handoff.md" in result.detail


def test_file_absent(tmp_path):
    assert check(Assertion(type="file_absent", path="handoff.md"), tmp_path, BASELINE).ok
    (tmp_path / "handoff.md").write_text("x", encoding="utf-8")
    assert not check(Assertion(type="file_absent", path="handoff.md"), tmp_path, BASELINE).ok


def test_file_matches_is_multiline(tmp_path):
    (tmp_path / "h.md").write_text("# Titel\n## Status\nfoo\n", encoding="utf-8")
    assert check(Assertion(type="file_matches", path="h.md", pattern=r"^## Status$"), tmp_path, BASELINE).ok
    assert not check(Assertion(type="file_matches", path="h.md", pattern=r"^## Fehlt$"), tmp_path, BASELINE).ok


def test_file_matches_on_missing_file_is_failure(tmp_path):
    result = check(Assertion(type="file_matches", path="nope.md", pattern="x"), tmp_path, BASELINE)
    assert not result.ok
    assert "existiert nicht" in result.detail


def test_file_max_lines(tmp_path):
    (tmp_path / "h.md").write_text("\n".join(str(i) for i in range(10)), encoding="utf-8")
    assert check(Assertion(type="file_max_lines", path="h.md", max_lines=10), tmp_path, BASELINE).ok
    assert not check(Assertion(type="file_max_lines", path="h.md", max_lines=9), tmp_path, BASELINE).ok


def test_file_unchanged(tmp_path):
    target = tmp_path / "stable.md"
    target.write_text("original", encoding="utf-8")
    baseline = {"stable.md": __import__("hashlib").sha256(b"original").hexdigest()}
    assert check(Assertion(type="file_unchanged", path="stable.md"), tmp_path, baseline).ok
    target.write_text("angefasst", encoding="utf-8")
    assert not check(Assertion(type="file_unchanged", path="stable.md"), tmp_path, baseline).ok


def test_file_unchanged_without_baseline_entry_fails_loudly(tmp_path):
    """Datei da, aber nicht in der Baseline: der Agent hat sie im Lauf angelegt."""
    (tmp_path / "unknown.md").write_text("neu", encoding="utf-8")
    result = check(Assertion(type="file_unchanged", path="unknown.md"), tmp_path, {})
    assert not result.ok
    assert "Baseline" in result.detail


def test_output_matches_reads_agent_stdout(tmp_path):
    assertion = Assertion(type="output_matches", pattern=r"\?")
    assert check(assertion, tmp_path, BASELINE, output="Soll ich das anlegen?").ok
    assert not check(assertion, tmp_path, BASELINE, output="Erledigt.").ok


def test_artifact_header_markdown(tmp_path):
    (tmp_path / "a.md").write_text(
        "<!-- skill: debug-ledger | schema: 1 | generated: python scripts/new_ledger.py -->\n# Ledger\n",
        encoding="utf-8",
    )
    assert check(Assertion(type="artifact_header", path="a.md"), tmp_path, BASELINE).ok


def test_artifact_header_yaml(tmp_path):
    (tmp_path / "a.yaml").write_text(
        "# skill: rest-api-architect | schema: 2 | generated: python scripts/gen_ruleset.py\nrules: []\n",
        encoding="utf-8",
    )
    assert check(Assertion(type="artifact_header", path="a.yaml"), tmp_path, BASELINE).ok


def test_artifact_header_missing(tmp_path):
    (tmp_path / "a.md").write_text("# Ledger ohne Kopfzeile\n", encoding="utf-8")
    result = check(Assertion(type="artifact_header", path="a.md"), tmp_path, BASELINE)
    assert not result.ok
    assert "Kopfzeile" in result.detail


def test_artifact_header_regex_captures_fields():
    match = ARTIFACT_HEADER_RE.match("<!-- skill: dev-report | schema: 3 | generated: python x.py --mode weekly -->")
    assert match.group("skill") == "dev-report"
    assert match.group("schema") == "3"
    assert match.group("cmd") == "python x.py --mode weekly"


def test_git_head_unchanged(tmp_path):
    baseline = {"__git_head__": "abc"}
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD_SHA").write_text("abc", encoding="utf-8")
    assert check(Assertion(type="git_head_unchanged"), tmp_path, baseline).ok
    (tmp_path / ".git" / "HEAD_SHA").write_text("xyz", encoding="utf-8")
    assert not check(Assertion(type="git_head_unchanged"), tmp_path, baseline).ok


def _run_git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def test_current_git_head_uses_real_git_without_probe_file(tmp_path):
    """Der Testkurzschritt .git/HEAD_SHA existiert nur für Unit-Tests ohne echtes
    Repo. Ohne ihn muss der produktive `git rev-parse`-Zweig laufen — genau der
    Pfad, den jeder echte Eval-Lauf nimmt."""
    _run_git("init", "--quiet", "--initial-branch=main", cwd=tmp_path)
    _run_git("config", "user.email", "e@example.invalid", cwd=tmp_path)
    _run_git("config", "user.name", "T", cwd=tmp_path)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    _run_git("add", "-A", cwd=tmp_path)
    _run_git("commit", "--quiet", "-m", "x", cwd=tmp_path)
    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert current_git_head(tmp_path) == expected


def test_current_git_head_returns_none_without_repo(tmp_path):
    assert current_git_head(tmp_path) is None


def test_git_head_unchanged_fails_loudly_when_baseline_has_no_head(tmp_path):
    """`before is None` heißt: die Baseline wurde für eine Fixture ohne Repo gezogen
    (oder git_head_unchanged wird gegen die falsche Baseline geprüft). Das ist ein
    Fehlschlag mit eigener Diagnose, kein stiller Sonderfall."""
    result = check(Assertion(type="git_head_unchanged"), tmp_path, {})
    assert not result.ok
    assert "kein Git-HEAD" in result.detail


def test_judge_assertion_is_rejected_here(tmp_path):
    with pytest.raises(MechanicalCheckError):
        check(Assertion(type="judge", claim="gut"), tmp_path, BASELINE)


def test_file_unchanged_on_excluded_claude_path_raises_instead_of_false_red(tmp_path):
    """snapshot() schließt .claude/ bewusst aus der Baseline aus. Ohne diese Wache
    würde file_unchanged für eine existierende, unveränderte Datei darunter fälschlich
    melden "nicht in der Baseline — vor dem Lauf existierte die Datei nicht" — falsches
    Rot mit falscher Diagnose statt eines klaren Hinweises auf eine ungeeignete
    Assertion."""
    target = tmp_path / ".claude" / "skills" / "handoff" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("---\nname: handoff\n---\n", encoding="utf-8")
    with pytest.raises(MechanicalCheckError, match=r"\.claude/"):
        check(Assertion(type="file_unchanged", path=".claude/skills/handoff/SKILL.md"), tmp_path, BASELINE)


def test_file_exists_on_excluded_git_path_raises(tmp_path):
    with pytest.raises(MechanicalCheckError, match=r"\.git/"):
        check(Assertion(type="file_exists", path=".git/config"), tmp_path, BASELINE)


def test_glob_path_finds_a_generated_filename(tmp_path):
    """Ein Glob im Pfad macht generierte Dateinamen mechanisch prüfbar.

    Ohne das erzwingt jeder Dateiname mit Datum oder Freitext-Slug eine
    behavior-Eval mit Judge, obwohl die Eigenschaft mechanisch prüfbar wäre --
    debug-ledger musste drei von vier Evals allein deshalb herunterstufen.
    """
    (tmp_path / "docs" / "debugging").mkdir(parents=True)
    (tmp_path / "docs" / "debugging" / "2026-08-16-lookup-schlaegt-fehl.md").write_text(
        "<!-- skill: debug-ledger | schema: 1 | generated: x -->\n# Ledger\n", encoding="utf-8"
    )

    result = check(Assertion(type="file_exists", path="docs/debugging/*.md"), tmp_path, {})
    assert result.ok

    header = check(Assertion(type="artifact_header", path="docs/debugging/*.md"), tmp_path, {})
    assert header.ok


def test_glob_without_match_reports_no_hit(tmp_path):
    (tmp_path / "docs").mkdir()
    result = check(Assertion(type="file_exists", path="docs/*.md"), tmp_path, {})
    assert not result.ok
    assert "kein Treffer" in result.detail


def test_glob_absent_is_satisfied_only_without_any_match(tmp_path):
    (tmp_path / "docs").mkdir()
    absent = check(Assertion(type="file_absent", path="docs/*.md"), tmp_path, {})
    assert absent.ok

    (tmp_path / "docs" / "irgendwas.md").write_text("x", encoding="utf-8")
    still_absent = check(Assertion(type="file_absent", path="docs/*.md"), tmp_path, {})
    assert not still_absent.ok


def test_several_glob_matches_are_deterministic_and_counted(tmp_path):
    """Sonst haenge das Ergebnis unsichtbar an der Verzeichnisreihenfolge."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "b.md").write_text("zweiter", encoding="utf-8")
    (tmp_path / "docs" / "a.md").write_text("erster", encoding="utf-8")

    result = check(Assertion(type="file_matches", path="docs/*.md", pattern="erster"), tmp_path, {})

    assert result.ok
    assert "a.md" in result.detail
    assert "+1 weitere" in result.detail
