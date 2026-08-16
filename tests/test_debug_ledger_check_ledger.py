import pytest

from conftest import load_script

check_ledger = load_script("skills/debug-ledger/scripts/check_ledger.py")
new_ledger = load_script("skills/debug-ledger/scripts/new_ledger.py")


def make_mini_ledger(tmp_path, **overrides):
    kwargs = dict(symptom="Login hängt", repro="pytest -x", expected="ok", observed="haengt", slug="bug", date_str="2026-08-16")
    kwargs.update(overrides)
    return new_ledger.action_new(tmp_path, **kwargs)


# --- parse_sections / is_unfilled -----------------------------------------------

def test_parse_sections_splits_on_headings():
    text = "## Symptom\nA\n\n## Repro-Kommando\nB\n"
    sections = check_ledger.parse_sections(text)
    assert sections["Symptom"].strip() == "A"
    assert sections["Repro-Kommando"].strip() == "B"


def test_is_unfilled_true_for_placeholder():
    assert check_ledger.is_unfilled("_(noch offen)_") is True


def test_is_unfilled_true_for_empty():
    assert check_ledger.is_unfilled("   \n\n") is True


def test_is_unfilled_false_for_real_content():
    assert check_ledger.is_unfilled("Cache-Key kollidiert") is False


def test_is_unfilled_strips_code_fences():
    assert check_ledger.is_unfilled("```\n_(noch offen)_\n```") is True
    assert check_ledger.is_unfilled("```\npytest -x tests/x.py\n```") is False


# --- Hypothesen-Tabelle ------------------------------------------------------

FULL_TABLE_UNTESTED = (
    "| Hypothese | Test | Ergebnis | Verdict |\n"
    "| --- | --- | --- | --- |\n"
    "| _(noch offen)_ | _(noch offen)_ | _(noch offen)_ | _(noch offen)_ |\n"
)

FULL_TABLE_ONE_TESTED = (
    "| Hypothese | Test | Ergebnis | Verdict |\n"
    "| --- | --- | --- | --- |\n"
    "| Cache-Key kollidiert | Log-Ausgabe geprüft | Kollision bestätigt | Bestätigt |\n"
    "| _(noch offen)_ | _(noch offen)_ | _(noch offen)_ | _(noch offen)_ |\n"
)


def test_count_tested_hypotheses_zero_for_placeholder_row():
    assert check_ledger.count_tested_hypotheses(FULL_TABLE_UNTESTED) == 0


def test_count_tested_hypotheses_counts_only_fully_filled_rows():
    assert check_ledger.count_tested_hypotheses(FULL_TABLE_ONE_TESTED) == 1


def test_parse_hypothesis_rows_skips_header_and_separator():
    rows = check_ledger.parse_hypothesis_rows(FULL_TABLE_ONE_TESTED)
    assert len(rows) == 2  # eine getestete, eine Platzhalter-Zeile


# --- Reviewer-Fund: Fuellwoerter duerfen nicht als Testevidenz zaehlen ---------

REVIEWER_REPRODUCED_TABLE = (
    "| Hypothese | Test | Ergebnis | Verdict |\n"
    "| --- | --- | --- | --- |\n"
    "| Vermutlich ein Cache-Problem | - | - | Unklar |\n"
)


def test_dash_and_unklar_are_not_testevidenz():
    """Der vom Reviewer nachgestellte Fall: '-'/'-'/'Unklar' ist keine Testevidenz."""
    assert check_ledger.count_tested_hypotheses(REVIEWER_REPRODUCED_TABLE) == 0


def test_check_flags_fix_backed_only_by_filler_hypothesis(tmp_path):
    """End-to-End-Reproduktion des Reviewer-Funds: check() muss das jetzt melden,
    nicht mehr OK/Exit 0 liefern."""
    target = make_mini_ledger(tmp_path)
    rel = target.relative_to(tmp_path).as_posix()
    new_ledger.action_escalate(tmp_path, rel)
    text = target.read_text(encoding="utf-8")
    text = text.replace(
        "| _(noch offen)_ | _(noch offen)_ | _(noch offen)_ | _(noch offen)_ |",
        "| Vermutlich ein Cache-Problem | - | - | Unklar |",
    )
    text = text.replace("## Root Cause\n_(noch offen)_", "## Root Cause\nWahrscheinlich der Cache")
    text = text.replace("## Fix\n_(noch offen)_", "## Fix\nCache-Key ändern")
    target.write_text(text, encoding="utf-8")

    violations = check_ledger.check(target)
    assert any("Hypothesen-Tabelle" in v for v in violations)


