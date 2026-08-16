#!/usr/bin/env python3
"""Brownfield-Erfassung: Routen statisch extrahieren, Ist-OpenAPI schreiben. Tier 1: nur Stdlib.

R2 — das ist keine reine Abhängigkeitsfrage, sondern eine Sicherheitsfrage: Eine fremde
Anwendung zu importieren, um ihre Routen zu erfahren, führt sie aus — Datenbankverbindungen,
Netzwerkaufrufe, Konfigurationsladen, Migrationen beim Start. Dieses Skript importiert die
Zielanwendung nie. FastAPI wird über `ast` analysiert (Dekoratoren wie `@app.get(...)`),
Express/Hono über Textsuche.

Was statisch nicht sicher auflösbar ist, wird als das markiert, was es ist:
- Ein Pfad, der kein String-Literal ist (f-String, Variable) -> `x-extraction.unresolved`,
  keine Pfad-Erfindung.
- Eine Route hinter einer Bedingung (`if ...: @app.get(...)`) -> `x-verified: false`.
- Jede über Textsuche gefundene Express/Hono-Route -> `x-verified: false`, immer — Textsuche
  ohne Kontrollfluss ist strukturell unsicherer als AST.

Bekannte Grenze (siehe docs/known-limits.md): Router-Präfixe aus
`app.include_router(sub_router, prefix="/v1")` in einer anderen Datei werden nicht aufgelöst.
Pfade aus einem so gemounteten Sub-Router erscheinen ohne das Präfix.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "options", "head"})
FASTAPI_UNRESOLVED_REASON = "Pfad ist kein String-Literal (f-String oder Variable) — nicht statisch auflösbar"
CONDITIONAL_REASON = "hinter Bedingung registriert (in einem if-Block) — zur Laufzeit ggf. nie erreichbar"
TEXT_SEARCH_REASON = "Express/Hono: Textsuche, nicht AST — Kontrollfluss (Bedingungen, Middleware-Gates) wird nicht geprüft"


class ExtractionResult:
    """Einfache Klasse statt @dataclass: Skript wird in Tests per importlib ohne
    Registrierung in sys.modules geladen (siehe tests/conftest.py); Python 3.13s
    `dataclasses` löst `cls.__module__` dann nicht auf und wirft AttributeError."""

    def __init__(self) -> None:
        self.paths: dict = {}
        self.unresolved: list = []


# --- minimaler YAML-Dumper -----------------------------------------------------
#
# Kein PyYAML installiert (Tier 1). Strings werden immer doppelt gequotet — das ist
# immer gültiges YAML, ohne dass eine Sonderfall-Erkennung (welche Strings brauchen
# Quotes?) selbst zur Fehlerquelle wird. Dieser Dumper ist für die kontrollierten,
# selbst erzeugten Strukturen hier gedacht (dict/list/str/bool/int/float/None), kein
# General-Purpose-YAML-Writer.


def _yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return _yaml_quote(value)
    raise TypeError(f"dump_yaml: nicht unterstützter Skalartyp {type(value).__name__}")


def _dump_dict(d: dict, indent: int, lines: list[str]) -> None:
    pad = "  " * indent
    for key, value in d.items():
        key_str = _yaml_quote(str(key))
        if isinstance(value, dict):
            if not value:
                lines.append(f"{pad}{key_str}: {{}}")
            else:
                lines.append(f"{pad}{key_str}:")
                _dump_dict(value, indent + 1, lines)
        elif isinstance(value, list):
            if not value:
                lines.append(f"{pad}{key_str}: []")
            else:
                lines.append(f"{pad}{key_str}:")
                _dump_list(value, indent + 1, lines)
        else:
            lines.append(f"{pad}{key_str}: {_scalar(value)}")


def _dump_list(items: list, indent: int, lines: list[str]) -> None:
    pad = "  " * indent
    for item in items:
        if isinstance(item, dict):
            if not item:
                lines.append(f"{pad}- {{}}")
                continue
            sub_lines: list[str] = []
            _dump_dict(item, indent + 1, sub_lines)
            first_pad = "  " * (indent + 1)
            first_stripped = sub_lines[0][len(first_pad):]
            lines.append(f"{pad}- {first_stripped}")
            lines.extend(sub_lines[1:])
        elif isinstance(item, list):
            if not item:
                lines.append(f"{pad}- []")
            else:
                lines.append(f"{pad}-")
                _dump_list(item, indent + 1, lines)
        else:
            lines.append(f"{pad}- {_scalar(item)}")


def dump_yaml(value: object) -> str:
    lines: list[str] = []
    if isinstance(value, dict):
        _dump_dict(value, 0, lines)
    elif isinstance(value, list):
        _dump_list(value, 0, lines)
    else:
        return _scalar(value) + "\n"
    return "\n".join(lines) + "\n"


# --- Pfad-Parameter --------------------------------------------------------


def _path_params_openapi_style(path: str) -> list[str]:
    return re.findall(r"\{([^}/]+)\}", path)


def _params_block(names: list[str]) -> list[dict]:
    return [{"name": name, "in": "path", "required": True, "schema": {"type": "string"}} for name in names]


# --- FastAPI: ast-basiert ---------------------------------------------------


def _route_call(decorator: ast.expr) -> tuple[str, ast.Call] | None:
    """Ist der Dekorator ein `<name>.<http-methode>(...)`-Aufruf? Liefert (methode, call)."""
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not isinstance(func, ast.Attribute) or func.attr not in HTTP_METHODS:
        return None
    if not isinstance(func.value, ast.Name):
        return None
    return func.attr, decorator


def _extract_functiondef(node: ast.FunctionDef | ast.AsyncFunctionDef, *, conditional: bool, relpath: str, result: ExtractionResult) -> None:
    for decorator in node.decorator_list:
        route = _route_call(decorator)
        if route is None:
            continue
        method, call = route
        if not call.args:
            continue
        path_arg = call.args[0]
        if not (isinstance(path_arg, ast.Constant) and isinstance(path_arg.value, str)):
            result.unresolved.append({"file": relpath, "line": getattr(call, "lineno", node.lineno), "reason": FASTAPI_UNRESOLVED_REASON, "function": node.name})
            continue
        path = path_arg.value
        operation: dict = {
            "operationId": node.name,
            "x-verified": not conditional,
            "parameters": _params_block(_path_params_openapi_style(path)),
            "responses": {"200": {"description": "TODO: aus Code ergänzen"}},
        }
        if conditional:
            operation["x-verified-reason"] = CONDITIONAL_REASON
        result.paths.setdefault(path, {})[method] = operation


def _walk_fastapi_body(body: list[ast.stmt], *, conditional: bool, relpath: str, result: ExtractionResult) -> None:
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _extract_functiondef(node, conditional=conditional, relpath=relpath, result=result)
        elif isinstance(node, ast.If):
            _walk_fastapi_body(node.body, conditional=True, relpath=relpath, result=result)
            _walk_fastapi_body(node.orelse, conditional=True, relpath=relpath, result=result)
        elif isinstance(node, ast.ClassDef):
            _walk_fastapi_body(node.body, conditional=conditional, relpath=relpath, result=result)


def extract_fastapi(src: Path) -> ExtractionResult:
    result = ExtractionResult()
    for path in sorted(src.rglob("*.py")):
        relpath = path.relative_to(src).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=relpath)
        except SyntaxError as exc:
            result.unresolved.append({"file": relpath, "line": exc.lineno or 0, "reason": f"Datei nicht parsbar: {exc.msg}"})
            continue
        _walk_fastapi_body(tree.body, conditional=False, relpath=relpath, result=result)
    return result


# --- Express/Hono: Textsuche ------------------------------------------------

_EXPRESS_ROUTE_RE = re.compile(
    r"\b(?:app|router)\.(get|post|put|patch|delete|options|head)\s*\(\s*['\"`]([^'\"`]+)['\"`]"
)


def _normalize_express_path(path: str) -> str:
    return re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", path)


def extract_express(src: Path) -> ExtractionResult:
    result = ExtractionResult()
    for path in sorted(list(src.rglob("*.js")) + list(src.rglob("*.ts"))):
        relpath = path.relative_to(src).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _EXPRESS_ROUTE_RE.finditer(text):
            method, raw_path = match.groups()
            openapi_path = _normalize_express_path(raw_path)
            line = text.count("\n", 0, match.start()) + 1
            operation = {
                "operationId": f"{method}_{openapi_path.strip('/').replace('/', '_').replace('{', '').replace('}', '') or 'root'}",
                "x-verified": False,
                "x-verified-reason": TEXT_SEARCH_REASON,
                "parameters": _params_block(_path_params_openapi_style(openapi_path)),
                "responses": {"200": {"description": "TODO: aus Code ergänzen"}},
                "x-source": f"{relpath}:{line}",
            }
            result.paths.setdefault(openapi_path, {})[method] = operation
    return result


FRAMEWORK_EXTRACTORS = {"fastapi": extract_fastapi, "express": extract_express, "hono": extract_express}


def extract(framework: str, src: Path) -> ExtractionResult:
    if framework != "auto":
        return FRAMEWORK_EXTRACTORS[framework](src)
    has_py = any(src.rglob("*.py"))
    has_js = any(src.rglob("*.js")) or any(src.rglob("*.ts"))
    combined = ExtractionResult()
    if has_py:
        py_result = extract_fastapi(src)
        combined.paths.update(py_result.paths)
        combined.unresolved.extend(py_result.unresolved)
    if has_js:
        js_result = extract_express(src)
        for path, methods in js_result.paths.items():
            combined.paths.setdefault(path, {}).update(methods)
        combined.unresolved.extend(js_result.unresolved)
    return combined


# --- Dokument-Aufbau ---------------------------------------------------------


def build_openapi_document(paths: dict, unresolved: list, *, title: str) -> dict:
    extraction: dict = {"tool": "extract_openapi.py", "unresolved": unresolved}
    if not paths:
        extraction["note"] = (
            "Keine Routen statisch gefunden — das Framework könnte nicht unterstützt sein, "
            "Routen sind dynamisch registriert, oder der --src-Pfad ist falsch. Nicht als "
            "vollständige Erfassung missverstehen."
        )
    return {
        "openapi": "3.0.3",
        "info": {"title": title, "version": "0.0.0-brownfield"},
        "paths": paths,
        "x-extraction": extraction,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brownfield: Routen statisch extrahieren, ohne die Anwendung zu importieren")
    parser.add_argument("--framework", choices=["fastapi", "express", "hono", "auto"], default="auto")
    parser.add_argument("--src", type=Path, required=True, help="Verzeichnis mit dem Quellcode")
    parser.add_argument("--out", type=Path, default=Path("api") / "openapi.yaml")
    parser.add_argument("--title", default="API (brownfield-erfasst)")
    args = parser.parse_args(argv)

    if not args.src.is_dir():
        print(f"--src nicht gefunden oder kein Verzeichnis: {args.src}", file=sys.stderr)
        return 1

    result = extract(args.framework, args.src)
    document = build_openapi_document(result.paths, result.unresolved, title=args.title)

    header = (
        f"# skill: rest-api-architect | schema: {SCHEMA_VERSION} | "
        f"generated: python skills/rest-api-architect/scripts/extract_openapi.py "
        f"--framework {args.framework} --src {args.src}\n"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(header + dump_yaml(document), encoding="utf-8")

    route_count = sum(len(methods) for methods in result.paths.values())
    print(f"{route_count} Route(n) statisch gefunden, {len(result.unresolved)} nicht auflösbar -> {args.out}")
    if route_count == 0:
        print(
            "Keine Routen statisch gefunden — Framework möglicherweise nicht unterstützt "
            "oder Routen sind dynamisch registriert. Datei trägt einen erklärenden Hinweis "
            "statt einer stillen leeren Spec."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
