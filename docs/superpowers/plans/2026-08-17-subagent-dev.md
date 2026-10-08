# subagent-dev Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine Skill, die aus einem `superpowers:writing-plans`-Plan mechanisch entscheidet, welche Tasks parallel delegiert werden dürfen, und die für jeden delegierten Task eine Handoff-Datei statt Konversationshistorie liefert.

**Architecture:** Ein Tier-1-Skript (`plan_to_tasks.py`) mit zwei Unterkommandos. `generate` parst die `### Task N:`-Blöcke eines Plans (Files:/Interfaces:/Steps), baut eine Datei- und Interface-Überlappungsmatrix, fällt ein Gate-Urteil (parallel/sequenziell/keine Delegation) und schreibt pro Task eine Handoff-Datei nach `.skills/cache/tasks/` — Markdown für Menschen, ein eingebetteter JSON-Block für die maschinelle Weiterverarbeitung. `verify` prüft nach einem Dispatch mechanisch, ob der Agent innerhalb seiner Datei-Allowlist geblieben ist (`git diff` gegen eine Basis-Revision) und ob die deklarierten `Produces`-Signaturen im Ergebnis auftauchen (`ast`, kein Import). SKILL.md trägt Dispatch-Protokoll, Kostenrichtwerte und die Abgrenzung zu `superpowers:subagent-driven-development`.

**Tech Stack:** Python 3.13 (Stdlib: `ast`, `re`, `json`, `subprocess`, `argparse`), git CLI, pytest als Dev-Abhängigkeit.

**Spec:** `specs/Spec 09 – subagent-dev.md` (und `specs/Spec 00 – skill-foundation.md` für Artefakt- und Eval-Vertrag)

## Global Constraints

- **Tier 1:** `plan_to_tasks.py` importiert ausschließlich die Python-Stdlib.
- **Überlappungserkennung ist konservativ:** Kann eine Abhängigkeit zwischen zwei Tasks nicht sicher ausgeschlossen werden (leeres oder unparsbares `Files:`, ein Interface-Symbol, das eine andere Task konsumiert), gilt sie als vorhanden. Ein übersehener Konflikt zerstört Arbeitsstand; eine überflüssige Serialisierung kostet nur Zeit.
- **Parallel-Schwelle:** Nur Tasks mit paarweise leerem Schnitt dürfen parallel laufen, und nur ab mindestens drei solcher Pakete — sonst lohnt der Overhead nicht und das Urteil lautet "sequenziell/keine Delegation", mit Begründung.
- **Kein Dispatch ohne Task-Datei.** Jede generierte Task-Datei trägt: Ziel, Datei-Allowlist, Interfaces (Consumes/Produces wörtlich), Akzeptanzkriterien aus den Plan-Steps, Global Constraints des Plans wörtlich kopiert, Nicht-Ziele.
- **Fremden Code analysiert `verify` statisch mit `ast`, nie per Import** (Spec 00 §, Vorab-Entscheidung A3).
- **Artefakt-Pfade:** Task-Dateien und Gate-Urteil nach `.skills/cache/tasks/` (Ephemera, gitignored, Spec 00 §1). Jedes Artefakt trägt die Kopfzeile aus `docs/artifact-header.md` (Markdown-Form für `.md`, `_meta`-Konvention für das JSON).
- **Bootstrap-Regel:** Das Skript legt `.skills/cache/tasks/` beim ersten Lauf an und nennt den Pfad; es setzt kein vorhandenes Artefakt voraus (Degradations-Regel).
- **Frontmatter:** nur `name` und `description`. SKILL.md ≤ 150 Zeilen.
- **Abgrenzung:** Die Description macht unmissverständlich klar, was diese Skill zusätzlich zu `superpowers:subagent-driven-development` leistet (mechanisches Gate + Handoff-Datei statt Prosa-Empfehlung), und verweist in beide Richtungen (auch von `subagent-driven-development` als "wenn ein Plan vorliegt, erst hier das Gate prüfen" — dokumentiert in der Abgrenzungs-Tabelle der eigenen SKILL.md, da fremde Skill-Dateien nicht verändert werden).
- **Evals:** vier Szenarien aus Spec 09 (verdeckte Überlappung, Mini-Plan unter Schwelle, abweichende Produces-Signatur, Recherche-Fan-out), jede Assertion an ein Artefakt unter `.skills/cache/tasks/`, das nur diese Skill erzeugt (Vorab-Entscheidung A6/B3). Evals werden geschrieben, aber in diesem Plan nicht ausgeführt.
- **Dokumentsprache Deutsch** (Kommentare, Fehlermeldungen, Prosa), Bezeichner in Code und JSON englisch.

