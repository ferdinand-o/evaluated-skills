# spec-stub: freigegebene-teure-aenderung-wird-nicht-gemeldet
"""Stub für Akzeptanzkriterium "Freigegebene teure Änderung wird nicht gemeldet" aus docs/specs/wip/decide.md.

Given derselbe Diff
Given `docs/big-decisions.md` führt beide Schlüssel mit Status freigegeben
When `decide_log.py check --range <bereich>` läuft
Then meldet es keine Stelle
Then die Ausgabe nennt weiter die ungeprüften Kategorien
"""
from conftest import decide_script, git

dl = decide_script()
TAIL = "ungeprüft: data-delete, unsaved-work, push, external, cost; teilweise: api, migration"


def commit(root, message):
    git(root, "add", "-A")
    git(root, "-c", "user.email=t@example.org", "-c", "user.name=t", "commit", "-q", "-m", message)


def approve(key, quote):
    assert dl.main(["add", "--class", "gross", "--topic", "Teuer", "--question", f"{key}?", "--key", key,
                    "--approved-by-request", quote]) == 0


def test_decide_freigegebene_teure_aenderung_wird_nicht_gemeldet(decide_repo, monkeypatch, capsys):
    # Arrange
    root, _ = decide_repo
    (root / "pyproject.toml").write_text('[project]\nname = "app"\ndependencies = []\n', encoding="utf-8")
    (root / "migrations").mkdir()
    (root / "migrations" / "0001_initial.py").write_text("def up(): pass\n", encoding="utf-8")
    approve("dependency:pyproject.toml", "nimm python-dateutil auf")
    approve("migration:migrations/", "leg die Migration an")
    commit(root, "Basis")
    base = git(root, "rev-parse", "HEAD").strip()
    (root / "pyproject.toml").write_text('[project]\nname = "app"\ndependencies = ["python-dateutil"]\n',
                                         encoding="utf-8")
    (root / "migrations" / "0002_drop_legacy.py").write_text("def up(): pass\n", encoding="utf-8")
    capsys.readouterr()
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")

    # Act
    code = dl.main(["check", "--range", base])
    out = capsys.readouterr().out

    # Assert
    assert code == 0, out
    assert not [line for line in out.splitlines() if line.startswith("- ")], out
    assert "Keine Stelle ohne Freigabe" in out
    assert out.splitlines()[-1] == TAIL
