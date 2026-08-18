import csv
import io
import json

from conftest import load_script

export = load_script("skills/exercise-forge/scripts/export.py")

DIFFICULTY = {"steps": 1, "prerequisites": [], "transfer": "near", "label": "leicht"}

# Fix-Runde 5: 'verification' trägt kein gespeichertes 'status'-Feld mehr —
# 'verified'/'suspicious' entstehen ausschließlich aus `verification.protocol`
# (derive_status_from_protocol). Diese vier Fixtures spiegeln, was ein echter
# verify_blind.py/run_coding.py-Lauf tatsächlich schreibt (kein 'status'-Key).
# Die Kontrast-Fixtures weiter unten (HAND_WRITTEN_*, STATUS_CONTRADICTS_*)
# fügen 'status' absichtlich wieder hinzu, um zu beweisen, dass er ignoriert
# wird, selbst wenn ihn jemand von Hand zurückschreibt.
MC_VERIFIED = {
    "method": "blind_solve_mc", "detail": "Blind-Löser wählte korrekt.",
    "checked_at": "2026-08-17T10:00:00Z", "protocol": {"chosen_index": 1},  # Option B ("3") ist correct: true
}
OPEN_UNVERIFIED = {
    "method": "not_run", "detail": "Blind-Gate noch nicht gelaufen",
    "checked_at": None, "protocol": None,
}
CODING_VERIFIED = {
    "method": "blind_solve_coding",
    "detail": "Musterlösung und Blind-Lösung bestehen beide die Tests.",
    "checked_at": "2026-08-17T10:00:00Z", "protocol": {"model_passed": True, "blind_passed": True},
}
CARD_SUSPICIOUS = {
    "method": "blind_check_flashcard", "detail": "Antwort weicht ab.",
    "checked_at": "2026-08-17T10:00:00Z", "protocol": {"matches": False},
}

