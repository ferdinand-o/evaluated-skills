#!/usr/bin/env python3
"""SQLAlchemy-Models statisch lesen und ein Mermaid-ER-Diagramm erzeugen. Tier 1: nur Stdlib.

Die Models werden mit `ast` gelesen, nie importiert. Ein Import führte
Anwendungscode aus — Engine-Erzeugung, Verbindungsaufbau, Konfigurationsladen —
und eine Skill, die ein fremdes Schema nur erfassen soll, darf dabei keine
Verbindung zur Datenbank öffnen (R3).

Was statisch nicht erreichbar ist (dynamisch erzeugte `__tablename__`,
Mixins über mehrere Ebenen) wird sichtbar im Diagramm markiert, nie
stillschweigend weggelassen.
"""

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1
ARTIFACT_HEADER = (
    "<!-- skill: sql-schema-architect | schema: {schema} | generated: {cmd} -->"
)


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type_text: str
    nullable: bool
    primary_key: bool
    unique: bool
    has_index: bool
    fk_target: str
    fk_ondelete: str = ""


@dataclass(frozen=True)
class TableInfo:
    name: str
    class_name: str
    resolvable: bool
    columns: list = field(default_factory=list)
    relationships: list = field(default_factory=list)


@dataclass(frozen=True)
class ScanResult:
    tables: list
    warnings: list


