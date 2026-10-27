#!/usr/bin/env python3
"""Bestandsaufnahme eines Claude-Code-Config-Verzeichnisses und Plan für setup-user.

Tier 1: nur Stdlib. Schreibt nur <config-dir>/setup-user/plan.md: oben die Ansicht für
den Nutzer, darunter den Block `json setup-user-plan`, den apply_config.py liest.
Format, Normalisierung und Hash: skills/setup-user/references/plan-format.md; welche
Schlüssel gemischt werden: references/settings-merge.md. Importiert kein anderes
Skript — den Hash rechnet apply_config.py selbst, ein Test hält beide gleich.

    python inspect_config.py [--config-dir PFAD] [--answers JSON|DATEI] [--python NAME]

Ohne --config-dir gilt $CLAUDE_CONFIG_DIR, sonst ~/.claude. Exit 0 mit Plan, 2 wenn das
Verzeichnis fehlt oder settings.json unlesbar ist.

Abschnitt B: Das Plugin-Profil (references/routing.md) kommt aus `route_check.py --json`,
als Unterprozess aufgerufen, nicht importiert. Ein gesetzter Wert in enabledPlugins wird
nie umgedreht, sondern als Konflikt geführt, bis die Antwort `plugins_off` die Plugin-ID
nennt.
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
ROUTE_CHECK = Path(__file__).resolve().parent / "route_check.py"
PLACEHOLDER = "<config-dir>"
MARKER = "# setup-user: statusline"
RULES = ("communication", "verification", "context", "git")
DEFAULT_ANSWERS = {"language": "Deutsch", "tone": "knapp und sachlich", "shell": "bash", "git": "kein Commit und kein Push ohne Auftrag"}
THRESHOLDS = {"context": [60, 80], "five_hour": [80], "seven_day": [85]}
SCRIPT_RE = re.compile(r'"([^"]+\.py)"|\'([^\']+\.py)\'|(\S+\.py)\b')
INTERPRETER_RE = re.compile(r"^(?:py(?:\s+-3(?:\.\d+)?)?|python(?:3(?:\.\d+)?)?(?:\.exe)?|\S*[/\\]python(?:3(?:\.\d+)?)?(?:\.exe)?)\b")


class PlanError(Exception):
    """Bestand nicht lesbar — kein Plan."""


def resolve_config_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser()
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env).expanduser() if env else Path.home() / ".claude"


def normalize(text: str, config_dir: Path) -> str:
    """LF statt CRLF, `<config-dir>` statt des absoluten Pfads (beide Schrägstrichformen)."""
    text = text.replace("\r\n", "\n")
    raw = str(Path(config_dir).resolve())
    for form in sorted({raw, raw.replace("\\", "/"), raw.replace("/", "\\")}, key=len, reverse=True):
        text = text.replace(form, PLACEHOLDER)
    return text


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plan_hash(block):
    body = {k: v for k, v in block.items() if k != "hash"}
    return _sha(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _settings(config_dir: Path) -> dict:
    path = config_dir / "settings.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PlanError(f"settings.json unlesbar ({type(exc).__name__}) — erst reparieren, dann planen") from exc
    if not isinstance(data, dict):
        raise PlanError("settings.json ist kein JSON-Objekt")
    return data


def _script_path(command: str, config_dir: Path) -> Path | None:
    m = SCRIPT_RE.search(command)
    if not m:
        return None
    raw = next(g for g in m.groups() if g).replace(PLACEHOLDER, str(config_dir))
    path = Path(os.path.expanduser(raw))
    return path if path.is_absolute() else Path.cwd() / path


def _known_hashes() -> set[str]:
    data = _read(ASSETS / "runtime" / "known-statusline-hashes.json")
    try:
        values = json.loads(data).get("sha256", []) if data else []
    except ValueError:
        values = []
    return {v for v in values if isinstance(v, str)}


def classify_statusline(settings: dict, config_dir: Path) -> dict:
    command = (settings.get("statusLine") or {}).get("command") if isinstance(settings.get("statusLine"), dict) else None
    if not command:
        return {"kind": "none", "command": None}
    path = _script_path(command, config_dir)
    text = _read(path) if path else None
    norm_cmd = normalize(command, config_dir)
    if text is not None:
        lf = text.replace("\r\n", "\n")
        if MARKER in lf.splitlines()[:3] or _sha(lf) in _known_hashes():
            return {"kind": "own", "command": norm_cmd}
    return {"kind": "foreign", "command": norm_cmd}


def _interpreter(command: str | None, fallback: str | None) -> str:
    if command:
        m = INTERPRETER_RE.match(command.strip())
        if m:
            return m.group(0)
    return fallback or "python3"


def _fill(template: str, answers: dict) -> str:
    for key, value in answers.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


def _hook_patch(python: str) -> dict:
    fragment = json.loads((ASSETS / "settings" / "context-hint.json").read_text(encoding="utf-8"))
    text = json.dumps(fragment, ensure_ascii=False).replace("<python>", python)
    return json.loads(text)


def _routing(config_dir):
    """Bericht von route_check.py oder None, wenn das Skript nicht lief."""
    try:
        proc = subprocess.run([sys.executable, str(ROUTE_CHECK), "--config-dir", str(config_dir), "--json"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return json.loads(proc.stdout) if proc.returncode == 0 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def plugin_profile(routing, answers, planned_rules):
    """(Feld `plugins` des Blocks, enabledPlugins-Patch) nach references/routing.md."""
    if routing is None:
        return {"checked": False, "reason": "route_check.py lief nicht", "profile": [], "condition": None}, {}
    condition = json.loads(json.dumps(routing["condition"]))
    missing = [f for f in condition["c"]["missing"] if f"rules/{f}" not in planned_rules]
    condition["c"] = {"ok": not missing, "missing": missing}
    condition["met"] = routing["checked"] and all(condition[k]["ok"] for k in "abc")
    if not routing["checked"]:
        return {"checked": False, "reason": routing["reason"], "profile": [], "condition": condition}, {}
    off = {str(i) for i in answers.get("plugins_off") or []} if isinstance(answers.get("plugins_off"), list) else set()
    unmet = "; ".join(f"({k}) " + ", ".join(condition[k].get("gaps") or condition[k].get("refs") or
                                            [f"rules/{f}" for f in condition[k].get("missing", [])])
                      for k in "abc" if not condition[k]["ok"])
    profile, patch = [], {}
    for plugin in routing["plugins"]:
        if plugin["role"] == "superpowers":
            if not condition["met"]:
                profile.append({"id": plugin["id"], "action": "keep",
                                "reason": f"Abschaltbedingung nicht erfüllt: {unmet}"})
                continue
            reason = "Abschaltbedingung erfüllt"
        elif plugin["role"] == "engineering":
            reason = "Annahme: überlappt mit testing-strategy, debug-ledger und review-context"
        else:
            continue
        if plugin["explicit"] is False:
            profile.append({"id": plugin["id"], "action": "none", "reason": "schon aus"})
        elif plugin["explicit"] is True and plugin["id"] not in off:
            profile.append({"id": plugin["id"], "action": "conflict",
                            "reason": f"{reason}; in enabledPlugins auf true gesetzt — ausschalten nur mit plugins_off"})
        else:
            profile.append({"id": plugin["id"], "action": "set", "reason": reason})
            patch[plugin["id"]] = False
    return {"checked": True, "reason": None, "profile": profile, "condition": condition}, patch


def build_plan(config_dir, answers, python):
    config_dir = Path(config_dir).resolve()
    settings = _settings(config_dir)
    status = classify_statusline(settings, config_dir)
    resolved_python = _interpreter((settings.get("statusLine") or {}).get("command")
                                   if isinstance(settings.get("statusLine"), dict) else None, python)
    merged_answers = {k: (answers or {}).get(k, v) for k, v in DEFAULT_ANSWERS.items()}
    assumed = sorted(k for k in DEFAULT_ANSWERS if k not in (answers or {}))

    ops: list[dict] = []
    runtime = ["context_hint.py"] + ([] if status["kind"] == "foreign" else ["statusline.py"])
    for name in sorted(runtime):
        ops.append({"path": f"setup-user/runtime/{name}", "action": "copy",
                    "content": (ASSETS / "runtime" / name).read_text(encoding="utf-8").replace("\r\n", "\n")})
    ops.append({"path": "setup-user/thresholds.json", "action": "copy", "content": json.dumps(
        {"_meta": {"skill": "setup-user", "schema": 1, "generated": "scripts/apply_config.py"}, **THRESHOLDS},
        ensure_ascii=False, indent=2) + "\n"})
    if not (config_dir / "CLAUDE.md").exists():
        ops.append({"path": "CLAUDE.md", "action": "create",
                    "content": _fill((ASSETS / "CLAUDE.md.tmpl").read_text(encoding="utf-8"), merged_answers)})
    for rule in RULES:
        rel = f"rules/{rule}.md"
        if not (config_dir / rel).exists():
            ops.append({"path": rel, "action": "create",
                        "content": _fill((ASSETS / "rules" / f"{rule}.md").read_text(encoding="utf-8"), merged_answers)})
    patch: dict = _hook_patch(resolved_python)
    if status["kind"] != "foreign":
        patch["statusLine"] = {"command": f'{resolved_python} "{PLACEHOLDER}/setup-user/runtime/statusline.py"'}
    planned_rules = {op["path"] for op in ops if op["path"].startswith("rules/")}
    plugins, plugin_patch = plugin_profile(_routing(config_dir), answers or {}, planned_rules)
    if plugin_patch:
        patch["enabledPlugins"] = plugin_patch
    if (answers or {}).get("deny_secrets") is True:
        patch["permissions"] = {"deny": ["Read(./.env)", "Read(./.env.*)", "Read(~/.ssh/**)", "Read(**/*.pem)", "Read(**/*.key)"]}
    ops.append({"path": "settings.json", "action": "merge", "patch": patch})

    base = {}
    for op in ops:
        text = _read(config_dir / op["path"])
        base[op["path"]] = _sha(normalize(text, config_dir)) if text is not None else None
    block = {"schema": 1, "python": resolved_python, "answers": merged_answers, "assumed": assumed,
             "statusline": status, "plugins": plugins, "operations": ops, "base": base}
    block["hash"] = plan_hash(block)
    return block


def render_plan(block, config_dir):
    config_dir = Path(config_dir).resolve()
    status = block["statusline"]
    lines = [
        f"<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py --config-dir {config_dir} -->",
        "",
        "# setup-user — Plan",
        "",
        f"Ziel: `{config_dir}` · Hash `{block['hash'][:16]}` · Interpreter `{block['python']}`",
        "",
        "## Statusline",
        "",
    ]
    if status["kind"] == "own":
        lines.append("Erkannt als eigene Statusline; `statusLine` zeigt danach auf `runtime/statusline.py`, die alte Datei bleibt liegen.")
    elif status["kind"] == "none":
        lines.append("Keine Statusline eingetragen; `apply` setzt das Asset ein.")
    else:
        lines.append(f"Fremde Statusline (`{status['command']}`) bleibt eingetragen. Kontext-Hinweise nicht verfügbar — "
                     "fremde Statusline schreibt keinen Kontextzustand. Der Hook wird trotzdem eingetragen und schweigt, "
                     "bis die Asset-Statusline läuft.")
    lines += ["", "## Annahmen", ""]
    if block["assumed"]:
        lines += [f"- {k}: {block['answers'][k]} (Asset-Wert, nicht gefragt oder nicht beantwortet)" for k in block["assumed"]]
    else:
        lines.append("- keine")
    lines += ["", *render_plugins(block["plugins"]), "", "## Änderungen", ""]
    for op in block["operations"]:
        state = "neu" if block["base"].get(op["path"]) is None else "vorhanden"
        lines.append(f"### `{op['path']}` — {op['action']} ({state})")
        lines.append("")
        if op["action"] == "merge":
            lines += ["```json", json.dumps(op["patch"], ensure_ascii=False, indent=2), "```"]
        else:
            current = _read(config_dir / op["path"])
            old = normalize(current, config_dir).splitlines() if current is not None else []
            diff = list(difflib.unified_diff(old, op["content"].splitlines(), "vorher", "nachher", lineterm="", n=1))
            shown = diff[:40] + ([f"… {len(diff) - 40} Zeilen mehr"] if len(diff) > 40 else [])
            lines += ["```diff", *(shown or ["(unverändert)"]), "```"]
        lines.append("")
    lines += [
        "## Nicht gesetzt",
        "",
        "- `permissions.deny` für `.env`, `~/.ssh` und Schlüsseldateien wird nur auf Bestätigung gesetzt "
        "(Antwort `deny_secrets: true`). Ein Read-Deny gilt für die Datei-Werkzeuge und erkannte "
        "Bash-Dateikommandos, nicht für beliebige Unterprozesse.",
        "",
        "## Block für apply",
        "",
        "```json setup-user-plan",
        json.dumps(block, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(lines)


ACTION_TEXT = {"set": "→ false", "conflict": "Konflikt", "keep": "bleibt an", "none": "unverändert"}


def render_plugins(plugins):
    lines = ["## Plugins", ""]
    if not plugins["checked"]:
        lines.append(f"- ungeprüft — {plugins['reason']}; `enabledPlugins` bleibt unberührt.")
        return lines
    cond = plugins["condition"]
    lines.append(f"Abschaltbedingung für superpowers (Spec 20): {'erfüllt' if cond['met'] else 'nicht erfüllt'} "
                 f"— (a) {'ok' if cond['a']['ok'] else 'Lücke'}, (b) {'ok' if cond['b']['ok'] else 'Verweise'}, "
                 f"(c) {'ok' if cond['c']['ok'] else 'Regel fehlt'}.")
    lines.append("")
    if not plugins["profile"]:
        lines.append("- Profil: nichts zu ändern; `evaluated-*`-Plugins bleiben ungesetzt.")
    for entry in plugins["profile"]:
        lines.append(f"- `{entry['id']}`: {ACTION_TEXT[entry['action']]} — {entry['reason']}")
    if any(e["action"] == "conflict" for e in plugins["profile"]):
        lines += ["", "Konflikt: Der Wert steht schon in `enabledPlugins` (eine Installation per CLI setzt `true`). "
                  "Ausschalten nur auf ausdrückliche Antwort: `--answers '{\"plugins_off\": [\"<id>\"]}'`, dann neu planen."]
    return lines


def _answers(arg: str | None) -> dict:
    if not arg:
        return {}
    text = arg if arg.lstrip().startswith("{") else Path(arg).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise PlanError("--answers ist kein JSON-Objekt")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description="Plan für setup-user schreiben (Spec 21)")
    parser.add_argument("--config-dir")
    parser.add_argument("--answers", help="JSON-Objekt oder Pfad zu einer JSON-Datei")
    parser.add_argument("--python", help="Interpreter für die Kommandos, falls keiner im Bestand steht")
    args = parser.parse_args(argv)
    config_dir = resolve_config_dir(args.config_dir)
    print(f"Ziel: {config_dir.resolve()}")
    if not config_dir.is_dir():
        print(f"Config-Verzeichnis existiert nicht: {config_dir}", file=sys.stderr)
        return 2
    try:
        block = build_plan(config_dir, _answers(args.answers), args.python)
    except (PlanError, ValueError, OSError) as exc:
        print(f"Kein Plan: {exc}", file=sys.stderr)
        return 2
    out = config_dir / "setup-user" / "plan.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_plan(block, config_dir), encoding="utf-8", newline="\n")
    print(f"Plan geschrieben: {out} (Hash {block['hash'][:16]}, {len(block['operations'])} Operationen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
