#!/usr/bin/env python3
"""Alembic-Revisionen statisch auf Gefahrenklasse prüfen. Tier 1: nur Stdlib.

Die Revision wird mit `ast` gelesen, nie importiert oder ausgeführt — eine
Revision auszuführen ist genau die Handlung, vor der diese Skill warnt.

Drei Gefahrenklassen je Operation: grün (additiv, locksicher), gelb (kurzer
Lock, Auflagen), rot (Tabellen-Rewrite oder Langzeit-Lock, Pflicht ist ein
dokumentierter Mehrschritt-Plan). Eine vierte, eigene Kategorie —
`unknown` — führt nie zu einem stillschweigend grünen Urteil: `op.execute()`
mit rohem SQL und jede unbekannte `op.*`-Methode sind statisch nicht
klassifizierbar und werden immer als "nicht bewertbar, manuell prüfen"
gemeldet.
"""

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1

GREEN = "green"
YELLOW = "yellow"
RED = "red"
UNKNOWN = "unknown"
_RANK = {GREEN: 0, YELLOW: 1, RED: 2}

HOOK_MARKER = "sql-schema-architect/scripts/migration_gate.py"
MULTISTEP_RE = re.compile(r"mehrschritt-plan:\s*(.{11,})", re.IGNORECASE)
SETTINGS_FILES = (".claude/settings.json", ".claude/settings.local.json")

# Vokabular aus migration-safety.md, das ein echtes Mehrschritt-Muster von hohlem Freitext
# unterscheidet (Fund 1 des Reviews: "# Mehrschritt-Plan: siehe unten unten" erfüllte bisher
# nur eine Längenschwelle). Der Marker muss mindestens zwei dieser Begriffe treffen, sonst
# ist er Form ohne Inhalt — mechanisch ist das die Grenze dessen, was prüfbar ist; der reale
# Inhalt (stimmt der Plan tatsächlich?) bleibt Sache der manuellen Freigabe, siehe
# classify_revision.
MULTISTEP_KEYWORDS = (
    "nullable", "backfill", "batch", "constraint", "valid", "concurrently", "revision",
)


class GateError(RuntimeError):
    """Die Revision konnte nicht gelesen oder geparst werden."""


@dataclass(frozen=True)
class OpCall:
    method: str
    args_text: list[str]
    kwargs_text: dict[str, str]
    lineno: int
    node: ast.Call = field(compare=False, repr=False)
    # `name -> Column(...)/mapped_column(...)`-Aufruf für einfache lokale Zuweisungen im
    # selben Funktionsrumpf, z. B. `col = sa.Column(..., nullable=False); op.add_column(t, col)`.
    # Pro Funktions-Scope neu berechnet (siehe _op_calls_in), nie über Funktionsgrenzen gemischt.
    local_columns: dict = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True)
class Classification:
    op: OpCall
    verdict: str  # green/yellow/red/unknown
    reason: str
    auflagen: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RevisionInfo:
    path: Path
    has_upgrade: bool
    has_downgrade: bool
    downgrade_empty: bool
    one_way_reason: str | None
    ops: list[OpCall]
    created_tables: set[str]
    multistep_note: str | None
    upgrade_nontrivial_without_ops: bool


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover — defensiv, ast.unparse ist stabil ab 3.9
        return "<unparsable>"


def _call_kwargs(call: ast.Call) -> dict[str, str]:
    return {kw.arg: _unparse(kw.value) for kw in call.keywords if kw.arg is not None}


def _call_args(call: ast.Call) -> list[str]:
    return [_unparse(a) for a in call.args]


def _call_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _local_column_vars(body: list[ast.stmt]) -> dict:
    """`name -> Call`-Zuordnung für einfache `name = Column(...)`/`mapped_column(...)`-
    Zuweisungen direkt im Funktionsrumpf (nicht in verschachtelten Blöcken wie `if`/`for` —
    das ist eine bewusste Grenze, siehe migration-safety.md)."""
    result: dict = {}
    for stmt in body:
        target = None
        value = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            target, value = stmt.targets[0].id, stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            target, value = stmt.target.id, stmt.value
        if target and isinstance(value, ast.Call) and _call_name(value) in ("Column", "mapped_column"):
            result[target] = value
    return result