def _unparse(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover
        return "<unparsable>"


def _call_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _bool_text(text) -> bool:
    return text == "True"


def _kwargs_of(call: ast.Call) -> dict:
    return {kw.arg: _unparse(kw.value) for kw in call.keywords if kw.arg is not None}


def _string_literal(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _find_nested_call(call: ast.Call, names: tuple) -> ast.Call | None:
    for arg in call.args:
        if isinstance(arg, ast.Call) and _call_name(arg) in names:
            return arg
    return None


def _fk_info(column_call: ast.Call) -> tuple:
    """(target, ondelete) aus einem verschachtelten ForeignKey(...)-Aufruf, oder ("", "")."""
    fk_call = _find_nested_call(column_call, ("ForeignKey",))
    if fk_call is None:
        return "", ""
    target = ""
    if fk_call.args:
        target = _string_literal(fk_call.args[0]) or _unparse(fk_call.args[0])
    ondelete = _kwargs_of(fk_call).get("ondelete", "")
    return target, ondelete.strip("'\"") if ondelete else ""


def _column_from_call(attr_name: str, call: ast.Call) -> ColumnInfo | None:
    call_name = _call_name(call)
    if call_name not in ("Column", "mapped_column"):
        return None
    kwargs = _kwargs_of(call)

    # Typ-Ausdruck: erstes positionales Argument, das kein Spaltenname (String)
    # und kein ForeignKey(...)/Index(...)-Aufruf ist.
    type_text = ""
    for a in call.args:
        if _string_literal(a) is not None:
            continue
        if isinstance(a, ast.Call) and _call_name(a) == "ForeignKey":
            continue
        type_text = _unparse(a)
        break

    fk_target, fk_ondelete = _fk_info(call)
    return ColumnInfo(
        name=attr_name,
        type_text=type_text or "?",
        nullable=_bool_text(kwargs.get("nullable", "True")) if "nullable" in kwargs else True,
        primary_key=_bool_text(kwargs.get("primary_key", "False")),
        unique=_bool_text(kwargs.get("unique", "False")),
        has_index=_bool_text(kwargs.get("index", "False")),
        fk_target=fk_target,
        fk_ondelete=fk_ondelete,
    )


def _table_args_has_index(class_body: list) -> bool:
    for stmt in class_body:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
            continue
        target = stmt.targets[0]
        if not (isinstance(target, ast.Name) and target.id == "__table_args__"):
            continue
        for sub in ast.walk(stmt.value):
            if isinstance(sub, ast.Call) and _call_name(sub) == "Index":
                return True
    return False


def _relationships_of(class_body: list) -> list:
    rels = []
    for stmt in class_body:
        value = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            value = stmt.value
            attr = stmt.targets[0].id
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            value = stmt.value
            attr = stmt.target.id
        else:
            continue
        if not (isinstance(value, ast.Call) and _call_name(value) == "relationship"):
            continue
        target = None
        if value.args:
            target = _string_literal(value.args[0]) or _unparse(value.args[0])
        rels.append({"attr": attr, "target": target or "?"})
    return rels


def _tablename_literal(class_body: list) -> tuple:
    """(tablename, resolvable). resolvable=False heißt: Attribut da, aber kein String-Literal."""
    for stmt in class_body:
        target = None
        value = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            target, value = stmt.targets[0].id, stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            target, value = stmt.target.id, stmt.value
        if target != "__tablename__":
            continue
        literal = _string_literal(value)
        if literal is not None:
            return literal, True
        return None, False
    return None, None


def _classes_in(tree: ast.Module) -> list:
    return [n for n in ast.iter_child_nodes(tree) if isinstance(n, ast.ClassDef)]


def scan_source(source: str, filename: str = "<unknown>") -> ScanResult:
    tree = ast.parse(source, filename=filename)
    tables: list = []
    warnings: list = []

    for cls in _classes_in(tree):
        tablename, resolvable = _tablename_literal(cls.body)
        columns = []
        for stmt in cls.body:
            attr = None
            value = None
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                attr, value = stmt.targets[0].id, stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                attr, value = stmt.target.id, stmt.value
            if attr is None or not isinstance(value, ast.Call):
                continue
            col = _column_from_call(attr, value)
            if col is not None:
                columns.append(col)

        has_table_args_index = _table_args_has_index(cls.body)
        relationships = _relationships_of(cls.body)

        if tablename is None and resolvable is False:
            # Attribut vorhanden, aber z.B. f-String oder Funktionsaufruf.
            warnings.append(
                f"Klasse {cls.name}: __tablename__ ist kein statisches Literal — "
                f"nicht auflösbar, im Diagramm als Klassenname markiert"
            )
            tables.append(TableInfo(
                name=f"unresolved_{cls.name}", class_name=cls.name, resolvable=False,
                columns=columns, relationships=relationships,
            ))
            continue

        if tablename is None and not columns:
            # Weder __tablename__ noch eigene Columns — kein Modell-Kandidat.
            continue

        if tablename is None and columns:
            warnings.append(
                f"Klasse {cls.name}: hat Columns, aber kein eigenes __tablename__ "
                f"(Mixin- oder Vererbungs-Kette?) — nicht auflösbar, im Diagramm als "
                f"Klassenname markiert statt weggelassen"
            )
            tables.append(TableInfo(
                name=f"unresolved_{cls.name}", class_name=cls.name, resolvable=False,
                columns=columns, relationships=relationships,
            ))
            continue

        if has_table_args_index and columns and not any(c.has_index for c in columns):
            # Index nur über __table_args__ sichtbar — an erster Spalte markieren, damit
            # er im Diagramm/Lint nicht verschwindet.
            columns[0] = ColumnInfo(
                name=columns[0].name, type_text=columns[0].type_text,
                nullable=columns[0].nullable, primary_key=columns[0].primary_key,
                unique=columns[0].unique, has_index=True, fk_target=columns[0].fk_target,
                fk_ondelete=columns[0].fk_ondelete,
            )

        tables.append(TableInfo(
            name=tablename, class_name=cls.name, resolvable=True,
            columns=columns, relationships=relationships,
        ))

    return ScanResult(tables=tables, warnings=warnings)


def scan_path(path: Path) -> ScanResult:
    files = [path] if path.is_file() else sorted(Path(path).rglob("*.py"))
    all_tables: list = []
    all_warnings: list = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError as exc:
            all_warnings.append(f"{f}: konnte nicht gelesen werden ({exc})")
            continue
        try:
            result = scan_source(text, filename=str(f))
        except SyntaxError as exc:
            all_warnings.append(f"{f}: kein gültiges Python — {exc}")
            continue
        all_tables.extend(result.tables)
        all_warnings.extend(result.warnings)
    return ScanResult(tables=all_tables, warnings=all_warnings)


def _column_line(col: ColumnInfo) -> str:
    flags = []
    if col.primary_key:
        flags.append("PK")
    if col.fk_target:
        flags.append("FK")
    if col.unique:
        flags.append("UK")
    suffix = f" {','.join(flags)}" if flags else ""
    type_text = col.type_text.replace('"', "'")
    return f'        {type_text} {col.name}{suffix}'


def render_mermaid(result: ScanResult) -> str:
    lines = ["erDiagram"]
    for table in result.tables:
        lines.append(f"    {table.name} {{")
        for col in table.columns:
            lines.append(_column_line(col))
        if not table.columns:
            lines.append("        %% keine Columns statisch gefunden")
        lines.append("    }")

    known_names = {t.name for t in result.tables}
    for table in result.tables:
        for col in table.columns:
            if not col.fk_target:
                continue
            target_table = col.fk_target.split(".")[0]
            if target_table not in known_names:
                continue
            cardinality = '||--||' if col.unique else '||--o{'
            lines.append(f'    {target_table} {cardinality} {table.name} : "{col.name}"')

    relationship_lines = [
        f"    %% relationship: {table.name}.{rel['attr']} -> {rel['target']}"
        for table in result.tables
        for rel in table.relationships
    ]
    if relationship_lines:
        lines.append("")
        lines.append("    %% relationship()-Aufrufe (Kardinalität nicht garantiert, nur FK-Kanten oben sind verlässlich):")
        lines.extend(relationship_lines)

    if result.warnings:
        lines.append("")
        lines.append("    %% Warnungen — statisch nicht vollständig auflösbar:")
        for w in result.warnings:
            lines.append(f"    %% {w}")

    return "\n".join(lines) + "\n"


def write_erd(repo: Path, models_path: Path, out_path: Path, cmd: str) -> Path:
    result = scan_path(models_path)
    body = render_mermaid(result)
    header = ARTIFACT_HEADER.format(schema=SCHEMA_VERSION, cmd=cmd)
    target = repo / out_path
    target.parent.mkdir(parents=True, exist_ok=True)
    content = f"{header}\n# ER-Diagramm (generiert)\n\n```mermaid\n{body}```\n"
    target.write_text(content, encoding="utf-8")
    return target


DEFAULT_OUT = Path("docs/schema/erd.md")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SQLAlchemy-Models statisch lesen, Mermaid-ER-Diagramm erzeugen")
    parser.add_argument("models", type=Path, help="Model-Datei oder -Verzeichnis")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    if not args.models.exists():
        print(f"gen_erd: {args.models} existiert nicht", file=sys.stderr)
        return 1

    cmd = f"python skills/sql-schema-architect/scripts/gen_erd.py {args.models}"
    target = write_erd(args.repo, args.models, args.out, cmd)
    result = scan_path(args.models)
    print(f"{len(result.tables)} Tabellen gefunden -> {target}")
    for w in result.warnings:
        print(f"Warnung: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
