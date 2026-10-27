# Eval-Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Einen geteilten Eval-Runner bauen, der eine Skill in einem Wegwerf-Workspace gegen falsifizierbare Assertions laufen lässt — plus die zwei Konventions-Dokumente, die Spec 00 noch schuldet.

**Architecture:** `run_evals.py` ist ein dünnes CLI über dem Paket `evalkit/`. Pro Eval wird ein Fixture in ein Temp-Verzeichnis kopiert, die zu testende Skill als Projekt-Skill hineingelegt, ein frischer `claude -p`-Prozess darin gestartet und sein Transcript eingesammelt. Mechanische Assertions (Datei da? Kopfzeile korrekt? HEAD unverändert?) werden direkt im Dateisystem geprüft; nur `judge`-Assertions kosten einen zweiten Agenten. Die Trennung ist der Kostenhebel aus Spec 00 §2: Contract-Evals laufen ohne Judge und damit billig.

**Tech Stack:** Python 3.13 (Stdlib), pytest als reine Dev-Abhängigkeit, Claude Code CLI 2.1.232 als Agent-Prozess.

**Spec:** `specs/Spec 00 – skill-foundation.md`

## Global Constraints

- **Tier 1 (Spec 00 §3):** `run_evals.py` und alles unter `evalkit/` importieren ausschließlich die Python-Stdlib. pytest ist Dev-Abhängigkeit und darf nie aus Produktivcode importiert werden.
- **Bestehens-Regel (Spec 00 §2):** Bestanden = alle `must` erfüllt und kein `must_not` verletzt. Kein Teilkredit, keine Punktzahl.
- **Assertions sind falsifizierbare Beobachtungen, nie Stimmungsurteile** (Spec 00 §2).
- **Contract-Evals dürfen keine `judge`-Assertion enthalten** — genau das macht sie billig. Das Schema erzwingt es.
- **Jede Skill braucht mindestens einen Anti-Zeremonie-Eval** (Spec 00 §2).
- **Fixtures sind minimal-synthetisch, 10–50 Dateien** (Spec 00 §2). Sie sollen die Falle enthalten, nicht Realismus beweisen.
- **Kopfzeilen-Format (Spec 00 §1, hier konkretisiert):** erste nicht-leere Zeile eines erzeugten Artefakts lautet
  `<!-- skill: <name> | schema: <n> | generated: <kommando> -->` (Markdown) bzw. `# skill: <name> | schema: <n> | generated: <kommando>` (YAML).
- **Ephemera nach `.skills/cache/`, gitignored** (Spec 00 §1). Eval-Workspaces liegen unter `tempfile`, nie im Repo.
- **Dokumentsprache Deutsch, Bezeichner in Code und Schema englisch** (Spec 00 Constraints).

### Zwei bewusste Abweichungen von Spec 00s „Next steps"

1. **Erster echter Lauf gegen `handoff`, nicht gegen Spec 01.** Spec 00 will den Runner „gegen die vier Evals aus Spec 01 als erste echte Last" fahren. Die Skill `debug-ledger` existiert noch nicht — man kann keine Skill evaluieren, die nicht gebaut ist. `handoff` ist gebaut, erzeugt ein Datei-Artefakt und hat einen scharf formulierten Contract (sechs Sektionen, ≤150 Zeilen, CLAUDE.md nie anfassen, kein Commit). Damit ist es die bessere erste Last und sofort verfügbar.
2. **Fixtures `legacy-monolith` und `cyclic-imports` werden vertagt.** Sie bedienen die Specs 05 und 10, die es noch nicht gibt. Gebaut wird der Fixture-*Mechanismus* plus das eine Fixture, das die handoff-Evals wirklich brauchen. YAGNI.

3. **`handoff.md` bekommt keine Artefakt-Kopfzeile.** Spec 00 §1 verlangt sie für jedes erzeugte Artefakt; das in `skills/handoff/SKILL.md` fixierte Format beginnt aber mit `# Handoff — …`. Die Ausnahme ist vertretbar — `handoff.md` hat genau zwei Konsumenten, die nächste Session und den Menschen, und beide brauchen keine Schema-Version, um sie zu lesen. Sie wird hier festgehalten, damit niemand später pflichtschuldig eine `artifact_header`-Assertion ergänzt und sich über den roten Eval wundert. Sobald ein *drittes* Werkzeug `handoff.md` parst, kippt die Abwägung und die Kopfzeile kommt ins Format.
4. **Kleinere Layout-Abweichungen.** Spec 00 §2 skizziert `run_evals.py` unter `evals/`; der Plan legt es ins Repo-Root, weil es das Paket `evalkit/` importiert und ein Skript im Root ohne Pfadakrobatik läuft. Die Next steps nennen `references/artifact-header.md` — Spec 00 ist aber keine Skill und hat kein `references/`, deshalb `docs/artifact-header.md`. Und die Fixtures unterschreiten die als Global Constraint zitierte Größe „10–50 Dateien" deutlich (5 bzw. 0 Dateien): Die Zahl war als Obergrenze gegen echte Repos gemeint, nicht als Mindestgröße — kleiner ist besser, solange die Falle drinsteckt.

### Eine offene Frage aus Spec 00, die dieser Plan beantwortet

Spec 00 fragt: „Braucht der Eval-Runner echte Worktrees pro Eval (sauber, langsam) oder reichen Kopien der Fixture-Ordner?" **Dieser Plan wählt Kopien** (`shutil.copytree` in ein `tempfile`-Verzeichnis, danach optional `git init`). Begründung: Ein Worktree setzt ein Repo voraus, aus dem er abzweigt — Fixtures sind aber synthetische Verzeichnisse ohne Vorgeschichte. Die Kopie ist einfacher, schneller und erlaubt Fixtures ganz ohne Git (`empty-dir`). Fixtures, die echte Historie brauchen (Spec 05s Legacy-Erkennung liest „alte, große Historie"), sprengen dieses Modell — dann kommt ein `commits`-Feld ins Fixture-Manifest. Bis dahin ist das YAGNI.

---

### Task 1: Projekt-Setup und Eval-Schema

**Files:**
- Create: `pyproject.toml`
- Create: `evalkit/__init__.py`
- Create: `evalkit/schema.py`
- Create: `tests/test_schema.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nichts (erste Task)
- Produces:
  - `evalkit.schema.Assertion(type: str, path: str | None, pattern: str | None, claim: str | None, max_lines: int | None)` — frozen dataclass
  - `evalkit.schema.Eval(id: str, eval_class: str, prompt: str, must: tuple[Assertion, ...], must_not: tuple[Assertion, ...], fixture: str | None, notes: str)` — frozen dataclass
  - `evalkit.schema.EvalSchemaError(ValueError)`
  - `evalkit.schema.load_evals(path: pathlib.Path) -> tuple[Eval, ...]`
  - `evalkit.schema.MECHANICAL_TYPES: frozenset[str]`, `evalkit.schema.JUDGE_TYPE: str`

- [ ] **Step 1: Projektgerüst anlegen**

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "evaluated-skills-evals"
version = "0.1.0"
description = "Geteilter Eval-Harness für die Skill-Sammlung (Spec 00 §2)"
requires-python = ">=3.13"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.0"]

# Explizit statt Autodiscovery: Im Repo-Root liegen skills/, specs/, docs/ und
# später evals/. Setuptools' Flat-Layout-Suche würde daran mit "Multiple
# top-level packages discovered" scheitern.
[tool.setuptools]
packages = ["evalkit"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`.gitignore` um diese Zeilen ergänzen (die bestehende Zeile `_in/` bleibt):

```
.venv/
__pycache__/
*.pyc
.skills/cache/
.pytest_cache/
```

Dann:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

- [ ] **Step 2: Write the failing test**

`tests/test_schema.py`:

```python
import json
import pytest
from evalkit.schema import Assertion, Eval, EvalSchemaError, load_evals


def write(tmp_path, payload):
    path = tmp_path / "evals.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


MINIMAL = {
    "evals": [
        {
            "id": "handoff-creates-file",
            "class": "contract",
            "prompt": "Wir hören hier auf für heute.",
            "must": [{"type": "file_exists", "path": "handoff.md"}],
        }
    ]
}


def test_loads_minimal_eval(tmp_path):
    evals = load_evals(write(tmp_path, MINIMAL))
    assert len(evals) == 1
    assert evals[0] == Eval(
        id="handoff-creates-file",
        eval_class="contract",
        prompt="Wir hören hier auf für heute.",
        must=(Assertion(type="file_exists", path="handoff.md"),),
        must_not=(),
        fixture=None,
        notes="",
    )


def test_rejects_contract_eval_with_judge_assertion(tmp_path):
    payload = {
        "evals": [
            {
                "id": "x",
                "class": "contract",
                "prompt": "p",
                "must": [{"type": "judge", "claim": "es ist gut"}],
            }
        ]
    }
    with pytest.raises(EvalSchemaError, match="contract"):
        load_evals(write(tmp_path, payload))


def test_rejects_empty_must(tmp_path):
    payload = {"evals": [{"id": "x", "class": "behavior", "prompt": "p", "must": []}]}
    with pytest.raises(EvalSchemaError, match="must"):
        load_evals(write(tmp_path, payload))


def test_rejects_duplicate_ids(tmp_path):
    ev = {"id": "same", "class": "contract", "prompt": "p",
          "must": [{"type": "file_exists", "path": "a"}]}
    with pytest.raises(EvalSchemaError, match="doppelt"):
        load_evals(write(tmp_path, {"evals": [ev, dict(ev)]}))


def test_rejects_file_matches_without_pattern(tmp_path):
    payload = {
        "evals": [
            {"id": "x", "class": "contract", "prompt": "p",
             "must": [{"type": "file_matches", "path": "a.md"}]}
        ]
    }
    with pytest.raises(EvalSchemaError, match="pattern"):
        load_evals(write(tmp_path, payload))


def test_rejects_invalid_regex_pattern(tmp_path):
    """Eine kaputte Regex muss beim Laden auffallen, nicht nach dem Agentenlauf."""
    payload = {
        "evals": [
            {"id": "x", "class": "contract", "prompt": "p",
             "must": [{"type": "file_matches", "path": "a.md", "pattern": "^## Status ["}]}
        ]
    }
    with pytest.raises(EvalSchemaError, match="Regex"):
        load_evals(write(tmp_path, payload))


