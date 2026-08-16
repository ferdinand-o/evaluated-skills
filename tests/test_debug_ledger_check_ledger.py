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
