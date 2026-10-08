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
- Eine Route hinter einer Bedingung (`if`/`for`/`while`/`try`, ...) -> `x-verified: false`.
- Jede über Textsuche gefundene Express/Hono-Route -> `x-verified: false`, immer — Textsuche
  ohne Kontrollfluss ist strukturell unsicherer als AST.
- Was wie ein Routen-Dekorator oder `add_api_route()`/`add_route()`-Aufruf *aussieht*, aber
  vom AST-Walk nicht zugeordnet werden konnte (z. B. eine aliasierte Decorator-Funktion),
  landet als dateiweiter `unresolved`-Eintrag statt spurlos zu verschwinden — Ergebnis eines
  Reviews, der drei Fälle nachwies, in denen Routen zuvor ganz ohne Spur verloren gingen:
  `path=`-Keyword-Argumente, programmatische `add_api_route()`-Registrierung, und
  Express-Router mit anderem Variablennamen als `app`/`router`.

Bekannte Grenzen (siehe docs/known-limits.md): Router-Präfixe aus
`app.include_router(sub_router, prefix="/v1")` in einer anderen Datei werden nicht aufgelöst;
Express-Chaining (`router.route(path).get(handler)`) wird nicht erkannt.
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
    # \r fehlte hier (Review-Fund): ein rohes CR innerhalb doppelter Anführungszeichen wird
    # von YAML-Loadern gemäß Flow-Scalar-Zeilenumbruch-Regeln still zu einem Leerzeichen
    # gefaltet — kein Parse-Fehler, sondern eine unbemerkte Verfälschung des Werts.
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
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


_REGISTRATION_METHODS = frozenset({"add_api_route", "add_route"})

# Review-Fund: eine Text-Heuristik als Auffangnetz. Was wie ein Routen-Dekorator oder ein
# add_api_route()/add_route()-Aufruf *aussieht*, aber vom AST-Walk unten nicht zugeordnet
# werden konnte (z. B. eine aliasierte Decorator-Funktion `get = app.get`, `@get(...)`),
# fällt sonst spurlos durch. Diese beiden Muster zählen Vorkommen im Rohtext, unabhängig vom
# AST — der Vergleich "Lookalikes gefunden" vs. "tatsächlich zugeordnet" in extract_fastapi()
# entscheidet, ob ein dateiweiter unresolved-Hinweis nötig ist.
_DECORATOR_LOOKALIKE_RE = re.compile(
    r"^[ \t]*@[\w.]*\b(?:get|post|put|patch|delete|options|head)\s*\(", re.MULTILINE
)
_REGISTRATION_LOOKALIKE_RE = re.compile(r"\.(?:add_api_route|add_route)\s*\(")


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


def _path_argument(call: ast.Call, *, keyword: str = "path") -> ast.expr | None:
    """Erstes positionales Argument, sonst das benannte Keyword — Review-Fund: ein Pfad, der
    nur als `path=`-Keyword übergeben wird (`@app.get(path="/x")`), hatte `call.args == []`
    und wurde davor komplett übersprungen, ohne jede Spur."""
    if call.args:
        return call.args[0]
    for kw in call.keywords:
        if kw.arg == keyword:
            return kw.value
    return None


def _literal_path_or_unresolved(path_arg: ast.expr | None, *, call: ast.Call, node_lineno: int, relpath: str, function: str | None, reason_no_arg: str, result: ExtractionResult) -> str | None:
    """Liefert den Pfad-String, oder None nach Eintrag in `unresolved` — nie stilles Verwerfen."""
    line = getattr(call, "lineno", node_lineno)
    if path_arg is None:
        result.unresolved.append({"file": relpath, "line": line, "reason": reason_no_arg, "function": function})
        return None
    if not (isinstance(path_arg, ast.Constant) and isinstance(path_arg.value, str)):
        result.unresolved.append({"file": relpath, "line": line, "reason": FASTAPI_UNRESOLVED_REASON, "function": function})
        return None
    return path_arg.value


def _build_operation(*, operation_id: str, path: str, conditional: bool, relpath: str, line: int) -> dict:
    operation: dict = {
        "operationId": operation_id,
        "x-verified": not conditional,
        "parameters": _params_block(_path_params_openapi_style(path)),
        "responses": {"200": {"description": "TODO: aus Code ergänzen"}},
        "x-source": f"{relpath}:{line}",
    }
    if conditional:
        operation["x-verified-reason"] = CONDITIONAL_REASON
    return operation


def _extract_functiondef(node: ast.FunctionDef | ast.AsyncFunctionDef, *, conditional: bool, relpath: str, result: ExtractionResult) -> None:
    for decorator in node.decorator_list:
        route = _route_call(decorator)
        if route is None:
            continue
        method, call = route
        path_arg = _path_argument(call)
        path = _literal_path_or_unresolved(
            path_arg, call=call, node_lineno=node.lineno, relpath=relpath, function=node.name,
            reason_no_arg="Kein Pfad-Argument gefunden (weder positional noch als path=Keyword)",
            result=result,
        )
        if path is None:
            continue
        operation = _build_operation(operation_id=node.name, path=path, conditional=conditional, relpath=relpath, line=getattr(call, "lineno", node.lineno))
        result.paths.setdefault(path, {})[method] = operation


