#!/usr/bin/env python3
"""Graphen neu extrahieren, mit dem `ARCHITECTURE.md`-Stand vergleichen. Tier 1: nur
Stdlib. Meldet Abweichungen, schreibt nie — die Bootstrap-/Degradations-Regel aus
Spec 00 §1 verbietet ungefragte Schreibzugriffe, und ein Auto-Commit von Diagrammen
wäre genau das (Spec 10, Abschnitt Drift-Check).

Kein separater Graph-Speicher nötig: `to_mermaid.py`s Format ist verlustfrei für
Knoten-IDs und Kanten, also liest `read_mermaid_blocks` + `to_mermaid.parse` den
zuletzt committeten Graphen direkt aus dem bereits committeten Markdown zurück. Der
Footer-Block `<!-- architecture-map:graph-hashes ... -->` trägt nur den Hash (schneller
Kurzschluss: kein Drift -> kein Parsen, kein Diff) und das Kommando, mit dem jede
Ebene ursprünglich extrahiert wurde.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
import to_mermaid  # noqa: E402  (Sibling-Skript, kein Paket — siehe Modulkommentar)

FOOTER_RE = re.compile(r"<!--\s*architecture-map:graph-hashes\s*([\s\S]*?)-->")
MERMAID_BLOCK_RE = re.compile(r"```mermaid\n([\s\S]*?)```")
HEADER_CMD_RE = re.compile(r"^%%\s*skill:\s*architecture-map\s*\|\s*schema:\s*\d+\s*\|\s*generated:\s*(.+?)\s*$", re.MULTILINE)


class DriftCheckError(RuntimeError):
    """Der Drift-Check konnte nicht sauber urteilen — mit benannter Ursache."""


def graph_hash(graph: dict) -> str:
    """sha256 über kanonisiertes Graph-JSON, ohne `_meta` — sonst ändert sich der
    Hash bei jedem Lauf allein durch das im Kommando enthaltene `--out`/Zeitstempel."""
    nodes = sorted(n["id"] for n in graph.get("nodes", []))
    edges = sorted((e["from"], e["to"]) for e in graph.get("edges", []))
    payload = json.dumps({"nodes": nodes, "edges": edges}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_footer(text: str) -> dict | None:
    """`{"<level>": {"command": str, "graph_hash": str}}` aus dem Footer, oder `None`
    ohne Footer. Ein vorhandener, aber kaputter Footer ist ein Fehler, kein `None`."""
    match = FOOTER_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise DriftCheckError(f"graph-hashes-Footer ist kein gültiges JSON: {exc}") from exc


def read_mermaid_blocks(text: str) -> dict[str, str]:
    """Mermaid-Fences, geschlüsselt über das Erzeugungskommando aus ihrem
    `%%`-Header — genau der String, der auch im Footer als `command` steht."""
    blocks: dict[str, str] = {}
    for match in MERMAID_BLOCK_RE.finditer(text):
        block_text = match.group(1)
        header_match = HEADER_CMD_RE.search(block_text)
        if header_match:
            blocks[header_match.group(1).strip()] = block_text
    return blocks


def diff_graph(old_nodes: set[str], old_edges: set[tuple[str, str]], new_graph: dict) -> dict:
    new_nodes = {n["id"] for n in new_graph.get("nodes", [])}
    new_edges = {(e["from"], e["to"]) for e in new_graph.get("edges", [])}
    return {
        "nodes_added": sorted(new_nodes - old_nodes),
        "nodes_removed": sorted(old_nodes - new_nodes),
        "edges_added": sorted(new_edges - old_edges),
        "edges_removed": sorted(old_edges - new_edges),
    }


def regenerate_graph(command: str, cwd: Path) -> dict:
    """Das im Footer gespeicherte Extraktionskommando erneut ausführen und das
    resultierende Graph-JSON von seinem `--out`-Pfad einlesen."""
    parts = shlex.split(command)
    if "--out" not in parts:
        raise DriftCheckError(f"Kommando ohne '--out', Ergebnis nicht lesbar: {command}")
    out_arg = Path(parts[parts.index("--out") + 1])
    out_path = out_arg if out_arg.is_absolute() else cwd / out_arg

    # Vorab prüfen statt aus dem Subprocess-Exit-Code raten: das Extraktions-Skript
    # selbst beendet sich bei "null Ergebnisse" ebenfalls mit Exit 2 (A4) — ein
    # falsches 'cwd' (Skript unter diesem Pfad nicht auffindbar) beendet sich beim
    # System-Python ebenfalls mit 2. Ohne diese Prüfung würde ein zufällig noch
    # vorhandenes altes `--out` stillschweigend als frisches Ergebnis gelesen.
    if len(parts) < 2:
        raise DriftCheckError(f"Kommando zu kurz, kein Skriptpfad erkennbar: {command}")
    script_arg = Path(parts[1])
    script_path = script_arg if script_arg.is_absolute() else cwd / script_arg
    if not script_path.is_file():
        raise DriftCheckError(f"Skript nicht gefunden: {script_path} (cwd={cwd}) — 'cwd' beim Aufruf korrekt gesetzt?")

    try:
        completed = subprocess.run(parts, cwd=cwd, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise DriftCheckError(f"Regenerieren konnte nicht gestartet werden ({command}): {exc}") from exc
    # Exit 2 bei den Extraktions-Skripten heißt "null Ergebnisse gefunden" (A4) — die
    # Datei wurde trotzdem geschrieben und ist lesbar. Nur Exit 1 (Extraktion selbst
    # gescheitert) ist ein harter Fehler ohne verwertbares Ergebnis.
    if completed.returncode == 1:
        raise DriftCheckError(f"Regenerieren fehlgeschlagen ({command}): {completed.stderr.strip()}")
    if not out_path.is_file():
        raise DriftCheckError(f"Regenerieren lieferte keine Datei unter {out_path}")
    return json.loads(out_path.read_text(encoding="utf-8"))


def check(architecture_md_path: Path, cwd: Path | None = None) -> dict:
    """Pro Footer-Eintrag: neu extrahieren, Hash vergleichen, bei Abweichung diffen.

    `cwd` ist das Arbeitsverzeichnis für die im Footer gespeicherten Kommandos — sie
    referenzieren die Extraktions-Skripte repo-relativ (`skills/architecture-map/
    scripts/extract_py.py ...`), genau wie beim ursprünglichen Aufruf aus der SKILL.md.
    Default ist das aktuelle Arbeitsverzeichnis, **nicht** das Verzeichnis von
    `architecture_md_path` — das Dokument liegt pro Service (Ruling C3), die Skripte
    aber immer relativ zum Repo-Root.

    Schreibt an keiner Stelle auf `architecture_md_path` — Drift wird gemeldet, nicht
    behoben.
    """
    cwd = cwd if cwd is not None else Path(".")
    text = architecture_md_path.read_text(encoding="utf-8")
    footer = read_footer(text)
    if footer is None:
        raise DriftCheckError(
            f"{architecture_md_path}: kein 'architecture-map:graph-hashes'-Footer gefunden — "
            "Dokument stammt nicht aus dieser Skill oder ist älter als der Drift-Check"
        )
    blocks = read_mermaid_blocks(text)

    results: dict[str, dict] = {}
    any_drift = False
    for level_key, entry in footer.items():
        command = entry.get("command")
        stored_hash = entry.get("graph_hash")
        if not command or not stored_hash:
            results[level_key] = {"status": "error", "detail": "Footer-Eintrag ohne 'command'/'graph_hash'"}
            any_drift = True
            continue
        try:
            new_graph = regenerate_graph(command, cwd)
        except DriftCheckError as exc:
            results[level_key] = {"status": "error", "detail": str(exc)}
            any_drift = True
            continue

        new_hash = graph_hash(new_graph)
        if new_hash == stored_hash:
            results[level_key] = {"status": "unchanged"}
            continue

        any_drift = True
        old_block = blocks.get(command)
        if old_block is None:
            results[level_key] = {
                "status": "drift",
                "detail": "Hash weicht ab, aber kein passender Mermaid-Block im Dokument gefunden — kein Kanten-Diff möglich",
            }
            continue
        old_nodes, old_edges = to_mermaid.parse(old_block)
        results[level_key] = {"status": "drift", "diff": diff_graph(old_nodes, old_edges, new_graph)}

    return {"any_drift": any_drift, "levels": results}


def _format_report(result: dict) -> str:
    lines = []
    for level, entry in sorted(result["levels"].items()):
        if entry["status"] == "unchanged":
            lines.append(f"{level}: unverändert")
        elif entry["status"] == "error":
            lines.append(f"{level}: FEHLER — {entry['detail']}")
        else:
            diff = entry.get("diff")
            if diff is None:
                lines.append(f"{level}: DRIFT — {entry['detail']}")
            else:
                lines.append(
                    f"{level}: DRIFT — Knoten +{len(diff['nodes_added'])}/-{len(diff['nodes_removed'])}, "
                    f"Kanten +{len(diff['edges_added'])}/-{len(diff['edges_removed'])}"
                )
                for node in diff["nodes_added"]:
                    lines.append(f"    + Knoten {node}")
                for node in diff["nodes_removed"]:
                    lines.append(f"    - Knoten {node}")
                for frm, to in diff["edges_added"]:
                    lines.append(f"    + Kante {frm} -> {to}")
                for frm, to in diff["edges_removed"]:
                    lines.append(f"    - Kante {frm} -> {to}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARCHITECTURE.md gegen den aktuellen Code auf Drift prüfen")
    parser.add_argument("--doc", type=Path, help="Drift-Check-Modus: bestehendes ARCHITECTURE.md prüfen")
    parser.add_argument("--graph", type=Path, help="Hash-Modus: nur den graph_hash für ein Graph-JSON ausgeben (zum Bauen des Footer-Blocks)")
    parser.add_argument("--cwd", type=Path, help="Arbeitsverzeichnis für die Extraktions-Kommandos (Default: aktuelles Arbeitsverzeichnis)")
    args = parser.parse_args(argv)

    if args.graph and args.doc:
        print("--doc und --graph schließen sich aus", file=sys.stderr)
        return 1
    if args.graph:
        graph = json.loads(args.graph.read_text(encoding="utf-8"))
        print(graph_hash(graph))
        return 0
    if not args.doc:
        print("entweder --doc (Drift-Check) oder --graph (Hash ausgeben) angeben", file=sys.stderr)
        return 1

    try:
        result = check(args.doc, cwd=args.cwd)
    except DriftCheckError as exc:
        print(f"Drift-Check gescheitert: {exc}", file=sys.stderr)
        return 1

    print(_format_report(result))
    return 1 if result["any_drift"] else 0


if __name__ == "__main__":
    sys.exit(main())
