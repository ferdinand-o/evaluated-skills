# spec-stub: regel-nie-fragen-haelt-kleine-entscheidung-aus-der-zusammenf
"""Stub für Akzeptanzkriterium "Regel nie fragen hält kleine Entscheidung aus der Zusammenfassung" aus docs/specs/wip/decide.md.

Given `.skills/decide/rules.md` enthält `nie fragen: Logging`
Given das Protokoll der Sitzung hat je eine kleine Entscheidung mit Thema `Logging` und `CLI`
When `decide_log.py summary` läuft
Then nennt es nur die Entscheidung mit Thema `CLI`
Then das Protokoll enthält weiter beide
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


def test_decide_regel_nie_fragen_haelt_kleine_entscheidung_aus_der_zusammenf(tmp_path, monkeypatch, capsys):
    # Arrange
    root, _ = repo(tmp_path, monkeypatch)
    (root / ".skills" / "decide").mkdir(parents=True)
    (root / ".skills" / "decide" / "rules.md").write_text("nie fragen: Logging\n", encoding="utf-8")
    assert add_small("Logging", "Loglevel für Retries?", "debug",
                     "gesucht: src/net.py — Treffer: src/net.py:30") == 0
    assert add_small("CLI", "Kurzoption für --verbose?", "Kurzform -v",
                     "gesucht: src/cli.py — Treffer: src/cli.py:12") == 0
    capsys.readouterr()

    # Act
    code = dl.main(["summary"])
    out = capsys.readouterr().out

    # Assert
    assert code == 0
    assert "Kurzoption für --verbose?" in out
    assert "Loglevel für Retries?" not in out
    assert [r[1] for r in rows(root)] == ["Logging", "CLI"]
