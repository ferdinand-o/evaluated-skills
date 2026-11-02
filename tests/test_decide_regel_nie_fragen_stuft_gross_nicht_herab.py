# spec-stub: regel-nie-fragen-stuft-gross-nicht-herab
"""Stub für Akzeptanzkriterium "Regel nie fragen stuft groß nicht herab" aus docs/specs/wip/decide.md.

Given `~/.skills/decide/rules.md` enthält `nie fragen: Migrationen`
When `decide_log.py add` eine große Entscheidung mit Thema `Migrationen` erhält
Then bleibt sie groß und offen
Then die Ausgabe meldet, dass die Regel auf große Entscheidungen nicht wirkt
"""
import re

from conftest import decide_script


def test_decide_regel_nie_fragen_stuft_gross_nicht_herab(decide_repo, capsys):
    # Arrange
    root, home = decide_repo
    rules = home / ".skills" / "decide" / "rules.md"
    rules.parent.mkdir(parents=True)
    rules.write_text("nie fragen: Migrationen\n", encoding="utf-8")
    dl = decide_script()

    # Act
    code = dl.main(["add", "--class", "gross", "--topic", "migrationen", "--question", "Spalte legacy_id entfernen?",
                    "--key", "migration:migrations/", "--option", "A: entfernen", "--option", "B: behalten",
                    "--recommendation", "B"])

    # Assert
    assert code == 0
    text = (root / "docs" / "big-decisions.md").read_text(encoding="utf-8")
    assert re.search(r"(?m)^## D-1 · .* · offen$", text)
    assert re.search(r"(?m)^Thema: Migrationen$", text)
    out = capsys.readouterr().out
    assert "nie fragen: Migrationen" in out and "wirkt nicht auf große Entscheidungen" in out
