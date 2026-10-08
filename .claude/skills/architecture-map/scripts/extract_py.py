#!/usr/bin/env python3
"""Python-Import- und Klassengraph extrahieren. Tier 1: nur Stdlib (`ast`).

Ruling C1 (rulings-final-four.md, Spec 10): pyreverse/pydeps sind in dieser Umgebung
nicht installiert und für einen Import-Graphen auch nicht nötig — `ast.parse` liest die
Import-Knoten direkt aus dem Quelltext. Fremder Code wird nirgends importiert oder
ausgeführt (A3), nur statisch geparst.

Zwei Ebenen (C4-angelehnt, siehe references/c4-levels.md):
- `module`: der vollständige Import-Graph unter `--root`.
- `class`: nur für explizit übergebene `--files` (Hotspot-Beschränkung — ein
  Vollgraph auf Klassenebene ist unlesbar, siehe Spec 10 Approach).
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

SCHEMA_VERSION = 1
EXCLUDED_DIR_NAMES = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", ".skills", ".claude",
    ".mypy_cache", ".pytest_cache",
}


class ExtractError(RuntimeError):
    """Die Extraktion ist gescheitert — mit einer Ursache, die der Nutzer versteht."""


def discover_modules(root: Path) -> dict[str, Path]:
    """Alle `.py`-Dateien unter `root`, als Modul-ID -> Dateipfad.

    Ausgeschlossene Verzeichnisnamen werden komplett übersprungen, auch tief
    verschachtelt (z. B. `src/.venv/lib/...`).

    Review-Defekt D3: zwei physisch verschiedene Dateien können auf dieselbe
    Modul-ID abbilden (z. B. `a/b.py` und `a.b.py` im Wurzelverzeichnis liefern
    beide `a.b`). Ein `dict`, das die zweite Datei stillschweigend über die erste
    schreibt, verliert einen ganzen Knoten samt seiner Kanten unbemerkt — kein
    Exit-2 greift, weil `edges`/`external` meist trotzdem nicht leer sind. Eine
    Kollision ist deshalb ein harter Fehler, kein still aufgelöster Konflikt.
    """
    modules: dict[str, Path] = {}
    if not root.is_dir():
        return modules
    for path in sorted(root.rglob("*.py")):
        if any(part in EXCLUDED_DIR_NAMES for part in path.relative_to(root).parts[:-1]):
            continue
        module_id = module_id_for(path, root)
        if module_id in modules and modules[module_id] != path:
            raise ExtractError(
                f"Modul-ID-Kollision: sowohl {modules[module_id].relative_to(root)} als auch "
                f"{path.relative_to(root)} ergeben die ID {module_id!r} — welche Datei gemeint "
                "ist, lässt sich nicht sicher entscheiden"
            )
        modules[module_id] = path
    return modules


def module_id_for(path: Path, root: Path) -> str:
    """Dotted Modul-ID relativ zu `root`. `__init__.py` wird zum Paketnamen selbst."""
    rel = path.relative_to(root)
    parts = list(rel.parts)
    parts[-1] = parts[-1][:-3] if parts[-1].endswith(".py") else parts[-1]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        raise ExtractError(f"{path}: kann keine Modul-ID aus dem Wurzelverzeichnis selbst bilden")
    return ".".join(parts)


def extract_imports(path: Path) -> list[tuple[str | None, int, tuple[str, ...] | None]]:
    """Alle `Import`/`ImportFrom`-Knoten einer Datei, gleich wie tief verschachtelt.

    Liefert je Fundstelle `(dotted_module, relative_level, imported_names)`:
    - `Import` (`import a.b.c`): `("a.b.c", 0, None)` je Alias.
    - `ImportFrom` (`from a.b import c, d`): `("a.b", 0, ("c", "d"))`.
    - `ImportFrom` relativ (`from . import x`, `from ..pkg import y`):
      `level >= 1`, `dotted_module` kann `None`/leer sein.

    Eine Abhängigkeit zählt unabhängig davon, ob sie auf Modulebene steht oder in
    einer Funktion/Klasse verschachtelt ist — deshalb `ast.walk`, nicht nur
    `ast.iter_child_nodes(tree)`.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except SyntaxError as exc:
        raise ExtractError(f"{path}: kein gültiges Python ({exc})") from exc

    found: list[tuple[str | None, int, tuple[str, ...] | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, 0, None))
        elif isinstance(node, ast.ImportFrom):
            names = tuple(alias.name for alias in node.names if alias.name != "*")
            found.append((node.module, node.level, names or None))
    return found


