#!/usr/bin/env python3
"""TypeScript/JavaScript-Import-Graph via Textsuche. Tier 1: nur Stdlib.

Ruling C2 (rulings-final-four.md, Spec 10): ts-morph und `npx` sind in dieser Umgebung
nicht installiert und nicht zu installieren (A1). Spec 10 erlaubt ausdrücklich die
Alternative — eine Tier-1-Textsuche nach `import`/`require`/`export ... from` — unter der
Bedingung, die Ungenauigkeit klar zu benennen:

- **Kein echter Parser.** Es gibt keine Typauflösung, keine Auflösung von
  tsconfig-Pfad-Aliasen (`@app/*`), keine Kenntnis von Barrel-Re-Exports jenseits des
  Dateinamens.
- **String-/Kommentar-Rauschen.** Kommentare werden vor dem Suchen entfernt, aber ein
  Treffer in einem String-Literal, das zufällig wie ein Import aussieht, bleibt eine
  bekannte Fehlerquelle.
- **Keine Klassenebene für TypeScript in v1** (Out of scope, siehe SKILL.md).

Diese Datei ist bewusst als "erprobt, aber ungenau" markiert, nie als vollwertiger
Ersatz für einen echten Parser.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
EXCLUDED_DIR_NAMES = {".git", "node_modules", "dist", "build", ".next", "coverage", ".skills"}
SUFFIXES = (".ts", ".tsx", ".js", ".jsx")


class ExtractError(RuntimeError):
    """Die Extraktion ist gescheitert — mit einer Ursache, die der Nutzer versteht."""


COMMENT_BLOCK_RE = re.compile(r"/\*[\s\S]*?\*/")
COMMENT_LINE_RE = re.compile(r"//[^\n]*")
IMPORT_FROM_RE = re.compile(r"""\bimport\s[\s\S]*?\bfrom\s+['"]([^'"]+)['"]""")
IMPORT_BARE_RE = re.compile(r"""\bimport\s+['"]([^'"]+)['"]""")
EXPORT_FROM_RE = re.compile(r"""\bexport\s[\s\S]*?\bfrom\s+['"]([^'"]+)['"]""")
REQUIRE_RE = re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)""")
DYNAMIC_IMPORT_RE = re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)""")


def discover_modules(root: Path) -> dict[str, Path]:
    """Alle TS/TSX/JS/JSX-Dateien unter `root`, als Modul-ID -> Dateipfad."""
    modules: dict[str, Path] = {}
    if not root.is_dir():
        return modules
    for path in sorted(root.rglob("*")):
        if path.suffix not in SUFFIXES or not path.is_file():
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in path.relative_to(root).parts[:-1]):
            continue
        modules[module_id_for(path, root)] = path
    return modules


def module_id_for(path: Path, root: Path) -> str:
    """Dotted Modul-ID relativ zu `root`. `index.<ext>` wird zum Verzeichnisnamen selbst."""
    rel = path.relative_to(root)
    parts = list(rel.parts)
    parts[-1] = parts[-1][: -len(path.suffix)]
    if parts[-1] == "index" and len(parts) > 1:
        parts = parts[:-1]
    return ".".join(parts)


def _strip_comments(text: str) -> str:
    """Block- und Zeilenkommentare entfernen — die dokumentierte Hauptfehlerquelle
    (Import-Wortlaut in Kommentaren) wird dadurch verhindert, String-Literale bleiben
    eine bekannte Restlücke."""
    return COMMENT_LINE_RE.sub("", COMMENT_BLOCK_RE.sub("", text))


def extract_specifiers(text: str) -> list[str]:
    """Alle Import-/Require-Spezifizierer einer Datei, als Rohtext (noch unaufgelöst)."""
    clean = _strip_comments(text)
    specifiers: list[str] = []
    specifiers.extend(IMPORT_FROM_RE.findall(clean))
    specifiers.extend(IMPORT_BARE_RE.findall(clean))
    specifiers.extend(EXPORT_FROM_RE.findall(clean))
    specifiers.extend(REQUIRE_RE.findall(clean))
    specifiers.extend(DYNAMIC_IMPORT_RE.findall(clean))
    return specifiers


def _relative_candidates(importer_path: Path, specifier: str, root: Path) -> list[str]:
    """Mögliche relative Pfade (als Posix-String relativ zu `root`) für einen
    relativen Spezifizierer, spezifischste zuerst: mit Extension direkt, sonst
    Datei-mit-Extension und `index.<ext>` im Verzeichnis (Node-Resolution-Konvention)."""
    importer_rel = importer_path.relative_to(root).as_posix()
    base_dir = posixpath.dirname(importer_rel)
    target = posixpath.normpath(posixpath.join(base_dir, specifier))

    if target.endswith(SUFFIXES):
        return [target]
    return [target + ext for ext in SUFFIXES] + [f"{target}/index{ext}" for ext in SUFFIXES]


def resolve_specifier(importer_path: Path, specifier: str, root: Path, known_by_relpath: dict[str, str]) -> str | None:
    """Internes Zielmodul für einen relativen Spezifizierer, oder `None` (nicht auffindbar).

    Nur `./` und `../` werden aufgelöst — Paket-Spezifizierer sind grundsätzlich extern
    (`resolve_specifier` wird für sie gar nicht aufgerufen, siehe `build_module_graph`).
    """
    for candidate in _relative_candidates(importer_path, specifier, root):
        if candidate in known_by_relpath:
            return known_by_relpath[candidate]
    return None


def _external_name(specifier: str) -> str:
    """Top-Level-Paketname eines externen Spezifizierers (`@scope/pkg` bleibt zusammen)."""
    parts = specifier.split("/")
    if specifier.startswith("@") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def build_module_graph(root: Path) -> dict:
    known = discover_modules(root)
    known_by_relpath = {path.relative_to(root).as_posix(): module_id for module_id, path in known.items()}
    nodes = [
        {"id": module_id, "path": path.relative_to(root).as_posix(), "kind": "module"}
        for module_id, path in known.items()
    ]

    edges: set[tuple[str, str]] = set()
    external: set[str] = set()
    for module_id, path in known.items():
        text = path.read_text(encoding="utf-8", errors="replace")
        for specifier in extract_specifiers(text):
            if specifier.startswith("./") or specifier.startswith("../"):
                target = resolve_specifier(path, specifier, root, known_by_relpath)
                if target is not None and target != module_id:
                    edges.add((module_id, target))
                # Unauflösbarer relativer Pfad: keine Datei gefunden, weder Kante noch
                # externes Paket — wird stillschweigend übersprungen (bekannte Grenze).
            else:
                external.add(_external_name(specifier))

    return {
        "language": "typescript",
        "level": "module",
        "nodes": sorted(nodes, key=lambda n: n["id"]),
        "edges": sorted(({"from": f, "to": t, "kind": "import"} for f, t in edges), key=lambda e: (e["from"], e["to"])),
        "external": sorted(external),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TS/JS-Import-Graph via Textsuche extrahieren (Tier 1, ungenau)")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    known_count = len(discover_modules(args.root))
    graph = build_module_graph(args.root)
    graph["_meta"] = {
        "skill": "architecture-map",
        "schema": SCHEMA_VERSION,
        "generated": f"python skills/architecture-map/scripts/extract_ts.py --root {args.root} --out {args.out}",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")

    if known_count > 0 and not graph["edges"] and not graph["external"]:
        print(
            f"Extraktion ergab null Ergebnisse bei {known_count} untersuchten Dateien — "
            "das ist ein Befund, keine leere Codebase. Root prüfen.",
            file=sys.stderr,
        )
        return 2

    print(f"{len(graph['nodes'])} Knoten, {len(graph['edges'])} Kanten -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
