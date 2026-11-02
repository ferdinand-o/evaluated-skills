# spec-stub: regel-nie-fragen-haelt-kleine-entscheidung-aus-der-zusammenf
"""Stub für Akzeptanzkriterium "Regel nie fragen hält kleine Entscheidung aus der Zusammenfassung" aus docs/specs/wip/decide.md.

Given `.skills/decide/rules.md` enthält `nie fragen: Logging`
Given das Protokoll der Sitzung hat je eine kleine Entscheidung mit Thema `Logging` und `CLI`
When `decide_log.py summary` läuft
Then nennt es nur die Entscheidung mit Thema `CLI`
Then das Protokoll enthält weiter beide
"""
import pytest


@pytest.mark.skip("stub: noch nicht implementiert")
def test_decide_regel_nie_fragen_haelt_kleine_entscheidung_aus_der_zusammenf():
    # Arrange
    ...

    # Act
    ...

    # Assert
    ...
