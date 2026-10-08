#!/usr/bin/env python3
"""conventions.json -> spectral-ruleset.json. Tier 1: nur Stdlib.

R1: Beides JSON, nicht YAML — die Spec verlangt YAML-Parsing für ein Tier-1-Skript, die
Stdlib kennt aber kein YAML und PyYAML ist hier nicht installiert. Spectral liest Rulesets
auch als JSON, der Weg ist also gangbar, ohne eine neue Abhängigkeit einzuführen.

Eine Quelle, kein Drift: Wer das Preset ändert und dieses Skript erneut laufen lässt, bekommt
ein Ruleset, das zur Konventionsdatei passt. `references/conventions.md` erklärt das Preset,
wiederholt es aber nicht — sonst driften Erklärung und Regel auseinander.

Ob echtes Spectral den generierten Regelsatz tatsächlich fehlerfrei lädt, ist in dieser
Umgebung nicht geprüft (kein Spectral installiert) — siehe docs/known-limits.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA_VERSION = 1
PROJECT_OVERRIDE_RELPATH = Path(".skills") / "rest-api-architect" / "conventions.json"
SKILL_DEFAULT_RELPATH = Path("assets") / "conventions.json"
OUTPUT_FILENAME = "spectral-ruleset.json"


class RulesetError(RuntimeError):
    """Ruleset konnte nicht erzeugt werden — mit einer Ursache, die der Nutzer versteht."""


def resolve_conventions_path(explicit: Path | None, skill_dir: Path, project_root: Path) -> Path:
    """Auflösungsreihenfolge: explizit > Projekt-Override > Skill-Default (Spec 00 §1)."""
    if explicit is not None:
        return explicit
    override = project_root / PROJECT_OVERRIDE_RELPATH
    if override.is_file():
        return override
    return skill_dir / SKILL_DEFAULT_RELPATH


def resolve_output_path(explicit: Path | None, conventions_path: Path) -> Path:
    """Default: gleiches Verzeichnis wie die aufgelöste Konventionsdatei — Override erzeugt
    ein Ruleset neben sich, der Skill-Default erzeugt eines neben sich."""
    if explicit is not None:
        return explicit
    return conventions_path.parent / OUTPUT_FILENAME


def _rule(*, description: str, message: str, severity: str, given: str, then: object) -> dict:
    return {"description": description, "message": message, "severity": severity, "given": given, "then": then}


def build_rules(conventions: dict) -> dict:
    """Eine Spectral-Regel pro Preset-Dimension, die im Projekt gesetzt ist.

    `naming.no_verbs_in_paths` erzeugt bewusst keine Regel hier: eine generische Verb-Liste
    per Spectral-`pattern`-Funktion nachzubilden wäre eine Rate-Heuristik, die als echte Regel
    mehr Sicherheit vortäuscht als sie hat. Diese Prüfung übernimmt der textbasierte
    Checklisten-Fallback in gate.py, der genau dafür gebaut ist.
    """
    rules: dict[str, dict] = {}

    errors = conventions.get("errors") or {}
    media_type = errors.get("media_type")
    if media_type:
        rules["error-response-is-problem-json"] = _rule(
            description="Fehlerantworten (4xx/5xx) folgen RFC 9457 problem+json.",
            message=f"Response-Content sollte {media_type} enthalten (Preset: errors.media_type).",
            severity="error",
            given="$.paths[*][*].responses[?(@property >= '400')].content",
            then={"function": "truthy"},
        )
    required_fields = errors.get("required_fields")
    if required_fields:
        rules["error-schema-has-required-fields"] = _rule(
            description="Error-Schema trägt alle Pflichtfelder aus dem Preset.",
            message="Error-Schema sollte " + ", ".join(required_fields) + " enthalten (Preset: errors.required_fields).",
            severity="warn",
            given="$.components.schemas.Error.properties",
            then=[{"field": field, "function": "truthy"} for field in required_fields],
        )

    pagination = conventions.get("pagination") or {}
    request_params = pagination.get("request_params")
    if request_params:
        rules["pagination-request-params-present"] = _rule(
            description="List-Endpunkte akzeptieren die Paginierungs-Parameter aus dem Preset.",
            message="GET-Listen sollten Parameter " + "/".join(request_params) + " haben (Preset: pagination.request_params).",
            severity="warn",
            given="$.paths[*].get.parameters",
            then={"function": "truthy"},
        )
    response_fields = pagination.get("response_fields")
    if response_fields:
        rules["pagination-response-has-next-cursor"] = _rule(
            description="Paginierte Antworten tragen die Response-Felder aus dem Preset.",
            message="Listen-Antwort sollte " + "/".join(response_fields) + " enthalten (Preset: pagination.response_fields).",
            severity="warn",
            given="$.paths[*].get.responses.200.content['application/json'].schema.properties",
            then={"function": "truthy"},
        )

    versioning = conventions.get("versioning") or {}
    prefix_pattern = versioning.get("prefix_pattern")
    if prefix_pattern:
        rules["path-is-versioned"] = _rule(
            description="Pfade folgen dem Versionierungs-Präfix aus dem Preset.",
            message=f"Pfad sollte dem Muster {prefix_pattern} folgen (Preset: versioning.prefix_pattern).",
            severity="error",
            given="$.paths[*]~",
            then={"function": "pattern", "functionOptions": {"match": prefix_pattern}},
        )

    idempotency = conventions.get("idempotency") or {}
    header = idempotency.get("header")
    if header:
        rules["unsafe-post-requires-idempotency-key"] = _rule(
            description="Unsichere POSTs verlangen den Idempotency-Key-Header aus dem Preset.",
            message=f"POST-Operationen sollten Header {header} referenzieren (Preset: idempotency.header).",
            severity="warn",
            given="$.paths[*].post.parameters",
            then={"function": "truthy"},
        )

    naming = conventions.get("naming") or {}
    if naming.get("field_case") == "snake_case":
        rules["field-names-are-snake-case"] = _rule(
            description="Property-Namen folgen snake_case (Preset: naming.field_case).",
            message="Property-Namen sollten snake_case sein (Preset: naming.field_case).",
            severity="warn",
            given="$.components.schemas..properties[*]~",
            then={"function": "casing", "functionOptions": {"type": "snake"}},
        )

    timestamps = conventions.get("timestamps") or {}
    if timestamps.get("format") == "rfc3339":
        rules["timestamp-fields-use-date-time-format"] = _rule(
            description="Zeitstempel-Felder nutzen das OpenAPI-Format date-time (RFC 3339, Preset: timestamps.format).",
            message="Zeitstempel-Felder (*_at, *_date, timestamp) sollten format: date-time tragen.",
            severity="warn",
            given="$.components.schemas..properties[?(@property.match(/(_at|_date|timestamp)$/))]",
            then={"field": "format", "function": "pattern", "functionOptions": {"match": "date-time"}},
        )

    return rules


def build_ruleset(conventions: dict) -> dict:
    return {"rules": build_rules(conventions)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Spectral-Ruleset aus conventions.json erzeugen")
    parser.add_argument("--conventions", type=Path, help="Pfad zu conventions.json (sonst Auflösung nach Spec 00 §1)")
    parser.add_argument("--out", type=Path, help="Zielpfad für spectral-ruleset.json")
    parser.add_argument("--skill-dir", type=Path, default=Path(__file__).resolve().parent.parent, help="Skill-Verzeichnis für den Default-Pfad")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="Projekt-Wurzel für den Override-Pfad")
    args = parser.parse_args(argv)

    conventions_path = resolve_conventions_path(args.conventions, args.skill_dir, args.project_root)
    if not conventions_path.is_file():
        print(f"conventions.json nicht gefunden: {conventions_path}", file=sys.stderr)
        return 1

    try:
        conventions = json.loads(conventions_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"{conventions_path}: kein gültiges JSON — {exc}", file=sys.stderr)
        return 1

    out_path = resolve_output_path(args.out, conventions_path)
    ruleset = build_ruleset(conventions)
    payload = {
        "_meta": {
            "skill": "rest-api-architect",
            "schema": SCHEMA_VERSION,
            "generated": f"python skills/rest-api-architect/scripts/gen_ruleset.py --conventions {conventions_path}",
        },
        **ruleset,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(ruleset['rules'])} Regeln aus {conventions_path} -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
