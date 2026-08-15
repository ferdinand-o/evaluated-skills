#!/usr/bin/env python3
"""Quellenregister für verified-research: Lookup, Tier-Auskunft, neue Bewertungen
eintragen. Tier 1: nur Stdlib (R7 — PyYAML ist in dieser Umgebung nicht installiert,
das Register ist deshalb registry.json statt registry.yaml. Der Kommentar-Nutzen von
YAML wird durch das Pflichtfeld `notiz` je Eintrag ersetzt: der Bewertungsgrund steht
in den Daten statt daneben).

Dieses Skript kapselt jeden Zugriff auf das Register, damit eine spätere Umstellung
auf YAML eine Änderung an einer Stelle bleibt.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SKILL_DIRNAME = "verified-research"
SCHEMA_VERSION = 1
VALID_TIERS = (1, 2, 3)
MIN_NOTIZ_LEN = 15

# An rating-rubric.md angelehnt — add_entry() verlangt, dass die notiz mindestens
# eines dieser Kriterien benennt. Das zwingt die Begründung in die Daten (R7) statt
# einer beliebigen Freitext-Floskel wie "wirkt seriös".
RUBRIC_KEYWORDS = frozenset({
    "Primärquelle", "Primärstatus", "Sekundärquelle", "Sekundärbericht",
    "redaktionell", "redaktionelle", "Anreizlage", "Interessenkonflikt",
    "Track Record", "Aktualität",
})

# Ab dieser Zahl an Themen-Dateien unter research/ warnt die Skill (R10) — sie
# gliedert aber nicht automatisch um. Flach bleiben, bis es weh tut.
TOPIC_WARNING_THRESHOLD = 30


class RegistryError(RuntimeError):
    """Das Register konnte nicht gelesen, geschrieben oder erweitert werden."""


def resolve_base_dir(repo: Path, home: Path | None = None) -> tuple[Path, bool]:
    """Basisverzeichnis für Register und Wissensdateien dieser Skill.

    Spec 00 §1 sagt für nicht projektgebundene Artefakte: Standard ist `~/.skills/`,
    mit optionalem Projekt-Override, "falls eine gleichnamige Datei im Repo liegt".
    Wörtlich auf Datei-Ebene geprüft, bricht das bei `research/<thema>.md`: Die erste
    Recherche zu einem neuen Thema hat naturgemäß noch keine gleichnamige Datei im
    Projekt, der Override würde nie greifen, und der erste Schreibzugriff ginge nach
    `~` — im Eval-Harness das echte Home-Verzeichnis des Aufrufers (siehe
    docs/known-limits.md, Abschnitt "Isolation").

    Deshalb prüft diese Funktion auf Verzeichnis-Ebene: Existiert
    `.skills/verified-research/` bereits im Projekt (mit beliebigem Inhalt, und sei es
    nur die registry.json), gilt der Override für *alle* Artefakte dieser Skill in
    diesem Lauf. Sonst ist `~/.skills/verified-research/` die Basis.
    """
    home = home or Path.home()
    project_dir = repo / ".skills" / SKILL_DIRNAME
    if project_dir.is_dir():
        return project_dir, True
    return home / ".skills" / SKILL_DIRNAME, False


def registry_path_for(base_dir: Path) -> Path:
    return base_dir / "registry.json"


def research_dir_for(base_dir: Path) -> Path:
    return base_dir / "research"


def ensure_registry(repo: Path, assets_path: Path, home: Path | None = None) -> tuple[Path, bool]:
    """Liefert den Registerpfad, legt ihn beim allerersten Lauf an (Bootstrap-Regel).

    Rückgabe: (Pfad, wurde_gerade_angelegt). Die Anlage wird auf stdout angekündigt —
    keine Skill legt ungefragt Dateien an, ohne den Pfad zu nennen (Spec 00 §1).
    """
    base_dir, _ = resolve_base_dir(repo, home)
    path = registry_path_for(base_dir)
    if path.is_file():
        return path, False

    base_dir.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy(assets_path, path)
    except OSError as exc:
        raise RegistryError(f"Register konnte nicht angelegt werden ({path}): {exc}") from exc
    print(f"Register neu angelegt (erster Lauf) unter {path}")
    return path, True


def load_registry(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RegistryError(f"Register nicht gefunden: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RegistryError(f"Register ist kein gültiges JSON: {path}: {exc}") from exc


def save_registry(path: Path, data: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _iter_sections(data: dict):
    """(section_name, entry) über alle Domänen plus 'allgemein'."""
    for domain, entries in (data.get("domains") or {}).items():
        for entry in entries:
            yield domain, entry
    for entry in data.get("allgemein") or []:
        yield "allgemein", entry


def lookup(data: dict, needle: str) -> dict | None:
    """Bester (längster) Substring-Treffer über alle Domänen + allgemein, oder None."""
    if not needle:
        return None
    needle_lower = needle.lower()
    best: dict | None = None
    best_len = -1
    for domain, entry in _iter_sections(data):
        pattern = entry.get("pattern", "")
        if pattern and pattern.lower() in needle_lower and len(pattern) > best_len:
            best = {**entry, "domain": domain}
            best_len = len(pattern)
    return best


def _section_entries(data: dict, domain: str) -> list:
    if domain == "allgemein":
        return data.setdefault("allgemein", [])
    domains = data.setdefault("domains", {})
    return domains.setdefault(domain, [])


def add_entry(data: dict, *, domain: str, pattern: str, name: str, tier: int, notiz: str) -> dict:
    """Fügt einen neuen, begründeten Registereintrag hinzu und liefert ihn zurück.

    Wirft RegistryError bei jeder Verletzung des Contracts aus R7/rating-rubric.md:
    Tier außerhalb 1-3, leere/zu kurze notiz, notiz ohne Rubrik-Stichwort, oder ein
    pattern, das in dieser Domäne bereits existiert (Bewertung geschieht einmal, nicht
    bei jedem Lauf neu — ein Duplikat deutet auf eine vergessene Lookup-Phase hin).
    """
    if not domain or not isinstance(domain, str):
        raise RegistryError("domain fehlt oder ist leer")
    if not pattern or not isinstance(pattern, str):
        raise RegistryError("pattern fehlt oder ist leer")
    if not name or not isinstance(name, str):
        raise RegistryError("name fehlt oder ist leer")
    if tier not in VALID_TIERS:
        raise RegistryError(f"tier muss 1, 2 oder 3 sein, war {tier!r}")
    if not notiz or len(notiz.strip()) < MIN_NOTIZ_LEN:
        raise RegistryError(
            f"notiz fehlt oder ist zu kurz (mindestens {MIN_NOTIZ_LEN} Zeichen) — "
            f"der Bewertungsgrund gehört in die Daten (R7), nicht daneben"
        )
    if not any(keyword in notiz for keyword in RUBRIC_KEYWORDS):
        raise RegistryError(
            f"notiz nennt kein Rubrik-Kriterium aus {sorted(RUBRIC_KEYWORDS)} — "
            f"eine Bewertung ohne erkennbares Kriterium ist keine Bewertung"
        )

    entries = _section_entries(data, domain)
    for existing in entries:
        if existing.get("pattern", "").lower() == pattern.lower():
            raise RegistryError(f"pattern {pattern!r} existiert bereits in Domäne {domain!r}")

    entry = {"pattern": pattern, "name": name, "tier": tier, "notiz": notiz}
    entries.append(entry)
    return entry


def count_topics(research_dir: Path) -> int:
    if not research_dir.is_dir():
        return 0
    return len(list(research_dir.glob("*.md")))


def topic_warning(research_dir: Path) -> str | None:
    """Warnung ab TOPIC_WARNING_THRESHOLD Themen-Dateien — keine automatische Umgliederung."""
    count = count_topics(research_dir)
    if count >= TOPIC_WARNING_THRESHOLD:
        return (
            f"{count} Themen-Dateien unter {research_dir} — das ist mehr als "
            f"{TOPIC_WARNING_THRESHOLD}. Flach bleibt trotzdem der Standard (R10); "
            f"eine Hierarchie einzuführen ist eine bewusste Entscheidung des Nutzers, "
            f"keine, die diese Skill automatisch trifft."
        )
    return None


def _default_assets_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "registry.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quellenregister für verified-research")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--assets", type=Path, default=None, help="Quelle für den Bootstrap (Default: gebündelte registry.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_lookup = sub.add_parser("lookup", help="Quelle im Register nachschlagen")
    p_lookup.add_argument("needle", help="URL/Domain/Pfad, gegen den gesucht wird")

    p_add = sub.add_parser("add", help="neue Bewertung eintragen")
    p_add.add_argument("--domain", required=True)
    p_add.add_argument("--pattern", required=True)
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--tier", required=True, type=int)
    p_add.add_argument("--notiz", required=True)

    sub.add_parser("topics", help="Anzahl Themen-Dateien und ggf. Warnung")

    args = parser.parse_args(argv)
    assets_path = args.assets or _default_assets_path()

    try:
        path, _ = ensure_registry(args.repo, assets_path)
        base_dir, is_project_local = resolve_base_dir(args.repo)

        if args.command == "lookup":
            data = load_registry(path)
            hit = lookup(data, args.needle)
            if hit is None:
                print(f"Kein Registertreffer für {args.needle!r} — Tier 3 (freie Suche), neu bewerten und eintragen.")
                return 1
            print(json.dumps(hit, indent=2, ensure_ascii=False))
            return 0

        if args.command == "add":
            data = load_registry(path)
            entry = add_entry(
                data, domain=args.domain, pattern=args.pattern, name=args.name,
                tier=args.tier, notiz=args.notiz,
            )
            save_registry(path, data)
            scope = "projektlokal" if is_project_local else "global (~)"
            print(f"Eintrag ergänzt ({scope}, {path}): {json.dumps(entry, ensure_ascii=False)}")
            return 0

        if args.command == "topics":
            research_dir = research_dir_for(base_dir)
            count = count_topics(research_dir)
            warning = topic_warning(research_dir)
            print(f"{count} Themen-Dateien unter {research_dir}")
            if warning:
                print(f"Warnung: {warning}")
            return 0

    except RegistryError as exc:
        print(f"Register-Fehler: {exc}", file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    sys.exit(main())
