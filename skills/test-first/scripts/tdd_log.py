#!/usr/bin/env python3
"""Beleg für den Test-zuerst-Zyklus von test-first (Spec 24). Tier 1, nur Stdlib.

    tdd_log.py start [--note TEXT]            neuer Abschnitt, alle Zustände zurück
    tdd_log.py red --test ID -- BEFEHL        der Befehl muss scheitern
    tdd_log.py green --test ID -- BEFEHL      nur nach Rot desselben Tests
    tdd_log.py refactor --test ID -- BEFEHL   nur nach Grün desselben Tests
    tdd_log.py status                         Zusammenfassung des letzten Abschnitts

Das Skript führt den übergebenen Testbefehl aus und schreibt je Aufruf höchstens eine
Zeile `| id | phase | befehl | exit | zeit | ausgabe |` nach
`.skills/cache/test-first/log.md` an der Repo-Wurzel (`git rev-parse --show-toplevel`,
sonst das Arbeitsverzeichnis; `--root` überschreibt beides). Zustandsmodell:

    red       Exit ≠ 0 → red (rot)          Exit 0 → sofort-grün (unverändert, Exit 1)
    green     nur aus rot: Exit 0 → green (grün), sonst noch-rot (rot, Exit 1)
    refactor  nur aus grün: Exit 0 → refactor (grün), sonst refactor-rot (rot, Exit 1)
    jeder     Programm fehlt, Exit 127, Zeitgrenze → ungeprüft (unverändert, Exit 1)

`green` ohne Rot und `refactor` ohne Grün schreiben keine Zeile und enden mit 1. Der
Zustand je Test steht nirgends sonst: Er wird bei jedem Aufruf aus dem letzten
Abschnitt des Logs gelesen. Unter der Tabelle steht `Vollständige Zyklen: N` — Tests,
deren letzter Zyklus (ab dem letzten `red`) ein Grün hat und die jetzt grün sind.

Ausführung wie `verify_stop.py` (setup-repo): Vorprüfung der Programme per shlex und
shutil.which, Shell an der Repo-Wurzel, Zeitgrenze 300 s, Ausgabe UTF-8 mit Ersetzung;
das Log wird vor jedem Schreiben neu gelesen und atomar ersetzt. Das Skript meldet; es
hält niemanden an. Exit 2 bei falschem Aufruf, etwa einer ID mit Leerzeichen oder `|`.
"""
import argparse
import os
import shlex
import signal
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HEADER = "<!-- skill: test-first | schema: 1 | generated: scripts/tdd_log.py -->"
TITLE = "# test-first — Beleg"
TABLE_HEAD = "| Test | Phase | Befehl | Exit | Zeit | Ausgabe |\n| --- | --- | --- | --- | --- | --- |"
SECTION_PREFIX = "## Abschnitt "
COUNT_PREFIX = "Vollständige Zyklen: "
TIMEOUT = 300
TAIL_LINES = 10
CELL_CHARS = 300

# Phase → Zustand danach; None heißt unverändert.
AFTER = {"red": "rot", "sofort-grün": None, "green": "grün", "noch-rot": "rot",
         "refactor": "grün", "refactor-rot": "rot", "ungeprüft": None}


def repo_root():
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd()


def log_path(root):
    return Path(root) / ".skills" / "cache" / "test-first" / "log.md"