def test_output_matches_needs_pattern_not_path(tmp_path):
    payload = {
        "evals": [
            {"id": "x", "class": "contract", "prompt": "p",
             "must": [{"type": "output_matches"}]}
        ]
    }
    with pytest.raises(EvalSchemaError, match="pattern"):
        load_evals(write(tmp_path, payload))


def test_rejects_unknown_assertion_type(tmp_path):
    payload = {
        "evals": [
            {"id": "x", "class": "contract", "prompt": "p",
             "must": [{"type": "vibes_good", "path": "a"}]}
        ]
    }
    with pytest.raises(EvalSchemaError, match="vibes_good"):
        load_evals(write(tmp_path, payload))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_schema.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'evalkit'`

- [ ] **Step 4: Write minimal implementation**

`evalkit/__init__.py`:

```python
"""Geteilter Eval-Harness für die Skill-Sammlung. Tier 1: nur Stdlib."""
```

`evalkit/schema.py`:

```python
"""Eval-Definitionen laden und validieren (Spec 00 §2). Tier 1: nur Stdlib."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

JUDGE_TYPE = "judge"
MECHANICAL_TYPES = frozenset({
    "file_exists",
    "file_absent",
    "file_matches",
    "file_unchanged",
    "file_max_lines",
    "artifact_header",
    "git_head_unchanged",
    "output_matches",
})
ASSERTION_TYPES = MECHANICAL_TYPES | {JUDGE_TYPE}
EVAL_CLASSES = frozenset({"contract", "behavior"})

_NEEDS_PATH = MECHANICAL_TYPES - {"git_head_unchanged", "output_matches"}
_NEEDS_PATTERN = frozenset({"file_matches", "output_matches"})


class EvalSchemaError(ValueError):
    """Eine evals.json verletzt das Schema aus Spec 00 §2."""


@dataclass(frozen=True)
class Assertion:
    type: str
    path: str | None = None
    pattern: str | None = None
    claim: str | None = None
    max_lines: int | None = None


@dataclass(frozen=True)
class Eval:
    id: str
    eval_class: str
    prompt: str
    must: tuple[Assertion, ...]
    must_not: tuple[Assertion, ...] = ()
    fixture: str | None = None
    notes: str = ""


def _parse_assertion(raw: object, where: str) -> Assertion:
    if not isinstance(raw, dict):
        raise EvalSchemaError(f"{where}: Assertion muss ein Objekt sein, war {type(raw).__name__}")
    kind = raw.get("type")
    if kind not in ASSERTION_TYPES:
        raise EvalSchemaError(f"{where}: unbekannter Assertion-Typ {kind!r}")
    if kind in _NEEDS_PATH and not raw.get("path"):
        raise EvalSchemaError(f"{where}: Typ {kind!r} braucht ein 'path'")
    if kind in _NEEDS_PATTERN:
        pattern = raw.get("pattern")
        if not pattern:
            raise EvalSchemaError(f"{where}: Typ {kind!r} braucht ein 'pattern'")
        try:
            re.compile(pattern)
        except re.error as exc:
            # Sonst fliegt die Regex erst beim Grading — nach dem teuren Agentenlauf.
            raise EvalSchemaError(f"{where}: 'pattern' ist keine gültige Regex — {exc}") from exc
    if kind == "file_max_lines" and not isinstance(raw.get("max_lines"), int):
        raise EvalSchemaError(f"{where}: Typ 'file_max_lines' braucht ein ganzzahliges 'max_lines'")
    if kind == JUDGE_TYPE and not raw.get("claim"):
        raise EvalSchemaError(f"{where}: Typ 'judge' braucht ein 'claim'")
    return Assertion(
        type=kind,
        path=raw.get("path"),
        pattern=raw.get("pattern"),
        claim=raw.get("claim"),
        max_lines=raw.get("max_lines"),
    )


def _parse_eval(raw: object, index: int) -> Eval:
    where = f"eval[{index}]"
    if not isinstance(raw, dict):
        raise EvalSchemaError(f"{where}: Eval muss ein Objekt sein")
    eval_id = raw.get("id")
    if not eval_id or not isinstance(eval_id, str):
        raise EvalSchemaError(f"{where}: 'id' fehlt oder ist leer")
    where = f"eval[{eval_id}]"
    eval_class = raw.get("class")
    if eval_class not in EVAL_CLASSES:
        raise EvalSchemaError(f"{where}: 'class' muss eine von {sorted(EVAL_CLASSES)} sein, war {eval_class!r}")
    prompt = raw.get("prompt")
    if not prompt or not isinstance(prompt, str):
        raise EvalSchemaError(f"{where}: 'prompt' fehlt oder ist leer")

    must = tuple(_parse_assertion(a, f"{where}.must") for a in raw.get("must", []))
    if not must:
        raise EvalSchemaError(f"{where}: 'must' darf nicht leer sein — ein Eval ohne Muss-Assertion behauptet nichts")
    must_not = tuple(_parse_assertion(a, f"{where}.must_not") for a in raw.get("must_not", []))

    if eval_class == "contract":
        for assertion in (*must, *must_not):
            if assertion.type == JUDGE_TYPE:
                raise EvalSchemaError(
                    f"{where}: contract-Evals dürfen keine judge-Assertion enthalten (Spec 00 §2) — "
                    f"nimm class 'behavior', wenn du ein Urteil brauchst"
                )

    return Eval(
        id=eval_id,
        eval_class=eval_class,
        prompt=prompt,
        must=must,
        must_not=must_not,
        fixture=raw.get("fixture"),
        notes=raw.get("notes", ""),
    )


def load_evals(path: Path) -> tuple[Eval, ...]:
    """Lade und validiere eine evals.json. Wirft EvalSchemaError bei jedem Verstoß."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvalSchemaError(f"{path}: kein gültiges JSON — {exc}") from exc

    raw_evals = payload.get("evals") if isinstance(payload, dict) else None
    if not isinstance(raw_evals, list):
        raise EvalSchemaError(f"{path}: erwartet ein Objekt mit der Liste 'evals'")

    evals = tuple(_parse_eval(raw, i) for i, raw in enumerate(raw_evals))

    seen: set[str] = set()
    for ev in evals:
        if ev.id in seen:
            raise EvalSchemaError(f"{path}: Eval-ID {ev.id!r} ist doppelt vergeben")
        seen.add(ev.id)
    return evals
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_schema.py -v`
Expected: PASS, 8 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore evalkit/__init__.py evalkit/schema.py tests/test_schema.py
git commit -m "feat(evals): Eval-Schema und Loader nach Spec 00 §2"
```

---

### Task 2: Mechanische Assertions

**Files:**
- Create: `evalkit/assertions.py`
- Create: `tests/test_assertions.py`

**Interfaces:**
- Consumes: `evalkit.schema.Assertion`, `evalkit.schema.JUDGE_TYPE`
- Produces:
  - `evalkit.assertions.AssertionResult(ok: bool, detail: str)` — frozen dataclass
  - `evalkit.assertions.ARTIFACT_HEADER_RE: re.Pattern[str]`
  - `evalkit.assertions.GIT_HEAD_KEY: str` — Sonderschlüssel `"__git_head__"` in der Baseline
  - `evalkit.assertions.check(assertion: Assertion, root: pathlib.Path, baseline: dict[str, str], output: str = "") -> AssertionResult`
  - `evalkit.assertions.file_sha256(path: pathlib.Path) -> str`
  - `evalkit.assertions.current_git_head(root: pathlib.Path) -> str | None`
  - `evalkit.assertions.MechanicalCheckError(RuntimeError)` — wenn eine `judge`-Assertion hierher gerät

- [ ] **Step 1: Write the failing test**

`tests/test_assertions.py`:

```python
import pytest
from evalkit.assertions import ARTIFACT_HEADER_RE, MechanicalCheckError, check
from evalkit.schema import Assertion

BASELINE = {"stable.md": "abc123", "__git_head__": "deadbeef"}


def test_file_exists_true(tmp_path):
    (tmp_path / "handoff.md").write_text("x", encoding="utf-8")
    result = check(Assertion(type="file_exists", path="handoff.md"), tmp_path, BASELINE)
    assert result.ok


def test_file_exists_false(tmp_path):
    result = check(Assertion(type="file_exists", path="handoff.md"), tmp_path, BASELINE)
    assert not result.ok
    assert "handoff.md" in result.detail


def test_file_absent(tmp_path):
    assert check(Assertion(type="file_absent", path="handoff.md"), tmp_path, BASELINE).ok
    (tmp_path / "handoff.md").write_text("x", encoding="utf-8")
    assert not check(Assertion(type="file_absent", path="handoff.md"), tmp_path, BASELINE).ok


def test_file_matches_is_multiline(tmp_path):
    (tmp_path / "h.md").write_text("# Titel\n## Status\nfoo\n", encoding="utf-8")
    assert check(Assertion(type="file_matches", path="h.md", pattern=r"^## Status$"), tmp_path, BASELINE).ok
    assert not check(Assertion(type="file_matches", path="h.md", pattern=r"^## Fehlt$"), tmp_path, BASELINE).ok


def test_file_matches_on_missing_file_is_failure(tmp_path):
    result = check(Assertion(type="file_matches", path="nope.md", pattern="x"), tmp_path, BASELINE)
    assert not result.ok
    assert "existiert nicht" in result.detail


def test_file_max_lines(tmp_path):
    (tmp_path / "h.md").write_text("\n".join(str(i) for i in range(10)), encoding="utf-8")
    assert check(Assertion(type="file_max_lines", path="h.md", max_lines=10), tmp_path, BASELINE).ok
    assert not check(Assertion(type="file_max_lines", path="h.md", max_lines=9), tmp_path, BASELINE).ok


def test_file_unchanged(tmp_path):
    target = tmp_path / "stable.md"
    target.write_text("original", encoding="utf-8")
    baseline = {"stable.md": __import__("hashlib").sha256(b"original").hexdigest()}
    assert check(Assertion(type="file_unchanged", path="stable.md"), tmp_path, baseline).ok
    target.write_text("angefasst", encoding="utf-8")
    assert not check(Assertion(type="file_unchanged", path="stable.md"), tmp_path, baseline).ok


def test_file_unchanged_without_baseline_entry_fails_loudly(tmp_path):
    """Datei da, aber nicht in der Baseline: der Agent hat sie im Lauf angelegt."""
    (tmp_path / "unknown.md").write_text("neu", encoding="utf-8")
    result = check(Assertion(type="file_unchanged", path="unknown.md"), tmp_path, {})
    assert not result.ok
    assert "Baseline" in result.detail


def test_output_matches_reads_agent_stdout(tmp_path):
    assertion = Assertion(type="output_matches", pattern=r"\?")
    assert check(assertion, tmp_path, BASELINE, output="Soll ich das anlegen?").ok
    assert not check(assertion, tmp_path, BASELINE, output="Erledigt.").ok


def test_artifact_header_markdown(tmp_path):
    (tmp_path / "a.md").write_text(
        "<!-- skill: debug-ledger | schema: 1 | generated: python scripts/new_ledger.py -->\n# Ledger\n",
        encoding="utf-8",
    )
    assert check(Assertion(type="artifact_header", path="a.md"), tmp_path, BASELINE).ok


def test_artifact_header_yaml(tmp_path):
    (tmp_path / "a.yaml").write_text(
        "# skill: rest-api-architect | schema: 2 | generated: python scripts/gen_ruleset.py\nrules: []\n",
        encoding="utf-8",
    )
    assert check(Assertion(type="artifact_header", path="a.yaml"), tmp_path, BASELINE).ok


def test_artifact_header_missing(tmp_path):
    (tmp_path / "a.md").write_text("# Ledger ohne Kopfzeile\n", encoding="utf-8")
    result = check(Assertion(type="artifact_header", path="a.md"), tmp_path, BASELINE)
    assert not result.ok
    assert "Kopfzeile" in result.detail


def test_artifact_header_regex_captures_fields():
    match = ARTIFACT_HEADER_RE.match("<!-- skill: dev-report | schema: 3 | generated: python x.py --mode weekly -->")
    assert match.group("skill") == "dev-report"
    assert match.group("schema") == "3"
    assert match.group("cmd") == "python x.py --mode weekly"


def test_git_head_unchanged(tmp_path):
    baseline = {"__git_head__": "abc"}
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD_SHA").write_text("abc", encoding="utf-8")
    assert check(Assertion(type="git_head_unchanged"), tmp_path, baseline).ok
    (tmp_path / ".git" / "HEAD_SHA").write_text("xyz", encoding="utf-8")
    assert not check(Assertion(type="git_head_unchanged"), tmp_path, baseline).ok


def test_judge_assertion_is_rejected_here(tmp_path):
    with pytest.raises(MechanicalCheckError):
        check(Assertion(type="judge", claim="gut"), tmp_path, BASELINE)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_assertions.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'evalkit.assertions'`

