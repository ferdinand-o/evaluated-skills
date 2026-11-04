# spec-stub: offene-grosse-fragen-ueberleben-die-sitzung
"""Stub für Akzeptanzkriterium "Offene große Fragen überleben die Sitzung" aus docs/specs/wip/decide.md.

Given `docs/big-decisions.md` hat einen offenen Block aus einer früheren Sitzung und einen freigegebenen
When `decide_log.py open` in einer neuen Sitzung läuft
Then nennt es genau den offenen Block mit Datum, Optionen und Empfehlung
"""
from conftest import decide_script


def test_decide_offene_grosse_fragen_ueberleben_die_sitzung(decide_repo, capsys, monkeypatch):
    # Arrange
    dl = decide_script()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "fruehere-sitzung")
    assert dl.main(["add", "--class", "gross", "--topic", "Abhängigkeiten", "--question", "Datum parsen?",
                    "--key", "dependency:pyproject.toml", "--option", "A: dateutil aufnehmen",
                    "--option", "B: strptime", "--recommendation", "B, weil Stdlib"]) == 0
    assert dl.main(["add", "--class", "gross", "--topic", "Migrationen", "--question", "Spalte weg?",
                    "--key", "migration:migrations/", "--approved-by-request", "lösch die Spalte"]) == 0
    root, _ = decide_repo
    ledger = root / "docs" / "big-decisions.md"
    text = ledger.read_text(encoding="utf-8")
    date = text.split("## D-1 · ", 1)[1].split(" · ", 1)[0]
    capsys.readouterr()

    # Act
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "neue-sitzung")
    code = dl.main(["open"])

    # Assert
    assert code == 0
    out = capsys.readouterr().out
    assert "D-1" in out and date in out
    assert "A: dateutil aufnehmen" in out and "B: strptime" in out
    assert "Empfehlung: B, weil Stdlib" in out
    assert "D-2" not in out and "Spalte weg?" not in out
    assert ledger.read_text(encoding="utf-8") == text