def _registration_methods(call: ast.Call) -> list[str]:
    for kw in call.keywords:
        if kw.arg == "methods" and isinstance(kw.value, ast.List):
            methods = [
                elt.value.lower()
                for elt in kw.value.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str) and elt.value.lower() in HTTP_METHODS
            ]
            if methods:
                return methods
    # Starlette/FastAPI-Default, wenn `methods` fehlt: GET. Dokumentierte Annahme, keine Norm.
    return ["get"]


def _registration_endpoint_name(call: ast.Call) -> str:
    target = call.args[1] if len(call.args) >= 2 else None
    if target is None:
        for kw in call.keywords:
            if kw.arg == "endpoint":
                target = kw.value
                break
    return target.id if isinstance(target, ast.Name) else "unbekannt"


def _handle_registration_call(call: ast.Call, *, conditional: bool, relpath: str, result: ExtractionResult) -> None:
    """`app.add_api_route(...)`/`app.add_route(...)` — programmatische Registrierung ohne
    Dekorator. Review-Fund: wurde vom Walk unten überhaupt nicht besucht (kein `ast.Expr`-
    Zweig), Routen verschwanden komplett. `.value` wird bewusst nicht auf `ast.Name`
    eingeschränkt (anders als bei Dekoratoren) — die Methodennamen sind spezifisch genug,
    dass eine engere Prüfung nur weitere Fälle stumm verlieren würde."""
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr not in _REGISTRATION_METHODS:
        return
    path_arg = _path_argument(call)
    path = _literal_path_or_unresolved(
        path_arg, call=call, node_lineno=call.lineno, relpath=relpath, function=None,
        reason_no_arg=f"{func.attr}(): kein Pfad-Argument gefunden (weder positional noch als path=Keyword)",
        result=result,
    )
    if path is None:
        return
    endpoint_name = _registration_endpoint_name(call)
    for method in _registration_methods(call):
        operation = _build_operation(operation_id=endpoint_name, path=path, conditional=conditional, relpath=relpath, line=call.lineno)
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
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            # Nicht garantiert einmalig/unbedingt wie ein Top-Level-Statement — konservativ
            # als conditional behandelt (x-verified: false), statt Sicherheit vorzutäuschen.
            _walk_fastapi_body(node.body, conditional=True, relpath=relpath, result=result)
            _walk_fastapi_body(node.orelse, conditional=True, relpath=relpath, result=result)
        elif isinstance(node, ast.Try):
            _walk_fastapi_body(node.body, conditional=True, relpath=relpath, result=result)
            for handler in node.handlers:
                _walk_fastapi_body(handler.body, conditional=True, relpath=relpath, result=result)
            _walk_fastapi_body(node.orelse, conditional=True, relpath=relpath, result=result)
            _walk_fastapi_body(node.finalbody, conditional=True, relpath=relpath, result=result)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            _walk_fastapi_body(node.body, conditional=conditional, relpath=relpath, result=result)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            _handle_registration_call(node.value, conditional=conditional, relpath=relpath, result=result)


def _count_entries_for_file(result: ExtractionResult, relpath: str) -> int:
    prefix = relpath + ":"
    count = sum(
        1
        for methods in result.paths.values()
        for op in methods.values()
        if op.get("x-source", "").startswith(prefix)
    )
    count += sum(1 for entry in result.unresolved if entry.get("file") == relpath)
    return count


def extract_fastapi(src: Path) -> ExtractionResult:
    result = ExtractionResult()
    for path in sorted(src.rglob("*.py")):
        relpath = path.relative_to(src).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text, filename=relpath)
        except SyntaxError as exc:
            result.unresolved.append({"file": relpath, "line": exc.lineno or 0, "reason": f"Datei nicht parsbar: {exc.msg}"})
            continue

        before = _count_entries_for_file(result, relpath)
        _walk_fastapi_body(tree.body, conditional=False, relpath=relpath, result=result)
        attributed = _count_entries_for_file(result, relpath) - before

        lookalikes = len(_DECORATOR_LOOKALIKE_RE.findall(text)) + len(_REGISTRATION_LOOKALIKE_RE.findall(text))
        gap = lookalikes - attributed
        if gap > 0:
            result.unresolved.append({
                "file": relpath,
                "line": 0,
                "reason": (
                    f"{gap} routenartige Aufruf(e) im Text gefunden, aber von der AST-Analyse "
                    f"nicht zugeordnet (z. B. aliasierte Decorator-Funktion oder unbekanntes "
                    f"Registrierungsmuster) — Datei manuell prüfen"
                ),
                "function": None,
            })
    return result


# --- Express/Hono: Textsuche ------------------------------------------------


# Review-Fund (Defekt 3): auf Variablennamen `app`/`router` beschränkt, verlor jede Route
# auf anders benannten Router-Objekten (`usersRouter`, `ordersRouter`, ...) spurlos — in
# Express sehr üblich. Jetzt: beliebiger gültiger JS-Bezeichner vor dem Methodennamen.
# Kosten: höheres False-Positive-Risiko bei generischen `.get()`-Aufrufen auf Nicht-Router-
# Objekten (Cache/Map-Zugriffe wie `cache.get('key')`) — hingenommen, weil jeder Treffer
# ohnehin x-verified: false trägt und nie stillschweigend als geprüft gilt (siehe
# docs/known-limits.md).
_EXPRESS_ROUTE_RE = re.compile(
    r"\b[A-Za-z_$][A-Za-z0-9_$]*\.(get|post|put|patch|delete|options|head)\s*\(\s*['\"`]([^'\"`]+)['\"`]"
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
