#!/usr/bin/env python3
"""Git-Fakten für dev-report sammeln. Tier 1: nur Stdlib.

Sammeln ist ein Skript, Schreiben ist ein Rendering — dieses Skript ist die
erste Hälfte. Was hier nicht landet, darf im Report nicht behauptet werden.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1
MODES = ("weekly", "feature", "release")
CACHE_PATH = Path(".skills") / "cache" / "facts.json"

# Nicht 2: den vergibt argparse selbst für Aufrufsfehler (unbekannter --mode,
# fehlendes Pflichtargument). Teilte sich der Leer-Bereich-Fall diesen Code, könnte
# ein Aufrufer "Bereich lieferte nichts" nicht von "du hast dich vertippt"
# unterscheiden — und würde beim Vertippen den Bereich prüfen statt den Befehl.
EXIT_EMPTY_RANGE = 3
FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"


class CollectError(RuntimeError):
    """Das Sammeln ist gescheitert — mit einer Ursache, die der Nutzer versteht."""


def _git(repo: Path, *args: str) -> str:
    try:
        done = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, timeout=120, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CollectError(f"git {' '.join(args)} konnte nicht gestartet werden: {exc}") from exc
    if done.returncode != 0:
        raise CollectError(f"git {' '.join(args)} fehlgeschlagen: {done.stderr.strip()}")
    return done.stdout


def _detect_trunk(repo: Path) -> str:
    """Trunk-Branch ermitteln statt raten — Repos heißen nicht alle `main`.

    Erst `origin/HEAD`, falls ein Remote das gesetzt hat; sonst der Reihe
    nach `main` und `master`, geprüft statt angenommen.
    """
    try:
        symbolic = _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD").strip()
    except CollectError:
        symbolic = ""
    if symbolic:
        return symbolic.rsplit("/", 1)[-1]

    for candidate in ("main", "master"):
        check = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", candidate],
            cwd=repo, capture_output=True, text=True, timeout=120, check=False,
        )
        if check.returncode == 0:
            return candidate

    raise CollectError(
        "kein Trunk-Branch gefunden (weder refs/remotes/origin/HEAD noch main noch master)"
    )


def resolve_range(
    repo: Path, mode: str, since: str | None, rev_range: str | None, branch: str | None
) -> tuple[str, str]:
    """Genau ein Selektor bestimmt das Zeitfenster; er liefert auch das Enddatum-Label."""
    chosen = [x for x in (since, rev_range, branch) if x]
    if len(chosen) != 1:
        raise CollectError("genau eine der Optionen --since, --range oder --branch angeben")
    if since:
        return f"--since={since}", since
    if rev_range:
        return rev_range, rev_range.split("..")[-1] or "HEAD"
    trunk = _detect_trunk(repo)
    return f"{trunk}..{branch}", branch.replace("/", "-")


def report_path(mode: str, end_label: str) -> str:
    return f"docs/reports/{mode}-{end_label}.md"


def collect_commits(repo: Path, rev_range: str) -> list[dict]:
    """Commits im Bereich, neueste zuerst, mit Dateien und Churn."""
    fmt = RECORD_SEP + FIELD_SEP.join(["%H", "%s", "%ad"])
    raw = _git(repo, "log", rev_range, f"--pretty=format:{fmt}", "--date=short", "--numstat")

    commits: list[dict] = []
    for block in raw.split(RECORD_SEP):
        block = block.strip("\n")
        if not block:
            continue
        lines = block.split("\n")
        if not lines:
            continue
        # First line is the header
        head = lines[0]
        parts = head.split(FIELD_SEP)
        if len(parts) < 3:
            continue
        files: list[str] = []
        insertions = deletions = 0
        # Remaining lines are file stats
        for line in lines[1:]:
            if not line.strip():
                continue
            columns = line.split("\t")
            if len(columns) != 3:
                continue
            added, removed, path = columns
            files.append(path)
            insertions += int(added) if added.isdigit() else 0
            deletions += int(removed) if removed.isdigit() else 0
        commits.append({
            "hash": parts[0][:12],
            "subject": parts[1],
            "date": parts[2],
            "files": files,
            "insertions": insertions,
            "deletions": deletions,
        })
    return commits


def _prefix_of(path: str) -> str:
    head, sep, _ = path.partition("/")
    return f"{head}/" if sep else "(root)"


def aggregate_modules(commits: list[dict]) -> list[dict]:
    """Berührte Module per Pfadpräfix — die erste Verzeichnisebene.

    Churn wird gleichmäßig auf die Dateien eines Commits verteilt: `git log
    --numstat` liefert sie pro Datei, aber die Summe pro Commit ist die Zahl,
    die im Report auftaucht. Genauer wäre teurer und nicht genauer genug.
    """
    buckets: dict[str, dict] = {}
    for commit in commits:
        files = commit["files"] or []
        share_in = commit["insertions"] // max(len(files), 1)
        share_out = commit["deletions"] // max(len(files), 1)
        counted: set[str] = set()
        for path in files:
            prefix = _prefix_of(path)
            bucket = buckets.setdefault(
                prefix, {"prefix": prefix, "commits": 0, "insertions": 0, "deletions": 0}
            )
            if prefix not in counted:
                bucket["commits"] += 1
                counted.add(prefix)
            bucket["insertions"] += share_in
            bucket["deletions"] += share_out
    return sorted(buckets.values(), key=lambda b: -b["commits"])


QUIET_THRESHOLD = 5
# Conventional Commits ("fix:", "fix(scope):") UND die gängigen
# nicht-konventionellen Formen ("Fix bug in parser", "Fixed the login flow",
# "hotfix"/"bugfix"). `\b` nach dem Stamm verhindert Treffer wie "prefix:"
# oder "Fixture angelegt" — siehe die Prüftabelle in den Tests.
FIX_RE = re.compile(r"^(fix|fixed|fixes|hotfix|bugfix)\b")


def detect_patterns(commits: list[dict]) -> dict:
    """Ehrliche Signale: Reverts, Fix-auf-Fix, ruhige Perioden.

    Ohne diese Erkennung berichtet die Skill nur, was gut lief — der Fehler,
    den Spec 02 dem Status quo vorwirft.
    """
    reverts = [
        {"hash": c["hash"], "subject": c["subject"]}
        for c in commits
        if c["subject"].lower().startswith("revert")
    ]

    fixes_per_file: dict[str, int] = {}
    fix_commits_count = 0
    for commit in commits:
        subject = commit["subject"].lower()
        if not FIX_RE.match(subject):
            continue
        fix_commits_count += 1
        for path in commit["files"]:
            fixes_per_file[path] = fixes_per_file.get(path, 0) + 1

    fix_chains = sorted(
        ({"path": path, "count": count} for path, count in fixes_per_file.items() if count >= 2),
        key=lambda entry: -entry["count"],
    )

    # Ein leerer Bereich ist kein ruhiger Bereich: "quiet" heißt "wenige, aber
    # echte Commits", nicht "keine Antwort von git bekommen". Die Unterscheidung
    # zwischen beidem trifft main() anhand von len(commits) == 0.
    quiet = 0 < len(commits) < QUIET_THRESHOLD
    return {"reverts": reverts, "fix_chains": fix_chains, "fix_commits": fix_commits_count, "quiet": quiet}


HARVEST_SOURCES = (
    ("docs/debugging/INDEX.md", 1),
    ("docs/decisions.md", 1),
    ("docs/specs/wip", 1),
    ("CHANGELOG.md", 1),
    ("handoff.md", 1),
)
EXCERPT_CHARS = 2000

HEADER_RE = re.compile(
    r"^(?:<!--|#)\s*skill:\s*(?P<skill>[a-z0-9][a-z0-9-]*)\s*\|"
    r"\s*schema:\s*(?P<schema>\d+)\s*\|"
    r"\s*generated:\s*(?P<cmd>.+?)\s*(?:-->)?\s*$"
)


def read_header(path: Path) -> dict | None:
    """Kopfzeile eines Artefakts lesen (Spec 00 §1), oder None wenn keine da ist."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        if not line.strip():
            continue
        match = HEADER_RE.match(line.strip())
        if not match:
            return None
        return {"skill": match.group("skill"), "schema": int(match.group("schema")), "generated": match.group("cmd")}
    return None