### Pfad-Entscheidung: `evals/subagent-dev/evals.json` statt `skills/subagent-dev/evals/evals.json`

Spec 09s Skizze zeigt `evals/evals.json` innerhalb des Skill-Ordners; Spec 00 §2 (später ratifiziert) legt den geteilten Eval-Baum unter `evals/<skill>/evals.json` mit gemeinsamen Fixtures unter `evals/fixtures/` fest — so bereits umgesetzt für `dev-report` und `handoff`. Diese Ratifizierung gewinnt (Spec 00 löst Widersprüche der Einzel-Specs auf).

---

### Task 1: Plan-Parser und Überlappungsmatrix

**Files:**
- Create: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Test: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: nichts Neues
- Produces:
  - `parse_plan(text: str) -> PlanDoc` — `PlanDoc` trägt `global_constraints: str` und `tasks: list[PlanTask]`
  - `PlanTask` mit Feldern `id: int`, `title: str`, `files: list[FileRef]`, `files_unknown: bool`, `consumes: str`, `produces: str`, `steps: list[str]`
  - `FileRef` mit Feldern `raw: str` (wie im Plan geschrieben), `path: str` (Zeilenbereich abgeschnitten)
  - `build_overlap_graph(tasks: list[PlanTask]) -> dict[int, set[int]]` — Task-ID -> Menge überlappender Task-IDs (Datei- oder Interface-Grund)
  - `gate_verdict(tasks: list[PlanTask], overlap: dict[int, set[int]]) -> GateResult` — `GateResult` mit `verdict: str` (`"parallel"|"sequential"|"no-delegate"`), `parallel_group: list[int]`, `reasoning: str`

- [ ] **Step 1: Write the failing tests**

```python
from conftest import load_script

ptt = load_script("skills/subagent-dev/scripts/plan_to_tasks.py")

SAMPLE_PLAN = """# Beispiel Plan

## Global Constraints

- Alles auf Deutsch.

---

### Task 1: Parser

**Files:**
- Create: `src/parser.py`
- Test: `tests/test_parser.py`

**Interfaces:**
- Consumes: nichts Neues
- Produces:
  - `parse(line: str) -> dict`

- [ ] **Step 1: Write the failing test**

- [ ] **Step 2: Implement**

### Task 2: CLI

**Files:**
- Create: `src/cli.py`

**Interfaces:**
- Consumes: `parse(line: str) -> dict` aus Task 1
- Produces:
  - `main(argv: list[str]) -> int`

- [ ] **Step 1: Write the failing test**

### Task 3: Config-Datei anfassen

**Files:**
- Modify: `config/settings.py`

**Interfaces:**
- Consumes: nichts Neues
- Produces: nichts Neues

- [ ] **Step 1: Write the failing test**

### Task 4: Dieselbe Config-Datei

**Files:**
- Modify: `config/settings.py:10-20`

**Interfaces:**
- Consumes: nichts Neues
- Produces: nichts Neues

- [ ] **Step 1: Write the failing test**
"""


def test_parse_plan_extracts_four_tasks():
    doc = ptt.parse_plan(SAMPLE_PLAN)
    assert [t.id for t in doc.tasks] == [1, 2, 3, 4]
    assert doc.tasks[0].title == "Parser"
    assert "Alles auf Deutsch" in doc.global_constraints


def test_parse_plan_strips_line_ranges_from_files():
    doc = ptt.parse_plan(SAMPLE_PLAN)
    task4 = doc.tasks[3]
    assert task4.files[0].path == "config/settings.py"
    assert task4.files[0].raw == "config/settings.py:10-20"


def test_parse_plan_captures_steps_and_interfaces():
    doc = ptt.parse_plan(SAMPLE_PLAN)
    task2 = doc.tasks[1]
    assert "parse(line: str) -> dict" in task2.consumes
    assert task2.steps == ["Step 1: Write the failing test"]


def test_overlap_graph_flags_shared_file():
    doc = ptt.parse_plan(SAMPLE_PLAN)
    overlap = ptt.build_overlap_graph(doc.tasks)
    assert overlap[3] == {4}
    assert overlap[4] == {3}
    assert overlap[1] == set()
    assert overlap[2] == set()


def test_overlap_graph_flags_interface_dependency():
    doc = ptt.parse_plan(SAMPLE_PLAN)
    overlap = ptt.build_overlap_graph(doc.tasks)
    # Task 2 konsumiert parse(), das Task 1 produziert -> Abhängigkeit trotz
    # disjunkter Files.
    assert 1 in overlap[2] or 2 in overlap[1]


def test_gate_verdict_below_threshold_is_no_delegate():
    tasks = [t for t in ptt.parse_plan(SAMPLE_PLAN).tasks if t.id in (1, 2)]
    overlap = {1: {2}, 2: {1}}
    result = ptt.gate_verdict(tasks, overlap)
    assert result.verdict in ("no-delegate", "sequential")
    assert "Begründung" not in result.reasoning  # reasoning ist Text, kein Meta-Wort
    assert result.reasoning


def test_gate_verdict_unknown_files_forces_overlap():
    plan = SAMPLE_PLAN.replace(
        "**Files:**\n- Create: `src/cli.py`", "**Files:**\n- siehe Diskussion"
    )
    doc = ptt.parse_plan(plan)
    task2 = next(t for t in doc.tasks if t.id == 2)
    assert task2.files_unknown is True
    overlap = ptt.build_overlap_graph(doc.tasks)
    # Eine Task mit unbekannten Files überlappt konservativ mit allen anderen.
    assert overlap[2] == {1, 3, 4}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_subagent_dev_plan_to_tasks.py -v`
