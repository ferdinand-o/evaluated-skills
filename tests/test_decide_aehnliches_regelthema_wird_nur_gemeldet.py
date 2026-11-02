# spec-stub: aehnliches-regelthema-wird-nur-gemeldet
"""Stub für Akzeptanzkriterium "Ähnliches Regelthema wird nur gemeldet" aus docs/specs/wip/decide.md.

Given `.skills/decide/rules.md` enthält `immer fragen: UI-Texte`
When `decide_log.py add` eine kleine Entscheidung mit Thema `UI-Text` erhält
Then bleibt sie klein
Then die Ausgabe nennt die Regel `immer fragen: UI-Texte` als Hinweis
"""
from conftest import decide_add_small as add_small
from conftest import decide_rows as rows


def test_decide_aehnliches_regelthema_wird_nur_gemeldet(decide_repo, capsys):
    # Arrange
    root, _ = decide_repo
    (root / ".skills" / "decide").mkdir(parents=True)
    (root / ".skills" / "decide" / "rules.md").write_text("immer fragen: UI-Texte\n", encoding="utf-8")

    # Act
    code = add_small("UI-Text", "Fehlermeldung beim Import?", "Datei nicht lesbar: <pfad>",
                     "gesucht: src/messages.py — Treffer: src/messages.py:8")
    out = capsys.readouterr().out

    # Assert
    assert code == 0
    [row] = rows(root)
    assert row[1:3] == ["UI-Text", "klein"]
    assert row[6] == "—"
    assert "Hinweis" in out
    assert "immer fragen: UI-Texte" in out
    assert not (root / "docs" / "big-decisions.md").exists()
