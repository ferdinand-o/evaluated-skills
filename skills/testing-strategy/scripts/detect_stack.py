#!/usr/bin/env python3
"""Repo-Klassifikation für testing-strategy. Tier 1: nur Stdlib (+ git-CLI).

Spec 05 deklariert diesen Skript-Kopf ursprünglich als Tier 2 — geprüft und
verworfen (Spec 00 §3 macht Tier 1 zum Standard, jede Stufe darüber ist zu
begründen). Was gebraucht wird, geht mit Stdlib: `package.json`/`manifest.json`
sind JSON, `pyproject.toml` muss hier nur nach Substrings (Abhängigkeitsnamen,
`[project.scripts]`) durchsucht werden, keine echte TOML-Semantik nötig — das
vermeidet zusätzlich eine Abhängigkeit von `tomllib`, das erst ab Python 3.11
in der Stdlib liegt. git-Aufrufe über `subprocess` gelten hier wie bei
`skills/dev-report/scripts/collect.py` als Tier 1 (etablierter Präzedenzfall).

**Fix-Runde (Review):** „Nur Substrings" hieß ursprünglich: der komplette
Rohtext, Kommentare eingeschlossen. Ein Kommentar wie `# früher haben wir
django evaluiert` reichte damit, ein reines CLI-Tool als `rest-api` zu
klassifizieren. Das widerlegt nicht die Tier-1-Entscheidung, sondern verlangt
eine schärfere Suche: `_strip_toml_line_comments`/`_extract_toml_dependency_text`
entfernen Kommentare zeilenweise (ohne `#` in Anführungszeichen zu werten) und
beschränken die Suche auf die Abschnitte, in denen Abhängigkeiten laut
TOML-Struktur überhaupt stehen können (`dependencies = [...]` im
`[project]`-Wurzelabschnitt, sowie `[project.optional-dependencies]` und
`[tool.poetry.(dev-)dependencies]`-Tabellen) — Freitextfelder wie
`description` fließen nie ein. `requirements.txt` und `pom.xml`/`build.gradle`
bekommen dieselbe Kommentar-Bereinigung, jeweils mit der für ihr Format
passenden Kommentarsyntax (`#` bzw. `<!-- -->`). Immer noch kein echter
Parser — genug, um einen Kommentar nicht mit einer Abhängigkeit zu verwechseln.

R5 (Auftrag): Es gibt keine Veraltungsregel für den Cache unter
`.skills/cache/detect_stack.json`. Jeder explizite Aufruf klassifiziert neu und
überschreibt einen etwaigen alten Stand vollständig — der Cache ist reine
Ephemera (Spec 00 §1) und wird von diesem Skript nie gelesen, nur geschrieben.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SCHEMA_VERSION = 1
CACHE_PATH = Path(".skills") / "cache" / "detect_stack.json"

IGNORE_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    "env", "dist", "build", ".next", ".nuxt", "target", ".idea", ".vscode",
    "coverage", ".pytest_cache", ".mypy_cache", ".skills", ".claude",
    "vendor", ".tox", "out", "site-packages", "egg-info",
}

MAX_WALK_FILES = 5000  # Sicherheitsventil gegen sehr große Repos

TEST_FILE_RE = re.compile(
    r"(^|/)(tests?|__tests__)/"
    r"|(^|/)(test_[^/]+\.py|[^/]+_test\.py)$"
    r"|(^|/)[^/]+\.(test|spec)\.[jt]sx?$"
    r"|(^|/)[^/]+Test\.java$"
)

ROUTER_ENTRY_FILES = (
    "app.py", "main.py", "asgi.py", "wsgi.py", "server.js", "server.ts",
    "index.js", "index.ts", "app.js", "app.ts", "Application.java",
)
ROUTER_PATTERNS = (
    re.compile(r"@app\.(get|post|put|delete|patch)\("),
    re.compile(r"@router\.(get|post|put|delete|patch)\("),
    re.compile(r"\bapp\.(get|post|put|delete|patch)\("),
    re.compile(r"\brouter\.(get|post|put|delete|patch)\("),
    re.compile(r"@RestController\b"),
    re.compile(r"@RequestMapping\b"),
)

OPENAPI_NAMES = ("openapi.yaml", "openapi.yml", "swagger.yaml", "swagger.yml", "swagger.json", "openapi.json")

REST_API_DEP_NAMES = (
    "flask", "fastapi", "django", "starlette", "express", "koa", "fastify",
    "spring-boot-starter-web", "spring-web",
)
CLI_DEP_NAMES = ("click", "typer", "commander", "yargs", "oclif")
FRONTEND_DEP_NAMES = ("react", "vue", "svelte", "@angular/core", "solid-js", "preact")
JS_TEST_RUNNERS = ("vitest", "jest", "mocha", "playwright", "@playwright/test", "cypress")

# "keine Tests" ist eine notwendige, nie eine hinreichende Bedingung für
# Legacy-Verdacht (Review-Fund: sonst gilt jedes frische, gerade erst
# begonnene Projekt als Legacy). Hinreichend wird sie erst zusammen mit einem
# Alters- oder Umfangssignal, dessen Schwellen bewusst über das hinausgehen,
# was ein Projekt in seinen ersten Commits ansammelt.
LEGACY_FILE_COUNT_THRESHOLD = 20
LEGACY_COMMIT_COUNT_THRESHOLD = 25
LEGACY_AGE_DAYS_THRESHOLD = 3 * 365

# TOML-Kommentare und Abhängigkeits-Abschnitte (siehe Skriptkopf, Fix-Runde).
_TOML_SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")
_TOML_DEP_TABLE_RE = re.compile(
    r"^(project\.optional-dependencies(\.[\w-]+)?"
    r"|tool\.poetry\.(dev-)?dependencies"
    r"|tool\.poetry\.group\.[\w-]+\.dependencies)$"
)
_TOML_SCRIPTS_SECTION_RE = re.compile(r"^(project\.scripts|tool\.poetry\.scripts)$")


class DetectError(RuntimeError):
    """Klassifikation ist an einem harten Fehler gescheitert (z. B. Pfad ungültig)."""


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _scan_locations(repo: Path) -> list[tuple[str, Path]]:
    """Repo-Wurzel plus direkte Unterordner (Tiefe 1) — reicht für die in der
    Spec genannten Monorepo-Fälle, ohne unbeschränkt zu rekursieren."""
    locations = [(".", repo)]
    if repo.is_dir():
        for child in sorted(repo.iterdir()):
            if child.is_dir() and child.name not in IGNORE_DIRS and not child.name.startswith("."):
                locations.append((f"{child.name}/", child))
    return locations


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _read_text(path: Path, limit: int = 100_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _bump(scores: dict[str, int], signals: dict[str, list[str]], kind: str, points: int, why: str) -> None:
    scores[kind] = scores.get(kind, 0) + points
    signals.setdefault(kind, []).append(why)


def _strip_toml_line_comments(text: str) -> str:
    """Entfernt `#`-Kommentare zeilenweise, ohne ein `#` innerhalb von
    Anführungszeichen als Kommentarbeginn zu werten. Kein echter TOML-Parser
    (Tier 1, siehe Skriptkopf) — aber genug, um einen Kommentar wie `# früher
    haben wir django evaluiert` nicht als Abhängigkeit misszuverstehen."""
    out_lines = []
    for line in text.splitlines():
        chars: list[str] = []
        quote: str | None = None
        for ch in line:
            if quote:
                chars.append(ch)
                if ch == quote:
                    quote = None
            elif ch in ("'", '"'):
                quote = ch
                chars.append(ch)
            elif ch == "#":
                break
            else:
                chars.append(ch)
        out_lines.append("".join(chars))
    return "\n".join(out_lines)


def _extract_toml_dependency_text(text: str) -> str:
    """Nur der Text, in dem Abhängigkeitsnamen laut TOML-Struktur überhaupt
    stehen können: die `dependencies = [...]`-Zeile(n) im
    `[project]`-Wurzelabschnitt, plus jede Zeile innerhalb einer bekannten
    Abhängigkeits-Tabelle (`[project.optional-dependencies]`,
    `[tool.poetry.dependencies]`, …). Freitextfelder wie `description` und
    Kommentare fließen nie ein — siehe Skriptkopf, Fix-Runde."""
    clean = _strip_toml_line_comments(text)
    relevant: list[str] = []
    current_section = ""
    in_dep_array = False

    for raw_line in clean.splitlines():
        header = _TOML_SECTION_RE.match(raw_line.strip())
        if header:
            current_section = header.group(1)
            in_dep_array = False
            continue

        if in_dep_array:
            relevant.append(raw_line)
            if raw_line.count("]") >= raw_line.count("["):
                in_dep_array = False
            continue

        stripped_line = raw_line.strip()
        if current_section in ("project", "") and re.match(r"^dependencies\s*=", stripped_line):
            relevant.append(raw_line)
            in_dep_array = raw_line.count("[") > raw_line.count("]")
            continue

        if _TOML_DEP_TABLE_RE.match(current_section):
            relevant.append(raw_line)

    return "\n".join(relevant)


def _has_toml_scripts_section(text: str) -> bool:
    """`[project.scripts]`/`[tool.poetry.scripts]` nur als echte Abschnitts-
    Kopfzeile, nicht als Substring irgendwo im Text (auch nicht in einem
    Kommentar wie `# TODO: add [project.scripts] someday`)."""
    clean = _strip_toml_line_comments(text)
    return any(
        _TOML_SCRIPTS_SECTION_RE.match(_TOML_SECTION_RE.match(line.strip()).group(1))
        for line in clean.splitlines()
        if _TOML_SECTION_RE.match(line.strip())
    )


def _strip_hash_comments(text: str) -> str:
    """Zeilenweises `#`-Kommentar-Entfernen für `requirements.txt` — dort
    gibt es keine Anführungszeichen-Fälle wie in TOML, ein einfacher Split
    reicht."""
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _strip_xml_comments(text: str) -> str:
    """`<!-- ... -->`-Kommentare aus pom.xml/build.gradle entfernen, damit ein
    Kommentar wie `<!-- frueher spring-web erwogen -->` keine Abhängigkeit
    vortäuscht."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