def _local_functions(tree: ast.Module) -> dict:
    """Modulweite Funktionsdefinitionen nach Name — die Grenze für „soweit statisch
    auflösbar" beim Folgen von Hilfsfunktions-Aufrufen (siehe _op_calls_in)."""
    return {n.name: n for n in ast.iter_child_nodes(tree) if isinstance(n, ast.FunctionDef)}


def _op_calls_in(node: ast.AST, functions: dict, seen: set | None = None) -> list[OpCall]:
    """Alle `op.<method>(...)`-Aufrufe innerhalb eines AST-Teilbaums, in Fundreihenfolge.

    Folgt Aufrufen an modulweite Funktionen im selben File (`upgrade(): _apply()` mit
    `def _apply(): op.execute(...)` an anderer Stelle im Modul), rekursiv mit Zyklenschutz.
    Was nicht gefolgt wird — bewusste Grenze, nicht Versehen: Attribut-Aufrufe (`self.x()`,
    `helpers.x()`), Aufrufe über Variablen, Methoden auf Klassen, Aufrufe importierter
    Funktionen, dynamisch aufgelöste Aufrufe (`getattr(...)`). Diese Fälle bleiben
    unsichtbar für den Scanner — sie zählen nicht mehr zu den `ops`, wodurch eine Revision,
    deren `upgrade()` ausschließlich über solche Wege operiert, auf 0 gefundene Operationen
    fällt. `classify_revision` behandelt das als eigenen Befund, nicht als `pass`.
    """
    if seen is None:
        seen = set()
    local_columns = _local_column_vars(node.body) if hasattr(node, "body") else {}
    found: list[OpCall] = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "op":
            found.append(OpCall(
                method=func.attr,
                args_text=_call_args(sub),
                kwargs_text=_call_kwargs(sub),
                lineno=sub.lineno,
                node=sub,
                local_columns=local_columns,
            ))
            continue
        if isinstance(func, ast.Name) and func.id in functions and func.id not in seen:
            seen.add(func.id)
            found.extend(_op_calls_in(functions[func.id], functions, seen))
    return sorted(found, key=lambda o: o.lineno)


def _add_column_target(op: OpCall) -> tuple[str, dict]:
    """(status, kwargs) für die Spalte in `op.add_column(table, column)`.

    status ist `inline` (Column(...) direkt als Argument), `resolved` (einfache lokale
    Variable, siehe `_local_column_vars`) oder `unresolved` (weder noch — z. B. Rückgabewert
    eines Funktionsaufrufs, Import, Zuweisung in einem verschachtelten Block). `unresolved`
    heißt: `nullable`/`server_default` sind nicht einsehbar, die Operation darf deshalb nicht
    grün klassifiziert werden.
    """
    if len(op.node.args) < 2:
        return "unresolved", {}
    column_arg = op.node.args[1]
    if isinstance(column_arg, ast.Call) and _call_name(column_arg) in ("Column", "mapped_column"):
        return "inline", _call_kwargs(column_arg)
    if isinstance(column_arg, ast.Name):
        resolved = op.local_columns.get(column_arg.id)
        if resolved is not None:
            return "resolved", _call_kwargs(resolved)
    return "unresolved", {}


def _find_func(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _is_docstring_expr(stmt: ast.stmt) -> bool:
    return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str)


def _is_trivial_body(func: ast.FunctionDef | None) -> bool:
    """True, wenn eine Funktion (abgesehen von einem Docstring) leer ist oder nur `pass` enthält."""
    if func is None:
        return True
    body = [s for s in func.body if not _is_docstring_expr(s)]
    if not body:
        return True
    return len(body) == 1 and isinstance(body[0], ast.Pass)


def _downgrade_status(func: ast.FunctionDef | None) -> tuple[bool, str | None]:
    """(ist_leer, one_way_reason). one_way_reason gesetzt heißt: begründete Einbahn-Migration."""
    if _is_trivial_body(func):
        return True, None
    body = [s for s in func.body if not _is_docstring_expr(s)]
    if len(body) == 1 and isinstance(body[0], ast.Raise):
        raise_stmt = body[0]
        exc = raise_stmt.exc
        if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and exc.func.id == "NotImplementedError":
            reason = None
            if exc.args and isinstance(exc.args[0], ast.Constant) and isinstance(exc.args[0].value, str):
                reason = exc.args[0].value.strip()
            if reason and len(reason) > 5:
                return False, reason
        return True, None
    return False, None