- [ ] **Step 3: Write minimal implementation**

`evalkit/assertions.py`:

```python
"""Mechanische Assertions — falsifizierbar, ohne Judge, ohne Kosten. Tier 1: nur Stdlib."""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from evalkit.schema import Assertion, JUDGE_TYPE

# Kopfzeilen-Format aus Spec 00 §1, hier verbindlich gemacht.
ARTIFACT_HEADER_RE = re.compile(
    r"^(?:<!--|#)\s*skill:\s*(?P<skill>[a-z0-9][a-z0-9-]*)\s*\|"
    r"\s*schema:\s*(?P<schema>\d+)\s*\|"
    r"\s*generated:\s*(?P<cmd>.+?)\s*(?:-->)?\s*$"
)

GIT_HEAD_KEY = "__git_head__"


class MechanicalCheckError(RuntimeError):
    """Eine Assertion, die hier nicht mechanisch prüfbar ist (z. B. judge)."""


@dataclass(frozen=True)
class AssertionResult:
    ok: bool
    detail: str


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_git_head(root: Path) -> str | None:
    """SHA von HEAD, oder None wenn kein Repo / kein Commit.

    Der Testpfad .git/HEAD_SHA existiert, damit Unit-Tests ohne echtes Repo
    auskommen; im echten Lauf gewinnt immer `git rev-parse`.
    """
    probe = root / ".git" / "HEAD_SHA"
    if probe.is_file():
        return probe.read_text(encoding="utf-8").strip()
    try:
        done = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def check(assertion: Assertion, root: Path, baseline: dict[str, str], output: str = "") -> AssertionResult:
    """Prüfe eine mechanische Assertion gegen den Workspace.

    `baseline` ist der Snapshot aus evalkit.workspace.prepare(): relpath -> sha256,
    plus der Sonderschlüssel `__git_head__`. `output` ist die Agent-Ausgabe — nötig,
    weil manche Contracts sich auf das Gesagte beziehen ("fragt nach, statt anzulegen").
    """
    if assertion.type == JUDGE_TYPE:
        raise MechanicalCheckError("judge-Assertions gehören zu evalkit.judge, nicht hierher")

    if assertion.type == "output_matches":
        hit = re.search(assertion.pattern, output, re.MULTILINE)
        return AssertionResult(bool(hit), f"Agent-Ausgabe: Muster {assertion.pattern!r} {'gefunden' if hit else 'nicht gefunden'}")

    if assertion.type == "git_head_unchanged":
        before = baseline.get(GIT_HEAD_KEY)
        after = current_git_head(root)
        if before is None:
            return AssertionResult(False, "kein Git-HEAD in der Baseline — Fixture ohne Repo?")
        if before == after:
            return AssertionResult(True, f"HEAD unverändert ({before[:8]})")
        return AssertionResult(False, f"HEAD verändert: {before[:8]} → {(after or 'None')[:8]}")

    target = root / assertion.path
    exists = target.is_file()

    if assertion.type == "file_exists":
        return AssertionResult(exists, f"{assertion.path} {'existiert' if exists else 'existiert nicht'}")

    if assertion.type == "file_absent":
        return AssertionResult(not exists, f"{assertion.path} {'existiert (unerwünscht)' if exists else 'fehlt wie erwartet'}")

    if not exists:
        return AssertionResult(False, f"{assertion.path} existiert nicht")

    if assertion.type == "file_matches":
        text = target.read_text(encoding="utf-8", errors="replace")
        hit = re.search(assertion.pattern, text, re.MULTILINE)
        return AssertionResult(bool(hit), f"{assertion.path}: Muster {assertion.pattern!r} {'gefunden' if hit else 'nicht gefunden'}")

    if assertion.type == "file_max_lines":
        count = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
        return AssertionResult(count <= assertion.max_lines, f"{assertion.path}: {count} Zeilen (erlaubt {assertion.max_lines})")

    if assertion.type == "file_unchanged":
        before = baseline.get(assertion.path)
        if before is None:
            return AssertionResult(False, f"{assertion.path}: nicht in der Baseline — vor dem Lauf existierte die Datei nicht")
        after = file_sha256(target)
        return AssertionResult(before == after, f"{assertion.path}: {'unverändert' if before == after else 'verändert'}")

    if assertion.type == "artifact_header":
        for line in target.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                ok = bool(ARTIFACT_HEADER_RE.match(line.strip()))
                return AssertionResult(ok, f"{assertion.path}: Kopfzeile {'korrekt' if ok else 'fehlt oder falsch formatiert'} ({line.strip()[:60]!r})")
        return AssertionResult(False, f"{assertion.path}: leer, keine Kopfzeile")

    raise MechanicalCheckError(f"kein Prüfpfad für Typ {assertion.type!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_assertions.py -v`
Expected: PASS, 15 passed

- [ ] **Step 5: Commit**

```bash
git add evalkit/assertions.py tests/test_assertions.py
git commit -m "feat(evals): mechanische Assertions inkl. Kopfzeilen-Format aus Spec 00 §1"
```

---

### Task 3: Workspace-Vorbereitung und Baseline

> **Nachtrag (Schluss-Review, 2026-08-14):** Der Implementierungscode in Step 3
> unten (`_git()` und `prepare()`) ist die **ungefixte Fassung** und im Repo
> längst korrigiert. Zwei Fehler, die dieser Plan-Text noch enthält:
> `_git()` übersetzt einen fehlgeschlagenen Prozessstart nicht in
> `WorkspaceError` (`subprocess.run` kann roh durchschlagen, wenn `git` selbst
> fehlt); und `prepare()` installiert die Skill **vor** dem Baseline-Commit,
> sodass sie mit in „fixture baseline" landet — ein Agent, der sich per
> `git log`/`git status` erdet, hält die Installationsspuren des Harness dann
> für Projektinhalt. Siehe `evalkit/workspace.py` im Repo für den korrigierten
> Stand (Commits nach `b4a993e`). Wer diesen Plan erneut ausführt, muss beide
> Fehler NICHT erneut einbauen.

**Files:**
- Create: `evalkit/workspace.py`
- Create: `tests/test_workspace.py`

**Interfaces:**
- Consumes: `evalkit.assertions.file_sha256`, `evalkit.assertions.current_git_head`, `evalkit.assertions.GIT_HEAD_KEY`
- Produces:
  - `evalkit.workspace.Workspace(root: pathlib.Path, baseline: dict[str, str])` — frozen dataclass
  - `evalkit.workspace.prepare(dest: pathlib.Path, skill_dir: pathlib.Path, fixture_dir: pathlib.Path | None) -> Workspace`
  - `evalkit.workspace.snapshot(root: pathlib.Path) -> dict[str, str]`
  - `evalkit.workspace.dump_changed_files(root: pathlib.Path, baseline: dict[str, str], *, max_bytes: int = 20_000) -> str`
  - `evalkit.workspace.WorkspaceError(RuntimeError)`

- [ ] **Step 1: Write the failing test**

`tests/test_workspace.py`:

