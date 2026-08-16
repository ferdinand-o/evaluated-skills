from conftest import load_script

extract = load_script("skills/rest-api-architect/scripts/extract_openapi.py")


# --- YAML-Dumper (Tier 1, kein PyYAML installiert -> golden-string-Tests) --------


def test_dump_yaml_scalars():
    assert extract.dump_yaml({"a": 1, "b": True, "c": None}) == '"a": 1\n"b": true\n"c": null\n'


def test_dump_yaml_nested_dict():
    assert extract.dump_yaml({"a": {"b": 1}}) == '"a":\n  "b": 1\n'


def test_dump_yaml_list_of_scalars():
    assert extract.dump_yaml({"a": [1, 2]}) == '"a":\n  - 1\n  - 2\n'


def test_dump_yaml_list_of_dicts():
    assert extract.dump_yaml({"a": [{"b": 1, "c": 2}]}) == '"a":\n  - "b": 1\n    "c": 2\n'


def test_dump_yaml_empty_containers_are_inline():
    assert extract.dump_yaml({"a": {}, "b": []}) == '"a": {}\n"b": []\n'


def test_dump_yaml_escapes_quotes_and_newlines():
    result = extract.dump_yaml({"a": 'He said "hi"\nbye'})
    assert result == '"a": "He said \\"hi\\"\\nbye"\n'


# --- FastAPI: ast-basiert -----------------------------------------------------


FASTAPI_SOURCE = '''
from fastapi import FastAPI

app = FastAPI()


@app.get("/v1/users/{id}")
def get_user(id: str):
    return {}


@app.post("/v1/users")
def create_user():
    return {}


if DEBUG:
    @app.get("/v1/debug/ping")
    def ping():
        return {}


PATH = compute_path()


@app.get(PATH)
def dynamic_route():
    return {}
'''


def _write(tmp_path, relpath, content):
    target = tmp_path / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def test_extract_fastapi_finds_direct_routes(tmp_path):
    _write(tmp_path, "main.py", FASTAPI_SOURCE)
    result = extract.extract_fastapi(tmp_path)
    assert "/v1/users/{id}" in result.paths
    op = result.paths["/v1/users/{id}"]["get"]
    assert op["operationId"] == "get_user"
    assert op["x-verified"] is True
    assert {p["name"] for p in op["parameters"]} == {"id"}


def test_extract_fastapi_marks_conditional_route_unverified(tmp_path):
    _write(tmp_path, "main.py", FASTAPI_SOURCE)
    result = extract.extract_fastapi(tmp_path)
    op = result.paths["/v1/debug/ping"]["get"]
    assert op["x-verified"] is False
    assert "Bedingung" in op["x-verified-reason"]


def test_extract_fastapi_marks_dynamic_path_as_unresolved(tmp_path):
    _write(tmp_path, "main.py", FASTAPI_SOURCE)
    result = extract.extract_fastapi(tmp_path)
    assert any("dynamic_route" in str(entry) or entry["reason"] for entry in result.unresolved)
    assert not any(True for path in result.paths if "dynamic_route" in path)


def test_extract_fastapi_finds_post_without_path_params(tmp_path):
    _write(tmp_path, "main.py", FASTAPI_SOURCE)
    result = extract.extract_fastapi(tmp_path)
    op = result.paths["/v1/users"]["post"]
    assert op["parameters"] == []


def test_extract_fastapi_ignores_non_route_dot_get(tmp_path):
    """`dict.get(...)` als normaler Aufruf (kein Decorator) darf keine Route erzeugen."""
    _write(tmp_path, "main.py", "config = {}\nvalue = config.get('x')\n")
    result = extract.extract_fastapi(tmp_path)
    assert result.paths == {}
    assert result.unresolved == []


# --- Express/Hono: Textsuche --------------------------------------------------


EXPRESS_SOURCE = """
const express = require('express');
const router = express.Router();

router.get('/v1/items', (req, res) => {});
app.post("/v1/items/:id/cancel", handler);
"""


def test_extract_express_finds_routes_via_text_search(tmp_path):
    _write(tmp_path, "routes.js", EXPRESS_SOURCE)
    result = extract.extract_express(tmp_path)
    assert "/v1/items" in result.paths
    assert "/v1/items/{id}/cancel" in result.paths


def test_extract_express_always_marks_unverified(tmp_path):
    _write(tmp_path, "routes.js", EXPRESS_SOURCE)
    result = extract.extract_express(tmp_path)
    for methods in result.paths.values():
        for op in methods.values():
            assert op["x-verified"] is False
            assert "Textsuche" in op["x-verified-reason"]


def test_extract_express_converts_colon_params_to_openapi_style(tmp_path):
    _write(tmp_path, "routes.js", EXPRESS_SOURCE)
    result = extract.extract_express(tmp_path)
    op = result.paths["/v1/items/{id}/cancel"]["post"]
    assert {p["name"] for p in op["parameters"]} == {"id"}


# --- Dokument-Aufbau und main() -----------------------------------------------


def test_build_openapi_document_reports_empty_extraction_explicitly():
    doc = extract.build_openapi_document({}, [], title="Leer")
    assert doc["paths"] == {}
    assert "note" in doc["x-extraction"]
    assert doc["x-extraction"]["unresolved"] == []


def test_build_openapi_document_carries_unresolved_list():
    unresolved = [{"file": "main.py", "line": 5, "reason": "x"}]
    doc = extract.build_openapi_document({"/x": {}}, unresolved, title="T")
    assert doc["x-extraction"]["unresolved"] == unresolved
    assert "note" not in doc["x-extraction"]


def test_main_writes_yaml_with_artifact_header(tmp_path):
    _write(tmp_path, "main.py", FASTAPI_SOURCE)
    out_path = tmp_path / "api" / "openapi.yaml"

    rc = extract.main([
        "--framework", "fastapi", "--src", str(tmp_path), "--out", str(out_path),
    ])
    assert rc == 0

    text = out_path.read_text(encoding="utf-8")
    first_line = text.splitlines()[0]
    assert first_line.startswith("# skill: rest-api-architect | schema:")
    assert "extract_openapi.py" in first_line
    assert '"/v1/users/{id}"' in text


def test_main_rejects_missing_src(tmp_path):
    rc = extract.main(["--framework", "fastapi", "--src", str(tmp_path / "nope"), "--out", str(tmp_path / "out.yaml")])
    assert rc == 1


def test_main_reports_zero_routes_visibly(tmp_path, capsys):
    _write(tmp_path, "irrelevant.py", "x = 1\n")
    out_path = tmp_path / "out.yaml"
    rc = extract.main(["--framework", "fastapi", "--src", str(tmp_path), "--out", str(out_path)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Keine Routen" in captured.out
