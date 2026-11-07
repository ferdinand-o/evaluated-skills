# spec-stub: zusammenfassung-kuerzt-ab-zehn-eintraegen
"""Stub für Akzeptanzkriterium "Zusammenfassung kürzt ab zehn Einträgen" aus docs/specs/wip/decide.md.

Given das Protokoll der laufenden Sitzung hat zwölf Einträge
When `decide_log.py summary` läuft
Then nennt es die zehn jüngsten und den Pfad des Protokolls
"""
from conftest import DECIDE_SESSION as SESSION
from conftest import decide_add_small as add_small
from conftest import decide_rows as rows
from conftest import decide_script

dl = decide_script()


def test_decide_zusammenfassung_kuerzt_ab_zehn_eintraegen(decide_repo, capsys):
    # Arrange
    root, _ = decide_repo
    for n in range(1, 13):
        assert add_small("CLI", f"Frage {n:02d}?", "ja", f"gesucht: cli.py — Treffer: cli.py:{n}") == 0
    capsys.readouterr()

    # Act
    code = dl.main(["summary"])
    out = capsys.readouterr().out

    # Assert
    assert code == 0
    entries = [line for line in out.splitlines() if line.startswith("- ")]
    assert len(entries) == 10
    assert [f"Frage {n:02d}?" in out for n in range(1, 13)] == [False] * 2 + [True] * 10
    assert f".skills/cache/decide/{SESSION}/log.md" in out
    assert len(rows(root)) == 12
