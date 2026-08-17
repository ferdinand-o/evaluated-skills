#!/usr/bin/env python3
"""Lernstand für learning-coach: parsen, Fälligkeit berechnen, Spacing-Intervall
vorschlagen. Tier 1: nur Stdlib (E1).

Was dieses Skript NICHT tut: Es führt keine Session, stellt keine Quiz-Fragen und
schreibt `learner.md` nicht zurück. Das Update am Sitzungsende ist Doktrin
(SKILL.md), kein Skript-Aufruf — ein Sokratischer Dialog lässt sich nicht durch ein
Python-Skript ersetzen. Dieses Skript liefert nur die zwei Dinge, die sich mechanisch
und deterministisch berechnen lassen: welche Themen fällig sind, und wie das nächste
Intervall aussieht.

Schnittstelle zu exercise-forge (Spec 13, E3): Nur der Pfad
`~/.skills/verified-research/research/<slug>.exercises.json` wird geprüft — auf
Existenz, nicht auf Inhalt. Das Aufgaben-JSON-Schema von exercise-forge wird hier
nicht geparst, weil Spec 13 parallel zu dieser Skill gebaut wird und die genauen
Feldnamen nicht bekannt sind (A4: was nicht sicher bekannt ist, wird nicht
angenommen).
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

SKILL_DIRNAME = "learning-coach"
# E3: Aufgaben-JSONs liegen neben der Wissensdatei aus Spec 12, nicht unter
# learning-coach/ selbst — siehe Spec 13 und rulings-final-four.md E3.
EXERCISES_SKILL_DIRNAME = "verified-research"
SCHEMA_VERSION = 1

# E4-Spacing-Regel (eigene, in methods.md dokumentierte Entscheidung): Intervall in
# Tagen je Beherrschungsgrad. Grad 0 ist sofort wieder fällig (kein Puffer für "nie
# gesehen"), jede weitere Stufe verdoppelt sich ungefähr — einfache, nachvollziehbare
# Progression statt eines vollen SM-2-Algorithmus, den `learner.md` mangels
# Wiederholungszähler ohnehin nicht abbilden könnte.
INTERVAL_DAYS: dict[int, int] = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14}
RESULTS = ("success", "failure")

HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
TOPIC_HEADING_RE = re.compile(r"^## (?P<slug>[a-z0-9][a-z0-9-]*): (?P<name>.+)$")
FIELD_LINE_RE = re.compile(r"^- ([^:]+):\s*(.*)$")
LIST_ITEM_RE = re.compile(r"^ {2,}- (.+)$")
LIST_LABELS = ("Typische Fehler", "Offene Fragen")


class DueTopicsError(RuntimeError):
    """Die Lernstandsdatei konnte nicht angelegt/gelesen werden, oder eine Eingabe
    (Grad, Ergebnis) war ungültig."""


@dataclass
class Topic:
    slug: str
    name: str
    gebiet: str | None
    grade: int
    last_query: date | None
    next_due: date | None
    typical_errors: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "thema"


def resolve_base_dir(repo: Path, skill_name: str, home: Path | None = None) -> tuple[Path, bool]:
    """Basisverzeichnis für ein nicht-projektgebundenes Artefakt (Spec 00 §1).

    Dasselbe Muster wie `verified-research/scripts/registry.py::resolve_base_dir`:
    Existiert `.skills/<skill_name>/` schon als Verzeichnis im Projekt, gilt der
    Override für alle Artefakte dieser Skill in diesem Lauf; sonst `~/.skills/<skill_name>/`.
    Parametrisiert über `skill_name`, weil learning-coach zwei verschiedene Basen
    braucht: die eigene (`learning-coach`, für `learner.md`) und die von
    verified-research (für den Aufgaben-Pfad aus E3).
    """
    home = home or Path.home()
    project_dir = repo / ".skills" / skill_name
    if project_dir.is_dir():
        return project_dir, True
    return home / ".skills" / skill_name, False


def learner_path_for(base_dir: Path) -> Path:
    return base_dir / "learner.md"


def exercises_path_for(repo: Path, slug: str, home: Path | None = None) -> Path:
    base_dir, _ = resolve_base_dir(repo, EXERCISES_SKILL_DIRNAME, home)
    return base_dir / "research" / f"{slug}.exercises.json"


def ensure_learner(repo: Path, assets_path: Path, home: Path | None = None) -> tuple[Path, bool]:
    """Liefert den Pfad zu `learner.md`, legt sie beim ersten Lauf aus dem Template an.

    Rückgabe: (Pfad, wurde_gerade_angelegt). Die Anlage wird auf stdout angekündigt —
    Bootstrap-Regel, Spec 00 §1: keine Skill legt ungefragt Dateien an, ohne den Pfad
    zu nennen.
    """
    base_dir, _ = resolve_base_dir(repo, SKILL_DIRNAME, home)
    path = learner_path_for(base_dir)
    if path.is_file():
        return path, False

    base_dir.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy(assets_path, path)
    except OSError as exc:
        raise DueTopicsError(f"Lernstandsdatei konnte nicht angelegt werden ({path}): {exc}") from exc
    print(f"Lernstandsdatei neu angelegt (erster Lauf) unter {path}")
    return path, True


def _parse_date(raw: str, field_name: str, warnings: list[str]) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        # E4: ein unlesbares Datum ist wie ein fehlendes zu behandeln — das Thema
        # bleibt fällig, statt stillschweigend als "nicht fällig" zu gelten.
        warnings.append(f"{field_name} unlesbar: {raw!r} — gilt als fehlend (Thema bleibt fällig)")
        return None


def _parse_grade(raw: str, warnings: list[str]) -> int:
    raw = raw.strip()
    if not raw:
        warnings.append("Beherrschungsgrad fehlt — als 0 angenommen")
        return 0
    try:
        value = int(raw)
    except ValueError:
        warnings.append(f"Beherrschungsgrad unlesbar: {raw!r} — als 0 angenommen")
        return 0
    if value < 0 or value > 4:
        clamped = max(0, min(4, value))
        warnings.append(f"Beherrschungsgrad {value} außerhalb 0-4 — auf {clamped} geklemmt")
        return clamped
    return value


def _parse_topic_block(heading_line: str, body: list[str]) -> Topic:
    warnings: list[str] = []
    match = TOPIC_HEADING_RE.match(heading_line)
    if match:
        slug, name = match.group("slug"), match.group("name").strip()
    else:
        title = heading_line[3:].strip() if heading_line.startswith("## ") else heading_line.strip()
        slug = slugify(title) if title else "thema"
        name = title or slug
        warnings.append(
            f"Kopfzeile ungültig: {heading_line!r} — erwartet '## <slug>: <Name>', "
            f"Slug abgeleitet: {slug!r}"
        )

    gebiet: str | None = None
    grade = 0
    grade_seen = False
    last_query: date | None = None
    next_due: date | None = None
    typical_errors: list[str] = []
    open_questions: list[str] = []
    list_target: list[str] | None = None

    for line in body:
        if not line.strip():
            list_target = None
            continue

        if list_target is not None:
            item_match = LIST_ITEM_RE.match(line)
            if item_match:
                list_target.append(item_match.group(1).strip())
                continue
            list_target = None  # Zeile gehört nicht mehr zur Liste — unten normal auswerten

        field_match = FIELD_LINE_RE.match(line)
        if not field_match:
            continue
        label, value = field_match.group(1).strip(), field_match.group(2)

        if label in LIST_LABELS:
            list_target = typical_errors if label == "Typische Fehler" else open_questions
        elif label == "Gebiet":
            gebiet = value.strip() or None
        elif label == "Beherrschungsgrad":
            grade = _parse_grade(value, warnings)
            grade_seen = True
        elif label == "Letzte Abfrage":
            last_query = _parse_date(value, "Letzte Abfrage", warnings)
        elif label == "Nächste Fälligkeit":
            next_due = _parse_date(value, "Nächste Fälligkeit", warnings)
        # Unbekannte Felder werden ignoriert statt als Fehler gewertet —
        # Vorwärtskompatibilität für Felder, die eine spätere Schema-Version ergänzt.

    if not grade_seen:
        warnings.append("Beherrschungsgrad fehlt — als 0 angenommen")

    return Topic(
        slug=slug, name=name, gebiet=gebiet, grade=grade,
        last_query=last_query, next_due=next_due,
        typical_errors=typical_errors, open_questions=open_questions, warnings=warnings,
    )


def parse_learner(text: str) -> tuple[list[Topic], list[str]]:
    """Parsen ist tolerant (A4): Ein fehlendes/unlesbares Feld erzeugt eine Warnung
    am Thema, nie einen Absturz. Rückgabe: (Themen, dateiweite Warnungen).

    HTML-Kommentare (Artefakt-Kopfzeile, Template-Beispiele) werden vor dem Scannen
    entfernt — sonst würde ein Beispiel-Thema aus einem `<!-- ... -->`-Block (wie im
    Template) als echtes Thema geparst.
    """
    text = HTML_COMMENT_RE.sub("", text)
    topics: list[Topic] = []
    current_heading: str | None = None
    current_body: list[str] = []

    def flush() -> None:
        if current_heading is not None:
            topics.append(_parse_topic_block(current_heading, current_body))

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current_heading = line.rstrip()
            current_body = []
        elif current_heading is not None:
            current_body.append(line)
    flush()

    file_warnings: list[str] = []
    counts: dict[str, int] = {}
    for topic in topics:
        counts[topic.slug] = counts.get(topic.slug, 0) + 1
    duplicates = sorted(slug for slug, count in counts.items() if count > 1)
    if duplicates:
        file_warnings.append(
            f"Doppelte Themen-Slugs: {', '.join(duplicates)} — beide Einträge bleiben erhalten, "
            f"Lernstandsdatei von Hand bereinigen"
        )

    return topics, file_warnings


def is_due(topic: Topic, today: date) -> bool:
    """E4: fehlendes oder unlesbares Datum (`next_due is None`) gilt als fällig."""
    return topic.next_due is None or topic.next_due <= today


def due_topics(topics: list[Topic], today: date) -> list[Topic]:
    """Fällige Themen, am überfälligsten zuerst; Themen ohne Datum zählen wie 'heute'."""
    due = [t for t in topics if is_due(t, today)]
    return sorted(due, key=lambda t: (t.next_due or today, t.slug))


def next_grade(grade: int, result: str) -> int:
    if result == "success":
        return min(4, grade + 1)
    if result == "failure":
        # Eigene Entscheidung (Spec-14-Open-Question "Herabstufung nach wie vielen
        # Fehlversuchen"): ein falscher Abruf senkt sofort um eine Stufe. Kein
        # Toleranz-Zähler, weil `learner.md` keinen separaten Fehlversuchs-Zähler
        # führt und "im Zweifel erinnern statt vergessen" (E4) für schnelles Sinken
        # statt langsames spricht.
        return max(0, grade - 1)
    raise DueTopicsError(f"result muss 'success' oder 'failure' sein, war {result!r}")


def next_interval(grade: int, result: str, today: date) -> tuple[int, date]:
    if grade not in INTERVAL_DAYS:
        raise DueTopicsError(f"grade muss 0-4 sein, war {grade!r}")
    new_grade = next_grade(grade, result)
    new_due = today + timedelta(days=INTERVAL_DAYS[new_grade])
    return new_grade, new_due


def _default_assets_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "learner-template.md"


def _cmd_due(args: argparse.Namespace) -> int:
    assets_path = args.assets or _default_assets_path()
    try:
        path, _ = ensure_learner(args.repo, assets_path)
    except DueTopicsError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Fehler: Lernstandsdatei nicht lesbar ({path}): {exc}", file=sys.stderr)
        return 2

    today = date.fromisoformat(args.today) if args.today else date.today()
    topics, file_warnings = parse_learner(text)

    print(f"Lernstandsdatei: {path}")
    for warning in file_warnings:
        print(f"Warnung: {warning}")

    if not topics:
        print("Keine Themen erfasst.")
        return 0

    due = due_topics(topics, today)
    print(f"{len(due)} von {len(topics)} Themen fällig.")

    if due:
        print("Fällig:")
        for topic in due:
            if topic.next_due is None:
                status = "ohne Fälligkeitsdatum, gilt als fällig"
            elif topic.next_due < today:
                status = f"{(today - topic.next_due).days} Tage überfällig"
            else:
                status = "heute fällig"
            print(f"- {topic.slug} ({topic.name}, Grad {topic.grade}) — {status}")
            for warning in topic.warnings:
                print(f"  Warnung: {warning}")
            ex_path = exercises_path_for(args.repo, topic.slug)
            if ex_path.is_file():
                print(f"  Aufgaben: {ex_path}")
            else:
                print(f"  Aufgaben: Keine verifizierten Aufgaben gefunden ({ex_path})")
        print("Abruf-Quiz-Budget: 2-4 Fragen aus den fälligen Themen.")

    not_due = sorted((t for t in topics if not is_due(t, today)), key=lambda t: (t.next_due, t.slug))
    if not_due:
        print("Nicht fällig:")
        for topic in not_due:
            assert topic.next_due is not None  # is_due() garantiert das für diesen Zweig
            print(f"- {topic.slug} ({topic.name}) — nächste Fälligkeit {topic.next_due.isoformat()}")

    return 0


def _cmd_interval(args: argparse.Namespace) -> int:
    today = date.fromisoformat(args.today) if args.today else date.today()
    try:
        new_grade, new_due = next_interval(args.grade, args.result, today)
    except DueTopicsError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2

    days = (new_due - today).days
    print(f"Grad: {args.grade} -> {new_grade} ({args.result})")
    if days <= 0:
        print(f"Nächste Fälligkeit: {new_due.isoformat()} (heute)")
    else:
        print(f"Nächste Fälligkeit: {new_due.isoformat()} (in {days} Tagen)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lernstand parsen, Fälligkeit und Spacing-Intervall berechnen (learning-coach)"
    )
    parser.add_argument("--repo", type=Path, default=Path("."))
    sub = parser.add_subparsers(dest="command", required=True)

    p_due = sub.add_parser("due", help="fällige Themen aus learner.md plus Aufgaben-Hinweis")
    p_due.add_argument("--today", help="YYYY-MM-DD, Default: heute")
    p_due.add_argument("--assets", type=Path, default=None, help="Quelle für den Bootstrap (Default: gebündeltes Template)")

    p_interval = sub.add_parser("interval", help="nächstes Spacing-Intervall berechnen")
    p_interval.add_argument("--grade", required=True, type=int, help="aktueller Beherrschungsgrad, 0-4")
    p_interval.add_argument("--result", required=True, choices=RESULTS)
    p_interval.add_argument("--today", help="YYYY-MM-DD, Default: heute")

    args = parser.parse_args(argv)
    if args.command == "due":
        return _cmd_due(args)
    if args.command == "interval":
        return _cmd_interval(args)
    return 2  # unerreichbar, argparse erzwingt eine bekannte Subcommand-Wahl


if __name__ == "__main__":
    sys.exit(main())
