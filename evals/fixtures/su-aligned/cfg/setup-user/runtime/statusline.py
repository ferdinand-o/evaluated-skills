#!/usr/bin/env python3
# setup-user: statusline
"""Claude Code Statusline.

Zeile 1: [Modell] Verzeichnis | Git-Branch
Zeile 2: Contextfenster-Balken | Session-Kosten | Session-Dauer
Zeile 3/4: Claude.ai Nutzungslimits (5h / 7 Tage) als Balken mit Reset-Zeit
           in Europe/Berlin

Mehrzeilen-Ausgabe: siehe https://code.claude.com/docs/en/statusline#display-multiple-lines
Jede per print() ausgegebene Zeile wird als eigene Statuszeile dargestellt.

Berechnet den Europe/Berlin-Offset selbst (EU-DST-Regel), weil das
zoneinfo-Modul unter Windows ohne das zusaetzliche Paket "tzdata" keine
IANA-Zeitzonendatenbank findet.

Asset von setup-user (Spec 21), Vorlage ist die Statusline des Nutzers vom 2026-10-11
(tests/fixtures/setup-user/statusline-original.py); die Anzeige ist gleich. Korrigiert:
stdin als UTF-8-Bytes, leeres oder kaputtes stdin und null-Felder brechen nichts; die
Zeilen kommen zuerst, geschrieben wird danach; der Limit-Cache liegt im
Config-Verzeichnis ($CLAUDE_CONFIG_DIR, sonst drei Ebenen über dieser Datei, sonst
~/.claude) und behält ein Fenster, für das kein neuer Wert kommt; je Session entsteht
setup-user/state/context-<session_id>.json für den Kontext-Hinweis; geschrieben wird
atomar; das Skript endet immer mit Exit 0. Format: references/thresholds.md.
"""
import calendar
import json
import os
import re
import subprocess
import sys
import time as _time
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"

BAR_WIDTH = 10
FOLDER = "\U0001F4C1"   # 📁
BRANCH = "\U0001F33F"   # 🌿
CLOCK = "⏱️"  # ⏱️

META = {"skill": "setup-user", "schema": 1, "generated": "assets/runtime/statusline.py"}
SESSION_RE = re.compile(r"[A-Za-z0-9_-]+")
STATE_MAX_AGE = 24 * 3600
TMP_MAX_AGE = 3600


def last_sunday(year, month):
    last_day = calendar.monthrange(year, month)[1]
    d = date(year, month, last_day)
    offset = (d.weekday() - 6) % 7  # Monday=0 ... Sunday=6
    return d - timedelta(days=offset)


def berlin_offset(dt_utc):
    year = dt_utc.year
    dst_start = datetime.combine(last_sunday(year, 3), time(1, 0), tzinfo=timezone.utc)
    dst_end = datetime.combine(last_sunday(year, 10), time(1, 0), tzinfo=timezone.utc)
    if dst_start <= dt_utc < dst_end:
        return timedelta(hours=2), "CEST"
    return timedelta(hours=1), "CET"


def to_berlin_str(epoch):
    if epoch is None:
        return None
    dt_utc = datetime.fromtimestamp(epoch, tz=timezone.utc)
    offset, abbr = berlin_offset(dt_utc)
    dt_berlin = dt_utc + offset
    return f"{dt_berlin:%d.%m. %H:%M} {abbr}"


