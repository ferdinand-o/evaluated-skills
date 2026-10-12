#!/usr/bin/env python3
"""Erkennt Stack, Runner, Tests, CLAUDE-Dateien und Plugin-IDs eines Repos (setup-repo, Spec 22). Tier 1.

    python detect_repo.py [--repo <pfad>] [--config-dir <pfad>] [--out <pfad>]

Liest nur; schreibt `.skills/cache/setup-repo/detect.json` mit `_meta`. Alle Pfade im
Ergebnis sind relativ zur Repo-Wurzel und nutzen `/`. Plugin-IDs kommen aus
`<config-dir>/plugins/installed_plugins.json` (Feld `installPath`) und
`<config-dir>/plugins/synced/`; ohne Code aus setup-user. Config-Verzeichnis:
`--config-dir`, sonst `$CLAUDE_CONFIG_DIR`, sonst `~/.claude`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

META = {"skill": "setup-repo", "schema": 1, "generated": "python skills/setup-repo/scripts/detect_repo.py"}
CACHE = Path(".skills") / "cache" / "setup-repo"
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".skills", "dist", "build",
             ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", "target", "__history"}
MAX_FILES = 20000
LANG_BY_SUFFIX = {".py": "python", ".ts": "typescript", ".tsx": "typescript", ".js": "javascript",
                  ".jsx": "javascript", ".mjs": "javascript", ".pas": "delphi", ".dpr": "delphi",
                  ".dproj": "delphi"}
FRONTENDS = [("next", "next"), ("@angular/core", "angular"), ("react", "react"), ("vue", "vue"),
             ("svelte", "svelte"), ("solid-js", "solid")]
TEST_DIRS = {"tests", "test", "__tests__", "spec"}
TEST_FILE_RE = re.compile(r"(^test_.*\.py$|_test\.py$|\.(test|spec)\.[jt]sx?$|Tests?\.dpr$)")
MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)\s*:(?![=:])")
JUST_RECIPE_RE = re.compile(r"^@?([A-Za-z0-9][A-Za-z0-9_-]*)(?:\s+[^:=]*)?:(?!=)")
CLAUDE_FILES = ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md")
CI_FILES = (".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile", ".circleci/config.yml")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _walk(root: Path) -> list[str]:
    files: list[str] = []
    for current, dirs, names in os.walk(root):
        rel_dir = Path(current).relative_to(root).as_posix()
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS
                         and not (rel_dir == ".claude" and d in ("skills", "worktrees")))
        for name in sorted(names):
            files.append(name if rel_dir == "." else f"{rel_dir}/{name}")
            if len(files) >= MAX_FILES:
                return files
    return files


def _make_targets(text: str) -> list[str]:
    targets = []
    for line in text.splitlines():
        m = MAKE_TARGET_RE.match(line)
        if m and not m.group(1).startswith(".") and m.group(1) not in targets:
            targets.append(m.group(1))
    return sorted(targets)


def _just_recipes(text: str) -> list[str]:
    recipes = []
    for line in text.splitlines():
        if line[:1].isspace() or line.startswith(("#", "set ", "export ", "alias ", "import ")):
            continue
        m = JUST_RECIPE_RE.match(line)
        if m and m.group(1) not in recipes:
            recipes.append(m.group(1))
    return sorted(recipes)


def _pyproject_runners(pyproject: dict) -> dict[str, list[str]]:
    tool = pyproject.get("tool", {}) if isinstance(pyproject.get("tool"), dict) else {}
    found = {
        "poe": (tool.get("poe") or {}).get("tasks"),
        "pdm": (tool.get("pdm") or {}).get("scripts"),
        "hatch": (((tool.get("hatch") or {}).get("envs") or {}).get("default") or {}).get("scripts"),
    }
    return {k: sorted(v) for k, v in found.items() if isinstance(v, dict) and v}


def _linters(root: Path, files: set[str], pyproject: dict, package: dict) -> list[dict]:
    tool = pyproject.get("tool", {}) if isinstance(pyproject.get("tool"), dict) else {}
    found: list[dict] = []

    def add(name: str, config: str) -> None:
        entry = {"tool": name, "config": config}
        if entry not in found:
            found.append(entry)

    for name in ("ruff", "black", "mypy"):
        if name in tool:
            add(name, "pyproject.toml")
    for cfg, name in (("ruff.toml", "ruff"), (".ruff.toml", "ruff"), ("mypy.ini", "mypy"), (".flake8", "flake8"),
                      ("tsconfig.json", "tsc"), (".editorconfig", "editorconfig")):
        if cfg in files:
            add(name, cfg)
    if "setup.cfg" in files and "[flake8]" in _read(root / "setup.cfg"):
        add("flake8", "setup.cfg")
    for rel in sorted(files):
        if "/" in rel:
            continue
        if rel.startswith(".eslintrc") or rel.startswith("eslint.config."):
            add("eslint", rel)
        if rel.startswith(".prettierrc") or rel.startswith("prettier.config."):
            add("prettier", rel)
    if isinstance(package.get("eslintConfig"), dict):
        add("eslint", "package.json")
    if "prettier" in package:
        add("prettier", "package.json")
    return found


def _plugin_skills(install: Path, name: str) -> list[str]:
    for manifest in (install / ".claude-plugin" / "marketplace.json", install / ".claude-plugin" / "plugin.json"):
        data = _json(manifest)
        if not isinstance(data, dict):
            continue
        entries = data.get("plugins") if manifest.name == "marketplace.json" else [data]
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, dict) and entry.get("name") == name and isinstance(entry.get("skills"), list):
                return sorted({Path(str(s)).name for s in entry["skills"]})
    skills_dir = install / "skills"
    if skills_dir.is_dir():
        return sorted(p.parent.name for p in skills_dir.glob("*/SKILL.md"))
    return []


def _plugins(config_dir: Path) -> list[dict]:
    plugins: dict[str, dict] = {}
    data = _json(config_dir / "plugins" / "installed_plugins.json")
    entries = data.get("plugins") if isinstance(data, dict) else None
    for plugin_id, value in sorted(entries.items()) if isinstance(entries, dict) else []:
        if "@" not in plugin_id:
            continue
        name, marketplace = plugin_id.split("@", 1)
        installs = value if isinstance(value, list) else [value]
        path = next((i.get("installPath") for i in installs if isinstance(i, dict) and i.get("installPath")), None)
        skills = _plugin_skills(Path(path), name) if path else []
        plugins[plugin_id] = {"id": plugin_id, "name": name, "marketplace": marketplace, "skills": skills}
    synced = config_dir / "plugins" / "synced"
    if synced.is_dir():
        for folder in sorted(p for p in synced.iterdir() if p.is_dir()):
            manifest = _json(folder / ".claude-plugin" / "plugin.json")
            if not isinstance(manifest, dict):
                continue
            name = str(manifest.get("name") or folder.name)
            plugin_id = f"{name}@synced"
            plugins.setdefault(plugin_id, {"id": plugin_id, "name": name, "marketplace": "synced",
                                           "skills": _plugin_skills(folder, name)})
    return [plugins[k] for k in sorted(plugins)]


def detect(repo_root, config_dir) -> dict:
    """Was im Repo liegt — nur lesend, Pfade relativ zur Wurzel."""
    root = Path(repo_root)
    files = _walk(root)
    fileset = set(files)
    pyproject = _toml(root / "pyproject.toml") if "pyproject.toml" in fileset else {}
    package = _json(root / "package.json") if "package.json" in fileset else None
    package = package if isinstance(package, dict) else {}

    languages = {LANG_BY_SUFFIX[Path(f).suffix] for f in files if Path(f).suffix in LANG_BY_SUFFIX}
    if "typescript" in languages:
        languages.discard("javascript")

    deps = {**(package.get("dependencies") or {}), **(package.get("devDependencies") or {})}
    frontend = next((label for dep, label in FRONTENDS if dep in deps), None)

    scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
    manager = next((m for lock, m in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"))
                    if lock in fileset), "npm")
    justfile = next((f for f in ("justfile", "Justfile", ".justfile") if f in fileset), None)
    runners = {
        "make": _make_targets(_read(root / "Makefile")) if "Makefile" in fileset else [],
        "just": _just_recipes(_read(root / justfile)) if justfile else [],
        "npm": {k: str(v) for k, v in sorted(scripts.items())},
        "package_manager": manager,
        "pyproject": _pyproject_runners(pyproject),
    }

    tests = any(TEST_FILE_RE.search(Path(f).name) or set(Path(f).parts[:-1]) & TEST_DIRS for f in files)
    tool = pyproject.get("tool", {}) if isinstance(pyproject.get("tool"), dict) else {}
    ci = sorted(f for f in files if f.startswith(".github/workflows/") and f.endswith((".yml", ".yaml")))
    ci += [f for f in CI_FILES if f in fileset]
    skills_dir = root / ".claude" / "skills"
    project_skills = sorted(p.parent.name for p in skills_dir.glob("*/SKILL.md")) if skills_dir.is_dir() else []

    return {
        "languages": sorted(languages),
        "frontend": frontend,
        "runners": runners,
        "pytest_config": "ini_options" in (tool.get("pytest") or {}) or "pytest.ini" in fileset,
        "tests": bool(tests),
        "linters": _linters(root, fileset, pyproject, package),
        "ci": ci,
        "claude_files": sorted(f for f in CLAUDE_FILES if (root / f).is_file()),
        "agents_md": (root / "AGENTS.md").is_file(),
        "project_skills": project_skills,
        "delphi_projects": sorted(f for f in files if f.endswith(".dproj")),
        "plugins": _plugins(Path(config_dir)),
    }


def _repo_root(arg: str | None) -> Path:
    if arg:
        return Path(arg).resolve()
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd().resolve()


def _config_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env) if env else Path(os.path.expanduser("~")) / ".claude"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo")
    parser.add_argument("--config-dir")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    root = _repo_root(args.repo)
    result = detect(root, _config_dir(args.config_dir))
    out = Path(args.out) if args.out else root / CACHE / "detect.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"_meta": META, **result}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    langs = ", ".join(result["languages"]) or "keine erkannt"
    print(f"Repo: {root}")
    print(f"Sprachen: {langs}; Frontend: {result['frontend'] or 'keins'}; Tests: {'ja' if result['tests'] else 'nein'}")
    print(f"Plugins gefunden: {len(result['plugins'])}")
    print(f"geschrieben: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