@pytest.mark.parametrize("verdict", ["Unklar", "vielleicht", "passt schon", "offen"])
def test_freetext_verdicts_do_not_count_as_tested(verdict):
    table = (
        "| Hypothese | Test | Ergebnis | Verdict |\n"
        "| --- | --- | --- | --- |\n"
        f"| Cache-Key kollidiert zwischen Nutzern | Log-Ausgabe geprüft | Zwei Nutzer erzeugten denselben Key | {verdict} |\n"
    )
    assert check_ledger.count_tested_hypotheses(table) == 0


@pytest.mark.parametrize("verdict", ["Bestätigt", "bestätigt", "BESTAETIGT", "Verworfen", "verworfen"])
def test_closed_set_verdicts_count_as_tested_case_insensitive(verdict):
    table = (
        "| Hypothese | Test | Ergebnis | Verdict |\n"
        "| --- | --- | --- | --- |\n"
        f"| Cache-Key kollidiert zwischen Nutzern | Log-Ausgabe geprüft | Zwei Nutzer erzeugten denselben Key | {verdict} |\n"
    )
    assert check_ledger.count_tested_hypotheses(table) == 1


@pytest.mark.parametrize("test_cell,ergebnis_cell", [
    ("-", "Kollision bestaetigt"),
    ("Log-Ausgabe geprüft", "-"),
    ("n/a", "Kollision bestaetigt"),
    ("TBD", "TBD"),
    ("ok", "ok"),  # unter Mindestlaenge
    ("???", "???"),  # keine Buchstaben
])
def test_filler_test_or_ergebnis_cells_do_not_count_as_tested(test_cell, ergebnis_cell):
    table = (
        "| Hypothese | Test | Ergebnis | Verdict |\n"
        "| --- | --- | --- | --- |\n"
        f"| Cache-Key kollidiert zwischen Nutzern | {test_cell} | {ergebnis_cell} | Bestätigt |\n"
    )
    assert check_ledger.count_tested_hypotheses(table) == 0


def test_genuinely_tested_row_still_counts_after_the_fix():
    """Gegenrichtung: ein echt ausgefülltes Ledger muss weiterhin durchgehen."""
    assert check_ledger.count_tested_hypotheses(FULL_TABLE_ONE_TESTED) == 1


def test_full_mode_fix_with_genuinely_tested_hypothesis_is_still_clean(tmp_path):
    """Gegenrichtung end-to-end: ein echtes Ledger darf durch den Fix nicht
    faelschlich rot werden."""
    target = make_mini_ledger(tmp_path)
    rel = target.relative_to(tmp_path).as_posix()
    new_ledger.action_escalate(tmp_path, rel)
    text = target.read_text(encoding="utf-8")
    text = text.replace("## Fix\n_(noch offen)_", "## Fix\nCache-Key-Präfix pro Layer eindeutig machen")
    text = text.replace(
        "| _(noch offen)_ | _(noch offen)_ | _(noch offen)_ | _(noch offen)_ |",
        "| Cache-Key kollidiert | Log-Ausgabe pro Request geprüft | Zwei Nutzer erzeugten denselben Key | Bestätigt |",
    )
    target.write_text(text, encoding="utf-8")
    assert check_ledger.check(target) == []


# --- check(): Mini-Ledger ------------------------------------------------------

def test_clean_mini_ledger_has_no_violations(tmp_path):
    target = make_mini_ledger(tmp_path)
    assert check_ledger.check(target) == []


def test_missing_symptom_field_is_flagged(tmp_path):
    target = make_mini_ledger(tmp_path)
    text = target.read_text(encoding="utf-8")
    text = text.replace("Login hängt\n\n## Repro-Kommando", "\n\n## Repro-Kommando")
    target.write_text(text, encoding="utf-8")
    violations = check_ledger.check(target)
    assert any("Symptom" in v for v in violations)


def test_missing_header_is_flagged(tmp_path):
    target = make_mini_ledger(tmp_path)
    text = target.read_text(encoding="utf-8")
    text = "\n".join(text.splitlines()[2:])  # Kopfzeile + Leerzeile entfernen
    target.write_text(text, encoding="utf-8")
    violations = check_ledger.check(target)
    assert any("Kopfzeile" in v for v in violations)


def test_wrong_skill_in_header_is_flagged(tmp_path):
    target = make_mini_ledger(tmp_path)
    text = target.read_text(encoding="utf-8")
    text = text.replace("skill: debug-ledger", "skill: some-other-skill")
    target.write_text(text, encoding="utf-8")
    violations = check_ledger.check(target)
    assert any("Skill" in v for v in violations)


# --- check(): voller Modus, der eigentliche Contract ---------------------------

