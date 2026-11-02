# spec-stub: zusammenfassung-kuerzt-ab-zehn-eintraegen
"""Stub für Akzeptanzkriterium "Zusammenfassung kürzt ab zehn Einträgen" aus docs/specs/wip/decide.md.

Given das Protokoll der laufenden Sitzung hat zwölf Einträge
When `decide_log.py summary` läuft
Then nennt es die zehn jüngsten und den Pfad des Protokolls
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


def test_decide_zusammenfassung_kuerzt_ab_zehn_eintraegen(tmp_path, monkeypatch, capsys):
    # Arrange
    root, _ = repo(tmp_path, monkeypatch)
    for n in range(1, 13):
        assert add_small("CLI", f"Frage {n:02d}?", "ja", f"gesucht: cli.py — Treffer: cli.py:{n}") == 0
    capsys.readouterr()

    # Act
    code = dl.main(["summary"])
    out = capsys.readouterr().out

    # Assert
    assert code == 0
    entries = [line for line in out.splitlines() if line.startswith("- ")]
    assert len(entries) == 10
    assert [f"Frage {n:02d}?" in out for n in range(1, 13)] == [False] * 2 + [True] * 10
    assert f".skills/cache/decide/{SESSION}/log.md" in out
    assert len(rows(root)) == 12
