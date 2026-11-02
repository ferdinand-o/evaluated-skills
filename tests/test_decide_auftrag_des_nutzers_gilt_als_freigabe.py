# spec-stub: auftrag-des-nutzers-gilt-als-freigabe
"""Stub für Akzeptanzkriterium "Auftrag des Nutzers gilt als Freigabe" aus docs/specs/wip/decide.md.

Given eine große Entscheidung mit Schlüssel `migration:migrations/`
When `decide_log.py add` sie mit `--approved-by-request "lösch die Spalte legacy_id"` erhält
Then steht ihr Block in `docs/big-decisions.md` auf freigegeben
Then als Quelle der Antwort steht das Zitat des Auftrags
"""
import re

from conftest import decide_script


def test_decide_auftrag_des_nutzers_gilt_als_freigabe(decide_repo):
    # Arrange
    root, _ = decide_repo
    dl = decide_script()

    # Act
    code = dl.main(["add", "--class", "gross", "--topic", "Migrationen",
                    "--question", "Spalte legacy_id aus User entfernen?", "--key", "migration:migrations/",
                    "--approved-by-request", "lösch die Spalte legacy_id"])

    # Assert
    assert code == 0
    text = (root / "docs" / "big-decisions.md").read_text(encoding="utf-8")
    assert re.search(r"(?m)^## D-1 · \d{4}-\d{2}-\d{2} · freigegeben$", text)
    assert "\nQuelle der Antwort: Auftrag: „lösch die Spalte legacy_id“\n" in text
    assert "\nSchlüssel: migration:migrations/\n" in text
