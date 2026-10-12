#!/usr/bin/env python3
"""Wendet einen bestätigten setup-repo-Plan an (Spec 22).

    python apply_repo.py [--repo <pfad>] [--plan .skills/cache/setup-repo/plan.md]

Wendet nur einen Block mit passendem Hash an, dessen Bestand sich seit dem Plan nicht
geändert hat und dessen versionierte Zieldateien keine uncommitteten Änderungen haben.
Unversionierte Zieldateien bekommen vorher ein Backup unter
`.skills/cache/setup-repo/backups/<JJJJMMTT-hhmmss>/`. `.claude/settings.json` wird als
Letztes geschrieben, danach läuft je Hook die Probe (`verify_stop.py --selftest`).
Schreibt in jedem Fall `.skills/cache/setup-repo/apply.md` mit Ergebnis oder
Abbruchgrund. Committet nie. Format und Mischregeln: references/plan-format.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CACHE = Path(".skills") / "cache" / "setup-repo"
BLOCK_RE = re.compile(r"^```json setup-repo-plan\n(.*?)^```", re.MULTILINE | re.DOTALL)
OWN_HOOK = ".claude/hooks/verify_stop.py"
SETTINGS = ".claude/settings.json"
ACTIONS = ("create", "append", "merge-json", "copy", "gitignore")


class ApplyError(Exception):
    """Abbruch vor dem ersten Schreiben; der Text landet in apply.md."""


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _read(path: Path) -> str | None:
    try:
        return _norm(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def _sha(text: str | None) -> str | None:
    return None if text is None else hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_hash(block) -> str:
    body = {k: v for k, v in block.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def read_block(plan_path: Path) -> dict:
    text = _read(Path(plan_path))
    if text is None:
        raise ApplyError(f"kein lesbarer Plan unter {plan_path} — zuerst plan_repo.py laufen lassen")
    blocks = BLOCK_RE.findall(text)
    if len(blocks) != 1:
        raise ApplyError(f"Plan enthält {len(blocks)} Blöcke `json setup-repo-plan`, erwartet genau einen")
    try:
        block = json.loads(blocks[0])
    except ValueError as exc:
        raise ApplyError(f"Block ist kein JSON: {exc}") from exc
    if not isinstance(block, dict) or block.get("schema") != 1:
        raise ApplyError("Block hat ein unbekanntes Schema — neu planen")
    if block.get("hash") != canonical_hash(block):
        raise ApplyError("Hash passt nicht — der Block wurde nach dem Planen geändert; neu planen, nie von Hand "
                         "anpassen")
    for op in block.get("operations", []):
        if op.get("action") not in ACTIONS or not isinstance(op.get("path"), str):
            raise ApplyError(f"unbekannte Operation: {op!r}")
        rel = op["path"]
        if rel.startswith(("/", "../")) or "/../" in rel or rel.startswith(".claude/skills/") or "\\" in rel:
            raise ApplyError(f"Pfad außerhalb des erlaubten Bereichs: {rel}")
    return block


# --- git ---------------------------------------------------------------------------

def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=30)


def _git_state(root: Path, paths: list[str]) -> tuple[set[str], set[str]]:
    """(versioniert, versioniert mit uncommitteten Änderungen) unter den Zielpfaden."""
    if shutil.which("git") is None:
        raise ApplyError("ungeprüft — kein git; ohne git lässt sich nicht prüfen, ob Zieldateien uncommittete "
                         "Änderungen haben")
    if _git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        return set(), set()
    tracked = {p for p in _git(root, "ls-files", "-z", "--", *paths).stdout.decode("utf-8").split("\0") if p}
    status = _git(root, "status", "--porcelain", "-z", "--untracked-files=no", "--", *paths).stdout.decode("utf-8")
    dirty = {entry[3:] for entry in status.split("\0") if len(entry) > 3 and entry[:2].strip()}
    return tracked, dirty & tracked


# --- Mischen und Schreiben ---------------------------------------------------------

def _is_own(hook) -> bool:
    return isinstance(hook, dict) and OWN_HOOK in str(hook.get("command", "")).replace("\\", "/")


def merge_settings(existing: dict, patch: dict) -> dict:
    result = dict(existing)
    for key, value in patch.items():
        if key == "permissions":
            perms = dict(result.get("permissions") or {})
            for kind, items in value.items():
                current = list(perms.get(kind) or [])
                perms[kind] = current + [i for i in items if i not in current]
            result["permissions"] = perms
        elif key == "hooks":
            hooks = dict(result.get("hooks") or {})
            for event, entries in value.items():
                kept = []
                for entry in hooks.get(event) or []:
                    if isinstance(entry, dict) and isinstance(entry.get("hooks"), list):
                        rest = [h for h in entry["hooks"] if not _is_own(h)]
                        if rest:
                            kept.append({**entry, "hooks": rest})
                    else:
                        kept.append(entry)
                hooks[event] = kept + json.loads(json.dumps(entries))
            result["hooks"] = hooks
        elif key == "enabledPlugins":
            result["enabledPlugins"] = {**(result.get("enabledPlugins") or {}), **value}
        else:
            result[key] = value
    return result


def _json_text(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _load_json(path: Path) -> dict:
    text = _read(path)
    if text is None:
        return {}
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError as exc:
        raise ApplyError(f"{path.name} ist kein gültiges JSON ({exc}) — von Hand reparieren, dann neu planen") from exc
    if not isinstance(data, dict):
        raise ApplyError(f"{path.name} ist kein JSON-Objekt")
    return data


def result_text(root: Path, op: dict) -> str:
    """Inhalt der Zieldatei, nachdem die Operation auf den heutigen Bestand angewendet wurde."""
    path = root / op["path"]
    current = _read(path)
    action = op["action"]
    if action in ("create", "copy"):
        return op["content"]
    if action == "append":
        return (current or "") + (op["content"] if op["content"].strip() not in (current or "") else "")
    if action == "merge-json":
        return _json_text(merge_settings(_load_json(path), op["patch"]))
    present = {line.strip() for line in (current or "").splitlines()}
    missing = [line for line in op["lines"] if line not in present]
    if not missing:
        return current or ""
    lead = "" if not current or current.endswith("\n") else "\n"
    return (current or "") + lead + "\n".join(missing) + "\n"


def _write(path: Path, text: str, *, crlf: bool = False, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\n", "\r\n") if crlf else text
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data.encode("utf-8"))
    if executable:
        tmp.chmod(0o755)
    os.replace(tmp, path)


def _timestamp_dir(root: Path) -> Path:
    base = root / CACHE / "backups"
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate, n = base / stamp, 2
    while candidate.exists():
        candidate, n = base / f"{stamp}-{n}", n + 1
    return candidate


def _probe(root: Path) -> tuple[bool, str]:
    script = root / OWN_HOOK
    try:
        proc = subprocess.run([sys.executable, str(script), "--selftest"], cwd=root, capture_output=True,
                              timeout=30, env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})
        result = json.loads(proc.stdout.decode("utf-8") or "{}")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return False, f"Probe von verify_stop.py gescheitert ({type(exc).__name__})"
    return bool(result.get("ok")), str(result.get("detail", ""))


# --- apply -------------------------------------------------------------------------

def _header(cmd: str) -> str:
    return f"<!-- skill: setup-repo | schema: 1 | generated: python skills/setup-repo/scripts/apply_repo.py{cmd} -->"


def _report(root: Path, cmd: str, status: str, details: list[str]) -> None:
    lines = [_header(cmd), "# setup-repo — apply", "", f"Ergebnis: {status}", "", *details]
    _write(root / CACHE / "apply.md", "\n".join(lines).rstrip("\n") + "\n")


def apply_plan(repo_root, plan_path) -> dict:
    root = Path(repo_root).resolve()
    plan_path = Path(plan_path)
    cmd = "" if plan_path.resolve() == (root / CACHE / "plan.md").resolve() else f" --plan {plan_path}"
    try:
        block = read_block(plan_path)
        ops = sorted(block["operations"], key=lambda op: op["path"] == SETTINGS)
        paths = [op["path"] for op in ops]
        for rel in paths:
            if _sha(_read(root / rel)) != block["base"].get(rel):
                raise ApplyError(f"Bestand geändert seit dem Plan: {rel} — neu planen")
        tracked, dirty = _git_state(root, paths)
        if dirty:
            raise ApplyError("uncommittete Änderungen in versionierten Zieldateien: " + ", ".join(sorted(dirty))
                             + " — erst committen oder verwerfen, dann neu planen")
        for op in ops:
            if op["action"] == "create" and (root / op["path"]).exists():
                raise ApplyError(f"{op['path']} existiert schon, der Plan wollte sie anlegen — neu planen")
        texts = {op["path"]: result_text(root, op) for op in ops}
    except ApplyError as exc:
        _report(root, cmd, f"abgebrochen — {exc}", ["Keine Datei außerhalb von `.skills/cache/setup-repo/` wurde "
                                                    "berührt."])
        return {"ok": False, "status": f"abgebrochen — {exc}", "written": [], "backups": [], "probes": []}

    backups: list[str] = []
    backup_dir = None
    written: list[str] = []
    for op in ops:
        target = root / op["path"]
        if target.exists() and op["path"] not in tracked:
            backup_dir = backup_dir or _timestamp_dir(root)
            dest = backup_dir / op["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dest)
            backups.append(dest.relative_to(root).as_posix())
        current_raw = target.read_bytes() if target.exists() else b""
        if _read(target) == texts[op["path"]]:
            continue
        _write(target, texts[op["path"]], crlf=op["action"] == "append" and b"\r\n" in current_raw,
               executable=op["action"] == "copy")
        written.append(op["path"])

    probes: list[tuple[bool, str]] = []
    if (root / OWN_HOOK).is_file() and any(op["path"] == OWN_HOOK for op in ops):
        probes.append(_probe(root))
    failed = [detail for ok, detail in probes if not ok]
    status = f"angewendet, ungeprüft — {'; '.join(failed)}" if failed else "angewendet und geprüft"
    details = ["## Geschrieben", "", *([f"- `{p}`" for p in written] or ["- nichts — Bestand entsprach dem Plan"]), ""]
    if backups:
        details += ["## Backups", "", *[f"- `{b}`" for b in backups], ""]
    if probes:
        details += ["## Proben", "", *[f"- verify_stop.py --selftest: {'ok' if ok else 'gescheitert'} — {d}"
                                         for ok, d in probes], ""]
    details += ["## Nächste Schritte", "",
                "- Nicht committet — prüfen und committen ist Sache des Nutzers.",
                "- Settings, Hooks und CLAUDE.md wirken ab der nächsten Session."]
    _report(root, cmd, status, details)
    return {"ok": True, "status": status, "written": written, "backups": backups,
            "probes": [d for _, d in probes]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".")
    parser.add_argument("--plan")
    args = parser.parse_args(argv)
    root = Path(args.repo).resolve()
    plan = Path(args.plan) if args.plan else root / CACHE / "plan.md"
    result = apply_plan(root, plan)
    print(f"Repo: {root}")
    print(result["status"])
    for path in result["written"]:
        print(f"  geschrieben: {path}")
    print(f"Bericht: {root / CACHE / 'apply.md'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
