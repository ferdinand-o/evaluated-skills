# spec-stub: aehnliches-regelthema-wird-nur-gemeldet
"""Stub für Akzeptanzkriterium "Ähnliches Regelthema wird nur gemeldet" aus docs/specs/wip/decide.md.

Given `.skills/decide/rules.md` enthält `immer fragen: UI-Texte`
When `decide_log.py add` eine kleine Entscheidung mit Thema `UI-Text` erhält
Then bleibt sie klein
Then die Ausgabe nennt die Regel `immer fragen: UI-Texte` als Hinweis
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


def test_decide_aehnliches_regelthema_wird_nur_gemeldet(tmp_path, monkeypatch, capsys):
    # Arrange
    root, _ = repo(tmp_path, monkeypatch)
    (root / ".skills" / "decide").mkdir(parents=True)
    (root / ".skills" / "decide" / "rules.md").write_text("immer fragen: UI-Texte\n", encoding="utf-8")

    # Act
    code = add_small("UI-Text", "Fehlermeldung beim Import?", "Datei nicht lesbar: <pfad>",
                     "gesucht: src/messages.py — Treffer: src/messages.py:8")
    out = capsys.readouterr().out

    # Assert
    assert code == 0
    [row] = rows(root)
    assert row[1:3] == ["UI-Text", "klein"]
    assert row[6] == "—"
    assert "Hinweis" in out
    assert "immer fragen: UI-Texte" in out
    assert not (root / "docs" / "big-decisions.md").exists()
