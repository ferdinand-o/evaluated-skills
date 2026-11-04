# spec-stub: zusammenfassung-zeigt-nur-die-eigene-sitzung
"""Stub für Akzeptanzkriterium "Zusammenfassung zeigt nur die eigene Sitzung" aus docs/specs/wip/decide.md.

Given das Protokoll der laufenden Sitzung hat zwei Entscheidungen und eine Annahme
Given ein Protokoll einer früheren Sitzung hat fünf Einträge
When `decide_log.py summary` läuft
Then nennt es genau die drei Einträge der laufenden Sitzung
"""
from conftest import decide_add_small as add_small
from conftest import decide_script

dl = decide_script()


def test_decide_zusammenfassung_zeigt_nur_die_eigene_sitzung(decide_repo, capsys):
    # Arrange
    root, _ = decide_repo
    for n in range(5):
        assert add_small("Alt", f"Frühere Frage {n}?", "x", "gesucht: a — nichts gefunden",
                         "--session", "frueher") == 0
    assert add_small("CLI", "Kurzoption?", "Kurzform -v", "gesucht: cli.py — Treffer: cli.py:3") == 0
    assert add_small("CSV", "Trenner?", "Semikolon", "gesucht: csv.py — Treffer: csv.py:9") == 0
    assert add_small("Konfig", "Dateiname?", "config.toml", "gesucht: docs — nichts gefunden") == 0
    capsys.readouterr()

    # Act
    code = dl.main(["summary"])
    out = capsys.readouterr().out

    # Assert
    assert code == 0
    entries = [line for line in out.splitlines() if line.startswith("- ")]
    assert len(entries) == 3
    assert all(q in out for q in ("Kurzoption?", "Trenner?", "Dateiname?"))
    assert "Frühere Frage" not in out
