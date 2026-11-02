# spec-stub: immer-fragen-geht-vor-nie-fragen
"""Stub für Akzeptanzkriterium "Immer fragen geht vor nie fragen" aus docs/specs/wip/decide.md.

Given `.skills/decide/rules.md` enthält `immer fragen: UI-Texte`
Given `~/.skills/decide/rules.md` enthält `nie fragen: UI-Texte`
When `decide_log.py add` eine kleine Entscheidung mit Thema `UI-Texte` erhält
Then legt es sie als große Frage ab
Then die Ausgabe nennt den Widerspruch mit beiden Dateien
"""
import re

from conftest import decide_add_small


def test_decide_immer_fragen_geht_vor_nie_fragen(decide_repo, capsys):
    # Arrange
    root, home = decide_repo
    for base, line in ((root, "immer fragen: UI-Texte\n"), (home, "nie fragen: UI-Texte\n")):
        rules = base / ".skills" / "decide" / "rules.md"
        rules.parent.mkdir(parents=True)
        rules.write_text(line, encoding="utf-8")

    # Act
    code = decide_add_small("UI-Texte", "Wortlaut der Fehlermeldung?", "B",
                            "gesucht: app/cli.py — Treffer: app/cli.py:12",
                            "--option", "A: kurz", "--option", "B: ausführlich")

    # Assert
    assert code == 0
    text = (root / "docs" / "big-decisions.md").read_text(encoding="utf-8")
    assert re.search(r"(?m)^## D-1 · .* · offen$", text)
    out = capsys.readouterr().out
    [line] = [line for line in out.splitlines() if line.startswith("Widerspruch")]
    assert "(.skills/decide/rules.md)" in line and "(~/.skills/decide/rules.md)" in line
