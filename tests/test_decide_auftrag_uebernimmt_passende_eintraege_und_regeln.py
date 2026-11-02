# spec-stub: auftrag-uebernimmt-passende-eintraege-und-regeln
"""Stub für Akzeptanzkriterium "Auftrag übernimmt passende Einträge und Regeln" aus docs/specs/wip/decide.md.

Given das Protokoll der Sitzung hat eine Entscheidung mit Thema `CLI` und eine mit Thema `Logging`
Given `.skills/decide/rules.md` enthält `immer fragen: UI-Texte`
When `decide_log.py brief --topic CLI` läuft
Then enthält der Auftrag unter Schon entschieden genau den Eintrag mit Thema `CLI`
Then unter Feste Vorgaben die Regel mit ihrer Datei als Quelle
Then die Felder Frage, Anlass und Wo nachsehen stehen leer zum Ausfüllen
"""
import pytest


@pytest.mark.skip("stub: noch nicht implementiert")
def test_decide_auftrag_uebernimmt_passende_eintraege_und_regeln():
    # Arrange
    ...

    # Act
    ...

    # Assert
    ...
