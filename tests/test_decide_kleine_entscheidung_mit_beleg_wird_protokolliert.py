# spec-stub: kleine-entscheidung-mit-beleg-wird-protokolliert
"""Stub für Akzeptanzkriterium "Kleine Entscheidung mit Beleg wird protokolliert" aus docs/specs/wip/decide.md.

Given eine Sitzung mit gesetzter `CLAUDE_CODE_SESSION_ID`
When `decide_log.py add` eine kleine Entscheidung mit Belegzeile „gesucht: src/parsers — Treffer: src/parsers/csv.py:12" erhält
Then steht in `.skills/cache/decide/<session>/log.md` eine Zeile mit Frage, Thema, Klasse klein, Entscheidung und Beleg
Then die Datei trägt in Zeile 1 die Kopfzeile
"""
import pytest


@pytest.mark.skip("stub: noch nicht implementiert")
def test_decide_kleine_entscheidung_mit_beleg_wird_protokolliert():
    # Arrange
    ...

    # Act
    ...

    # Assert
    ...
