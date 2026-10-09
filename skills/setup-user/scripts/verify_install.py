#!/usr/bin/env python3
"""Prüft eine setup-user-Installation, indem es die eingetragenen Befehle laufen lässt.

Tier 1: nur Stdlib. Ausgeführt werden nur Befehle aus settings.json (Statusline und
UserPromptSubmit-Hook), deren Skript Byte für Byte (LF-normalisiert) einem Asset gleicht.
Jeder andere Befehl — die alte Statusline des Nutzers, eine fremde — läuft nie und steht
als „ungeprüft (fremd, nicht ausgeführt)" im Ergebnis, weil er CLAUDE_CONFIG_DIR
ignorieren und den echten Cache beschreiben könnte.

Die Asset-Befehle laufen über `bash -c` wie in Claude Code (unter Windows Git Bash), mit
CLAUDE_CONFIG_DIR, HOME und USERPROFILE auf einem Temp-Verzeichnis und 10 Sekunden je
Befehl. Dort liegt vorher ein Beispielzustand oberhalb jeder Schwelle. Erwartet: die
Statusline gibt eine Zeile aus und schreibt den Cache; der Hook gibt genau ein JSON-Objekt
mit additionalContext aus. Ein Hook, der schweigt, ein Exit ungleich 0 und eine leere
Statusline sind Befunde. Fehlt bash, heißt das Ergebnis „ungeprüft — keine bash".

    python verify_install.py [--config-dir PFAD]

Exit 0 ohne Befund (auch wenn etwas ungeprüft blieb — das steht in der Ausgabe),
1 mit Befund.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SCRIPT_RE = re.compile(r'"([^"]+\.py)"|\'([^\']+\.py)\'|(\S+\.py)\b')
SESSION = "setup-user-verify"
TIMEOUT = 10


def _find_bash():
    return shutil.which("bash")


def _sha_lf(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    except OSError:
        return None


def _script(command: str) -> Path | None:
    m = SCRIPT_RE.search(command)
    if not m:
        return None
    path = Path(os.path.expanduser(next(g for g in m.groups() if g)))
    return path if path.is_absolute() else Path.cwd() / path


def _commands(settings: dict) -> list[tuple[str, str]]:
    found = []
    line = settings.get("statusLine")
    if isinstance(line, dict) and isinstance(line.get("command"), str):
        found.append(("statusline", line["command"]))
    hooks = settings.get("hooks") if isinstance(settings.get("hooks"), dict) else {}
    for group in hooks.get("UserPromptSubmit", []) if isinstance(hooks.get("UserPromptSubmit"), list) else []:
        for item in group.get("hooks", []) if isinstance(group, dict) else []:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                found.append(("hook", item["command"]))
    return found


def _seed(sandbox: Path, now: int) -> None:
    (sandbox / "home").mkdir()
    state = sandbox / "setup-user" / "state"
    state.mkdir(parents=True)
    (state / f"context-{SESSION}.json").write_text(
        json.dumps({"session_id": SESSION, "used_percentage": 85}), encoding="utf-8")
    (sandbox / "usage-cache.json").write_text(json.dumps({
        "five_hour": {"used_percentage": 90, "resets_at_epoch": now + 3600},
        "seven_day": {"used_percentage": 90, "resets_at_epoch": now + 86400}}), encoding="utf-8")


def _payload(kind: str, sandbox: Path, now: int) -> bytes:
    if kind == "statusline":
        data = {"session_id": SESSION, "model": {"id": "verify", "display_name": "Verify"},
                "workspace": {"current_dir": str(sandbox), "project_dir": str(sandbox)},
                "context_window": {"used_percentage": 85},
                "rate_limits": {"five_hour": {"used_percentage": 90, "resets_at": now + 3600},
                                "seven_day": {"used_percentage": 90, "resets_at": now + 86400}}}
    else:
        data = {"session_id": SESSION, "hook_event_name": "UserPromptSubmit", "prompt": "verify",
                "cwd": str(sandbox), "transcript_path": str(sandbox / "t.jsonl"), "permission_mode": "default"}
    return json.dumps(data).encode("utf-8")


def _run(bash: str, command: str, payload: bytes, sandbox: Path):
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(sandbox), "HOME": str(sandbox / "home"),
           "USERPROFILE": str(sandbox / "home")}
    return subprocess.run([bash, "-c", command], input=payload, capture_output=True, env=env,
                          cwd=sandbox, timeout=TIMEOUT)


def _check_output(kind: str, proc, sandbox: Path) -> list[str]:
    out = proc.stdout.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        return [f"{kind}: Exit {proc.returncode} — {proc.stderr.decode('utf-8', errors='replace').strip()[:120]}"]
    if kind == "statusline":
        problems = [] if out.strip() else ["statusline: Ausgabe leer"]
        if not (sandbox / "usage-cache.json").is_file():
            problems.append("statusline: kein Limit-Cache in der Sandbox")
        return problems
    if not out.strip():
        return ["hook: schweigt, obwohl der Beispielzustand über jeder Schwelle liegt"]
    try:
        data = json.loads(out)
    except ValueError:
        return ["hook: stdout ist nicht genau ein JSON-Objekt"]
    spec = data.get("hookSpecificOutput") if isinstance(data, dict) else None
    if not isinstance(spec, dict) or spec.get("hookEventName") != "UserPromptSubmit" \
            or not str(spec.get("additionalContext", "")).startswith("[setup-user]"):
        return ["hook: Ausgabe ohne hookEventName UserPromptSubmit oder ohne [setup-user]-Hinweis"]
    return []


def verify(config_dir):
    config_dir = Path(config_dir)
    result = {"ran": [], "findings": [], "unchecked": []}
    try:
        settings = json.loads((config_dir / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        result["findings"].append(f"settings.json unlesbar ({type(exc).__name__})")
        return result
    assets = {"statusline": _sha_lf(ASSETS / "runtime" / "statusline.py"),
              "hook": _sha_lf(ASSETS / "runtime" / "context_hint.py")}
    runnable = []
    for kind, command in _commands(settings if isinstance(settings, dict) else {}):
        script = _script(command)
        if script is None:
            result["unchecked"].append(f"{kind}: ungeprüft (fremd, nicht ausgeführt) — kein Python-Skript: {command}")
            continue
        if not script.is_file():
            result["findings"].append(f"{kind}: Skript fehlt: {script}")
            continue
        if _sha_lf(script) != assets[kind]:
            result["unchecked"].append(f"{kind}: ungeprüft (fremd, nicht ausgeführt): {command}")
            continue
        runnable.append((kind, command))
    if not runnable:
        return result
    bash = _find_bash()
    if bash is None:
        result["unchecked"] += [f"{kind}: ungeprüft — keine bash" for kind, _ in runnable]
        return result
    now = int(time.time())
    with tempfile.TemporaryDirectory(prefix="setup-user-verify-") as tmp:
        sandbox = Path(tmp)
        _seed(sandbox, now)
        for kind, command in sorted(runnable, key=lambda r: r[0] != "statusline"):
            try:
                proc = _run(bash, command, _payload(kind, sandbox, now), sandbox)
            except subprocess.TimeoutExpired:
                result["findings"].append(f"{kind}: Zeitüberschreitung nach {TIMEOUT} s")
                continue
            result["ran"].append({"kind": kind, "command": command, "exit": proc.returncode})
            result["findings"] += _check_output(kind, proc, sandbox)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="setup-user-Installation in einer Sandbox prüfen (Spec 21)")
    parser.add_argument("--config-dir")
    args = parser.parse_args(argv)
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    config_dir = Path(args.config_dir or env or Path.home() / ".claude").expanduser()
    result = verify(config_dir)
    for item in result["ran"]:
        print(f"gelaufen: {item['kind']} (Exit {item['exit']})")
    for item in result["findings"]:
        print(f"BEFUND: {item}")
    for item in result["unchecked"]:
        print(f"UNGEPRÜFT: {item}")
    if result["findings"]:
        print("Ergebnis: Befunde")
        return 1
    print("Ergebnis: " + ("geprüft" if not result["unchecked"] else "teilweise ungeprüft — siehe oben"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