def test_full_mode_without_fix_has_no_hypothesis_violation(tmp_path):
    target = make_mini_ledger(tmp_path)
    rel = target.relative_to(tmp_path).as_posix()
    new_ledger.action_escalate(tmp_path, rel)
    violations = check_ledger.check(target)
    assert not any("Hypothesen-Tabelle" in v for v in violations)


def test_full_mode_fix_without_tested_hypothesis_is_flagged(tmp_path):
    target = make_mini_ledger(tmp_path)
    rel = target.relative_to(tmp_path).as_posix()
    new_ledger.action_escalate(tmp_path, rel)
    text = target.read_text(encoding="utf-8")
    text = text.replace("## Fix\n_(noch offen)_", "## Fix\nCache-Key-Präfix pro Layer eindeutig machen")
    target.write_text(text, encoding="utf-8")
    violations = check_ledger.check(target)
    assert any("Hypothesen-Tabelle" in v for v in violations)


def test_full_mode_fix_with_tested_hypothesis_is_clean(tmp_path):
    target = make_mini_ledger(tmp_path)
    rel = target.relative_to(tmp_path).as_posix()
    new_ledger.action_escalate(tmp_path, rel)
    text = target.read_text(encoding="utf-8")
    text = text.replace("## Fix\n_(noch offen)_", "## Fix\nCache-Key-Präfix pro Layer eindeutig machen")
    text = text.replace(
        "| _(noch offen)_ | _(noch offen)_ | _(noch offen)_ | _(noch offen)_ |",
        "| Cache-Key kollidiert | Log-Ausgabe geprüft | Kollision bestätigt | Bestätigt |",
    )
    target.write_text(text, encoding="utf-8")
    violations = check_ledger.check(target)
    assert violations == []


# --- main() / CLI-Verdrahtung ----------------------------------------------------

def test_main_missing_file_returns_two(tmp_path, capsys):
    rc = check_ledger.main([str(tmp_path / "nope.md")])
    assert rc == 2
    assert "nicht gefunden" in capsys.readouterr().err


def test_main_clean_ledger_returns_zero_and_prints_ok(tmp_path, capsys):
    target = make_mini_ledger(tmp_path)
    rc = check_ledger.main([str(target)])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


# --- --staged (Grundlage des optionalen G3-Hooks) -------------------------------

def git(repo, *args):
    import subprocess
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def staged_repo(tmp_path):
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "init")
    return tmp_path


def test_staged_ledgers_finds_only_staged_debugging_files(staged_repo):
    target = make_mini_ledger(staged_repo)
    git(staged_repo, "add", "-A")
    rels = check_ledger.staged_ledgers(staged_repo)
    assert rels == [target.relative_to(staged_repo).as_posix()]


def test_staged_ledgers_excludes_index(staged_repo):
    make_mini_ledger(staged_repo)  # bootstrapt auch INDEX.md
    git(staged_repo, "add", "-A")
    rels = check_ledger.staged_ledgers(staged_repo)
    assert all(not r.endswith("INDEX.md") for r in rels)


def test_main_staged_clean_when_nothing_staged(staged_repo, capsys):
    rc = check_ledger.main(["--staged", "--repo", str(staged_repo)])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_main_staged_reports_violation(staged_repo, capsys):
    target = make_mini_ledger(staged_repo)
    rel = target.relative_to(staged_repo).as_posix()
    new_ledger.action_escalate(staged_repo, rel)
    text = target.read_text(encoding="utf-8")
    text = text.replace("## Fix\n_(noch offen)_", "## Fix\nirgendein Fix")
    target.write_text(text, encoding="utf-8")
    git(staged_repo, "add", "-A")

    rc = check_ledger.main(["--staged", "--repo", str(staged_repo)])
    assert rc == 1
    assert "Hypothesen-Tabelle" in capsys.readouterr().out


def test_main_staged_rejects_non_git_repo(tmp_path, capsys):
    rc = check_ledger.main(["--staged", "--repo", str(tmp_path)])
    assert rc == 2
    assert "kein Git-Repository" in capsys.readouterr().err


def test_main_rejects_staged_and_ledger_together(tmp_path):
    with pytest.raises(SystemExit):
        check_ledger.main(["--staged", str(tmp_path / "x.md")])


def test_main_rejects_neither_staged_nor_ledger():
    with pytest.raises(SystemExit):
        check_ledger.main([])


def test_main_violation_returns_one_and_lists_it(tmp_path, capsys):
    target = make_mini_ledger(tmp_path)
    rel = target.relative_to(tmp_path).as_posix()
    new_ledger.action_escalate(tmp_path, rel)
    text = target.read_text(encoding="utf-8")
    text = text.replace("## Fix\n_(noch offen)_", "## Fix\nirgendein Fix")
    target.write_text(text, encoding="utf-8")

    rc = check_ledger.main([str(target)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Hypothesen-Tabelle" in out
