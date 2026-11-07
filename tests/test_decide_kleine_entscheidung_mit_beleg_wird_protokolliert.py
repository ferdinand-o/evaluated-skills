# spec-stub: kleine-entscheidung-mit-beleg-wird-protokolliert
"""Stub für Akzeptanzkriterium "Kleine Entscheidung mit Beleg wird protokolliert" aus docs/specs/wip/decide.md.

Given eine Sitzung mit gesetzter `CLAUDE_CODE_SESSION_ID`
When `decide_log.py add` eine kleine Entscheidung mit Belegzeile „gesucht: src/parsers — Treffer: src/parsers/csv.py:12" erhält
Then steht in `.skills/cache/decide/<session>/log.md` eine Zeile mit Frage, Thema, Klasse klein, Entscheidung und Beleg
Then die Datei trägt in Zeile 1 die Kopfzeile
"""
import re

from conftest import decide_add_small as add_small
from conftest import decide_log_file as log_file
from conftest import decide_rows as rows


def test_decide_kleine_entscheidung_mit_beleg_wird_protokolliert(decide_repo, capsys):
    # Arrange
    root, _ = decide_repo

    # Act
    code = add_small("CSV-Parser", "Welcher Trenner gilt ohne Angabe?", "Semikolon wie im bestehenden Parser",
                     "gesucht: src/parsers — Treffer: src/parsers/csv.py:12")
    out = capsys.readouterr()

    # Assert
    assert code == 0, out
    lines = log_file(root).read_text(encoding="utf-8").splitlines()
    assert re.fullmatch(r"<!-- skill: decide \| schema: 1 \| generated: .+ -->", lines[0])
    assert "| zeit | thema | klasse | frage | entscheidung | beleg | regel |" in lines
    assert len(rows(root)) == 1
    zeit, *rest = rows(root)[0]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", zeit)
    assert rest == ["CSV-Parser", "klein", "Welcher Trenner gilt ohne Angabe?",
                    "Semikolon wie im bestehenden Parser",
                    "gesucht: src/parsers — Treffer: src/parsers/csv.py:12", "—"]
