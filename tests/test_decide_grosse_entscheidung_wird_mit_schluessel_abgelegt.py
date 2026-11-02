# spec-stub: grosse-entscheidung-wird-mit-schluessel-abgelegt
"""Stub für Akzeptanzkriterium "Große Entscheidung wird mit Schlüssel abgelegt" aus docs/specs/wip/decide.md.

Given ein Repo ohne `docs/big-decisions.md`
When `decide_log.py add` eine große Entscheidung mit Schlüssel `dependency:pyproject.toml`, drei Optionen und einer Empfehlung erhält
Then entsteht `docs/big-decisions.md` mit Kopfzeile und einem Block `D-1` mit Status offen und dem Schlüssel
Then die Ausgabe meldet „angelegt: docs/big-decisions.md"
"""
import pytest


@pytest.mark.skip("stub: noch nicht implementiert")
def test_decide_grosse_entscheidung_wird_mit_schluessel_abgelegt():
    # Arrange
    ...

    # Act
    ...

    # Assert
    ...