def _resolve_base(importer_id: str, is_package: bool, dotted_module: str | None, level: int) -> str:
    """Absoluten Dotted-Präfix für eine Import-Anweisung bilden.

    `level == 0` heißt absolut: der Präfix ist `dotted_module` selbst. Für relative
    Importe (`level >= 1`) ist das aktuelle Paket der Ausgangspunkt — bei einem
    `__init__.py` das Modul selbst, sonst dessen Elternpaket — und `level - 1`
    zusätzliche Ebenen werden abgeschnitten (Python-Semantik für führende Punkte).
    """
    if level == 0:
        return dotted_module or ""

    parts = importer_id.split(".") if importer_id else []
    package_parts = parts if is_package else parts[:-1]
    up = level - 1
    base_parts = package_parts[: len(package_parts) - up] if up <= len(package_parts) else []
    base = ".".join(base_parts)
    if dotted_module:
        return f"{base}.{dotted_module}" if base else dotted_module
    return base


def build_candidates(
    importer_id: str, is_package: bool, dotted_module: str | None, level: int, imported_names: tuple[str, ...] | None
) -> list[str]:
    """Kandidaten für das Zielmodul, spezifischste zuerst.

    `from pkg import submodule` kann ein Submodul meinen (`pkg.submodule` existiert
    als Datei) oder einen Namen innerhalb von `pkg` (dann existiert nur `pkg`) — ohne
    Typinferenz ist das nicht sicher unterscheidbar, deshalb wird zuerst das
    spezifischste Submodul versucht und auf das Basispaket zurückgefallen.
    """
    base = _resolve_base(importer_id, is_package, dotted_module, level)
    candidates: list[str] = []
    if imported_names:
        candidates.extend(f"{base}.{name}" if base else name for name in imported_names)
    if base:
        candidates.append(base)
    return candidates


def resolve_import(candidates: list[str], known: dict[str, Path]) -> str | None:
    for candidate in candidates:
        if candidate in known:
            return candidate
    return None


