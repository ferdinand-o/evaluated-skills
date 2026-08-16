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


def test_dump_yaml_escapes_carriage_return():
    """Review-Fund (Lücke): ein rohes CR wurde nicht escaped. Gegen echtes PyYAML 6.0.3
    nachgewiesen: `yaml.safe_load('"foo\\rbar"')` faltet ein unescaptes CR still zu einem
    Leerzeichen (Flow-Scalar-Zeilenumbruch-Regel) — kein Parse-Fehler, eine stille
    Verfälschung. Dieser Test prüft nur die Escape-Ausgabe (PyYAML ist hier nicht
    installiert, siehe docs/known-limits.md); die Faltung selbst wurde extern verifiziert."""
    result = extract.dump_yaml({"a": "foo\rbar"})
    assert result == '"a": "foo\\rbar"\n'
    assert "\r" not in result


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
    """Review-Fund (Defekt 4): die ursprüngliche Assertion `"dynamic_route" in str(entry) or
    entry["reason"]` ist wegen Operatorpriorität für praktisch jeden nichtleeren
    unresolved-Eintrag wahr (`entry["reason"]` ist ein truthy String) — sie bewacht nichts.
    Diese Fassung prüft den konkreten Eintrag (Funktion + exakter Grund) statt nur, dass
    irgendein Eintrag mit einem truthy `reason`-Feld existiert."""
    _write(tmp_path, "main.py", FASTAPI_SOURCE)
    result = extract.extract_fastapi(tmp_path)
    dynamic_entries = [e for e in result.unresolved if e.get("function") == "dynamic_route"]
    assert len(dynamic_entries) == 1
    assert dynamic_entries[0]["reason"] == extract.FASTAPI_UNRESOLVED_REASON
    assert not any("dynamic_route" in path for path in result.paths)


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


# --- Review-Fund Defekt 1: path=-Keyword-Argument -----------------------------


def test_extract_fastapi_finds_path_keyword_argument(tmp_path):
    _write(tmp_path, "main.py", (
        "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n"
        "@app.get(path=\"/v1/widgets\")\ndef list_widgets():\n    return []\n"
    ))
    result = extract.extract_fastapi(tmp_path)
    assert "/v1/widgets" in result.paths
    op = result.paths["/v1/widgets"]["get"]
    assert op["operationId"] == "list_widgets"
    assert op["x-verified"] is True
    assert result.unresolved == []


def test_extract_fastapi_path_keyword_with_non_literal_is_unresolved(tmp_path):
    _write(tmp_path, "main.py", (
        "from fastapi import FastAPI\n\napp = FastAPI()\nPATH = compute()\n\n\n"
        "@app.get(path=PATH)\ndef handler():\n    return []\n"
    ))
    result = extract.extract_fastapi(tmp_path)
    assert result.paths == {}
    assert any(e["function"] == "handler" for e in result.unresolved)


# --- Review-Fund Defekt 2: add_api_route()/add_route() ------------------------


def test_extract_fastapi_finds_add_api_route_registration(tmp_path):
    _write(tmp_path, "main.py", (
        "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n"
        "def list_widgets():\n    return []\n\n\n"
        "app.add_api_route(\"/v1/widgets\", list_widgets, methods=[\"GET\"])\n"
    ))
    result = extract.extract_fastapi(tmp_path)
    assert "/v1/widgets" in result.paths
    op = result.paths["/v1/widgets"]["get"]
    assert op["operationId"] == "list_widgets"
    assert op["x-verified"] is True


def test_extract_fastapi_add_route_defaults_to_get_without_methods(tmp_path):
    _write(tmp_path, "main.py", (
        "from starlette.applications import Starlette\n\napp = Starlette()\n\n\n"
        "def handler():\n    return []\n\n\n"
        "app.add_route(\"/v1/health\", handler)\n"
    ))
    result = extract.extract_fastapi(tmp_path)
    assert "get" in result.paths["/v1/health"]