# ---------------------------------------------------------------------------
# Signal-Scanner, einer je Manifest-Art
# ---------------------------------------------------------------------------


def _scan_extension(loc_label: str, loc_path: Path, scores: dict, signals: dict) -> None:
    manifest = loc_path / "manifest.json"
    if not manifest.is_file():
        return
    data = _read_json(manifest)
    if data is None or "manifest_version" not in data:
        # PWA-Web-App-Manifeste heißen auch `manifest.json`, haben aber kein
        # `manifest_version` — ohne diese Prüfung gälte jede PWA als Extension.
        return
    extra = [key for key in ("background", "content_scripts", "action", "browser_action") if key in data]
    detail = f" ({', '.join(extra)})" if extra else ""
    _bump(scores, signals, "chrome-extension", 3,
          f"manifest.json mit manifest_version={data.get('manifest_version')} in {loc_label}{detail}")


def _scan_package_json(loc_label: str, loc_path: Path, scores: dict, signals: dict, languages: list[dict]) -> None:
    pkg = loc_path / "package.json"
    if not pkg.is_file():
        return
    data = _read_json(pkg)
    if data is None:
        return

    deps: dict = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        value = data.get(key)
        if isinstance(value, dict):
            deps.update(value)
    dep_names = {str(k).lower() for k in deps}

    runner = next((name for name in JS_TEST_RUNNERS if name in dep_names), None)
    scripts = data.get("scripts") or {}
    test_script = scripts.get("test") if isinstance(scripts, dict) else None
    if runner is None and test_script and "no test specified" not in str(test_script).lower():
        runner = "npm test"

    is_ts = (loc_path / "tsconfig.json").is_file()
    languages.append({
        "name": "typescript" if is_ts else "javascript",
        "location": loc_label,
        "runner": runner,
    })

    frontend_hits = [n for n in FRONTEND_DEP_NAMES if n in dep_names]
    if frontend_hits:
        _bump(scores, signals, "frontend-spa", 2, f"package.json in {loc_label} referenziert {', '.join(frontend_hits)}")

    rest_hits = [n for n in REST_API_DEP_NAMES if n in dep_names]
    if rest_hits:
        _bump(scores, signals, "rest-api", 1, f"package.json in {loc_label} referenziert {', '.join(rest_hits)}")

    if isinstance(data.get("bin"), (str, dict)):
        _bump(scores, signals, "cli-library", 2, f"package.json in {loc_label} hat ein 'bin'-Feld")


