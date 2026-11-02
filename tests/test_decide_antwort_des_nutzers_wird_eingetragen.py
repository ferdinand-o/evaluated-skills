# spec-stub: antwort-des-nutzers-wird-eingetragen
"""Stub für Akzeptanzkriterium "Antwort des Nutzers wird eingetragen" aus docs/specs/wip/decide.md.

Given `docs/big-decisions.md` hat einen Block `D-1` mit Status offen
When `decide_log.py resolve D-1 --answer "Option B"` läuft
Then steht `D-1` auf freigegeben mit Antwort „Option B"
Then der Block bleibt in der Datei stehen
"""
import re

from conftest import decide_script


def test_decide_antwort_des_nutzers_wird_eingetragen(decide_repo):
    # Arrange
    root, _ = decide_repo
    dl = decide_script()
    assert dl.main(["add", "--class", "gross", "--topic", "Abhängigkeiten", "--question", "Datum parsen?",
                    "--key", "dependency:pyproject.toml", "--option", "A: dateutil", "--option", "B: strptime",
                    "--recommendation", "B"]) == 0
    ledger = root / "docs" / "big-decisions.md"
    assert re.search(r"(?m)^## D-1 · .* · offen$", ledger.read_text(encoding="utf-8"))

    # Act
    code = dl.main(["resolve", "D-1", "--answer", "Option B"])

    # Assert
    assert code == 0
    text = ledger.read_text(encoding="utf-8")
    assert re.search(r"(?m)^## D-1 · \d{4}-\d{2}-\d{2} · freigegeben$", text)
    assert "\nAntwort: Option B\n" in text
    assert "\nQuelle der Antwort: Nutzer in Sitzung\n" in text
    # der Block bleibt stehen
    assert len(re.findall(r"(?m)^## D-", text)) == 1
    assert "\nFrage: Datum parsen?\n" in text and "\n- A: dateutil\n" in text
