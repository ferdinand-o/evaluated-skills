#!/usr/bin/env python3
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
"""
import calendar
import json
import os
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"

BAR_WIDTH = 10
FOLDER = "\U0001F4C1"   # 📁
BRANCH = "\U0001F33F"   # 🌿
CLOCK = "⏱️"  # ⏱️


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


def main():
    # Windows setzt stdout/stdin beim Piping sonst auf die Systemcodepage
    # (z.B. cp1252) statt UTF-8, was Umlaute/Emojis zerstoert.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

    data = json.load(sys.stdin)

    model = data.get("model", {}).get("display_name", "?")
    current_dir = data.get("workspace", {}).get("current_dir") or data.get("cwd") or ""
    dir_base = os.path.basename(current_dir.rstrip("/\\")) or current_dir

    rate_limits = data.get("rate_limits") or {}
    five_hour = rate_limits.get("five_hour") or {}
    seven_day = rate_limits.get("seven_day") or {}

    five_pct = five_hour.get("used_percentage")
    five_reset_epoch = five_hour.get("resets_at")
    week_pct = seven_day.get("used_percentage")
    week_reset_epoch = seven_day.get("resets_at")

    five_reset_berlin = to_berlin_str(five_reset_epoch)
    week_reset_berlin = to_berlin_str(week_reset_epoch)

    # --- Cache-Datei aktualisieren: ~/.claude/usage-cache.json ---
    cache_file = os.path.join(os.path.expanduser("~"), ".claude", "usage-cache.json")
    now_utc = datetime.now(timezone.utc)
    now_offset, now_abbr = berlin_offset(now_utc)
    now_berlin = now_utc + now_offset
    cache = {
        "updated_at": f"{now_berlin:%Y-%m-%dT%H:%M:%S} {now_abbr}",
        "five_hour": {
            "used_percentage": five_pct,
            "resets_at_epoch": five_reset_epoch,
            "resets_at_berlin": five_reset_berlin,
        },
        "seven_day": {
            "used_percentage": week_pct,
            "resets_at_epoch": week_reset_epoch,
            "resets_at_berlin": week_reset_berlin,
        },
    }
    try:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except OSError:
        pass

    context_pct = data.get("context_window", {}).get("used_percentage")
    cost_usd = data.get("cost", {}).get("total_cost_usd")
    duration_str = fmt_duration(data.get("cost", {}).get("total_duration_ms"))
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

    print("\n".join(lines))


if __name__ == "__main__":
    main()