def _harvest_one(repo: Path, relpath: str, expected_schema: int) -> dict:
    path = repo / relpath
    if path.is_dir():
        files = sorted(p for p in path.glob("*.md") if p.is_file())
        if not files:
            return {"path": relpath, "status": "missing", "schema": None, "excerpt": ""}
        path = files[0]
    if not path.is_file():
        return {"path": relpath, "status": "missing", "schema": None, "excerpt": ""}

    header = read_header(path)
    if header is None:
        # Sichtbar überspringen statt raten — Konsumenten-Regel, Spec 00 §1.
        return {"path": relpath, "status": "no_header", "schema": None, "excerpt": ""}
    if header["schema"] != expected_schema:
        return {"path": relpath, "status": "schema_mismatch", "schema": header["schema"], "excerpt": ""}

    text = path.read_text(encoding="utf-8", errors="replace")
    return {"path": relpath, "status": "read", "schema": header["schema"], "excerpt": text[:EXCERPT_CHARS]}


def harvest(repo: Path) -> list[dict]:
    """Zweite Faktenquelle: Artefakte der Geschwister-Skills, falls vorhanden."""
    return [_harvest_one(repo, relpath, schema) for relpath, schema in HARVEST_SOURCES]


def _tag_end_ref(rev_range: str) -> str:
    """Endpunkt für `git tag --merged`, aus dem Range-Ausdruck abgeleitet.

    `--since=X` kennt keinen expliziten Endpunkt außer HEAD; `a..b`-Formen
    (explizite Range oder `main..feature/x`) liefern `b`.
    """
    if rev_range.startswith("--since"):
        return "HEAD"
    if ".." in rev_range:
        return rev_range.rsplit("..", 1)[-1] or "HEAD"
    return rev_range or "HEAD"


