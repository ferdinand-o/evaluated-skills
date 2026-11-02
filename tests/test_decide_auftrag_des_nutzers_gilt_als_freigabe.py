# spec-stub: auftrag-des-nutzers-gilt-als-freigabe
"""Stub für Akzeptanzkriterium "Auftrag des Nutzers gilt als Freigabe" aus docs/specs/wip/decide.md.

Given eine große Entscheidung mit Schlüssel `migration:migrations/`
When `decide_log.py add` sie mit `--approved-by-request "lösch die Spalte legacy_id"` erhält
Then steht ihr Block in `docs/big-decisions.md` auf freigegeben
Then als Quelle der Antwort steht das Zitat des Auftrags
"""
import pytest


@pytest.mark.skip("stub: noch nicht implementiert")
def test_decide_auftrag_des_nutzers_gilt_als_freigabe():
    # Arrange
    ...

    # Act
    ...

    # Assert
    ...
