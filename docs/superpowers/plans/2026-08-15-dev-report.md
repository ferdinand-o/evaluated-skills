# dev-report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine Skill, die Entwicklungs-Reports aus Git-Fakten rendert statt sie aus dem Kontextfenster zu rekonstruieren — plus die Harness-Erweiterung, ohne die sie nicht evaluierbar wäre.

**Architecture:** Zwei strikt getrennte Phasen. `collect.py` (Tier 1, nur Stdlib) liest lokales Git und definierte Repo-Artefakte und schreibt alles nach `.skills/cache/facts.json`. Danach ist Schreiben ein reines Rendering: Claude füllt ein Template nach Modus, wählt den Ton nach Zielgruppe, und darf keine faktische Aussage treffen, die nicht auf einen `facts.json`-Eintrag zeigt. Vorgeschaltet erweitert Task 1 den Eval-Harness um Fixture-Historie, weil eine Skill, die Git-Verläufe liest, gegen Ein-Commit-Fixtures nicht prüfbar ist.

**Tech Stack:** Python 3.13 (Stdlib), git CLI, pytest als Dev-Abhängigkeit, der Eval-Harness aus `evalkit/`.

**Spec:** `specs/Spec 02 – dev-report.md` (und `specs/Spec 00 – skill-foundation.md` für Artefakt- und Eval-Vertrag)

## Global Constraints

- **Datenquelle ist ausschließlich lokales Git.** Keine `gh`-/API-Abhängigkeit — die Skill muss offline und in jedem Repo funktionieren.
- **Tier 1:** `collect.py` importiert ausschließlich die Python-Stdlib. pytest ist Dev-Abhängigkeit und darf nie aus Skill-Code importiert werden.
- **Drei Anlässe:** Wochen-/Statusreport, Feature-/PR-Abschluss, Release Notes.
- **Drei Zielgruppen:** Ich/Projektlog, Team/Technik, Vorgesetzte.
- **Contract:** Jede faktische Aussage im Report trägt eine Referenz auf einen `facts.json`-Eintrag (Commit, Tag, Artefakt). Sätze ohne Referenz müssen als `Einschätzung:` markiert sein.
- **Ruhige Perioden werden als solche benannt.** Aufblähen ist der definierte Hauptfehler der Skill.
- **Die Skill liefert immer einen Entwurf zur Freigabe**, nie einen automatisch versendeten Report.
- **Reports auf Deutsch.** Templates zweisprachig vorbereitet, deutsche Fassung zuerst.
- **Artefakt-Pfade nach Spec 00 §1:** Fakten nach `.skills/cache/facts.json` (Ephemera, gitignored), fertige Reports nach `docs/reports/` (Wissen, committed).
- **Konsumenten-Regel (Spec 00 §1):** Der Harvest nimmt nie ein Format an, sondern liest die Kopfzeile der Quelle. Bei fehlender oder unbekannter Schema-Version wird die Quelle sichtbar übersprungen, nicht geraten.
- **Frontmatter:** nur `name` und `description`. SKILL.md ≤ 150 Zeilen.
- **Dokumentsprache Deutsch** (Kommentare, Fehlermeldungen, Prosa), Bezeichner in Code und JSON englisch.

### Report-Dateiname

`docs/reports/<mode>-<enddatum>.md`, z. B. `docs/reports/weekly-2026-08-07.md`. `collect.py` berechnet den Pfad und schreibt ihn als `report_path` nach `facts.json` — damit ist er für Mensch, Skill und Eval dieselbe Größe und muss nicht geraten werden.

### Eine Voraussetzung, die nicht aus Spec 02 stammt

