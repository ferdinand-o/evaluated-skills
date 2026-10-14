import json
import sys

from conftest import REPO_ROOT, load_script

drift_check = load_script("skills/architecture-map/scripts/drift_check.py")
to_mermaid = load_script("skills/architecture-map/scripts/to_mermaid.py")


def make_graph(node_ids, edges, generated="python extract_py.py --root . --out g.json"):
    return {
        "_meta": {"skill": "architecture-map", "schema": 1, "generated": generated},
        "nodes": [{"id": n, "path": f"{n}.py", "kind": "module"} for n in node_ids],
        "edges": [{"from": f, "to": t, "kind": "import"} for f, t in edges],
        "external": [],
    }


def doc_with_footer(mermaid_block, footer: dict) -> str:
    return (
        "# ARCHITECTURE.md\n\n## Module\n\n"
        + mermaid_block
        + "\n<!-- architecture-map:graph-hashes\n"
        + json.dumps(footer)
        + "\n-->\n"
    )


def test_graph_hash_ignores_meta():
    g1 = make_graph(["a", "b"], [("a", "b")], generated="cmd-one")
    g2 = make_graph(["a", "b"], [("a", "b")], generated="cmd-two")
    assert drift_check.graph_hash(g1) == drift_check.graph_hash(g2)


def test_graph_hash_changes_with_edges():
    g1 = make_graph(["a", "b"], [("a", "b")])
    g2 = make_graph(["a", "b"], [])
    assert drift_check.graph_hash(g1) != drift_check.graph_hash(g2)


def test_graph_hash_changes_with_external():
    """Review-Defekt D2: eine neue/entfernte externe Abhängigkeit ändert nodes/edges
    nicht, ist aber Teil der Kontext-Ebene — der Hash muss trotzdem reagieren."""
    g1 = make_graph(["a"], [])
    g2 = make_graph(["a"], [])
    g1["external"] = []
    g2["external"] = ["requests"]
    assert drift_check.graph_hash(g1) != drift_check.graph_hash(g2)


def test_read_footer_parses_json_block():
    text = doc_with_footer("```mermaid\nfoo\n```\n", {"module": {"command": "x", "graph_hash": "h"}})
    footer = drift_check.read_footer(text)
    assert footer == {"module": {"command": "x", "graph_hash": "h"}}


def test_read_footer_returns_none_without_block():
    assert drift_check.read_footer("# nur Text\n") is None


def test_read_footer_raises_on_invalid_json():
    text = "<!-- architecture-map:graph-hashes\nnot json\n-->\n"
    try:
        drift_check.read_footer(text)
        assert False, "sollte werfen"
    except drift_check.DriftCheckError:
        pass


def test_read_mermaid_blocks_keyed_by_generated_command():
    graph = make_graph(["a", "b"], [("a", "b")], generated="python extract_py.py --root . --out g.json")
    block = to_mermaid.render(graph)
    text = f"# doc\n{block}\n"
    blocks = drift_check.read_mermaid_blocks(text)
    assert "python extract_py.py --root . --out g.json" in blocks


def test_diff_graph_reports_added_and_removed():
    old_nodes = {"a", "b"}
    old_edges = {("a", "b")}
    new_graph = make_graph(["a", "c"], [("a", "c")])
    diff = drift_check.diff_graph(old_nodes, old_edges, new_graph)
    assert diff["nodes_added"] == ["c"]
    assert diff["nodes_removed"] == ["b"]
    assert diff["edges_added"] == [("a", "c")]
    assert diff["edges_removed"] == [("a", "b")]
    assert diff["external_added"] == []
    assert diff["external_removed"] == []


def test_diff_graph_reports_external_added_and_removed():
    new_graph = make_graph(["a"], [])
    new_graph["external"] = ["requests", "yaml"]
    diff = drift_check.diff_graph({"a"}, set(), new_graph, old_external=["yaml"])
    assert diff["external_added"] == ["requests"]
    assert diff["external_removed"] == []


