import json
import stat
import sys

from conftest import load_script

rc = load_script("skills/exercise-forge/scripts/run_coding.py")

ADD_TESTS = "from solution import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"

CODING_EXERCISE = {
    "id": "code-01",
    "type": "coding",
    "stem": "Schreibe eine Funktion add(a, b), die die Summe liefert.",
    "model_solution": "def add(a, b):\n    return a + b\n",
    "test_suite": ADD_TESTS,
}


def fake_python_without_pytest(tmp_path):
    script = tmp_path / "fake-python-no-pytest"
    script.write_text("#!/bin/bash\necho 'No module named pytest' >&2\nexit 1\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


# --- pytest_available ---------------------------------------------------------

def test_pytest_available_true_with_real_interpreter():
    assert rc.pytest_available(python=sys.executable) is True


def test_pytest_available_false_without_pytest_module(tmp_path):
    assert rc.pytest_available(python=fake_python_without_pytest(tmp_path)) is False


# --- run_pytest_against ---------------------------------------------------------

def test_run_pytest_against_passing_solution(tmp_path):
    result = rc.run_pytest_against("def add(a, b):\n    return a + b\n", ADD_TESTS, tmp_path)
    assert result["passed"] is True


def test_run_pytest_against_failing_solution(tmp_path):
    result = rc.run_pytest_against("def add(a, b):\n    return a - b\n", ADD_TESTS, tmp_path)
    assert result["passed"] is False
    assert result["detail"]


# --- verify_coding: die Wahrheitstabelle aus Spec 13 ----------------------------

def test_verify_coding_both_pass_is_verified():
    result = rc.verify_coding(CODING_EXERCISE, "def add(a, b):\n    return a + b\n")
    assert result["status"] == "verified"
    assert result["method"] == "blind_solve_coding"


def test_verify_coding_model_fails_is_unverified():
    broken = dict(CODING_EXERCISE, model_solution="def add(a, b):\n    return a - b\n")
    result = rc.verify_coding(broken, "def add(a, b):\n    return a + b\n")
    assert result["status"] == "unverified"
    assert "Musterlösung" in result["detail"]


def test_verify_coding_overspecified_tests_flags_suspicious():
    """Test prüft eine Implementierungsdetail (Zeilenzahl) statt nur Verhalten —
    eine mathematisch korrekte, aber anders geschriebene Blind-Lösung fällt durch."""
    overspecified = dict(CODING_EXERCISE, test_suite=(
        "import inspect\n"
        "from solution import add\n\n\n"
        "def test_add_correct():\n"
        "    assert add(2, 3) == 5\n\n\n"
        "def test_add_is_two_lines():\n"
        "    assert len(inspect.getsource(add).strip().splitlines()) == 2\n"
    ))
    blind = "def add(a, b):\n    total = a + b\n    return total\n"  # korrekt, aber 3 Zeilen
    result = rc.verify_coding(overspecified, blind)
    assert result["status"] == "suspicious"
    assert "überspezifiziert" in result["detail"]


def test_verify_coding_without_blind_solution_is_unverified():
    """Ohne Blind-Lösung ist das Blind-Gate unvollständig — nie 'verified'."""
    result = rc.verify_coding(CODING_EXERCISE, None)
    assert result["status"] == "unverified"
    assert "Blind-Lösung" in result["detail"]


def test_verify_coding_pytest_unavailable_is_unverified(tmp_path):
    result = rc.verify_coding(CODING_EXERCISE, "def add(a, b):\n    return a + b\n",
                               python=fake_python_without_pytest(tmp_path))
    assert result["status"] == "unverified"
    assert "pytest" in result["detail"]
    assert result["method"] == "blind_solve_coding"


# --- main() CLI -------------------------------------------------------------------

def test_main_prints_json_result_with_verification_key(tmp_path, capsys):
    exercises_path = tmp_path / "topic.exercises.json"
    exercises_path.write_text(json.dumps({"exercises": [CODING_EXERCISE]}), encoding="utf-8")
    blind_path = tmp_path / "blind.py"
    blind_path.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    rc_code = rc.main(["--exercises", str(exercises_path), "--id", "code-01", "--blind-file", str(blind_path)])
    assert rc_code == 0
    out = capsys.readouterr().out
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload["verification"]["status"] == "verified"


def test_main_with_update_writes_back_to_file(tmp_path):
    exercises_path = tmp_path / "topic.exercises.json"
    exercises_path.write_text(json.dumps({"exercises": [CODING_EXERCISE]}), encoding="utf-8")
    blind_path = tmp_path / "blind.py"
    blind_path.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    rc.main(["--exercises", str(exercises_path), "--id", "code-01", "--blind-file", str(blind_path), "--update"])

    written = json.loads(exercises_path.read_text(encoding="utf-8"))
    assert written["exercises"][0]["verification"]["status"] == "verified"


def test_main_unknown_id_is_reported(tmp_path, capsys):
    exercises_path = tmp_path / "topic.exercises.json"
    exercises_path.write_text(json.dumps({"exercises": [CODING_EXERCISE]}), encoding="utf-8")
    rc_code = rc.main(["--exercises", str(exercises_path), "--id", "does-not-exist"])
    assert rc_code != 0
    assert "nicht gefunden" in capsys.readouterr().err