def _scan_pyproject(loc_label: str, loc_path: Path, scores: dict, signals: dict, languages: list[dict]) -> None:
    path = loc_path / "pyproject.toml"
    if not path.is_file():
        return
    raw_text = _read_text(path)
    # Nur der Abhängigkeits-relevante Text zählt — Kommentare und Freitextfelder
    # (description, readme, …) fließen nicht ein (siehe Skriptkopf, Fix-Runde).
    dep_text = _extract_toml_dependency_text(raw_text).lower()
    has_scripts_section = _has_toml_scripts_section(raw_text)

    runner = "pytest" if "pytest" in dep_text else None
    languages.append({"name": "python", "location": loc_label, "runner": runner})

    rest_hits = [n for n in REST_API_DEP_NAMES if n in dep_text]
    if rest_hits:
        _bump(scores, signals, "rest-api", 1,
              f"pyproject.toml in {loc_label} erwähnt {', '.join(rest_hits)} (Abhängigkeitsabschnitt)")

    cli_hits = [n for n in CLI_DEP_NAMES if n in dep_text]
    if cli_hits or has_scripts_section:
        why = (f"pyproject.toml in {loc_label} erwähnt {', '.join(cli_hits)} (Abhängigkeitsabschnitt)" if cli_hits
               else f"pyproject.toml in {loc_label} hat einen Scripts-Abschnitt")
        _bump(scores, signals, "cli-library", 2, why)


