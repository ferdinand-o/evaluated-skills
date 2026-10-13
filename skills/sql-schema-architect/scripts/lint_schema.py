#!/usr/bin/env python3
"""Modelle gegen das Konventions-Preset prüfen (R4). Tier 1 im Kern, sqlfluff optional.

Die Namens-, Typ-, Pflichtspalten-, FK- und Steckbrief-Prüfungen brauchen kein
sqlfluff — sie laufen überall. Ist sqlfluff installiert, ergänzt es die
SQL-Formatprüfung; fehlt es, sagt die Ausgabe das ausdrücklich (Spec 00 §3/§4:
kein stilles Überspringen), und die Kernprüfungen laufen trotzdem.

G2-Gate: meldet Verstöße, blockiert nicht.
"""

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VARCHAR_RE = re.compile(r"\b(String|VARCHAR|Varchar)\s*\(")
ARTIFACT_HEADER_RE = re.compile(
    r"^(?:<!--|#)\s*skill:\s*(?P<skill>[a-z0-9][a-z0-9-]*)\s*\|"
    r"\s*schema:\s*(?P<schema>\d+)\s*\|"
    r"\s*generated:\s*(?P<cmd>.+?)\s*(?:-->)?\s*$"
)
# Das mitgelieferte Preset liegt neben dem Skript, nicht im aufrufenden Projekt: ein
# repo-relativer Pfad gegen --repo fand es nur im cc-skills-Repo selbst und brach in
# jedem anderen Projekt — und in jeder installierten Skill — mit exit 1 ab.
SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONVENTIONS_PATH = SKILL_DIR / "assets" / "conventions.json"
PROJECT_OVERRIDE_PATH = Path(".skills/sql-schema-architect/conventions.json")
CACHE_PATH = Path(".skills") / "cache" / "lint-schema-report.json"


