import json
import stat
from pathlib import Path

import pytest

from conftest import load_script

vb = load_script("skills/exercise-forge/scripts/verify_blind.py")


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


def test_verify_mc_distractor_choice_is_suspicious(tmp_path):
    cli = fake_cli(tmp_path, 'echo "Weil man beim Zaehlen bei 0 anfaengt.\\nANTWORT: A"\n')
    result = vb.verify_mc(MC_EXERCISE, tmp_path, cli=cli)
    assert result["status"] == "suspicious"
    assert "A" in result["detail"] or "2" in result["detail"]


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


def test_verify_open_unmet_criterion_on_plausible_answer_is_suspicious(tmp_path):
    grading = json.dumps({"answer_is_plausible": True, "criteria_met": [True, False], "why": "kein Anwendungsfall genannt"})
    cli = fake_cli_sequence(tmp_path, "Listen sind veraenderbar, Tupel nicht.", grading)
    result = vb.verify_open(OPEN_EXERCISE, tmp_path, cli=cli)
    assert result["status"] == "suspicious"
    assert "eng" in result["detail"]


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


def test_verify_flashcard_diverging_answer_is_suspicious(tmp_path):
    grading = json.dumps({"matches": False, "why": "Frage koennte auch Bevoelkerungsfrage sein"})
    cli = fake_cli_sequence(tmp_path, "67 Millionen", grading)
    result = vb.verify_flashcard(CARD_EXERCISE, tmp_path, cli=cli)
    assert result["status"] == "suspicious"
    assert "mehrdeutig" in result["detail"]


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


def test_main_unknown_id_is_reported(tmp_path, capsys):
    path = tmp_path / "topic.exercises.json"
    vb.save_exercises(path, {"topic": "topic", "exercises": [MC_EXERCISE]})
    rc = vb.main(["--exercises", str(path), "--id", "does-not-exist"])
    assert rc != 0
    assert "nicht gefunden" in capsys.readouterr().err