def _scan_requirements(loc_label: str, loc_path: Path, scores: dict, signals: dict, languages: list[dict]) -> None:
    path = loc_path / "requirements.txt"
    if not path.is_file():
        return
    # pyproject.toml gewinnt, falls beides da ist — requirements.txt ist nur der
    # Fallback für Repos ohne pyproject.toml.
    if any(lang["location"] == loc_label and lang["name"] == "python" for lang in languages):
        return
    # requirements.txt ist zeilenweise ohnehin nur Abhängigkeiten (kein
    # Freitext wie bei pyproject.toml) — hier reicht Kommentar-Entfernung.
    text = _strip_hash_comments(_read_text(path)).lower()
    runner = "pytest" if "pytest" in text else None
    languages.append({"name": "python", "location": loc_label, "runner": runner})

    rest_hits = [n for n in REST_API_DEP_NAMES if n in text]
    if rest_hits:
        _bump(scores, signals, "rest-api", 1, f"requirements.txt in {loc_label} erwähnt {', '.join(rest_hits)}")


def _scan_pom(loc_label: str, loc_path: Path, scores: dict, signals: dict, languages: list[dict]) -> None:
    for name in ("pom.xml", "build.gradle", "build.gradle.kts"):
        build_file = loc_path / name
        if build_file.is_file():
            break
    else:
        return
    raw_text = _read_text(build_file)
    text = _strip_xml_comments(raw_text).lower()
    runner = "maven/junit" if "junit" in text else None
    languages.append({"name": "java", "location": loc_label, "runner": runner})
    if "spring-boot-starter-web" in text or "spring-web" in text:
        _bump(scores, signals, "rest-api", 1, f"{build_file.name} in {loc_label} erwähnt Spring Web")


