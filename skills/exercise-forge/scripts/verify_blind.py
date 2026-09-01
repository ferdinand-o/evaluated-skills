#!/usr/bin/env python3
"""Blind-Gate für exercise-forge. Tier 1: nur Stdlib.

Ruft die `claude`-CLI als Subprozess für einen unabhängigen Blind-Löser
(G2 — das Urteil ist maschinell, der Aufruf bleibt freiwillig). Duplziert
absichtlich das Subprozess-Muster aus `evalkit.dispatch.run_agent` statt es zu
importieren: Skill-Skripte müssen portabel bleiben, unabhängig vom
Eval-Harness dieses Repos (siehe Spec 00 §3, Rulings A1/A3).

Für Aufgabentyp `coding` ruft `verify_coding_task` zusätzlich `run_coding.py`
(Tier 2, pytest) als eigenen Subprozess auf und reicht dessen Urteil durch.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_TIMEOUT = 300
LETTERS = "ABCDEFGH"
# Dupliziert aus export.py (Rulings A3, Skripte bleiben eigenständig) — die
# einzigen 'method'-Werte, die ein echter Blind-Lauf schreibt.
REAL_VERIFICATION_METHODS = {"blind_solve_mc", "blind_solve_open", "blind_solve_coding", "blind_check_flashcard"}


class VerifyError(RuntimeError):
    """Das Blind-Gate konnte kein Urteil bilden — Ursache benannt (Rulings A4)."""


@dataclass(frozen=True)
class Transcript:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


def run_agent(
    prompt: str,
    cwd: Path,
    *,
    cli: str = "claude",
    timeout: int = DEFAULT_TIMEOUT,
    permission_mode: str = "bypassPermissions",
) -> Transcript:
    """Starte `claude -p <prompt>` in `cwd` und liefere sein Transcript.

    Ein fehlendes CLI, ein Timeout oder ein fehlendes `cwd` werden gemeldet,
    nie als Exception hochgereicht — der Aufrufer entscheidet, ob das ein
    'unverified'-Urteil ist (Rulings A4: kein stilles Scheitern).
    """
    cwd = Path(cwd)
    if not cwd.is_dir():
        return Transcript(stdout="", stderr=f"Arbeitsverzeichnis nicht gefunden: {cwd}", exit_code=127, timed_out=False)

    argv = [
        cli, "-p",
        "--permission-mode", permission_mode,
        "--setting-sources", "project",
        "--strict-mcp-config",
        prompt,
    ]
    try:
        done = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return Transcript(stdout="", stderr=f"Timeout nach {timeout}s", exit_code=124, timed_out=True)
    except FileNotFoundError:
        return Transcript(stdout="", stderr=f"CLI nicht gefunden: {cli}", exit_code=127, timed_out=False)
    except OSError as exc:
        return Transcript(stdout="", stderr=f"CLI nicht startbar: {exc}", exit_code=126, timed_out=False)

    return Transcript(stdout=done.stdout, stderr=done.stderr, exit_code=done.returncode, timed_out=False)


# --- verification-Objekt -----------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_verification(method: str, detail: str, protocol: dict | None = None) -> dict:
    """Kein `status`-Feld mehr (Fix-Runde 5): `protocol` trägt die Rohdaten,
    aus denen sich ein Status ableiten lässt (z. B. `chosen_index` bei MC) —
    ein zusätzliches, frei editierbares `status`-Feld wäre redundant dazu und
    genau die Fehlerquelle, die Fix-Runde 3/4 in der Praxis traf (eine Session
    schrieb `status: "verified"` neben einem Protokoll, das etwas anderes
    zeigte — die Aufgaben-JSON, ein Artefakt, das auch andere Werkzeuge lesen,
    behielt den Widerspruch, selbst nachdem `export.py` ihn beim Rendern schon
    ignorierte). Wer einen Status braucht, ruft `derive_status_from_protocol()`
    auf — hier für `main()`s eigene Entscheidungen, in `export.py` fürs
    Rendern, in `learning-coach` (Zyklus 14) nach derselben Regel (siehe
    `references/task-schemas.md`)."""
    return {"method": method, "detail": detail, "checked_at": _now_iso(), "protocol": protocol}


def _verified(method: str, detail: str, protocol: dict | None = None) -> dict:
    return _make_verification(method, detail, protocol)


def _suspicious(method: str, detail: str, protocol: dict | None = None) -> dict:
    return _make_verification(method, detail, protocol)


def _unverified(method: str, detail: str, protocol: dict | None = None) -> dict:
    return _make_verification(method, detail, protocol)


def derive_status_from_protocol(exercise: dict) -> tuple[str, str]:
    """(status, detail) aus `verification.protocol` — dupliziert aus
    `export.derive_status_from_protocol()` (Rulings A3, Skripte bleiben
    eigenständig). Gleiche Regel, gleiche Rückgabewerte; siehe dort für die
    ausführlicheren Kommentare pro Typ und `references/task-schemas.md` für
    die Regel unabhängig vom Code."""
    verification = exercise.get("verification") or {}
    method = verification.get("method")
    checked_at = verification.get("checked_at")
    protocol = verification.get("protocol")
    ex_type = exercise.get("type")

    if method == "not_run" or method is None:
        return "unverified", verification.get("detail") or "Blind-Gate noch nicht gelaufen"

    if method not in REAL_VERIFICATION_METHODS:
        return "unverified", f"'{method}' ist keine der vom Blind-Gate erzeugten Methoden — kein Prüfnachweis"

    if not checked_at or not isinstance(protocol, dict):
        return "unverified", (
            f"method {method!r} sieht nach einem echten Lauf aus, aber checked_at "
            "und/oder protocol fehlen oder sind unvollständig — kein vollständiger Prüfnachweis"
        )

    if ex_type == "multiple_choice" and method == "blind_solve_mc":
        options = exercise.get("options")
        chosen_index = protocol.get("chosen_index")
        if not isinstance(options, list) or not isinstance(chosen_index, int) or not (0 <= chosen_index < len(options)):
            return "unverified", "Protokoll verweist auf keine gültige Option der Aufgabe"
        chosen = options[chosen_index]
        letter = LETTERS[chosen_index] if chosen_index < len(LETTERS) else str(chosen_index)
        if chosen.get("correct"):
            return "verified", f"Blind-Löser wählte laut Protokoll die als korrekt markierte Option {letter}."
        return "suspicious", f"Blind-Löser wählte laut Protokoll Option {letter} — nicht als korrekt markiert."

    if ex_type == "open_question" and method == "blind_solve_open":
        criteria = exercise.get("criteria") or []
        met = protocol.get("criteria_met")
        plausible = protocol.get("answer_is_plausible")
        if not criteria or not isinstance(met, list) or len(met) != len(criteria) or not isinstance(plausible, bool):
            return "unverified", "Protokoll passt nicht zur Kriterienliste der Aufgabe"
        if not plausible:
            return "unverified", "Blind-Antwort war laut Protokoll nicht plausibel genug für ein Urteil"
        if all(met):
            return "verified", "Blind-Antwort erfüllt laut Protokoll alle Kriterien."
        unmet = [i + 1 for i, ok in enumerate(met) if not ok]
        return "suspicious", f"Blind-Antwort erfüllt laut Protokoll Kriterium/-ien {unmet} nicht."

    if ex_type == "flashcard" and method == "blind_check_flashcard":
        matches = protocol.get("matches")
        if not isinstance(matches, bool):
            return "unverified", "Protokoll enthält kein 'matches'-Feld"
        if matches:
            return "verified", "Blind-Antwort trifft laut Protokoll die Rückseite."
        return "suspicious", "Blind-Antwort weicht laut Protokoll von der Rückseite ab."

    if ex_type == "coding" and method == "blind_solve_coding":
        model_passed = protocol.get("model_passed")
        blind_passed = protocol.get("blind_passed")
        if not isinstance(model_passed, bool):
            return "unverified", "Protokoll enthält kein Testergebnis für die Musterlösung"
        if not model_passed:
            return "unverified", "Musterlösung besteht laut Protokoll die eigenen Tests nicht"
        if not isinstance(blind_passed, bool):
            return "unverified", "Protokoll enthält kein Testergebnis für die Blind-Lösung"
        if blind_passed:
            return "verified", "Musterlösung und Blind-Lösung bestehen laut Protokoll beide die Tests."
        return "suspicious", "Blind-Lösung besteht laut Protokoll nicht, obwohl die Musterlösung besteht."

    return "unverified", f"Methode {method!r} passt nicht zum Aufgabentyp {ex_type!r}"


def _find_json_object(text: str, required_key: str) -> dict | None:
    """Letztes JSON-Objekt in `text`, das `required_key` trägt.

    `raw_decode` statt Klammerzählung, wie `evalkit.judge._last_json_object` —
    eine geschweifte Klammer innerhalb eines Strings (z. B. einer
    Begründung, die Code zitiert) würde eine eigene Zählung aus dem Tritt
    bringen.
    """
    decoder = json.JSONDecoder()
    candidates: list[dict] = []
    for start, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text, start)
        except ValueError:
            continue
        if isinstance(value, dict):
            candidates.append(value)
    for candidate in reversed(candidates):
        if required_key in candidate:
            return candidate
    return None


# --- Multiple Choice ----------------------------------------------------------

def build_mc_prompt(stem: str, options: list[str]) -> str:
    lines = [f"{LETTERS[i]}) {opt}" for i, opt in enumerate(options)]
    return (
        "Du löst eine Multiple-Choice-Aufgabe blind — ohne die Musterlösung zu kennen.\n"
        "Wähle die beste Antwort und begründe kurz, warum.\n\n"
        f"Frage: {stem}\n\n" + "\n".join(lines) +
        "\n\nAntworte auf Deutsch. Die letzte Zeile deiner Antwort muss exakt lauten:\n"
        "ANTWORT: <Buchstabe>"
    )


MC_ANSWER_RE = re.compile(r"ANTWORT:\s*([A-H])", re.IGNORECASE)


def parse_mc_letter(output: str) -> str | None:
    matches = MC_ANSWER_RE.findall(output)
    return matches[-1].upper() if matches else None


def verify_mc(exercise: dict, cwd: Path, *, cli: str = "claude", timeout: int = DEFAULT_TIMEOUT) -> dict:
    options = exercise.get("options") or []
    texts = [o["text"] for o in options]
    result = run_agent(build_mc_prompt(exercise["stem"], texts), cwd, cli=cli, timeout=timeout)
    if result.exit_code != 0:
        return _unverified("blind_solve_mc", f"Blind-Löser nicht erreichbar: {result.stderr.strip()[:200]}")

    letter = parse_mc_letter(result.stdout)
    if letter is None:
        return _unverified("blind_solve_mc", "Blind-Antwort nicht parsebar (kein 'ANTWORT: <Buchstabe>' gefunden)")

    index = LETTERS.index(letter) if letter in LETTERS[:len(options)] else -1
    if index < 0:
        return _unverified("blind_solve_mc", f"Blind-Löser nannte Option {letter}, es gibt nur {len(options)} Optionen")

    chosen = options[index]
    protocol = {"chosen_index": index}
    if chosen.get("correct"):
        return _verified("blind_solve_mc", f"Blind-Löser wählte korrekt (Option {letter}).", protocol)
    return _suspicious(
        "blind_solve_mc",
        f"Möglicherweise kaputter oder mehrdeutiger Distraktor: Blind-Löser wählte "
        f"{letter} ('{chosen.get('text')}') statt der markierten korrekten Option. "
        f"Begründung: {result.stdout.strip()[:300]}",
        protocol,
    )


# --- Offene Frage ---------------------------------------------------------

def build_open_prompt(stem: str) -> str:
    return (
        "Du beantwortest eine offene Lernfrage blind — ohne Musterlösung oder "
        "Bewertungskriterien zu kennen. Antworte fachlich, in eigenen Worten, auf Deutsch.\n\n"
        f"Frage: {stem}"
    )


def build_grading_prompt(stem: str, blind_answer: str, criteria: list[str]) -> str:
    numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(criteria, start=1))
    return (
        "Du bewertest eine Antwort auf eine Lernfrage gegen feste Kriterien. Urteile "
        "nur anhand des Materials unten, wohlwollend gegenüber der Antwort, aber "
        "ehrlich gegenüber den Kriterien.\n\n"
        f"Frage: {stem}\n\nAntwort:\n{blind_answer}\n\nKriterien:\n{numbered}\n\n"
        "Antworte mit einem einzigen JSON-Objekt, ohne Markdown-Zaun, ohne Vor- und "
        "Nachtext:\n"
        '{"answer_is_plausible": true|false, "criteria_met": [true|false, ...], "why": "ein Satz"}'
    )


def parse_grading_json(output: str) -> dict | None:
    return _find_json_object(output, "criteria_met")


def verify_open(exercise: dict, cwd: Path, *, cli: str = "claude", timeout: int = DEFAULT_TIMEOUT) -> dict:
    stem = exercise["stem"]
    criteria = exercise.get("criteria") or []

    if not criteria:
        # all([]) ist True — ohne diese Vorabprüfung würde eine Aufgabe ohne
        # ein einziges Kriterium den Abgleich mit einer leeren Liste bestehen
        # und als 'verified' gelten, obwohl nichts geprüft wurde (D2).
        return _unverified("blind_solve_open", "Kriterienliste ist leer - kein Abgleich möglich, Aufgabe unvollständig")

    blind = run_agent(build_open_prompt(stem), cwd, cli=cli, timeout=timeout)
    if blind.exit_code != 0:
        return _unverified("blind_solve_open", f"Blind-Löser nicht erreichbar: {blind.stderr.strip()[:200]}")

    grading = run_agent(build_grading_prompt(stem, blind.stdout.strip(), criteria), cwd, cli=cli, timeout=timeout)
    if grading.exit_code != 0:
        return _unverified("blind_solve_open", f"Bewertung nicht erreichbar: {grading.stderr.strip()[:200]}")

    verdict = parse_grading_json(grading.stdout)
    if verdict is None:
        return _unverified("blind_solve_open", "Bewertungs-Antwort nicht parsebar")

    met = verdict.get("criteria_met")
    plausible = verdict.get("answer_is_plausible")
    if not isinstance(met, list) or len(met) != len(criteria) or not isinstance(plausible, bool):
        return _unverified("blind_solve_open", "Bewertungs-JSON hat unerwartete Form")

    protocol = {"criteria_met": met, "answer_is_plausible": plausible}

    if not plausible:
        return _unverified(
            "blind_solve_open",
            f"Blind-Antwort nicht plausibel genug für ein Urteil: {verdict.get('why', '')}",
            protocol,
        )

    if all(met):
        return _verified("blind_solve_open", "Blind-Antwort erfüllt alle Kriterien.", protocol)

    unmet = [i + 1 for i, ok in enumerate(met) if not ok]
    return _suspicious(
        "blind_solve_open",
        f"Plausible Blind-Antwort erfüllt Kriterium/-ien {unmet} nicht — vermutlich zu eng. {verdict.get('why', '')}",
        protocol,
    )


# --- Flashcard --------------------------------------------------------------

def build_flashcard_prompt(front: str) -> str:
    return (
        "Du beantwortest eine Lernkarte blind — du siehst nur die Vorderseite.\n\n"
        f"Vorderseite: {front}\n\nAntworte kurz und auf Deutsch."
    )


def build_flashcard_grading_prompt(front: str, back: str, blind_answer: str) -> str:
    return (
        "Prüfe, ob eine Blind-Antwort inhaltlich zur Rückseite einer Lernkarte passt. "
        "Urteile nur anhand des Materials unten.\n\n"
        f"Vorderseite: {front}\nRückseite (Soll): {back}\nBlind-Antwort (Ist): {blind_answer}\n\n"
        "Antworte mit einem einzigen JSON-Objekt, ohne Markdown-Zaun, ohne Vor- und "
        "Nachtext:\n"
        '{"matches": true|false, "why": "ein Satz"}'
    )


def parse_match_json(output: str) -> dict | None:
    return _find_json_object(output, "matches")


def verify_flashcard(exercise: dict, cwd: Path, *, cli: str = "claude", timeout: int = DEFAULT_TIMEOUT) -> dict:
    front, back = exercise["front"], exercise["back"]

    blind = run_agent(build_flashcard_prompt(front), cwd, cli=cli, timeout=timeout)
    if blind.exit_code != 0:
        return _unverified("blind_check_flashcard", f"Blind-Löser nicht erreichbar: {blind.stderr.strip()[:200]}")

    grading = run_agent(build_flashcard_grading_prompt(front, back, blind.stdout.strip()), cwd, cli=cli, timeout=timeout)
    if grading.exit_code != 0:
        return _unverified("blind_check_flashcard", f"Bewertung nicht erreichbar: {grading.stderr.strip()[:200]}")

    verdict = parse_match_json(grading.stdout)
    if verdict is None or not isinstance(verdict.get("matches"), bool):
        return _unverified("blind_check_flashcard", "Bewertungs-Antwort nicht parsebar")

    protocol = {"matches": verdict["matches"]}
    if verdict["matches"]:
        return _verified("blind_check_flashcard", "Blind-Antwort trifft die Rückseite.", protocol)
    return _suspicious(
        "blind_check_flashcard",
        f"Blind-Antwort weicht von der Rückseite ab — Vorderseite vermutlich mehrdeutig. {verdict.get('why', '')}",
        protocol,
    )


# --- Coding -------------------------------------------------------------------

def build_coding_prompt(stem: str, test_suite: str) -> str:
    return (
        "Du löst eine Coding-Aufgabe blind — du kennst die Musterlösung nicht. Du "
        "siehst die Aufgabenstellung und die Testsuite, gegen die dein Code laufen wird.\n\n"
        f"Aufgabe: {stem}\n\nTestsuite (test_solution.py):\n```python\n{test_suite}\n```\n\n"
        "Schreibe eine vollständige `solution.py`, die alle Tests besteht. Antworte "
        "NUR mit dem Code in einem einzigen ```python-Codeblock, ohne weiteren Text."
    )


CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def extract_code_block(output: str) -> str | None:
    match = CODE_BLOCK_RE.search(output)
    if not match:
        return None
    code = match.group(1)
    return code if code.strip() else None


def verify_coding_task(
    exercise: dict,
    cwd: Path,
    *,
    cli: str = "claude",
    timeout: int = DEFAULT_TIMEOUT,
    python: str = sys.executable,
    run_coding_path: Path | None = None,
) -> dict:
    stem = exercise["stem"]
    test_suite = exercise.get("test_suite", "")

    blind = run_agent(build_coding_prompt(stem, test_suite), cwd, cli=cli, timeout=timeout)
    if blind.exit_code != 0:
        return _unverified("blind_solve_coding", f"Blind-Löser nicht erreichbar: {blind.stderr.strip()[:200]}")

    code = extract_code_block(blind.stdout)
    if code is None:
        return _unverified("blind_solve_coding", "Blind-Lösung enthält keinen ```python-Codeblock")

    run_coding_path = run_coding_path or (Path(__file__).resolve().parent / "run_coding.py")

    with tempfile.TemporaryDirectory() as td:
        blind_file = Path(td) / "blind_solution.py"
        blind_file.write_text(code, encoding="utf-8")
        exercises_file = Path(td) / "exercises.json"
        exercises_file.write_text(json.dumps({"exercises": [exercise]}), encoding="utf-8")

        try:
            done = subprocess.run(
                [python, str(run_coding_path), "--exercises", str(exercises_file),
                 "--id", exercise["id"], "--blind-file", str(blind_file)],
                capture_output=True, text=True, timeout=timeout, check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return _unverified("blind_solve_coding", f"run_coding.py nicht startbar: {exc}")

    payload = _find_json_object(done.stdout, "verification")
    if payload is None or "verification" not in payload:
        return _unverified(
            "blind_solve_coding",
            f"run_coding.py lieferte kein verwertbares Ergebnis: {done.stderr.strip()[:200]}",
        )
    return payload["verification"]


# --- Dispatch -----------------------------------------------------------------

TYPE_VERIFIERS = {
    "multiple_choice": verify_mc,
    "open_question": verify_open,
    "flashcard": verify_flashcard,
}


def verify_one(
    exercise: dict,
    cwd: Path,
    *,
    cli: str = "claude",
    timeout: int = DEFAULT_TIMEOUT,
    python: str = sys.executable,
    run_coding_path: Path | None = None,
) -> dict:
    ex_type = exercise.get("type")
    if ex_type == "coding":
        return verify_coding_task(exercise, cwd, cli=cli, timeout=timeout, python=python, run_coding_path=run_coding_path)
    verifier = TYPE_VERIFIERS.get(ex_type)
    if verifier is None:
        return _unverified("not_run", f"Unbekannter Aufgabentyp: {ex_type!r}")
    return verifier(exercise, cwd, cli=cli, timeout=timeout)


# --- Pfad, I/O, CLI -------------------------------------------------------------

def resolve_exercises_path(topic: str, repo: Path = Path(".")) -> Path:
    """Projekt-Override vor Home (D2/Rulings), festgemacht an der **Basis**
    `.skills/verified-research/`, nicht am `research/`-Unterverzeichnis.

    Der Namensraum gehört verified-research, und dessen eigenes
    `registry.py::resolve_base_dir` prüft die Basis — ebenso `learning-coach`s
    `due_topics.py`, das diese Dateien liest. Die frühere `research/`-Bedingung
    wich davon ab: Existierte die Basis, aber noch kein `research/`, schrieb
    diese Skill nach `~`, während `learning-coach` projektlokal suchte und die
    Aufgaben dauerhaft als "nicht gefunden" meldete."""
    base_dir = Path(repo) / ".skills" / "verified-research"
    if base_dir.is_dir():
        return base_dir / "research" / f"{topic}.exercises.json"
    return Path.home() / ".skills" / "verified-research" / "research" / f"{topic}.exercises.json"


def load_exercises(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_exercises(path: Path, data: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Blind-Gate für exercise-forge-Aufgaben")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--exercises", type=Path, help="Pfad zur exercises.json")
    target.add_argument("--topic", help="Thema — Pfad wird aufgelöst (Projekt-Override oder Home)")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--id", help="nur diese eine Aufgabe prüfen")
    which.add_argument("--all", action="store_true", help="alle noch nicht 'verified' geprüften Aufgaben")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--cli", default="claude")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)

    path = args.exercises or resolve_exercises_path(args.topic, args.repo)
    if not path.is_file():
        print(f"Aufgaben-JSON nicht gefunden: {path}", file=sys.stderr)
        return 2

    data = load_exercises(path)
    exercises = data.get("exercises", [])

    if args.id:
        targets = [e for e in exercises if e.get("id") == args.id]
        if not targets:
            print(f"Aufgabe {args.id!r} nicht gefunden in {path}", file=sys.stderr)
            return 2
    else:
        targets = [e for e in exercises if derive_status_from_protocol(e)[0] != "verified"]

    checked = 0
    with tempfile.TemporaryDirectory() as td:
        cwd = Path(td)
        for exercise in targets:
            try:
                verdict = verify_one(exercise, cwd, cli=args.cli, timeout=args.timeout)
            except Exception as exc:  # noqa: BLE001 — eine malformte Aufgabe darf den
                # Batch nie mitreißen: ohne diesen Fang würde ein KeyError (z. B. eine
                # MC-Option ohne 'text') das Skript vor save_exercises() abbrechen und
                # die bereits berechneten Urteile der übrigen Aufgaben verwerfen (L2).
                verdict = _unverified(
                    "not_run", f"Blind-Gate-Aufruf fehlgeschlagen ({type(exc).__name__}): {exc}"
                )
            exercise["verification"] = verdict
            checked += 1
            status, _ = derive_status_from_protocol(exercise)
            print(f"{exercise.get('id')}: {status} ({verdict['method']}) — {verdict['detail']}")
            # Nach jeder Aufgabe sichern, nicht erst am Ende der Schleife — ein
            # Abbruch später im Batch (Timeout von außen, SIGKILL) darf bereits
            # geprüfte Urteile nicht mehr verwerfen können als bis hierhin ohnehin.
            save_exercises(path, data)

    save_exercises(path, data)  # deckt auch den Fall targets == [] ab (Schleife lief nie)
    print(f"{checked} Aufgabe(n) geprüft -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
