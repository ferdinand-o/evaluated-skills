#!/usr/bin/env python3
"""Breaking-Change-Gate: Spectral-Lint + oasdiff-Check + Konventions-Checkliste. Tier 3, G2.

R3 — Spectral und oasdiff sind hier nicht installiert, `npx` fehlt, Node ist da. Dieses
Skript ist trotzdem vollständig geschrieben, inklusive Erfolgspfad. Was das bedeutet:

- `detect_toolchain`, `describe_toolchain_gap`, `run_checklist` und die Degradationsmeldung
  sind in dieser Umgebung echt getestet — sie brauchen keine externe Toolchain.
- `run_lint`/`run_breaking_change_check` haben einen echten Erfolgspfad (`subprocess.run` auf
  Spectral/oasdiff, JSON-Parsing der Ausgabe), der nur mit **gemocktem** `subprocess.run`
  getestet ist. Kein Test hier behauptet eine echte Spectral-/oasdiff-Integration — das bleibt
  in `docs/known-limits.md` als ungeprüft vermerkt.
- Fehlt die Toolchain, trägt das Ergebnis sichtbar „ungeprüft (...)" statt stillschweigend zu
  bestehen oder zu verschwinden (Spec 00 §4). Die Konventions-Checkliste läuft davon
  unabhängig immer — sie ist reine Textprüfung, kein Aufruf einer externen Toolchain.
- Durchsetzungsgrad **G2**: Das Urteil ist maschinell, der Aufruf bleibt Teil des Workflows.
  Dieses Skript nennt sich nirgends „Blocker" — wer daran vorbei committet, umgeht es.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEGRADED_BOTH = "ungeprüft (Spectral/oasdiff nicht verfügbar)"
DEGRADED_SPECTRAL = "ungeprüft (Spectral nicht verfügbar)"
DEGRADED_OASDIFF = "ungeprüft (oasdiff nicht verfügbar)"
NO_PREVIOUS_MESSAGE = "kein Vorgänger, Breaking-Change-Check übersprungen"

_SPECTRAL_SEVERITY = {0: "error", 1: "warn", 2: "info", 3: "hint"}


# --- Toolchain-Erkennung (der einzig verifizierbare Zweig in dieser Umgebung) -----


def detect_toolchain(which=shutil.which) -> dict:
    """`which` ist injizierbar, damit dieser Kern ohne echte Toolchain testbar ist."""
    node = which("node") is not None
    npx = which("npx") is not None
    spectral_direct = which("spectral") is not None
    oasdiff = which("oasdiff") is not None
    return {
        "node": node,
        "npx": npx,
        "spectral_direct": spectral_direct,
        "spectral_usable": spectral_direct or (node and npx),
        "oasdiff_usable": oasdiff,
    }


def describe_toolchain_gap(status: dict) -> str | None:
    missing_spectral = not status["spectral_usable"]
    missing_oasdiff = not status["oasdiff_usable"]
    if missing_spectral and missing_oasdiff:
        return DEGRADED_BOTH
    if missing_spectral:
        return DEGRADED_SPECTRAL
    if missing_oasdiff:
        return DEGRADED_OASDIFF
    return None


# --- Konventions-Checkliste: reine Textprüfung, läuft immer -----------------------
#
# Das ist der Teil aus R3, der auch ohne Spectral "als Checkliste abgearbeitet" wird.
# Bewusst textbasiert statt strukturell: Ein Claude-editiertes OpenAPI-YAML folgt keinem
# festen Dialekt, und dieses Skript bringt kein YAML-Parsing mit (kein PyYAML installiert).
# Eine Regex-Checkliste ist gröber als echtes Lint, aber ehrlich als das benannt, was sie ist.

_VERB_CANDIDATES = ("get", "create", "update", "delete", "list", "fetch", "remove")


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "passed": passed, "skipped": False, "detail": detail}


def _skip(name: str, detail: str) -> dict:
    """Voraussetzung des Checks fehlt im Dokument (kein Listen-Endpoint, keine der
    relevanten Methoden, ...). Weder `passed` noch `failed` — explizit als drittes
    Ergebnis markiert, damit es im Report nicht mit einem stillschweigend bestandenen
    Check verwechselt wird (Spec 00 §4: Auslassung sichtbar machen, nie verschwinden lassen)."""
    return {"name": name, "passed": None, "skipped": True, "detail": detail}


def _versioning_prefix_regex(prefix_pattern: str) -> re.Pattern:
    """`versioning.prefix_pattern` in conventions.json ist als Regex auf einen einzelnen
    Pfad-String formuliert (typischerweise `^/v[0-9]+/`), nicht auf den Rohtext des ganzen
    Dokuments. Der Anker `^` wird hier durch Zeilenanfang plus optionalem Leerraum und
    optionalem Anführungszeichen ersetzt: YAML quotet Pfad-Schlüssel nicht zwingend (siehe
    assets/openapi-skeleton.yaml), `extract_openapi.py`s Dumper dagegen immer — beide Stile
    müssen erkannt werden, sonst meldet der Check einen Fehlalarm rein je nach Schreibstil."""
    inner = prefix_pattern.lstrip("^")
    return re.compile(rf'(?m)^[ \t]*"?{inner}')


def _document_has_method(openapi_text: str, method: str) -> bool:
    """Textheuristik (kein YAML-Parsing, siehe Modulkopf): erkennt eine HTTP-Methode als
    eigene Mapping-Key-Zeile (`post:` oder `"post":`), so wie OpenAPI Pfad-Items sie
    schreiben — Grundlage dafür, ob idempotency.header überhaupt anwendbar ist."""
    escaped = re.escape(method.strip().lower())
    pattern = re.compile(rf'(?mi)^[ \t]*"?{escaped}"?[ \t]*:[ \t]*$')
    return bool(pattern.search(openapi_text))


def _document_has_list_endpoint(openapi_text: str) -> bool:
    """Textheuristik für „es gibt einen Listen-Endpoint": ein Array-typisiertes
    Antwortschema (`type: array` bzw. `"type": "array"`) ist das übliche OpenAPI-Signal für
    eine Collection-Response. Ohne dieses Signal ist Cursor-Paginierung schlicht nicht
    anwendbar — ihr Fehlen ist dann kein Konventionsbruch, sondern eine fehlende Voraussetzung."""
    return bool(re.search(r'"?type"?\s*:\s*"?array"?', openapi_text))


def run_checklist(openapi_text: str, conventions: dict) -> list[dict]:
    checks: list[dict] = []

    errors = conventions.get("errors") or {}
    media_type = errors.get("media_type")
    if media_type:
        passed = media_type in openapi_text
        checks.append(_check("errors.media_type", passed, f"{media_type} {'gefunden' if passed else 'nicht gefunden'}"))

    pagination = conventions.get("pagination") or {}
    request_params = pagination.get("request_params")
    response_fields = pagination.get("response_fields")
    if request_params or response_fields:
        if _document_has_list_endpoint(openapi_text):
            if request_params:
                missing = [p for p in request_params if p not in openapi_text]
                checks.append(_check("pagination.request_params", not missing, "fehlend: " + ", ".join(missing) if missing else "alle gefunden"))
            if response_fields:
                missing = [f for f in response_fields if f not in openapi_text]
                checks.append(_check("pagination.response_fields", not missing, "fehlend: " + ", ".join(missing) if missing else "alle gefunden"))
        else:
            skip_detail = "kein Listen-Endpoint gefunden (kein Array-Antwortschema) — Voraussetzung fehlt"
            if request_params:
                checks.append(_skip("pagination.request_params", skip_detail))
            if response_fields:
                checks.append(_skip("pagination.response_fields", skip_detail))

    versioning = conventions.get("versioning") or {}
    prefix_pattern = versioning.get("prefix_pattern")
    if prefix_pattern:
        passed = bool(_versioning_prefix_regex(prefix_pattern).search(openapi_text))
        checks.append(_check("versioning.prefix_pattern", passed, "versionierter Pfad gefunden" if passed else "kein versionierter Pfad gefunden"))

    idempotency = conventions.get("idempotency") or {}
    header = idempotency.get("header")
    if header:
        required_for_methods = idempotency.get("required_for_methods") or []
        applicable = not required_for_methods or any(_document_has_method(openapi_text, m) for m in required_for_methods)
        if applicable:
            passed = header in openapi_text
            checks.append(_check("idempotency.header", passed, f"{header} {'gefunden' if passed else 'nicht gefunden'}"))
        else:
            methods_str = ", ".join(required_for_methods)
            checks.append(_skip("idempotency.header", f"keine der Methoden ({methods_str}) im Dokument gefunden — Voraussetzung fehlt"))

    naming = conventions.get("naming") or {}
    if naming.get("field_case") == "snake_case":
        camel_hits = re.findall(r'"([a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*)":', openapi_text)
        passed = not camel_hits
        checks.append(_check("naming.field_case", passed, "keine camelCase-artigen Feldnamen" if passed else f"camelCase-artig: {', '.join(sorted(set(camel_hits)))}"))
    if naming.get("no_verbs_in_paths"):
        exceptions = set(naming.get("verb_exceptions") or [])
        hits = [v for v in _VERB_CANDIDATES if v not in exceptions and re.search(rf'/{v}(/|"|$)', openapi_text)]
        passed = not hits
        checks.append(_check("naming.no_verbs_in_paths", passed, "keine Verben in Pfaden" if passed else f"Verb(e) in Pfad gefunden: {', '.join(hits)}"))

    timestamps = conventions.get("timestamps") or {}
    if timestamps.get("format") == "rfc3339":
        passed = "date-time" in openapi_text
        checks.append(_check("timestamps.format", passed, "format: date-time gefunden" if passed else "kein format: date-time gefunden"))

    return checks


# --- Erfolgspfad: subprocess-Aufrufe, nur mit Mock getestet -----------------------


def _build_spectral_command(openapi_path, ruleset_path, status: dict) -> list[str]:
    if status["spectral_direct"]:
        return ["spectral", "lint", str(openapi_path), "--ruleset", str(ruleset_path), "-f", "json"]
    return ["npx", "--yes", "@stoplight/spectral-cli", "lint", str(openapi_path), "--ruleset", str(ruleset_path), "-f", "json"]


def _parse_json_or_empty(stdout: str) -> list:
    if not stdout.strip():
        return []
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def parse_spectral_output(stdout: str) -> list[dict]:
    findings = []
    for item in _parse_json_or_empty(stdout):
        if not isinstance(item, dict):
            continue
        findings.append({
            "code": item.get("code"),
            "message": item.get("message"),
            "severity": _SPECTRAL_SEVERITY.get(item.get("severity"), "unknown"),
        })
    return findings


def run_lint(openapi_path, ruleset_path, status: dict, *, run=subprocess.run) -> dict:
    if not status["spectral_usable"]:
        return {"tool": "spectral", "ok": None, "degraded": True, "message": DEGRADED_SPECTRAL, "findings": []}

    cmd = _build_spectral_command(openapi_path, ruleset_path, status)
    try:
        completed = run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"tool": "spectral", "ok": False, "degraded": False, "message": f"Spectral-Aufruf fehlgeschlagen: {exc}", "findings": []}

    findings = parse_spectral_output(completed.stdout)
    ok = not any(f["severity"] == "error" for f in findings)
    return {"tool": "spectral", "ok": ok, "degraded": False, "message": "geprüft", "findings": findings}


def parse_oasdiff_output(stdout: str) -> list[dict]:
    findings = []
    for item in _parse_json_or_empty(stdout):
        if not isinstance(item, dict):
            continue
        findings.append({
            "id": item.get("id"),
            "text": item.get("text") or item.get("message"),
            "level": item.get("level"),
        })
    return findings


def run_breaking_change_check(previous_path, current_path, status: dict, *, run=subprocess.run) -> dict:
    if previous_path is None or not Path(previous_path).is_file():
        return {"tool": "oasdiff", "ok": None, "degraded": False, "message": NO_PREVIOUS_MESSAGE, "findings": []}

    if not status["oasdiff_usable"]:
        return {"tool": "oasdiff", "ok": None, "degraded": True, "message": DEGRADED_OASDIFF, "findings": []}

    cmd = ["oasdiff", "breaking", str(previous_path), str(current_path), "-f", "json"]
    try:
        completed = run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"tool": "oasdiff", "ok": False, "degraded": False, "message": f"oasdiff-Aufruf fehlgeschlagen: {exc}", "findings": []}

    findings = parse_oasdiff_output(completed.stdout)
    ok = len(findings) == 0
    return {"tool": "oasdiff", "ok": ok, "degraded": False, "message": "geprüft" if ok else f"{len(findings)} Breaking Change(s)", "findings": findings}


# --- Gesamt-Report -----------------------------------------------------------------


def build_gate_report(openapi_path, ruleset_path, conventions: dict, *, previous_path=None, which=shutil.which, run=subprocess.run) -> dict:
    status = detect_toolchain(which=which)
    openapi_path = Path(openapi_path)
    text = openapi_path.read_text(encoding="utf-8", errors="replace") if openapi_path.is_file() else ""

    checklist = run_checklist(text, conventions)
    lint = run_lint(openapi_path, ruleset_path, status, run=run)
    breaking = run_breaking_change_check(previous_path, openapi_path, status, run=run)

    checklist_ok = all(c["passed"] is not False for c in checklist)
    overall_ok = checklist_ok and lint["ok"] is not False and breaking["ok"] is not False

    return {
        "status": status,
        "checklist": checklist,
        "checklist_ok": checklist_ok,
        "lint": lint,
        "breaking": breaking,
        "overall_ok": overall_ok,
    }


def format_report(report: dict) -> str:
    lines = ["Konventions-Checkliste:"]
    for check in report["checklist"]:
        if check.get("skipped"):
            mark = "[SKIP]"
        elif check["passed"]:
            mark = "[OK]"
        else:
            mark = "[FAIL]"
        lines.append(f"  {mark} {check['name']}: {check['detail']}")

    lines.append(f"Spectral-Lint: {report['lint']['message']}")
    for finding in report["lint"]["findings"]:
        lines.append(f"  - {finding['severity']}: {finding['code']} — {finding['message']}")

    lines.append(f"Breaking-Change-Check: {report['breaking']['message']}")
    for finding in report["breaking"]["findings"]:
        lines.append(f"  - {finding.get('level')}: {finding.get('text')}")

    gap = describe_toolchain_gap(report["status"])
    if gap:
        lines.append(gap)

    lines.append(f"Gesamtergebnis: {'bestanden' if report['overall_ok'] else 'Verstoß gemeldet'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Breaking-Change-Gate: Lint + oasdiff + Konventions-Checkliste (G2 — meldet Verstoß, blockiert nicht)")
    parser.add_argument("--openapi", type=Path, required=True)
    parser.add_argument("--ruleset", type=Path, required=True)
    parser.add_argument("--conventions", type=Path, required=True)
    parser.add_argument("--previous", type=Path, default=None, help="Letzte committete OpenAPI-Version, falls vorhanden")
    args = parser.parse_args(argv)

    if not args.openapi.is_file():
        print(f"--openapi nicht gefunden: {args.openapi}", file=sys.stderr)
        return 2
    if not args.conventions.is_file():
        print(f"--conventions nicht gefunden: {args.conventions}", file=sys.stderr)
        return 2

    conventions = json.loads(args.conventions.read_text(encoding="utf-8"))
    report = build_gate_report(args.openapi, args.ruleset, conventions, previous_path=args.previous)
    print(format_report(report))
    return 0 if report["overall_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
