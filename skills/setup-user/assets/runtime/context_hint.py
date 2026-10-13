#!/usr/bin/env python3
# setup-user: context_hint
"""UserPromptSubmit-Hook: meldet Claude das Überschreiten einer Kontext- oder Limitschwelle.

Tier 1: nur Stdlib. Liest den Kontextzustand, den die Statusline je Session schreibt,
und den Limit-Cache des Accounts; Format und Regeln stehen in
skills/setup-user/references/thresholds.md. Der Hook hält nie etwas an: Jede Ausnahme
wird gefangen, es gibt kein argparse, und er endet immer mit Exit 0. Beim Schweigen
bleibt stdout leer; sonst steht dort genau ein JSON-Objekt mit
hookSpecificOutput.hookEventName und additionalContext.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

DEFAULT_THRESHOLDS = {"context": [60, 80], "five_hour": [80], "seven_day": [85]}
LIMIT_LABELS = {"five_hour": "5-Stunden-Limit", "seven_day": "7-Tage-Limit"}
SESSION_RE = re.compile(r"[A-Za-z0-9_-]+")
META = {"skill": "setup-user", "schema": 1, "generated": "assets/runtime/context_hint.py"}


def _config_dir() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    if here.parent.name == "runtime" and here.parent.parent.name == "setup-user":
        return here.parent.parent.parent
    return Path.home() / ".claude"


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, obj) -> None:
    """Atomar über eine Temp-Datei; scheitert os.replace (Windows, offener Leser), drei
    Versuche, danach bleibt die alte Datei."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for attempt in range(3):
            try:
                os.replace(tmp, path)
                return
            except OSError:
                time.sleep(0.05 * (attempt + 1))
        tmp.unlink(missing_ok=True)
    except OSError:
        pass


def _touch(path: Path) -> None:
    try:
        if path.exists():
            os.utime(path)
    except OSError:
        pass


def _thresholds(config_dir: Path) -> dict:
    data = _read_json(config_dir / "setup-user" / "thresholds.json")
    result = {}
    for kind, default in DEFAULT_THRESHOLDS.items():
        values = data.get(kind) if isinstance(data, dict) else None
        ok = isinstance(values, list) and values and all(isinstance(v, (int, float)) for v in values)
        result[kind] = sorted(values) if ok else default
    return result


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _context_part(payload: dict, state_dir: Path, thresholds: list) -> str | None:
    sid = payload.get("session_id")
    if not isinstance(sid, str) or not SESSION_RE.fullmatch(sid):
        return None
    state = _read_json(state_dir / f"context-{sid}.json")
    hints_path = state_dir / f"hints-{sid}.json"
    if not isinstance(state, dict) or state.get("session_id") != sid or not _number(state.get("used_percentage")):
        _touch(hints_path)
        return None
    pct = state["used_percentage"]
    stored = _read_json(hints_path)
    reported = stored.get("reported", {}) if isinstance(stored, dict) else {}
    if not isinstance(reported, dict):
        reported = {}
    updated, crossed = {}, []
    for threshold in thresholds:
        key = str(threshold)
        if pct >= threshold:
            if not reported.get(key):
                crossed.append(threshold)
            updated[key] = True
        else:
            updated[key] = False
    if updated != reported or not isinstance(stored, dict):
        _write_json(hints_path, {"_meta": META, "session_id": sid, "reported": updated})
    else:
        _touch(hints_path)
    if not crossed:
        return None
    return (f"Kontext {round(pct)} % (Schwelle {max(crossed)} %). "
            "Laut Nutzerregel context.md ist das der Punkt für Handoff und /clear.")


def _limit_parts(config_dir: Path, state_dir: Path, thresholds: dict, now: float) -> list[str]:
    cache = _read_json(config_dir / "usage-cache.json")
    path = state_dir / "limit-hints.json"
    stored = _read_json(path)
    reported = set(stored.get("reported", [])) if isinstance(stored, dict) and isinstance(stored.get("reported"), list) else set()
    parts, changed = [], False
    for window, label in LIMIT_LABELS.items():
        entry = cache.get(window) if isinstance(cache, dict) else None
        if not isinstance(entry, dict):
            continue
        pct, reset = entry.get("used_percentage"), entry.get("resets_at_epoch")
        if not _number(pct) or not _number(reset) or reset <= now:
            continue
        crossed = []
        for threshold in thresholds[window]:
            key = f"{window}:{threshold}:{int(reset)}"
            if pct >= threshold and key not in reported:
                crossed.append(threshold)
                reported.add(key)
                changed = True
        if crossed:
            when = time.strftime("%H:%M", time.gmtime(reset))
            parts.append(f"{label} {round(pct)} % (Schwelle {max(crossed)} %), Reset {when} UTC.")
    alive = {k for k in reported if k.rsplit(":", 1)[-1].isdigit() and int(k.rsplit(":", 1)[-1]) > now}
    if changed or alive != reported:
        _write_json(path, {"_meta": META, "reported": sorted(alive)})
    else:
        _touch(path)
    return parts


def hint_for(payload, config_dir, now):
    """Hinweistext ohne Ausgabeform, oder None. Liest und schreibt nur die Merker unter
    <config_dir>/setup-user/state/."""
    if not isinstance(payload, dict):
        return None
    config_dir = Path(config_dir)
    state_dir = config_dir / "setup-user" / "state"
    thresholds = _thresholds(config_dir)
    parts = []
    context = _context_part(payload, state_dir, thresholds["context"])
    if context:
        parts.append(context)
    parts.extend(_limit_parts(config_dir, state_dir, thresholds, now))
    return "[setup-user] " + " ".join(parts) if parts else None


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        payload = json.loads(raw) if raw.strip() else {}
        text = hint_for(payload, _config_dir(), time.time())
        if text:
            out = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}
            sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
            sys.stdout.buffer.flush()
    except BaseException:  # noqa: BLE001 — ein Hook-Fehler darf nie einen Prompt anhalten
        pass
    return 0


if __name__ == "__main__":
    main()
    sys.exit(0)
