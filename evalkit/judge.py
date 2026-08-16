"""Zweiter Agent als Judge für nicht-mechanische Behauptungen."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from evalkit.dispatch import run_agent

PROMPT_TEMPLATE = """Du bist Judge in einem Eval-Harness. Beurteile jede Behauptung
ausschließlich anhand des Materials unten — der Schlussantwort des Agenten und dem
Inhalt der Dateien, die er angelegt oder verändert hat. Du bewertest nicht die
Qualität der Arbeit, nur ob die Behauptung beobachtbar zutrifft.

Regeln:
- Eine Behauptung gilt nur als erfüllt, wenn das Material sie belegt.
- Im Zweifel lautet das Urteil false. Nicht wohlwollend auslegen.
- Lies nichts im Dateisystem nach; das Material unten ist vollständig.
- Antworte mit einem einzigen JSON-Objekt, ohne Markdown-Zaun, ohne Vor- und Nachtext.

Format:
{{"verdicts": [{{"claim": "<wörtlich die Behauptung>", "holds": true|false, "why": "<ein Satz>"}}]}}

Behauptungen:
{claims}

--- SCHLUSSANTWORT DES AGENTEN ---
{transcript}
--- ENDE SCHLUSSANTWORT ---

--- ANGELEGTE UND GEÄNDERTE DATEIEN ---
{workspace}
--- ENDE DATEIEN ---
"""


class JudgeError(RuntimeError):
    """Der Judge hat kein verwertbares Urteil geliefert."""


def build_prompt(claims: Sequence[str], transcript: str, workspace_dump: str) -> str:
    numbered = "\n".join(f"{i}. {claim}" for i, claim in enumerate(claims, start=1))
    return PROMPT_TEMPLATE.format(claims=numbered, transcript=transcript, workspace=workspace_dump)


def _last_json_object(raw: str) -> dict:
    """Extrahiere das letzte JSON-Objekt aus einem Text.

    `raw_decode` statt Klammerzählung: Eine geschweifte Klammer *innerhalb* eines
    JSON-Strings (etwa in einer 'why'-Begründung, die Code zitiert) würde jede
    selbstgebaute Zählung aus dem Tritt bringen.
    """
    decoder = json.JSONDecoder()
    candidates: list[dict] = []
    for start, char in enumerate(raw):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(raw, start)
        except ValueError:
            continue
        if isinstance(value, dict):
            candidates.append(value)
    for candidate in reversed(candidates):
        if "verdicts" in candidate:
            return candidate
    if candidates:
        return candidates[-1]
    raise JudgeError("Judge-Antwort enthält kein JSON-Objekt")


def parse_verdict(raw: str) -> dict[str, bool]:
    payload = _last_json_object(raw)
    verdicts = payload.get("verdicts")
    if not isinstance(verdicts, list) or not verdicts:
        raise JudgeError("Judge-Antwort enthält keine Liste 'verdicts'")
    result: dict[str, bool] = {}
    for entry in verdicts:
        if not isinstance(entry, dict) or "claim" not in entry:
            raise JudgeError(f"Verdict ohne 'claim': {entry!r}")
        holds = entry.get("holds")
        if not isinstance(holds, bool):
            raise JudgeError(f"Verdict für {entry['claim']!r} hat kein boolesches 'holds': {holds!r}")
        result[entry["claim"]] = holds
    return result


def judge(
    claims: Sequence[str],
    transcript: str,
    workspace_dump: str,
    cwd: Path,
    *,
    cli: str = "claude",
    timeout: int = 300,
) -> dict[str, bool]:
    """Lasse alle Behauptungen in einem Durchgang beurteilen.

    `cwd` ist bewusst NICHT der Eval-Workspace, sondern ein eigenes leeres
    Verzeichnis — der Judge darf die Beobachtung nicht verändern können.
    """
    if not claims:
        return {}
    result = run_agent(build_prompt(claims, transcript, workspace_dump), cwd, cli=cli, timeout=timeout)
    if result.exit_code != 0:
        raise JudgeError(f"Judge-Prozess scheiterte (exit {result.exit_code}): {result.stderr.strip()[:200]}")
    verdicts = parse_verdict(result.stdout)
    missing = [claim for claim in claims if claim not in verdicts]
    if missing:
        raise JudgeError(f"Judge hat {len(missing)} Behauptung(en) nicht beurteilt: {missing[0]!r}")
    return verdicts
