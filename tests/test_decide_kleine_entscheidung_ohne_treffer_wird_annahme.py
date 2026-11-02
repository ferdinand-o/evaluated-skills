# spec-stub: kleine-entscheidung-ohne-treffer-wird-annahme
"""Stub für Akzeptanzkriterium "Kleine Entscheidung ohne Treffer wird Annahme" aus docs/specs/wip/decide.md.

Given eine Belegzeile „gesucht: docs, README — nichts gefunden"
When `decide_log.py add` die kleine Entscheidung erhält
Then steht sie als Annahme im Protokoll, nicht als Entscheidung
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


def test_decide_kleine_entscheidung_ohne_treffer_wird_annahme(tmp_path, monkeypatch, capsys):
    # Arrange
    root, _ = repo(tmp_path, monkeypatch)

    # Act
    code = add_small("Konfiguration", "Wo liegt die Konfigurationsdatei?", "config.toml im Repo-Wurzelordner",
                     "gesucht: docs, README — nichts gefunden")
    out = capsys.readouterr().out

    # Assert
    assert code == 0
    [row] = rows(root)
    assert row[2] == "annahme"
    assert row[4] == "config.toml im Repo-Wurzelordner"
    assert row[5] == "gesucht: docs, README — nichts gefunden"
    assert "Annahme" in out
