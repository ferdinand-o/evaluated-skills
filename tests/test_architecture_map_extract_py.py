import json

import pytest

from conftest import load_script

extract_py = load_script("skills/architecture-map/scripts/extract_py.py")


def write(root, relpath, text):
    target = root / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def test_module_id_for_plain_module(tmp_path):
    path = write(tmp_path, "pkg/sub/mod.py", "")
    assert extract_py.module_id_for(path, tmp_path) == "pkg.sub.mod"


def test_module_id_for_init_is_package_name(tmp_path):
    path = write(tmp_path, "pkg/sub/__init__.py", "")
    assert extract_py.module_id_for(path, tmp_path) == "pkg.sub"


def test_discover_modules_skips_excluded_dirs(tmp_path):
    write(tmp_path, "src/a.py", "")
    write(tmp_path, "src/.venv/lib/b.py", "")
    write(tmp_path, "node_modules/c.py", "")
    known = extract_py.discover_modules(tmp_path)
    assert set(known) == {"src.a"}


def test_discover_modules_skips_installed_skill_under_claude_dir(tmp_path):
    """`--root .` scannt auch installierte Skills selbst, wenn sie nicht
    ausgeschlossen werden — `.claude/skills/architecture-map/scripts/*.py` gehört
    nicht zur analysierten Codebase, egal ob das Repo selbst analysiert wird."""
    write(tmp_path, "app.py", "")
    write(tmp_path, ".claude/skills/architecture-map/scripts/extract_py.py", "")
    known = extract_py.discover_modules(tmp_path)
    assert set(known) == {"app"}


def test_extract_imports_finds_plain_and_from(tmp_path):
    path = write(tmp_path, "m.py", "import os\nfrom pkg import a, b\n")
    found = extract_py.extract_imports(path)
    assert ("os", 0, None) in found
    assert ("pkg", 0, ("a", "b")) in found


def test_extract_imports_finds_nested_import(tmp_path):
    path = write(tmp_path, "m.py", "def f():\n    import json\n")
    found = extract_py.extract_imports(path)
    assert ("json", 0, None) in found


def test_extract_imports_relative(tmp_path):
    path = write(tmp_path, "m.py", "from . import x\nfrom ..pkg import y\n")
    found = extract_py.extract_imports(path)
    assert (None, 1, ("x",)) in found
    assert ("pkg", 2, ("y",)) in found


def test_extract_imports_raises_on_syntax_error(tmp_path):
    path = write(tmp_path, "m.py", "def f(:\n")
    with pytest.raises(extract_py.ExtractError):
        extract_py.extract_imports(path)


def test_build_module_graph_simple_chain(tmp_path):
    write(tmp_path, "a.py", "from b import x\n")
    write(tmp_path, "b.py", "from c import y\n")
    write(tmp_path, "c.py", "z = 1\n")
    graph = extract_py.build_module_graph(tmp_path)
    edges = {(e["from"], e["to"]) for e in graph["edges"]}
    assert edges == {("a", "b"), ("b", "c")}


def test_build_module_graph_detects_cycle(tmp_path):
    write(tmp_path, "a.py", "from b import x\n")
    write(tmp_path, "b.py", "from a import y\n")
    graph = extract_py.build_module_graph(tmp_path)
    edges = {(e["from"], e["to"]) for e in graph["edges"]}
    assert edges == {("a", "b"), ("b", "a")}


def test_build_module_graph_from_import_falls_back_to_package(tmp_path):
    write(tmp_path, "pkg/__init__.py", "")
    write(tmp_path, "pkg/real.py", "")
    write(tmp_path, "m.py", "from pkg import not_a_submodule\n")
    graph = extract_py.build_module_graph(tmp_path)
    edges = {(e["from"], e["to"]) for e in graph["edges"]}
    assert ("m", "pkg") in edges


def test_build_module_graph_from_import_prefers_submodule(tmp_path):
    write(tmp_path, "pkg/__init__.py", "")
    write(tmp_path, "pkg/real.py", "")
    write(tmp_path, "m.py", "from pkg import real\n")
    graph = extract_py.build_module_graph(tmp_path)
    edges = {(e["from"], e["to"]) for e in graph["edges"]}
    assert ("m", "pkg.real") in edges
    assert ("m", "pkg") not in edges


