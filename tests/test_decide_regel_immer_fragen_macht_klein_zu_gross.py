# spec-stub: regel-immer-fragen-macht-klein-zu-gross
"""Stub für Akzeptanzkriterium "Regel immer fragen macht klein zu groß" aus docs/specs/wip/decide.md.

Given `.skills/decide/rules.md` enthält `immer fragen: UI-Texte`
When `decide_log.py add` eine kleine Entscheidung mit Thema `UI-Texte` erhält
Then legt es sie als große Frage mit Status offen in `docs/big-decisions.md` ab
Then das Protokoll nennt die Regel als Grund
"""
import re

from conftest import decide_add_small, decide_rows


def test_decide_regel_immer_fragen_macht_klein_zu_gross(decide_repo):
    # Arrange
    root, _ = decide_repo
    rules = root / ".skills" / "decide" / "rules.md"
    rules.parent.mkdir(parents=True)
    rules.write_text("immer fragen: UI-Texte\n", encoding="utf-8")

    # Act
    code = decide_add_small("UI-Texte", "Wortlaut der Fehlermeldung?", "B: „Datei nicht gefunden“",
                            "gesucht: app/cli.py — Treffer: app/cli.py:12",
                            "--option", "A: „Fehler: Datei“", "--option", "B: „Datei nicht gefunden“")

    # Assert
    assert code == 0
    text = (root / "docs" / "big-decisions.md").read_text(encoding="utf-8")
    assert re.search(r"(?m)^## D-1 · \d{4}-\d{2}-\d{2} · offen$", text)
    assert re.search(r"(?m)^Thema: UI-Texte$", text)
    [row] = decide_rows(root)
    assert row[1:5] == ["UI-Texte", "gross", "Wortlaut der Fehlermeldung?", "D-1"]
    assert row[6] == "immer fragen: UI-Texte"
