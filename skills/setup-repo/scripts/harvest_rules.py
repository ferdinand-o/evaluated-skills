#!/usr/bin/env python3
"""Sammelt Regelkandidaten mit Quelle aus einem Repo (setup-repo, Spec 22).

    python harvest_rules.py [--repo <pfad>] [--detect <detect.json>] [--out <pfad>]

Liest `detect.json` (von detect_repo.py), die Konfigurationen der erkannten Werkzeuge,
`CONTRIBUTING*` und die Betreffs der letzten 50 Commits. Schreibt
`.skills/cache/setup-repo/candidates.json` mit `_meta`. Eine Klasse vergibt dieses Skript
nicht — `checked_by` ist nur der Beleg, welches Werkzeug den Kandidaten prüft. Quellen
und Klassen: references/rules-harvest.md.
"""
from __future__ import annotations

import argparse
import configparser
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

META = {"skill": "setup-repo", "schema": 1, "generated": "python skills/setup-repo/scripts/harvest_rules.py"}
CACHE = Path(".skills") / "cache" / "setup-repo"
MAX_CONTRIBUTING = 20
COMMITS = 50
CONVENTIONAL_RE = re.compile(r"^[a-z]+(\([^)]*\))?!?: \S")
BULLET_RE = re.compile(r"^[-*]\s+(\S.*)$")
EDITOR_KEYS = ("indent_style", "indent_size", "max_line_length")
PRETTIER_KEYS = ("printWidth", "semi", "singleQuote")


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    return str(value)


def _toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _json_loose(path: Path):
    """JSON mit //- und /* */-Kommentaren, wie tsconfig.json sie erlaubt."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r'(?m)^\s*//.*$|(?<=[,{\[\s])//[^"\n]*$', "", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        return json.loads(text)
    except ValueError:
        return None


class _Collector:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, text: str, source: str, checked_by: str | None) -> None:
        if any(c["text"] == text and c["source"] == source for c in self.items):
            return
        self.items.append({"id": f"c{len(self.items) + 1}", "text": text, "source": source,
                           "checked_by": checked_by})

    def keys(self, table: dict, keys: tuple[str, ...], source: str, tool: str) -> None:
        for key in keys:
            if isinstance(table, dict) and key in table:
                self.add(f"`{key} = {_toml_value(table[key])}`", source, tool)


def _ruff(root: Path, config: str, out: _Collector) -> None:
    data = _toml(root / config)
    table = data.get("tool", {}).get("ruff", {}) if config == "pyproject.toml" else data
    section = "pyproject.toml [tool.ruff]" if config == "pyproject.toml" else config
    out.keys(table, ("line-length", "target-version", "select"), section, "ruff")
    lint = table.get("lint") if isinstance(table, dict) else None
    out.keys(lint or {}, ("select",), section, "ruff")


def _ini(path: Path, section: str) -> dict:
    parser = configparser.ConfigParser()
    try:
        parser.read_string(path.read_text(encoding="utf-8"))
    except (OSError, configparser.Error):
        return {}
    return dict(parser[section]) if parser.has_section(section) else {}


def _editorconfig(path: Path, out: _Collector) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    section = None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line
            continue
        if section and "=" in line:
            key, value = (p.strip() for p in line.split("=", 1))
            if key in EDITOR_KEYS:
                out.add(f"`{section} {key} = {value}`", ".editorconfig", "editorconfig")


def _tools(root: Path, detect: dict, out: _Collector) -> None:
    pyproject = _toml(root / "pyproject.toml")
    tool = pyproject.get("tool", {}) if isinstance(pyproject.get("tool"), dict) else {}
    for entry in detect.get("linters", []):
        name, config = entry.get("tool"), entry.get("config")
        if name == "ruff":
            _ruff(root, config, out)
        elif name == "black" and config == "pyproject.toml":
            out.keys(tool.get("black", {}), ("line-length",), "pyproject.toml [tool.black]", "black")
        elif name == "mypy" and config == "pyproject.toml":
            out.keys(tool.get("mypy", {}), ("strict",), "pyproject.toml [tool.mypy]", "mypy")
        elif name == "mypy":
            out.keys(_ini(root / config, "mypy"), ("strict",), config, "mypy")
        elif name == "flake8":
            out.keys(_ini(root / config, "flake8"), ("max-line-length",), f"{config} [flake8]", "flake8")
        elif name == "editorconfig":
            _editorconfig(root / config, out)
        elif name == "prettier":
            data = _json_loose(root / config)
            if config == "package.json":
                data = data.get("prettier") if isinstance(data, dict) else None
            if isinstance(data, dict):
                out.keys(data, PRETTIER_KEYS, config, "prettier")
            else:
                out.add("Prettier-Konfiguration gilt", config, "prettier")
        elif name == "tsc":
            data = _json_loose(root / config)
            options = data.get("compilerOptions") if isinstance(data, dict) else None
            out.keys(options or {}, ("strict",), f"{config} compilerOptions", "tsc")
        elif name == "eslint":
            out.add("ESLint-Konfiguration gilt", config, "eslint")
    pytest_opts = (tool.get("pytest") or {}).get("ini_options") if isinstance(tool.get("pytest"), dict) else None
    out.keys(pytest_opts or {}, ("testpaths",), "pyproject.toml [tool.pytest.ini_options]", "pytest")


def _contributing(root: Path, out: _Collector) -> None:
    files = sorted(p for p in root.glob("CONTRIBUTING*") if p.is_file())
    files += sorted(p for p in (root / ".github").glob("CONTRIBUTING*") if p.is_file()) if (root / ".github").is_dir() else []
    count = 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = BULLET_RE.match(line)
            if m and count < MAX_CONTRIBUTING:
                out.add(m.group(1).strip(), rel, None)
                count += 1


def _commits(root: Path, out: _Collector) -> None:
    try:
        proc = subprocess.run(["git", "log", f"-{COMMITS}", "--format=%s"], cwd=root, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=20)
    except (OSError, subprocess.SubprocessError):
        return
    if proc.returncode != 0:
        return
    subjects = [s for s in proc.stdout.splitlines() if s.strip()]
    hits = sum(1 for s in subjects if CONVENTIONAL_RE.match(s))
    if len(subjects) >= 5 and hits / len(subjects) >= 0.6:
        out.add("Commit-Betreffs im Format `typ(bereich): beschreibung`", f"git log ({hits} von {len(subjects)} Betreffs)",
                None)


def harvest(repo_root, detect) -> list[dict]:
    """Kandidaten in der Reihenfolge von references/rules-harvest.md, IDs c1, c2, …"""
    root = Path(repo_root)
    out = _Collector()
    _tools(root, detect if isinstance(detect, dict) else {}, out)
    _contributing(root, out)
    _commits(root, out)
    return out.items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".")
    parser.add_argument("--detect")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    root = Path(args.repo).resolve()
    detect_path = Path(args.detect) if args.detect else root / CACHE / "detect.json"
    try:
        detect = json.loads(detect_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(f"kein lesbares {detect_path} — zuerst detect_repo.py laufen lassen", file=sys.stderr)
        return 2
    candidates = harvest(root, detect)
    out = Path(args.out) if args.out else root / CACHE / "candidates.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"_meta": META, "candidates": candidates}, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"{len(candidates)} Kandidat(en), Klassen trägt Claude über plan_repo.py --classes ein")
    for c in candidates:
        print(f"  {c['id']}: {c['text']} · {c['source']}" + (f" · geprüft von {c['checked_by']}" if c["checked_by"] else ""))
    print(f"geschrieben: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