def test_diff_graph_missing_old_external_defaults_to_empty():
    new_graph = make_graph(["a"], [])
    new_graph["external"] = ["requests"]
    diff = drift_check.diff_graph({"a"}, set(), new_graph)
    assert diff["external_added"] == ["requests"]


def test_check_raises_without_footer(tmp_path):
    doc = tmp_path / "ARCHITECTURE.md"
    doc.write_text("# keine Kopfzeile hier\n", encoding="utf-8")
    try:
        drift_check.check(doc)
        assert False, "sollte werfen"
    except drift_check.DriftCheckError:
        pass


def _write_py_project(root, a_imports_b=True):
    (root / "a.py").write_text("from b import x\n" if a_imports_b else "", encoding="utf-8")
    (root / "b.py").write_text("", encoding="utf-8")


def _build_and_write_module_doc(project_dir, cache_out):
    """Baut den ersten Graph-Stand über eine echte `python skills/.../extract_py.py`-
    Subprocess-Invokation (nicht `extract_py.main()` in-process) — die aufgezeichnete
    `_meta.generated`-Kette (`python scripts/extract_py.py …`) muss genauso entstehen, wie
    `drift_check.regenerate_graph()` sie später erneut ausführt."""
    import subprocess

    cmd = [
        "python", "skills/architecture-map/scripts/extract_py.py",
        "--root", str(project_dir), "--level", "module", "--out", str(cache_out),
    ]
    completed = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    graph = json.loads(cache_out.read_text(encoding="utf-8"))
    block = to_mermaid.render(graph)
    footer = {
        "module": {
            "command": graph["_meta"]["generated"],
            "graph_hash": drift_check.graph_hash(graph),
            "external": graph["external"],
        }
    }
    return block, footer


def test_check_reports_unchanged_when_code_did_not_change(tmp_path):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    _write_py_project(project_dir)
    cache_out = tmp_path / "graph.json"
    block, footer = _build_and_write_module_doc(project_dir, cache_out)

    doc = project_dir / "ARCHITECTURE.md"
    doc.write_text(doc_with_footer(block, footer), encoding="utf-8")
    doc_hash_before = doc.read_bytes()

    result = drift_check.check(doc, cwd=REPO_ROOT)
    assert result["any_drift"] is False
    assert result["levels"]["module"]["status"] == "unchanged"
    assert doc.read_bytes() == doc_hash_before  # nie geschrieben


def test_check_reports_drift_with_edge_diff_when_code_changed(tmp_path):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    _write_py_project(project_dir, a_imports_b=True)
    cache_out = tmp_path / "graph.json"
    block, footer = _build_and_write_module_doc(project_dir, cache_out)

    doc = project_dir / "ARCHITECTURE.md"
    doc.write_text(doc_with_footer(block, footer), encoding="utf-8")

    # Code ändert sich: a.py importiert b nicht mehr, dafür ein neues c.py
    (project_dir / "a.py").write_text("", encoding="utf-8")
    (project_dir / "c.py").write_text("", encoding="utf-8")

    result = drift_check.check(doc, cwd=REPO_ROOT)
    assert result["any_drift"] is True
    level = result["levels"]["module"]
    assert level["status"] == "drift"
    assert level["diff"]["edges_removed"] == [("a", "b")]
    assert "c" in level["diff"]["nodes_added"]