def _created_tables(ops: list[OpCall]) -> set[str]:
    tables: set[str] = set()
    for op in ops:
        if op.method == "create_table" and op.args_text:
            first = op.args_text[0]
            if len(first) >= 2 and first[0] in "'\"" and first[-1] == first[0]:
                tables.add(first[1:-1])
    return tables


_TABLE_ARG_INDEX = {
    "create_table": 0,
    "add_column": 0,
    "drop_column": 0,
    "alter_column": 0,
    "drop_table": 0,
    "rename_table": 0,
    "create_index": 1,
    "drop_index": 1,
    "create_foreign_key": 1,
}


def _unquote(text: str) -> str | None:
    if len(text) >= 2 and text[0] in "'\"" and text[-1] == text[0]:
        return text[1:-1]
    return None


def _table_of(op: OpCall) -> str | None:
    """Tabellenname nach der jeweiligen `op.*`-Signatur, nicht pauschal 'erstes Argument'.

    `create_index`/`drop_index` haben den Index-Namen an Position 0, den Tabellennamen an
    Position 1 (oder als `table_name`-Kwarg); `create_foreign_key` hat den Constraint-Namen
    an Position 0, die Quelltabelle an Position 1. Ein pauschaler Blick auf die ersten zwei
    Text-Argumente würde dort den falschen Namen als Tabelle behandeln.
    """
    kwarg = op.kwargs_text.get("table_name")
    if kwarg is not None:
        unquoted = _unquote(kwarg)
        if unquoted is not None:
            return unquoted
    idx = _TABLE_ARG_INDEX.get(op.method, 0)
    if idx < len(op.args_text):
        return _unquote(op.args_text[idx])
    return None


def parse_revision(path: Path) -> RevisionInfo:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GateError(f"{path}: konnte nicht gelesen werden: {exc}") from exc
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise GateError(f"{path}: kein gültiges Python — {exc}") from exc

    upgrade = _find_func(tree, "upgrade")
    downgrade = _find_func(tree, "downgrade")
    downgrade_empty, one_way_reason = _downgrade_status(downgrade)

    functions = _local_functions(tree)
    ops = _op_calls_in(upgrade, functions) if upgrade is not None else []
    created_tables = _created_tables(ops)

    # upgrade() enthält Code, aber der Scanner konnte keine einzige op.*-Operation daraus
    # lesen (Aufrufe außerhalb dessen, was _op_calls_in statisch folgt) — das ist etwas
    # anderes als eine bewusst leere Revision und darf nie als "pass" durchgehen.
    upgrade_nontrivial_without_ops = (
        upgrade is not None and not _is_trivial_body(upgrade) and not ops
    )

    multistep_note = None
    match = MULTISTEP_RE.search(source)
    if match:
        multistep_note = match.group(1).strip()

    return RevisionInfo(
        path=path,
        has_upgrade=upgrade is not None,
        has_downgrade=downgrade is not None,
        downgrade_empty=downgrade_empty,
        one_way_reason=one_way_reason,
        ops=ops,
        created_tables=created_tables,
        multistep_note=multistep_note,
        upgrade_nontrivial_without_ops=upgrade_nontrivial_without_ops,
    )


# --- Klassifikation je Operation -------------------------------------------------

def _bool_text(text: str | None) -> bool | None:
    if text == "True":
        return True
    if text == "False":
        return False
    return None


def _kwarg_bool(op: OpCall, name: str) -> bool | None:
    return _bool_text(op.kwargs_text.get(name))


