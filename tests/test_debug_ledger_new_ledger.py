import pytest

from conftest import load_script

new_ledger = load_script("skills/debug-ledger/scripts/new_ledger.py")


# --- slugify -----------------------------------------------------------------

def test_slugify_lowercases_and_hyphenates():
    assert new_ledger.slugify("Login hängt beim Start") == "login-haengt-beim-start"


def test_slugify_never_empty():
    assert new_ledger.slugify("!!!") == "fall"


def test_slugify_truncates_long_symptoms():
    long_text = "x" * 200
    assert len(new_ledger.slugify(long_text)) <= 40


# --- action_new: Bootstrap und Anlage -----------------------------------------

def test_action_new_creates_mini_ledger_with_header(tmp_path):
    target = new_ledger.action_new(
        tmp_path, symptom="Login hängt", repro="pytest tests/test_login.py::test_hang",
        expected="Login kehrt in < 1s zurück", observed="Login hängt endlos",
        slug=None, date_str="2026-08-16",
    )
    text = target.read_text(encoding="utf-8")
    assert text.startswith("<!-- skill: debug-ledger | schema: 1 | generated:")
    assert "Login hängt" in text
    assert "pytest tests/test_login.py::test_hang" in text
    assert "Erwartet: Login kehrt in < 1s zurück" in text
    assert "Beobachtet: Login hängt endlos" in text
    assert target.name == "2026-08-16-login-haengt.md"


def test_action_new_bootstraps_archive_and_index(tmp_path):
    assert not (tmp_path / "docs" / "debugging").exists()
    new_ledger.action_new(
        tmp_path, symptom="Bug", repro="cmd", expected="a", observed="b",
        slug="bug", date_str="2026-08-16",
    )
    index = tmp_path / "docs" / "debugging" / "INDEX.md"
    assert index.is_file()
    assert index.read_text(encoding="utf-8").startswith("<!-- skill: debug-ledger | schema: 1")


def test_action_new_bootstrap_header_reflects_the_real_invoking_command(tmp_path):
    """Reviewer-Fund: ein Bootstrap über --symptom trug vorher fest eine
    --resolve-Kopfzeile mit literalen Platzhaltern ('<ledger>', '<ursache>') —
    ein Kommando, das nie lief und nicht re-eintippbar war. Die Kopfzeile muss
    das tatsächlich laufende --symptom-Kommando zeigen."""
    new_ledger.action_new(
        tmp_path, symptom="Login hängt", repro="pytest -x", expected="ok", observed="haengt",
        slug="bug", date_str="2026-08-16",
    )
    index_text = (tmp_path / "docs" / "debugging" / "INDEX.md").read_text(encoding="utf-8")
    header_line = index_text.splitlines()[0]
    assert "--symptom" in header_line
    assert "--resolve" not in header_line
    assert "<ledger>" not in header_line
    assert "<ursache>" not in header_line


def test_action_resolve_bootstrap_header_uses_resolve_command(tmp_path):
    """Gegenrichtung: bootstrapt --resolve das Archiv (kein --symptom-Aufruf
    vorher), muss die Kopfzeile korrekt das --resolve-Kommando zeigen."""
    target = new_ledger.action_new(
        tmp_path, symptom="Bug", repro="cmd", expected="a", observed="b",
        slug="bug", date_str="2026-08-16",
    )
    (tmp_path / "docs" / "debugging" / "INDEX.md").unlink()  # Bootstrap erneut erzwingen
    rel = target.relative_to(tmp_path).as_posix()
    new_ledger.action_resolve(tmp_path, rel, "Ursache X")
    header_line = (tmp_path / "docs" / "debugging" / "INDEX.md").read_text(encoding="utf-8").splitlines()[0]
    assert "--resolve" in header_line
    assert rel in header_line
    assert "Ursache X" in header_line


def test_action_new_does_not_recreate_existing_index(tmp_path):
    (tmp_path / "docs" / "debugging").mkdir(parents=True)
    index = tmp_path / "docs" / "debugging" / "INDEX.md"
    index.write_text("<!-- skill: debug-ledger | schema: 1 | generated: x -->\n\nAlter Inhalt\n", encoding="utf-8")
    new_ledger.action_new(
        tmp_path, symptom="Bug", repro="cmd", expected="a", observed="b",
        slug="bug", date_str="2026-08-16",
    )
    assert "Alter Inhalt" in index.read_text(encoding="utf-8")


