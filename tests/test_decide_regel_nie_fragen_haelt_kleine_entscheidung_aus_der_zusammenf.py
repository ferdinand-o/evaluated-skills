# spec-stub: regel-nie-fragen-haelt-kleine-entscheidung-aus-der-zusammenf
"""Stub für Akzeptanzkriterium "Regel nie fragen hält kleine Entscheidung aus der Zusammenfassung" aus docs/specs/wip/decide.md.

Given `.skills/decide/rules.md` enthält `nie fragen: Logging`
Given das Protokoll der Sitzung hat je eine kleine Entscheidung mit Thema `Logging` und `CLI`
When `decide_log.py summary` läuft
Then nennt es nur die Entscheidung mit Thema `CLI`
Then das Protokoll enthält weiter beide
"""
from conftest import decide_add_small as add_small
from conftest import decide_rows as rows
from conftest import decide_script

dl = decide_script()


def test_decide_regel_nie_fragen_haelt_kleine_entscheidung_aus_der_zusammenf(decide_repo, capsys):
    # Arrange
    root, _ = decide_repo
    (root / ".skills" / "decide").mkdir(parents=True)
    (root / ".skills" / "decide" / "rules.md").write_text("nie fragen: Logging\n", encoding="utf-8")
    assert add_small("Logging", "Loglevel für Retries?", "debug",
                     "gesucht: src/net.py — Treffer: src/net.py:30") == 0
    assert add_small("CLI", "Kurzoption für --verbose?", "Kurzform -v",
                     "gesucht: src/cli.py — Treffer: src/cli.py:12") == 0
    capsys.readouterr()

    # Act
    code = dl.main(["summary"])
    out = capsys.readouterr().out

    # Assert
    assert code == 0
    assert "Kurzoption für --verbose?" in out
    assert "Loglevel für Retries?" not in out
    assert [r[1] for r in rows(root)] == ["Logging", "CLI"]
