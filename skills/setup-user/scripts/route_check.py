#!/usr/bin/env python3
"""Routing-Prüfung von setup-user (Spec 21, Abschnitt B): welche Plugins im User-Scope
aktiv sind und ob superpowers abgeschaltet werden darf.

Tier 1: nur Stdlib, importiert kein anderes Skript. Liest nur, schreibt nichts.

    python route_check.py [--config-dir PFAD] [--json | --markdown]

Bestand: `<config-dir>/plugins/installed_plugins.json` (Version 1 oder 2) mit Feld
`installPath`; zeigt der Pfad ins Leere, sucht das Skript unter
`$CLAUDE_CODE_PLUGIN_CACHE_DIR`, sonst `<config-dir>/plugins/cache`, nach
`<marketplace>/<plugin>/<version>`. Dazu `plugins/synced/*/.claude-plugin/plugin.json`
(Plugin-ID `<name>@synced`). Aktiv ist ein Plugin nach `enabledPlugins` der
User-Settings, sonst nach `defaultEnabled` seines Marketplace-Eintrags, sonst an.
Projekt-Settings bewertet es nicht.

Gemeldet werden SessionStart-Hooks aktiver Plugins (`<plugin> · SessionStart-Hook ·
<matcher>`), Namenskollisionen zwischen aktiven Plugins und `<config-dir>/skills/`,
Descriptions mit `superpowers:` und die Abschaltbedingung aus Spec 20:
(a) `references/superpowers-gaps.json` hat keine Zeile „Lücke"; (b) keine Description
eines aktiven Plugins außer superpowers selbst enthält `superpowers:`; (c) die Dateien
der Zeilen mit Status „Regel" liegen unter `<config-dir>/rules/`.

Der Bericht enthält keine absoluten Pfade — inspect_config.py nimmt ihn in den Plan,
dessen Hash ortsneutral bleiben muss. Ohne `plugins/` heißt er „ungeprüft". Exit 0,
auch mit Befunden; 2 nur bei falschem Aufruf.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

GAPS_PATH = Path(__file__).resolve().parent.parent / "references" / "superpowers-gaps.json"
DESCRIPTION_RE = re.compile(r"^description:\s*(.*)$", re.MULTILINE)


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def resolve_config_dir(arg):
    if arg:
        return Path(arg).expanduser()
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env).expanduser() if env else Path.home() / ".claude"


def _description(skill_md):
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    if not text.startswith("---"):
        return ""
    front = text.split("---", 2)[1] if text.count("---") >= 2 else ""
    m = DESCRIPTION_RE.search(front)
    return m.group(1).strip().strip('"').strip("'") if m else ""


def _entry(root, name):
    """Marketplace-Eintrag oder plugin.json des Plugins `name` unter `root`, oder {}."""
    data = _json(root / ".claude-plugin" / "marketplace.json")
    for entry in (data.get("plugins") if isinstance(data, dict) else None) or []:
        if isinstance(entry, dict) and entry.get("name") == name:
            return entry
    data = _json(root / ".claude-plugin" / "plugin.json")
    return data if isinstance(data, dict) else {}


def _skills(root, entry):
    """{skill-name: SKILL.md-Pfad} — aus der skills-Liste des Eintrags, sonst skills/*/."""
    listed = entry.get("skills") if isinstance(entry.get("skills"), list) else None
    if listed is not None:
        dirs = [(root / str(s)).resolve() for s in listed]
    else:
        dirs = sorted(p.parent for p in (root / "skills").glob("*/SKILL.md"))
    return {d.name: d / "SKILL.md" for d in dirs if (d / "SKILL.md").is_file()}


def _hook_files(root, entry):
    files = [root / "hooks" / "hooks.json"]
    declared = entry.get("hooks")
    for item in declared if isinstance(declared, list) else [declared]:
        if isinstance(item, str):
            files.append(root / item)
    inline = [declared] if isinstance(declared, dict) else []
    return files, inline


def _session_start(root, entry):
    files, inline = _hook_files(root, entry)
    configs = inline + [d for d in (_json(f) for f in dict.fromkeys(files) if f.is_file()) if isinstance(d, dict)]
    matchers = []
    for config in configs:
        events = config.get("hooks") if isinstance(config.get("hooks"), dict) else config
        for group in events.get("SessionStart") or [] if isinstance(events, dict) else []:
            if isinstance(group, dict):
                matchers.append(str(group.get("matcher") or "*"))
    return matchers


def _cache_dirs(config_dir):
    env = os.environ.get("CLAUDE_CODE_PLUGIN_CACHE_DIR")
    return [Path(env).expanduser()] if env else [config_dir / "plugins" / "cache"]


def _install_root(config_dir, install_path, marketplace, name):
    if install_path and Path(install_path).is_dir():
        return Path(install_path)
    for cache in _cache_dirs(config_dir):
        versions = sorted((p for p in (cache / marketplace / name).glob("*") if p.is_dir()),
                          key=lambda p: (p.stat().st_mtime, p.name))
        if versions:
            return versions[-1]
    return None


def _role(name):
    if name == "superpowers":
        return "superpowers"
    if name == "engineering":
        return "engineering"
    return "cc" if name.startswith("evaluated-") else "other"


