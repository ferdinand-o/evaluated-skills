import json
import stat
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT, load_script

vb = load_script("skills/exercise-forge/scripts/verify_blind.py")
RUN_CODING_PATH = REPO_ROOT / "skills" / "exercise-forge" / "scripts" / "run_coding.py"


def fake_cli(tmp_path: Path, body: str, name: str = "fake-claude") -> str:
    script = tmp_path / name
    script.write_text("#!/bin/bash\n" + body, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def fake_cli_sequence(tmp_path: Path, *responses: str, name: str = "fake-claude-seq") -> str:
    """CLI, das bei jedem Aufruf die nächste Antwort aus `responses` liefert."""
    counter = tmp_path / f"{name}.count"
    counter.write_text("0", encoding="utf-8")
    lines = ["#!/bin/bash", f'N=$(cat "{counter}")', f'echo $((N+1)) > "{counter}"', "case $N in"]
    for i, resp in enumerate(responses):
        resp_file = tmp_path / f"{name}.resp{i}.txt"
        resp_file.write_text(resp, encoding="utf-8")
        lines.append(f'  {i}) cat "{resp_file}" ;;')
    lines.append('  *) echo "no more responses" >&2; exit 1 ;;')
    lines.append("esac")
    script = tmp_path / name
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


# --- resolve_exercises_path ---------------------------------------------

def test_resolve_uses_home_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(vb.Path, "home", staticmethod(lambda: tmp_path / "home"))
    path = vb.resolve_exercises_path("python-basics", repo=tmp_path / "repo")
    assert path == tmp_path / "home" / ".skills" / "verified-research" / "research" / "python-basics.exercises.json"


def test_resolve_prefers_project_override_when_dir_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(vb.Path, "home", staticmethod(lambda: tmp_path / "home"))
    repo = tmp_path / "repo"
    project_dir = repo / ".skills" / "verified-research" / "research"
    project_dir.mkdir(parents=True)
    path = vb.resolve_exercises_path("python-basics", repo=repo)
    assert path == project_dir / "python-basics.exercises.json"


# --- MC protocol ----------------------------------------------------------

MC_EXERCISE = {
    "id": "mc-01",
    "type": "multiple_choice",
    "stem": "Was liefert len([1,2,3])?",
    "options": [
        {"text": "2", "correct": False},
        {"text": "3", "correct": True},
        {"text": "4", "correct": False},
    ],
}


def test_verify_mc_correct_choice_is_verified(tmp_path):
    cli = fake_cli(tmp_path, 'echo "Begruendung ...\\nANTWORT: B"\n')
    result = vb.verify_mc(MC_EXERCISE, tmp_path, cli=cli)
    assert result["status"] == "verified"
    assert result["method"] == "blind_solve_mc"
    assert result["checked_at"]
    assert result["protocol"] == {"chosen_index": 1}  # Option B, "3", correct: true


def test_verify_mc_distractor_choice_is_suspicious(tmp_path):
    cli = fake_cli(tmp_path, 'echo "Weil man beim Zaehlen bei 0 anfaengt.\\nANTWORT: A"\n')
    result = vb.verify_mc(MC_EXERCISE, tmp_path, cli=cli)
    assert result["status"] == "suspicious"
    assert "A" in result["detail"] or "2" in result["detail"]
    assert result["protocol"] == {"chosen_index": 0}  # Option A, "2", correct: false


def test_verify_mc_unparsable_answer_is_unverified(tmp_path):
    cli = fake_cli(tmp_path, 'echo "Ich bin mir nicht sicher."\n')
    result = vb.verify_mc(MC_EXERCISE, tmp_path, cli=cli)
    assert result["status"] == "unverified"
    assert "parsebar" in result["detail"]


def test_verify_mc_missing_cli_is_unverified_not_raised(tmp_path):
    result = vb.verify_mc(MC_EXERCISE, tmp_path, cli=str(tmp_path / "does-not-exist"))
    assert result["status"] == "unverified"
    assert "erreichbar" in result["detail"]


def test_parse_mc_letter_takes_last_match():
    text = "Ich dachte erst A, aber eigentlich...\nANTWORT: B"
    assert vb.parse_mc_letter(text) == "B"


def test_parse_mc_letter_none_without_marker():
    assert vb.parse_mc_letter("keine Ahnung") is None


# --- Open question protocol ------------------------------------------------

OPEN_EXERCISE = {
    "id": "open-01",
    "type": "open_question",
    "stem": "Was ist der Unterschied zwischen Liste und Tupel in Python?",
    "criteria": ["Nennt Mutability als Unterschied", "Nennt mindestens einen Anwendungsfall"],
}


def test_verify_open_all_criteria_met_is_verified(tmp_path):
    grading = json.dumps({"answer_is_plausible": True, "criteria_met": [True, True], "why": "passt"})
    cli = fake_cli_sequence(tmp_path, "Listen sind veraenderbar, Tupel nicht. Tupel fuer Koordinaten.", grading)
    result = vb.verify_open(OPEN_EXERCISE, tmp_path, cli=cli)
    assert result["status"] == "verified"
    assert result["method"] == "blind_solve_open"
    assert result["protocol"] == {"criteria_met": [True, True], "answer_is_plausible": True}


def test_verify_open_unmet_criterion_on_plausible_answer_is_suspicious(tmp_path):
    grading = json.dumps({"answer_is_plausible": True, "criteria_met": [True, False], "why": "kein Anwendungsfall genannt"})
    cli = fake_cli_sequence(tmp_path, "Listen sind veraenderbar, Tupel nicht.", grading)
    result = vb.verify_open(OPEN_EXERCISE, tmp_path, cli=cli)
    assert result["status"] == "suspicious"
    assert "eng" in result["detail"]
    assert result["protocol"] == {"criteria_met": [True, False], "answer_is_plausible": True}


def test_verify_open_implausible_answer_is_unverified(tmp_path):
    grading = json.dumps({"answer_is_plausible": False, "criteria_met": [False, False], "why": "unverstaendlich"})
    cli = fake_cli_sequence(tmp_path, "asdf qwer", grading)
    result = vb.verify_open(OPEN_EXERCISE, tmp_path, cli=cli)
    assert result["status"] == "unverified"
    assert "plausibel" in result["detail"]


def test_verify_open_unparsable_grading_is_unverified(tmp_path):
    cli = fake_cli_sequence(tmp_path, "Eine Antwort.", "kein JSON hier")
    result = vb.verify_open(OPEN_EXERCISE, tmp_path, cli=cli)
    assert result["status"] == "unverified"
    assert "parsebar" in result["detail"]


def test_verify_open_empty_criteria_is_unverified_not_verified(tmp_path):
    """Regression D2: all([]) ist True in Python — ohne Vorabprüfung würde eine
    Aufgabe ohne ein einziges Kriterium den (leeren) Abgleich 'bestehen' und
    als 'verified' gelten, obwohl nichts geprüft wurde. Kein CLI-Aufruf sollte
    dafür nötig sein — ein fehlendes CLI würde sonst fälschlich 'nicht
    erreichbar' statt der eigentlichen Ursache melden."""
    empty_criteria = dict(OPEN_EXERCISE, criteria=[])
    result = vb.verify_open(empty_criteria, tmp_path, cli=str(tmp_path / "does-not-exist"))
    assert result["status"] == "unverified"
    assert "leer" in result["detail"]


def test_verify_open_missing_criteria_field_is_unverified():
    without_criteria = {"id": "open-02", "type": "open_question", "stem": "Frage ohne Kriterien?"}
    result = vb.verify_open(without_criteria, Path("."), cli="does-not-matter")
    assert result["status"] == "unverified"
    assert "leer" in result["detail"]


# --- Flashcard protocol -----------------------------------------------------

CARD_EXERCISE = {
    "id": "card-01",
    "type": "flashcard",
    "front": "Hauptstadt von Frankreich?",
    "back": "Paris",
}


def test_verify_flashcard_matching_answer_is_verified(tmp_path):
    grading = json.dumps({"matches": True, "why": "trifft zu"})
    cli = fake_cli_sequence(tmp_path, "Paris", grading)
    result = vb.verify_flashcard(CARD_EXERCISE, tmp_path, cli=cli)
    assert result["status"] == "verified"
    assert result["method"] == "blind_check_flashcard"
    assert result["protocol"] == {"matches": True}


def test_verify_flashcard_diverging_answer_is_suspicious(tmp_path):
    grading = json.dumps({"matches": False, "why": "Frage koennte auch Bevoelkerungsfrage sein"})
    cli = fake_cli_sequence(tmp_path, "67 Millionen", grading)
    result = vb.verify_flashcard(CARD_EXERCISE, tmp_path, cli=cli)
    assert result["status"] == "suspicious"
    assert "mehrdeutig" in result["detail"]
    assert result["protocol"] == {"matches": False}


# --- verify_one dispatch -----------------------------------------------------

def test_verify_one_dispatches_by_type(tmp_path):
    cli = fake_cli(tmp_path, 'echo "ANTWORT: B"\n')
    result = vb.verify_one(MC_EXERCISE, tmp_path, cli=cli)
    assert result["method"] == "blind_solve_mc"


def test_verify_one_unknown_type_is_unverified(tmp_path):
    result = vb.verify_one({"id": "x", "type": "essay"}, tmp_path, cli="claude")
    assert result["status"] == "unverified"
    assert result["method"] == "not_run"


# --- load/save + main --------------------------------------------------------

def test_load_and_save_roundtrip(tmp_path):
    path = tmp_path / "topic.exercises.json"
    data = {"_meta": {"skill": "exercise-forge"}, "topic": "topic", "exercises": [MC_EXERCISE]}
    vb.save_exercises(path, data)
    loaded = vb.load_exercises(path)
    assert loaded["topic"] == "topic"


def test_main_with_id_updates_only_that_exercise(tmp_path, monkeypatch):
    other = dict(CARD_EXERCISE, id="card-02", verification={"status": "unverified", "method": "not_run", "detail": "x", "checked_at": None})
    target = dict(MC_EXERCISE, verification={"status": "unverified", "method": "not_run", "detail": "x", "checked_at": None})
    path = tmp_path / "topic.exercises.json"
    vb.save_exercises(path, {"topic": "topic", "exercises": [target, other]})

    cli = fake_cli(tmp_path, 'echo "ANTWORT: B"\n')
    rc = vb.main(["--exercises", str(path), "--id", "mc-01", "--cli", cli])
    assert rc == 0

    written = vb.load_exercises(path)
    by_id = {e["id"]: e for e in written["exercises"]}
    assert by_id["mc-01"]["verification"]["status"] == "verified"
    assert by_id["card-02"]["verification"]["status"] == "unverified"  # unangetastet


def test_main_with_all_skips_already_verified(tmp_path):
    verified = dict(CARD_EXERCISE, id="card-01", verification={"status": "verified", "method": "blind_check_flashcard", "detail": "ok", "checked_at": "2026-01-01T00:00:00Z"})
    unverified = dict(MC_EXERCISE, verification={"status": "unverified", "method": "not_run", "detail": "x", "checked_at": None})
    path = tmp_path / "topic.exercises.json"
    vb.save_exercises(path, {"topic": "topic", "exercises": [verified, unverified]})

    cli = fake_cli(tmp_path, 'echo "ANTWORT: B"\n')
    rc = vb.main(["--exercises", str(path), "--all", "--cli", cli])
    assert rc == 0

    written = vb.load_exercises(path)
    by_id = {e["id"]: e for e in written["exercises"]}
    assert by_id["mc-01"]["verification"]["status"] == "verified"
    assert by_id["card-01"]["verification"]["checked_at"] == "2026-01-01T00:00:00Z"  # unangetastet


def test_main_missing_exercises_file_is_reported(tmp_path, capsys):
    rc = vb.main(["--exercises", str(tmp_path / "nope.json"), "--id", "x"])
    assert rc != 0
    assert "nicht gefunden" in capsys.readouterr().err


def test_main_all_survives_one_malformed_exercise_and_keeps_the_rest(tmp_path):
    """Regression L2: eine MC-Option ohne 'text' wirft in verify_mc ein
    KeyError. Ohne Fang bricht main() vor save_exercises() ab und die bereits
    berechneten Urteile für die anderen Aufgaben im selben Batch gehen
    verloren. Der Batch muss die malformte Aufgabe stattdessen benannt als
    unverified markieren und mit den übrigen weiterlaufen."""
    malformed = {
        "id": "mc-broken", "type": "multiple_choice", "stem": "Kaputte Optionen?",
        "options": [{"correct": True}, {"correct": False}],  # kein 'text'
        "verification": {"status": "unverified", "method": "not_run", "detail": "x", "checked_at": None},
    }
    healthy = dict(MC_EXERCISE, verification={"status": "unverified", "method": "not_run", "detail": "x", "checked_at": None})
    path = tmp_path / "topic.exercises.json"
    vb.save_exercises(path, {"topic": "topic", "exercises": [malformed, healthy]})

    cli = fake_cli(tmp_path, 'echo "ANTWORT: B"\n')
    rc = vb.main(["--exercises", str(path), "--all", "--cli", cli])
    assert rc == 0

    written = vb.load_exercises(path)
    by_id = {e["id"]: e for e in written["exercises"]}
    assert by_id["mc-broken"]["verification"]["status"] == "unverified"
    assert "KeyError" in by_id["mc-broken"]["verification"]["detail"] or "text" in by_id["mc-broken"]["verification"]["detail"]
    assert by_id["mc-01"]["verification"]["status"] == "verified"  # nicht mitgerissen


def test_main_saves_incrementally_not_only_at_the_end(tmp_path, monkeypatch):
    """Ein Absturz mitten im Batch darf bereits berechnete Urteile nicht
    verwerfen — save_exercises() muss nach jeder Aufgabe laufen, nicht erst am
    Schluss."""
    save_calls = []
    original_save = vb.save_exercises

    def counting_save(path, data):
        save_calls.append(len(data["exercises"]))
        original_save(path, data)

    monkeypatch.setattr(vb, "save_exercises", counting_save)

    ex1 = dict(MC_EXERCISE, id="mc-a", verification={"status": "unverified", "method": "not_run", "detail": "x", "checked_at": None})
    ex2 = dict(MC_EXERCISE, id="mc-b", verification={"status": "unverified", "method": "not_run", "detail": "x", "checked_at": None})
    path = tmp_path / "topic.exercises.json"
    vb.save_exercises(path, {"topic": "topic", "exercises": [ex1, ex2]})
    save_calls.clear()

    cli = fake_cli(tmp_path, 'echo "ANTWORT: B"\n')
    vb.main(["--exercises", str(path), "--all", "--cli", cli])

    assert len(save_calls) >= 2  # mindestens einmal pro Aufgabe, nicht nur am Ende


def test_main_unknown_id_is_reported(tmp_path, capsys):
    path = tmp_path / "topic.exercises.json"
    vb.save_exercises(path, {"topic": "topic", "exercises": [MC_EXERCISE]})
    rc = vb.main(["--exercises", str(path), "--id", "does-not-exist"])
    assert rc != 0
    assert "nicht gefunden" in capsys.readouterr().err


# --- Coding: verify_blind.py bindet run_coding.py an ---------------------------

CODING_EXERCISE = {
    "id": "code-01",
    "type": "coding",
    "stem": "Schreibe eine Funktion add(a, b), die die Summe liefert.",
    "model_solution": "def add(a, b):\n    return a + b\n",
    "test_suite": "from solution import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
}


def fake_cli_heredoc(tmp_path: Path, content: str, name: str = "fake-claude-hd") -> str:
    """Wie fake_cli, aber über ein Heredoc — echte Zeilenumbrüche und Backticks
    im Inhalt bleiben erhalten (ein einfaches `echo "…\\n…"` liefert nur den
    literalen Zwei-Zeichen-String `\\n`, keinen echten Zeilenumbruch)."""
    body = "cat <<'FAKE_CLI_EOF'\n" + content + "\nFAKE_CLI_EOF\n"
    return fake_cli(tmp_path, body, name=name)


CODE_FENCE_RESPONSE = "```python\ndef add(a, b):\n    return a + b\n```"


def test_extract_code_block_finds_python_fence():
    text = "Hier ist mein Code:\n" + CODE_FENCE_RESPONSE + "\nFertig."
    code = vb.extract_code_block(text)
    assert "return a + b" in code


def test_extract_code_block_none_without_fence():
    assert vb.extract_code_block("kein Code hier") is None


def test_verify_coding_task_correct_blind_solution_is_verified(tmp_path):
    cli = fake_cli_heredoc(tmp_path, CODE_FENCE_RESPONSE)
    result = vb.verify_coding_task(
        CODING_EXERCISE, tmp_path, cli=cli, python=sys.executable, run_coding_path=RUN_CODING_PATH,
    )
    assert result["status"] == "verified"


def test_verify_coding_task_no_code_block_is_unverified(tmp_path):
    cli = fake_cli(tmp_path, 'echo "Ich weiss es nicht."\n')
    result = vb.verify_coding_task(
        CODING_EXERCISE, tmp_path, cli=cli, python=sys.executable, run_coding_path=RUN_CODING_PATH,
    )
    assert result["status"] == "unverified"
    assert "Codeblock" in result["detail"]


def test_verify_one_dispatches_coding(tmp_path):
    cli = fake_cli_heredoc(tmp_path, CODE_FENCE_RESPONSE)
    result = vb.verify_one(
        CODING_EXERCISE, tmp_path, cli=cli, python=sys.executable, run_coding_path=RUN_CODING_PATH,
    )
    assert result["status"] == "verified"
    assert result["method"] == "blind_solve_coding"
