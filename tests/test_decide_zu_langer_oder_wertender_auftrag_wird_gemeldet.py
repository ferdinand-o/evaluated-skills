# spec-stub: zu-langer-oder-wertender-auftrag-wird-gemeldet
"""Stub für Akzeptanzkriterium "Zu langer oder wertender Auftrag wird gemeldet" aus docs/specs/wip/decide.md.

Given ein ausgefüllter Auftrag mit 30 Zeilen, einem Feld `Empfehlung des Hauptagenten` und der Frage „Sollte die CLI besser argparse nutzen?"
When `decide_log.py brief --check` den Auftrag prüft
Then meldet es die Länge über 25 Zeilen, das unzulässige Feld und die Wörter „sollte" und „besser" in der Frage
Then endet mit Exit 1
"""
import pytest


@pytest.mark.skip("stub: noch nicht implementiert")
def test_decide_zu_langer_oder_wertender_auftrag_wird_gemeldet():
    # Arrange
    ...

    # Act
    ...

    # Assert
    ...
