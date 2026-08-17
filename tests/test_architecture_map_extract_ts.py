import json

import pytest

from conftest import load_script

extract_ts = load_script("skills/architecture-map/scripts/extract_ts.py")


def write(root, relpath, text):
    target = root / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def test_module_id_for_plain_file(tmp_path):
    path = write(tmp_path, "src/util.ts", "")
    assert extract_ts.module_id_for(path, tmp_path) == "src.util"


def test_module_id_for_index_is_directory_name(tmp_path):
    path = write(tmp_path, "src/widgets/index.ts", "")
    assert extract_ts.module_id_for(path, tmp_path) == "src.widgets"


def test_discover_modules_skips_node_modules(tmp_path):
    write(tmp_path, "src/a.ts", "")
    write(tmp_path, "node_modules/pkg/b.ts", "")
    known = extract_ts.discover_modules(tmp_path)
    assert set(known) == {"src.a"}


def test_discover_modules_skips_installed_skill_under_claude_dir(tmp_path):
    write(tmp_path, "src/a.ts", "")
    write(tmp_path, ".claude/skills/architecture-map/scripts/extract_ts.py", "")
    known = extract_ts.discover_modules(tmp_path)
    assert set(known) == {"src.a"}


def test_discover_modules_raises_on_barrel_index_collision(tmp_path):
    """Review-Defekt D3: src/widgets.ts und src/widgets/index.ts liefern beide die
    ID 'src.widgets' — ein realistischer Barrel-Fall, darf nicht still verlieren."""
    write(tmp_path, "src/widgets.ts", "")
    write(tmp_path, "src/widgets/index.ts", "")
    with pytest.raises(extract_ts.ExtractError, match="Kollision"):
        extract_ts.discover_modules(tmp_path)


def test_extract_specifiers_named_import(tmp_path):
    specs = extract_ts.extract_specifiers("import { a } from './a';\n")
    assert specs == ["./a"]


def test_extract_specifiers_bare_side_effect_import(tmp_path):
    specs = extract_ts.extract_specifiers("import './side-effect';\n")
    assert specs == ["./side-effect"]


def test_extract_specifiers_mixed_bare_and_named(tmp_path):
    specs = extract_ts.extract_specifiers("import './side-effect';\nimport { a } from './a';\n")
    assert set(specs) == {"./side-effect", "./a"}


def test_extract_specifiers_export_from(tmp_path):
    specs = extract_ts.extract_specifiers("export { a } from './a';\n")
    assert specs == ["./a"]


def test_extract_specifiers_require(tmp_path):
    specs = extract_ts.extract_specifiers("const x = require('./x');\n")
    assert specs == ["./x"]


def test_extract_specifiers_dynamic_import(tmp_path):
    specs = extract_ts.extract_specifiers("const y = await import('./y');\n")
    assert specs == ["./y"]


def test_extract_specifiers_ignores_comments(tmp_path):
    text = "// import { a } from './a';\n/* import { b } from './b'; */\nconst z = 1;\n"
    assert extract_ts.extract_specifiers(text) == []


def test_resolve_specifier_with_explicit_extension(tmp_path):
    write(tmp_path, "src/a.ts", "")
    known = {"src/a.ts": "src.a"}
    target = extract_ts.resolve_specifier(tmp_path / "src" / "m.ts", "./a", tmp_path, known)
    assert target == "src.a"


def test_resolve_specifier_index_fallback(tmp_path):
    write(tmp_path, "src/widgets/index.ts", "")
    known = {"src/widgets/index.ts": "src.widgets"}
    target = extract_ts.resolve_specifier(tmp_path / "src" / "m.ts", "./widgets", tmp_path, known)
    assert target == "src.widgets"


def test_resolve_specifier_parent_dir(tmp_path):
    write(tmp_path, "src/util.ts", "")
    known = {"src/util.ts": "src.util"}
    target = extract_ts.resolve_specifier(tmp_path / "src" / "sub" / "m.ts", "../util", tmp_path, known)
    assert target == "src.util"


def test_resolve_specifier_js_extension_resolves_to_ts_source(tmp_path):
    """Review-Lücke L3: nodenext-ESM-Konvention, `.js`-Import einer `.ts`-Quelle."""
    write(tmp_path, "src/foo.ts", "")
    known = {"src/foo.ts": "src.foo"}
    target = extract_ts.resolve_specifier(tmp_path / "src" / "m.ts", "./foo.js", tmp_path, known)
    assert target == "src.foo"


def test_resolve_specifier_written_extension_still_preferred_when_it_exists(tmp_path):
    """Die geschriebene Extension gewinnt weiterhin, wenn sie tatsächlich existiert —
    Geschwister-Extensionen sind nur ein Rückfall, keine Umgehung."""
    write(tmp_path, "src/foo.js", "")
    write(tmp_path, "src/foo.ts", "")
    known = {"src/foo.js": "src.foo.js", "src/foo.ts": "src.foo.ts"}
    target = extract_ts.resolve_specifier(tmp_path / "src" / "m.ts", "./foo.js", tmp_path, known)
    assert target == "src.foo.js"


def test_resolve_specifier_unresolvable_returns_none(tmp_path):
    target = extract_ts.resolve_specifier(tmp_path / "src" / "m.ts", "./missing", tmp_path, {})
    assert target is None


def test_build_module_graph_relative_import_creates_edge(tmp_path):
    write(tmp_path, "src/a.ts", "import { b } from './b';\n")
    write(tmp_path, "src/b.ts", "")
    graph = extract_ts.build_module_graph(tmp_path)
    edges = {(e["from"], e["to"]) for e in graph["edges"]}
    assert ("src.a", "src.b") in edges


def test_build_module_graph_package_import_is_external(tmp_path):
    write(tmp_path, "src/a.ts", "import React from 'react';\nimport { z } from '@scope/pkg';\n")
    graph = extract_ts.build_module_graph(tmp_path)
    assert graph["external"] == ["@scope/pkg", "react"]
    assert graph["edges"] == []


def test_build_module_graph_empty_root_is_not_an_error(tmp_path):
    graph = extract_ts.build_module_graph(tmp_path)
    assert graph["nodes"] == []


def test_main_writes_graph(tmp_path):
    write(tmp_path, "src/a.ts", "import { b } from './b';\n")
    write(tmp_path, "src/b.ts", "")
    out = tmp_path / "graph.json"
    rc = extract_ts.main(["--root", str(tmp_path), "--out", str(out)])
    assert rc == 0
    graph = json.loads(out.read_text(encoding="utf-8"))
    assert graph["_meta"]["skill"] == "architecture-map"
    assert graph["language"] == "typescript"


def test_main_reports_null_result_visibly(tmp_path, capsys):
    write(tmp_path, "src/a.ts", "const x = 1;\n")
    write(tmp_path, "src/b.ts", "const y = 2;\n")
    out = tmp_path / "graph.json"
    rc = extract_ts.main(["--root", str(tmp_path), "--out", str(out)])
    assert rc == 2
    assert "null Ergebnisse" in capsys.readouterr().err