def _installed(config_dir):
    """[(id, name, marketplace, root|None)] aus installed_plugins.json und synced/."""
    found = []
    data = _json(config_dir / "plugins" / "installed_plugins.json")
    entries = data.get("plugins") if isinstance(data, dict) else None
    for plugin_id, value in sorted(entries.items()) if isinstance(entries, dict) else []:
        if "@" not in plugin_id:
            continue
        name, marketplace = plugin_id.split("@", 1)
        installs = value if isinstance(value, list) else [value]
        path = next((i.get("installPath") for i in installs if isinstance(i, dict) and i.get("installPath")), None)
        found.append((plugin_id, name, marketplace, _install_root(config_dir, path, marketplace, name)))
    synced = config_dir / "plugins" / "synced"
    for folder in sorted(p for p in synced.iterdir() if p.is_dir()) if synced.is_dir() else []:
        manifest = _json(folder / ".claude-plugin" / "plugin.json")
        if isinstance(manifest, dict):
            name = str(manifest.get("name") or folder.name)
            found.append((f"{name}@synced", name, "synced", folder))
    return found


def _gaps():
    data = _json(GAPS_PATH)
    return data.get("rows", []) if isinstance(data, dict) else None


def route_report(config_dir):
    """Bericht als JSON-fähiges Dict, ohne absolute Pfade."""
    config_dir = Path(config_dir)
    settings = _json(config_dir / "settings.json")
    enabled = settings.get("enabledPlugins") if isinstance(settings, dict) else None
    enabled = enabled if isinstance(enabled, dict) else {}
    plugins = []
    if (config_dir / "plugins").is_dir():
        for plugin_id, name, marketplace, root in _installed(config_dir):
            entry = _entry(root, name) if root else {}
            explicit = enabled.get(plugin_id) if isinstance(enabled.get(plugin_id), bool) else None
            default = entry.get("defaultEnabled") if isinstance(entry.get("defaultEnabled"), bool) else None
            active = explicit if explicit is not None else (default if default is not None else True)
            why = "enabledPlugins" if explicit is not None else ("defaultEnabled" if default is not None else "installiert")
            skills = _skills(root, entry) if root else {}
            plugins.append({
                "id": plugin_id, "name": name, "marketplace": marketplace, "role": _role(name),
                "found": root is not None, "active": active, "why": why, "explicit": explicit,
                "skills": sorted(skills),
                "session_start": _session_start(root, entry) if root else [],
                "superpowers_refs": sorted(s for s, md in skills.items() if "superpowers:" in _description(md)),
            })
    report = {"checked": bool(plugins), "reason": None if plugins else
              "keine Plugins unter <config-dir>/plugins", "plugins": plugins}

    owners = {}
    for p in plugins:
        if p["active"]:
            for s in p["skills"]:
                owners.setdefault(s, []).append(p["id"])
    for md in sorted((config_dir / "skills").glob("*/SKILL.md")):
        owners.setdefault(md.parent.name, []).append("user-skills")
    report["collisions"] = [{"skill": s, "plugins": sorted(ids)} for s, ids in sorted(owners.items()) if len(ids) > 1]

    rows = _gaps()
    gaps = None if rows is None else sorted(n for r in rows if r.get("status") == "Lücke" for n in r.get("superpowers", []))
    refs = [f"{p['id']}/{s}" for p in plugins if p["active"] and p["role"] != "superpowers" for s in p["superpowers_refs"]]
    rules = sorted({f for r in rows or [] if r.get("status") == "Regel" for f in r.get("rules", [])})
    missing = [f for f in rules if not (config_dir / "rules" / f).is_file()]
    condition = {
        "a": {"ok": gaps == [], "gaps": gaps if gaps is not None else ["superpowers-gaps.json unlesbar"]},
        "b": {"ok": not refs, "refs": refs},
        "c": {"ok": not missing and rows is not None, "missing": missing},
    }
    condition["met"] = all(condition[k]["ok"] for k in "abc")
    report["condition"] = condition
    return report


def render_markdown(report):
    lines = ["## Plugins", ""]
    if not report["checked"]:
        lines.append(f"- ungeprüft — {report['reason']}")
    else:
        active = [p for p in report["plugins"] if p["active"]]
        inactive = [p for p in report["plugins"] if not p["active"]]
        lines.append("- Aktiv: " + (", ".join(f"{p['id']} ({p['why']})" for p in active) or "keins"))
        if inactive:
            lines.append("- Aus: " + ", ".join(f"{p['id']} ({p['why']})" for p in inactive))
        for p in report["plugins"]:
            if not p["found"]:
                lines.append(f"- {p['id']}: Installationsordner nicht gefunden — Skills und Hooks ungeprüft")
        for p in active:
            lines += [f"- {p['name']} · SessionStart-Hook · {m}" for m in p["session_start"]]
        lines += [f"- Kollision: {c['skill']} in {', '.join(c['plugins'])}" for c in report["collisions"]]
        lines += [f"- superpowers:-Verweis: {r}" for r in report["condition"]["b"]["refs"]]
    cond = report["condition"]
    parts = [
        "(a) " + ("keine Lücke" if cond["a"]["ok"] else "Lücke: " + ", ".join(cond["a"]["gaps"])),
        "(b) " + ("kein superpowers:-Verweis" if cond["b"]["ok"] else f"{len(cond['b']['refs'])} superpowers:-Verweis(e)"),
        "(c) " + ("Regeln installiert" if cond["c"]["ok"] else "fehlt rules/" + ", rules/".join(cond["c"]["missing"])),
    ]
    if not report["checked"]:
        parts[1] = "(b) ungeprüft"
    met = cond["met"] and report["checked"]
    lines.append(f"- Abschaltbedingung: {'erfüllt' if met else 'nicht erfüllt'} — " + "; ".join(parts))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Plugins im User-Scope prüfen (setup-user, Spec 21 B)")
    parser.add_argument("--config-dir")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true")
    mode.add_argument("--markdown", action="store_true")
    args = parser.parse_args(argv)
    report = route_report(resolve_config_dir(args.config_dir))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
