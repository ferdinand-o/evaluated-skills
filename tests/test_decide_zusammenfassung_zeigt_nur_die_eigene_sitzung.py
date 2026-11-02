# spec-stub: zusammenfassung-zeigt-nur-die-eigene-sitzung
"""Stub für Akzeptanzkriterium "Zusammenfassung zeigt nur die eigene Sitzung" aus docs/specs/wip/decide.md.

Given das Protokoll der laufenden Sitzung hat zwei Entscheidungen und eine Annahme
Given ein Protokoll einer früheren Sitzung hat fünf Einträge
When `decide_log.py summary` läuft
Then nennt es genau die drei Einträge der laufenden Sitzung
"""
from conftest import git, load_script

dl = load_script("skills/decide/scripts/decide_log.py")
SESSION = "sitzung-1"


def repo(tmp_path, monkeypatch):
    """Git-Repo als Wurzel, eigenes HOME, Sitzung aus der Umgebung."""
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
    """Zellen der Tabellenzeilen ohne Kopf: [zeit, thema, klasse, frage, entscheidung, beleg, regel]."""
    lines = log_file(root, session).read_text(encoding="utf-8").splitlines()
    return [[c.strip() for c in line.strip()[1:-1].split("|")]
            for line in lines
            if line.startswith("| ") and not line.startswith(("| zeit ", "| ---"))]


def add_small(topic, question, decision, evidence, *extra):
    return dl.main(["add", "--class", "klein", "--topic", topic, "--question", question,
                    "--decision", decision, "--evidence", evidence, *extra])


def test_decide_zusammenfassung_zeigt_nur_die_eigene_sitzung(tmp_path, monkeypatch, capsys):
    # Arrange
    root, _ = repo(tmp_path, monkeypatch)
    for n in range(5):
        assert add_small("Alt", f"Frühere Frage {n}?", "x", "gesucht: a — nichts gefunden",
                         "--session", "frueher") == 0
    assert add_small("CLI", "Kurzoption?", "Kurzform -v", "gesucht: cli.py — Treffer: cli.py:3") == 0
    assert add_small("CSV", "Trenner?", "Semikolon", "gesucht: csv.py — Treffer: csv.py:9") == 0
    assert add_small("Konfig", "Dateiname?", "config.toml", "gesucht: docs — nichts gefunden") == 0
    capsys.readouterr()

    # Act
    code = dl.main(["summary"])
    out = capsys.readouterr().out

    # Assert
    assert code == 0
    entries = [line for line in out.splitlines() if line.startswith("- ")]
    assert len(entries) == 3
    assert all(q in out for q in ("Kurzoption?", "Trenner?", "Dateiname?"))
    assert "Frühere Frage" not in out
