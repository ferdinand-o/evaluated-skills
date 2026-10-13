#!/usr/bin/env python3
"""Wendet einen setup-user-Plan an — nur, wenn Plan und Bestand seit der Planung gleich sind.

Tier 1: nur Stdlib. Liest aus plan.md nur den Block `json setup-user-plan`, prüft seinen
Hash und die Basis-Hashes der berührten Dateien (G2: das Skript meldet und bricht ab),
legt Backups an und schreibt in der Reihenfolge aus references/settings-merge.md:
runtime/ (je Kopie per Hash geprüft), thresholds.json, CLAUDE.md und Regeln, zuletzt
settings.json. Bricht ein Schritt ab, bleibt settings.json unberührt. Importiert kein
anderes Skript; den Hash rechnet es wie inspect_config.py, ein Test hält beide gleich.

    python apply_config.py --plan <config-dir>/setup-user/plan.md --config-dir <config-dir>

--config-dir muss auf der Kommandozeile stehen und existieren; $CLAUDE_CONFIG_DIR zählt
nicht. Exit 0 angewendet, 2 abgebrochen (Grund auf stderr, keine Datei berührt).
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

PLACEHOLDER = "<config-dir>"
BLOCK_RE = re.compile(r"^```json setup-user-plan[ \t]*\n(.*?)\n```[ \t]*$", re.MULTILINE | re.DOTALL)
OWN_SUFFIXES = ("setup-user/runtime/context_hint.py", "setup-user/runtime/statusline.py")
ORDER = {"copy": 0, "create": 2, "append": 2, "merge": 3}


class ApplyError(Exception):
    """Plan nicht anwendbar — nichts wurde geschrieben, oder settings.json blieb unberührt."""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_hash(block):
    body = {k: v for k, v in block.items() if k != "hash"}
    return _sha(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def normalize(text: str, config_dir: Path) -> str:
    text = text.replace("\r\n", "\n")
    raw = str(Path(config_dir).resolve())
    for form in sorted({raw, raw.replace("\\", "/"), raw.replace("/", "\\")}, key=len, reverse=True):
        text = text.replace(form, PLACEHOLDER)
    return text


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def read_block(plan_path: Path) -> dict:
    text = _read(Path(plan_path))
    if text is None:
        raise ApplyError(f"Plan nicht lesbar: {plan_path}")
    blocks = BLOCK_RE.findall(text.replace("\r\n", "\n"))
    if len(blocks) != 1:
        raise ApplyError(f"Plan hat {len(blocks)} Blöcke `json setup-user-plan`, erwartet genau einen")
    try:
        block = json.loads(blocks[0])
    except ValueError as exc:
        raise ApplyError(f"Block ist kein JSON ({exc})") from exc
    if not isinstance(block, dict) or block.get("schema") != 1:
        raise ApplyError("Block mit unbekanntem schema — Plan neu erzeugen")
    if canonical_hash(block) != block.get("hash"):
        raise ApplyError("Hash passt nicht — der Plan wurde nach der Planung geändert; neu planen")
    return block


def _check_base(block: dict, config_dir: Path) -> None:
    changed = []
    for path, expected in block.get("base", {}).items():
        current = _read(config_dir / path)
        actual = _sha(normalize(current, config_dir)) if current is not None else None
        if actual != expected:
            changed.append(path)
    if changed:
        raise ApplyError("Bestand seit der Planung geändert: " + ", ".join(changed) + " — neu planen")


def _substitute(text: str, config_dir: Path) -> str:
    return text.replace(PLACEHOLDER, Path(config_dir).resolve().as_posix())


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    for attempt in range(3):
        try:
            os.replace(tmp, path)
            return
        except OSError:
            if attempt == 2:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.05 * (attempt + 1))


def _backup_dir(config_dir: Path) -> Path:
    root = config_dir / "setup-user" / "backups"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    candidate, n = root / stamp, 1
    while candidate.exists():
        n += 1
        candidate = root / f"{stamp}-{n}"
    return candidate


def _is_own(command) -> bool:
    if not isinstance(command, str):
        return False
    norm = command.replace("\\", "/")
    return any(suffix in norm for suffix in OWN_SUFFIXES)


def merge_settings(current: dict, patch: dict) -> dict:
    result = dict(current)
    if "statusLine" in patch:
        line = dict(result["statusLine"]) if isinstance(result.get("statusLine"), dict) else {"type": "command"}
        line["command"] = patch["statusLine"]["command"]
        result["statusLine"] = line
    for event, groups in (patch.get("hooks") or {}).items():
        hooks = dict(result["hooks"]) if isinstance(result.get("hooks"), dict) else {}
        kept = []
        for group in hooks.get(event, []) if isinstance(hooks.get(event), list) else []:
            if not isinstance(group, dict):
                kept.append(group)
                continue
            items = [h for h in group.get("hooks", []) if not (isinstance(h, dict) and _is_own(h.get("command")))]
            if items:
                kept.append({**group, "hooks": items})
        hooks[event] = kept + groups
        result["hooks"] = hooks
    if "permissions" in patch:
        perms = dict(result["permissions"]) if isinstance(result.get("permissions"), dict) else {}
        for key, values in patch["permissions"].items():
            existing = perms.get(key) if isinstance(perms.get(key), list) else []
            perms[key] = existing + [v for v in values if v not in existing]
        result["permissions"] = perms
    return result


def apply_plan(plan_path, config_dir):
    config_dir = Path(config_dir)
    if not config_dir.is_dir():
        raise ApplyError(f"Config-Verzeichnis existiert nicht: {config_dir} — apply legt es nie an")
    config_dir = config_dir.resolve()
    block = read_block(Path(plan_path))
    _check_base(block, config_dir)
    ops = sorted(block["operations"], key=lambda op: (ORDER.get(op["action"], 9),
                                                      0 if op["path"].startswith("setup-user/runtime/") else 1))

    backup = None
    to_back_up = [op["path"] for op in ops if (config_dir / op["path"]).is_file()
                  and op["action"] in ("copy", "append", "merge")]
    try:
        if to_back_up:
            backup = _backup_dir(config_dir)
            for rel in to_back_up:
                target = backup / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(config_dir / rel, target)

        written = []
        for op in ops:
            dest = config_dir / op["path"]
            if op["action"] in ("copy", "create"):
                if op["action"] == "create" and dest.exists():
                    raise ApplyError(f"{op['path']} existiert inzwischen — create überschreibt nie")
                text = _substitute(op["content"], config_dir)
                _atomic_write(dest, text)
                if _sha(dest.read_text(encoding="utf-8")) != _sha(text):
                    raise ApplyError(f"{op['path']} nach dem Schreiben anders als geplant")
            elif op["action"] == "append":
                current = dest.read_text(encoding="utf-8")
                _atomic_write(dest, current.rstrip("\n") + "\n\n" + _substitute(op["content"], config_dir))
            elif op["action"] == "merge":
                current = json.loads(dest.read_text(encoding="utf-8")) if dest.is_file() else {}
                patch = json.loads(_substitute(json.dumps(op["patch"], ensure_ascii=False), config_dir))
                merged = merge_settings(current, patch)
                _atomic_write(dest, json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
            else:
                raise ApplyError(f"unbekannte Aktion {op['action']!r}")
            written.append(op["path"])
    except OSError as exc:
        raise ApplyError(f"Schreiben abgebrochen ({type(exc).__name__}: {exc}); settings.json unberührt, "
                         f"Backup: {backup}") from exc
    return {"written": written, "backup": str(backup) if backup else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description="setup-user-Plan anwenden (Spec 21)")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--config-dir", help="Pflicht; $CLAUDE_CONFIG_DIR zählt nicht")
    args = parser.parse_args(argv)
    if not args.config_dir:
        print("Abbruch: --config-dir fehlt — apply braucht das Ziel ausdrücklich", file=sys.stderr)
        return 2
    try:
        result = apply_plan(args.plan, args.config_dir)
    except ApplyError as exc:
        print(f"Abbruch: {exc}", file=sys.stderr)
        return 2
    print(f"angewendet: {len(result['written'])} Datei(en) in {Path(args.config_dir).resolve()}")
    print(f"Backup: {result['backup'] or 'keins nötig'}")
    print("Weiter: verify_install.py — bis dahin heißt die Übergabe „angewendet, ungeprüft“.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
