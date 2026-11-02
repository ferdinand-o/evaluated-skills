# spec-stub: ohne-sitzung-wird-abgewiesen
"""Stub für Akzeptanzkriterium "Ohne Sitzung wird abgewiesen" aus docs/specs/wip/decide.md.

Given `CLAUDE_CODE_SESSION_ID` ist nicht gesetzt
When `decide_log.py add` ohne `--session` läuft
Then legt es keine Datei an und endet mit Exit 1
Then der Grund nennt `--session`
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


def test_decide_ohne_sitzung_wird_abgewiesen(tmp_path, monkeypatch, capsys):
    # Arrange
    root, _ = repo(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    call = ["add", "--class", "klein", "--topic", "CLI", "--question", "Kurzoption -v?", "--decision", "ja",
            "--evidence", "gesucht: cli.py — Treffer: cli.py:4"]

    # Act
    code = dl.main(call)
    out = capsys.readouterr()

    # Assert
    assert code == 1
    assert "--session" in out.out + out.err
    assert not (root / ".skills").exists()

    # --session ersetzt die Umgebungsvariable
    assert dl.main(call + ["--session", "von-hand"]) == 0
    assert rows(root, "von-hand")[0][1] == "CLI"
