import json

from conftest import load_script

analyze_graph = load_script("skills/architecture-map/scripts/analyze_graph.py")


def make_graph(node_ids, edges):
    return {
        "nodes": [{"id": n, "path": f"{n.replace('.', '/')}.py", "kind": "module"} for n in node_ids],
        "edges": [{"from": f, "to": t, "kind": "import"} for f, t in edges],
        "external": [],
    }


def test_find_cycles_detects_two_node_cycle():
    graph = make_graph(["a", "b"], [("a", "b"), ("b", "a")])
    assert analyze_graph.find_cycles(graph) == [["a", "b"]]


def test_find_cycles_ignores_acyclic_chain():
    graph = make_graph(["a", "b", "c"], [("a", "b"), ("b", "c")])
    assert analyze_graph.find_cycles(graph) == []


def test_find_cycles_detects_self_loop():
    graph = make_graph(["a"], [("a", "a")])
    assert analyze_graph.find_cycles(graph) == [["a"]]


def test_fan_in_out_counts_correctly():
    graph = make_graph(["a", "b", "c"], [("a", "c"), ("b", "c")])
    counts = analyze_graph.fan_in_out(graph)
    assert counts["c"] == {"in": 2, "out": 0}
    assert counts["a"] == {"in": 0, "out": 1}


def test_find_outliers_above_threshold():
    edges = [(f"m{i}", "hub") for i in range(11)]
    graph = make_graph([f"m{i}" for i in range(11)] + ["hub"], edges)
    outliers = analyze_graph.find_outliers(graph, None)
    assert {"id": "hub", "reason": "fan_in", "value": 11, "threshold": 10} in outliers


def test_find_outliers_below_threshold_is_clean():
    graph = make_graph(["a", "hub"], [("a", "hub")])
    assert analyze_graph.find_outliers(graph, None) == []


def test_find_outliers_uses_configured_threshold():
    graph = make_graph(["a", "b", "hub"], [("a", "hub"), ("b", "hub")])
    outliers = analyze_graph.find_outliers(graph, {"thresholds": {"fan_in": 1}})
    assert any(o["id"] == "hub" and o["reason"] == "fan_in" for o in outliers)


def test_find_layer_violations_none_without_config():
    graph = make_graph(["a", "b"], [("a", "b")])
    assert analyze_graph.find_layer_violations(graph, None) is None


LAYERS_CFG = {
    "order": ["domain", "application", "infrastructure"],
    "layers": {"domain": "domain/", "application": "application/", "infrastructure": "infrastructure/"},
}


def test_find_layer_violations_detects_inner_importing_outer():
    graph = {
        "nodes": [
            {"id": "domain.user", "path": "domain/user.py", "kind": "module"},
            {"id": "infrastructure.db", "path": "infrastructure/db.py", "kind": "module"},
        ],
        "edges": [{"from": "domain.user", "to": "infrastructure.db", "kind": "import"}],
        "external": [],
    }
    violations = analyze_graph.find_layer_violations(graph, LAYERS_CFG)
    assert violations == [{"from": "domain.user", "to": "infrastructure.db", "from_layer": "domain", "to_layer": "infrastructure"}]


def test_find_layer_violations_allows_outer_importing_inner():
    graph = {
        "nodes": [
            {"id": "domain.user", "path": "domain/user.py", "kind": "module"},
            {"id": "infrastructure.db", "path": "infrastructure/db.py", "kind": "module"},
        ],
        "edges": [{"from": "infrastructure.db", "to": "domain.user", "kind": "import"}],
        "external": [],
    }
    assert analyze_graph.find_layer_violations(graph, LAYERS_CFG) == []


def test_find_dead_modules_no_fan_in_and_not_entry():
    graph = make_graph(["a", "b"], [("a", "a_uses_nothing")])
    # b has no incoming edge and no outgoing either
    graph = make_graph(["a", "b"], [])
    assert "b" in analyze_graph.find_dead_modules(graph)
    assert "a" in analyze_graph.find_dead_modules(graph)


def test_find_dead_modules_excludes_entry_points():
    graph = make_graph(["cli", "domain"], [])
    dead = analyze_graph.find_dead_modules(graph)
    assert "cli" not in dead
    assert "domain" in dead  # "domain" != "main", must not falsely match as entry


def test_find_dead_modules_excludes_modules_with_fan_in():
    graph = make_graph(["a", "b"], [("a", "b")])
    assert "b" not in analyze_graph.find_dead_modules(graph)


def test_analyze_reports_missing_layers_config_status():
    graph = make_graph(["a"], [])
    findings = analyze_graph.analyze(graph, None)
    assert findings["layers_config_status"] == "missing"
    assert findings["layer_violations"] is None


def test_analyze_reports_used_layers_config_status():
    graph = make_graph(["a"], [])
    findings = analyze_graph.analyze(graph, LAYERS_CFG)
    assert findings["layers_config_status"] == "used"
    assert findings["layer_violations"] == []


def test_main_writes_findings(tmp_path):
    graph = make_graph(["a", "b"], [("a", "b"), ("b", "a")])
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    out = tmp_path / "findings.json"
    rc = analyze_graph.main(["--graph", str(graph_path), "--out", str(out)])
    assert rc == 0
    findings = json.loads(out.read_text(encoding="utf-8"))
    assert findings["cycles"] == [["a", "b"]]
    assert findings["_meta"]["skill"] == "architecture-map"