```python
import json
import pytest
from evalkit.workspace import WorkspaceError, dump_changed_files, prepare, snapshot


def make_skill(tmp_path, name="handoff"):
    skill = tmp_path / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n", encoding="utf-8")
    return skill


def make_fixture(tmp_path, *, git=True, name="dirty-worktree"):
    fixture = tmp_path / "fixtures" / name
    fixture.mkdir(parents=True)
    (fixture / "fixture.json").write_text(json.dumps({"git": git, "description": "test"}), encoding="utf-8")
    (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
    (fixture / "CLAUDE.md").write_text("# Konventionen\n", encoding="utf-8")
    return fixture


def test_copies_fixture_content(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    assert (ws.root / "README.md").is_file()
    assert (ws.root / "CLAUDE.md").is_file()


def test_installs_skill_as_project_skill(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    installed = ws.root / ".claude" / "skills" / "handoff" / "SKILL.md"
    assert installed.is_file()
    assert "name: handoff" in installed.read_text(encoding="utf-8")


def test_fixture_json_is_not_copied_into_workspace(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    assert not (ws.root / "fixture.json").exists()


def test_git_fixture_gets_repo_with_one_commit(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path, git=True))
    assert (ws.root / ".git").is_dir()
    assert ws.baseline["__git_head__"]


def test_non_git_fixture_has_no_repo(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path, git=False))
    assert not (ws.root / ".git").exists()
    assert ws.baseline["__git_head__"] is None


def test_baseline_hashes_fixture_files_but_not_dot_git(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    assert "CLAUDE.md" in ws.baseline
    assert not any(key.startswith(".git/") for key in ws.baseline)


def test_baseline_excludes_installed_skill(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    assert not any(key.startswith(".claude/") for key in ws.baseline)


def test_prepare_without_fixture_creates_empty_workspace(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), None)
    assert ws.root.is_dir()
    assert list(ws.root.iterdir()) == [ws.root / ".claude"]


def test_missing_skill_dir_raises(tmp_path):
    with pytest.raises(WorkspaceError, match="Skill"):
        prepare(tmp_path / "ws", tmp_path / "nope", None)


def test_snapshot_is_stable_for_unchanged_tree(tmp_path):
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    assert snapshot(tmp_path) == snapshot(tmp_path)


def test_dump_changed_files_shows_only_new_and_changed(tmp_path):
    """Der Judge urteilt über Artefakte — er braucht deren Inhalt, nicht das ganze Repo."""
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    (ws.root / "handoff.md").write_text("# Handoff\n## Status\nfoo\n", encoding="utf-8")
    dump = dump_changed_files(ws.root, ws.baseline)
    assert "handoff.md" in dump
    assert "## Status" in dump
    assert "CLAUDE.md" not in dump


def test_dump_changed_files_reports_when_nothing_changed(tmp_path):
    ws = prepare(tmp_path / "ws", make_skill(tmp_path), make_fixture(tmp_path))
    assert "keine Datei" in dump_changed_files(ws.root, ws.baseline)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_workspace.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'evalkit.workspace'`

- [ ] **Step 3: Write minimal implementation**

`evalkit/workspace.py`:

```python
"""Wegwerf-Workspace pro Eval: Fixture kopieren, Skill installieren, Baseline ziehen."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from evalkit.assertions import GIT_HEAD_KEY, current_git_head, file_sha256

EXCLUDED_PREFIXES = (".git/", ".claude/")
FIXTURE_MANIFEST = "fixture.json"


class WorkspaceError(RuntimeError):
    """Der Workspace konnte nicht aufgebaut werden."""


@dataclass(frozen=True)
class Workspace:
    root: Path
    baseline: dict[str, str]


def snapshot(root: Path) -> dict[str, str]:
    """relpath -> sha256 für alle Dateien außerhalb von .git/ und .claude/."""
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(EXCLUDED_PREFIXES):
            continue
        result[rel] = file_sha256(path)
    return result


def _git(root: Path, *args: str) -> None:
    done = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, timeout=60, check=False,
    )
    if done.returncode != 0:
        raise WorkspaceError(f"git {' '.join(args)} fehlgeschlagen: {done.stderr.strip()}")


def _init_git(root: Path) -> None:
    _git(root, "init", "--quiet", "--initial-branch=main")
    _git(root, "config", "user.email", "evals@example.invalid")
    _git(root, "config", "user.name", "Eval Harness")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "fixture baseline")


def prepare(dest: Path, skill_dir: Path, fixture_dir: Path | None) -> Workspace:
    """Baue einen frischen Workspace unter `dest` auf und liefere seine Baseline."""
    skill_dir = Path(skill_dir)
    if not (skill_dir / "SKILL.md").is_file():
        raise WorkspaceError(f"Skill-Verzeichnis ohne SKILL.md: {skill_dir}")

    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)

    wants_git = False
    if fixture_dir is not None:
        fixture_dir = Path(fixture_dir)
        if not fixture_dir.is_dir():
            raise WorkspaceError(f"Fixture nicht gefunden: {fixture_dir}")
        manifest_path = fixture_dir / FIXTURE_MANIFEST
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        wants_git = bool(manifest.get("git", False))
        shutil.copytree(
            fixture_dir, dest,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(FIXTURE_MANIFEST),
        )

    skill_target = dest / ".claude" / "skills" / skill_dir.name
    skill_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill_dir, skill_target, dirs_exist_ok=True)

    if wants_git:
        _init_git(dest)

    baseline = snapshot(dest)
    baseline[GIT_HEAD_KEY] = current_git_head(dest) if wants_git else None
    return Workspace(root=dest, baseline=baseline)


def dump_changed_files(root: Path, baseline: dict[str, str], *, max_bytes: int = 20_000) -> str:
    """Inhalt aller Dateien, die der Lauf neu angelegt oder verändert hat.

    Der Judge urteilt über das erzeugte Artefakt, nicht über die Schlussantwort des
    Agenten — ohne diesen Dump könnte er inhaltliche Behauptungen gar nicht prüfen.
    """
    chunks: list[str] = []
    budget = max_bytes
    for rel, digest in sorted(snapshot(root).items()):
        if baseline.get(rel) == digest:
            continue
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        if len(text) > budget:
            text = text[:budget] + "\n… (gekürzt)"
        chunks.append(f"--- DATEI: {rel} ---\n{text}")
        budget -= min(len(text), budget)
        if budget <= 0:
            break
    return "\n\n".join(chunks) if chunks else "(keine Datei wurde angelegt oder verändert)"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_workspace.py -v`
Expected: PASS, 12 passed

- [ ] **Step 5: Commit**

```bash
git add evalkit/workspace.py tests/test_workspace.py
git commit -m "feat(evals): Workspace-Aufbau mit Skill-Installation und Baseline-Snapshot"
```

---

### Task 4: Agent-Dispatch

**Files:**
- Create: `evalkit/dispatch.py`
- Create: `tests/test_dispatch.py`

**Interfaces:**
- Consumes: nichts aus `evalkit`
- Produces:
  - `evalkit.dispatch.Transcript(stdout: str, stderr: str, exit_code: int, timed_out: bool)` — frozen dataclass
  - `evalkit.dispatch.run_agent(prompt: str, cwd: pathlib.Path, *, cli: str = "claude", timeout: int = 600, permission_mode: str = "bypassPermissions") -> Transcript`
  - `evalkit.dispatch.DEFAULT_TIMEOUT: int`

**Warum ein Fake-CLI im Test:** Der echte `claude`-Prozess kostet Zeit und Tokens und ist nicht deterministisch. Die Unit-Tests sprechen deshalb ein Shell-Skript an, das sich wie das CLI verhält. Schritt 6 fährt genau einmal den echten Prozess, um die Flags zu verifizieren — Annahmen über fremde CLIs gehören geprüft, nicht geglaubt.

- [ ] **Step 1: Write the failing test**

`tests/test_dispatch.py`:

```python
import os
import stat
from pathlib import Path

from evalkit.dispatch import run_agent


def fake_cli(tmp_path: Path, body: str) -> str:
    # bash, nicht sh: ${@: -1} ist ein Bashismus und bricht unter dash.
    script = tmp_path / "fake-claude"
    script.write_text("#!/bin/bash\n" + body, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_captures_stdout_and_exit_code(tmp_path):
    cli = fake_cli(tmp_path, 'echo "hallo"\nexit 0\n')
    result = run_agent("prompt", tmp_path, cli=cli)
    assert result.stdout.strip() == "hallo"
    assert result.exit_code == 0
    assert not result.timed_out


def test_passes_prompt_as_last_argument(tmp_path):
    cli = fake_cli(tmp_path, 'echo "$#" "${@: -1}"\n')
    result = run_agent("mein prompt", tmp_path, cli=cli)
    assert "mein prompt" in result.stdout


def test_passes_print_and_permission_flags(tmp_path):
    cli = fake_cli(tmp_path, 'echo "$@"\n')
    result = run_agent("p", tmp_path, cli=cli, permission_mode="acceptEdits")
    assert "-p" in result.stdout
    assert "--permission-mode acceptEdits" in result.stdout


def test_isolates_from_user_configuration(tmp_path):
    """Ohne diese Flags testet der Eval die global installierte Skill, nicht die im Workspace."""
    cli = fake_cli(tmp_path, 'echo "$@"\n')
    result = run_agent("p", tmp_path, cli=cli)
    assert "--setting-sources project" in result.stdout
    assert "--strict-mcp-config" in result.stdout


def test_runs_in_given_working_directory(tmp_path):
    workdir = tmp_path / "ws"
    workdir.mkdir()
    cli = fake_cli(tmp_path, "pwd\n")
    result = run_agent("p", workdir, cli=cli)
    assert os.path.realpath(result.stdout.strip()) == os.path.realpath(str(workdir))


def test_timeout_is_reported_not_raised(tmp_path):
    cli = fake_cli(tmp_path, "sleep 5\n")
    result = run_agent("p", tmp_path, cli=cli, timeout=1)
    assert result.timed_out
    assert result.exit_code != 0


def test_missing_cli_is_reported_not_raised(tmp_path):
    result = run_agent("p", tmp_path, cli=str(tmp_path / "does-not-exist"))
    assert result.exit_code != 0
    assert "nicht gefunden" in result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_dispatch.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'evalkit.dispatch'`

- [ ] **Step 3: Write minimal implementation**

`evalkit/dispatch.py`:

```python
"""Einen frischen Agenten im Workspace starten und sein Transcript einsammeln."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT = 600


@dataclass(frozen=True)
class Transcript:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


def run_agent(
    prompt: str,
    cwd: Path,
    *,
    cli: str = "claude",
    timeout: int = DEFAULT_TIMEOUT,
    permission_mode: str = "bypassPermissions",
) -> Transcript:
    """Starte `claude -p <prompt>` in `cwd`.

    `bypassPermissions` ist vertretbar, weil `cwd` immer ein Wegwerf-Workspace
    unter tempfile ist — nie ein echtes Repo. Der Runner erzwingt das.
    """
    argv = [
        cli,
        "-p",
        "--permission-mode", permission_mode,
        # Isolation: ohne das misst der Eval die global installierte Fassung der
        # Skill (und lässt fremde Plugins mitreden) statt der Repo-Version im
        # Workspace. Ergebnisse wären maschinenabhängig.
        "--setting-sources", "project",
        "--strict-mcp-config",
        prompt,
    ]
    try:
        done = subprocess.run(
            argv, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return Transcript(
            stdout=(exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=f"Timeout nach {timeout}s",
            exit_code=124,
            timed_out=True,
        )
    except FileNotFoundError:
        return Transcript(stdout="", stderr=f"CLI nicht gefunden: {cli}", exit_code=127, timed_out=False)
    except OSError as exc:
        return Transcript(stdout="", stderr=f"CLI nicht startbar: {exc}", exit_code=126, timed_out=False)

    return Transcript(stdout=done.stdout, stderr=done.stderr, exit_code=done.returncode, timed_out=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_dispatch.py -v`
