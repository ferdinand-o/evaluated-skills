# spec-stub: kleine-entscheidung-mit-beleg-wird-protokolliert
"""Stub für Akzeptanzkriterium "Kleine Entscheidung mit Beleg wird protokolliert" aus docs/specs/wip/decide.md.

Given eine Sitzung mit gesetzter `CLAUDE_CODE_SESSION_ID`
When `decide_log.py add` eine kleine Entscheidung mit Belegzeile „gesucht: src/parsers — Treffer: src/parsers/csv.py:12" erhält
Then steht in `.skills/cache/decide/<session>/log.md` eine Zeile mit Frage, Thema, Klasse klein, Entscheidung und Beleg
Then die Datei trägt in Zeile 1 die Kopfzeile
"""
import re

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


def test_decide_kleine_entscheidung_mit_beleg_wird_protokolliert(tmp_path, monkeypatch, capsys):
    # Arrange
    root, _ = repo(tmp_path, monkeypatch)

    # Act
    code = add_small("CSV-Parser", "Welcher Trenner gilt ohne Angabe?", "Semikolon wie im bestehenden Parser",
                     "gesucht: src/parsers — Treffer: src/parsers/csv.py:12")
    out = capsys.readouterr()

    # Assert
    assert code == 0, out
    lines = log_file(root).read_text(encoding="utf-8").splitlines()
    assert re.fullmatch(r"<!-- skill: decide \| schema: 1 \| generated: .+ -->", lines[0])
    assert "| zeit | thema | klasse | frage | entscheidung | beleg | regel |" in lines
    assert len(rows(root)) == 1
    zeit, *rest = rows(root)[0]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", zeit)
    assert rest == ["CSV-Parser", "klein", "Welcher Trenner gilt ohne Angabe?",
                    "Semikolon wie im bestehenden Parser",
                    "gesucht: src/parsers — Treffer: src/parsers/csv.py:12", "—"]