def test_action_new_avoids_filename_collision(tmp_path):
    first = new_ledger.action_new(
        tmp_path, symptom="Bug", repro="cmd", expected="a", observed="b",
        slug="bug", date_str="2026-08-16",
    )
    second = new_ledger.action_new(
        tmp_path, symptom="Bug erneut", repro="cmd2", expected="a2", observed="b2",
        slug="bug", date_str="2026-08-16",
    )
    assert first != second
    assert second.name == "2026-08-16-bug-2.md"


def test_action_new_defaults_to_todays_date(tmp_path, monkeypatch):
    import datetime
    fixed = datetime.date(2030, 1, 2)

    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr(new_ledger, "date", FakeDate)
    target = new_ledger.action_new(
        tmp_path, symptom="Bug", repro="cmd", expected="a", observed="b",
        slug="bug", date_str=None,
    )
    assert target.name == "2030-01-02-bug.md"


# --- action_escalate -----------------------------------------------------------

def test_action_escalate_appends_full_schema(tmp_path):
    target = new_ledger.action_new(
        tmp_path, symptom="Bug", repro="cmd", expected="a", observed="b",
        slug="bug", date_str="2026-08-16",
    )
    rel = target.relative_to(tmp_path).as_posix()
    new_ledger.action_escalate(tmp_path, rel)
    text = target.read_text(encoding="utf-8")
    assert "## Hypothesen" in text
    assert "## Root Cause" in text
    assert "| Hypothese | Test | Ergebnis | Verdict |" in text
    # Mini-Felder bleiben erhalten
    assert "## Symptom" in text


def test_action_escalate_is_idempotent(tmp_path, capsys):
    target = new_ledger.action_new(
        tmp_path, symptom="Bug", repro="cmd", expected="a", observed="b",
        slug="bug", date_str="2026-08-16",
    )
    rel = target.relative_to(tmp_path).as_posix()
    new_ledger.action_escalate(tmp_path, rel)
    before = target.read_text(encoding="utf-8")
    capsys.readouterr()
    new_ledger.action_escalate(tmp_path, rel)
    after = target.read_text(encoding="utf-8")
    assert before == after
    assert "bereits im vollen modus" in capsys.readouterr().out.lower()


def test_action_escalate_missing_ledger_raises(tmp_path):
    with pytest.raises(new_ledger.LedgerError, match="nicht gefunden"):
        new_ledger.action_escalate(tmp_path, "docs/debugging/does-not-exist.md")


# --- action_resolve -------------------------------------------------------------

def test_action_resolve_appends_index_entry(tmp_path):
    target = new_ledger.action_new(
        tmp_path, symptom="Login hängt beim Start", repro="cmd", expected="a", observed="b",
        slug="login", date_str="2026-08-16",
    )
    rel = target.relative_to(tmp_path).as_posix()
    new_ledger.action_resolve(tmp_path, rel, "Cache-Key kollidierte zwischen zwei Layern")

    index_text = (tmp_path / "docs" / "debugging" / "INDEX.md").read_text(encoding="utf-8")
    assert "Login hängt beim Start" in index_text
    assert "Cache-Key kollidierte zwischen zwei Layern" in index_text
    assert rel in index_text


def test_action_resolve_is_idempotent(tmp_path, capsys):
    target = new_ledger.action_new(
        tmp_path, symptom="Bug", repro="cmd", expected="a", observed="b",
        slug="bug", date_str="2026-08-16",
    )
    rel = target.relative_to(tmp_path).as_posix()
    new_ledger.action_resolve(tmp_path, rel, "Ursache A")
    index_before = (tmp_path / "docs" / "debugging" / "INDEX.md").read_text(encoding="utf-8")

    new_ledger.action_resolve(tmp_path, rel, "Ursache A")
    index_after = (tmp_path / "docs" / "debugging" / "INDEX.md").read_text(encoding="utf-8")
    assert index_before == index_after


