#!/usr/bin/env python3
"""Bereichs-Hook von setup-repo (Spec 22, Abschnitt C). Tier 1, nur Stdlib.

Läuft an zwei Ereignissen, erkannt an `hook_event_name` der Payload auf stdin:

- `UserPromptSubmit`: hält die Basis des Turns fest — HEAD und für jede geänderte oder
  unversionierte Datei einen Inhalts-Hash — und gibt eine offene Meldung aus dem letzten
  Turn als `hookSpecificOutput.additionalContext` aus.
- `Stop`: bestimmt die Dateien, die sich im Turn geändert haben (Commits des Turns zählen
  mit, vorher Uncommittetes nur, wenn es sich weiter ändert). Liegt eine außerhalb der
  Bereiche aller aktiven Ziele in `docs/goals.md` und wurde sie in der Session noch nicht
  gemeldet, gibt er `systemMessage` aus und merkt die Meldung für den nächsten Prompt.

Er hält nie etwas an: kein `decision`, kein Exit 2, kein Folgeturn; Exit immer 0.
Schweigt ohne Repo-Commit, ohne Ledger, ohne aktives Ziel mit Bereich. Eine fehlende oder
unbekannte Ledger-Kopfzeile und ein gescheiterter git-Aufruf werden einmal je Session per
`systemMessage` gemeldet. Pfade relativ zur Repo-Wurzel, git immer mit `-z`. Zustand:
`$SETUP_REPO_GOAL_STATE`, sonst `.skills/cache/setup-repo/goal-scope.json`, mit `_meta`,
atomar geschrieben; unlesbar heißt Neustart; Einträge älter als sieben Tage fallen weg.
Ledger, Glob-Dialekt und Ausnahmen: references/goals.md.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

META = {"skill": "setup-repo", "schema": 1, "generated": "assets/runtime/goal_scope.py"}
PREFIX = "[setup-repo]"
MAX_AGE = 7 * 24 * 3600
MAX_LISTED = 10
HEADER_RE = re.compile(r"^<!--\s*skill:\s*setup-repo\s*\|\s*schema:\s*1\s*\|")
GOAL_ID_RE = re.compile(r"^G\d+$")
EXCLUDED_FILES = {"docs/goals.md", "handoff.md", "docs/decisions.md", "CLAUDE.md", ".gitignore"}
EXCLUDED_DIRS = ("docs/debugging/", "docs/specs/wip/", "docs/plans/", ".claude/", ".skills/")


class GitError(Exception):
    pass


# --- Globs -------------------------------------------------------------------------

def _segment_regex(segment):
    out = []
    for ch in segment:
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
    return "".join(out)


def glob_match(pattern, path):
    """`**` beliebig viele Ordner, `*` und `?` innerhalb eines Pfadteils, `/` als Trenner,
    Groß- und Kleinschreibung zählen, keine Klammern; `src/` gilt als `src/**`."""
    pattern = pattern.strip()
    if not pattern:
        return False
    if pattern.endswith("/"):
        pattern += "**"
    parts = pattern.split("/")
    regex = ""
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if part == "**":
            regex += ".*" if last else "(?:[^/]+/)*"
        else:
            regex += _segment_regex(part) + ("" if last else "/")
    return re.fullmatch(regex, path) is not None


# --- git ---------------------------------------------------------------------------

def _git(cwd, *args):
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, timeout=30)
    except FileNotFoundError as exc:
        raise GitError("git nicht gefunden") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitError(f"git {args[0]} gescheitert ({type(exc).__name__})") from exc
    if proc.returncode != 0:
        raise GitError(f"git {args[0]} gescheitert: {proc.stderr.decode('utf-8', 'replace').strip()[:120]}")
    return proc.stdout.decode("utf-8", "replace")


def _toplevel(root):
    return Path(_git(root, "rev-parse", "--show-toplevel").strip())


def _head(top):
    try:
        return _git(top, "rev-parse", "--verify", "-q", "HEAD").strip() or None
    except GitError:
        return None


def _hash(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _z(text):
    return [p for p in text.split("\0") if p]


def _dirty(top):
    """Pfade mit Änderungen gegenüber HEAD samt unversionierten, aus `git status -z`."""
    entries = _git(top, "status", "--porcelain", "-z", "--untracked-files=all").split("\0")
    paths, i = [], 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        paths.append(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            if i < len(entries) and entries[i]:
                paths.append(entries[i])
            i += 1
    return paths


# --- Ledger ------------------------------------------------------------------------

def read_ledger(top):
    """(None, None) ohne Ledger; (Grund, None) bei unbekannter Kopfzeile; sonst
    (None, [(id, [globs]), …]) der aktiven Ziele."""
    try:
        text = (top / "docs" / "goals.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, None
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not HEADER_RE.match(first):
        return "Kopfzeile von docs/goals.md fehlt oder ist unbekannt — Bereichsprüfung aus", None
    goals, in_active = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            in_active = line.strip() == "## Aktiv"
            continue
        if not in_active or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not GOAL_ID_RE.match(cells[0]):
            continue
        globs = [g.strip().strip("`") for g in cells[3].split(",") if g.strip().strip("`")]
        goals.append((cells[0], globs))
    return None, goals


def _excluded(path):
    return path in EXCLUDED_FILES or path.startswith(EXCLUDED_DIRS)


# --- Zustand -----------------------------------------------------------------------

def _state_path(top):
    env = os.environ.get("SETUP_REPO_GOAL_STATE")
    return Path(env) if env else top / ".skills" / "cache" / "setup-repo" / "goal-scope.json"


def load_state(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    sessions = data.get("sessions") if isinstance(data, dict) else None
    return sessions if isinstance(sessions, dict) else {}


def save_state(path, sessions):
    now = time.time()
    sessions = {k: v for k, v in sessions.items()
                if isinstance(v, dict) and now - float(v.get("at", 0) or 0) <= MAX_AGE}
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


def _session(sessions, sid):
    entry = sessions.get(sid)
    entry = entry if isinstance(entry, dict) else {}
    entry.setdefault("reported", [])
    entry.setdefault("notified", [])
    entry.setdefault("pending", None)
    entry["at"] = time.time()
    sessions[sid] = entry
    return entry


def _notice(text):
    return json.dumps({"systemMessage": f"{PREFIX} {text}"}, ensure_ascii=False)


def _sid(payload):
    sid = payload.get("session_id") if isinstance(payload, dict) else None
    return sid if isinstance(sid, str) and sid else "ohne-session"


# --- Ereignisse --------------------------------------------------------------------

def on_prompt(payload, root):
    """Basis des Turns festhalten; offene Meldung als additionalContext ausgeben."""
    try:
        top = _toplevel(root)
    except GitError:
        return ""
    head = _head(top)
    if head is None:
        return ""
    state_path = _state_path(top)
    sessions = load_state(state_path)
    entry = _session(sessions, _sid(payload))
    try:
        entry["base"] = {"head": head, "files": {p: _hash(top / p) for p in _dirty(top)}}
    except GitError:
        entry["base"] = None
    pending, entry["pending"] = entry.get("pending"), None
    save_state(state_path, sessions)
    if not pending:
        return ""
    return json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                              "additionalContext": pending}}, ensure_ascii=False)


def on_stop(payload, root):
    """Änderungen des Turns gegen die Bereiche aktiver Ziele; meldet, hält nie an."""
    sid = _sid(payload)
    try:
        top = _toplevel(root)
    except GitError as exc:
        return _once_without_repo(root, sid, str(exc))
    if _head(top) is None:
        return ""
    problem, goals = read_ledger(top)
    state_path = _state_path(top)
    sessions = load_state(state_path)
    entry = _session(sessions, sid)

    def once(reason):
        if reason in entry["notified"]:
            save_state(state_path, sessions)
            return ""
        entry["notified"].append(reason)
        save_state(state_path, sessions)
        return _notice(reason)

    if problem:
        return once(problem)
    scoped = [(gid, globs) for gid, globs in goals or [] if globs]
    base = entry.get("base")
    if not scoped or not isinstance(base, dict) or not base.get("head"):
        save_state(state_path, sessions)
        return ""
    try:
        candidates = set(_z(_git(top, "diff", base["head"], "--name-only", "-z")))
        candidates |= set(_z(_git(top, "ls-files", "--others", "--exclude-standard", "-z")))
    except GitError as exc:
        return once(str(exc))
    before = base.get("files") or {}
    changed = set()
    for path in candidates | set(before):
        now = _hash(top / path)
        if path in before:
            if now != before[path]:
                changed.add(path)
        else:
            changed.add(path)
    outside = sorted(p for p in changed if not _excluded(p) and p not in entry["reported"]
                     and not any(glob_match(g, p) for _, globs in scoped for g in globs))
    if not outside:
        save_state(state_path, sessions)
        return ""
    entry["reported"].extend(outside)
    ids = ", ".join(gid for gid, _ in scoped)
    where = f"des Bereichs von {ids}" if len(scoped) == 1 else f"der Bereiche von {ids}"
    listed = ", ".join(outside[:MAX_LISTED]) + (f" und {len(outside) - MAX_LISTED} weitere"
                                                if len(outside) > MAX_LISTED else "")
    text = (f"{PREFIX} Geändert außerhalb {where}: {listed}. Laut Zielregel: vom Nutzer verlangt, "
            "Teil des Ziels, trivial oder ein Kandidat.")
    entry["pending"] = f"{entry['pending']}\n{text}" if entry.get("pending") else text
    save_state(state_path, sessions)
    return json.dumps({"systemMessage": text}, ensure_ascii=False)


def _once_without_repo(root, sid, reason):
    """git fehlt oder scheitert schon an der Wurzel: einmal je Session melden. Der Zustand
    liegt dann am Ort, den SETUP_REPO_GOAL_STATE nennt, sonst unter dem Projektordner."""
    path = _state_path(Path(root))
    sessions = load_state(path)
    entry = _session(sessions, sid)
    if reason in entry["notified"]:
        save_state(path, sessions)
        return ""
    entry["notified"].append(reason)
    save_state(path, sessions)
    return _notice(f"Bereichsprüfung aus — {reason}")


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except ValueError:
            payload = {}
        payload = payload if isinstance(payload, dict) else {}
        cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
        root = os.environ.get("CLAUDE_PROJECT_DIR") or cwd or os.getcwd()
        event = payload.get("hook_event_name")
        out = on_prompt(payload, root) if event == "UserPromptSubmit" else \
            on_stop(payload, root) if event == "Stop" else ""
        if out:
            sys.stdout.buffer.write((out + "\n").encode("utf-8"))
    except BaseException as exc:  # noqa: BLE001 — ein Hook endet nie mit Traceback und nie anders als 0
        try:
            sys.stdout.write(_notice(f"goal_scope: interner Fehler ({type(exc).__name__})") + "\n")
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    main()
    sys.exit(0)
