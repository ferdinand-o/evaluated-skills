"""Tests für skills/test-first/scripts/tdd_log.py (Spec 24): Zustandsmodell, Log-Format,
Abschnitte. Die Befehle sind kleine Python-Einzeiler, damit kein Testrunner nötig ist."""

import re
import shlex
import sys

import pytest
from conftest import git, load_script

tdd = load_script("skills/test-first/scripts/tdd_log.py")

PY = shlex.quote(sys.executable)
PASS = f"{PY} -c pass"
FAIL = f"{PY} -c \"import sys; sys.exit(1)\""


def make_root(tmp_path, name="repo"):
    root = tmp_path / name
    root.mkdir()
    git(root, "init", "-q")
    return root


def log_text(root):
    return (root / ".skills" / "cache" / "test-first" / "log.md").read_text(encoding="utf-8")


def rows(root):
    """(id, phase) der Zeilen im letzten Abschnitt."""
    section = log_text(root).split("\n## ")[-1]
    return [tuple(c.strip() for c in line.split("|")[1:3])
            for line in section.splitlines()
            if line.startswith("| ") and not line.startswith(("| Test ", "| ---"))]


def run(root, action, test_id, command, capsys=None):
    code = tdd.main([action, "--root", str(root), "--test", test_id, "--", command])
    return code


def test_state_model(tmp_path):
    root = make_root(tmp_path)
    # unbekannt: green und refactor laufen nicht
    assert run(root, "green", "t_a", PASS) == 1
    assert run(root, "refactor", "t_a", PASS) == 1
    assert not (root / ".skills" / "cache" / "test-first" / "log.md").exists() or rows(root) == []

    assert run(root, "red", "t_a", FAIL) == 0           # rot
    assert run(root, "refactor", "t_a", PASS) == 1      # nicht grün: keine Zeile
    assert run(root, "green", "t_a", FAIL) == 1         # noch-rot, bleibt rot
    assert run(root, "green", "t_a", PASS) == 0         # grün
    assert run(root, "green", "t_a", PASS) == 1         # nicht rot: keine Zeile
    assert run(root, "refactor", "t_a", PASS) == 0      # refactor, bleibt grün
    assert run(root, "refactor", "t_a", FAIL) == 1      # refactor-rot → rot
    assert run(root, "green", "t_a", PASS) == 0         # aus rot wieder grün
    assert rows(root) == [("t_a", p) for p in ("red", "noch-rot", "green", "refactor", "refactor-rot", "green")]
    assert "Vollständige Zyklen: 1" in log_text(root)

    # red nach grün beginnt einen neuen Zyklus: bis zum nächsten Grün nicht vollständig
    assert run(root, "red", "t_a", FAIL) == 0
    assert "Vollständige Zyklen: 0" in log_text(root)
    assert run(root, "green", "t_a", PASS) == 0
    assert "Vollständige Zyklen: 1" in log_text(root)


def test_sofort_gruen_never_counts_as_red(tmp_path):
    root = make_root(tmp_path)
    assert run(root, "red", "t_b", PASS) == 1
    assert run(root, "green", "t_b", PASS) == 1
    assert rows(root) == [("t_b", "sofort-grün")]
    assert "Vollständige Zyklen: 0" in log_text(root)
    # sofort grün lässt einen laufenden Zyklus unverändert
    assert run(root, "red", "t_c", FAIL) == 0
    assert run(root, "red", "t_c", PASS) == 1
    assert run(root, "green", "t_c", PASS) == 0
    assert rows(root)[-3:] == [("t_c", "red"), ("t_c", "sofort-grün"), ("t_c", "green")]


def test_unverified_runs(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    assert run(root, "red", "t_d", "kein-solches-programm-xyz --flag") == 1
    assert run(root, "red", "t_d", f"{PY} -c \"import sys; sys.exit(127)\"") == 1
    monkeypatch.setattr(tdd, "TIMEOUT", 0.5)
    assert run(root, "red", "t_d", f"{PY} -c \"import time; time.sleep(5)\"") == 1
    assert rows(root) == [("t_d", "ungeprüft")] * 3
    text = log_text(root)
    assert "kein-solches-programm-xyz fehlt" in text and "Zeitgrenze" in text
    # Zustand unverändert: green läuft nicht
    assert run(root, "green", "t_d", PASS) == 1
    # mitten im Zyklus ändert ungeprüft nichts
    monkeypatch.setattr(tdd, "TIMEOUT", 300)
    assert run(root, "red", "t_d", FAIL) == 0
    assert run(root, "green", "t_d", "kein-solches-programm-xyz") == 1
    assert run(root, "green", "t_d", PASS) == 0


def test_log_format(tmp_path, capsys):
    root = make_root(tmp_path)
    for bad in ("mit leer", "a|b", ""):
        assert run(root, "red", bad, FAIL) == 2
    assert not (root / ".skills" / "cache" / "test-first" / "log.md").exists()

    noisy = f"{PY} -c \"print('\\n'.join('zeile %d a|b Äpfel' % i for i in range(30))); raise SystemExit(1)\""
    assert run(root, "red", "test_äpfel", noisy) == 0
    text = log_text(root)
    assert re.match(r"<!-- skill: test-first \| schema: 1 \| generated: [^>]+ -->\n", text)
    row = next(line for line in text.splitlines() if line.startswith("| test_äpfel |"))
    cells = row.split(" | ")
    assert len(row.split("|")) == 8, row          # sechs Spalten, kein `|` aus der Ausgabe
    assert "a¦b Äpfel" in row
    assert "zeile 29" in row and "zeile 19" not in row and "zeile 20" in row   # letzte zehn Zeilen
    assert cells[1] == "red"
    (root / ".skills" / "cache" / "test-first" / "log.md").read_bytes().decode("utf-8")


def test_start_and_status(tmp_path, capsys):
    root = make_root(tmp_path)
    assert tdd.main(["status", "--root", str(root)]) == 1
    assert "kein Log" in capsys.readouterr().out

    assert run(root, "red", "t_e", FAIL) == 0
    assert run(root, "green", "t_e", PASS) == 0
    assert run(root, "red", "t_f", PASS) == 1
    assert run(root, "red", "t_g", FAIL) == 0
    capsys.readouterr()
    assert tdd.main(["status", "--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert "Vollständige Zyklen: 1" in out
    assert re.search(r"t_e: grün", out) and re.search(r"t_f: sofort-grün", out) and re.search(r"t_g: rot", out)

    assert tdd.main(["start", "--root", str(root), "--note", "zweite Aufgabe"]) == 0
    assert log_text(root).count("\n## Abschnitt ") == 2
    assert run(root, "green", "t_g", PASS) == 1      # Zustand zurückgesetzt
    capsys.readouterr()
    assert tdd.main(["status", "--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert "Vollständige Zyklen: 0" in out and "t_e" not in out
    assert "zweite Aufgabe" in log_text(root)


def test_root_defaults_to_git_toplevel(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    sub = root / "src"
    sub.mkdir()
    monkeypatch.chdir(sub)
    assert tdd.main(["red", "--test", "t_h", "--", FAIL]) == 0
    assert (root / ".skills" / "cache" / "test-first" / "log.md").is_file()


@pytest.mark.parametrize("ignored", [True, False])
def test_first_log_names_unversioned_folder(tmp_path, capsys, ignored):
    root = make_root(tmp_path)
    if ignored:
        (root / ".gitignore").write_text(".skills/cache/\n", encoding="utf-8")
    run(root, "red", "t_i", FAIL)
    out = capsys.readouterr().out
    assert ("nicht in .gitignore" in out) is not ignored
