# spec-stub: kleine-entscheidung-ohne-treffer-wird-annahme
"""Stub für Akzeptanzkriterium "Kleine Entscheidung ohne Treffer wird Annahme" aus docs/specs/wip/decide.md.

Given eine Belegzeile „gesucht: docs, README — nichts gefunden"
When `decide_log.py add` die kleine Entscheidung erhält
Then steht sie als Annahme im Protokoll, nicht als Entscheidung
"""
from conftest import decide_add_small as add_small
from conftest import decide_rows as rows


def test_decide_kleine_entscheidung_ohne_treffer_wird_annahme(decide_repo, capsys):
    # Arrange
    root, _ = decide_repo

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