def _scan_openapi(loc_label: str, loc_path: Path, scores: dict, signals: dict) -> None:
    for name in OPENAPI_NAMES:
        if (loc_path / name).is_file():
            _bump(scores, signals, "rest-api", 3, f"{name} gefunden in {loc_label}")


def _scan_router_patterns(loc_label: str, loc_path: Path, scores: dict, signals: dict) -> None:
    hits = []
    for fname in ROUTER_ENTRY_FILES:
        target = loc_path / fname
        if not target.is_file():
            continue
        text = _read_text(target, limit=20_000)
        for pattern in ROUTER_PATTERNS:
            if pattern.search(text):
                hits.append(fname)
                break  # ein Treffer pro Datei reicht als Signal
    if hits:
        _bump(scores, signals, "rest-api", 2, f"Router-Muster in {loc_label} gefunden ({', '.join(hits)})")


# ---------------------------------------------------------------------------
# Repo-weiter Scan: Dateizahl, Testdateien, Git-Historie
# ---------------------------------------------------------------------------


def _walk_repo(repo: Path) -> tuple[int, bool]:
    """(Dateianzahl, Testdateien gefunden) — begrenzter, sicherer Scan."""
    count = 0
    tests_found = False
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        rel_dir = Path(dirpath).relative_to(repo).as_posix()
        for fname in filenames:
            count += 1
            relpath = fname if rel_dir == "." else f"{rel_dir}/{fname}"
            if TEST_FILE_RE.search(relpath):
                tests_found = True
            if count >= MAX_WALK_FILES:
                return count, tests_found
    return count, tests_found


