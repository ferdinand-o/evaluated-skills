# spec-stub: auftrag-uebernimmt-passende-eintraege-und-regeln
"""Stub für Akzeptanzkriterium "Auftrag übernimmt passende Einträge und Regeln" aus docs/specs/wip/decide.md.

Given das Protokoll der Sitzung hat eine Entscheidung mit Thema `CLI` und eine mit Thema `Logging`
Given `.skills/decide/rules.md` enthält `immer fragen: UI-Texte`
When `decide_log.py brief --topic CLI` läuft
Then enthält der Auftrag unter Schon entschieden genau den Eintrag mit Thema `CLI`
Then unter Feste Vorgaben die Regel mit ihrer Datei als Quelle
Then die Felder Frage, Anlass und Wo nachsehen stehen leer zum Ausfüllen
"""
import re

from conftest import decide_add_small, decide_log_file, decide_script


def test_decide_auftrag_uebernimmt_passende_eintraege_und_regeln(decide_repo, capsys):
    # Arrange
    root, _ = decide_repo
    assert decide_add_small("CLI", "Kurzoption für --verbose?", "Kurzform -v",
                            "gesucht: app/cli.py — Treffer: app/cli.py:12") == 0
    assert decide_add_small("Logging", "Format der Logzeilen?", "JSON",
                            "gesucht: app/log.py — Treffer: app/log.py:4") == 0
    rules = root / ".skills" / "decide" / "rules.md"
    rules.parent.mkdir(parents=True)
    rules.write_text("immer fragen: UI-Texte\n", encoding="utf-8")
    capsys.readouterr()

    # Act
    code = decide_script().main(["brief", "--topic", "CLI"])

    # Assert
    out = capsys.readouterr().out
    assert code == 0, out
    path = decide_log_file(root).parent / "brief-1.md"
    assert ".skills/cache/decide/sitzung-1/brief-1.md" in out, out
    lines = path.read_text(encoding="utf-8").splitlines()
    assert re.fullmatch(r"<!-- skill: decide \| schema: 1 \| generated: python decide_log\.py brief --topic CLI -->",
                        lines[0]), lines[0]
    sections, current = {}, None
    for line in lines[1:]:
        if line.startswith("## "):
            current = line[3:]
            sections[current] = []
        elif line.strip():
            sections[current].append(line)
    assert list(sections) == ["Frage", "Anlass", "Feste Vorgaben", "Schon entschieden", "Wo nachsehen", "Rückgabe"]
    [decided] = sections["Schon entschieden"]
    assert "Kurzoption für --verbose?" in decided and "Kurzform -v" in decided, decided
    [rule] = sections["Feste Vorgaben"]
    assert "immer fragen: UI-Texte" in rule and ".skills/decide/rules.md" in rule, rule
    assert sections["Frage"] == sections["Anlass"] == sections["Wo nachsehen"] == []
