"""Eval-Definitionen laden und validieren (Spec 00 §2). Tier 1: nur Stdlib."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

JUDGE_TYPE = "judge"
MECHANICAL_TYPES = frozenset({
    "file_exists",
    "file_absent",
    "file_matches",
    "file_unchanged",
    "file_max_lines",
    "artifact_header",
    "git_head_unchanged",
    "output_matches",
})
ASSERTION_TYPES = MECHANICAL_TYPES | {JUDGE_TYPE}
EVAL_CLASSES = frozenset({"contract", "behavior"})

_NEEDS_PATH = MECHANICAL_TYPES - {"git_head_unchanged", "output_matches"}
_NEEDS_PATTERN = frozenset({"file_matches", "output_matches"})


class EvalSchemaError(ValueError):
    """Eine evals.json verletzt das Schema aus Spec 00 §2."""


@dataclass(frozen=True)
class Assertion:
    type: str
    path: str | None = None
    pattern: str | None = None
    claim: str | None = None
    max_lines: int | None = None


@dataclass(frozen=True)
class Eval:
    id: str
    eval_class: str
    prompt: str
    must: tuple[Assertion, ...]
    must_not: tuple[Assertion, ...] = ()
    fixture: str | None = None
    notes: str = ""


def _reject_unsafe_path(path: str, where: str) -> None:
    """Ein Assertion-`path` bleibt innerhalb des Workspace — sonst ersetzt ein
    absoluter Pfad die Workspace-Wurzel vollständig (`root / "/etc/passwd"` liefert
    `/etc/passwd`) oder eine `..`-Komponente läuft aus ihr heraus. Ein kopierter
    oder vertippter Pfad in einer evals.json würde sonst gegen das echte Repo statt
    gegen den Workspace prüfen und trotzdem PASS melden.
    """
    if Path(path).is_absolute():
        raise EvalSchemaError(f"{where}: 'path' muss relativ zum Workspace sein, war absolut: {path!r}")
    if ".." in PurePosixPath(path).parts:
        raise EvalSchemaError(f"{where}: 'path' darf nicht aus dem Workspace herausführen (enthält '..'): {path!r}")


def _parse_assertion(raw: object, where: str) -> Assertion:
    if not isinstance(raw, dict):
        raise EvalSchemaError(f"{where}: Assertion muss ein Objekt sein, war {type(raw).__name__}")
    kind = raw.get("type")
    if kind not in ASSERTION_TYPES:
        raise EvalSchemaError(f"{where}: unbekannter Assertion-Typ {kind!r}")

    path = raw.get("path")
    if kind in _NEEDS_PATH:
        if not path:
            raise EvalSchemaError(f"{where}: Typ {kind!r} braucht ein 'path'")
        if not isinstance(path, str):
            # Sonst wirft `root / path` erst beim Grading ein TypeError — nach dem
            # teuren Agentenlauf, aufgefangen nur vom generischen Sicherheitsnetz.
            raise EvalSchemaError(f"{where}: 'path' muss eine Zeichenkette sein, war {type(path).__name__}")
        _reject_unsafe_path(path, where)

    pattern = raw.get("pattern")
    if kind in _NEEDS_PATTERN:
        if not pattern:
            raise EvalSchemaError(f"{where}: Typ {kind!r} braucht ein 'pattern'")
        if not isinstance(pattern, str):
            # re.compile() auf einem Nicht-String wirft TypeError, nicht re.error —
            # das würde die folgende except-Klausel nicht auffangen.
            raise EvalSchemaError(f"{where}: 'pattern' muss eine Zeichenkette sein, war {type(pattern).__name__}")
        try:
            re.compile(pattern)
        except re.error as exc:
            # Sonst fliegt die Regex erst beim Grading — nach dem teuren Agentenlauf.
            raise EvalSchemaError(f"{where}: 'pattern' ist keine gültige Regex — {exc}") from exc

    if kind == "file_max_lines" and not isinstance(raw.get("max_lines"), int):
        raise EvalSchemaError(f"{where}: Typ 'file_max_lines' braucht ein ganzzahliges 'max_lines'")

    claim = raw.get("claim")
    if kind == JUDGE_TYPE:
        if not claim:
            raise EvalSchemaError(f"{where}: Typ 'judge' braucht ein 'claim'")
        if not isinstance(claim, str):
            raise EvalSchemaError(f"{where}: 'claim' muss eine Zeichenkette sein, war {type(claim).__name__}")

    return Assertion(
        type=kind,
        path=path,
        pattern=pattern,
        claim=claim,
        max_lines=raw.get("max_lines"),
    )


def _parse_eval(raw: object, index: int) -> Eval:
    where = f"eval[{index}]"
    if not isinstance(raw, dict):
        raise EvalSchemaError(f"{where}: Eval muss ein Objekt sein")
    eval_id = raw.get("id")
    if not eval_id or not isinstance(eval_id, str):
        raise EvalSchemaError(f"{where}: 'id' fehlt oder ist leer")
    where = f"eval[{eval_id}]"
    eval_class = raw.get("class")
    if eval_class not in EVAL_CLASSES:
        raise EvalSchemaError(f"{where}: 'class' muss eine von {sorted(EVAL_CLASSES)} sein, war {eval_class!r}")
    prompt = raw.get("prompt")
    if not prompt or not isinstance(prompt, str):
        raise EvalSchemaError(f"{where}: 'prompt' fehlt oder ist leer")

    must = tuple(_parse_assertion(a, f"{where}.must") for a in raw.get("must", []))
    if not must:
        raise EvalSchemaError(f"{where}: 'must' darf nicht leer sein — ein Eval ohne Muss-Assertion behauptet nichts")
    must_not = tuple(_parse_assertion(a, f"{where}.must_not") for a in raw.get("must_not", []))

    if eval_class == "contract":
        for assertion in (*must, *must_not):
            if assertion.type == JUDGE_TYPE:
                raise EvalSchemaError(
                    f"{where}: contract-Evals dürfen keine judge-Assertion enthalten (Spec 00 §2) — "
                    f"nimm class 'behavior', wenn du ein Urteil brauchst"
                )

    return Eval(
        id=eval_id,
        eval_class=eval_class,
        prompt=prompt,
        must=must,
        must_not=must_not,
        fixture=raw.get("fixture"),
        notes=raw.get("notes", ""),
    )


def load_evals(path: Path) -> tuple[Eval, ...]:
    """Lade und validiere eine evals.json. Wirft EvalSchemaError bei jedem Verstoß."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvalSchemaError(f"{path}: kein gültiges JSON — {exc}") from exc

    raw_evals = payload.get("evals") if isinstance(payload, dict) else None
    if not isinstance(raw_evals, list):
        raise EvalSchemaError(f"{path}: erwartet ein Objekt mit der Liste 'evals'")

    evals = tuple(_parse_eval(raw, i) for i, raw in enumerate(raw_evals))

    seen: set[str] = set()
    for ev in evals:
        if ev.id in seen:
            raise EvalSchemaError(f"{path}: Eval-ID {ev.id!r} ist doppelt vergeben")
        seen.add(ev.id)
    return evals