def fmt_duration(ms):
    if not ms:
        return None
    total_sec = int(ms // 1000)
    mins, secs = divmod(total_sec, 60)
    hours, mins = divmod(mins, 60)
    if hours:
        return f"{hours}h {mins}m"
    return f"{mins}m {secs}s"


def bar(pct):
    pct = max(0, min(100, pct))
    filled = round(pct * BAR_WIDTH / 100)
    color = RED if pct >= 90 else YELLOW if pct >= 70 else GREEN
    return f"{color}{'█' * filled}{'░' * (BAR_WIDTH - filled)}{RESET}"


def git_branch(cwd):
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd, capture_output=True, text=True, timeout=2,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


# --- Eingabe, robust gegen null, falsche Typen und kaputtes stdin -----------------

def _obj(value):
    return value if isinstance(value, dict) else {}


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def read_input():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        data = json.loads(raw) if raw.strip() else {}
    except (OSError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


# --- Anzeige (gleich der Vorlage) --------------------------------------------------

def render(data):
    model = _obj(data.get("model")).get("display_name", "?")
    workspace = _obj(data.get("workspace"))
    current_dir = workspace.get("current_dir") or data.get("cwd") or ""
    if not isinstance(current_dir, str):
        current_dir = ""
    dir_base = os.path.basename(current_dir.rstrip("/\\")) or current_dir

    rate_limits = _obj(data.get("rate_limits"))
    five_hour = _obj(rate_limits.get("five_hour"))
    seven_day = _obj(rate_limits.get("seven_day"))
    five_pct = _num(five_hour.get("used_percentage"))
    week_pct = _num(seven_day.get("used_percentage"))
    five_reset_berlin = to_berlin_str(_num(five_hour.get("resets_at")))
    week_reset_berlin = to_berlin_str(_num(seven_day.get("resets_at")))

    cost = _obj(data.get("cost"))
    context_pct = _num(_obj(data.get("context_window")).get("used_percentage"))
    cost_usd = _num(cost.get("total_cost_usd"))
    duration_str = fmt_duration(_num(cost.get("total_duration_ms")))
    branch = git_branch(current_dir or None)

    # --- Zeile 1: Modell, Verzeichnis, Git-Branch ---
    line1 = f"{CYAN}[{model}]{RESET} {FOLDER} {dir_base}"
    if branch:
        line1 += f" | {BRANCH} {branch}"

    lines = [line1]

    # --- Zeile 2: Context-Balken, Kosten, Dauer ---
    if context_pct is not None:
        parts = [f"{bar(context_pct)} {context_pct:.0f}% Kontext"]
        if cost_usd is not None:
            parts.append(f"{YELLOW}${cost_usd:.2f}{RESET}")
        if duration_str:
            parts.append(f"{CLOCK} {duration_str}")
        lines.append(" | ".join(parts))

    # --- Zeile 3/4: Nutzungslimits ---
    if five_pct is not None:
        text = f"{bar(five_pct)} {five_pct:.0f}% 5h-Limit"
        if five_reset_berlin:
            text += f" | Reset {five_reset_berlin}"
        lines.append(text)

    if week_pct is not None:
        text = f"{bar(week_pct)} {week_pct:.0f}% Wochen-Limit"
        if week_reset_berlin:
            text += f" | Reset {week_reset_berlin}"
        lines.append(text)

    return "\n".join(lines)


# --- Schreiben: Cache und Kontextzustand -------------------------------------------

def config_dir():
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    if here.parent.name == "runtime" and here.parent.parent.name == "setup-user":
        return here.parent.parent.parent
    return Path(os.path.expanduser("~")) / ".claude"


def _read_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data


def write_json(path, obj):
    """Über eine Temp-Datei und os.replace; drei Versuche (Windows, offener Leser),
    danach bleibt die alte Datei."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        for attempt in range(3):
            try:
                os.replace(tmp, path)
                return
            except OSError:
                _time.sleep(0.05 * (attempt + 1))
        tmp.unlink(missing_ok=True)
    except OSError:
        pass


def _window(new, old):
    """Neuer Wert nur, wenn das Fenster da ist und used_percentage eine Zahl; sonst der alte."""
    new = _obj(new)
    pct = _num(new.get("used_percentage"))
    if pct is not None:
        epoch = _num(new.get("resets_at"))
        return {"used_percentage": pct, "resets_at_epoch": epoch, "resets_at_berlin": to_berlin_str(epoch)}
    if isinstance(old, dict):
        return old
    return {"used_percentage": None, "resets_at_epoch": None, "resets_at_berlin": None}


def update_cache(data, cfg):
    path = cfg / "usage-cache.json"
    existing = _obj(_read_json(path))
    rate_limits = _obj(data.get("rate_limits"))
    now_utc = datetime.now(timezone.utc)
    now_offset, now_abbr = berlin_offset(now_utc)
    now_berlin = now_utc + now_offset
    cache = dict(existing)
    cache["_meta"] = META
    cache["updated_at"] = f"{now_berlin:%Y-%m-%dT%H:%M:%S} {now_abbr}"
    cache["five_hour"] = _window(rate_limits.get("five_hour"), existing.get("five_hour"))
    cache["seven_day"] = _window(rate_limits.get("seven_day"), existing.get("seven_day"))
    write_json(path, cache)


def update_context_state(data, cfg):
    sid = data.get("session_id")
    if not isinstance(sid, str) or not SESSION_RE.fullmatch(sid):
        return
    pct = _num(_obj(data.get("context_window")).get("used_percentage"))
    write_json(cfg / "setup-user" / "state" / f"context-{sid}.json",
               {"_meta": META, "session_id": sid, "used_percentage": pct})


def prune(cfg):
    now = _time.time()
    for folder in (cfg, cfg / "setup-user" / "state"):
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            try:
                age = now - path.stat().st_mtime
                if path.name.endswith(".tmp") and age > TMP_MAX_AGE:
                    path.unlink()
                elif folder.name == "state" and path.is_file() and age > STATE_MAX_AGE:
                    path.unlink()
            except OSError:
                pass


def main():
    try:
        data = read_input()
        try:
            text = render(data)
        except Exception:  # noqa: BLE001 — eine Statuszeile ohne Details ist besser als keine
            text = f"{CYAN}[?]{RESET}"
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
        cfg = config_dir()
        update_cache(data, cfg)
        update_context_state(data, cfg)
        prune(cfg)
    except BaseException:  # noqa: BLE001 — die Statusline endet immer mit 0
        pass
    return 0


if __name__ == "__main__":
    main()
    sys.exit(0)
