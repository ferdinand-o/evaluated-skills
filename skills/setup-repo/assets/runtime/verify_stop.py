#!/usr/bin/env python3
"""Optionaler Stop-Hook von setup-repo (Spec 22): hält das Turn-Ende an, solange die
Verifikation rot ist — höchstens dreimal in Folge je Session.

    verify_stop.py              Stop-Hook, liest die Hook-Payload von stdin
    verify_stop.py --selftest   prüft nur, ob das Programm des Befehls existiert

Der Befehl steht in der CLAUDE.md der Repo-Wurzel als Zeile `Verifikation: `<befehl>``;
Repo-Wurzel ist `$CLAUDE_PROJECT_DIR`, sonst das Arbeitsverzeichnis. Rot → Exit 2, der
Grund auf stderr (Claude sieht ihn). Nach drei roten Läufen in Folge Exit 0 mit
`systemMessage` „rot nach drei Versuchen", und die Zählung beginnt neu; grün setzt sie
zurück. Fehlt der Befehl oder sein Programm, oder läuft er in die Zeitgrenze: Exit 0 mit
`systemMessage` „ungeprüft — …", dieselbe Meldung höchstens einmal je Session. Zustand:
`.skills/cache/setup-repo/verify-stop.json` mit `_meta`, atomar geschrieben, Einträge
älter als sieben Tage fallen weg. Jede Ausnahme wird gefangen; Exit nur 0 oder 2.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

META = {"skill": "setup-repo", "schema": 1, "generated": "assets/runtime/verify_stop.py"}
LINE_RE = re.compile(r"^Verifikation:\s*`([^`]+)`\s*$", re.MULTILINE)
MAX_BLOCKS = 3
TIMEOUT = 300
MAX_AGE = 7 * 24 * 3600
TAIL_LINES = 40
PREFIX = "[setup-repo]"


def repo_root():
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env else Path.cwd()


def read_command(root):
    try:
        text = (Path(root) / "CLAUDE.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = LINE_RE.search(text)
    return m.group(1).strip() if m else None


def missing_program(command):
    """Das erste Programm einer Befehlskette, das nicht auffindbar ist, oder None.

    Zerlegt mit shlex samt Operatoren, damit `;` oder `&&` in Anführungszeichen nicht
    trennen; unter Windows ohne POSIX-Escapes, damit Backslash-Pfade heil bleiben."""
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


def selftest(repo_root):
    command = read_command(repo_root)
    if not command:
        return {"ok": False, "detail": "kein Verifikationsbefehl in CLAUDE.md"}
    missing = missing_program(command)
    if missing:
        return {"ok": False, "detail": f"{missing} fehlt"}
    return {"ok": True, "detail": f"Programm gefunden für: {command}"}


def _state_path(root):
    return Path(root) / ".skills" / "cache" / "setup-repo" / "verify-stop.json"


def load_state(root):
    try:
        data = json.loads(_state_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    sessions = data.get("sessions") if isinstance(data, dict) else None
    return sessions if isinstance(sessions, dict) else {}


def save_state(root, sessions):
    now = time.time()
    sessions = {k: v for k, v in sessions.items()
                if isinstance(v, dict) and now - float(v.get("at", 0) or 0) <= MAX_AGE}
    path = _state_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps({"_meta": META, "sessions": sessions}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        for attempt in range(3):
            try:
                os.replace(tmp, path)
                return
            except OSError:
                time.sleep(0.05 * (attempt + 1))
        tmp.unlink(missing_ok=True)
    except OSError:
        pass


def _notice(text):
    return json.dumps({"systemMessage": f"{PREFIX} {text}"}, ensure_ascii=False)


def run_stop(payload, repo_root):
    """(exit_code, stdout, stderr) für eine Stop-Payload."""
    payload = payload if isinstance(payload, dict) else {}
    sid = payload.get("session_id")
    sid = sid if isinstance(sid, str) and sid else "ohne-session"
    sessions = load_state(repo_root)
    entry = sessions.get(sid) if isinstance(sessions.get(sid), dict) else {}
    entry = {"red": int(entry.get("red", 0) or 0), "notified": list(entry.get("notified", []))}

    def unverified(reason):
        if reason in entry["notified"]:
            return 0, "", ""
        entry["notified"].append(reason)
        sessions[sid] = {**entry, "at": time.time()}
        save_state(repo_root, sessions)
        return 0, _notice(f"Verifikation ungeprüft — {reason}"), ""

    command = read_command(repo_root)
    if not command:
        return unverified("kein Verifikationsbefehl in CLAUDE.md")
    missing = missing_program(command)
    if missing:
        return unverified(f"{missing} fehlt")
    try:
        proc = subprocess.run(command, shell=True, cwd=str(repo_root), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return unverified(f"Zeitüberschreitung nach {TIMEOUT} s")

    if proc.returncode == 0:
        if entry["red"]:
            sessions[sid] = {**entry, "red": 0, "at": time.time()}
            save_state(repo_root, sessions)
        return 0, "", ""

    red = entry["red"] + 1
    if red > MAX_BLOCKS:
        sessions[sid] = {**entry, "red": 0, "at": time.time()}
        save_state(repo_root, sessions)
        return 0, _notice(f"Verifikation rot nach drei Versuchen: {command} — Turn-Ende zugelassen."), ""
    sessions[sid] = {**entry, "red": red, "at": time.time()}
    save_state(repo_root, sessions)
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-TAIL_LINES:])
    reason = (f"{PREFIX} Verifikation rot (Versuch {red} von {MAX_BLOCKS}): {command}\n"
              f"Behebe den Fehler, bevor du den Turn beendest.\n{tail}\n")
    return 2, "", reason


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        root = repo_root()
        if "--selftest" in argv:
            sys.stdout.write(json.dumps(selftest(root), ensure_ascii=False) + "\n")
            return 0
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except ValueError:
            payload = {}
        code, out, err = run_stop(payload, root)
        if out:
            sys.stdout.buffer.write((out + "\n").encode("utf-8"))
        if err:
            sys.stderr.buffer.write(err.encode("utf-8"))
        return code
    except BaseException as exc:  # noqa: BLE001 — ein Hook endet nie mit Traceback
        try:
            sys.stdout.write(_notice(f"verify_stop: interner Fehler ({type(exc).__name__})") + "\n")
        except Exception:  # noqa: BLE001
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
