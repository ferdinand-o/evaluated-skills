# spec-stub: teure-aenderung-ohne-freigabe-wird-gemeldet
"""Stub für Akzeptanzkriterium "Teure Änderung ohne Freigabe wird gemeldet" aus docs/specs/wip/decide.md.

Given ein Diff, der eine neue Abhängigkeit in `pyproject.toml` und eine neue Datei unter `migrations/` enthält
Given `docs/big-decisions.md` führt `dependency:pyproject.toml` mit Status offen und `migration:migrations/` gar nicht
When `decide_log.py check --range <bereich>` läuft
Then meldet es beide Stellen mit Datei, Kategorie und Grund aus `reversibility.md`
Then die Ausgabe nennt die ungeprüften Kategorien
"""
import pytest


@pytest.mark.skip("stub: noch nicht implementiert")
def test_decide_teure_aenderung_ohne_freigabe_wird_gemeldet():
    # Arrange
    ...

    # Act
    ...

    # Assert
    ...