def classify_op(op: OpCall, created_tables: set[str]) -> Classification:
    table = _table_of(op)
    is_new_table = table is not None and table in created_tables
    method = op.method

    if method == "create_table":
        return Classification(op, GREEN, "legt eine neue Tabelle an")

    if method == "add_column":
        target_status, column_kwargs = _add_column_target(op)
        if target_status == "unresolved":
            return Classification(
                op, UNKNOWN,
                "Spaltendefinition in add_column nicht statisch auflösbar (weder inline "
                "Column(...)/mapped_column(...) noch eine einfache lokale Variable) — "
                "nullable/Default nicht einsehbar, manuell prüfen",
            )
        nullable = _bool_text(column_kwargs.get("nullable"))
        has_default = "server_default" in column_kwargs
        if nullable is False and not has_default and not is_new_table:
            return Classification(
                op, RED,
                "NOT NULL ohne Default auf Bestandstabelle — vollständiger Table-Rewrite möglich",
            )
        if nullable is False and has_default and not is_new_table:
            return Classification(
                op, YELLOW,
                "NOT NULL mit Default auf Bestandstabelle — kurzer Lock zur Validierung (PG-Version-abhängig)",
                ["lock_timeout setzen", "außerhalb der Peak-Zeit ausführen"],
            )
        return Classification(op, GREEN, "additive Spalte (nullable oder auf neuer Tabelle)")

    if method == "create_index":
        concurrently = _kwarg_bool(op, "postgresql_concurrently")
        if is_new_table or concurrently is True:
            return Classification(op, GREEN, "Index ohne bestehende Zeilen bzw. CONCURRENTLY")
        return Classification(
            op, RED,
            "Index ohne CONCURRENTLY auf Bestandstabelle — sperrt Schreibzugriffe für die Bauzeit",
        )

    if method == "drop_index":
        return Classification(op, YELLOW, "kurzer exklusiver Lock beim Entfernen des Index",
                               ["lock_timeout setzen"])

    if method == "drop_column":
        return Classification(
            op, YELLOW,
            "kurzer exklusiver Lock, aber irreversibler Datenverlust — downgrade() kann die Daten nicht wiederherstellen",
            ["lock_timeout setzen", "Datenverlust im PR/Review explizit benennen"],
        )

    if method == "create_foreign_key":
        if is_new_table:
            return Classification(op, GREEN, "Fremdschlüssel auf neu angelegter Tabelle")
        return Classification(
            op, RED,
            "Fremdschlüssel auf Bestandstabelle validiert alle Zeilen unter Lock",
        )

    if method == "alter_column":
        nullable = _kwarg_bool(op, "nullable")
        type_text = op.kwargs_text.get("type_")
        if type_text is not None:
            return Classification(op, RED, "Typänderung — konservativ als Table-Rewrite behandelt")
        if nullable is True:
            return Classification(op, GREEN, "NULL wieder erlauben ist reine Metadatenänderung")
        if nullable is False and not is_new_table:
            return Classification(
                op, RED,
                "NOT NULL auf Bestandsspalte ohne validiertes CHECK-Constraint — Full-Table-Scan unter Lock",
            )
        if "new_column_name" in op.kwargs_text:
            return Classification(
                op, YELLOW, "Spalten-Rename bricht laufenden Code, der den alten Namen nutzt",
                ["rückwärtskompatiblen Rollout planen (View/Alias)"],
            )
        return Classification(op, GREEN, "additive alter_column auf neuer Tabelle")

    if method == "rename_table":
        return Classification(
            op, YELLOW, "Tabellen-Rename bricht laufenden Code, der den alten Namen nutzt",
            ["rückwärtskompatiblen Rollout planen (View/Alias)"],
        )

    if method == "bulk_insert":
        return Classification(op, YELLOW, "Schreiblast durch Masseneinfügung",
                               ["in Batches ausführen", "außerhalb der Peak-Zeit"])

    if method == "drop_table":
        return Classification(op, RED, "irreversibel — unabhängig von der aktuellen Zeilenzahl (R5)")

    if method == "execute":
        return Classification(
            op, UNKNOWN,
            "rohes SQL ist statisch nicht klassifizierbar — nicht bewertbar, manuell prüfen",
        )

    return Classification(
        op, UNKNOWN,
        f"unbekannte Operation 'op.{method}' — nicht bewertbar, manuell prüfen",
    )


# --- Revisions-Urteil --------------------------------------------------------------

def _multistep_structure_ok(note: str) -> bool:
    """Mindestens zwei Begriffe aus MULTISTEP_KEYWORDS — Struktur statt Masse (Fund 1)."""
    lowered = note.lower()
    hits = {kw for kw in MULTISTEP_KEYWORDS if kw in lowered}
    return len(hits) >= 2


@dataclass(frozen=True)
class RevisionVerdict:
    status: str  # pass / violation / review_required
    overall_class: str | None  # green/yellow/red, None wenn keine bekannten Ops
    classifications: list[Classification]
    unknown_ops: list[Classification]
    violations: list[str]
    notes: list = field(default_factory=list)