MC = {
    "id": "mc-01", "type": "multiple_choice", "learning_objective": "len() verstehen",
    "bloom_level": "verstehen", "difficulty": DIFFICULTY,
    "stem": "Was liefert len([1,2,3])?",
    "options": [{"text": "2", "correct": False}, {"text": "3", "correct": True}],
    "verification": MC_VERIFIED,
}
OPEN = {
    "id": "open-01", "type": "open_question", "learning_objective": "Liste vs Tupel",
    "bloom_level": "verstehen", "difficulty": DIFFICULTY,
    "stem": "Unterschied Liste/Tupel?",
    "model_solution": "Listen sind veraenderbar, Tupel nicht.",
    "criteria": ["Nennt Mutability"],
    "verification": OPEN_UNVERIFIED,
}
CODING = {
    "id": "code-01", "type": "coding", "learning_objective": "Addition schreiben",
    "bloom_level": "anwenden", "difficulty": DIFFICULTY,
    "stem": "Schreibe add(a, b).",
    "model_solution": "def add(a, b):\n    return a + b\n",
    "test_suite": "from solution import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    "verification": CODING_VERIFIED,
}
CARD = {
    "id": "card-01", "type": "flashcard", "learning_objective": "Hauptstadt kennen",
    "bloom_level": "erinnern", "difficulty": DIFFICULTY,
    "stem": "Hauptstadt von Frankreich?",
    "front": "Hauptstadt von Frankreich?", "back": "Paris",
    "verification": CARD_SUSPICIOUS,
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


# --- Fix-Runde 4: status wird abgeleitet, nie gelesen --------------------------
#
# D1 (Fix-Runde 1) prüfte nur, dass method/checked_at *vorhanden* sind — das
# reichte nicht (Fix-Runde 3, mit drei echten Eval-Läufen gemessen): eine
# Session kann ein 'status: verified' neben method/checked_at eines echten,
# aber ANDEREN (z. B. 'suspicious') Laufs schreiben, und die alte Prüfung hätte
# das nicht bemerkt. Der Fix in dieser Runde liest 'status' beim Rendern
# überhaupt nicht mehr — der angezeigte Status kommt ausschließlich aus
# `derive_status_from_protocol()`. Die Tests hier decken beide Richtungen ab:
# ein erfundenes 'verified' neben einem Protokoll, das etwas anderes zeigt,
# UND das Fehlen jedes Protokolls.

HAND_WRITTEN_VERIFIED_NO_PROTOCOL = {
    "status": "verified", "method": "sieht_plausibel_aus", "detail": "kurz überflogen",
    "checked_at": None, "protocol": None,
}
REAL_METHOD_NO_TIMESTAMP = {
    "status": "verified", "method": "blind_solve_mc", "detail": "wirkt korrekt",
    "checked_at": None, "protocol": {"chosen_index": 1},
}
# Der eigentliche Fix-Runde-3-Fall: method/checked_at sehen echt aus (stammen
# von einem tatsächlichen Lauf), aber das Protokoll hält einen Konflikt fest
# (Option A ist NICHT 'correct') — nur 'status' wurde von Hand auf 'verified'
# gedreht.
STATUS_CONTRADICTS_PROTOCOL = {
    "status": "verified", "method": "blind_solve_mc",
    "detail": "Blind-Löser wählte Distraktor A ('2'). Begründung: ...",
    "checked_at": "2026-08-17T10:00:00Z", "protocol": {"chosen_index": 0},  # Option A, "2", correct: false
}


def test_derive_status_verified_when_protocol_confirms_correct_choice():
    status, _ = export.derive_status_from_protocol(MC)
    assert status == "verified"


def test_derive_status_ignores_status_word_entirely():
    """Der Kern von Fix-Runde 4: 'status' wird nicht gelesen. Ein Objekt mit
    status: 'unverified', aber einem Protokoll, das eindeutig 'verified'
    zeigt, ergibt trotzdem 'verified' — die Ableitung ist die einzige Quelle."""
    inverted = dict(MC_VERIFIED, status="unverified")
    exercise = dict(MC, verification=inverted)
    status, _ = export.derive_status_from_protocol(exercise)
    assert status == "verified"


def test_derive_status_verified_claim_next_to_conflicting_protocol_is_suspicious():
    """Der gemessene Fix-Runde-3-Defekt, direkt nachgestellt: status: 'verified'
    neben einem Protokoll, das eine Distraktor-Wahl festhält — die Ableitung
    hält sich ans Protokoll, nicht ans Wort."""
    exercise = dict(MC, verification=STATUS_CONTRADICTS_PROTOCOL)
    status, detail = export.derive_status_from_protocol(exercise)
    assert status == "suspicious"
    assert "nicht als korrekt markiert" in detail


def test_derive_status_open_question_verified_claim_next_to_unmet_criterion_is_suspicious():
    faked = dict(
        OPEN,
        verification={
            "status": "verified", "method": "blind_solve_open", "detail": "sieht gut aus",
            "checked_at": "2026-08-17T10:00:00Z",
            "protocol": {"criteria_met": [False], "answer_is_plausible": True},
        },
    )
    status, detail = export.derive_status_from_protocol(faked)
    assert status == "suspicious"
    assert "nicht" in detail


def test_derive_status_coding_verified_claim_next_to_failed_blind_solution_is_suspicious():
    faked = dict(
        CODING,
        verification={
            "status": "verified", "method": "blind_solve_coding", "detail": "sieht gut aus",
            "checked_at": "2026-08-17T10:00:00Z",
            "protocol": {"model_passed": True, "blind_passed": False},
        },
    )
    status, detail = export.derive_status_from_protocol(faked)
    assert status == "suspicious"
    assert "nicht" in detail


def test_derive_status_coding_without_blind_passed_is_unverified_not_suspicious():
    """Regression: 'blind_passed' fehlt komplett, wenn keine Blind-Lösung
    übergeben wurde (Blind-Gate unvollständig, run_coding.verify_coding gibt
    dann nur {'model_passed': True} zurück). Das ist 'unverified', nicht
    'suspicious' — ein bloßes protocol.get('blind_passed') würde beides
    (fehlend und explizit False) gleich behandeln (falsy)."""
    faked = dict(
        CODING,
        verification={
            "method": "blind_solve_coding", "detail": "nur Musterlösung geprüft",
            "checked_at": "2026-08-17T10:00:00Z",
            "protocol": {"model_passed": True},
        },
    )
    status, _ = export.derive_status_from_protocol(faked)
    assert status == "unverified"


def test_derive_status_flashcard_verified_claim_next_to_non_matching_protocol_is_suspicious():
    faked = dict(
        CARD,
        verification={
            "status": "verified", "method": "blind_check_flashcard", "detail": "sieht gut aus",
            "checked_at": "2026-08-17T10:00:00Z",
            "protocol": {"matches": False},
        },
    )
    status, detail = export.derive_status_from_protocol(faked)
    assert status == "suspicious"
    assert "weicht" in detail


def test_derive_status_unverified_for_unknown_method():
    exercise = dict(MC, verification=HAND_WRITTEN_VERIFIED_NO_PROTOCOL)
    status, detail = export.derive_status_from_protocol(exercise)
    assert status == "unverified"
    assert "sieht_plausibel_aus" in detail


def test_derive_status_unverified_for_fresh_not_run_exercise():
    fresh = dict(MC, verification={"method": "not_run", "detail": "Blind-Gate noch nicht gelaufen", "checked_at": None, "protocol": None})
    status, detail = export.derive_status_from_protocol(fresh)
    assert status == "unverified"
    assert detail == "Blind-Gate noch nicht gelaufen"


def test_derive_status_unverified_without_checked_at_even_with_protocol():
    exercise = dict(MC, verification=REAL_METHOD_NO_TIMESTAMP)
    status, _ = export.derive_status_from_protocol(exercise)
    assert status == "unverified"


def test_hand_written_verified_is_not_excluded_but_rendered_as_ungeprueft():
    """Eine erfundene 'verified'-Behauptung darf die Aufgabe nicht aus dem
    Export werfen (sie bleibt strukturell gültig — Stamm, Optionen etc. sind
    da), aber sie darf nie als [geprüft] erscheinen."""
    faked = dict(MC, verification=HAND_WRITTEN_VERIFIED_NO_PROTOCOL)
    assert export.validate_exercise(faked) == []  # strukturell weiterhin gültig
    md = export.render_markdown("t", [faked])
    assert "[geprüft]" not in md
    assert "[UNGEPRÜFT" in md


def test_status_next_to_conflicting_protocol_never_renders_as_geprueft():
    """Die vom Koordinator explizit verlangte Deckung: ein von Hand auf
    'verified' gesetzter Status neben einem 'suspicious'-Protokoll darf
    nirgends als geprüft erscheinen — weder im Markdown-Blatt noch in der
    Anki-CSV."""
    faked = dict(MC, verification=STATUS_CONTRADICTS_PROTOCOL)
    md = export.render_markdown("t", [faked])
    assert "[geprüft]" not in md
    assert "[UNGEPRÜFT" in md

    csv_text = export.render_anki_csv([faked])
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert "verified" not in rows[1][2].split()
    assert "suspicious" in rows[1][2]


def test_hand_written_verified_without_checked_at_is_also_downgraded():
    faked = dict(MC, verification=REAL_METHOD_NO_TIMESTAMP)
    md = export.render_markdown("t", [faked])
    assert "[geprüft]" not in md
    assert "[UNGEPRÜFT" in md


def test_hand_written_verified_gets_unverified_tag_in_csv():
    faked = dict(MC, verification=HAND_WRITTEN_VERIFIED_NO_PROTOCOL)
    csv_text = export.render_anki_csv([faked])
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert "unverified" in rows[1][2]
    assert "verified" not in rows[1][2].split()  # nicht als eigenständiges Tag-Wort


def test_main_exports_hand_faked_exercise_as_ungeprueft_not_excluded(tmp_path, capsys):
    faked = dict(MC, verification=HAND_WRITTEN_VERIFIED_NO_PROTOCOL)
    exercises_path = tmp_path / "topic.exercises.json"
    exercises_path.write_text(json.dumps({"topic": "t", "exercises": [faked]}), encoding="utf-8")
    out_dir = tmp_path / "out"

    rc = export.main(["--exercises", str(exercises_path), "--out-dir", str(out_dir)])
    assert rc == 0
    md = (out_dir / "t.md").read_text(encoding="utf-8")
    assert "mc-01" in md  # exportiert, nicht ausgeschlossen
    assert "[geprüft]" not in md  # aber nie als geprüft ausgewiesen
