import csv
import io
import json

from conftest import load_script

export = load_script("skills/exercise-forge/scripts/export.py")

DIFFICULTY = {"steps": 1, "prerequisites": [], "transfer": "near", "label": "leicht"}
VERIFIED = {"status": "verified", "method": "blind_solve_mc", "detail": "Blind-Löser wählte korrekt.", "checked_at": "2026-08-17T10:00:00Z"}
UNVERIFIED = {"status": "unverified", "method": "not_run", "detail": "Blind-Gate noch nicht gelaufen", "checked_at": None}
SUSPICIOUS = {"status": "suspicious", "method": "blind_check_flashcard", "detail": "Antwort weicht ab.", "checked_at": "2026-08-17T10:00:00Z"}

MC = {
    "id": "mc-01", "type": "multiple_choice", "learning_objective": "len() verstehen",
    "bloom_level": "verstehen", "difficulty": DIFFICULTY,
    "stem": "Was liefert len([1,2,3])?",
    "options": [{"text": "2", "correct": False}, {"text": "3", "correct": True}],
    "verification": VERIFIED,
}
OPEN = {
    "id": "open-01", "type": "open_question", "learning_objective": "Liste vs Tupel",
    "bloom_level": "verstehen", "difficulty": DIFFICULTY,
    "stem": "Unterschied Liste/Tupel?",
    "model_solution": "Listen sind veraenderbar, Tupel nicht.",
    "criteria": ["Nennt Mutability"],
    "verification": UNVERIFIED,
}
CODING = {
    "id": "code-01", "type": "coding", "learning_objective": "Addition schreiben",
    "bloom_level": "anwenden", "difficulty": DIFFICULTY,
    "stem": "Schreibe add(a, b).",
    "model_solution": "def add(a, b):\n    return a + b\n",
    "test_suite": "from solution import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    "verification": VERIFIED,
}
CARD = {
    "id": "card-01", "type": "flashcard", "learning_objective": "Hauptstadt kennen",
    "bloom_level": "erinnern", "difficulty": DIFFICULTY,
    "stem": "Hauptstadt von Frankreich?",
    "front": "Hauptstadt von Frankreich?", "back": "Paris",
    "verification": SUSPICIOUS,
}

ALL_EXERCISES = [MC, OPEN, CODING, CARD]


# --- validate_exercise ---------------------------------------------------------

def test_validate_exercise_accepts_well_formed_mc():
    assert export.validate_exercise(MC) == []


def test_validate_exercise_flags_missing_difficulty():
    broken = dict(MC)
    del broken["difficulty"]
    problems = export.validate_exercise(broken)
    assert any("difficulty" in p for p in problems)


def test_validate_exercise_flags_mc_without_correct_option():
    broken = dict(MC, options=[{"text": "2", "correct": False}, {"text": "3", "correct": False}])
    problems = export.validate_exercise(broken)
    assert any("correct" in p for p in problems)


def test_validate_exercise_flags_mc_with_two_correct_options():
    broken = dict(MC, options=[{"text": "2", "correct": True}, {"text": "3", "correct": True}])
    problems = export.validate_exercise(broken)
    assert any("correct" in p for p in problems)


def test_validate_exercise_flags_missing_verification():
    broken = dict(MC)
    del broken["verification"]
    problems = export.validate_exercise(broken)
    assert any("verification" in p for p in problems)


def test_validate_exercise_flags_unknown_type():
    broken = dict(MC, type="essay")
    problems = export.validate_exercise(broken)
    assert any("type" in p for p in problems)


def test_validate_exercise_flags_missing_flashcard_back():
    broken = dict(CARD)
    del broken["back"]
    problems = export.validate_exercise(broken)
    assert any("back" in p for p in problems)


# --- render_markdown ------------------------------------------------------------