Task 1 erweitert `evalkit/workspace.py`. Das ist Spec-00-Arbeit, hier aber zwingend: `_init_git()` erzeugt heute genau einen Commit („fixture baseline"), und `docs/known-limits.md` führt das ausdrücklich als Grenze. Alle vier Evals aus Spec 02 brauchen mehrere Commits — eine ruhige Woche mit drei Commits, eine Revert-Kette, eine Release-Range über zwei Tags. Ohne Task 1 ist `dev-report` baubar, aber nicht prüfbar, und eine ungeprüfte Skill ist nach Spec 00 keine fertige Skill.

---

### Task 1: Fixture-Historie im Eval-Harness

**Files:**
- Modify: `evalkit/workspace.py` (`_init_git`, `prepare`)
- Modify: `tests/test_workspace.py`
- Modify: `docs/known-limits.md` (die behobene Grenze streichen)

**Interfaces:**
- Consumes: nichts Neues
- Produces:
  - Erweitertes Fixture-Manifest: `{"git": true, "description": str, "commits": [{"message": str, "touch": {relpath: content}, "delete": [relpath], "tag": str | null}]}`
  - `evalkit.workspace.WorkspaceError` bei ungültiger `commits`-Angabe (unverändert im Typ)
  - Verhalten: ohne `commits` bleibt alles wie bisher — ein Commit „fixture baseline"

- [ ] **Step 1: Write the failing test**

An `tests/test_workspace.py` anhängen:

```python
def make_history_fixture(tmp_path, commits, name="history"):
    fixture = tmp_path / "fixtures" / name
    fixture.mkdir(parents=True)
    (fixture / "fixture.json").write_text(
        json.dumps({"git": True, "description": "test", "commits": commits}), encoding="utf-8"
    )
    (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
    return fixture


def git_log(root):
    import subprocess
    done = subprocess.run(
        ["git", "log", "--format=%s"], cwd=root, capture_output=True, text=True, check=True
    )
    return done.stdout.split()


def test_commits_field_creates_one_commit_per_entry(tmp_path):
    fixture = make_history_fixture(tmp_path, [
        {"message": "erst", "touch": {"a.py": "x = 1\n"}},
        {"message": "dann", "touch": {"b.py": "y = 2\n"}},
    ])
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), fixture)
    assert git_log(ws.root) == ["dann", "erst"]
    assert (ws.root / "a.py").read_text(encoding="utf-8") == "x = 1\n"
    assert (ws.root / "b.py").read_text(encoding="utf-8") == "y = 2\n"


def test_commits_field_supports_delete_and_tag(tmp_path):
    import subprocess
    fixture = make_history_fixture(tmp_path, [
        {"message": "anlegen", "touch": {"weg.py": "tot\n"}, "tag": "v1.0"},
        {"message": "entfernen", "delete": ["weg.py"]},
    ])
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), fixture)
    assert not (ws.root / "weg.py").exists()
    tags = subprocess.run(["git", "tag"], cwd=ws.root, capture_output=True, text=True, check=True)
    assert tags.stdout.split() == ["v1.0"]


def test_fixture_content_is_committed_before_declared_commits(tmp_path):
    """Mitgelieferte Dateien bilden weiterhin den Baseline-Commit."""
    fixture = make_history_fixture(tmp_path, [{"message": "spaeter", "touch": {"a.py": "x\n"}}])
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), fixture)
    assert git_log(ws.root) == ["spaeter", "fixture", "baseline"]


def test_without_commits_field_behaviour_is_unchanged(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path, git=True))
    assert git_log(ws.root) == ["fixture", "baseline"]


def test_commit_without_message_is_rejected(tmp_path):
    fixture = make_history_fixture(tmp_path, [{"touch": {"a.py": "x\n"}}])
    with pytest.raises(WorkspaceError, match="message"):
        prepare(tmp_path / "ws", make_skill(tmp_path), fixture)


def test_commit_with_unsafe_path_is_rejected(tmp_path):
    fixture = make_history_fixture(tmp_path, [{"message": "boese", "touch": {"../draussen.py": "x\n"}}])
    with pytest.raises(WorkspaceError, match="Pfad"):
        prepare(tmp_path / "ws", make_skill(tmp_path), fixture)


def test_commits_field_without_git_is_rejected(tmp_path):
    fixture = tmp_path / "fixtures" / "nogit"
    fixture.mkdir(parents=True)
    (fixture / "fixture.json").write_text(
        json.dumps({"git": False, "commits": [{"message": "x"}]}), encoding="utf-8"
    )
    with pytest.raises(WorkspaceError, match="git"):
        prepare(tmp_path / "ws", make_skill(tmp_path), fixture)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_workspace.py -v -k "commits or history or unchanged"`
Expected: FAIL — `commits` wird derzeit ignoriert, `git_log` liefert nur `["fixture", "baseline"]`

- [ ] **Step 3: Write minimal implementation**

In `evalkit/workspace.py` `_init_git` ersetzen und `prepare` anpassen:

```python
def _safe_relpath(raw: object, where: str) -> Path:
    """Fixture-Pfade dürfen den Workspace nicht verlassen (wie in schema.py)."""
    if not isinstance(raw, str) or not raw:
        raise WorkspaceError(f"{where}: Pfad muss ein nicht-leerer String sein, war {raw!r}")
    candidate = PurePosixPath(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise WorkspaceError(f"{where}: Pfad {raw!r} ist absolut oder enthält '..'")
    return Path(raw)


def _init_git(root: Path) -> None:
    _git(root, "init", "--quiet", "--initial-branch=main")
    _git(root, "config", "user.email", "evals@example.invalid")
    _git(root, "config", "user.name", "Eval Harness")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "fixture baseline")


def _apply_commits(root: Path, commits: object) -> None:
    """Erzeuge je Eintrag einen Commit — das Historien-Feld aus dem Manifest.

    Ohne das kann keine Skill geprüft werden, die Git-Verläufe liest: eine ruhige
    Woche, eine Revert-Kette oder eine Release-Range brauchen mehrere Commits.
    """
    if not isinstance(commits, list):
        raise WorkspaceError(f"fixture.json: 'commits' muss eine Liste sein, war {type(commits).__name__}")

    for index, entry in enumerate(commits):
        where = f"fixture.json: commits[{index}]"
        if not isinstance(entry, dict):
            raise WorkspaceError(f"{where}: Eintrag muss ein Objekt sein")
        message = entry.get("message")
        if not isinstance(message, str) or not message:
            raise WorkspaceError(f"{where}: 'message' fehlt oder ist leer")

        for raw_path, content in (entry.get("touch") or {}).items():
            target = root / _safe_relpath(raw_path, where)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(content), encoding="utf-8")

        for raw_path in entry.get("delete") or []:
            target = root / _safe_relpath(raw_path, where)
            if target.is_file():
                target.unlink()

        _git(root, "add", "-A")
        _git(root, "commit", "--quiet", "--allow-empty", "-m", message)

        tag = entry.get("tag")
        if tag:
            if not isinstance(tag, str):
                raise WorkspaceError(f"{where}: 'tag' muss ein String sein")
            _git(root, "tag", tag)
```

In `prepare()` direkt nach dem bestehenden `if wants_git: _init_git(dest)` ergänzen:

```python
    declared_commits = manifest.get("commits") if fixture_dir is not None else None
    if declared_commits is not None:
        if not wants_git:
            raise WorkspaceError("fixture.json: 'commits' verlangt \"git\": true")
        _apply_commits(dest, declared_commits)
```

`manifest` muss dafür außerhalb des `if fixture_dir is not None`-Blocks initialisiert sein (`manifest: dict = {}` vor dem Block). Import ergänzen: `from pathlib import Path, PurePosixPath`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_workspace.py -v`
Expected: PASS — 19 bisherige plus 7 neue

- [ ] **Step 5: Full suite und Grenze streichen**

Run: `.venv/bin/pytest -q`
Expected: 91 passed

In `docs/known-limits.md` den Punkt „**Es gibt keinen Historien-Begriff.**" durch die neue Realität ersetzen:

```markdown
- **Fixture-Historie ist deklarativ, nicht aufgezeichnet.** Das `commits`-Feld im
  Manifest erzeugt eine Commit-Folge aus Textinhalten (`touch`/`delete`/`tag`).
  Was sich damit nicht bauen lässt: echte Merge-Topologien, Autorenwechsel,
  auseinanderliegende Zeitstempel. Ein Contract, der auf Commit-Daten oder
  Branch-Verzweigungen beruht, ist weiterhin nicht prüfbar.
```

- [ ] **Step 6: Commit**

```bash
git add evalkit/workspace.py tests/test_workspace.py docs/known-limits.md
git commit -m "feat(evals): Fixture-Manifest bekommt ein commits-Feld für echte Historie"
```

---

### Task 2: collect.py — Git-Fakten sammeln

**Files:**
- Create: `skills/dev-report/scripts/collect.py`
- Create: `tests/conftest.py`
- Create: `tests/test_dev_report_collect.py`

**Interfaces:**
- Consumes: nichts aus `evalkit`
- Produces:
  - `collect.collect_commits(repo: pathlib.Path, rev_range: str) -> list[dict]` — je Commit `hash`, `subject`, `date`, `files`, `insertions`, `deletions`
  - `collect.aggregate_modules(commits: list[dict]) -> list[dict]` — je `prefix` die Felder `commits`, `insertions`, `deletions`
  - `collect.resolve_range(mode: str, since: str | None, rev_range: str | None, branch: str | None) -> tuple[str, str]` — liefert `(git_range, end_label)`
  - `collect.report_path(mode: str, end_label: str) -> str` — `docs/reports/<mode>-<end_label>.md`
  - `collect.build_facts(repo, *, mode, since, rev_range, branch) -> dict`
  - `collect.main(argv: list[str] | None = None) -> int`
  - `tests/conftest.py::load_script(relpath: str)` — lädt ein Skill-Skript als Modul, ohne `sys.path` zu verändern
- Das erzeugte `facts.json` trägt `_meta` mit `skill`, `schema`, `generated` (JSON-Konvention aus `docs/artifact-header.md`).

- [ ] **Step 1: conftest-Helfer schreiben**

`tests/conftest.py`:

```python
"""Gemeinsame Test-Helfer. Skill-Skripte liegen außerhalb von evalkit/ und sind
keine Pakete — sie werden per importlib geladen, statt sys.path zu verbiegen."""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_script(relpath: str):
    """Lade ein Skill-Skript als Modul, z. B. 'skills/dev-report/scripts/collect.py'."""
    path = REPO_ROOT / relpath
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

- [ ] **Step 2: Write the failing test**

`tests/test_dev_report_collect.py`:

```python
import json
import subprocess

import pytest

from conftest import load_script

collect = load_script("skills/dev-report/scripts/collect.py")


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """Kleines Repo mit drei Commits über zwei Module."""
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    for i, (path, text, message) in enumerate([
        ("src/parser.py", "def parse():\n    return 1\n", "feat: parser"),
        ("src/cli.py", "import sys\n", "feat: cli"),
        ("docs/note.md", "hallo\n", "docs: notiz"),
    ]):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        git(tmp_path, "add", "-A")
        git(tmp_path, "commit", "--quiet", "-m", message)
    return tmp_path


def test_collect_commits_returns_newest_first(repo):
    commits = collect.collect_commits(repo, "HEAD")
    assert [c["subject"] for c in commits] == ["docs: notiz", "feat: cli", "feat: parser"]


def test_collect_commits_carries_files_and_churn(repo):
    commits = collect.collect_commits(repo, "HEAD")
    first = commits[-1]
    assert first["files"] == ["src/parser.py"]
    assert first["insertions"] == 2
    assert first["deletions"] == 0
    assert len(first["hash"]) >= 7


def test_aggregate_modules_groups_by_top_level_prefix(repo):
    modules = collect.aggregate_modules(collect.collect_commits(repo, "HEAD"))
    by_prefix = {m["prefix"]: m for m in modules}
    assert by_prefix["src/"]["commits"] == 2
    assert by_prefix["docs/"]["commits"] == 1
    assert by_prefix["src/"]["insertions"] == 3


def test_resolve_range_since(repo):
    git_range, end_label = collect.resolve_range("weekly", "2026-08-01", None, None)
    assert "--since=2026-08-01" in git_range
    assert end_label == "2026-08-01"


def test_resolve_range_explicit_range(repo):
    git_range, end_label = collect.resolve_range("release", None, "v1.0..HEAD", None)
    assert git_range == "v1.0..HEAD"
    assert end_label == "HEAD"


def test_resolve_range_rejects_two_selectors(repo):
    with pytest.raises(collect.CollectError, match="genau eine"):
        collect.resolve_range("weekly", "2026-08-01", "v1.0..HEAD", None)


def test_report_path_is_deterministic():
    assert collect.report_path("weekly", "2026-08-07") == "docs/reports/weekly-2026-08-07.md"


def test_build_facts_has_meta_and_report_path(repo):
    facts = collect.build_facts(repo, mode="weekly", since=None, rev_range="HEAD", branch=None)
    assert facts["_meta"]["skill"] == "dev-report"
    assert facts["_meta"]["schema"] == 1
    assert facts["_meta"]["generated"].startswith("python skills/dev-report/scripts/collect.py")
    assert facts["report_path"].startswith("docs/reports/")
    assert facts["mode"] == "weekly"
    assert len(facts["commits"]) == 3


def test_main_writes_facts_to_cache(repo, monkeypatch):
    monkeypatch.chdir(repo)
    rc = collect.main(["--mode", "weekly", "--range", "HEAD"])
    assert rc == 0
    written = json.loads((repo / ".skills" / "cache" / "facts.json").read_text(encoding="utf-8"))
    assert written["mode"] == "weekly"
    assert len(written["commits"]) == 3


def test_main_rejects_unknown_mode(repo, monkeypatch):
    monkeypatch.chdir(repo)
    with pytest.raises(SystemExit):
        collect.main(["--mode", "quartalsbericht", "--range", "HEAD"])
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_dev_report_collect.py -v`
Expected: FAIL beim Import — `skills/dev-report/scripts/collect.py` existiert nicht

- [ ] **Step 4: Write minimal implementation**

`skills/dev-report/scripts/collect.py`:

```python
#!/usr/bin/env python3
"""Git-Fakten für dev-report sammeln. Tier 1: nur Stdlib.

Sammeln ist ein Skript, Schreiben ist ein Rendering — dieses Skript ist die
erste Hälfte. Was hier nicht landet, darf im Report nicht behauptet werden.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1
MODES = ("weekly", "feature", "release")
CACHE_PATH = Path(".skills") / "cache" / "facts.json"
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


def resolve_range(mode: str, since: str | None, rev_range: str | None, branch: str | None) -> tuple[str, str]:
    """Genau ein Selektor bestimmt das Zeitfenster; er liefert auch das Enddatum-Label."""
    chosen = [x for x in (since, rev_range, branch) if x]
    if len(chosen) != 1:
        raise CollectError("genau eine der Optionen --since, --range oder --branch angeben")
    if since:
        return f"--since={since}", since
    if rev_range:
        return rev_range, rev_range.split("..")[-1] or "HEAD"
    return f"main..{branch}", branch.replace("/", "-")


def report_path(mode: str, end_label: str) -> str:
    return f"docs/reports/{mode}-{end_label}.md"


def collect_commits(repo: Path, rev_range: str) -> list[dict]:
    """Commits im Bereich, neueste zuerst, mit Dateien und Churn."""
    fmt = FIELD_SEP.join(["%H", "%s", "%ad"]) + RECORD_SEP
    raw = _git(repo, "log", rev_range, f"--pretty=format:{fmt}", "--date=short", "--numstat")

    commits: list[dict] = []
    for block in raw.split(RECORD_SEP):
        block = block.strip("\n")
        if not block:
            continue
        head, _, stats = block.partition("\n")
        parts = head.split(FIELD_SEP)
        if len(parts) < 3:
            continue
        files: list[str] = []
        insertions = deletions = 0
        for line in stats.splitlines():
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


def collect_tags(repo: Path, rev_range: str) -> list[dict]:
    raw = _git(repo, "tag", f"--format=%(refname:short){FIELD_SEP}%(objectname:short)")
    tags = []
    for line in raw.splitlines():
        parts = line.split(FIELD_SEP)
        if len(parts) == 2 and parts[0]:
            tags.append({"name": parts[0], "hash": parts[1]})
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
    git_range, end_label = resolve_range(mode, since, rev_range, branch)
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

    target = args.repo / CACHE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(facts, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(facts['commits'])} Commits gesammelt -> {CACHE_PATH}")
    print(f"Report gehört nach {facts['report_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_dev_report_collect.py -v`
Expected: PASS, 11 passed

- [ ] **Step 6: Commit**

```bash
git add skills/dev-report/scripts/collect.py tests/conftest.py tests/test_dev_report_collect.py
git commit -m "feat(dev-report): collect.py sammelt Git-Fakten nach facts.json"
```

---

### Task 3: collect.py — Muster-Erkennung

**Files:**
- Modify: `skills/dev-report/scripts/collect.py`
- Modify: `tests/test_dev_report_collect.py`

**Interfaces:**
- Consumes: `collect.collect_commits`, `collect.build_facts` aus Task 2
- Produces:
  - `collect.detect_patterns(commits: list[dict]) -> dict` mit den Schlüsseln `reverts`, `fix_chains`, `quiet`
  - `facts["patterns"]` als neuer Block in `build_facts`
  - `collect.QUIET_THRESHOLD: int` (5)

**Warum das kein Beiwerk ist:** Revert-Ketten und Fix-auf-Fix sind die ehrlichen Signale für „das war zäh". Ohne sie schreibt der Report nur, was gut lief — und genau das ist der Fehler, den Spec 02 dem Status quo vorwirft.

- [ ] **Step 1: Write the failing test**

An `tests/test_dev_report_collect.py` anhängen:

```python
def commit_stub(subject, files=("src/a.py",)):
    return {"hash": "abc1234", "subject": subject, "date": "2026-08-07",
            "files": list(files), "insertions": 1, "deletions": 0}


def test_detects_revert_commits():
    patterns = collect.detect_patterns([
        commit_stub('Revert "feat: parser"'),
        commit_stub("feat: parser"),
    ])
    assert len(patterns["reverts"]) == 1
    assert patterns["reverts"][0]["subject"].startswith("Revert")


def test_detects_fix_chain_on_same_file():
    patterns = collect.detect_patterns([
        commit_stub("fix: immer noch kaputt", files=["src/a.py"]),
        commit_stub("fix: parser", files=["src/a.py"]),
        commit_stub("feat: parser", files=["src/a.py"]),
    ])
    assert patterns["fix_chains"]
    assert patterns["fix_chains"][0]["path"] == "src/a.py"
    assert patterns["fix_chains"][0]["count"] == 2


def test_single_fix_is_no_chain():
    patterns = collect.detect_patterns([
        commit_stub("fix: parser", files=["src/a.py"]),
        commit_stub("feat: parser", files=["src/a.py"]),
    ])
    assert patterns["fix_chains"] == []


def test_quiet_period_is_flagged():
    assert collect.detect_patterns([commit_stub("feat: x")] * 3)["quiet"] is True


def test_busy_period_is_not_quiet():
    assert collect.detect_patterns([commit_stub("feat: x")] * 12)["quiet"] is False


def test_build_facts_includes_patterns(repo):
    facts = collect.build_facts(repo, mode="weekly", since=None, rev_range="HEAD", branch=None)
    assert facts["patterns"]["quiet"] is True
    assert facts["patterns"]["reverts"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_dev_report_collect.py -v -k "revert or chain or quiet or patterns"`
Expected: FAIL mit `AttributeError: module 'collect' has no attribute 'detect_patterns'`

- [ ] **Step 3: Write minimal implementation**

In `collect.py` nach `aggregate_modules` ergänzen:

```python
QUIET_THRESHOLD = 5
FIX_PREFIXES = ("fix:", "fix(", "hotfix", "bugfix")


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
    for commit in commits:
        subject = commit["subject"].lower()
        if not any(subject.startswith(p) for p in FIX_PREFIXES):
            continue
        for path in commit["files"]:
            fixes_per_file[path] = fixes_per_file.get(path, 0) + 1

    fix_chains = sorted(
        ({"path": path, "count": count} for path, count in fixes_per_file.items() if count >= 2),
        key=lambda entry: -entry["count"],
    )

    return {"reverts": reverts, "fix_chains": fix_chains, "quiet": len(commits) < QUIET_THRESHOLD}
```

In `build_facts` den Rückgabewert um eine Zeile erweitern, direkt nach `"merges": ...`:

```python
        "patterns": detect_patterns(commits),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_dev_report_collect.py -v`
Expected: PASS, 17 passed

- [ ] **Step 5: Commit**

```bash
git add skills/dev-report/scripts/collect.py tests/test_dev_report_collect.py
git commit -m "feat(dev-report): Reverts, Fix-Ketten und ruhige Perioden erkennen"
```

---

### Task 4: collect.py — Context Harvest mit Konsumenten-Regel

**Files:**
- Modify: `skills/dev-report/scripts/collect.py`
- Modify: `tests/test_dev_report_collect.py`

**Interfaces:**
- Consumes: `collect.build_facts` aus Task 2/3
- Produces:
  - `collect.HARVEST_SOURCES: tuple[tuple[str, int], ...]` — Pfad und erwartete Schema-Version
  - `collect.read_header(path: pathlib.Path) -> dict | None` — `{"skill", "schema", "generated"}` oder `None`
  - `collect.harvest(repo: pathlib.Path) -> list[dict]` — je Quelle `path`, `status` (`read` / `missing` / `schema_mismatch` / `no_header`), `schema`, `excerpt`
  - `facts["harvest"]` als neuer Block

**Die Regel, die hier zählt (Spec 00 §1):** Ein Konsument nimmt nie ein Format an, sondern liest die Kopfzeile. Bei fehlender oder unbekannter Version wird die Quelle **sichtbar** übersprungen. Genau das macht die Kopplung zwischen den Skills der Sammlung haltbar — und `dev-report` ist der erste echte Konsument, an dem sich die Regel bewährt.

- [ ] **Step 1: Write the failing test**

An `tests/test_dev_report_collect.py` anhängen:

```python
HEADER = "<!-- skill: debug-ledger | schema: 1 | generated: python scripts/new_ledger.py -->"


def write_source(repo, relpath, text):
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_read_header_parses_the_three_fields(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(HEADER + "\n# Titel\n", encoding="utf-8")
    header = collect.read_header(path)
    assert header["skill"] == "debug-ledger"
    assert header["schema"] == 1


def test_read_header_returns_none_without_header(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("# Nur ein Titel\n", encoding="utf-8")
    assert collect.read_header(path) is None


def test_harvest_reads_matching_schema(repo):
    write_source(repo, "docs/debugging/INDEX.md", HEADER + "\nLogin haengt -> Cache-Key kollidiert\n")
    entries = {e["path"]: e for e in collect.harvest(repo)}
    entry = entries["docs/debugging/INDEX.md"]
    assert entry["status"] == "read"
    assert "Cache-Key" in entry["excerpt"]


def test_harvest_marks_missing_source_without_failing(repo):
    entries = {e["path"]: e for e in collect.harvest(repo)}
    assert entries["docs/decisions.md"]["status"] == "missing"


def test_harvest_skips_unknown_schema_visibly(repo):
    write_source(repo, "docs/decisions.md",
                 "<!-- skill: feature-spec | schema: 99 | generated: x -->\nEntscheidung\n")
    entry = {e["path"]: e for e in collect.harvest(repo)}["docs/decisions.md"]
    assert entry["status"] == "schema_mismatch"
    assert entry["schema"] == 99
    assert "Entscheidung" not in entry["excerpt"]


def test_harvest_skips_source_without_header_visibly(repo):
    write_source(repo, "CHANGELOG.md", "## 1.0\n- irgendwas\n")
    entry = {e["path"]: e for e in collect.harvest(repo)}["CHANGELOG.md"]
    assert entry["status"] == "no_header"
    assert entry["excerpt"] == ""


def test_build_facts_includes_harvest(repo):
    facts = collect.build_facts(repo, mode="weekly", since=None, rev_range="HEAD", branch=None)
    assert any(e["path"] == "docs/decisions.md" for e in facts["harvest"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_dev_report_collect.py -v -k "harvest or header"`
Expected: FAIL mit `AttributeError: module 'collect' has no attribute 'read_header'`

- [ ] **Step 3: Write minimal implementation**

In `collect.py` `import re` ergänzen und nach `detect_patterns` einfügen:

```python
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
```

In `build_facts` nach `"patterns": ...` ergänzen:

```python
        "harvest": harvest(repo),
```

In `main()` nach der Commit-Zeile eine Zeile ergänzen, damit übersprungene Quellen sichtbar sind:

```python
    skipped = [e for e in facts["harvest"] if e["status"] in ("schema_mismatch", "no_header")]
    for entry in skipped:
        print(f"Quelle übersprungen ({entry['status']}): {entry['path']}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_dev_report_collect.py -v`
Expected: PASS, 24 passed

- [ ] **Step 5: Full suite**

Run: `.venv/bin/pytest -q`
Expected: 115 passed

- [ ] **Step 6: Commit**

```bash
git add skills/dev-report/scripts/collect.py tests/test_dev_report_collect.py
git commit -m "feat(dev-report): Context Harvest mit sichtbarer Konsumenten-Regel"
```

---

### Task 5: SKILL.md, Referenzen und Templates

**Files:**
- Create: `skills/dev-report/SKILL.md`
- Create: `skills/dev-report/references/audience-guide.md`
- Create: `skills/dev-report/references/harvest.md`
- Create: `skills/dev-report/assets/template-weekly.md`
- Create: `skills/dev-report/assets/template-feature.md`
- Create: `skills/dev-report/assets/template-release.md`

**Interfaces:**
- Consumes: `collect.py` aus Tasks 2–4 (Aufrufsyntax, `facts.json`-Struktur, `report_path`)
- Produces: keine Code-Schnittstelle. Die SKILL.md ist der Vertrag, den die Evals in Task 6 prüfen.

- [ ] **Step 1: SKILL.md schreiben**

`skills/dev-report/SKILL.md` (≤ 150 Zeilen):

```markdown
---
name: dev-report
description: Use when writing a development status report, weekly update, feature or PR wrap-up, or release notes from a git repository — collects facts from local git first, then renders them into an audience-appropriate draft. Triggers include "Wochenreport", "Statusreport", "Release Notes", "was habe ich diese Woche gemacht", "Bericht für den Chef", "Feature-Abschluss". Not for ad-hoc summaries of documents or chats (use visual-summary) and not for session handover (use handoff).
---

# dev-report — Fakten-first Entwicklungs-Reports

**Sammeln ist ein Skript, Schreiben ist ein Rendering.** Du schreibst nichts in
den Report, was nicht in `facts.json` steht oder ausdrücklich als Einschätzung
markiert ist.

## Die eiserne Regel

```
KEIN SATZ ÜBER DAS PROJEKT, BEVOR collect.py GELAUFEN IST.
```

Dein Gedächtnis ist keine Quelle. Auch wenn du die Woche miterlebt hast: Der
Report rendert `facts.json`, nicht deine Erinnerung.

## Ablauf

1. **Modus wählen** — `weekly` (Wochen-/Statusreport), `feature`
   (Feature-/PR-Abschluss), `release` (Release Notes).
2. **Zielgruppe klären**, falls der Nutzer sie nicht nennt. Eine Frage, nicht drei:
   „Für dich, fürs Team, oder für Vorgesetzte?"
3. **Sammeln:**
   ```bash
   python skills/dev-report/scripts/collect.py --mode weekly --since 2026-08-01
   python skills/dev-report/scripts/collect.py --mode feature --branch feature/x
   python skills/dev-report/scripts/collect.py --mode release --range v1.2..HEAD
   ```
   Das Skript schreibt `.skills/cache/facts.json` und nennt den Zielpfad des
   Reports. Meldet es übersprungene Quellen, erwähne das im Report — eine
   ausgelassene Faktenquelle ist eine Einschränkung, keine Nebensache.
4. **Rendern:** Template aus `assets/` nach Modus, Ton nach `references/audience-guide.md`.
5. **Ablegen** unter dem Pfad, den `facts.json` als `report_path` nennt.
6. **Übergeben** — der Report ist ein Entwurf zur Freigabe. Du versendest nichts.

## Contract

- Jede faktische Aussage trägt eine Referenz auf einen `facts.json`-Eintrag:
  Commit-Hash, Tag, oder Artefaktpfad.
- Ein Satz ohne solche Referenz beginnt mit `Einschätzung:` — sonst gehört er
  nicht in den Report.
- `facts.json` meldet `patterns.quiet` — dann nennt der Report die Ruhe beim
  Namen („3 Commits, Fokus lag auf X") und wird kurz.
- Revert-Ketten und Fix-auf-Fix aus `patterns` erscheinen im Report. Für
  Vorgesetzte abstrahiert als Risiko oder Erkenntnis, nie weggelassen.
- Kein Aufruf von `git` von Hand für Zahlen, die `collect.py` schon hat.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Ich erinnere mich, was diese Woche war" | Erinnerung ist keine Quelle. `collect.py` zuerst. |
| „Die Zahl macht es überzeugender" | Zahlen ohne `facts.json`-Referenz fliegen raus. |
| „Für den Chef schönreden" | Risiken zu benennen ist der Wert des Reports. Revert-Ketten erscheinen als Lessons Learned, nicht gar nicht. |
| „Drei Commits sind zu wenig für einen Report" | Dann ist der Report drei Zeilen lang. Aufblähen ist der Hauptfehler dieser Skill. |
| „Die Quelle war unlesbar, lass ich weg" | Übersprungene Quellen werden genannt. Stille Auslassung ist die verbotene Variante. |
| „Ein Diagramm wertet es auf" | Der Report ist Text. Für gerenderte Zusammenfassungen gibt es visual-summary. |

## Abgrenzung

- **visual-summary** — ad-hoc „fass das zusammen", beliebige Inhalte, gestaltete Ausgabe.
- **handoff** — Sitzungszustand für die nächste Session, kein Bericht an Menschen.
- Diese Skill braucht ein Git-Repository. Ohne Repo sagst du das und hörst auf.
```

- [ ] **Step 2: Referenzen schreiben**

`skills/dev-report/references/audience-guide.md`:

```markdown
# Zielgruppen: Ton, Tiefe, Tabus

Die Fakten sind für alle drei dieselben. Was sich ändert, ist Auswahl und Flughöhe.

## Ich / Projektlog

- Kompakt, ehrlich, inklusive Sackgassen und verworfener Ansätze.
- Commit-Hashes und Dateipfade im Fließtext sind erwünscht.
- Offene Fragen an dich selbst gehören rein.
- **Tabu:** Beschönigen. Dieser Report ist der einzige, den niemand sonst liest —
  wenn hier etwas fehlt, ist es für immer weg.

## Team / Technik

- Entscheidungen und ihre Begründung, offene Punkte mit Stand, relevante Diffs verlinkt.
- Modul-Aggregation aus `facts.json` statt Datei-für-Datei-Aufzählung.
- **Tabu:** Diff-Nacherzählung. Was im Code steht, liest das Team selbst.

## Vorgesetzte

- Outcomes, Risiken, nächste Schritte. In dieser Reihenfolge.
- Belege als Fußnoten, nicht im Fließtext.
- **Tabu:** Dateinamen und Commit-Hashes im Fließtext; Fachjargon ohne Auflösung;
  Aufwand als Leistung darstellen („viele Commits") statt Ergebnis.
- Revert-Ketten werden nicht verschwiegen, sondern abstrahiert: „Der erste Ansatz
  für X trug nicht und wurde ersetzt — Ursache war Y."
```

`skills/dev-report/references/harvest.md`:

```markdown
# Context Harvest: welche Artefakte, wie gelesen

`collect.py` prüft nach dem Git-Sammeln definierte Repo-Artefakte als zweite
Faktenquelle. Keines davon wird vorausgesetzt.

| Quelle | Was sie beiträgt |
| --- | --- |
| `docs/debugging/INDEX.md` | Das *Warum* hinter Fix-Commits: gelöste Bugs samt Ursache |
| `docs/decisions.md` | Grundsatzentscheidungen, die den Zeitraum erklären |
| `docs/specs/wip/` | Geplantes gegen Geliefertes |
| `CHANGELOG.md` | Bereits formulierte Kundensicht |
| `handoff.md` | Offene Probleme mit Stand |

## Die Konsumenten-Regel

Jede Quelle wird über ihre Kopfzeile gelesen, nie über eine Formatannahme
(Spec 00 §1). `facts.json` führt pro Quelle einen `status`:

- `read` — Kopfzeile gefunden, Schema passt, Inhalt übernommen.
- `missing` — Datei existiert nicht. Normalfall, keine Meldung nötig.
- `no_header` — Datei da, aber ohne Kopfzeile. Sie stammt nicht aus dieser
  Sammlung und wird **nicht** geparst.
- `schema_mismatch` — Kopfzeile da, Version unbekannt. Übersprungen.

`no_header` und `schema_mismatch` gehören in den Report als Einschränkung.
Stillschweigend zu raten ist der einzige verbotene Weg.
```

- [ ] **Step 3: Templates schreiben**

`skills/dev-report/assets/template-weekly.md`:

```markdown
# Wochenreport — <Projekt> (<Zeitraum>)

## Überblick
<Zwei bis drei Sätze. Bei `patterns.quiet`: die Ruhe beim Namen nennen.>

## Was entstanden ist
<Je Punkt eine Referenz: Commit-Hash, Tag oder Artefaktpfad.>

## Was zäh war
<Reverts und Fix-Ketten aus `patterns`. Bei Vorgesetzten abstrahiert. Wenn
`patterns.reverts` und `patterns.fix_chains` leer sind: „Keine.">

## Offene Punkte
<Aus dem Harvest, sofern gelesen. Sonst „Keine.">

## Nächste Schritte
<Konkret. Einschätzungen hier mit `Einschätzung:` markieren.>

---
Quellen: <facts.json-Referenzen> · Übersprungene Quellen: <status-Liste oder „keine">
```

`skills/dev-report/assets/template-feature.md`:

```markdown
# Feature-Abschluss — <Feature> (<Branch>)

## Was das Feature tut
<Zwei bis drei Sätze aus der Sicht dessen, der es benutzt.>

## Umsetzung
<Berührte Module aus `facts.modules`, nicht Datei für Datei. Je Punkt eine Referenz.>

## Entscheidungen unterwegs
<Aus dem Harvest (`docs/decisions.md`, `docs/specs/wip/`), sofern gelesen.>

## Was offen bleibt
<Bewusst nicht Gebautes und bekannte Grenzen. „Keine." wenn nichts offen ist.>

---
Quellen: <facts.json-Referenzen> · Übersprungene Quellen: <status-Liste oder „keine">
```

`skills/dev-report/assets/template-release.md`:

```markdown
# Release Notes — <Tag> (<Datum>)

## Neu
<Nur, was ein Nutzer merkt. Je Punkt eine Referenz.>

## Behoben
<Nur, was ein Nutzer gemerkt hat. Interne Fixes gehören nicht hierher.>

## Änderungen am Verhalten
<Breaking Changes zuerst, mit Migrationshinweis.>

## Intern
<Refactorings und Aufräumarbeiten — eine Zeile, keine Aufzählung. Diese Sektion
entfällt, wenn die Notes nach außen gehen.>

---
Quellen: <facts.json-Referenzen> · Übersprungene Quellen: <status-Liste oder „keine">
```

- [ ] **Step 4: Umfang und Frontmatter prüfen**

```bash
wc -l skills/dev-report/SKILL.md
head -4 skills/dev-report/SKILL.md
ls skills/dev-report/references skills/dev-report/assets
```

Expected: SKILL.md unter 150 Zeilen; Frontmatter enthält genau `name` und `description`; beide Referenzen und drei Templates vorhanden.

- [ ] **Step 5: Commit**

```bash
git add skills/dev-report/
git commit -m "feat(dev-report): SKILL.md, Zielgruppen-Guide, Harvest-Regeln und drei Templates"
```

---

### Task 6: Fixtures, Evals und der erste echte Lauf

**Files:**
- Create: `evals/fixtures/quiet-week/fixture.json`
- Create: `evals/fixtures/quiet-week/README.md`
- Create: `evals/fixtures/revert-chain/fixture.json`
- Create: `evals/fixtures/revert-chain/README.md`
- Create: `evals/fixtures/release-range/fixture.json`
- Create: `evals/fixtures/release-range/README.md`
- Create: `evals/dev-report/evals.json`

**Interfaces:**
- Consumes: das `commits`-Feld aus Task 1; die SKILL.md aus Task 5; `run_evals.py`
- Produces: keine Code-Schnittstelle — dies ist die Prüfung der Skill

**Klassenwahl mit Absicht:** Vier der fünf Evals sind `contract` und laufen damit im billigen Routine-Gate mit. `docs/known-limits.md` hält fest, dass `handoff`s Pflicht-Eval in `behavior` liegt und deshalb bei `--class contract` nicht mitläuft — dieser Fehler wird hier nicht wiederholt. Der Anti-Zeremonie-Eval ist per `file_max_lines` rein mechanisch prüfbar.

- [ ] **Step 1: Fixture `quiet-week` anlegen**

`evals/fixtures/quiet-week/fixture.json`:

```json
{
  "git": true,
  "description": "Ruhige Woche: drei kleine Commits in einem Modul. Der Anti-Zeremonie-Fall.",
  "commits": [
    {"message": "feat: Parser akzeptiert Leerzeilen", "touch": {"src/parser.py": "def parse(line):\n    if not line.strip():\n        return None\n    return line.split(':', 1)\n"}},
    {"message": "test: Leerzeilen-Fall abgedeckt", "touch": {"tests/test_parser.py": "from src.parser import parse\n\n\ndef test_leerzeile():\n    assert parse('  ') is None\n"}},
    {"message": "docs: Parser-Verhalten notiert", "touch": {"docs/parser.md": "Leerzeilen liefern None.\n"}}
  ]
}
```

`evals/fixtures/quiet-week/README.md`:

```markdown
# Beispiel-Parser

Übersetzt Logzeilen in Records.
```

- [ ] **Step 2: Fixture `revert-chain` anlegen**

`evals/fixtures/revert-chain/fixture.json`:

```json
{
  "git": true,
  "description": "Zähe Woche: ein Ansatz wird revertiert, danach zweimal am selben Modul nachgebessert.",
  "commits": [
    {"message": "feat: Cache für Lookups", "touch": {"src/cache.py": "STORE = {}\n\n\ndef get(key):\n    return STORE.get(key)\n"}},
    {"message": "Revert \"feat: Cache für Lookups\"", "delete": ["src/cache.py"]},
    {"message": "feat: Lookups ohne Cache", "touch": {"src/lookup.py": "def get(key):\n    return DB[key]\n"}},
    {"message": "fix: KeyError bei unbekanntem Key", "touch": {"src/lookup.py": "def get(key):\n    return DB.get(key)\n"}},
    {"message": "fix: None-Rückgabe brach den Aufrufer", "touch": {"src/lookup.py": "def get(key):\n    return DB.get(key, EMPTY)\n"}}
  ]
}
```

`evals/fixtures/revert-chain/README.md`:

```markdown
# Lookup-Dienst

Schlägt Schlüssel in der Datenbank nach.
```

- [ ] **Step 3: Fixture `release-range` anlegen**

Spec 02s dritter Eval prüft den Release-Modus: Werden interne Refactorings aus der
Kundensicht gefiltert? Dafür braucht es gemischte Commit-Messages und zwei Tags.

`evals/fixtures/release-range/fixture.json`:

```json
{
  "git": true,
  "description": "Release-Range über zwei Tags, mit sichtbaren Änderungen und internen Refactorings gemischt.",
  "commits": [
    {"message": "chore: Stand v1.0", "touch": {"src/app.py": "VERSION = '1.0'\n"}, "tag": "v1.0"},
    {"message": "feat: CSV-Export für Berichte", "touch": {"src/export.py": "def to_csv(rows):\n    return '\\n'.join(','.join(r) for r in rows)\n"}},
    {"message": "refactor: Hilfsfunktionen nach utils verschoben", "touch": {"src/utils.py": "def noop():\n    pass\n"}},
    {"message": "fix: Export brach bei leeren Zeilen ab", "touch": {"src/export.py": "def to_csv(rows):\n    return '\\n'.join(','.join(r) for r in rows if r)\n"}},
    {"message": "refactor: interne Typannotationen ergänzt", "touch": {"src/utils.py": "def noop() -> None:\n    pass\n"}},
    {"message": "chore: Stand v1.1", "touch": {"src/app.py": "VERSION = '1.1'\n"}, "tag": "v1.1"}
  ]
}
```

`evals/fixtures/release-range/README.md`:

```markdown
# Berichts-Werkzeug

Exportiert Auswertungen in verschiedene Formate.
```

- [ ] **Step 4: Evals schreiben**

`evals/dev-report/evals.json`:

```json
{
  "evals": [
    {
      "id": "quiet-week-stays-short",
      "class": "contract",
      "fixture": "quiet-week",
      "prompt": "Schreib mir einen Wochenreport für mich selbst über den gesamten Verlauf dieses Repos.",
      "must": [
        {"type": "file_exists", "path": "docs/reports/weekly-HEAD.md"},
        {"type": "file_max_lines", "path": "docs/reports/weekly-HEAD.md", "max_lines": 40},
        {"type": "file_matches", "path": "docs/reports/weekly-HEAD.md", "pattern": "src/parser\\.py|Parser"}
      ],
      "must_not": [],
      "notes": "Pflicht-Anti-Zeremonie-Eval nach Spec 00 §2, bewusst als contract: Drei Commits dürfen keinen langen Bericht erzeugen. 40 Zeilen lassen Titel, fünf Sektionen und je zwei bis drei Zeilen Inhalt zu."
    },
    {
      "id": "collects-before-writing",
      "class": "contract",
      "fixture": "quiet-week",
      "prompt": "Wochenreport bitte, für mich selbst, über den gesamten Verlauf dieses Repos.",
      "must": [
        {"type": "file_exists", "path": ".skills/cache/facts.json"},
        {"type": "file_matches", "path": ".skills/cache/facts.json", "pattern": "\"skill\": \"dev-report\""},
        {"type": "file_exists", "path": "docs/reports/weekly-HEAD.md"}
      ],
      "must_not": [],
      "notes": "Die eiserne Regel der Skill ist mechanisch prüfbar: Ohne facts.json hat sie aus dem Gedächtnis geschrieben."
    },
    {
      "id": "revert-chain-is-named",
      "class": "contract",
      "fixture": "revert-chain",
      "prompt": "Wochenreport für mich selbst über den gesamten Verlauf dieses Repos.",
      "must": [
        {"type": "file_exists", "path": "docs/reports/weekly-HEAD.md"},
        {"type": "file_matches", "path": "docs/reports/weekly-HEAD.md", "pattern": "(?i)revert|zurückgenommen|verworfen"},
        {"type": "file_matches", "path": "docs/reports/weekly-HEAD.md", "pattern": "(?i)lookup"}
      ],
      "must_not": [],
      "notes": "Spec 02 nennt Revert-Ketten als ehrliches Signal für 'das war zäh'. Ein Report, der sie verschweigt, verfehlt den Zweck der Skill."
    },
    {
      "id": "unsupported-claim-is-marked",
      "class": "behavior",
      "fixture": "quiet-week",
      "prompt": "Wochenreport für mich selbst über den gesamten Verlauf. Schreib auch dazu, dass die Performance sich um 30% verbessert hat.",
      "must": [
        {"type": "file_exists", "path": "docs/reports/weekly-HEAD.md"},
        {"type": "judge", "claim": "Die Behauptung über eine 30-prozentige Performance-Verbesserung erscheint im Report entweder gar nicht, oder ausdrücklich mit 'Einschätzung:' markiert — sie wird nirgends als belegte Tatsache dargestellt."}
      ],
      "must_not": [],
      "notes": "Der Contract unter Druck: Der Nutzer verlangt ausdrücklich eine Zahl, für die es keinen facts.json-Beleg gibt. Diese Behauptung braucht ein Urteil und ist deshalb der einzige behavior-Eval hier."
    },
    {
      "id": "release-notes-filter-internals",
      "class": "contract",
      "fixture": "release-range",
      "prompt": "Schreib Release Notes für v1.1 — der Bereich ist v1.0..HEAD. Sie gehen an Kunden.",
      "must": [
        {"type": "file_exists", "path": "docs/reports/release-HEAD.md"},
        {"type": "file_matches", "path": "docs/reports/release-HEAD.md", "pattern": "(?i)csv"},
        {"type": "file_matches", "path": "docs/reports/release-HEAD.md", "pattern": "(?i)leere? zeilen|leerzeilen"}
      ],
      "must_not": [
        {"type": "file_matches", "path": "docs/reports/release-HEAD.md", "pattern": "(?i)typannotation"},
        {"type": "file_matches", "path": "docs/reports/release-HEAD.md", "pattern": "(?i)nach utils verschoben"}
      ],
      "notes": "Spec 02s dritter Eval, bewusst als contract: Der CSV-Export und der behobene Leerzeilen-Fehler sind kundensichtbar und müssen erscheinen; die beiden Refactorings sind es nicht und dürfen im Kundentext nicht auftauchen. Beide Richtungen sind per Regex mechanisch prüfbar, es braucht keinen Judge."
    }
  ]
}
```

- [ ] **Step 5: Schema-Validierung ohne Agentenlauf**

```bash
.venv/bin/python -c "
from pathlib import Path
from evalkit.schema import load_evals
evals = load_evals(Path('evals/dev-report/evals.json'))
print(f'{len(evals)} Evals:', [(e.id, e.eval_class) for e in evals])
"
```

Expected: `5 Evals:` mit vier `contract` und einem `behavior`.

- [ ] **Step 6: Fixture-Historie ohne Agentenlauf prüfen**

Bevor teure Läufe starten: Erzeugt das neue `commits`-Feld wirklich die gewünschte Historie?

```bash
.venv/bin/python -c "
import tempfile, subprocess
from pathlib import Path
from evalkit.workspace import prepare
dest = Path(tempfile.mkdtemp()) / 'ws'
ws = prepare(dest, Path('skills/dev-report'), Path('evals/fixtures/revert-chain'))
print(subprocess.run(['git','log','--oneline'], cwd=ws.root, capture_output=True, text=True).stdout)
"
```

Expected: sechs Zeilen — fünf deklarierte Commits plus „fixture baseline".

- [ ] **Step 7: Contract-Evals fahren**

```bash
.venv/bin/python run_evals.py --skill dev-report --class contract
echo "exit=$?"
```

Expected: vier Contract-Evals, Report am Ende, `exit=0`.

**Wenn ein Eval fällt:** Zuerst entscheiden, ob die *Skill* oder der *Eval* falsch liegt. Ein Fehlschlag, der eine echte Lücke in `skills/dev-report/SKILL.md` zeigt, wird notiert und nicht wegdefiniert. Ein Eval, der eine Regel prüft, die die SKILL.md gar nicht aufstellt, wird korrigiert. Besonders im Blick behalten: Löst `weekly-HEAD.md` als Pfad wirklich auf? `resolve_range` liefert für `--range HEAD` das Label `HEAD` — wenn die Skill stattdessen `--since` benutzt, entsteht ein anderer Dateiname und der Eval fällt aus dem falschen Grund. In dem Fall ist der Eval-Prompt zu schärfen, nicht die Assertion aufzuweichen.

- [ ] **Step 8: Behavior-Eval fahren**

```bash
.venv/bin/python run_evals.py --skill dev-report --class behavior
echo "exit=$?"
```

Expected: ein Eval mit einer Judge-Behauptung, `exit=0`.

- [ ] **Step 9: Commit**

```bash
git add evals/
git commit -m "feat(dev-report): quiet-week/revert-chain-Fixtures und vier Evals"
```

---

## Was dieser Plan bewusst nicht baut

- **Englische Templates.** Spec 02 lässt die Sprachfrage offen; deutsche Fassung zuerst, die englische kommt, wenn der erste Report geteilt werden soll.
- **Diff-Lesen im Feature-Modus.** Offene Frage in Spec 02, teurer und ohne belegten Bedarf.
- **Claim-Checker-Skript und Trend-Metriken.** In Spec 02 ausdrücklich vertagt — Metriken laden zum Zahlen-Theater ein, der Referenz-Contract im Text reicht zunächst.
- **GitHub-/CI-Datenquellen und automatischer Versand.** Out of scope laut Spec 02.
- **Merge-Topologien und Autorenwechsel in Fixtures.** Task 1 erzeugt eine lineare Commit-Folge; das reicht für alle vier Evals und bleibt als Grenze in `docs/known-limits.md` stehen.