def test_action_resolve_missing_ledger_raises(tmp_path):
    with pytest.raises(new_ledger.LedgerError, match="nicht gefunden"):
        new_ledger.action_resolve(tmp_path, "docs/debugging/nope.md", "Ursache")


def test_action_resolve_warns_visibly_at_fifty_entries(tmp_path, capsys):
    (tmp_path / "docs" / "debugging").mkdir(parents=True)
    lines = "\n".join(f"- Symptom {i} → Ursache {i} ([f{i}.md](docs/debugging/f{i}.md))" for i in range(49))
    (tmp_path / "docs" / "debugging" / "INDEX.md").write_text(
        "<!-- skill: debug-ledger | schema: 1 | generated: x -->\n\n" + lines + "\n",
        encoding="utf-8",
    )
    target = new_ledger.action_new(
        tmp_path, symptom="Der 50. Fall", repro="cmd", expected="a", observed="b",
        slug="fall50", date_str="2026-08-16",
    )
    rel = target.relative_to(tmp_path).as_posix()
    capsys.readouterr()
    new_ledger.action_resolve(tmp_path, rel, "Ursache 50")
    out = capsys.readouterr().out
    assert "WARNUNG" in out
    assert "50" in out


def test_action_resolve_no_warning_below_fifty(tmp_path, capsys):
    target = new_ledger.action_new(
        tmp_path, symptom="Bug", repro="cmd", expected="a", observed="b",
        slug="bug", date_str="2026-08-16",
    )
    rel = target.relative_to(tmp_path).as_posix()
    capsys.readouterr()
    new_ledger.action_resolve(tmp_path, rel, "Ursache")
    out = capsys.readouterr().out
    assert "WARNUNG" not in out


# --- Verdrahtung über main() (CLI) ---------------------------------------------

def test_main_new_action_end_to_end(tmp_path, capsys):
    rc = new_ledger.main([
        "--symptom", "CLI-Bug", "--repro", "pytest -x", "--expected", "gruen", "--observed", "rot",
        "--slug", "cli-bug", "--date", "2026-08-16", "--repo", str(tmp_path),
    ])
    assert rc == 0
    target = tmp_path / "docs" / "debugging" / "2026-08-16-cli-bug.md"
    assert target.is_file()
    out = capsys.readouterr().out
    assert "Mini-Ledger angelegt" in out


def test_main_rejects_no_action(tmp_path):
    with pytest.raises(SystemExit):
        new_ledger.main(["--repo", str(tmp_path)])


def test_main_rejects_two_actions_at_once(tmp_path):
    with pytest.raises(SystemExit):
        new_ledger.main([
            "--symptom", "x", "--repro", "y", "--expected", "z", "--observed", "w",
            "--resolve", "docs/debugging/x.md", "--cause", "c", "--repo", str(tmp_path),
        ])


def test_main_new_requires_all_four_fields(tmp_path):
    with pytest.raises(SystemExit):
        new_ledger.main(["--symptom", "nur symptom", "--repo", str(tmp_path)])


def test_main_resolve_requires_cause(tmp_path):
    with pytest.raises(SystemExit):
        new_ledger.main(["--resolve", "docs/debugging/x.md", "--repo", str(tmp_path)])


def test_main_escalate_end_to_end(tmp_path, capsys):
    new_ledger.main([
        "--symptom", "x", "--repro", "y", "--expected", "z", "--observed", "w",
        "--slug", "x", "--date", "2026-08-16", "--repo", str(tmp_path),
    ])
    capsys.readouterr()
    rc = new_ledger.main(["--escalate", "docs/debugging/2026-08-16-x.md", "--repo", str(tmp_path)])
    assert rc == 0
    text = (tmp_path / "docs" / "debugging" / "2026-08-16-x.md").read_text(encoding="utf-8")
    assert "## Hypothesen" in text


def test_main_escalate_missing_ledger_returns_error_code(tmp_path):
    rc = new_ledger.main(["--escalate", "docs/debugging/nope.md", "--repo", str(tmp_path)])
    assert rc == 1
