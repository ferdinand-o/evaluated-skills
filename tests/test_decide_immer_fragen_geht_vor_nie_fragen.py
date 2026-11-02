# spec-stub: immer-fragen-geht-vor-nie-fragen
"""Stub für Akzeptanzkriterium "Immer fragen geht vor nie fragen" aus docs/specs/wip/decide.md.

Given `.skills/decide/rules.md` enthält `immer fragen: UI-Texte`
Given `~/.skills/decide/rules.md` enthält `nie fragen: UI-Texte`
When `decide_log.py add` eine kleine Entscheidung mit Thema `UI-Texte` erhält
Then legt es sie als große Frage ab
Then die Ausgabe nennt den Widerspruch mit beiden Dateien
"""
import pytest


@pytest.mark.skip("stub: noch nicht implementiert")
def test_decide_immer_fragen_geht_vor_nie_fragen():
    # Arrange
    ...

    # Act
    ...

    # Assert
    ...