def _load_gen_erd():
    """gen_erd.py aus demselben scripts/-Verzeichnis dynamisch laden.

    Keine Paketstruktur nötig (Tier 1, standalone CLI-Skripte wie collect.py) —
    dasselbe Muster wie tests/conftest.py::load_script, hier aber zur Laufzeit
    innerhalb des Skripts selbst, damit `python lint_schema.py` ohne
    zusätzliches PYTHONPATH funktioniert.
    """
    path = Path(__file__).resolve().parent / "gen_erd.py"
    spec = importlib.util.spec_from_file_location("gen_erd", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("gen_erd", module)
    spec.loader.exec_module(module)
    return module


class LintError(RuntimeError):
    """Konventionen oder Modelle konnten nicht gelesen werden."""


def load_conventions(repo: Path, skill_dir: Path | None = None) -> dict:
    """Default-Preset, projektüberschrieben nach Spec 00 §1 unter .skills/<skill>/."""
    default_path = (skill_dir / "assets" / "conventions.json") if skill_dir else DEFAULT_CONVENTIONS_PATH
    if not default_path.is_file():
        raise LintError(f"Konventions-Preset fehlt: {default_path}")
    conventions = json.loads(default_path.read_text(encoding="utf-8"))

    override_path = repo / PROJECT_OVERRIDE_PATH
    if override_path.is_file():
        try:
            override = json.loads(override_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise LintError(f"{override_path}: kein gültiges JSON — {exc}") from exc
        conventions = {**conventions, **override}
    return conventions


def _finding(rule: str, table: str, message: str) -> dict:
    return {"rule": rule, "table": table, "message": message}


def check_naming(tables) -> list:
    findings = []
    for t in tables:
        if not t.resolvable:
            continue
        if not NAME_RE.match(t.name):
            findings.append(_finding("naming", t.name, f"Tabellenname '{t.name}' ist nicht snake_case"))
        for c in t.columns:
            if not NAME_RE.match(c.name):
                findings.append(_finding("naming", t.name, f"Spalte '{c.name}' ist nicht snake_case (z. B. camelCase erkannt)"))
    return findings


def check_types(tables, conventions: dict) -> list:
    findings = []
    types_cfg = conventions.get("types", {})
    reject_varchar = types_cfg.get("reject_varchar", True)
    reject_naive_datetime = types_cfg.get("reject_datetime_without_timezone", True)
    for t in tables:
        if not t.resolvable:
            continue
        for c in t.columns:
            if c.type_unresolved:
                # Review-Fund 4: SQL-Typ nicht statisch auflösbar (oft SQLAlchemy-2.0-Stil
                # ohne explizites Typ-Argument) — die Regeln unten würden hier ohnehin nicht
                # feuern, aber stillschweigend nichts zu finden ist keine bestandene Prüfung,
                # sondern eine ungeprüfte Spalte. Das muss sichtbar sein, nicht nur ein "?"
                # im Diagramm.
                hint = f" (Python-Annotation: {c.python_annotation})" if c.python_annotation else ""
                findings.append(_finding(
                    "type_coverage", t.name,
                    f"Typ von Spalte '{c.name}' nicht statisch auflösbar{hint} — "
                    f"varchar-/timestamptz-Prüfung konnte diese Spalte nicht bewerten",
                ))
                continue
            if reject_varchar and VARCHAR_RE.search(c.type_text):
                findings.append(_finding(
                    "type", t.name,
                    f"Spalte '{c.name}' verwendet {c.type_text!r} statt text laut Preset",
                ))
            if reject_naive_datetime and "DateTime" in c.type_text and "timezone=True" not in c.type_text:
                findings.append(_finding(
                    "type", t.name,
                    f"Spalte '{c.name}' verwendet DateTime ohne timezone=True (kein timestamptz)",
                ))
    return findings


def check_required_columns(tables, conventions: dict) -> list:
    findings = []
    required = conventions.get("required_columns", [])
    for t in tables:
        if not t.resolvable or not required:
            continue
        present = {c.name for c in t.columns}
        for name in required:
            if name not in present:
                findings.append(_finding("required_column", t.name, f"Pflichtspalte '{name}' fehlt"))
    return findings


def check_foreign_keys(tables, conventions: dict) -> list:
    findings = []
    if not conventions.get("foreign_keys", {}).get("ondelete_required", True):
        return findings
    for t in tables:
        if not t.resolvable:
            continue
        for c in t.columns:
            if c.fk_target and not c.fk_ondelete:
                findings.append(_finding(
                    "foreign_key", t.name,
                    f"Fremdschlüssel '{c.name}' -> {c.fk_target} ohne explizites ondelete-Verhalten",
                ))
    return findings


def _section_content(text: str, section: str) -> str | None:
    """Inhalt einer '## <section>'-Sektion bis zur nächsten '##'-Überschrift, oder None."""
    pattern = re.compile(
        rf"^##\s*{re.escape(section)}\s*$(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL
    )
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1).strip()


def check_steckbriefe(tables, conventions: dict, repo: Path) -> list:
    findings = []
    cfg = conventions.get("table_steckbrief", {})
    required_sections = cfg.get("required_sections", ["Zweck", "Owner", "Erwartetes Wachstum", "Hauptzugriffsmuster"])
    path_template = cfg.get("path_template", "docs/schema/{table}.md")

    for t in tables:
        if not t.resolvable:
            continue
        path = repo / path_template.format(table=t.name)
        has_index = any(c.has_index for c in t.columns)

        if not path.is_file():
            findings.append(_finding("steckbrief", t.name, f"kein Steckbrief unter {path_template.format(table=t.name)}"))
            if has_index:
                findings.append(_finding("index_pattern", t.name, "Index ohne benanntes Zugriffsmuster (kein Steckbrief vorhanden)"))
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        first_line = next((l for l in text.splitlines() if l.strip()), "")
        if not ARTIFACT_HEADER_RE.match(first_line.strip()):
            findings.append(_finding("steckbrief", t.name, "Steckbrief ohne Artefakt-Kopfzeile"))

        access_pattern_empty = True
        for section in required_sections:
            content = _section_content(text, section)
            if content is None:
                findings.append(_finding("steckbrief", t.name, f"Steckbrief-Sektion '{section}' fehlt"))
            elif not content:
                findings.append(_finding("steckbrief", t.name, f"Steckbrief-Sektion '{section}' ist leer"))
            if section == "Hauptzugriffsmuster" and content:
                access_pattern_empty = False

        if has_index and access_pattern_empty:
            findings.append(_finding("index_pattern", t.name, "Index ohne benanntes Zugriffsmuster (Sektion leer oder fehlend)"))

    return findings


def sqlfluff_status(sql_path: Path | None) -> dict:
    """Optionale Erweiterung (R4). Fehlt sqlfluff, ist das immer sichtbar, nie still."""
    executable = shutil.which("sqlfluff")
    if executable is None:
        return {
            "available": False,
            "note": "sqlfluff nicht installiert — SQL-Formatprüfung übersprungen, Kernprüfungen liefen trotzdem",
            "findings": [],
        }
    if sql_path is None:
        return {"available": True, "note": "sqlfluff verfügbar, aber kein --sql-Pfad angegeben", "findings": []}
    try:
        done = subprocess.run(
            [executable, "lint", "--format", "json", str(sql_path)],
            capture_output=True, text=True, timeout=120, check=False,
        )
        payload = json.loads(done.stdout or "[]")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return {"available": True, "note": f"sqlfluff-Lauf fehlgeschlagen: {exc}", "findings": []}
    findings = []
    for entry in payload if isinstance(payload, list) else []:
        for violation in entry.get("violations", []):
            findings.append(_finding("sqlfluff", entry.get("filepath", str(sql_path)), violation.get("description", "")))
    return {"available": True, "note": "sqlfluff ausgeführt", "findings": findings}


def run_lint(repo: Path, models_path: Path, sql_path: Path | None, skill_dir: Path | None) -> dict:
    gen_erd = _load_gen_erd()
    conventions = load_conventions(repo, skill_dir)
    result = gen_erd.scan_path(models_path)

    findings: list = []
    findings += check_naming(result.tables)
    findings += check_types(result.tables, conventions)
    findings += check_required_columns(result.tables, conventions)
    findings += check_foreign_keys(result.tables, conventions)
    findings += check_steckbriefe(result.tables, conventions, repo)

    sqlfluff = sqlfluff_status(sql_path)
    findings += sqlfluff["findings"]

    return {
        "_meta": {
            "skill": "sql-schema-architect",
            "schema": SCHEMA_VERSION,
            "generated": "python skills/sql-schema-architect/scripts/lint_schema.py",
        },
        "sqlfluff": {"available": sqlfluff["available"], "note": sqlfluff["note"]},
        "model_warnings": result.warnings,
        "findings": findings,
    }


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description="Modelle gegen das Konventions-Preset prüfen")
    parser.add_argument("models", type=Path, help="Model-Datei oder -Verzeichnis")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--skill-dir", type=Path, default=None, help="Skill-Verzeichnis für das Default-Preset (Test-/Eval-Zweck)")
    parser.add_argument("--sql", type=Path, default=None, help="Optional: SQL-Datei/-Verzeichnis für sqlfluff")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.models.exists():
        print(f"lint_schema: {args.models} existiert nicht", file=sys.stderr)
        return 1

    try:
        report = run_lint(args.repo, args.models, args.sql, args.skill_dir)
    except LintError as exc:
        print(f"lint_schema: {exc}", file=sys.stderr)
        return 1

    if not args.json:
        print(report["sqlfluff"]["note"])
        for w in report["model_warnings"]:
            print(f"Modell-Warnung: {w}")
        for f in report["findings"]:
            print(f"[{f['rule']}] {f['table']}: {f['message']}")
        if not report["findings"]:
            print("Keine Befunde.")

    target = args.repo / CACHE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 1 if report["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
