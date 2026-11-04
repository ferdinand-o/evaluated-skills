# spec-stub: teure-aenderung-ohne-freigabe-wird-gemeldet
"""Stub für Akzeptanzkriterium "Teure Änderung ohne Freigabe wird gemeldet" aus docs/specs/wip/decide.md.

Given ein Diff, der eine neue Abhängigkeit in `pyproject.toml` und eine neue Datei unter `migrations/` enthält
Given `docs/big-decisions.md` führt `dependency:pyproject.toml` mit Status offen und `migration:migrations/` gar nicht
When `decide_log.py check --range <bereich>` läuft
Then meldet es beide Stellen mit Datei, Kategorie und Grund aus `reversibility.md`
Then die Ausgabe nennt die ungeprüften Kategorien
"""
from conftest import DECIDE_TAIL as TAIL
from conftest import decide_commit as commit
from conftest import decide_script, git

dl = decide_script()


def test_decide_teure_aenderung_ohne_freigabe_wird_gemeldet(decide_repo, monkeypatch, capsys):
    # Arrange
    root, _ = decide_repo
    (root / "pyproject.toml").write_text('[project]\nname = "app"\ndependencies = []\n', encoding="utf-8")
    (root / "migrations").mkdir()
    (root / "migrations" / "0001_initial.py").write_text("def up(): pass\n", encoding="utf-8")
    assert dl.main(["add", "--class", "gross", "--topic", "Abhängigkeiten", "--question", "Datumsangaben parsen?",
                    "--key", "dependency:pyproject.toml", "--option", "A: python-dateutil",
                    "--option", "B: strptime", "--recommendation", "B, weil Stdlib"]) == 0
    commit(root, "Basis")
    base = git(root, "rev-parse", "HEAD").strip()
    (root / "pyproject.toml").write_text('[project]\nname = "app"\ndependencies = ["python-dateutil"]\n',
                                         encoding="utf-8")
    (root / "migrations" / "0002_drop_legacy.py").write_text("def up(): pass\n", encoding="utf-8")
    capsys.readouterr()
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")            # check braucht keine Sitzung

    # Act
    code = dl.main(["check", "--range", base])
    out = capsys.readouterr().out

    # Assert
    categories, problem = dl.load_categories(dl.REFERENCE)
    assert problem is None
    assert code == 1, out
    lines = out.splitlines()
    dep = next(line for line in lines if line.startswith("- pyproject.toml "))
    mig = next(line for line in lines if line.startswith("- migrations/0002_drop_legacy.py "))
    assert "dependency" in dep and categories["dependency"].meaning in dep and "D-1" in dep and "offen" in dep
    assert "migration" in mig and categories["migration"].meaning in mig and "kein Eintrag" in mig
    assert "0001_initial.py" not in out                      # unverändert: keine Stelle
    # die offene Frage D-1 steht nach den Stellen und vor der Schlusszeile (wie `open`); ohne Sitzung
    # keine Zusammenfassung
    pending = lines.index("Offene große Fragen in docs/big-decisions.md: 1")
    assert max(lines.index(dep), lines.index(mig)) < pending < len(lines) - 1, out
    assert "Einträge der Sitzung" not in out
    assert lines[-1] == TAIL