def classify_revision(revision: RevisionInfo) -> RevisionVerdict:
    violations: list[str] = []
    notes: list[str] = []

    if not revision.has_upgrade:
        violations.append("upgrade() fehlt")

    if revision.upgrade_nontrivial_without_ops:
        violations.append(
            "upgrade() enthält Code, aber keine op.*-Operation konnte erkannt werden "
            "(Aufruf außerhalb dessen, was der Scanner statisch verfolgt — z. B. über "
            "self./Modul-Attribute, eine Variable, eine importierte Funktion oder "
            "dynamisch aufgelöst) — nicht analysiert, keine automatische Freigabe möglich"
        )

    if revision.downgrade_empty and revision.one_way_reason is None:
        violations.append(
            "downgrade() fehlt oder ist leer, ohne begründete Einbahn-Migration "
            "(raise NotImplementedError('<Grund>') wäre die zulässige Form)"
        )

    classifications = [classify_op(op, revision.created_tables) for op in revision.ops]
    known = [c for c in classifications if c.verdict in _RANK]
    unknown_ops = [c for c in classifications if c.verdict == UNKNOWN]

    overall_class = None
    if known:
        overall_class = max((c.verdict for c in known), key=lambda v: _RANK[v])

    red_plan_needs_manual_review = False
    if overall_class == RED:
        if revision.multistep_note is None:
            violations.append(
                "rote Migration ohne Mehrschritt-Plan (Marker 'Mehrschritt-Plan: <Beschreibung>' fehlt) — abgelehnt"
            )
        elif not _multistep_structure_ok(revision.multistep_note):
            violations.append(
                "rote Migration mit Mehrschritt-Plan-Marker, aber ohne erkennbare Schrittstruktur "
                f"(erwartet mindestens zwei Begriffe aus {', '.join(MULTISTEP_KEYWORDS)}) — abgelehnt"
            )
        else:
            red_plan_needs_manual_review = True
            notes.append(
                "roter Plan mit erkennbarer Schrittstruktur vorhanden — der tatsächliche "
                "Inhalt ist mit statischer Analyse nicht vollständig prüfbar, manuelle "
                "Freigabe nötig (Klasse bleibt rot)"
            )

    if violations:
        status = "violation"
    elif unknown_ops:
        status = "review_required"
    elif red_plan_needs_manual_review:
        status = "review_required"
    else:
        status = "pass"

    return RevisionVerdict(
        status=status,
        overall_class=overall_class,
        classifications=classifications,
        unknown_ops=unknown_ops,
        violations=violations,
        notes=notes,
    )


# --- Härte-Erkennung (R6) -----------------------------------------------------------

def detect_hook_installed(repo: Path) -> bool:
    """Sucht den Hook-Pfad in .claude/settings*.json — mechanisch, nicht behauptet."""
    for relpath in SETTINGS_FILES:
        path = repo / relpath
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if HOOK_MARKER in text:
            return True
    return False


def hardness_line(hook_installed: bool) -> str:
    if hook_installed:
        return "Härte: G3 (Hook installiert) — blockiert."
    return "Härte: G2 (kein Hook installiert) — meldet Verstoß, blockiert nicht."


# --- Report / CLI -------------------------------------------------------------------

CACHE_PATH = Path(".skills") / "cache" / "migration-gate-report.json"


def _classification_dict(c: Classification) -> dict:
    return {
        "op": c.op.method,
        "line": c.op.lineno,
        "verdict": c.verdict,
        "reason": c.reason,
        "auflagen": c.auflagen,
    }


def build_report(repo: Path, revisions: list[tuple[Path, RevisionVerdict]]) -> dict:
    hook_installed = detect_hook_installed(repo)
    entries = []
    for path, verdict in revisions:
        entries.append({
            "path": str(path),
            "status": verdict.status,
            "overall_class": verdict.overall_class,
            "operations": [_classification_dict(c) for c in verdict.classifications],
            "unknown_operations": [_classification_dict(c) for c in verdict.unknown_ops],
            "violations": verdict.violations,
            "notes": verdict.notes,
        })
    return {
        "_meta": {
            "skill": "sql-schema-architect",
            "schema": SCHEMA_VERSION,
            "generated": "python skills/sql-schema-architect/scripts/migration_gate.py",
        },
        "hardness": hardness_line(hook_installed),
        "hook_installed": hook_installed,
        "revisions": entries,
    }