def test_extract_fastapi_registration_call_alongside_decorators_all_survive(tmp_path):
    """Der im Review konkret nachgewiesene Fall: drei Registrierungen in einer Datei, zwei
    davon zuvor spurlos verschwunden, nur weil eine dritte (Decorator-)Route gefunden wurde
    und die globale 'keine Routen gefunden'-Warnung deshalb nicht griff."""
    _write(tmp_path, "main.py", (
        "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n"
        "@app.get(path=\"/v1/widgets\")\ndef list_widgets():\n    return []\n\n\n"
        "app.add_api_route(\"/v1/orders\", list_widgets, methods=[\"GET\"])\n\n\n"
        "@app.get(\"/v1/items\")\ndef list_items():\n    return []\n"
    ))
    result = extract.extract_fastapi(tmp_path)
    assert set(result.paths) == {"/v1/widgets", "/v1/orders", "/v1/items"}


def test_extract_fastapi_registration_call_with_non_literal_path_is_unresolved(tmp_path):
    _write(tmp_path, "main.py", (
        "from fastapi import FastAPI\n\napp = FastAPI()\nPATH = compute()\n\n\n"
        "def handler():\n    return []\n\n\n"
        "app.add_api_route(PATH, handler, methods=[\"GET\"])\n"
    ))
    result = extract.extract_fastapi(tmp_path)
    assert result.paths == {}
    assert any(e["reason"] == extract.FASTAPI_UNRESOLVED_REASON for e in result.unresolved)


def test_extract_fastapi_registration_call_without_any_path_argument_is_unresolved(tmp_path):
    _write(tmp_path, "main.py", (
        "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n"
        "def handler():\n    return []\n\n\n"
        "app.add_api_route(endpoint=handler, methods=[\"GET\"])\n"
    ))
    result = extract.extract_fastapi(tmp_path)
    assert result.paths == {}
    assert any("add_api_route" in e["reason"] for e in result.unresolved)


# --- Review-Fund Auffangnetz: Lookalikes, die auch die Erweiterungen nicht fassen ---


def test_extract_fastapi_aliased_decorator_is_caught_by_fallback(tmp_path):
    """`get = app.get` gefolgt von `@get(...)` ist kein `<name>.<methode>(...)`-Dekorator mehr
    (der Funktionsname ist ein bloßer ast.Name, kein ast.Attribute) und bleibt daher auch nach
    den Erweiterungen für den AST-Walk unsichtbar. Das Text-Auffangnetz muss diese Lücke
    trotzdem sichtbar machen, statt sie stillschweigend zu verlieren."""
    _write(tmp_path, "main.py", (
        "from fastapi import FastAPI\n\napp = FastAPI()\nget = app.get\n\n\n"
        "@get(\"/v1/mystery\")\ndef handler():\n    return []\n"
    ))
    result = extract.extract_fastapi(tmp_path)
    assert result.paths == {}
    assert any(e["file"] == "main.py" and "manuell prüfen" in e["reason"] for e in result.unresolved)


def test_extract_fastapi_no_fallback_noise_when_everything_is_attributed(tmp_path):
    _write(tmp_path, "main.py", FASTAPI_SOURCE)
    result = extract.extract_fastapi(tmp_path)
    assert not any("manuell prüfen" in e.get("reason", "") for e in result.unresolved)


def test_extract_fastapi_routes_in_for_loop_are_conditional_not_invisible(tmp_path):
    _write(tmp_path, "main.py", (
        "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n"
        "for _ in range(1):\n"
        "    @app.get(\"/v1/loop\")\n"
        "    def handler():\n"
        "        return []\n"
    ))
    result = extract.extract_fastapi(tmp_path)
    assert result.paths["/v1/loop"]["get"]["x-verified"] is False


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


def test_extract_express_finds_routes_on_arbitrary_router_variable_name(tmp_path):
    """Review-Fund (Defekt 3): auf `app`/`router` beschränkt, verlor jede Route auf anders
    benannten Router-Objekten spurlos. Der Reviewer-Fall: zwei Router, einer heißt
    `usersRouter` — vorher fehlte dessen Route komplett, ohne jede Spur."""
    source = (
        "const usersRouter = require('express').Router();\n"
        "usersRouter.get('/v1/users', (req, res) => {});\n"
        "const router = require('express').Router();\n"
        "router.get('/v1/orders', (req, res) => {});\n"
    )
    _write(tmp_path, "routes.js", source)
    result = extract.extract_express(tmp_path)
    assert "/v1/users" in result.paths
    assert "/v1/orders" in result.paths
    assert result.paths["/v1/users"]["get"]["x-verified"] is False


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