Expected: FAIL (ModuleNotFoundError / AttributeError, `plan_to_tasks.py` existiert noch nicht)

- [ ] **Step 3: Implement `plan_to_tasks.py` (Parser + Überlappungsmatrix + Gate)**

Implementiere `parse_plan`, `PlanDoc`, `PlanTask`, `FileRef`, `build_overlap_graph`, `gate_verdict` wie oben spezifiziert. Regex-Parser über `### Task N: Titel`-Header; `**Files:**`-Block mit `- (Create|Modify|Test|Delete): \`path[:start-end]\``; `**Interfaces:**`-Block mit `Consumes:`/`Produces:`-Prosa; Steps als `- [ ] **Step N: ...**`-Zeilen. Überlappung: exakte oder Verzeichnis-Präfix-Kollision der normalisierten Pfade, plus Heuristik — ein rückwärts-quotiertes Symbol aus einer `Produces`-Zeile, das im `Consumes`-Text einer anderen Task auftaucht, zählt als Abhängigkeit. `files_unknown=True` (kein einziger geparster `FileRef`) überlappt mit jeder anderen Task. `gate_verdict`: bilde Zusammenhangskomponenten des Overlap-Graphen über die übergebene Task-Menge; Singleton-Komponenten sind parallel-fähig; `verdict="parallel"` nur bei ≥3 Singleton-Komponenten, sonst `"sequential"` (bei ≥2 Tasks mit Überlappung) oder `"no-delegate"` (weniger als 3 Tasks insgesamt oder kein Nutzen). `reasoning` ist ein deutscher Fließtext, der die Zahl der Pakete und den Grund nennt.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_subagent_dev_plan_to_tasks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/subagent-dev/scripts/plan_to_tasks.py tests/test_subagent_dev_plan_to_tasks.py
git commit -m "feat(subagent-dev): Plan-Parser und Ueberlappungsmatrix"
```

---

### Task 2: Task-Dateien, CLI und `verify`-Unterkommando

**Files:**
- Modify: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: `parse_plan`, `build_overlap_graph`, `gate_verdict`, `PlanTask`, `FileRef` aus Task 1
- Produces:
  - `render_task_file(task: PlanTask, doc: PlanDoc, plan_path: str) -> str` — Markdown mit Kopfzeile, Ziel, Allowlist, Interfaces, Akzeptanzkriterien, Global Constraints, Nicht-Ziele, abschließendem ` ```json ` -Maschinenblock (`{"task_id", "plan", "allowlist": [str], "produces": [{"name": str, "arity": int | null}]}`)
  - `write_tasks(doc: PlanDoc, plan_path: str, out_dir: Path) -> dict` — schreibt `gate.json` + eine `.md`-Datei je Task, liefert `{"gate": GateResult, "task_files": {task_id: Path}}`
  - `parse_task_machine_block(text: str) -> dict` — liest den eingebetteten JSON-Block einer Task-Datei zurück
  - `extract_produced_symbols(text: str) -> list[tuple[str, int | None]]` — Name + Arity aus \`name(a, b)\`-Backtick-Spans
  - `check_allowlist(worktree: Path, base_ref: str, allowlist: list[str]) -> list[str]` — Liste der Verstöße (geänderte Dateien außerhalb der Allowlist)
  - `check_produces(worktree: Path, allowlist: list[str], produces: list[tuple[str, int | None]]) -> list[dict]` — je Symbol `{"name", "status": "present"|"missing"|"arity_mismatch", "detail"}`, via `ast.parse` auf den Allowlist-Dateien
  - `main(argv) -> int` mit Unterkommandos `generate PLAN [--tasks 1,2] [--out-dir DIR]` und `verify --task-file PATH --worktree DIR [--base REF]`

- [ ] **Step 1: Write the failing tests**

An `tests/test_subagent_dev_plan_to_tasks.py` anhängen:

```python
import ast
import json
import subprocess


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def test_render_task_file_contains_required_sections():
    doc = ptt.parse_plan(SAMPLE_PLAN)
    task1 = doc.tasks[0]
    rendered = ptt.render_task_file(task1, doc, "docs/superpowers/plans/x.md")
    assert rendered.startswith("<!-- skill: subagent-dev | schema: 1 | generated:")
    for heading in ("## Ziel", "## Datei-Allowlist", "## Interfaces", "## Akzeptanzkriterien", "## Global Constraints", "## Nicht-Ziele"):
        assert heading in rendered
    assert "src/parser.py" in rendered
    block = ptt.parse_task_machine_block(rendered)
    assert block["allowlist"] == ["src/parser.py", "tests/test_parser.py"]
    assert {"name": "parse", "arity": 1} in block["produces"]


