#!/usr/bin/env python3
"""Graph-JSON -> deterministischer Mermaid-Block. Tier 1: nur Stdlib.

Ruling C4: der Graph wird generiert, nie von Hand gezeichnet — das ist der
Drift-Schutz, der Grund für die Skill. Knoten sind nach `id` sortiert, Kanten nach
`(from, to)`; zwei Läufe über denselben Graphen erzeugen exakt denselben Text, egal in
welcher Reihenfolge Extraktion die Listen geliefert hat. Das eigene Format ist bewusst
so einfach gehalten, dass `parse()` es verlustfrei zurückliest — `drift_check.py`
braucht dafür keinen separaten Graph-Speicher, das committete Markdown reicht.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

NODE_LINE_RE = re.compile(r'^\s*(\w+)\["(.*)"\]\s*$')
EDGE_LINE_RE = re.compile(r'^\s*(\w+)\s*-->\s*(\w+)\s*$')
_INVALID_CHARS_RE = re.compile(r"[^A-Za-z0-9_]")


def sanitize_id(node_id: str) -> str:
    """Mermaid-taugliche ID aus einer Graph-Knoten-ID. Kollisionen (verschiedene
    Original-IDs, gleiches Sanitize-Ergebnis) löst `render()` separat auf — diese
    Funktion kennt nur eine einzelne ID."""
    sane = _INVALID_CHARS_RE.sub("_", node_id)
    if not sane or sane[0].isdigit():
        sane = f"n_{sane}"
    return sane


def _assign_ids(node_ids: list[str]) -> dict[str, str]:
    """Kollisionsfreie Sanitize-Zuordnung, deterministisch nach sortierter Eingabe."""
    used: set[str] = set()
    mapping: dict[str, str] = {}
    for node_id in node_ids:
        base = sanitize_id(node_id)
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}__{suffix}"
            suffix += 1
        used.add(candidate)
        mapping[node_id] = candidate
    return mapping


def render(graph: dict) -> str:
    """Vollständiger ` ```mermaid ` -Block mit Erzeugungskommando im Header-Kommentar
    (Spec 10 Contract: jedes Diagramm trägt sein Kommando)."""
    meta = graph.get("_meta") or {}
    generated = meta.get("generated")
    if not generated:
        raise ValueError("render() braucht graph['_meta']['generated'] für den Header-Kommentar")
    schema = meta.get("schema", 1)

    nodes = sorted(graph.get("nodes", []), key=lambda n: n["id"])
    edges = sorted(graph.get("edges", []), key=lambda e: (e["from"], e["to"]))
    mapping = _assign_ids([n["id"] for n in nodes])

    lines = [
        "```mermaid",
        f"%% skill: architecture-map | schema: {schema} | generated: {generated}",
        "flowchart LR",
    ]
    for node in nodes:
        lines.append(f'    {mapping[node["id"]]}["{node["id"]}"]')
    for edge in edges:
        frm = mapping.get(edge["from"], sanitize_id(edge["from"]))
        to = mapping.get(edge["to"], sanitize_id(edge["to"]))
        lines.append(f"    {frm} --> {to}")
    lines.append("```")
    return "\n".join(lines) + "\n"


def parse(mermaid_text: str) -> tuple[set[str], set[tuple[str, str]]]:
    """Eigenes Format zurücklesen: (Original-Knoten-IDs, (from, to)-Kanten mit
    Original-IDs). Nur Zeilen im von `render()` erzeugten Format werden erkannt."""
    id_to_label: dict[str, str] = {}
    raw_edges: list[tuple[str, str]] = []
    for line in mermaid_text.splitlines():
        node_match = NODE_LINE_RE.match(line)
        if node_match:
            id_to_label[node_match.group(1)] = node_match.group(2)
            continue
        edge_match = EDGE_LINE_RE.match(line)
        if edge_match:
            raw_edges.append((edge_match.group(1), edge_match.group(2)))

    nodes = set(id_to_label.values())
    edges = {(id_to_label.get(a, a), id_to_label.get(b, b)) for a, b in raw_edges}
    return nodes, edges


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Graph-JSON deterministisch nach Mermaid rendern")
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="fehlt: Ausgabe auf stdout")
    args = parser.parse_args(argv)

    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    block = render(graph)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(block, encoding="utf-8")
        print(f"Mermaid-Block -> {args.out}")
    else:
        print(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
