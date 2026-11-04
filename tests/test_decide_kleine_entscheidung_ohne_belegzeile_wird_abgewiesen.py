# spec-stub: kleine-entscheidung-ohne-belegzeile-wird-abgewiesen
"""Stub für Akzeptanzkriterium "Kleine Entscheidung ohne Belegzeile wird abgewiesen" aus docs/specs/wip/decide.md.

Given ein Aufruf von `decide_log.py add` für eine kleine Entscheidung ohne Belegzeile
When das Skript läuft
Then schreibt es keine Zeile und endet mit Exit 1 und dem Grund
"""
from conftest import decide_log_file as log_file
from conftest import decide_script

dl = decide_script()


def test_decide_kleine_entscheidung_ohne_belegzeile_wird_abgewiesen(decide_repo, capsys):
    # Arrange
    root, _ = decide_repo
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
