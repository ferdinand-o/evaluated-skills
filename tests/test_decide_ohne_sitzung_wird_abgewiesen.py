# spec-stub: ohne-sitzung-wird-abgewiesen
"""Stub für Akzeptanzkriterium "Ohne Sitzung wird abgewiesen" aus docs/specs/wip/decide.md.

Given `CLAUDE_CODE_SESSION_ID` ist nicht gesetzt
When `decide_log.py add` ohne `--session` läuft
Then legt es keine Datei an und endet mit Exit 1
Then der Grund nennt `--session`
"""
import pytest


@pytest.mark.skip("stub: noch nicht implementiert")
def test_decide_ohne_sitzung_wird_abgewiesen():
    # Arrange
    ...

    # Act
    ...

    # Assert
    ...
