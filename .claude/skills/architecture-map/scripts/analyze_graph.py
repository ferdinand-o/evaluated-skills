#!/usr/bin/env python3
"""Graph-JSON -> Befund-JSON: Zyklen, Fan-in/Fan-out-Ausreißer, Schichtverletzungen,
tote Module. Tier 1: nur Stdlib. Alles hier ist aus dem Graphen deterministisch
ableitbar — kein LLM-Urteil an dieser Stelle (Spec 10 Contract: jeder Befund stammt
aus `analyze_graph.py`, das LLM darf ihn nur einordnen).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_FAN_IN_THRESHOLD = 10
DEFAULT_FAN_OUT_THRESHOLD = 10
DEFAULT_ENTRY_PATTERNS = ("__main__", "main", "cli", "app", "index")


def _adjacency(graph: dict) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {}
    for edge in graph.get("edges", []):
        adj.setdefault(edge["from"], []).append(edge["to"])
    return adj


def find_cycles(graph: dict) -> list[list[str]]:
    """Starke Zusammenhangskomponenten (Tarjan) mit Größe >= 2, plus Selbstkanten.

    Rekursiv implementiert — für die Größenordnung typischer Modulgraphen (hunderte,
    nicht zehntausende Knoten) unproblematisch; sehr lange azyklische Ketten könnten
    Pythons Rekursionslimit erreichen, das ist eine bekannte Grenze dieser Tier-1-
    Implementierung, kein stiller Fehler (sie wirft `RecursionError`, statt falsche
    Ergebnisse zu liefern).
    """
    node_ids = sorted({n["id"] for n in graph.get("nodes", [])} | {e["from"] for e in graph.get("edges", [])} | {e["to"] for e in graph.get("edges", [])})
    adj = _adjacency(graph)
    self_loops = {e["from"] for e in graph.get("edges", []) if e["from"] == e["to"]}

    index_counter = [0]
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    stack: list[str] = []
    sccs: list[list[str]] = []

    def strongconnect(v: str) -> None:
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True
        for w in sorted(adj.get(v, [])):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w):
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            component: list[str] = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                component.append(w)
                if w == v:
                    break
            sccs.append(component)

    for node in node_ids:
        if node not in index:
            strongconnect(node)

    cycles = [
        sorted(comp) for comp in sccs
        if len(comp) >= 2 or (len(comp) == 1 and comp[0] in self_loops)
    ]
    cycles.sort(key=lambda c: (c[0], len(c), c))
    return cycles


def fan_in_out(graph: dict) -> dict[str, dict[str, int]]:
    counts = {n["id"]: {"in": 0, "out": 0} for n in graph.get("nodes", [])}
    for edge in graph.get("edges", []):
        counts.setdefault(edge["from"], {"in": 0, "out": 0})["out"] += 1
        counts.setdefault(edge["to"], {"in": 0, "out": 0})["in"] += 1
    return counts


def find_outliers(graph: dict, layers_cfg: dict | None) -> list[dict]:
    """Fan-in-/Fan-out-Ausreißer gegen Schwellen aus `layers_cfg["thresholds"]`,
    sonst gegen die eingebauten Defaults (10/10) — konfigurierbar gehört in die
    Konfiguration (Spec 10 Approach), aber eine fehlende Konfiguration darf die
    Prüfung nicht stillschweigend abschalten."""
    thresholds = (layers_cfg or {}).get("thresholds", {})
    fan_in_threshold = thresholds.get("fan_in", DEFAULT_FAN_IN_THRESHOLD)
    fan_out_threshold = thresholds.get("fan_out", DEFAULT_FAN_OUT_THRESHOLD)

    counts = fan_in_out(graph)
    outliers = []
    for node_id in sorted(counts):
        c = counts[node_id]
        if c["in"] > fan_in_threshold:
            outliers.append({"id": node_id, "reason": "fan_in", "value": c["in"], "threshold": fan_in_threshold})
        if c["out"] > fan_out_threshold:
            outliers.append({"id": node_id, "reason": "fan_out", "value": c["out"], "threshold": fan_out_threshold})
    return sorted(outliers, key=lambda o: (o["id"], o["reason"]))


def find_layer_violations(graph: dict, layers_cfg: dict | None) -> list[dict] | None:
    """`None` heißt "ungeprüft", nicht "sauber" (A4) — nur bei fehlender `layers_cfg`.

    `layers_cfg["order"]` ist von innen nach außen sortiert (Index 0 = innerste
    Schicht, z. B. `domain`). Erlaubt ist nur eine Kante von gleichem oder höherem
    Index zu niedrigerem (außen -> innen); eine Kante nach außen (niedriger Index ->
    höherer Index) ist die Dependency-Rule-Verletzung.
    """
    if not layers_cfg:
        return None

    order = layers_cfg.get("order") or []
    rank = {name: i for i, name in enumerate(order)}
    prefixes = layers_cfg.get("layers") or {}

    node_layer: dict[str, str | None] = {}
    for node in graph.get("nodes", []):
        path = node.get("path", "")
        layer = next((name for name, prefix in prefixes.items() if path.startswith(prefix)), None)
        node_layer[node["id"]] = layer

    violations = []
    for edge in graph.get("edges", []):
        from_layer = node_layer.get(edge["from"])
        to_layer = node_layer.get(edge["to"])
        if from_layer not in rank or to_layer not in rank:
            continue
        if rank[from_layer] < rank[to_layer]:
            violations.append({"from": edge["from"], "to": edge["to"], "from_layer": from_layer, "to_layer": to_layer})
    return sorted(violations, key=lambda v: (v["from"], v["to"]))


def find_dead_modules(graph: dict, entry_patterns: tuple[str, ...] = DEFAULT_ENTRY_PATTERNS) -> list[str]:
    """Module ohne Fan-in, die nicht wie ein Einstiegspunkt heißen (exakter Treffer
    des letzten Namensteils gegen `entry_patterns` — eine Substring-Prüfung hätte
    z. B. `domain` fälschlich gegen `main` matchen lassen)."""
    counts = fan_in_out(graph)
    dead = []
    for node in graph.get("nodes", []):
        node_id = node["id"]
        if counts.get(node_id, {"in": 0})["in"] > 0:
            continue
        last_segment = node_id.rsplit(".", 1)[-1]
        if last_segment in entry_patterns:
            continue
        dead.append(node_id)
    return sorted(dead)


def layers_summary(layer_violations: list[dict] | None) -> str:
    """Ein Satz, den die Narration wörtlich übernimmt (Review-Lücke L1): `null` vs.
    `[]` ist im Befund-JSON sauber unterschieden, aber ob das auch im für Menschen
    bestimmten `ARCHITECTURE.md` als **"ungeprüft"** ankommt statt implizit als
    "sauber" durchzugehen, hing bisher komplett von freier Textgenerierung ab. Ein
    kanonischer Satz pro Fall macht den Unterschied sprachlich unübersehbar:
    "ungeprüft" erscheint ausschließlich im fehlenden-Konfiguration-Fall, "geprüft"
    (ohne "un"-Präfix) ausschließlich in den beiden anderen.
    """
    if layer_violations is None:
        return "ungeprüft (keine layers.json gefunden)"
    if not layer_violations:
        return "geprüft: keine Schichtverletzungen gefunden"
    return f"geprüft: {len(layer_violations)} Schichtverletzung(en) gefunden"


def analyze(graph: dict, layers_cfg: dict | None = None) -> dict:
    violations = find_layer_violations(graph, layers_cfg)
    return {
        "cycles": find_cycles(graph),
        "outliers": find_outliers(graph, layers_cfg),
        "layer_violations": violations,
        "dead_modules": find_dead_modules(graph),
        "layers_config_status": "used" if layers_cfg else "missing",
        "layers_summary": layers_summary(violations),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Graph-JSON auf Zyklen, Ausreißer, Schichtverletzungen, tote Module prüfen")
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--layers", type=Path, help="optional: .skills/architecture-map/layers.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    layers_cfg = json.loads(args.layers.read_text(encoding="utf-8")) if args.layers and args.layers.is_file() else None

    findings = analyze(graph, layers_cfg)
    findings["_meta"] = {
        "skill": "architecture-map",
        "schema": SCHEMA_VERSION,
        "generated": f"python scripts/analyze_graph.py --graph {args.graph}"
        + (f" --layers {args.layers}" if args.layers else "")
        + f" --out {args.out}",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")

    if layers_cfg is None:
        print("Hinweis: keine layers.json — Schichtverletzungen sind ungeprüft, nicht sauber.", file=sys.stderr)
    print(
        f"{len(findings['cycles'])} Zyklen, {len(findings['outliers'])} Ausreißer, "
        f"{len(findings['dead_modules'])} tote Module -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
