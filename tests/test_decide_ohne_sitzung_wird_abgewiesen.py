# spec-stub: ohne-sitzung-wird-abgewiesen
"""Stub für Akzeptanzkriterium "Ohne Sitzung wird abgewiesen" aus docs/specs/wip/decide.md.

Given `CLAUDE_CODE_SESSION_ID` ist nicht gesetzt
When `decide_log.py add` ohne `--session` läuft
Then legt es keine Datei an und endet mit Exit 1
Then der Grund nennt `--session`
"""
from conftest import decide_rows as rows
from conftest import decide_script

dl = decide_script()


def test_decide_ohne_sitzung_wird_abgewiesen(decide_repo, monkeypatch, capsys):
    # Arrange
    root, _ = decide_repo
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
