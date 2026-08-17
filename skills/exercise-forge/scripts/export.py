#!/usr/bin/env python3
"""Rendert das Aufgaben-JSON nach Markdown-Übungsblatt und Anki-CSV.

Tier 1: nur Stdlib. Reines Rendering — dieses Skript erzeugt keine Aufgaben
und ändert nie `verification`. Eine Aufgabe ohne (oder mit widersprüchlichem)
Prüfnachweis wird sichtbar als ungeprüft exportiert, nie stillschweigend als
geprüft (Nutzervorgabe, Spec 13 Constraint 'Blind-Verifikation ist
Pflicht-Gate').
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
VERIFICATION_STATUSES = {"verified", "suspicious", "unverified"}


# --- Pfad (dupliziert aus verify_blind.py — Skripte bleiben eigenständig, Rulings A3) --

def resolve_exercises_path(topic: str, repo: Path = Path(".")) -> Path:
    project_dir = Path(repo) / ".skills" / "verified-research" / "research"
    if project_dir.is_dir():
        return project_dir / f"{topic}.exercises.json"
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
    if not isinstance(verification, dict):
        return ["'verification' fehlt oder ist kein Objekt"]
    problems = []
    if verification.get("status") not in VERIFICATION_STATUSES:
        problems.append("'verification.status' muss verified/suspicious/unverified sein")
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


# --- Statusmarkierung (nie stillschweigend 'geprüft') -----------------------------

def _status_marker(exercise: dict) -> str:
    verification = exercise.get("verification") or {}
    if verification.get("status") == "verified":
        return "[geprüft]"
    reason = verification.get("detail") or "Blind-Gate noch nicht gelaufen"
    return f"[UNGEPRÜFT: {reason}]"


def _tag_status(exercise: dict) -> str:
    verification = exercise.get("verification") or {}
    status = verification.get("status")
    return status if status in VERIFICATION_STATUSES else "unverified"


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