def missing_program(command):
    """Das erste Programm einer Befehlskette, das nicht auffindbar ist, oder None —
    dieselbe Zerlegung wie in verify_stop.py."""
    lexer = shlex.shlex(command, posix=os.name != "nt", punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = command.split()
    expect_program = True
    for token in tokens:
        if token and set(token) <= set("&|;()<>"):
            expect_program = True
            continue
        if expect_program:
            expect_program = False
            program = token.strip('"')
            if "=" in program and not program.startswith(("/", ".")):
                expect_program = True  # Variablenzuweisung vor dem Programm
                continue
            if shutil.which(program) is None and not (os.path.isfile(program) and os.access(program, os.X_OK)):
                return program
    return None


def cell(text):
    """Text für eine Tabellenzelle: `|` wird `¦`, Zeilen werden mit `<br>` verbunden."""
    lines = str(text).splitlines() or [""]
    return "<br>".join(" ".join(line.replace("|", "¦").split()) for line in lines)


def tail(output):
    lines = [line[:CELL_CHARS] for line in output.splitlines() if line.strip()]
    return cell("\n".join(lines[-TAIL_LINES:]))


# --- Log lesen und schreiben ---------------------------------------------------------

def read_log(root):
    try:
        return log_path(root).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def split_sections(text):
    """(Kopf, [Abschnitts-Texte]) — jeder Abschnitt beginnt mit `## Abschnitt `."""
    parts = text.split("\n" + SECTION_PREFIX)
    return parts[0], [SECTION_PREFIX + p for p in parts[1:]]


def section_rows(section):
    """[(id, phase)] in Reihenfolge."""
    rows = []
    for line in section.splitlines():
        if not line.startswith("| ") or line.startswith(("| Test ", "| ---")):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2:
            rows.append((cells[0], cells[1]))
    return rows


def states(rows):
    """{id: (zustand, zyklus_vollständig, phasen)} aus den Zeilen eines Abschnitts."""
    result = {}
    for test_id, phase in rows:
        state, complete, phases = result.get(test_id, (None, False, []))
        after = AFTER.get(phase)
        if phase == "red":
            complete = False
        elif phase == "green":
            complete = True
        if after is not None:
            state = after
        result[test_id] = (state, complete, phases + [phase])
    return result


def complete_cycles(rows):
    return sum(1 for state, complete, _ in states(rows).values() if complete and state == "grün")


def new_section(note=""):
    stamp = datetime.now().isoformat(timespec="seconds")
    title = SECTION_PREFIX + stamp + (f" — {cell(note)}" if note else "")
    return f"{title}\n\n{TABLE_HEAD}\n\n{COUNT_PREFIX}0\n"


def with_row(section, row):
    """Abschnitt mit angehängter Zeile und neu gezählter Zyklen-Zeile."""
    lines = [line for line in section.rstrip("\n").splitlines() if not line.startswith(COUNT_PREFIX)]
    while lines and not lines[-1].strip():
        lines.pop()
    lines.append(row)
    body = "\n".join(lines)
    return f"{body}\n\n{COUNT_PREFIX}{complete_cycles(section_rows(body))}\n"


def write_log(root, text):
    path = log_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    for attempt in range(3):
        try:
            os.replace(tmp, path)
            return
        except OSError:
            time.sleep(0.05 * (attempt + 1))
    tmp.unlink(missing_ok=True)
    raise OSError(f"{path}: nicht schreibbar")


def compose(text, section=None, row=None):
    """Neuer Log-Text: optional ein neuer Abschnitt, optional eine Zeile im letzten."""
    if text is None:
        head, sections = f"{HEADER}\n{TITLE}\n", []
    else:
        head, sections = split_sections(text)
        head = head.rstrip("\n") + "\n"
    if section is not None or not sections:
        sections.append(section if section is not None else new_section())
    if row is not None:
        sections[-1] = with_row(sections[-1], row)
    return head + "".join("\n" + s.rstrip("\n") + "\n" for s in sections)


def unversioned_notice(root):
    """Hinweis, wenn `.skills/cache/` nicht ignoriert ist (Bootstrap, Spec 00 §1)."""
    try:
        out = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", ".skills/cache/test-first/log.md"],
                             capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode == 1:
        return ("Hinweis: .skills/cache/ ist nicht in .gitignore — dort ist ein unversionierter "
                "Ordner entstanden (setup-repo trägt die Zeile ein).")
    return None


# --- Aufrufe -----------------------------------------------------------------------

def run_command(root, command):
    """(phase_hint, exit, ausgabe): phase_hint ist 'ungeprüft' oder None."""
    missing = missing_program(command)
    if missing:
        return "ungeprüft", None, f"{missing} fehlt"
    # Eigene Prozessgruppe: Bei der Zeitgrenze endet die ganze Kette, nicht nur die Shell —
    # sonst hielte ein Kindprozess die Pipe offen und der Aufruf hinge weiter.
    posix = os.name != "nt"
    proc = subprocess.Popen(command, shell=True, cwd=str(root), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                            start_new_session=posix)
    try:
        output, _ = proc.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL) if posix else proc.kill()
        except OSError:
            pass
        proc.communicate()
        return "ungeprüft", None, f"Zeitgrenze {TIMEOUT} s überschritten"
    output = output or ""
    if proc.returncode == 127:
        return "ungeprüft", 127, output or "Exit 127 — Programm nicht gefunden"
    return None, proc.returncode, output