Expected: PASS, 7 passed

- [ ] **Step 5: Commit**

```bash
git add evalkit/dispatch.py tests/test_dispatch.py
git commit -m "feat(evals): Agent-Dispatch als gekapselte Subprozess-Grenze"
```

- [ ] **Step 6: Echten CLI-Aufruf einmal verifizieren**

Die Flags `-p` und `--permission-mode` sind eine Annahme über ein fremdes CLI. Einmal gegen die echte Binary prüfen:

```bash
mkdir -p /tmp/eval-smoke/.claude/skills && cd /tmp/eval-smoke
claude -p --permission-mode bypassPermissions --setting-sources project --strict-mcp-config \
  "Lege eine Datei ok.txt mit dem Inhalt 'ok' an. Welche Skills stehen dir zur Verfügung?" ; echo "exit=$?"
ls -l ok.txt
cd - && rm -rf /tmp/eval-smoke
```

Expected: exit=0, `ok.txt` existiert — **und die Antwort nennt keine der global installierten Skills** (handoff, superpowers, …). Genau das ist der Punkt von `--setting-sources project`: Auf dieser Maschine ist `handoff` auch persönlich installiert; ohne die Isolation würde der Eval die globale Kopie messen statt der Repo-Version im Workspace, und Ergebnisse wären maschinenabhängig.

**Wenn die Flags abweichen:** `run_agent`, `test_passes_print_and_permission_flags` und `test_isolates_from_user_configuration` auf die tatsächliche Syntax korrigieren (`claude --help` zeigt sie), dann Task 4 erneut committen. Nicht weitermachen, bevor dieser Schritt grün ist — alle folgenden Tasks hängen daran.

---

### Task 5: Judge

**Files:**
- Create: `evalkit/judge.py`
- Create: `tests/test_judge.py`

**Interfaces:**
- Consumes: `evalkit.dispatch.run_agent`, `evalkit.dispatch.Transcript`
- Produces:
  - `evalkit.judge.JudgeError(RuntimeError)`
  - `evalkit.judge.build_prompt(claims: collections.abc.Sequence[str], transcript: str, workspace_dump: str) -> str`
  - `evalkit.judge.parse_verdict(raw: str) -> dict[str, bool]`
  - `evalkit.judge.judge(claims: collections.abc.Sequence[str], transcript: str, workspace_dump: str, cwd: pathlib.Path, *, cli: str = "claude", timeout: int = 300) -> dict[str, bool]`

**Warum der Judge den Dateiinhalt braucht:** `claude -p` gibt nur die finale Antwort aus — bei handoff sind das laut SKILL.md „1–2 Sätze Bestätigung". Behauptungen über den *Inhalt* der erzeugten `handoff.md` wären daraus prinzipiell nicht beurteilbar; der Judge müsste nach seiner eigenen Zweifelsregel immer `false` urteilen. Deshalb bekommt er zusätzlich den Dump der geänderten Dateien aus Task 3.

**Warum der Judge ein eigenes Arbeitsverzeichnis bekommt:** Er ist selbst ein Agent mit Schreibrechten. Liefe er im Workspace, könnte er dort Dateien anlegen und damit die mechanischen Assertions (`file_unchanged`, `file_absent`, `git_head_unchanged`) verfälschen, die danach ausgewertet werden.

- [ ] **Step 1: Write the failing test**

`tests/test_judge.py`:

```python
import pytest
from evalkit.judge import JudgeError, build_prompt, parse_verdict


def test_prompt_contains_every_claim_and_the_transcript():
    prompt = build_prompt(["Claim A", "Claim B"], "AGENT SAGTE X", "(nichts)")
    assert "Claim A" in prompt
    assert "Claim B" in prompt
    assert "AGENT SAGTE X" in prompt


def test_prompt_contains_the_workspace_dump():
    """Ohne Dateiinhalt könnte der Judge inhaltliche Behauptungen nie bejahen."""
    prompt = build_prompt(["A"], "kurze Bestätigung", "--- DATEI: handoff.md ---\n## Status\nfoo")
    assert "handoff.md" in prompt
    assert "## Status" in prompt


def test_prompt_demands_bare_json_and_default_false():
    prompt = build_prompt(["A"], "t", "d")
    assert "JSON" in prompt
    assert "holds" in prompt
    # Im Zweifel gilt eine Behauptung als nicht erfüllt — sonst besteht alles.
    assert "false" in prompt


def test_parse_plain_verdict():
    raw = '{"verdicts": [{"claim": "A", "holds": true, "why": "steht da"}]}'
    assert parse_verdict(raw) == {"A": True}


def test_parse_verdict_wrapped_in_prose():
    raw = 'Hier mein Urteil:\n\n{"verdicts": [{"claim": "A", "holds": false, "why": "fehlt"}]}\n\nEnde.'
    assert parse_verdict(raw) == {"A": False}


def test_parse_verdict_ignores_earlier_json_objects():
    raw = '{"note": "ignoriere mich"}\n{"verdicts": [{"claim": "A", "holds": true}]}'
    assert parse_verdict(raw) == {"A": True}


def test_parse_verdict_survives_braces_inside_strings():
    """Eine Klammer in der Begründung darf das Parsing nicht aus dem Tritt bringen."""
    raw = '{"verdicts": [{"claim": "A", "holds": true, "why": "der Code sagt def main() { ..."}]}'
    assert parse_verdict(raw) == {"A": True}


def test_parse_verdict_without_json_raises():
    with pytest.raises(JudgeError, match="kein JSON"):
        parse_verdict("Ich finde das alles ganz gut.")


def test_parse_verdict_with_missing_holds_raises():
    with pytest.raises(JudgeError, match="holds"):
        parse_verdict('{"verdicts": [{"claim": "A"}]}')


def test_parse_verdict_with_non_boolean_holds_raises():
    with pytest.raises(JudgeError, match="holds"):
        parse_verdict('{"verdicts": [{"claim": "A", "holds": "ja"}]}')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_judge.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'evalkit.judge'`

- [ ] **Step 3: Write minimal implementation**

`evalkit/judge.py`:

```python
"""Zweiter Agent als Judge für nicht-mechanische Behauptungen."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from evalkit.dispatch import run_agent

PROMPT_TEMPLATE = """Du bist Judge in einem Eval-Harness. Beurteile jede Behauptung
ausschließlich anhand des Materials unten — der Schlussantwort des Agenten und dem
Inhalt der Dateien, die er angelegt oder verändert hat. Du bewertest nicht die
Qualität der Arbeit, nur ob die Behauptung beobachtbar zutrifft.

Regeln:
- Eine Behauptung gilt nur als erfüllt, wenn das Material sie belegt.
- Im Zweifel lautet das Urteil false. Nicht wohlwollend auslegen.
- Lies nichts im Dateisystem nach; das Material unten ist vollständig.
- Antworte mit einem einzigen JSON-Objekt, ohne Markdown-Zaun, ohne Vor- und Nachtext.

Format:
{{"verdicts": [{{"claim": "<wörtlich die Behauptung>", "holds": true|false, "why": "<ein Satz>"}}]}}

Behauptungen:
{claims}

--- SCHLUSSANTWORT DES AGENTEN ---
{transcript}
--- ENDE SCHLUSSANTWORT ---

--- ANGELEGTE UND GEÄNDERTE DATEIEN ---
{workspace}
--- ENDE DATEIEN ---
"""


class JudgeError(RuntimeError):
    """Der Judge hat kein verwertbares Urteil geliefert."""


def build_prompt(claims: Sequence[str], transcript: str, workspace_dump: str) -> str:
    numbered = "\n".join(f"{i}. {claim}" for i, claim in enumerate(claims, start=1))
    return PROMPT_TEMPLATE.format(claims=numbered, transcript=transcript, workspace=workspace_dump)


def _last_json_object(raw: str) -> dict:
    """Extrahiere das letzte JSON-Objekt aus einem Text.

    `raw_decode` statt Klammerzählung: Eine geschweifte Klammer *innerhalb* eines
    JSON-Strings (etwa in einer 'why'-Begründung, die Code zitiert) würde jede
    selbstgebaute Zählung aus dem Tritt bringen.
    """
    decoder = json.JSONDecoder()
    candidates: list[dict] = []
    for start, char in enumerate(raw):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(raw, start)
        except ValueError:
            continue
        if isinstance(value, dict):
            candidates.append(value)
    for candidate in reversed(candidates):
        if "verdicts" in candidate:
            return candidate
    if candidates:
        return candidates[-1]
    raise JudgeError("Judge-Antwort enthält kein JSON-Objekt")


def parse_verdict(raw: str) -> dict[str, bool]:
    payload = _last_json_object(raw)
    verdicts = payload.get("verdicts")
    if not isinstance(verdicts, list) or not verdicts:
        raise JudgeError("Judge-Antwort enthält keine Liste 'verdicts'")
    result: dict[str, bool] = {}
    for entry in verdicts:
        if not isinstance(entry, dict) or "claim" not in entry:
            raise JudgeError(f"Verdict ohne 'claim': {entry!r}")
        holds = entry.get("holds")
        if not isinstance(holds, bool):
            raise JudgeError(f"Verdict für {entry['claim']!r} hat kein boolesches 'holds': {holds!r}")
        result[entry["claim"]] = holds
    return result


def judge(
    claims: Sequence[str],
    transcript: str,
    workspace_dump: str,
    cwd: Path,
    *,
    cli: str = "claude",
    timeout: int = 300,
) -> dict[str, bool]:
    """Lasse alle Behauptungen in einem Durchgang beurteilen.

    `cwd` ist bewusst NICHT der Eval-Workspace, sondern ein eigenes leeres
    Verzeichnis — der Judge darf die Beobachtung nicht verändern können.
    """
    if not claims:
        return {}
    result = run_agent(build_prompt(claims, transcript, workspace_dump), cwd, cli=cli, timeout=timeout)
    if result.exit_code != 0:
        raise JudgeError(f"Judge-Prozess scheiterte (exit {result.exit_code}): {result.stderr.strip()[:200]}")
    verdicts = parse_verdict(result.stdout)
    missing = [claim for claim in claims if claim not in verdicts]
    if missing:
        raise JudgeError(f"Judge hat {len(missing)} Behauptung(en) nicht beurteilt: {missing[0]!r}")
    return verdicts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_judge.py -v`