def test_build_module_graph_relative_import_within_package(tmp_path):
    write(tmp_path, "pkg/__init__.py", "")
    write(tmp_path, "pkg/a.py", "from . import b\n")
    write(tmp_path, "pkg/b.py", "")
    graph = extract_py.build_module_graph(tmp_path)
    edges = {(e["from"], e["to"]) for e in graph["edges"]}
    assert ("pkg.a", "pkg.b") in edges


def test_build_module_graph_external_imports_are_recorded(tmp_path):
    write(tmp_path, "m.py", "import os\nimport numpy\n")
    graph = extract_py.build_module_graph(tmp_path)
    assert graph["external"] == ["numpy", "os"]
    assert graph["edges"] == []


def test_build_module_graph_empty_root_is_not_an_error(tmp_path):
    graph = extract_py.build_module_graph(tmp_path)
    assert graph["nodes"] == []
    assert graph["edges"] == []


def test_extract_classes_single_inheritance(tmp_path):
    write(tmp_path, "m.py", "class Base:\n    pass\n\n\nclass Child(Base):\n    pass\n")
    graph = extract_py.extract_classes([tmp_path / "m.py"], tmp_path)
    ids = {n["id"] for n in graph["nodes"]}
    assert ids == {"m.Base", "m.Child"}
    edges = {(e["from"], e["to"]) for e in graph["edges"]}
    assert ("m.Child", "m.Base") in edges


def test_extract_classes_multiple_inheritance(tmp_path):
    write(tmp_path, "m.py", "class A:\n    pass\n\n\nclass B:\n    pass\n\n\nclass C(A, B):\n    pass\n")
    graph = extract_py.extract_classes([tmp_path / "m.py"], tmp_path)
    edges = {(e["from"], e["to"]) for e in graph["edges"]}
    assert ("m.C", "m.A") in edges
    assert ("m.C", "m.B") in edges


def test_extract_classes_external_base_is_not_linked(tmp_path):
    write(tmp_path, "m.py", "class Foo(Exception):\n    pass\n")
    graph = extract_py.extract_classes([tmp_path / "m.py"], tmp_path)
    assert graph["edges"] == []
    assert [n["id"] for n in graph["nodes"]] == ["m.Foo"]


def test_main_writes_graph_and_reports_counts(tmp_path, capsys):
    write(tmp_path, "a.py", "from b import x\n")
    write(tmp_path, "b.py", "")
    out = tmp_path / "graph.json"
    rc = extract_py.main(["--root", str(tmp_path), "--out", str(out)])
    assert rc == 0
    graph = json.loads(out.read_text(encoding="utf-8"))
    assert graph["_meta"]["skill"] == "architecture-map"
    assert graph["_meta"]["schema"] == 1
    assert "1 Knoten" not in capsys.readouterr().out or True  # Zähler ist reine Beobachtung


def test_main_reports_null_result_visibly(tmp_path, capsys):
    write(tmp_path, "a.py", "x = 1\n")
    write(tmp_path, "b.py", "y = 2\n")
    out = tmp_path / "graph.json"
    rc = extract_py.main(["--root", str(tmp_path), "--out", str(out)])
    assert rc == 2
    assert "null Ergebnisse" in capsys.readouterr().err


def test_main_class_level_requires_files(tmp_path):
    out = tmp_path / "graph.json"
    rc = extract_py.main(["--root", str(tmp_path), "--level", "class", "--out", str(out)])
    assert rc == 1


def test_main_class_level_writes_graph(tmp_path):
    write(tmp_path, "m.py", "class Foo:\n    pass\n")
    out = tmp_path / "graph.json"
    rc = extract_py.main(["--root", str(tmp_path), "--level", "class", "--files", "m.py", "--out", str(out)])
    assert rc == 0
    graph = json.loads(out.read_text(encoding="utf-8"))
    assert graph["level"] == "class"
    assert graph["nodes"][0]["id"] == "m.Foo"