def record(root, action, test_id, command):
    """(exit_code, meldung) für red, green oder refactor; schreibt höchstens eine Zeile."""
    root = Path(root)
    text = read_log(root)
    sections = split_sections(text)[1] if text else []
    current = states(section_rows(sections[-1])) if sections else {}
    state = current.get(test_id, (None, False, []))[0]
    if action == "green" and state != "rot":
        return 1, f"{test_id}: kein Rot im aktuellen Abschnitt — erst `red`, keine Zeile geschrieben."
    if action == "refactor" and state != "grün":
        return 1, f"{test_id}: nicht grün — `refactor` erst nach `green`, keine Zeile geschrieben."

    hint, code, output = run_command(root, command)
    if hint:
        phase = hint
    elif action == "red":
        phase = "red" if code != 0 else "sofort-grün"
    elif action == "green":
        phase = "green" if code == 0 else "noch-rot"
    else:
        phase = "refactor" if code == 0 else "refactor-rot"

    stamp = datetime.now().isoformat(timespec="seconds")
    row = (f"| {test_id} | {phase} | `{cell(command).replace('`', chr(39))}` | "
           f"{'—' if code is None else code} | {stamp} | {tail(output)} |")
    first = text is None
    write_log(root, compose(read_log(root), row=row))   # neu gelesen vor dem Schreiben

    messages = {
        "red": f"{test_id}: rot (Exit {code}) — jetzt minimal implementieren.",
        "sofort-grün": f"{test_id}: sofort grün — der Test prüft nichts Neues. Schärfen, oder das Verhalten gibt es schon.",
        "green": f"{test_id}: grün nach Rot — Zyklus vollständig.",
        "noch-rot": f"{test_id}: noch rot (Exit {code}).",
        "refactor": f"{test_id}: nach dem Aufräumen grün.",
        "refactor-rot": f"{test_id}: Aufräumen hat den Test rot gemacht (Exit {code}) — zurück auf grün bringen.",
        "ungeprüft": f"{test_id}: ungeprüft — {output.splitlines()[0] if output.strip() else 'kein Lauf'}.",
    }
    message = messages[phase]
    if first:
        notice = unversioned_notice(root)
        message = f"{message}\nLog angelegt: {log_path(root)}" + (f"\n{notice}" if notice else "")
    return (0 if phase in ("red", "green", "refactor") else 1), message


def status(root):
    text = read_log(root)
    sections = split_sections(text)[1] if text else []
    if not sections:
        return 1, f"ungeprüft — kein Log unter {log_path(root)}"
    rows = section_rows(sections[-1])
    lines = [sections[-1].splitlines()[0]]
    for test_id, (state, complete, phases) in states(rows).items():
        shown = state or ("sofort-grün" if phases and phases[-1] == "sofort-grün" else "ungeprüft")
        mark = " — Zyklus vollständig" if complete and state == "grün" else ""
        lines.append(f"- {test_id}: {shown} ({' → '.join(phases)}){mark}")
    lines.append(f"{COUNT_PREFIX}{complete_cycles(rows)}")
    return 0, "\n".join(lines)


def start(root, note):
    write_log(root, compose(read_log(root), section=new_section(note)))
    return 0, f"Neuer Abschnitt in {log_path(root)}"


def _command(parts):
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return subprocess.list2cmdline(parts) if os.name == "nt" else shlex.join(parts)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    command_parts = []
    if "--" in argv:
        i = argv.index("--")
        argv, command_parts = argv[:i], argv[i + 1:]
    parser = argparse.ArgumentParser(prog="tdd_log.py", description="Beleg für Rot vor Grün (test-first).")
    parser.add_argument("action", choices=["start", "red", "green", "refactor", "status"])
    parser.add_argument("--test", default=None, help="Test-ID ohne Leerzeichen und ohne |")
    parser.add_argument("--note", default="", help="Notiz zum Abschnitt (nur start)")
    parser.add_argument("--root", default=None, help="Repo-Wurzel (Default: git toplevel, sonst cwd)")
    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else repo_root()

    if args.action == "status":
        code, message = status(root)
    elif args.action == "start":
        code, message = start(root, args.note)
    else:
        test_id = args.test or ""
        if not test_id or any(ch.isspace() for ch in test_id) or "|" in test_id:
            print(f"Test-ID ungültig: {test_id!r} — ohne Leerzeichen und ohne |.", file=sys.stderr)
            return 2
        command = _command(command_parts)
        if not command:
            print("Befehl fehlt: tdd_log.py " + args.action + " --test ID -- BEFEHL", file=sys.stderr)
            return 2
        code, message = record(root, args.action, test_id, command)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