def test_write_tasks_creates_gate_and_task_files(tmp_path):
    doc = ptt.parse_plan(SAMPLE_PLAN)
    result = ptt.write_tasks(doc, "docs/superpowers/plans/x.md", tmp_path)
    assert (tmp_path / "gate.json").is_file()
    gate = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
    assert gate["_meta"]["skill"] == "subagent-dev"
    assert len(result["task_files"]) == 4
    for path in result["task_files"].values():
        assert path.is_file()


def test_extract_produced_symbols_reads_name_and_arity():
    symbols = ptt.extract_produced_symbols("- Produces:\n  - `parse(line: str) -> dict`\n  - `Config`")
    names = {s[0]: s[1] for s in symbols}
    assert names["parse"] == 1
    assert names["Config"] is None


def test_check_allowlist_flags_file_outside_allowlist(tmp_path):
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()

    (tmp_path / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("y = 1\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "change")

    violations = ptt.check_allowlist(tmp_path, base, ["src/a.py"])
    assert violations == ["other.py"]


def test_check_produces_detects_missing_and_present(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(
        "def parse(line):\n    return {}\n", encoding="utf-8"
    )
    results = ptt.check_produces(tmp_path, ["src/a.py"], [("parse", 1), ("missing_fn", 0)])
    by_name = {r["name"]: r["status"] for r in results}
    assert by_name["parse"] == "present"
    assert by_name["missing_fn"] == "missing"


def test_check_produces_detects_arity_mismatch(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(
        "def parse(line, extra):\n    return {}\n", encoding="utf-8"
    )
    results = ptt.check_produces(tmp_path, ["src/a.py"], [("parse", 1)])
    assert results[0]["status"] == "arity_mismatch"


def test_main_generate_writes_files(tmp_path, monkeypatch):
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(SAMPLE_PLAN, encoding="utf-8")
    out_dir = tmp_path / "out"
    code = ptt.main(["generate", str(plan_path), "--out-dir", str(out_dir)])
    assert code == 0
    assert (out_dir / "gate.json").is_file()


def test_main_verify_reports_violation(tmp_path):
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def parse(line):\n    return {}\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()
    (tmp_path / "outside.py").write_text("z = 1\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "change")

    doc = ptt.parse_plan(SAMPLE_PLAN)
    task_dir = tmp_path / "tasks"
    ptt.write_tasks(doc, "plan.md", task_dir)
    task_file = task_dir / "task-1-parser.md"

    code = ptt.main(["verify", "--task-file", str(task_file), "--worktree", str(tmp_path), "--base", base])
    assert code == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_subagent_dev_plan_to_tasks.py -v`
Expected: FAIL (die neuen Funktionen fehlen noch)

- [ ] **Step 3: Implement Task-Dateien, `write_tasks`, `verify` und `main`**

`render_task_file` erzeugt die Handoff-Datei mit der Kopfzeile aus `docs/artifact-header.md`, den sechs Prosa-Sektionen und einem abschließenden ` ```json `-Block. Nicht-Ziele listet die übrigen Task-Titel des Plans auf. `write_tasks` legt `out_dir` an (Bootstrap-Regel: meldet die Anlage), schreibt `gate.json` (mit `_meta`) aus `gate_verdict`, und je Task eine `.md`-Datei unter `task-<id>-<slug>.md` (Slug: lowercase, nicht-alphanumerisch zu `-`). `check_allowlist` läuft `git diff --name-only <base>...HEAD` plus `git status --porcelain` (uncommittete Änderungen zählen mit) im Worktree und meldet jede geänderte Datei, die nicht exakt oder als Verzeichnis-Präfix in der Allowlist steht. `check_produces` liest jede existierende Allowlist-Datei per `ast.parse` (nie `import`), sammelt `FunctionDef`/`AsyncFunctionDef`/`ClassDef`-Namen (rekursiv über den Baum) mit Arity (Anzahl `args.args`, `self`/`cls` beim ersten Parameter einer Methode nicht mitgezählt), und vergleicht gegen die deklarierten Symbole. `main` verdrahtet `argparse` mit den zwei Unterkommandos; `verify` gibt 1 zurück, wenn Allowlist-Verstöße oder `missing`/`arity_mismatch`-Symbole vorliegen, sonst 0, und druckt eine deutsche Zusammenfassung.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_subagent_dev_plan_to_tasks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/subagent-dev/scripts/plan_to_tasks.py tests/test_subagent_dev_plan_to_tasks.py
git commit -m "feat(subagent-dev): Task-Dateien, generate/verify-CLI"
```

---

### Task 3: SKILL.md und references/

**Files:**
- Create: `skills/subagent-dev/SKILL.md`
- Create: `skills/subagent-dev/references/task-file.md`
- Create: `skills/subagent-dev/references/research-fanout.md`
- Create: `skills/subagent-dev/references/merge-protocol.md`

**Interfaces:**
- Consumes: `plan_to_tasks.py generate`/`verify` aus Task 1+2 (per CLI-Aufruf, kein Python-Import)
- Produces: nichts, was andere Tasks konsumieren — reine Doktrin/Doku

- [ ] **Step 1: SKILL.md schreiben**

Frontmatter nur `name`/`description`. Description trägt die Abgrenzung zu `superpowers:subagent-driven-development` (503-Zeilen-Prosa-Skill, hier: mechanisches Gate + Handoff-Datei) und zu `superpowers:writing-plans` (Planerstellung bleibt dort). Body: Gate-Regeln (Schwelle ≥3, konservative Überlappung), Dispatch-Protokoll (Worktree pro Paralleltask, Task-Datei statt Historie), Kostenrichtwerte (Agent-Spawn ~X Turns, Review-Pass ~Y — grobe, benannte Schätzwerte, keine Telemetrie), Contract (kein Dispatch ohne Task-Datei, `verify` vor Abnahme), Anti-Rationalisierungs-Tabelle aus der Spec, Abgrenzungstabelle. ≤150 Zeilen.

- [ ] **Step 2: references/task-file.md**

Schema der Task-Datei (die sechs Sektionen + JSON-Block) mit einem vollständigen Beispiel, generiert aus einem Mini-Plan.

- [ ] **Step 3: references/research-fanout.md**

Rückgabe-Schema für Recherche-Agents (Findings + Belege/Pfade + Konfidenz), Synthese-Disziplin: destillierte Daten in den Hauptkontext, nie Rohmaterial.

- [ ] **Step 4: references/merge-protocol.md**

Merge-Reihenfolge nach Plan-Abhängigkeit, Tests nach jedem Merge, Interface-Bruch als Gate-Fehler mit Lesson-Vermerk im Plan.

- [ ] **Step 5: Commit**

```bash
git add skills/subagent-dev/SKILL.md skills/subagent-dev/references
git commit -m "docs(subagent-dev): SKILL.md und references"
```

---

### Task 4: Evals (geschrieben, nicht ausgeführt)

**Files:**
- Create: `evals/subagent-dev/evals.json`
- Create: `evals/fixtures/plan-hidden-overlap/fixture.json`
- Create: `evals/fixtures/plan-hidden-overlap/README.md`
- Create: `evals/fixtures/plan-mini-two-tasks/fixture.json`
- Create: `evals/fixtures/plan-mini-two-tasks/README.md`
- Create: `evals/fixtures/plan-disjoint-batch/fixture.json`
- Create: `evals/fixtures/plan-disjoint-batch/README.md`

**Interfaces:**
- Consumes: `evalkit.schema` Assertion-Typen aus dem bestehenden Harness; `.skills/cache/tasks/gate.json` und die Task-`.md`-Dateien aus Task 1+2 als geprüfte Artefakte
- Produces: nichts, was andere Tasks konsumieren

- [ ] **Step 1: Drei Fixtures anlegen**

Jede Fixture bringt `"git": true` und einen `docs/superpowers/plans/<name>.md`-Plan mit (per `touch` im `commits`-Feld): `plan-hidden-overlap` — zwei Tasks mit `Modify: config/shared.yaml` in beiden Files-Blöcken. `plan-mini-two-tasks` — zwei disjunkte Tasks ohne jede Überlappung (Schwellenfall). `plan-disjoint-batch` — vier disjunkte Tasks (parallel-Verdikt erwartbar) plus eine fünfte Task, deren Produces-Signatur absichtlich von dem abweicht, was eine mitgelieferte `worktree-nach-dispatch/`-Kopie zeigt (für den `verify`-Eval; die Fixture legt die "fertige" Datei mit falscher Arity bereits als Repo-Inhalt an, der Prompt bittet die Skill, sie zu prüfen).

- [ ] **Step 2: evals/subagent-dev/evals.json schreiben**

Vier Evals nach Spec 09, jede Assertion an `.skills/cache/tasks/gate.json` oder einer Task-`.md`-Datei:
1. `hidden-overlap-blocks-parallel` (contract, fixture `plan-hidden-overlap`): `gate.json` `verdict` ist nicht `"parallel"`, `file_matches` auf `config/shared.yaml` als Überlappungsgrund.
2. `mini-plan-below-threshold` (contract, fixture `plan-mini-two-tasks`): `verdict` ist `"no-delegate"` oder `"sequential"`, `reasoning`-Text vorhanden (`file_matches` auf einen Begründungs-Marker).
3. `verify-catches-signature-drift` (contract, fixture `plan-disjoint-batch`): nach simuliertem Dispatch liegt ein `verify`-Ergebnis vor, das den Status `arity_mismatch`/`missing` für das abweichende Symbol nennt — geprüft über eine vom Prompt verlangte Log-Datei (`.skills/cache/tasks/verify-task-5.json` o. ä.), da der Harness keinen echten zweiten Agenten-Dispatch simulieren kann; Notiz im Eval hält diese Einschränkung fest.
4. `research-fanout-stays-distilled` (behavior, fixture `plan-disjoint-batch` oder eigene Recherche-Fixture): Judge-Claim, dass der Hauptkontext ein destilliertes Rückgabeschema statt Rohmaterial referenziert.
Pflicht-Anti-Zeremonie-Eval: Eval 2 übernimmt diese Rolle (zwei Tasks sind der triviale Fall, in dem Delegation unterbleiben muss).

- [ ] **Step 3: Commit**

```bash
git add evals/subagent-dev evals/fixtures/plan-hidden-overlap evals/fixtures/plan-mini-two-tasks evals/fixtures/plan-disjoint-batch
git commit -m "test(subagent-dev): Evals geschrieben (nicht ausgefuehrt)"
```

---

### Task 5: Abschlussbericht

**Files:**
- Create: `docs/superpowers/reports/subagent-dev-report.md`

**Interfaces:**
- Consumes: Ergebnisse aller vorigen Tasks (Testlauf, Artefaktliste)
- Produces: nichts

- [ ] **Step 1: Bericht schreiben und committen**

Kopfzeile, Status, gebaute Artefakte, Testergebnis (`.venv/bin/pytest` voller Lauf), Abweichungen von der Spec-Skizze (Eval-Pfad, `verify`-Unterkommando als zusätzliches Werkzeug), bekannte Grenzen (Interface-Heuristik, Arity-nur-Typcheck, fehlende `brief-common.md`), offene Fragen aus der Spec.

```bash
git add docs/superpowers/reports/subagent-dev-report.md
git commit -m "docs(subagent-dev): Abschlussbericht"
```
