# spec-stub: zu-langer-oder-wertender-auftrag-wird-gemeldet
"""Stub für Akzeptanzkriterium "Zu langer oder wertender Auftrag wird gemeldet" aus docs/specs/wip/decide.md.

Given ein ausgefüllter Auftrag mit 30 Zeilen, einem Feld `Empfehlung des Hauptagenten` und der Frage „Sollte die CLI besser argparse nutzen?"
When `decide_log.py brief --check` den Auftrag prüft
Then meldet es die Länge über 25 Zeilen, das unzulässige Feld und die Wörter „sollte" und „besser" in der Frage
Then endet mit Exit 1
"""
from conftest import decide_log_file, decide_script


def test_decide_zu_langer_oder_wertender_auftrag_wird_gemeldet(decide_repo, capsys):
    # Arrange
    root, _ = decide_repo
    path = decide_log_file(root).parent / "brief-1.md"
    path.parent.mkdir(parents=True)
    body = ["## Frage", "Sollte die CLI besser argparse nutzen?",
            "## Anlass", *[f"Schritt {i} der laufenden Aufgabe" for i in range(17)],
            "## Feste Vorgaben", "- nur Stdlib (Spec 28)",
            "## Schon entschieden", "—",
            "## Wo nachsehen", "- app/cli.py",
            "## Empfehlung des Hauptagenten", "argparse",
            "## Rückgabe", "Optionen mit Belegen datei:zeile, Folgen, Umkehrbarkeit, Empfehlung."]
    assert len(body) == 30
    path.write_text("<!-- skill: decide | schema: 1 | generated: python decide_log.py brief --topic CLI -->\n"
                    + "\n".join(body) + "\n", encoding="utf-8")

    # Act
    code = decide_script().main(["brief", "--check", str(path)])

    # Assert
    out = capsys.readouterr().out
    assert code == 1, out
    assert "30 Zeilen" in out and "25" in out, out
    assert "„Empfehlung des Hauptagenten“" in out, out
    assert "„sollte“" in out and "„besser“" in out, out
    for word in ("lieber", "empfehle", "ich würde", "offensichtlich"):
        assert f"„{word}“" not in out, out