Expected: PASS, 10 passed

- [ ] **Step 5: Commit**

```bash
git add evalkit/judge.py tests/test_judge.py
git commit -m "feat(evals): Judge mit strikter Verdict-Auswertung"
```

---

### Task 6: Report und Runner-CLI

**Files:**
- Create: `evalkit/report.py`
- Create: `evalkit/runner.py`
- Create: `run_evals.py`
- Create: `tests/test_report.py`
- Create: `tests/test_runner.py`

**Interfaces:**
- Consumes: `evalkit.schema.load_evals`, `evalkit.schema.Eval`, `evalkit.schema.JUDGE_TYPE`, `evalkit.assertions.check`, `evalkit.workspace.prepare`, `evalkit.dispatch.run_agent`, `evalkit.judge.judge`
- Produces:
  - `evalkit.report.EvalResult(eval_id: str, passed: bool, failures: tuple[str, ...], skipped: bool, note: str)` — frozen dataclass
  - `evalkit.report.format_report(results: collections.abc.Sequence[EvalResult]) -> str`
  - `evalkit.report.exit_code(results: collections.abc.Sequence[EvalResult]) -> int` — 0 alles grün, 1 mindestens ein Eval gefallen, 2 Harness-Fehler
  - `evalkit.runner.grade(ev: Eval, root: pathlib.Path, baseline: dict[str, str], verdicts: dict[str, bool], output: str = "") -> EvalResult`
  - `evalkit.runner.run_one(ev: Eval, *, skill_dir, fixtures_dir, cli, timeout, keep) -> EvalResult`
  - `evalkit.runner.main(argv: collections.abc.Sequence[str] | None = None) -> int`

- [ ] **Step 1: Write the failing test for grading and report**

`tests/test_report.py`:

```python
from evalkit.report import EvalResult, exit_code, format_report


def test_exit_code_all_green():
    assert exit_code([EvalResult("a", True, (), False, "")]) == 0


def test_exit_code_one_failure():
    assert exit_code([EvalResult("a", True, (), False, ""), EvalResult("b", False, ("x",), False, "")]) == 1


def test_exit_code_harness_error_wins_over_failure():
    results = [EvalResult("a", False, ("x",), False, ""), EvalResult("b", False, ("boom",), True, "Harness-Fehler")]
    assert exit_code(results) == 2


def test_report_lists_failures_verbatim():
    text = format_report([EvalResult("handoff-creates-file", False, ("handoff.md existiert nicht",), False, "")])
    assert "handoff-creates-file" in text
    assert "handoff.md existiert nicht" in text
    assert "1 gefallen" in text
```

`tests/test_runner.py`:

```python
import pytest
from evalkit.report import EvalResult
from evalkit.runner import grade
from evalkit.schema import Assertion, Eval


def make_eval(must=(), must_not=(), eval_class="contract"):
    return Eval(id="e", eval_class=eval_class, prompt="p", must=tuple(must), must_not=tuple(must_not))


def test_passes_when_all_must_hold(tmp_path):
    (tmp_path / "handoff.md").write_text("x", encoding="utf-8")
    ev = make_eval(must=[Assertion(type="file_exists", path="handoff.md")])
    assert grade(ev, tmp_path, {}, {}).passed


def test_fails_when_a_must_is_unmet(tmp_path):
    ev = make_eval(must=[Assertion(type="file_exists", path="handoff.md")])
    result = grade(ev, tmp_path, {}, {})
    assert not result.passed
    assert "must" in result.failures[0]


def test_must_not_is_inverted(tmp_path):
    """must_not ist erfüllt, wenn die Beobachtung NICHT zutrifft."""
    ev = make_eval(
        must=[Assertion(type="file_absent", path="egal.md")],
        must_not=[Assertion(type="file_exists", path="CLAUDE.md")],
    )
    assert grade(ev, tmp_path, {}, {}).passed
    (tmp_path / "CLAUDE.md").write_text("x", encoding="utf-8")
    result = grade(ev, tmp_path, {}, {})
    assert not result.passed
    assert "must_not" in result.failures[0]


def test_judge_verdicts_are_honoured(tmp_path):
    ev = make_eval(
        must=[Assertion(type="judge", claim="A")],
        eval_class="behavior",
    )
    assert grade(ev, tmp_path, {}, {"A": True}).passed
    assert not grade(ev, tmp_path, {}, {"A": False}).passed


def test_missing_judge_verdict_is_a_failure(tmp_path):
    ev = make_eval(must=[Assertion(type="judge", claim="A")], eval_class="behavior")
    result = grade(ev, tmp_path, {}, {})
    assert not result.passed
    assert "kein Urteil" in result.failures[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_report.py tests/test_runner.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'evalkit.report'`

- [ ] **Step 3: Write the report module**

`evalkit/report.py`:

```python
"""Ergebnisse formatieren und in einen Exit-Code übersetzen."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class EvalResult:
    eval_id: str
    passed: bool
    failures: tuple[str, ...]
    skipped: bool = False
    note: str = ""


def format_report(results: Sequence[EvalResult]) -> str:
    lines: list[str] = []
    for result in results:
        if result.skipped:
            mark = "SKIP"
        elif result.passed:
            mark = "PASS"
        else:
            mark = "FAIL"
        suffix = f" — {result.note}" if result.note else ""
        lines.append(f"[{mark}] {result.eval_id}{suffix}")
        for failure in result.failures:
            lines.append(f"       {failure}")

    passed = sum(1 for r in results if r.passed and not r.skipped)
    failed = sum(1 for r in results if not r.passed and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    lines.append("")
    lines.append(f"{passed} bestanden, {failed} gefallen, {skipped} übersprungen")
    return "\n".join(lines)


def exit_code(results: Sequence[EvalResult]) -> int:
    """0 = alles grün, 1 = mindestens ein Eval gefallen, 2 = Harness-Fehler."""
    if any(r.skipped and r.failures for r in results):
        return 2
    if any(not r.passed and not r.skipped for r in results):
        return 1
    return 0
```

- [ ] **Step 4: Write the runner module**

`evalkit/runner.py`:

```python
"""Orchestrierung: Workspace bauen, Agent laufen lassen, bewerten, berichten."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path

from evalkit.assertions import check
from evalkit.dispatch import DEFAULT_TIMEOUT, run_agent
from evalkit.judge import JudgeError, judge
from evalkit.report import EvalResult, exit_code, format_report
from evalkit.schema import JUDGE_TYPE, Eval, EvalSchemaError, load_evals
from evalkit.workspace import WorkspaceError, dump_changed_files, prepare

REPO_ROOT = Path(__file__).resolve().parent.parent


def grade(ev: Eval, root: Path, baseline: dict[str, str], verdicts: dict[str, bool], output: str = "") -> EvalResult:
    """Bestanden = alle must erfüllt und kein must_not verletzt (Spec 00 §2)."""
    failures: list[str] = []

    for assertion in ev.must:
        if assertion.type == JUDGE_TYPE:
            if assertion.claim not in verdicts:
                failures.append(f"must: kein Urteil zu {assertion.claim!r}")
            elif not verdicts[assertion.claim]:
                failures.append(f"must: Judge verneint {assertion.claim!r}")
            continue
        result = check(assertion, root, baseline, output)
        if not result.ok:
            failures.append(f"must: {result.detail}")

    for assertion in ev.must_not:
        if assertion.type == JUDGE_TYPE:
            # Achtung auf die Polung: Der Judge urteilt im Zweifel false, und false
            # lässt ein must_not bestehen. Behauptungen für must_not deshalb so
            # formulieren, dass der Zweifel gegen den Verstoß spricht.
            if assertion.claim not in verdicts:
                failures.append(f"must_not: kein Urteil zu {assertion.claim!r}")
            elif verdicts[assertion.claim]:
                failures.append(f"must_not: Judge bejaht {assertion.claim!r}")
            continue
        result = check(assertion, root, baseline, output)
        if result.ok:
            failures.append(f"must_not: {result.detail}")

    return EvalResult(eval_id=ev.id, passed=not failures, failures=tuple(failures))


def _claims(ev: Eval) -> list[str]:
    return [a.claim for a in (*ev.must, *ev.must_not) if a.type == JUDGE_TYPE]


def run_one(
    ev: Eval,
    *,
    skill_dir: Path,
    fixtures_dir: Path,
    cli: str,
    timeout: int,
    keep: bool,
) -> EvalResult:
    fixture_dir = fixtures_dir / ev.fixture if ev.fixture else None
    workdir = Path(tempfile.mkdtemp(prefix=f"eval-{ev.id}-"))
    try:
        workspace = prepare(workdir / "ws", skill_dir, fixture_dir)
        transcript = run_agent(ev.prompt, workspace.root, cli=cli, timeout=timeout)
        if transcript.exit_code != 0:
            note = "Timeout" if transcript.timed_out else f"Agent exit {transcript.exit_code}"
            return EvalResult(ev.id, False, (f"harness: {note}: {transcript.stderr.strip()[:200]}",), True, note)

        verdicts: dict[str, bool] = {}
        claims = _claims(ev)
        if claims:
            # Der Judge läuft in einem eigenen leeren Verzeichnis, nicht im Workspace:
            # Er ist selbst ein Agent mit Schreibrechten und würde sonst genau die
            # Beobachtung verändern, die anschließend bewertet wird.
            judge_dir = workdir / "judge"
            judge_dir.mkdir(exist_ok=True)
            dump = dump_changed_files(workspace.root, workspace.baseline)
            verdicts = judge(claims, transcript.stdout, dump, judge_dir, cli=cli, timeout=timeout)
        return grade(ev, workspace.root, workspace.baseline, verdicts, transcript.stdout)
    except (WorkspaceError, JudgeError) as exc:
        return EvalResult(ev.id, False, (f"harness: {exc}",), True, "Harness-Fehler")
    finally:
        if keep:
            print(f"  Workspace behalten: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval-Runner für die Skill-Sammlung (Spec 00 §2)")
    parser.add_argument("--skill", action="append", dest="skills", help="nur diese Skill (wiederholbar)")
    parser.add_argument("--class", dest="eval_class", choices=["contract", "behavior"], help="nur diese Eval-Klasse")
    parser.add_argument("--evals-dir", type=Path, default=REPO_ROOT / "evals")
    parser.add_argument("--skills-dir", type=Path, default=REPO_ROOT / "skills")
    parser.add_argument("--cli", default="claude")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--keep-workspace", action="store_true", help="Workspaces zur Diagnose behalten")
    args = parser.parse_args(argv)

    fixtures_dir = args.evals_dir / "fixtures"
    results: list[EvalResult] = []

    for evals_file in sorted(args.evals_dir.glob("*/evals.json")):
        skill_name = evals_file.parent.name
        if args.skills and skill_name not in args.skills:
            continue
        skill_dir = args.skills_dir / skill_name
        try:
            evals = load_evals(evals_file)
        except EvalSchemaError as exc:
            results.append(EvalResult(f"{skill_name}/evals.json", False, (f"harness: {exc}",), True, "Schema-Fehler"))
            continue

        for ev in evals:
            if args.eval_class and ev.eval_class != args.eval_class:
                continue
            print(f"→ {skill_name}/{ev.id} ({ev.eval_class})")
            results.append(run_one(
                ev, skill_dir=skill_dir, fixtures_dir=fixtures_dir,
                cli=args.cli, timeout=args.timeout, keep=args.keep_workspace,
            ))

    if not results:
        print("Keine Evals gefunden — Filter zu eng oder evals/ leer.")
        return 2

    print()
    print(format_report(results))
    return exit_code(results)
```

