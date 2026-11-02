# spec-stub: grosse-entscheidung-wird-mit-schluessel-abgelegt
"""Stub für Akzeptanzkriterium "Große Entscheidung wird mit Schlüssel abgelegt" aus docs/specs/wip/decide.md.

Given ein Repo ohne `docs/big-decisions.md`
When `decide_log.py add` eine große Entscheidung mit Schlüssel `dependency:pyproject.toml`, drei Optionen und einer Empfehlung erhält
Then entsteht `docs/big-decisions.md` mit Kopfzeile und einem Block `D-1` mit Status offen und dem Schlüssel
Then die Ausgabe meldet „angelegt: docs/big-decisions.md"
"""
import re
from datetime import date

from conftest import decide_script


def test_decide_grosse_entscheidung_wird_mit_schluessel_abgelegt(decide_repo, capsys):
    # Arrange
    root, _ = decide_repo
    dl = decide_script()
    ledger = root / "docs" / "big-decisions.md"
    assert not ledger.exists()

    # Act
    code = dl.main(["add", "--class", "gross", "--topic", "Abhängigkeiten",
                    "--question", "Datumsangaben mit einer neuen Abhängigkeit parsen oder mit der Stdlib?",
                    "--key", "dependency:pyproject.toml",
                    "--option", "A: python-dateutil aufnehmen — Folgen: neue Abhängigkeit — Umkehrbarkeit: per Revert",
                    "--option", "B: datetime.strptime mit drei Formaten — Folgen: drei Formate — Umkehrbarkeit: billig",
                    "--option", "C: Eingabe auf ISO 8601 festlegen — Folgen: Aufrufer ändern — Umkehrbarkeit: teuer",
                    "--recommendation", "B, weil die Stdlib reicht"])

    # Assert
    assert code == 0
    text = ledger.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "<!-- skill: decide | schema: 1 | generated: python decide_log.py add -->"
    assert re.search(rf"(?m)^## D-1 · {date.today().isoformat()} · offen$", text)
    assert "\nSchlüssel: dependency:pyproject.toml\n" in text
    assert len(re.findall(r"(?m)^- [ABC]: ", text)) == 3
    assert "\nEmpfehlung: B, weil die Stdlib reicht\n" in text
    assert "angelegt: docs/big-decisions.md" in capsys.readouterr().out
