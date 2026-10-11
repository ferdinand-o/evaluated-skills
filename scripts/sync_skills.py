#!/usr/bin/env python3
"""Projekt-Installation unter `.claude/skills/` spiegeln und superpowers-Verweise zählen.

Tier 1: nur Stdlib. Repo-Werkzeug aus Spec 20 (plugin-split), keine Skill.

    python scripts/sync_skills.py            # spiegelt PROJECT_SKILLS nach .claude/skills/
    python scripts/sync_skills.py --check    # schreibt nichts, Exit 1 bei Abweichung
    python scripts/sync_skills.py --report   # superpowers:-Verweise in Descriptions aktiver Plugins

`skills/<name>/` ist das Original. Die Kopie unter `.claude/skills/<name>/` lädt eine
Cloud-Session als Projekt-Skill, weil Plugins dort nicht laden. Gespiegelt heißt: neue
und geänderte Dateien werden kopiert, in der Kopie überzählige gelöscht, `__pycache__/`
und `*.pyc` ignoriert. Eine installierte Skill, die nicht in der Tabelle steht, gilt
als überzählig.

`--report` zählt für die Abschaltbedingung (b) aus Spec 20 die Fundstellen von
`superpowers:` in den Descriptions der Skills, die in der `skills`-Liste eines Plugins
mit `defaultEnabled: true` stehen. Ein Manifest, das kein JSON ist, oder ein
`excluded.json`, das kein Objekt ist, endet mit Exit 2 — ein Bericht, der nicht prüfen
konnte, meldet nie null Fundstellen.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

# Skills für die Arbeit an diesem Repo (Spec 20, Zuschnitt). Neue Zeile hier, dann
# `python scripts/sync_skills.py`.
PROJECT_SKILLS = [
    "architecture-map",
    "debug-ledger",
    "dev-report",
    "feature-spec",
    "handoff",
    "impl-plan",
    "review-context",
    "skill-forge",
    "subagent-dev",
    "testing-strategy",
]

IGNORED_DIRS = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc"}
REPO_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(Exception):
    """Manifest oder excluded.json unlesbar — der Bericht kann nicht prüfen."""


def _files(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if not path.is_file() or IGNORED_DIRS & set(rel.parts) or path.suffix in IGNORED_SUFFIXES:
            continue
        out[rel.as_posix()] = path
    return out


def sync(repo_root, check=False):
    """Spiegelt PROJECT_SKILLS nach `.claude/skills/`.

    Gibt eine sortierte Liste `(status, pfad)` zurück, Pfad relativ zu `.claude/skills/`.
    Mit `check=True` wird nichts geschrieben; die Liste sind die Befunde. Ohne `check`
    ist sie, was geändert wurde.
    """
    repo_root = Path(repo_root)
    installed = repo_root / ".claude" / "skills"
    results: list[tuple[str, str]] = []

    for name in PROJECT_SKILLS:
        src_files = _files(repo_root / "skills" / name)
        dst_root = installed / name
        dst_files = _files(dst_root)
        for rel in sorted(set(src_files) | set(dst_files)):
            src, dst = src_files.get(rel), dst_files.get(rel)
            if src is None:
                status = "überzählig"
            elif dst is None:
                status = "fehlend"
            elif src.read_bytes() != dst.read_bytes():
                status = "abweichend"
            else:
                continue
            results.append((status, f"{name}/{rel}"))
            if check:
                continue
            target = dst_root / rel
            if src is None:
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, target)
        if not check and dst_root.is_dir():
            _prune_empty_dirs(dst_root)

    if installed.is_dir():
        for extra in sorted(p for p in installed.iterdir() if p.is_dir() and p.name not in PROJECT_SKILLS):
            for rel in sorted(_files(extra)):
                results.append(("überzählig", f"{extra.name}/{rel}"))
            if not check:
                shutil.rmtree(extra)

    return sorted(results, key=lambda r: r[1])


def _prune_empty_dirs(root: Path) -> None:
    for path in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(path.iterdir()):
            path.rmdir()


def _load_json(path: Path, what: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"{what} unlesbar: {path} ({exc})") from exc


def _description(skill_md: Path) -> str:
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    return ""


def superpowers_report(repo_root):
    """`{plugin: {skill: anzahl}}` für Plugins mit `defaultEnabled: true` (Default true).

    Ausgeschlossene Skills zählen nicht, auch wenn sie in einer Liste stehen. Skills ohne
    Fundstelle fehlen im Ergebnis; ein leeres Dict heißt „keine Fundstelle".
    """
    repo_root = Path(repo_root)
    manifest = _load_json(repo_root / ".claude-plugin" / "marketplace.json", "Manifest")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("plugins"), list):
        raise ConfigError("Manifest ohne Liste `plugins`")
    excluded_path = repo_root / ".claude-plugin" / "excluded.json"
    excluded = _load_json(excluded_path, "excluded.json") if excluded_path.is_file() else {}
    if not isinstance(excluded, dict):
        raise ConfigError("excluded.json ist kein JSON-Objekt")

    report: dict[str, dict[str, int]] = {}
    for entry in manifest["plugins"]:
        if not isinstance(entry, dict) or entry.get("defaultEnabled", True) is False:
            continue
        for skill_path in entry.get("skills") or []:
            name = Path(skill_path).name
            if name in excluded:
                continue
            skill_md = repo_root / "skills" / name / "SKILL.md"
            count = _description(skill_md).count("superpowers:") if skill_md.is_file() else 0
            if count:
                report.setdefault(entry.get("name", "?"), {})[name] = count
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="nichts schreiben, Exit 1 bei Abweichung")
    mode.add_argument("--report", action="store_true", help="superpowers:-Verweise in aktiven Plugins zählen")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT, help="Repo-Wurzel (Default: Elternordner von scripts/)")
    args = parser.parse_args(argv)

    if args.report:
        try:
            report = superpowers_report(args.repo)
        except ConfigError as exc:
            print(f"ungeprüft — {exc}", file=sys.stderr)
            return 2
        total = sum(sum(skills.values()) for skills in report.values())
        for plugin, skills in sorted(report.items()):
            for name, count in sorted(skills.items()):
                print(f"{plugin}: {name} {count}")
        print(f"superpowers:-Verweise in Descriptions aktiver Plugins: {total}")
        return 0

    results = sync(args.repo, check=args.check)
    for status, path in results:
        print(f"{status}: .claude/skills/{path}")
    if args.check:
        print("keine Abweichung" if not results else f"{len(results)} Abweichung(en) — python scripts/sync_skills.py")
        return 1 if results else 0
    print(f"{len(results)} Datei(en) gespiegelt" if results else "nichts zu tun")
    return 0


if __name__ == "__main__":
    sys.exit(main())