`run_evals.py` im Repo-Root:

```python
#!/usr/bin/env python3
"""Eval-Runner für die Skill-Sammlung. Tier 1: nur Stdlib.

    python run_evals.py --skill handoff --class contract
"""

import sys

from evalkit.runner import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/ -v`
Expected: PASS, alle Tests aus Task 1–6 grün (61 passed)

- [ ] **Step 6: Commit**

```bash
git add evalkit/report.py evalkit/runner.py run_evals.py tests/test_report.py tests/test_runner.py
git commit -m "feat(evals): Runner-CLI, Bewertung und Report"
```

---

### Task 7: Fixture und handoff-Evals — der erste echte Lauf

**Files:**
- Create: `evals/fixtures/dirty-worktree/fixture.json`
- Create: `evals/fixtures/dirty-worktree/README.md`
- Create: `evals/fixtures/dirty-worktree/CLAUDE.md`
- Create: `evals/fixtures/dirty-worktree/src/parser.py`
- Create: `evals/fixtures/dirty-worktree/src/cli.py`
- Create: `evals/fixtures/dirty-worktree/tests/test_parser.py`
- Create: `evals/fixtures/empty-dir/fixture.json`
- Create: `evals/fixtures/stale-handoff/fixture.json`
- Create: `evals/fixtures/stale-handoff/README.md`
- Create: `evals/fixtures/stale-handoff/src/parser.py`
- Create: `evals/fixtures/stale-handoff/handoff.md` (generiert, siehe Step 3)
- Create: `evals/handoff/evals.json`

**Interfaces:**
- Consumes: `evalkit.runner.main` (via `run_evals.py`), das Fixture-Manifest-Format aus Task 3
- Produces: keine Code-Schnittstelle — dies ist die erste echte Last auf dem Harness

**Warum diese Evals:** Sie kommen direkt aus dem Contract von `skills/handoff/SKILL.md` — sechs Pflicht-Sektionen, max. 150 Zeilen, `CLAUDE.md` nie anfassen, kein Commit, und bei einem Verzeichnis ohne Projektcharakter erst nachfragen statt anlegen. Jede dieser Regeln ist mechanisch beobachtbar, außer der Anti-Zeremonie-Frage — die ist die eine `judge`-Behauptung und damit der Pflicht-Eval aus Spec 00 §2.

- [ ] **Step 1: Fixture `dirty-worktree` anlegen**

`evals/fixtures/dirty-worktree/fixture.json`:

```json
{
  "git": true,
  "description": "Kleines Python-Projekt mit Git-Historie und CLAUDE.md — Normalfall für handoff."
}
```

`evals/fixtures/dirty-worktree/README.md`:

```markdown
# Beispiel-Parser

Ein kleines Werkzeug, das Logzeilen in Records übersetzt.
```

`evals/fixtures/dirty-worktree/CLAUDE.md`:

```markdown
# Konventionen

- Python 3.13, keine externen Abhängigkeiten.
- Tests mit pytest unter `tests/`.
```

`evals/fixtures/dirty-worktree/src/parser.py`:

```python
"""Übersetzt Logzeilen in Records."""


def parse_line(line: str) -> dict[str, str]:
    level, _, message = line.partition(":")
    return {"level": level.strip(), "message": message.strip()}
```

`evals/fixtures/dirty-worktree/src/cli.py`:

```python
"""Kommandozeilen-Einstieg."""

import sys

from parser import parse_line


def main() -> int:
    for line in sys.stdin:
        record = parse_line(line)
        print(f"{record['level']}\t{record['message']}")
    return 0
```

`evals/fixtures/dirty-worktree/tests/test_parser.py`:

```python
from src.parser import parse_line


def test_parse_line_splits_level_and_message():
    assert parse_line("WARN: platte fast voll") == {"level": "WARN", "message": "platte fast voll"}
```

- [ ] **Step 2: Fixture `empty-dir` anlegen**

`evals/fixtures/empty-dir/fixture.json`:

```json
{
  "git": false,
  "description": "Verzeichnis ohne Projektcharakter — handoff muss nachfragen statt anzulegen."
}
```

- [ ] **Step 3: Fixture `stale-handoff` anlegen**

Der Update-Pfad ist die riskantere Hälfte von handoff („komplett neu schreiben, nie
anhängen" und „vorgefundene längere Datei aggressiv auf 150 Zeilen prunen") und
gleichzeitig trivial mechanisch prüfbar. Dafür braucht es eine vorbelegte, überlange
`handoff.md`.

`evals/fixtures/stale-handoff/fixture.json`:

```json
{
  "git": true,
  "description": "Projekt mit vorhandener, überlanger handoff.md — prüft den Update-Pfad."
}
```

`evals/fixtures/stale-handoff/README.md`:

```markdown
# Beispiel-Parser

Ein kleines Werkzeug, das Logzeilen in Records übersetzt.
```

`evals/fixtures/stale-handoff/src/parser.py`:

```python
"""Übersetzt Logzeilen in Records."""


def parse_line(line: str) -> dict[str, str]:
    level, _, message = line.partition(":")
    return {"level": level.strip(), "message": message.strip()}
```

Die überlange `handoff.md` wird generiert statt getippt:

```bash
mkdir -p evals/fixtures/stale-handoff/src
python3 - <<'PY'
from pathlib import Path

root = Path("evals/fixtures/stale-handoff")
lines = [
    "# Handoff — Beispiel-Parser (Stand: 2026-07-01)", "",
    "## Status", "Alter Stand aus dem Juli, längst überholt.", "",
    "## Implementiert",
]
lines += [f"- Erledigter Punkt {i} (src/legacy_{i}.py)" for i in range(1, 160)]
lines += [
    "", "## Offene Probleme", "Keine.",
    "", "## Erkenntnisse & Entscheidungen", "Keine.",
    "", "## Nächste Schritte", "Keine.",
    "", "## Einstiegspunkte", "- src/parser.py",
]
(root / "handoff.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(len(lines), "Zeilen geschrieben")
PY
```

Expected: `176 Zeilen geschrieben` — deutlich über der 150-Zeilen-Grenze.

- [ ] **Step 4: handoff-Evals schreiben**

`evals/handoff/evals.json`:

```json
{
  "evals": [
    {
      "id": "creates-handoff-with-all-sections",
      "class": "contract",
      "fixture": "dirty-worktree",
      "prompt": "Ich habe heute den Parser in src/parser.py gebaut und die Tests dazu geschrieben. Der CLI-Einstieg in src/cli.py importiert noch falsch — das ist offen. Wir hören hier auf für heute.",
      "must": [
        {"type": "file_exists", "path": "handoff.md"},
        {"type": "file_matches", "path": "handoff.md", "pattern": "^# Handoff — .+\\(Stand: \\d{4}-\\d{2}-\\d{2}\\)[ \\t]*$"},
        {"type": "file_matches", "path": "handoff.md", "pattern": "^## Status[ \\t]*$"},
        {"type": "file_matches", "path": "handoff.md", "pattern": "^## Implementiert[ \\t]*$"},
        {"type": "file_matches", "path": "handoff.md", "pattern": "^## Offene Probleme[ \\t]*$"},
        {"type": "file_matches", "path": "handoff.md", "pattern": "^## Erkenntnisse & Entscheidungen[ \\t]*$"},
        {"type": "file_matches", "path": "handoff.md", "pattern": "^## Nächste Schritte[ \\t]*$"},
        {"type": "file_matches", "path": "handoff.md", "pattern": "^## Einstiegspunkte[ \\t]*$"},
        {"type": "file_max_lines", "path": "handoff.md", "max_lines": 150}
      ],
      "must_not": [],
      "notes": "Kern-Contract aus skills/handoff/SKILL.md: sechs Sektionen, Titelzeile mit absolutem Datum, harte Zeilengrenze. Das [ \\t]* am Zeilenende toleriert Trailing Whitespace — der Contract ist inhaltlich, nicht typografisch."
    },
    {
      "id": "never-touches-claude-md-or-history",
      "class": "contract",
      "fixture": "dirty-worktree",
      "prompt": "Übergabe bitte, ich mache morgen weiter.",
      "must": [
        {"type": "file_exists", "path": "handoff.md"},
        {"type": "file_unchanged", "path": "CLAUDE.md"},
        {"type": "git_head_unchanged"}
      ],
      "must_not": [],
      "notes": "SKILL.md verbietet beides ausdrücklich: CLAUDE.md nie anfassen, kein git commit."
    },
    {
      "id": "asks-before-creating-in-non-project-dir",
      "class": "contract",
      "fixture": "empty-dir",
      "prompt": "Sichere den Stand.",
      "must": [
        {"type": "file_absent", "path": "handoff.md"},
        {"type": "output_matches", "pattern": "\\?"}
      ],
      "must_not": [],
      "notes": "Randfall aus SKILL.md: kein Git, kein Code → erst nachfragen, nichts anlegen. Die output_matches-Assertion ist nötig, damit der Eval nicht vakuös besteht: Ohne sie wäre er auch dann grün, wenn die Skill gar nicht ausgelöst hätte und der Agent einfach nichts tat."
    },
    {
      "id": "update-prunes-instead-of-appending",
      "class": "contract",
      "fixture": "stale-handoff",
      "prompt": "Wir hören auf. Heute habe ich nur die Tests in tests/test_parser.py ergänzt.",
      "must": [
        {"type": "file_max_lines", "path": "handoff.md", "max_lines": 150},
        {"type": "file_matches", "path": "handoff.md", "pattern": "^# Handoff — .+\\(Stand: \\d{4}-\\d{2}-\\d{2}\\)[ \\t]*$"},
        {"type": "file_matches", "path": "handoff.md", "pattern": "^## Einstiegspunkte[ \\t]*$"}
      ],
      "must_not": [
        {"type": "file_matches", "path": "handoff.md", "pattern": "Erledigter Punkt 159"}
      ],
      "notes": "Update-Pfad: SKILL.md verlangt komplettes Neuschreiben statt Anhängen und aggressives Prunen auf 150 Zeilen. Die must_not-Zeile fängt genau die Regression 'angehängt statt ersetzt' — der Füllzeilen-Rest aus dem Fixture dürfte dann noch dastehen."
    },
    {
      "id": "anti-ceremony-invents-nothing",
      "class": "behavior",
      "fixture": "dirty-worktree",
      "prompt": "Wir hören auf. Ich habe heute nur den README-Text gelesen, sonst nichts gemacht.",
      "must": [
        {"type": "file_exists", "path": "handoff.md"},
        {"type": "judge", "claim": "Die Sektion 'Implementiert' behauptet keine Arbeit, die über das Lesen des README hinausgeht — sie erfindet insbesondere keine Implementierung am Parser oder an den Tests."},
        {"type": "judge", "claim": "Leere Sektionen sind mit 'Keine.' gefüllt statt weggelassen oder mit Fülltext aufgeblasen."}
      ],
      "must_not": [],
      "notes": "Pflicht-Anti-Zeremonie-Eval nach Spec 00 §2: Der triviale Fall muss klein bleiben."
    }
  ]
}
```

