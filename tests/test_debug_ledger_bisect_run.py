import sys
import textwrap

import pytest

from conftest import load_script

bisect_run = load_script("skills/debug-ledger/scripts/bisect_run.py")


def git(repo, *args):
    import subprocess
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


CHECK_SCRIPT = textwrap.dedent(
    """
    import os
    import sys
    sys.exit(1 if os.path.exists("BROKEN") else 0)
    """
).strip()


@pytest.fixture
def bisect_repo(tmp_path):
    """Fünf Commits: die ersten zwei gut, ab Commit 3 bricht `BROKEN` das Repro.

    `check_repro.py` bleibt über alle Commits hinweg unverändert vorhanden, damit
    `git bisect` es bei jedem Checkout ausführen kann.
    """
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")

    (tmp_path / "check_repro.py").write_text(CHECK_SCRIPT + "\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "feat: check script + gut")
    good_hash = git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "feat: noch gut")

    (tmp_path / "BROKEN").write_text("kaputt\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "feat: der Bug")
    bad_commit_hash = git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "feat: danach 1")

    (tmp_path / "c.txt").write_text("c\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "feat: danach 2 (HEAD)")

    return tmp_path, good_hash, bad_commit_hash


COMMAND = f"{sys.executable} check_repro.py"


def test_is_git_repo_true_for_git_dir(bisect_repo):
    repo, _, _ = bisect_repo
    assert bisect_run.is_git_repo(repo) is True


def test_is_git_repo_false_for_plain_dir(tmp_path):
    assert bisect_run.is_git_repo(tmp_path) is False


def test_first_bad_commit_regex_matches_git_output():
    sample = "deadbeef1234 is the first bad commit\ncommit deadbeef1234\n"
    match = bisect_run.FIRST_BAD_RE.search(sample)
    assert match.group("hash") == "deadbeef1234"


def test_run_bisect_finds_the_culprit_commit(bisect_repo):
    repo, good_hash, bad_commit_hash = bisect_repo
    culprit, output = bisect_run.run_bisect(repo, good_hash, "HEAD", COMMAND)
    assert culprit is not None
    assert bad_commit_hash.startswith(culprit) or culprit.startswith(bad_commit_hash[: len(culprit)])
    assert "is the first bad commit" in output


def test_run_bisect_leaves_repo_on_original_branch(bisect_repo):
    repo, good_hash, _ = bisect_repo
    bisect_run.main(["--good", good_hash, "--bad", "HEAD", "--command", COMMAND, "--repo", str(repo)])
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    assert branch == "main"


def test_main_returns_two_for_non_git_repo(tmp_path, capsys):
    rc = bisect_run.main(["--good", "a", "--bad", "b", "--command", "true", "--repo", str(tmp_path)])
    assert rc == 2
    assert "kein Git-Repository" in capsys.readouterr().err


def test_main_finds_culprit_end_to_end(bisect_repo, capsys):
    repo, good_hash, _ = bisect_repo
    rc = bisect_run.main(["--good", good_hash, "--bad", "HEAD", "--command", COMMAND, "--repo", str(repo)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Erster schlechter Commit" in out


# --- Reviewer-Fund 1: kaputtes Repro-Kommando muss VOR der Bisektion auffallen ---

def test_verify_endpoints_rejects_command_that_fails_everywhere(bisect_repo):
    """Reviewer-Reproduktion: `false` schlaegt an JEDEM Commit fehl (auch am
    bekannt guten). Vorher liess `git bisect run false` trotzdem einen
    scheinbaren Culprit finden -- verify_endpoints muss das jetzt VOR dem
    eigentlichen Bisect abfangen."""
    repo, good_hash, _ = bisect_repo
    with pytest.raises(bisect_run.BisectError, match="bekannt guten Commit"):
        bisect_run.verify_endpoints(repo, good_hash, "HEAD", ["false"])


def test_run_bisect_raises_instead_of_reporting_a_fake_culprit(bisect_repo, capsys):
    """End-to-End: main() darf bei einem durchgehend fehlschlagenden Kommando
    NIE 'Erster schlechter Commit' drucken."""
    repo, good_hash, _ = bisect_repo
    rc = bisect_run.main(["--good", good_hash, "--bad", "HEAD", "--command", "false", "--repo", str(repo)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Erster schlechter Commit" not in captured.out
    assert "bekannt guten Commit" in captured.err


def test_verify_endpoints_rejects_command_that_never_fails(bisect_repo):
    """Umkehrfall: ein Kommando, das ueberall besteht (auch am bekannt
    schlechten Commit), unterscheidet nicht und ist genauso wertlos."""
    repo, good_hash, _ = bisect_repo
    with pytest.raises(bisect_run.BisectError, match="bekannt schlechten Commit"):
        bisect_run.verify_endpoints(repo, good_hash, "HEAD", ["true"])


def test_verify_endpoints_passes_for_a_real_discriminating_command(bisect_repo):
    """Gegenrichtung: ein echt unterscheidendes Kommando darf nicht scheitern."""
    repo, good_hash, _ = bisect_repo
    bisect_run.verify_endpoints(repo, good_hash, "HEAD", shlex_command())


def shlex_command():
    import shlex
    return shlex.split(COMMAND)


def test_verify_endpoints_restores_original_ref(bisect_repo):
    repo, good_hash, _ = bisect_repo
    branch_before = git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    bisect_run.verify_endpoints(repo, good_hash, "HEAD", shlex_command())
    branch_after = git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    assert branch_before == branch_after == "main"


# --- Reviewer-Fund 2: eine laufende Bisektion darf nie kommentarlos verworfen werden ---

def test_bisect_in_progress_false_when_no_session(bisect_repo):
    repo, _, _ = bisect_repo
    assert bisect_run.bisect_in_progress(repo) is False


def test_bisect_in_progress_true_mid_session(bisect_repo):
    repo, good_hash, _ = bisect_repo
    git(repo, "bisect", "start")
    git(repo, "bisect", "bad", "HEAD")
    git(repo, "bisect", "good", good_hash)
    try:
        assert bisect_run.bisect_in_progress(repo) is True
    finally:
        git(repo, "bisect", "reset")


def test_main_aborts_visibly_when_bisect_already_in_progress(bisect_repo, capsys):
    """Reviewer-Reproduktion: eine vom Nutzer selbst gestartete Bisektion darf
    nicht stillschweigend verworfen werden."""
    repo, good_hash, _ = bisect_repo
    git(repo, "bisect", "start")
    git(repo, "bisect", "bad", "HEAD")
    git(repo, "bisect", "good", good_hash)
    try:
        rc = bisect_run.main(["--good", good_hash, "--bad", "HEAD", "--command", COMMAND, "--repo", str(repo)])
        assert rc == 3
        assert "läuft bereits eine git-bisect-Sitzung" in capsys.readouterr().err
        # Der entscheidende Teil: die Sitzung des Nutzers existiert danach noch.
        assert bisect_run.bisect_in_progress(repo) is True
    finally:
        git(repo, "bisect", "reset")
