import json
import subprocess

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


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


# --------------------------------------------------------------------------
# Task 1: Parser + Überlappungsmatrix
# --------------------------------------------------------------------------


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


def test_parse_plan_global_constraints_excludes_its_own_heading():
    doc = ptt.parse_plan(SAMPLE_PLAN)
    assert not doc.global_constraints.startswith("#")
    assert doc.global_constraints.startswith("- Alles auf Deutsch.")


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
    # Task 3/4 (dieselbe Config-Datei) überlappen nicht mit Task 1 — das
    # Interface-Overlap zwischen 1 und 2 wird in der nächsten Testfunktion
    # separat geprüft.
    assert overlap[1] - {2} == set()
    assert 3 not in overlap[1] and 4 not in overlap[1]


def test_overlap_graph_flags_interface_dependency():
    doc = ptt.parse_plan(SAMPLE_PLAN)
    overlap = ptt.build_overlap_graph(doc.tasks)
    # Task 2 konsumiert parse(), das Task 1 produziert -> Abhängigkeit trotz
    # disjunkter Files. Beide Richtungen tragen dieselbe Kante.
    assert 1 in overlap[2]
    assert 2 in overlap[1]


def test_gate_verdict_below_threshold_is_no_delegate():
    tasks = [t for t in ptt.parse_plan(SAMPLE_PLAN).tasks if t.id in (1, 2)]
    overlap = {1: {2}, 2: {1}}
    result = ptt.gate_verdict(tasks, overlap)
    assert result.verdict in ("no-delegate", "sequential")
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


def test_parse_plan_rejects_text_without_task_headers():
    import pytest
    with pytest.raises(ptt.PlanParseError):
        ptt.parse_plan("# Kein Plan\n\nNur Prosa, keine Task-Header.")


def test_parse_plan_rejects_duplicate_task_ids():
    import pytest
    dup = SAMPLE_PLAN + "\n### Task 1: Doppelt\n\n**Files:**\n- Create: `x.py`\n"
    with pytest.raises(ptt.PlanParseError):
        ptt.parse_plan(dup)


def test_parse_plan_ignores_task_headers_inside_fenced_code():
    """Ein Plan, der (wie dieser hier) einen Beispiel-Plan als Codeblock
    zitiert, darf die zitierten '### Task N:'-Header nicht als echte Struktur
    lesen — sonst kollidieren Task-IDs oder Files:/Steps: werden verfälscht."""
    plan = SAMPLE_PLAN.replace(
        "- [ ] **Step 1: Write the failing test**\n\n- [ ] **Step 2: Implement**",
        "- [ ] **Step 1: Write the failing test**\n\n"
        "```python\nZITAT = '''\n### Task 1: Geister-Task\n\n"
        "**Files:**\n- Create: `geist.py`\n'''\n```\n\n"
        "- [ ] **Step 2: Implement**",
    )
    doc = ptt.parse_plan(plan)
    assert [t.id for t in doc.tasks] == [1, 2, 3, 4]
    assert doc.tasks[0].files[0].path == "src/parser.py"


def test_gate_verdict_at_least_three_singletons_is_parallel():
    plan = """## Global Constraints

- x

---

### Task 1: A

**Files:**
- Create: `a.py`

**Interfaces:**
- Consumes: nichts Neues
- Produces: nichts Neues

- [ ] **Step 1: x**

### Task 2: B

**Files:**
- Create: `b.py`

**Interfaces:**
- Consumes: nichts Neues
- Produces: nichts Neues

- [ ] **Step 1: x**

### Task 3: C

**Files:**
- Create: `c.py`

**Interfaces:**
- Consumes: nichts Neues
- Produces: nichts Neues

- [ ] **Step 1: x**
"""
    doc = ptt.parse_plan(plan)
    overlap = ptt.build_overlap_graph(doc.tasks)
    result = ptt.gate_verdict(doc.tasks, overlap)
    assert result.verdict == "parallel"
    assert sorted(result.parallel_group) == [1, 2, 3]


# --------------------------------------------------------------------------
# Task 2: Task-Dateien, generate/verify-CLI
# --------------------------------------------------------------------------


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


def test_check_allowlist_allows_directory_prefix(tmp_path):
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()

    (tmp_path / "src" / "b.py").write_text("y = 1\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "change")

    violations = ptt.check_allowlist(tmp_path, base, ["src"])
    assert violations == []


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


def test_check_produces_never_imports_module_with_side_effects(tmp_path):
    """Ein Modul, das beim Import abstürzen würde, darf `check_produces` trotzdem
    prüfen können — das Skript liest per `ast`, führt den Code nie aus."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(
        "raise RuntimeError('würde beim Import crashen')\n\n\ndef parse(line):\n    return {}\n",
        encoding="utf-8",
    )
    results = ptt.check_produces(tmp_path, ["src/a.py"], [("parse", 1)])
    assert results[0]["status"] == "present"


def test_main_generate_writes_files(tmp_path):
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(SAMPLE_PLAN, encoding="utf-8")
    out_dir = tmp_path / "out"
    code = ptt.main(["generate", str(plan_path), "--out-dir", str(out_dir)])
    assert code == 0
    assert (out_dir / "gate.json").is_file()


def test_main_generate_respects_task_filter(tmp_path):
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(SAMPLE_PLAN, encoding="utf-8")
    out_dir = tmp_path / "out"
    code = ptt.main(["generate", str(plan_path), "--tasks", "1,2", "--out-dir", str(out_dir)])
    assert code == 0
    gate = json.loads((out_dir / "gate.json").read_text(encoding="utf-8"))
    assert [t["id"] for t in gate["tasks"]] == [1, 2]


def test_main_verify_reports_violation(tmp_path):
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "parser.py").write_text("def parse(line):\n    return {}\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_parser.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()
    (tmp_path / "outside.py").write_text("z = 1\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "change")

    doc = ptt.parse_plan(SAMPLE_PLAN)
    # Task-Verzeichnis bewusst außerhalb des geprüften Worktrees: In echter
    # Nutzung liegt `.skills/cache/tasks/` im Plan-Repo, während `verify` gegen
    # den isolierten Worktree eines einzelnen Task-Dispatches läuft.
    task_dir = tmp_path.parent / "tasks-out-of-worktree"
    ptt.write_tasks(doc, "plan.md", task_dir)
    task_file = task_dir / "task-1-parser.md"

    code = ptt.main(["verify", "--task-file", str(task_file), "--worktree", str(tmp_path), "--base", base])
    assert code == 1


def test_main_verify_passes_when_clean(tmp_path):
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "parser.py").write_text("def parse(line):\n    return {}\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_parser.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()

    doc = ptt.parse_plan(SAMPLE_PLAN)
    task_dir = tmp_path.parent / "tasks-out-of-worktree-clean"
    ptt.write_tasks(doc, "plan.md", task_dir)
    task_file = task_dir / "task-1-parser.md"

    code = ptt.main(["verify", "--task-file", str(task_file), "--worktree", str(tmp_path), "--base", base])
    assert code == 0
