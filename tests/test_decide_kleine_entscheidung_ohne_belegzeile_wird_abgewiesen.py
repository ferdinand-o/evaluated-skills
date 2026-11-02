# spec-stub: kleine-entscheidung-ohne-belegzeile-wird-abgewiesen
"""Stub für Akzeptanzkriterium "Kleine Entscheidung ohne Belegzeile wird abgewiesen" aus docs/specs/wip/decide.md.

Given ein Aufruf von `decide_log.py add` für eine kleine Entscheidung ohne Belegzeile
When das Skript läuft
Then schreibt es keine Zeile und endet mit Exit 1 und dem Grund
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


def test_decide_kleine_entscheidung_ohne_belegzeile_wird_abgewiesen(tmp_path, monkeypatch, capsys):
    # Arrange
    root, _ = repo(tmp_path, monkeypatch)
    call = ["add", "--class", "klein", "--topic", "CLI", "--question", "Kurzoption -v?", "--decision", "ja"]

    # Act
    code = dl.main(call)
    out = capsys.readouterr()
    code_empty = dl.main(call + ["--evidence", "  "])
    out_empty = capsys.readouterr()

    # Assert
    assert code == 1 and code_empty == 1
    assert "Keine Belegzeile" in out.out + out.err
    assert "Keine Belegzeile" in out_empty.out + out_empty.err
    assert "--evidence" in out.out + out.err
    assert not log_file(root).exists()