- [ ] **Step 5: Schema-Validierung ohne Agentenlauf prüfen**

```bash
.venv/bin/python -c "
from pathlib import Path
from evalkit.schema import load_evals
evals = load_evals(Path('evals/handoff/evals.json'))
print(f'{len(evals)} Evals geladen:', [e.id for e in evals])
print('Klassen:', sorted({e.eval_class for e in evals}))
"
```

Expected: `5 Evals geladen: [...]` und `Klassen: ['behavior', 'contract']`

- [ ] **Step 6: Contract-Evals gegen den echten Agenten fahren**

```bash
.venv/bin/python run_evals.py --skill handoff --class contract
echo "exit=$?"
```

Expected: vier Contract-Evals laufen, Report am Ende, `exit=0`.

**Wenn ein Eval fällt:** Zuerst entscheiden, ob die *Skill* oder der *Eval* falsch liegt — das ist der eigentliche Ertrag dieses Schrittes. Ein gefallener Eval, der eine echte Lücke in `skills/handoff/SKILL.md` zeigt, wird notiert und nicht wegdefiniert. Ein Eval, der eine Regel prüft, die die SKILL.md gar nicht aufstellt, wird korrigiert. Mit `--keep-workspace` lässt sich der Workspace zur Diagnose behalten.

- [ ] **Step 7: Behavior-Eval fahren**

```bash
.venv/bin/python run_evals.py --skill handoff --class behavior
echo "exit=$?"
```

Expected: ein Eval mit zwei Judge-Behauptungen, `exit=0`.

- [ ] **Step 8: Commit**

```bash
git add evals/
git commit -m "feat(evals): dirty-worktree/empty-dir-Fixtures und vier handoff-Evals"
```

---

### Task 8: Konventions-Dokumente nachziehen

**Files:**
- Create: `docs/artifact-header.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `evalkit.assertions.ARTIFACT_HEADER_RE` (die Regex ist die ausführbare Fassung dieses Dokuments)
- Produces: keine Code-Schnittstelle

- [ ] **Step 1: Kopf- und Konsumenten-Regel schreiben**

`docs/artifact-header.md`:

```markdown
# Artefakt-Kopfzeile und Konsumenten-Regel

Gilt für jedes Artefakt, das eine Skill dieser Sammlung erzeugt (Spec 00 §1).
Die ausführbare Fassung dieser Regel ist `ARTIFACT_HEADER_RE` in
`evalkit/assertions.py`; der Eval-Typ `artifact_header` prüft sie.

## Format

Die erste nicht-leere Zeile eines erzeugten Artefakts ist seine Kopfzeile.

Markdown:

    <!-- skill: debug-ledger | schema: 1 | generated: python scripts/new_ledger.py --symptom "Login hängt" -->

YAML:

    # skill: rest-api-architect | schema: 2 | generated: python scripts/gen_ruleset.py

JSON kennt keine Kommentare — dort trägt das Objekt stattdessen den Schlüssel
`_meta` mit denselben drei Feldern:

    {"_meta": {"skill": "dev-report", "schema": 1, "generated": "python scripts/collect.py --since 2026-08-01"}}

## Die drei Felder

- **skill** — der Skill-Name aus dem Frontmatter, kleingeschrieben mit Bindestrichen.
  Damit ist beim Lesen sofort klar, wer die Datei besitzt.
- **schema** — eine Zählnummer pro Artefaktart, beginnend bei 1. Sie wird
  hochgezählt, wenn sich die *Struktur* ändert, nicht der Inhalt.
- **generated** — das Kommando, das die Datei erzeugt hat, so wie man es erneut
  eintippen würde. Wer die Datei verstehen will, kann sie damit neu erzeugen.

## Bootstrap-Regel

Keine Skill legt ungefragt Dateien in fremden Repos an. Der erste Lauf kündigt
die Anlage an und nennt den Pfad.

## Konsumenten-Regel

Ein Konsument nimmt nie ein Format an, sondern liest die Kopfzeile:

1. Kopfzeile fehlt → das Artefakt stammt nicht aus dieser Sammlung. Nicht parsen,
   sondern sichtbar überspringen.
2. `schema` höher als erwartet → sichtbar überspringen und melden:
   „`docs/decisions.md` schema 1 erwartet, 2 gefunden — Scan übersprungen."
3. `schema` niedriger als erwartet → lesen erlaubt, wenn der Konsument die alte
   Struktur kennt; sonst wie Fall 2 behandeln.

Stillschweigendes Raten ist der einzige verbotene Weg. Die Kopplung der Skills
untereinander hält genau so lange, wie diese Regel eingehalten wird.

## Degradations-Regel

Keine Skill *setzt* ein Artefakt voraus. Fehlt es, arbeitet die Skill ohne es
weiter und sagt, was ihr dadurch fehlt.
```

- [ ] **Step 2: Routing-Matrix ins README heben**

`README.md` vollständig ersetzen:

```markdown
# evaluated-skills

Persönliche Claude-Skills und ihre Spezifikationen.

## Aufbau

| Ordner | Inhalt |
| --- | --- |
| `skills/` | die gebauten Skills (je ein Ordner mit `SKILL.md`) |
| `specs/` | Spezifikationen, Spec 00 ist die gemeinsame Grundlage |
| `evals/` | Eval-Definitionen und Fixtures |
| `evalkit/` | der geteilte Eval-Harness |
| `docs/` | Konventionen und Pläne |

## Evals laufen lassen

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest                                  # Harness-Unit-Tests
.venv/bin/python run_evals.py --class contract    # billige Contract-Evals
.venv/bin/python run_evals.py --skill handoff     # alles für eine Skill
```

Exit-Codes: `0` alles grün, `1` mindestens ein Eval gefallen, `2` Harness-Fehler.

## Routing

Welche Skill für welchen Anlass — die zentrale Matrix aus Spec 00 §5. Jede
Description trägt zusätzlich eine Abgrenzungsklausel gegen ihre zwei stärksten
Konkurrenten. Mit `(geplant)` markierte Skills sind spezifiziert, aber noch
nicht gebaut — die Matrix beschreibt den Zielzustand.

| Anlass | zuständig | nicht |
| --- | --- | --- |
| neues Feature, Codebase existiert | feature-spec *(geplant)* | brainstorming (kein Codebase-Bezug), writing-plans (das *Wie* danach) |
| Bug, Testfehler | debug-ledger *(geplant)* | feature-spec |
| Testplan, Repo-Typ-Frage | testing-strategy *(geplant)* | test-driven-development (Zyklus *während* der Implementierung) |
| Diff prüfen | `/code-review` (mitgeliefert) | eigene Review-Skill — siehe Spec 04, Zuschnitt offen |
| Sicherheit | `/security-review`, trailofbits | alle eigenen Skills |
| UI: Stil und Tokens | ui-architect | enterprise-ui (Produktoberfläche), motion-landing (Bewegung) |
| UI: Produktoberfläche, Tabellen, Formulare | enterprise-ui | ui-architect (Marketing/Brand) |
| Landing-Page-Bewegung | motion-landing *(geplant)* | ui-architect (Stil/Tokens), enterprise-ui |
| ad-hoc „fass zusammen" | visual-summary *(geplant)* | dev-report (periodisch), handoff (Sitzungsende) |
| Sitzungsende, Übergabe | handoff | visual-summary, dev-report |

## Konventionen

- [Artefakt-Kopfzeile und Konsumenten-Regel](docs/artifact-header.md)
- [Spec 00 — Artefakt-Vertrag, Evals, Tiers und Routing](specs/Spec%2000%20%E2%80%93%20skill-foundation.md)
```

- [ ] **Step 3: Verweise prüfen**

```bash
ls docs/artifact-header.md "specs/Spec 00 – skill-foundation.md"
grep -c "^| " README.md
```

Expected: beide Dateien existieren, die Tabellenzeilen sind da.

- [ ] **Step 4: Commit**

```bash
git add docs/artifact-header.md README.md
git commit -m "docs: Kopfzeilen-Konvention und Routing-Matrix aus Spec 00"
```

---

## Was dieser Plan bewusst nicht baut

- **Fixtures `legacy-monolith` und `cyclic-imports`** — sie bedienen Spec 05 und 10, die noch nicht existieren. Der Mechanismus steht, die Fixtures kommen mit ihren Skills.
- **Evals für die 14 geplanten Skills** — jede Skill bringt ihre eigenen mit, wenn sie gebaut wird.
- **CI-Integration und Contract-Eval-Hook** — Spec 00 führt beides als offene Frage; ohne Antwort wird nichts gebaut.
- **Parallelisierung der Eval-Läufe** — sequenziell ist bei vier Evals schnell genug. Erst optimieren, wenn es weh tut.
- **`.skills/cache/`-Nutzung** — der Harness braucht keinen Cache; die Konvention gilt für die Skills, nicht für ihn.