def test_render_markdown_separates_aufgaben_and_loesungen():
    md = export.render_markdown("python-basics", ALL_EXERCISES)
    aufgaben_pos = md.index("## Aufgaben")
    loesungen_pos = md.index("## Lösungen")
    assert aufgaben_pos < loesungen_pos
    # Die Musterlösung darf im Aufgaben-Teil nicht auftauchen.
    aufgaben_teil = md[aufgaben_pos:loesungen_pos]
    assert "return a + b" not in aufgaben_teil


def test_render_markdown_marks_verified_exercise():
    md = export.render_markdown("t", [MC])
    assert "[geprüft]" in md


def test_render_markdown_marks_unverified_exercise_visibly():
    md = export.render_markdown("t", [OPEN])
    assert "[UNGEPRÜFT" in md
    assert "Blind-Gate noch nicht gelaufen" in md


def test_render_markdown_never_marks_suspicious_as_verified():
    """Regression A1: die ursprüngliche Assertion prüfte den Substring
    'card-01 [geprüft]', der wegen des echten Headerformats
    ('### {id} — {stem} {marker}') nie auftreten kann — sie wäre auch bei
    einem kaputten _status_marker nie fehlgeschlagen. '[geprüft]' darf im
    gesamten Dokument nirgends auftauchen, wenn die einzige Aufgabe
    'suspicious' ist."""
    md = export.render_markdown("t", [CARD])
    assert "[geprüft]" not in md
    assert "[UNGEPRÜFT" in md


def test_render_markdown_shows_correct_option_only_in_solutions():
    md = export.render_markdown("t", [MC])
    loesungen = md[md.index("## Lösungen"):]
    assert "Richtige Antwort" in loesungen and "3" in loesungen


# --- render_anki_csv --------------------------------------------------------------

def test_render_anki_csv_has_header_and_one_row_per_exercise():
    csv_text = export.render_anki_csv(ALL_EXERCISES)
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert rows[0] == ["front", "back", "tags"]
    assert len(rows) == 1 + len(ALL_EXERCISES)


def test_render_anki_csv_mc_front_hides_correct_answer():
    csv_text = export.render_anki_csv([MC])
    rows = list(csv.reader(io.StringIO(csv_text)))
    front = rows[1][0]
    assert "correct" not in front.lower()
    assert "A)" in front and "B)" in front


def test_render_anki_csv_tags_carry_status_and_type():
    csv_text = export.render_anki_csv(ALL_EXERCISES)
    rows = {r[2].split()[1]: r[2] for r in list(csv.reader(io.StringIO(csv_text)))[1:]}
    assert "verified" in rows["multiple_choice"]
    assert "unverified" in rows["open_question"]
    assert "suspicious" in rows["flashcard"]


def test_render_anki_csv_flashcard_is_front_back_directly():
    csv_text = export.render_anki_csv([CARD])
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert rows[1][0] == "Hauptstadt von Frankreich?"
    assert rows[1][1] == "Paris"


# --- main() -----------------------------------------------------------------------

def test_main_writes_markdown_and_csv(tmp_path):
    exercises_path = tmp_path / "topic.exercises.json"
    exercises_path.write_text(json.dumps({"topic": "python-basics", "exercises": ALL_EXERCISES}), encoding="utf-8")
    out_dir = tmp_path / "out"

    rc = export.main(["--exercises", str(exercises_path), "--out-dir", str(out_dir)])
    assert rc == 0
    assert (out_dir / "python-basics.md").is_file()
    assert (out_dir / "python-basics-anki.csv").is_file()


def test_main_markdown_carries_artifact_header(tmp_path):
    exercises_path = tmp_path / "topic.exercises.json"
    exercises_path.write_text(json.dumps({"topic": "python-basics", "exercises": [MC]}), encoding="utf-8")
    out_dir = tmp_path / "out"

    export.main(["--exercises", str(exercises_path), "--out-dir", str(out_dir)])
    first_line = (out_dir / "python-basics.md").read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("<!-- skill: exercise-forge | schema: 1 | generated:")


