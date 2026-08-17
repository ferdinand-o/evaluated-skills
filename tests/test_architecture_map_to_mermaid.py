import pytest

from conftest import load_script

to_mermaid = load_script("skills/architecture-map/scripts/to_mermaid.py")


def make_graph(nodes, edges, generated="python extract_py.py --root ."):
    return {
        "_meta": {"skill": "architecture-map", "schema": 1, "generated": generated},
        "nodes": [{"id": n, "path": f"{n}.py", "kind": "module"} for n in nodes],
        "edges": [{"from": f, "to": t, "kind": "import"} for f, t in edges],
        "external": [],
    }


def test_sanitize_id_replaces_invalid_chars():
    assert to_mermaid.sanitize_id("pkg.sub-mod") == "pkg_sub_mod"


def test_sanitize_id_prefixes_leading_digit():
    assert to_mermaid.sanitize_id("1module").startswith("n_")


def test_render_contains_header_with_generated_command():
    graph = make_graph(["a"], [])
    block = to_mermaid.render(graph)
    assert "%% skill: architecture-map | schema: 1 | generated: python extract_py.py --root ." in block


def test_render_requires_meta():
    graph = {"nodes": [], "edges": []}
    with pytest.raises(ValueError):
        to_mermaid.render(graph)


def test_render_is_deterministic_regardless_of_input_order():
    g1 = make_graph(["b", "a", "c"], [("b", "c"), ("a", "b")])
    g2 = make_graph(["c", "b", "a"], [("a", "b"), ("b", "c")])
    assert to_mermaid.render(g1) == to_mermaid.render(g2)


def test_render_empty_graph_is_valid_block():
    block = to_mermaid.render(make_graph([], []))
    assert block.startswith("```mermaid")
    assert block.strip().endswith("```")


def test_render_assigns_distinct_ids_on_collision():
    graph = make_graph(["a.b", "a-b"], [])
    block = to_mermaid.render(graph)
    lines = [l for l in block.splitlines() if l.strip().startswith("a_b")]
    assert len(lines) == 2
    ids = {l.split("[")[0].strip() for l in lines}
    assert len(ids) == 2


def test_parse_round_trips_nodes_and_edges():
    graph = make_graph(["pkg.a", "pkg.b"], [("pkg.a", "pkg.b")])
    block = to_mermaid.render(graph)
    nodes, edges = to_mermaid.parse(block)
    assert nodes == {"pkg.a", "pkg.b"}
    assert edges == {("pkg.a", "pkg.b")}


def test_parse_empty_block_returns_empty_sets():
    block = to_mermaid.render(make_graph([], []))
    nodes, edges = to_mermaid.parse(block)
    assert nodes == set()
    assert edges == set()


def test_main_writes_block_to_file(tmp_path):
    import json

    graph = make_graph(["a", "b"], [("a", "b")])
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    out = tmp_path / "out.md"
    rc = to_mermaid.main(["--graph", str(graph_path), "--out", str(out)])
    assert rc == 0
    assert "flowchart LR" in out.read_text(encoding="utf-8")
