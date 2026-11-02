"""Tests für skills/decide/scripts/decide_log.py (Spec 28, Task 1): Wurzel und Sitzung,
Form der Belegzeile, Tabellenzeichen und Umlaute, Regeln aus Repo- und Nutzerdatei."""

from pathlib import Path

from conftest import git, load_script

dl = load_script("skills/decide/scripts/decide_log.py")
SESSION = "sitzung-1"


def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SESSION)
    monkeypatch.chdir(root)
    return root, home


def log_file(root, session=SESSION):
    return root / ".skills" / "cache" / "decide" / session / "log.md"


def rows(root, session=SESSION):
    lines = log_file(root, session).read_text(encoding="utf-8").splitlines()
    return [[c.strip() for c in line.strip()[1:-1].split("|")]
            for line in lines
            if line.startswith("| ") and not line.startswith(("| zeit ", "| ---"))]


def add_small(topic, question, decision, evidence, *extra):
    return dl.main(["add", "--class", "klein", "--topic", topic, "--question", question,
                    "--decision", decision, "--evidence", evidence, *extra])


def write_rules(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_root_and_session(tmp_path, monkeypatch, capsys):
    root = tmp_path / "repo"
    (root / "a" / "b").mkdir(parents=True)
    git(root, "init", "-q")
    assert dl.repo_root(root / "a" / "b").resolve() == root.resolve()
    plain = tmp_path / "ohne-git"
    plain.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    assert dl.repo_root(plain) == plain

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "aus-env")
    assert dl.session_id("von-hand") == "von-hand"
    assert dl.session_id(None) == "aus-env"
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    assert dl.session_id(None) is None

    # Eine Sitzungs-ID wird Ordnername: kein Pfadtrenner, kein `..`.
    monkeypatch.chdir(root)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert add_small("CLI", "?", "ja", "gesucht: a — nichts gefunden", "--session", "../weg") == 1
    assert "--session" in capsys.readouterr().err
    assert not (root / ".skills").exists()


def test_evidence_form(tmp_path, monkeypatch, capsys):
    root, _ = repo(tmp_path, monkeypatch)
    want = "gesucht: x — Treffer: a.py:3"
    assert dl.normalize_evidence("gesucht: x - Treffer: ./a.py:3", root) == want
    assert dl.normalize_evidence("gesucht: x -- Treffer: a.py:3", root) == want
    assert dl.normalize_evidence(f"gesucht: x — Treffer: {root}/a.py:3", root) == want
    assert dl.normalize_evidence(f"gesucht: x — Treffer: {root.resolve()}/a.py:3", root) == want
    assert (dl.normalize_evidence(f"gesucht: {root}/src, ./docs — nichts gefunden", root)
            == "gesucht: src, docs — nichts gefunden")
    outside = tmp_path / "anderswo" / "a.py"
    assert (dl.normalize_evidence(f"gesucht: x — Treffer: {outside}:3", root)
            == f"gesucht: x — Treffer: {outside}:3")

    # über die Kommandozeile: normalisiert ins Protokoll
    assert add_small("CLI", "Kurzoption?", "Kurzform -v", f"gesucht: x -- Treffer: {root}/a.py:3") == 0
    assert rows(root)[0][5] == want

    # andere Form: Exit 1, keine Zeile, der Grund nennt die erwartete Form
    capsys.readouterr()
    for bad in ("gesucht: x", "Treffer: a.py:3", "gesucht: x — Treffer: a.py", "gesucht: — nichts gefunden"):
        assert add_small("CLI", "Noch eine?", "nein", bad) == 1, bad
        err = capsys.readouterr().err
        assert "nichts gefunden" in err and "Treffer: <datei:zeile>" in err, err
    assert len(rows(root)) == 1


def test_pipe_and_unicode(tmp_path, monkeypatch):
    root, _ = repo(tmp_path, monkeypatch)
    assert add_small("Übersetzungen", "Trenner | oder ; für Größen?", "„|“ bleibt",
                     "gesucht: a|b — nichts gefunden") == 0
    [row] = rows(root)
    assert len(row) == 7
    assert row[1:6] == ["Übersetzungen", "annahme", "Trenner ¦ oder ; für Größen?", "„¦“ bleibt",
                        "gesucht: a¦b — nichts gefunden"]
    raw = log_file(root).read_bytes()
    assert "Größen".encode("utf-8") in raw
    raw.decode("utf-8")


def test_rules_listing(tmp_path, monkeypatch, capsys):
    root, home = repo(tmp_path, monkeypatch)
    repo_rules = root / ".skills" / "decide" / "rules.md"
    user_rules = home / ".skills" / "decide" / "rules.md"
    write_rules(repo_rules, "# Kommentarzeile\nnie fragen: UI-Texte   # Wortlaut ist egal\n\n")
    write_rules(user_rules, "immer fragen: Migrationen\n#immer fragen: Versteckt\nunsinn ohne Doppelpunkt\n")

    rules = dl.load_rules(root, home)
    assert [(r.kind, r.topic) for r in rules] == [("nie fragen", "UI-Texte"), ("immer fragen", "Migrationen")]
    assert rules[0].path == repo_rules and rules[1].path == user_rules

    assert dl.main(["rules"]) == 0
    out = capsys.readouterr().out
    assert "nie fragen: UI-Texte" in out and ".skills/decide/rules.md" in out
    assert "immer fragen: Migrationen" in out and "~/.skills/decide/rules.md" in out
    assert "Versteckt" not in out and "Kommentarzeile" not in out and "Wortlaut" not in out
    assert "unsinn ohne Doppelpunkt" in out          # sichtbar ignoriert, nicht still

    # Treffer nach Kleinschreibung und Trimmen: Thema in der Schreibweise der Regel
    assert add_small("  ui-texte ", "Text der Fehlermeldung?", "Datei fehlt",
                     "gesucht: msgs.py — Treffer: msgs.py:2") == 0
    [row] = rows(root)
    assert row[1:3] == ["UI-Texte", "klein"]
    assert "nie fragen: UI-Texte" in row[6]
    out = capsys.readouterr().out
    assert "nie fragen: UI-Texte" in out


def test_rules_without_files(tmp_path, monkeypatch, capsys):
    repo(tmp_path, monkeypatch)
    assert dl.load_rules(Path.cwd(), Path(tmp_path / "home")) == []
    assert dl.main(["rules"]) == 0
    assert "Keine Regeln" in capsys.readouterr().out


def test_upgrade_without_options_writes_nothing(tmp_path, monkeypatch, capsys):
    root, home = repo(tmp_path, monkeypatch)
    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: UI-Texte\n")
    assert add_small("ui-texte", "Text der Fehlermeldung?", "Datei fehlt",
                     "gesucht: msgs.py — Treffer: msgs.py:2") == 1
    err = capsys.readouterr().err
    assert "Regel immer fragen: UI-Texte trifft — zwei bis vier --option nötig" in err
    assert add_small("UI-Texte", "Text?", "A", "gesucht: msgs.py — Treffer: msgs.py:2",
                     "--option", "A: kurz") == 1
    assert "zwei bis vier --option" in capsys.readouterr().err
    assert not log_file(root).exists()
    assert not (root / "docs").exists()


def test_summary_without_entries(tmp_path, monkeypatch, capsys):
    repo(tmp_path, monkeypatch)
    assert dl.main(["summary"]) == 0
    out = capsys.readouterr().out
    assert "Keine Einträge" in out
    assert not [line for line in out.splitlines() if line.startswith("- ")]