def test_main_reports_invalid_exercise_and_excludes_it(tmp_path, capsys):
    broken = dict(MC)
    del broken["verification"]
    exercises_path = tmp_path / "topic.exercises.json"
    exercises_path.write_text(json.dumps({"topic": "t", "exercises": [broken, OPEN]}), encoding="utf-8")
    out_dir = tmp_path / "out"

    export.main(["--exercises", str(exercises_path), "--out-dir", str(out_dir)])
    err = capsys.readouterr().err
    assert "mc-01" in err
    md = (out_dir / "t.md").read_text(encoding="utf-8")
    assert "mc-01" not in md
    assert "open-01" in md


def test_main_missing_exercises_file_is_reported(tmp_path, capsys):
    rc = export.main(["--exercises", str(tmp_path / "nope.json"), "--out-dir", str(tmp_path / "out")])
    assert rc != 0
    assert "nicht gefunden" in capsys.readouterr().err


# --- D1: eine von Hand geschriebene Verifikation wird nicht mehr geglaubt --------

HAND_WRITTEN_VERIFIED = {
    "status": "verified", "method": "sieht_plausibel_aus", "detail": "kurz überflogen", "checked_at": None,
}
REAL_METHOD_NO_TIMESTAMP = {
    "status": "verified", "method": "blind_solve_mc", "detail": "wirkt korrekt", "checked_at": None,
}


def test_has_verified_provenance_true_for_real_blind_gate_result():
    assert export.has_verified_provenance(VERIFIED) is True


def test_has_verified_provenance_false_for_unknown_method():
    assert export.has_verified_provenance(HAND_WRITTEN_VERIFIED) is False


def test_has_verified_provenance_false_without_checked_at():
    assert export.has_verified_provenance(REAL_METHOD_NO_TIMESTAMP) is False


def test_hand_written_verified_is_not_excluded_but_rendered_as_ungeprueft():
    """D1: eine erfundene 'verified'-Behauptung darf die Aufgabe nicht aus dem
    Export werfen (sie bleibt strukturell gültig — Stamm, Optionen etc. sind
    da), aber sie darf nie als [geprüft] erscheinen."""
    faked = dict(MC, verification=HAND_WRITTEN_VERIFIED)
    assert export.validate_exercise(faked) == []  # strukturell weiterhin gültig
    md = export.render_markdown("t", [faked])
    assert "[geprüft]" not in md
    assert "[UNGEPRÜFT" in md
    assert "ohne nachvollziehbaren Blind-Gate-Lauf" in md


def test_hand_written_verified_without_checked_at_is_also_downgraded():
    faked = dict(MC, verification=REAL_METHOD_NO_TIMESTAMP)
    md = export.render_markdown("t", [faked])
    assert "[geprüft]" not in md
    assert "[UNGEPRÜFT" in md


def test_hand_written_verified_gets_unverified_tag_in_csv():
    faked = dict(MC, verification=HAND_WRITTEN_VERIFIED)
    csv_text = export.render_anki_csv([faked])
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert "unverified" in rows[1][2]
    assert "verified" not in rows[1][2].split()  # nicht als eigenständiges Tag-Wort


def test_main_exports_hand_faked_exercise_as_ungeprueft_not_excluded(tmp_path, capsys):
    faked = dict(MC, verification=HAND_WRITTEN_VERIFIED)
    exercises_path = tmp_path / "topic.exercises.json"
    exercises_path.write_text(json.dumps({"topic": "t", "exercises": [faked]}), encoding="utf-8")
    out_dir = tmp_path / "out"

    rc = export.main(["--exercises", str(exercises_path), "--out-dir", str(out_dir)])
    assert rc == 0
    md = (out_dir / "t.md").read_text(encoding="utf-8")
    assert "mc-01" in md  # exportiert, nicht ausgeschlossen
    assert "[geprüft]" not in md  # aber nie als geprüft ausgewiesen