def _run_git(repo: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _git_info(repo: Path) -> dict:
    if not (repo / ".git").exists():
        return {"available": False, "commit_count": None, "first_commit_days_ago": None}

    count_raw = _run_git(repo, "rev-list", "--count", "HEAD")
    commit_count = int(count_raw) if count_raw and count_raw.isdigit() else None

    first_epoch = _run_git(repo, "log", "--reverse", "--format=%at", "-1")
    days_ago = None
    if first_epoch and first_epoch.lstrip("-").isdigit():
        days_ago = max(0.0, (time.time() - int(first_epoch)) / 86400)

    return {"available": True, "commit_count": commit_count, "first_commit_days_ago": days_ago}


def _legacy_score(file_count: int, tests_found: bool, git_info: dict) -> dict:
    """Score, kein Orakel (Spec 05) — aber **keine reine Summe mehr** (Review-
    Fund): 'keine Tests' ist eine notwendige, nie eine hinreichende Bedingung.
    Ein frisches, gerade erst begonnenes Projekt hat fast immer noch keine
    Tests und ist trotzdem kein Legacy-Fall, sondern braucht normale Units —
    der Unterschied zwischen beiden ist der ganze Sinn dieses Adapters.
    `suspected` ist deshalb: keine Tests **UND** (Alterssignal ODER
    Umfangssignal), wobei die Umfangsschwellen bewusst über das hinausgehen,
    was ein Projekt in seinen ersten Commits ansammelt.

    Bekannte Grenze: `evalkit`-Fixtures können kein Commit-Alter simulieren
    (alle Fixture-Commits entstehen "jetzt") — das Alterssignal ist deshalb
    über Evals nicht auslösbar, nur das Umfangssignal (Datei-/Commit-Zahl).
    Siehe docs/known-limits.md, Abschnitt testing-strategy."""
    if tests_found:
        return {"suspected": False, "score": 0, "reasons": ["Testdateien gefunden"]}

    reasons: list[str] = ["keine Testdateien gefunden"]
    scale_signals: list[str] = []

    if git_info["available"]:
        commit_count = git_info["commit_count"] or 0
        if commit_count >= LEGACY_COMMIT_COUNT_THRESHOLD:
            scale_signals.append(f"{commit_count} Commits Historie (Schwelle {LEGACY_COMMIT_COUNT_THRESHOLD})")
        days = git_info["first_commit_days_ago"]
        if days is not None and days >= LEGACY_AGE_DAYS_THRESHOLD:
            scale_signals.append(f"erster Commit vor {days / 365:.1f} Jahren")
    else:
        reasons.append("kein Git-Repo — Historiensignale (Alter, Commit-Zahl) fehlen")

    if file_count >= LEGACY_FILE_COUNT_THRESHOLD:
        scale_signals.append(f"{file_count} Dateien im Repo (Schwelle {LEGACY_FILE_COUNT_THRESHOLD})")

    reasons.extend(scale_signals)
    # score bleibt informativ (wie viele Umfangs-/Alterssignale zusätzlich zu
    # "keine Tests" vorliegen) — die Entscheidung selbst ist die
    # notwendig-und-hinreichend-Bedingung unten, kein Schwellenwert-Vergleich.
    return {"suspected": bool(scale_signals), "score": len(scale_signals) + 1, "reasons": reasons}


# ---------------------------------------------------------------------------
# Orchestrierung
# ---------------------------------------------------------------------------


def classify(repo: Path) -> dict:
    """Klassifiziere `repo` neu — liest nie den alten Cache (R5)."""
    repo = Path(repo)
    if not repo.is_dir():
        raise DetectError(f"kein Verzeichnis: {repo}")

    scores: dict[str, int] = {}
    signals: dict[str, list[str]] = {}
    languages: list[dict] = []

    for loc_label, loc_path in _scan_locations(repo):
        _scan_extension(loc_label, loc_path, scores, signals)
        _scan_package_json(loc_label, loc_path, scores, signals, languages)
        _scan_pyproject(loc_label, loc_path, scores, signals, languages)
        _scan_requirements(loc_label, loc_path, scores, signals, languages)
        _scan_pom(loc_label, loc_path, scores, signals, languages)
        _scan_openapi(loc_label, loc_path, scores, signals)
        _scan_router_patterns(loc_label, loc_path, scores, signals)

    candidates = sorted(
        ({"type": t, "score": s, "signals": signals.get(t, [])} for t, s in scores.items() if s > 0),
        key=lambda c: (-c["score"], c["type"]),
    )

    primary = None
    ambiguous = False
    if candidates:
        top_score = candidates[0]["score"]
        leaders = [c for c in candidates if c["score"] == top_score]
        if len(leaders) == 1:
            primary = leaders[0]["type"]
        else:
            ambiguous = True

    file_count, tests_found = _walk_repo(repo)
    git_info = _git_info(repo)
    legacy = _legacy_score(file_count, tests_found, git_info)

    if not candidates:
        note = "keine Typ-Signale gefunden (leeres oder unbekanntes Repository)"
    elif ambiguous:
        note = "mehrdeutig — mehrere Kandidaten mit gleicher Punktzahl, nachfragen statt raten"
    else:
        note = None

    return {
        "_meta": {
            "skill": "testing-strategy",
            "schema": SCHEMA_VERSION,
            "generated": "python skills/testing-strategy/scripts/detect_stack.py",
        },
        "candidates": candidates,
        "primary": primary,
        "ambiguous": ambiguous,
        "note": note,
        "languages": languages,
        "legacy": legacy,
        "git": git_info,
        "file_count": file_count,
        "tests_found": tests_found,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repo-Klassifikation für testing-strategy")
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    try:
        result = classify(args.repo)
    except DetectError as exc:
        print(f"Klassifikation gescheitert: {exc}", file=sys.stderr)
        return 1

    target = args.repo / CACHE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    if result["ambiguous"]:
        types = ", ".join(c["type"] for c in result["candidates"])
        print(f"Mehrdeutig: {types} — nachfragen statt raten.")
    elif result["primary"]:
        print(f"Erkannt: {result['primary']}")
    else:
        print("Keine Typ-Signale gefunden.")

    if result["legacy"]["suspected"]:
        print(f"Legacy-Verdacht (Score {result['legacy']['score']}): {'; '.join(result['legacy']['reasons'])}")

    for lang in result["languages"]:
        if lang["runner"] is None:
            print(f"Kein Test-Runner erkannt für {lang['name']} in {lang['location']} — bitte angeben.")

    print(f"-> {CACHE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