def _print_human(report: dict) -> None:
    print(report["hardness"])
    for entry in report["revisions"]:
        print(f"{entry['path']}: {entry['status']} (Gesamtklasse: {entry['overall_class'] or '—'})")
        for op in entry["operations"]:
            flag = "?" if op["verdict"] == UNKNOWN else op["verdict"][0].upper()
            print(f"  [{flag}] Zeile {op['line']} op.{op['op']}: {op['reason']}")
            for a in op["auflagen"]:
                print(f"      Auflage: {a}")
        for v in entry["violations"]:
            print(f"  VERSTOSS: {v}")
        for n in entry["notes"]:
            print(f"  HINWEIS: {n}")


def _collect_revision_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(target.glob("*.py"))
    raise GateError(f"{target}: weder Datei noch Verzeichnis")


def _worst_status(statuses: list[str]) -> int:
    """Exit-Code aus mehreren Revisions-Urteilen: violation schlägt review_required.

    `violation` (1) ist ein Kontraktverstoß — abgelehnt. `review_required` (2) heißt: kein
    Verstoß gefunden, aber mindestens eine Operation ist nicht bewertbar und darf deshalb
    nie stillschweigend als bestanden gelten. `pass` (0) heißt: alles geprüft und grün/gelb.
    """
    if any(s == "violation" for s in statuses):
        return 1
    if any(s == "review_required" for s in statuses):
        return 2
    return 0


def _run_hook_check(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--versions-dir", default="alembic/versions")
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    # Substring-Suche, kein Anker am Zeilenanfang — erkennt "alembic upgrade" auch hinter
    # "poetry run"/"python -m" (verifiziert). Bekannte Grenze, nicht behoben: Indirektion
    # über ein Makefile-Target ("make migrate") oder ein CI-Skript, dessen Bash-Aufruf den
    # literalen Text "alembic upgrade" nicht enthält, sieht der Hook nicht — er kennt nur
    # den Bash-Befehl, den der Agent aufruft, nicht was ein Target intern tut.
    if not re.search(r"alembic\s+upgrade", command, re.IGNORECASE):
        return 0

    versions_dir = args.repo / args.versions_dir
    if not versions_dir.is_dir():
        return 0

    files = sorted(versions_dir.glob("*.py"))
    if not files:
        return 0

    statuses = []
    for f in files:
        try:
            verdict = classify_revision(parse_revision(f))
        except GateError as exc:
            print(f"migration_gate: {exc}", file=sys.stderr)
            return 2
        statuses.append(verdict.status)
        if verdict.status != "pass":
            print(f"migration_gate blockiert: {f} ist {verdict.status} — {', '.join(verdict.violations) or 'unbewertbare Operation vorhanden'}", file=sys.stderr)

    if _worst_status(statuses) > 0:
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if argv and argv[0] == "--hook-check":
        return _run_hook_check(argv[1:])

    parser = argparse.ArgumentParser(description="Alembic-Revision(en) statisch auf Gefahrenklasse prüfen")
    parser.add_argument("target", type=Path, help="Revisionsdatei oder Verzeichnis mit Revisionen")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true", help="nur JSON auf stdout, kein menschenlesbares Format")
    args = parser.parse_args(argv)

    try:
        files = _collect_revision_files(args.target)
    except GateError as exc:
        print(f"migration_gate: {exc}", file=sys.stderr)
        return 1

    if not files:
        print(f"migration_gate: keine Revisionsdateien unter {args.target} gefunden", file=sys.stderr)
        return 1

    revisions: list[tuple[Path, RevisionVerdict]] = []
    for f in files:
        try:
            revisions.append((f, classify_revision(parse_revision(f))))
        except GateError as exc:
            print(f"migration_gate: {exc}", file=sys.stderr)
            return 1

    report = build_report(args.repo, revisions)

    if not args.json:
        _print_human(report)

    target = args.repo / CACHE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    worst = _worst_status([e["status"] for e in report["revisions"]])
    return worst


if __name__ == "__main__":
    sys.exit(main())