def collect_tags(repo: Path, rev_range: str) -> list[dict]:
    """Tags im Bereich — nicht alle Tags des Repos.

    `--merged <endref>` schränkt auf Tags ein, die im Verlauf des
    Bereichsendes liegen; ohne das listet `git tag` jeden Tag der gesamten
    Projekthistorie, ungeachtet von `rev_range`.

    Bei annotierten Tags zeigt `%(objectname)` auf das Tag-Objekt, nicht auf
    den Commit — ein Beleg, der auf keinen Eintrag in `facts.commits` zeigt.
    `%(*objectname)` dereferenziert; bei leichten Tags ist das Feld leer,
    dort gilt `%(objectname)` bereits direkt der Commit.
    """
    end_ref = _tag_end_ref(rev_range)
    fmt = FIELD_SEP.join(["%(refname:short)", "%(objectname:short)", "%(*objectname:short)"])
    raw = _git(repo, "tag", "--merged", end_ref, f"--format={fmt}")
    tags = []
    for line in raw.splitlines():
        parts = line.split(FIELD_SEP)
        if len(parts) != 3 or not parts[0]:
            continue
        name, direct_hash, dereferenced_hash = parts
        tags.append({"name": name, "hash": dereferenced_hash or direct_hash})
    return tags


def collect_merges(repo: Path, rev_range: str) -> list[dict]:
    fmt = FIELD_SEP.join(["%h", "%s"])
    raw = _git(repo, "log", rev_range, "--merges", f"--pretty=format:{fmt}")
    out = []
    for line in raw.splitlines():
        parts = line.split(FIELD_SEP)
        if len(parts) == 2:
            out.append({"hash": parts[0], "subject": parts[1]})
    return out


def build_facts(repo: Path, *, mode: str, since: str | None, rev_range: str | None, branch: str | None) -> dict:
    git_range, end_label = resolve_range(repo, mode, since, rev_range, branch)
    selector = f"--since {since}" if since else (f"--range {rev_range}" if rev_range else f"--branch {branch}")
    commits = collect_commits(repo, git_range)
    return {
        "_meta": {
            "skill": "dev-report",
            "schema": SCHEMA_VERSION,
            "generated": f"python skills/dev-report/scripts/collect.py --mode {mode} {selector}",
        },
        "mode": mode,
        "range": {"git_range": git_range, "end_label": end_label},
        "report_path": report_path(mode, end_label),
        "commits": commits,
        "modules": aggregate_modules(commits),
        "tags": collect_tags(repo, git_range),
        "merges": collect_merges(repo, git_range),
        "patterns": detect_patterns(commits),
        "harvest": harvest(repo),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Git-Fakten für dev-report sammeln")
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--since", help="Zeitfenster, z. B. 2026-08-01")
    parser.add_argument("--range", dest="rev_range", help="Ref-Bereich, z. B. v1.2..HEAD")
    parser.add_argument("--branch", help="Branch gegen main, z. B. feature/x")
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    try:
        facts = build_facts(
            args.repo, mode=args.mode, since=args.since, rev_range=args.rev_range, branch=args.branch,
        )
    except CollectError as exc:
        print(f"Sammeln gescheitert: {exc}", file=sys.stderr)
        return 1

    if not facts["commits"]:
        print(
            "Sammeln ergab null Commits im angegebenen Bereich. Das ist keine "
            "ruhige Periode, sondern vermutlich ein falsch angegebener oder "
            "von git unlesbarer Bereich (z. B. ein Datum, das git als 'jetzt' "
            "deutet). Kein facts.json geschrieben — Bereich prüfen und erneut "
            "versuchen.",
            file=sys.stderr,
        )
        return EXIT_EMPTY_RANGE

    target = args.repo / CACHE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(facts, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(facts['commits'])} Commits gesammelt -> {CACHE_PATH}")
    skipped = [e for e in facts["harvest"] if e["status"] in ("schema_mismatch", "no_header")]
    for entry in skipped:
        print(f"Quelle übersprungen ({entry['status']}): {entry['path']}")
    print(f"Report gehört nach {facts['report_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