def build_module_graph(root: Path) -> dict:
    """Reiner Import-Graph unter `root`: Knoten, Kanten, externe Top-Level-Pakete."""
    known = discover_modules(root)
    nodes = [
        {"id": module_id, "path": path.relative_to(root).as_posix(), "kind": "module"}
        for module_id, path in known.items()
    ]

    edges: set[tuple[str, str]] = set()
    external: set[str] = set()
    for module_id, path in known.items():
        is_package = path.name == "__init__.py"
        for dotted_module, level, imported_names in extract_imports(path):
            candidates = build_candidates(module_id, is_package, dotted_module, level, imported_names)
            if not candidates:
                continue
            target = resolve_import(candidates, known)
            if target is not None:
                if target != module_id:
                    edges.add((module_id, target))
            else:
                top = candidates[-1].split(".")[0]
                if top:
                    external.add(top)

    return {
        "language": "python",
        "level": "module",
        "nodes": sorted(nodes, key=lambda n: n["id"]),
        "edges": sorted(({"from": f, "to": t, "kind": "import"} for f, t in edges), key=lambda e: (e["from"], e["to"])),
        "external": sorted(external),
    }


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def extract_classes(files: list[Path], root: Path) -> dict:
    """Klassen + Vererbungskanten für explizit gewählte Hotspot-Dateien.

    Basisklassen werden nur über den einfachen (nicht voll qualifizierten) Namen
    innerhalb derselben Dateimenge aufgelöst — Basisklassen außerhalb der gewählten
    Dateien (z. B. `Exception`, `BaseModel`) bleiben unverknüpft. Das ist eine bewusste
    Grenze der Hotspot-Beschränkung, keine Fehlfunktion.

    Review-Anmerkung A1: Trägt derselbe Name innerhalb der gewählten Dateimenge zwei
    verschiedene Klassen (z. B. je eine `Config`-Klasse in zwei unabhängigen
    Hotspot-Dateien) und wird dieser Name als Basisklasse referenziert, ist nicht
    sicher entscheidbar, welche gemeint ist — eine stillschweigend geratene Kante
    verletzt den Contract ("jede Struktur-Behauptung ist graph-belegt") ohne jede
    Fehlermeldung. Ein solcher Fall bricht die Extraktion hart ab, statt zu raten.
    Zwei gleichnamige, nie als Basis referenzierte Klassen bleiben dagegen erlaubt.
    """
    nodes: list[dict] = []
    name_occurrences: dict[str, list[str]] = {}
    per_file_classes: dict[Path, list[ast.ClassDef]] = {}

    for file in files:
        try:
            tree = ast.parse(file.read_text(encoding="utf-8", errors="replace"), filename=str(file))
        except SyntaxError as exc:
            raise ExtractError(f"{file}: kein gültiges Python ({exc})") from exc
        module_id = module_id_for(file, root)
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        per_file_classes[file] = classes
        for cls in classes:
            class_id = f"{module_id}.{cls.name}"
            nodes.append({"id": class_id, "path": file.relative_to(root).as_posix(), "kind": "class"})
            name_occurrences.setdefault(cls.name, []).append(class_id)

    edges: set[tuple[str, str]] = set()
    for file, classes in per_file_classes.items():
        module_id = module_id_for(file, root)
        for cls in classes:
            class_id = f"{module_id}.{cls.name}"
            for base in cls.bases:
                base_name = _base_name(base)
                if not base_name:
                    continue
                occurrences = name_occurrences.get(base_name, [])
                if len(occurrences) > 1:
                    raise ExtractError(
                        f"Klassenname {base_name!r} ist unter den gewählten Hotspot-Dateien mehrfach "
                        f"vergeben ({', '.join(occurrences)}) und wird von {class_id} als Basisklasse "
                        "referenziert — welche gemeint ist, lässt sich ohne Modul-Qualifizierung nicht "
                        "sicher entscheiden"
                    )
                if len(occurrences) == 1 and occurrences[0] != class_id:
                    edges.add((class_id, occurrences[0]))

    return {
        "language": "python",
        "level": "class",
        "nodes": sorted(nodes, key=lambda n: n["id"]),
        "edges": sorted(({"from": f, "to": t, "kind": "inherits"} for f, t in edges), key=lambda e: (e["from"], e["to"])),
        "external": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Python-Import-/Klassengraph extrahieren")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--level", choices=("module", "class"), default="module")
    parser.add_argument("--files", nargs="+", help="nur für --level class: Hotspot-Dateien relativ zu --root")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    command_parts = [f"--root {args.root}", f"--level {args.level}"]
    if args.files:
        command_parts.append("--files " + " ".join(args.files))

    try:
        if args.level == "module":
            known_count = len(discover_modules(args.root))
            graph = build_module_graph(args.root)
        else:
            if not args.files:
                raise ExtractError("--level class braucht --files")
            files = [args.root / f for f in args.files]
            known_count = len(files)
            graph = extract_classes(files, args.root)
    except ExtractError as exc:
        print(f"Extraktion gescheitert: {exc}", file=sys.stderr)
        return 1

    # sys.argv[0] statt eines hartkodierten Pfads: die Skill kann unter
    # `skills/architecture-map/` (dieses Repo) oder `.claude/skills/architecture-map/`
    # (Standard-Installation, z. B. im Eval-Harness) liegen. drift_check.py führt dieses
    # Kommando später erneut aus — ein falscher hartkodierter Pfad wäre dort nicht nur
    # eine kosmetische Ungenauigkeit, sondern ein Fehlschlag beim Regenerieren.
    graph["_meta"] = {
        "skill": "architecture-map",
        "schema": SCHEMA_VERSION,
        "generated": f"python {sys.argv[0]} " + " ".join(command_parts) + f" --out {args.out}",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")

    # A4: Null Kanten/Knoten aus einer nicht-leeren Eingabe ist ein Befund, kein
    # stiller Erfolg. Ein leeres --root (0 Module gefunden) ist dagegen kein Fehler.
    # Bei --level module heißt "null" konkret: nicht ein einziger Import — weder
    # intern noch extern — wurde in irgendeiner der gefundenen Dateien erkannt. Ein
    # legitimer Zwei-Datei-Mini-Fall ohne Cross-Import ist selten genug, dass das
    # weiterhin ein meldenswertes Signal ist statt eines plausiblen Normalfalls.
    empty_result = args.level == "module" and known_count > 0 and not graph["edges"] and not graph["external"]
    no_classes_found = args.level == "class" and known_count > 0 and not graph["nodes"]
    if empty_result or no_classes_found:
        print(
            f"Extraktion ergab null Ergebnisse bei {known_count} untersuchten Dateien — "
            "das ist ein Befund, keine leere Codebase. Root/Files prüfen.",
            file=sys.stderr,
        )
        return 2

    print(f"{len(graph['nodes'])} Knoten, {len(graph['edges'])} Kanten -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
