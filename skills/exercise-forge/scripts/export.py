#!/usr/bin/env python3
"""Rendert das Aufgaben-JSON nach Markdown-Übungsblatt und Anki-CSV.

Tier 1: nur Stdlib. Reines Rendering — dieses Skript erzeugt keine Aufgaben
und ändert nie `verification`. Eine Aufgabe ohne (oder mit unvollständigem)
Prüfnachweis wird sichtbar als ungeprüft exportiert, nie stillschweigend als
geprüft (Nutzervorgabe, Spec 13 Constraint 'Blind-Verifikation ist
Pflicht-Gate').

Fix-Runde 5: `verification` trägt seit dieser Runde **kein `status`-Feld
mehr**. Ein gespeicherter, frei editierbarer Status wäre redundant zu dem,
was `derive_status_from_protocol()` ohnehin aus `protocol` berechnet — und
ein redundantes, frei beschreibbares Feld war genau die Fehlerquelle
(Fix-Runde 3/4: eine Session konnte `status: "verified"` neben einem
Protokoll schreiben, das etwas anderes zeigte; Fix-Runde 4 entkoppelte nur
das *Rendering* davon, ließ den Widerspruch aber im Aufgaben-JSON selbst
stehen — einem Artefakt, das auch andere Werkzeuge lesen, siehe
`references/task-schemas.md`). Ohne das Feld kann der Widerspruch gar nicht
mehr entstehen.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

SCHEMA_VERSION = 1
LETTERS = "ABCDEFGH"
KNOWN_TYPES = {"multiple_choice", "open_question", "coding", "flashcard"}
DIFFICULTY_LABELS = {"leicht", "mittel", "schwer"}
TRANSFER_VALUES = {"near", "far"}
# Die möglichen Ergebnisse von derive_status_from_protocol() — kein
# gespeichertes Feld mehr (Fix-Runde 5), sondern der Wertebereich der
# Ableitung.
VERIFICATION_STATUSES = {"verified", "suspicious", "unverified"}
# Die einzigen 'method'-Werte, die verify_blind.py/run_coding.py tatsächlich
# schreiben, wenn das Blind-Gate wirklich lief (Rulings D4, Review-Befund D1).
# 'not_run' ist der Startzustand einer frisch erzeugten, noch ungeprüften
# Aufgabe — real, aber kein Prüfnachweis.
REAL_VERIFICATION_METHODS = {"blind_solve_mc", "blind_solve_open", "blind_solve_coding", "blind_check_flashcard"}
ALL_VERIFICATION_METHODS = REAL_VERIFICATION_METHODS | {"not_run"}


# --- Pfad (dupliziert aus verify_blind.py — Skripte bleiben eigenständig, Rulings A3) --

def resolve_exercises_path(topic: str, repo: Path = Path(".")) -> Path:
    """Projekt-Override an der **Basis** `.skills/verified-research/` festmachen,
    nicht am `research/`-Unterverzeichnis.

    Der Namensraum gehört verified-research, und dessen eigenes
    `registry.py::resolve_base_dir` prüft die Basis — ebenso `learning-coach`s
    `due_topics.py`, das diese Dateien liest. Die frühere `research/`-Bedingung
    wich davon ab: Existierte die Basis, aber noch kein `research/`, schrieb
    diese Skill nach `~`, während `learning-coach` projektlokal suchte und die
    Aufgaben dauerhaft als "nicht gefunden" meldete.
    """
    base_dir = Path(repo) / ".skills" / "verified-research"
    if base_dir.is_dir():
        return base_dir / "research" / f"{topic}.exercises.json"
    return Path.home() / ".skills" / "verified-research" / "research" / f"{topic}.exercises.json"


# --- Validierung -----------------------------------------------------------------

def _check_difficulty(difficulty: object) -> list[str]:
    if not isinstance(difficulty, dict):
        return ["'difficulty' fehlt oder ist kein Objekt"]
    problems = []
    if not isinstance(difficulty.get("steps"), int):
        problems.append("'difficulty.steps' fehlt oder ist keine Zahl")
    if not isinstance(difficulty.get("prerequisites"), list):
        problems.append("'difficulty.prerequisites' fehlt oder ist keine Liste")
    if difficulty.get("transfer") not in TRANSFER_VALUES:
        problems.append("'difficulty.transfer' muss 'near' oder 'far' sein")
    if difficulty.get("label") not in DIFFICULTY_LABELS:
        problems.append("'difficulty.label' muss leicht/mittel/schwer sein")
    return problems


def _check_verification(verification: object) -> list[str]:
    """Rein strukturell: `status` ist seit Fix-Runde 5 kein gespeichertes Feld
    mehr und wird hier nicht (mehr) verlangt — er entsteht ausschließlich aus
    `derive_status_from_protocol()`."""
    if not isinstance(verification, dict):
        return ["'verification' fehlt oder ist kein Objekt"]
    problems = []
    if not verification.get("method"):
        problems.append("'verification.method' fehlt")
    return problems


def validate_exercise(exercise: dict) -> list[str]:
    """Liste fehlender/falscher Pflichtfelder. Leer heißt: renderbar."""
    problems: list[str] = []
    for field in ("id", "learning_objective", "bloom_level", "stem"):
        if not exercise.get(field):
            problems.append(f"'{field}' fehlt oder ist leer")

    ex_type = exercise.get("type")
    if ex_type not in KNOWN_TYPES:
        problems.append(f"'type' unbekannt oder fehlt: {ex_type!r}")

    problems += _check_difficulty(exercise.get("difficulty"))
    problems += _check_verification(exercise.get("verification"))

    if ex_type == "multiple_choice":
        options = exercise.get("options")
        if not isinstance(options, list) or len(options) < 2:
            problems.append("'options' braucht mindestens zwei Einträge")
        else:
            correct_count = sum(1 for o in options if isinstance(o, dict) and o.get("correct"))
            if correct_count != 1:
                problems.append(f"genau eine Option muss 'correct': true tragen, gefunden: {correct_count}")
    elif ex_type == "open_question":
        if not exercise.get("model_solution"):
            problems.append("'model_solution' fehlt")
        if not exercise.get("criteria"):
            problems.append("'criteria' fehlt oder ist leer")
    elif ex_type == "coding":
        if not exercise.get("model_solution"):
            problems.append("'model_solution' fehlt")
        if not exercise.get("test_suite"):
            problems.append("'test_suite' fehlt")
    elif ex_type == "flashcard":
        if not exercise.get("front"):
            problems.append("'front' fehlt")
        if not exercise.get("back"):
            problems.append("'back' fehlt")

    return problems


# --- Statusmarkierung: Ableiten statt Validieren (Fix-Runde 4) --------------------
#
# Ein gemessener Defekt, nicht nur eine theoretische Lücke: Eine Doktrin allein
# ("status: verified entsteht ausschließlich durch das Blind-Gate", SKILL.md)
# wurde ausprobiert und reichte nicht — ein Agent setzte `status: "verified"`
# von Hand, nachdem er einen vom Gate gefundenen Konflikt bereits gemeldet
# hatte (drei echte Eval-Läufe, siehe docs/known-limits.md). Die vorherige
# Herkunftsprüfung (`method`/`checked_at` vorhanden) hätte das nicht gefangen,
# wenn `method`/`checked_at` von einem früheren, echten Lauf unverändert
# übernommen wurden — sie prüfte *Vorhandensein*, nicht *Stimmigkeit* mit dem
# aktuellen `status`.
#
# Der Fix: `status` wird beim Rendern nie gelesen. Der angezeigte Status wird
# stattdessen aus `verification.protocol` — den Rohdaten, die `verify_blind.py`/
# `run_coding.py` bei einem echten Lauf mitschreiben — und den Aufgabendaten
# selbst (Options, Kriterien) neu berechnet. Ein von Hand auf `verified`
# gesetztes `status`-Wort hat dadurch schlicht keine Wirkung mehr: Es wird für
# die Anzeige gar nicht angesehen.

def derive_status_from_protocol(exercise: dict) -> tuple[str, str]:
    """(status, detail) — berechnet aus `verification.protocol` (Fix-Runde 5:
    `status` ist seit dieser Runde gar kein gespeichertes Feld mehr, siehe
    Modul-Docstring — es gibt also auch nichts mehr, dem widersprochen werden
    könnte). Fehlt ein vollständiges, zum Aufgabentyp passendes Protokoll, ist
    das Ergebnis `unverified` — dieselbe A4-Regel wie überall sonst in dieser
    Skill: nicht sicher erkannt heißt nie 'in Ordnung'."""
    verification = exercise.get("verification") or {}
    method = verification.get("method")
    checked_at = verification.get("checked_at")
    protocol = verification.get("protocol")
    ex_type = exercise.get("type")

    if method == "not_run" or method is None:
        # Normalfall: frisch erzeugte, noch nicht geprüfte Aufgabe. Der
        # ursprüngliche `detail`-Text ist hier unbedenklich (er entscheidet
        # nichts über 'geprüft'), also darf er als freundliche Meldung
        # durchgereicht werden.
        return "unverified", verification.get("detail") or "Blind-Gate noch nicht gelaufen"

    if method not in REAL_VERIFICATION_METHODS:
        return "unverified", f"'{method}' ist keine der vom Blind-Gate erzeugten Methoden — kein Prüfnachweis"

    if not checked_at or not isinstance(protocol, dict):
        # method sieht nach einem echten Lauf aus, aber checked_at/protocol
        # fehlen oder sind unvollständig — das ist der verdächtigere Fall
        # (ein Teil-Hand-Edit), nicht einfach "noch nicht geprüft".
        return "unverified", (
            f"method {method!r} sieht nach einem echten Lauf aus, aber checked_at "
            "und/oder protocol fehlen oder sind unvollständig — kein vollständiger Prüfnachweis"
        )

    if ex_type == "multiple_choice" and method == "blind_solve_mc":
        options = exercise.get("options")
        chosen_index = protocol.get("chosen_index")
        if not isinstance(options, list) or not isinstance(chosen_index, int) or not (0 <= chosen_index < len(options)):
            return "unverified", "Protokoll verweist auf keine gültige Option der Aufgabe"
        chosen = options[chosen_index]
        letter = LETTERS[chosen_index] if chosen_index < len(LETTERS) else str(chosen_index)
        if chosen.get("correct"):
            return "verified", f"Blind-Löser wählte laut Protokoll die als korrekt markierte Option {letter}."
        return "suspicious", f"Blind-Löser wählte laut Protokoll Option {letter} — nicht als korrekt markiert."

    if ex_type == "open_question" and method == "blind_solve_open":
        criteria = exercise.get("criteria") or []
        met = protocol.get("criteria_met")
        plausible = protocol.get("answer_is_plausible")
        if not criteria or not isinstance(met, list) or len(met) != len(criteria) or not isinstance(plausible, bool):
            return "unverified", "Protokoll passt nicht zur Kriterienliste der Aufgabe"
        if not plausible:
            return "unverified", "Blind-Antwort war laut Protokoll nicht plausibel genug für ein Urteil"
        if all(met):
            return "verified", "Blind-Antwort erfüllt laut Protokoll alle Kriterien."
        unmet = [i + 1 for i, ok in enumerate(met) if not ok]
        return "suspicious", f"Blind-Antwort erfüllt laut Protokoll Kriterium/-ien {unmet} nicht."

    if ex_type == "flashcard" and method == "blind_check_flashcard":
        matches = protocol.get("matches")
        if not isinstance(matches, bool):
            return "unverified", "Protokoll enthält kein 'matches'-Feld"
        if matches:
            return "verified", "Blind-Antwort trifft laut Protokoll die Rückseite."
        return "suspicious", "Blind-Antwort weicht laut Protokoll von der Rückseite ab."

    if ex_type == "coding" and method == "blind_solve_coding":
        model_passed = protocol.get("model_passed")
        blind_passed = protocol.get("blind_passed")
        if not isinstance(model_passed, bool):
            return "unverified", "Protokoll enthält kein Testergebnis für die Musterlösung"
        if not model_passed:
            return "unverified", "Musterlösung besteht laut Protokoll die eigenen Tests nicht"
        if not isinstance(blind_passed, bool):
            return "unverified", "Protokoll enthält kein Testergebnis für die Blind-Lösung"
        if blind_passed:
            return "verified", "Musterlösung und Blind-Lösung bestehen laut Protokoll beide die Tests."
        return "suspicious", "Blind-Lösung besteht laut Protokoll nicht, obwohl die Musterlösung besteht."

    return "unverified", f"Methode {method!r} passt nicht zum Aufgabentyp {ex_type!r}"


def _status_marker(exercise: dict) -> str:
    status, detail = derive_status_from_protocol(exercise)
    if status == "verified":
        return "[geprüft]"
    return f"[UNGEPRÜFT: {detail}]"


def _tag_status(exercise: dict) -> str:
    status, _ = derive_status_from_protocol(exercise)
    return status


# --- Markdown ---------------------------------------------------------------------

def _render_aufgabe(exercise: dict) -> str:
    ex_type = exercise["type"]
    header = f"### {exercise['id']} — {exercise['stem']} {_status_marker(exercise)}"
    if ex_type == "multiple_choice":
        lines = [f"{LETTERS[i]}) {o['text']}" for i, o in enumerate(exercise["options"])]
        return header + "\n" + "\n".join(lines)
    if ex_type == "open_question":
        return header
    if ex_type == "coding":
        return header + f"\n\nTestsuite:\n```python\n{exercise['test_suite']}\n```"
    if ex_type == "flashcard":
        return header
    return header


def _render_loesung(exercise: dict) -> str:
    ex_type = exercise["type"]
    header = f"### {exercise['id']}"
    if ex_type == "multiple_choice":
        correct = next(o for o in exercise["options"] if o.get("correct"))
        letter = LETTERS[exercise["options"].index(correct)]
        return header + f"\nRichtige Antwort: {letter}) {correct['text']}"
    if ex_type == "open_question":
        criteria = "\n".join(f"- {c}" for c in exercise.get("criteria", []))
        return header + f"\nMusterantwort: {exercise['model_solution']}\n\nKriterien:\n{criteria}"
    if ex_type == "coding":
        return header + f"\nMusterlösung:\n```python\n{exercise['model_solution']}\n```"
    if ex_type == "flashcard":
        return header + f"\n{exercise['back']}"
    return header


def render_markdown(topic: str, exercises: list[dict]) -> str:
    aufgaben = "\n\n".join(_render_aufgabe(e) for e in exercises) or "(keine Aufgaben)"
    loesungen = "\n\n".join(_render_loesung(e) for e in exercises) or "(keine Aufgaben)"
    return (
        f"# Übungsblatt — {topic}\n\n"
        f"## Aufgaben\n\n{aufgaben}\n\n"
        "---\n\n"
        f"## Lösungen\n\n{loesungen}\n"
    )


# --- Anki-CSV -----------------------------------------------------------------------

def _anki_row(exercise: dict) -> list[str]:
    ex_type = exercise["type"]
    tags = f"exercise-forge {ex_type} {_tag_status(exercise)}"
    if ex_type == "multiple_choice":
        front = exercise["stem"] + "\n" + "\n".join(
            f"{LETTERS[i]}) {o['text']}" for i, o in enumerate(exercise["options"])
        )
        correct = next(o for o in exercise["options"] if o.get("correct"))
        letter = LETTERS[exercise["options"].index(correct)]
        back = f"Richtige Antwort: {letter}) {correct['text']}"
    elif ex_type == "open_question":
        front = exercise["stem"]
        back = exercise["model_solution"]
    elif ex_type == "coding":
        front = exercise["stem"] + "\n\n" + exercise["test_suite"]
        back = exercise["model_solution"]
    elif ex_type == "flashcard":
        front = exercise["front"]
        back = exercise["back"]
    else:
        front, back = exercise.get("stem", ""), ""
    return [front, back, tags]


def render_anki_csv(exercises: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["front", "back", "tags"])
    for exercise in exercises:
        writer.writerow(_anki_row(exercise))
    return buf.getvalue()


# --- CLI ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="exercises.json nach Markdown + Anki-CSV rendern")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--exercises", type=Path, help="Pfad zur exercises.json")
    target.add_argument("--topic", help="Thema — Pfad wird aufgelöst (Projekt-Override oder Home)")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, default=Path("docs/exercises"))
    args = parser.parse_args(argv)

    path = args.exercises or resolve_exercises_path(args.topic, args.repo)
    if not path.is_file():
        print(f"Aufgaben-JSON nicht gefunden: {path}", file=sys.stderr)
        return 2

    data = json.loads(path.read_text(encoding="utf-8"))
    topic = data.get("topic") or (args.topic or path.stem.removesuffix(".exercises"))
    all_exercises = data.get("exercises", [])

    valid: list[dict] = []
    for exercise in all_exercises:
        problems = validate_exercise(exercise)
        if problems:
            print(f"Aufgabe {exercise.get('id', '?')!r} übersprungen (ungültig): {'; '.join(problems)}", file=sys.stderr)
            continue
        valid.append(exercise)

    if not valid:
        print("Keine gültige Aufgabe im Aufgaben-JSON — nichts exportiert.", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / f"{topic}.md"
    csv_path = args.out_dir / f"{topic}-anki.csv"

    generated_cmd = f"python skills/exercise-forge/scripts/export.py --exercises {path}"
    header = f"<!-- skill: exercise-forge | schema: {SCHEMA_VERSION} | generated: {generated_cmd} -->\n\n"
    md_path.write_text(header + render_markdown(topic, valid), encoding="utf-8")

    # Anki-CSV trägt bewusst KEINE Kopfzeile: Anki interpretiert Zeilen, die mit
    # '#' beginnen, als Import-Direktiven (z. B. '#separator:comma') — eine
    # Kommentar-Kopfzeile könnte den Import stören. Begründete Ausnahme wie
    # handoff.md, siehe docs/artifact-header.md.
    csv_path.write_text(render_anki_csv(valid), encoding="utf-8")

    print(f"{len(valid)} Aufgabe(n) exportiert -> {md_path}, {csv_path}")
    skipped = len(all_exercises) - len(valid)
    if skipped:
        print(f"{skipped} Aufgabe(n) wegen ungültigem Schema übersprungen (siehe oben)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