def test_check_reports_drift_when_only_external_changes(tmp_path):
    """Review-Defekt D2, End-to-End: nodes/edges bleiben identisch, nur eine neue
    externe Abhängigkeit kommt hinzu — der Drift-Check darf das nicht als
    'unverändert' durchwinken."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    _write_py_project(project_dir)
    cache_out = tmp_path / "graph.json"
    block, footer = _build_and_write_module_doc(project_dir, cache_out)

    doc = project_dir / "ARCHITECTURE.md"
    doc.write_text(doc_with_footer(block, footer), encoding="utf-8")

    (project_dir / "a.py").write_text("from b import x\nimport requests\n", encoding="utf-8")

    result = drift_check.check(doc, cwd=REPO_ROOT)
    assert result["any_drift"] is True
    level = result["levels"]["module"]
    assert level["status"] == "drift"
    assert level["diff"]["nodes_added"] == []
    assert level["diff"]["nodes_removed"] == []
    assert level["diff"]["edges_added"] == []
    assert level["diff"]["edges_removed"] == []
    assert level["diff"]["external_added"] == ["requests"]


def test_check_short_circuits_diff_when_hash_matches(tmp_path, monkeypatch):
    """Plan-Zusage (L2): kein Drift heißt auch kein Parsen/Diffen — der Kurzschluss
    in `check()` wird über Spies statt nur über das Endergebnis geprüft."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    _write_py_project(project_dir)
    cache_out = tmp_path / "graph.json"
    block, footer = _build_and_write_module_doc(project_dir, cache_out)
    doc = project_dir / "ARCHITECTURE.md"
    doc.write_text(doc_with_footer(block, footer), encoding="utf-8")

    diff_calls = []
    parse_calls = []
    monkeypatch.setattr(drift_check, "diff_graph", lambda *a, **k: diff_calls.append(1))
    monkeypatch.setattr(drift_check.to_mermaid, "parse", lambda *a, **k: parse_calls.append(1))

    result = drift_check.check(doc, cwd=REPO_ROOT)
    assert result["levels"]["module"]["status"] == "unchanged"
    assert diff_calls == []
    assert parse_calls == []


def test_main_print_hash_mode(tmp_path, capsys):
    graph = make_graph(["a", "b"], [("a", "b")])
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    rc = drift_check.main(["--graph", str(graph_path)])
    assert rc == 0
    printed = capsys.readouterr().out.strip()
    assert printed == drift_check.graph_hash(graph)


def test_main_rejects_doc_and_graph_together(tmp_path):
    rc = drift_check.main(["--doc", str(tmp_path / "x.md"), "--graph", str(tmp_path / "g.json")])
    assert rc == 1


def test_main_exit_code_reflects_drift(tmp_path, capsys):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    _write_py_project(project_dir)
    cache_out = tmp_path / "graph.json"
    block, footer = _build_and_write_module_doc(project_dir, cache_out)
    doc = project_dir / "ARCHITECTURE.md"
    doc.write_text(doc_with_footer(block, footer), encoding="utf-8")

    rc = drift_check.main(["--doc", str(doc), "--cwd", str(REPO_ROOT)])
    assert rc == 0
    assert "unverändert" in capsys.readouterr().out


def test_drift_check_resolves_old_and_new_paths(tmp_path):
    """Spec 25: Die Erzeuger schreiben `python scripts/<datei>` statt eines Pfads, der nur
    auf einer Maschine stimmt; drift_check führt jede Form mit dem eigenen Skript aus —
    auch Footer, die vor der Umstellung entstanden sind."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    _write_py_project(project_dir)
    cache_out = tmp_path / "graph.json"
    block, footer = _build_and_write_module_doc(project_dir, cache_out)
    command = footer["module"]["command"]
    assert command.startswith("python scripts/extract_py.py "), command
    rest = command[len("python scripts/extract_py.py "):]
    for script in ("scripts/extract_py.py", "skills/architecture-map/scripts/extract_py.py",
                   ".claude/skills/architecture-map/scripts/extract_py.py",
                   "/nirgends/anderer-rechner/architecture-map/scripts/extract_py.py"):
        footer["module"]["command"] = f"python {script} {rest}"
        doc = project_dir / "ARCHITECTURE.md"
        doc.write_text(doc_with_footer(block, footer), encoding="utf-8")
        result = drift_check.check(doc, cwd=tmp_path)
        assert result["levels"]["module"]["status"] == "unchanged", (script, result)
    parts = drift_check.resolve_script("python scripts/analyze_graph.py --graph g.json")
    assert parts[1].endswith("/architecture-map/scripts/analyze_graph.py") and parts[0] == sys.executable
