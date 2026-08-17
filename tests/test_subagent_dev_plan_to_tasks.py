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


def test_gate_verdict_coupled_pair_below_threshold_is_sequential():
    tasks = [t for t in ptt.parse_plan(SAMPLE_PLAN).tasks if t.id in (1, 2)]
    overlap = {1: {2}, 2: {1}}
    result = ptt.gate_verdict(tasks, overlap)
    assert result.verdict == "sequential"
    assert result.parallel_group == []
    assert result.reasoning


def test_gate_verdict_disjoint_pair_below_threshold_is_no_delegate():
    """Der Anti-Zeremonie-Fall: zwei völlig unabhängige Tasks sind unter der
    Schwelle keinen Dispatch-Overhead wert — anders als ein gekoppeltes Paar,
    das trotzdem sequenziell dispatcht werden würde."""
    tasks = [t for t in ptt.parse_plan(SAMPLE_PLAN).tasks if t.id in (3, 4)]
    overlap = {3: set(), 4: set()}
    result = ptt.gate_verdict(tasks, overlap)
    assert result.verdict == "no-delegate"
    assert result.parallel_group == []
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


def test_main_verify_writes_json_artifact_when_out_given(tmp_path):
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "parser.py").write_text("def parse(line, extra):\n    return {}\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_parser.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "base")

    doc = ptt.parse_plan(SAMPLE_PLAN)
    task_dir = tmp_path.parent / "tasks-out-artifact"
    ptt.write_tasks(doc, "plan.md", task_dir)
    task_file = task_dir / "task-1-parser.md"
    out_path = tmp_path.parent / "verify-out" / "task-1.json"

    code = ptt.main(["verify", "--task-file", str(task_file), "--worktree", str(tmp_path), "--out", str(out_path)])
    assert code == 1
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["_meta"]["skill"] == "subagent-dev"
    assert payload["ok"] is False
    assert payload["produces"][0]["status"] == "arity_mismatch"


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


# --------------------------------------------------------------------------
# Fix-Runde: D1 — verify meldet nie PASS für eine übersprungene Allowlist-Prüfung
# --------------------------------------------------------------------------


def test_verify_without_base_never_reports_pass_even_if_allowlist_violated(tmp_path):
    """Reproduziert D1: --base fehlt, ein Agent hat nachweislich außerhalb
    seiner Allowlist geschrieben (src/secrets.py) — vorher meldete das Skript
    trotzdem 'ok': true, weil check_allowlist ohne --base gar nicht lief."""
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "parser.py").write_text("def parse(line):\n    return {}\n", encoding="utf-8")
    (tmp_path / "src" / "secrets.py").write_text("TOKEN = 'x'\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_parser.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "base")

    doc = ptt.parse_plan(SAMPLE_PLAN)
    task_dir = tmp_path.parent / "tasks-d1-no-base"
    ptt.write_tasks(doc, "plan.md", task_dir)
    task_file = task_dir / "task-1-parser.md"
    out_path = tmp_path.parent / "verify-d1-no-base.json"

    code = ptt.main(["verify", "--task-file", str(task_file), "--worktree", str(tmp_path), "--out", str(out_path)])
    assert code != 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["allowlist_checked"] is False
    assert payload["verdict"] != "pass"
    assert payload["ok"] is False


def test_verify_without_base_reports_unverified_not_fail_when_nothing_else_wrong(tmp_path):
    """Produces stimmt, nur die Allowlist-Prüfung ist ungeprüft — das Verdikt
    ist 'unverified', keine erfundene Zustimmung und kein erfundener Fehler."""
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "parser.py").write_text("def parse(line):\n    return {}\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_parser.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "base")

    doc = ptt.parse_plan(SAMPLE_PLAN)
    task_dir = tmp_path.parent / "tasks-d1-unverified"
    ptt.write_tasks(doc, "plan.md", task_dir)
    task_file = task_dir / "task-1-parser.md"
    out_path = tmp_path.parent / "verify-d1-unverified.json"

    code = ptt.main(["verify", "--task-file", str(task_file), "--worktree", str(tmp_path), "--out", str(out_path)])
    assert code != 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "unverified"
    assert payload["ok"] is False


def test_verify_with_base_still_reports_pass_when_actually_clean(tmp_path):
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
    task_dir = tmp_path.parent / "tasks-d1-pass"
    ptt.write_tasks(doc, "plan.md", task_dir)
    task_file = task_dir / "task-1-parser.md"
    out_path = tmp_path.parent / "verify-d1-pass.json"

    code = ptt.main(["verify", "--task-file", str(task_file), "--worktree", str(tmp_path), "--base", base, "--out", str(out_path)])
    assert code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["allowlist_checked"] is True
    assert payload["verdict"] == "pass"
    assert payload["ok"] is True


# --------------------------------------------------------------------------
# Fix-Runde: D2 — Datei-Überlappung normalisiert Case/Absolut/Glob/Backslash,
# und ein nicht erkanntes Files:-Vokabular (Rename mit eigenem Wortlaut) macht
# die Task-Files unsicher statt spurlos zu verschwinden.
# --------------------------------------------------------------------------


def test_paths_overlap_ignores_case_drift():
    assert ptt._paths_overlap("Config/settings.py", "config/settings.py") is True


def test_paths_overlap_matches_absolute_against_relative():
    assert ptt._paths_overlap("/home/user/repo/src/a.py", "src/a.py") is True


def test_paths_overlap_treats_double_star_glob_as_its_root_directory():
    assert ptt._paths_overlap("src/**/*.py", "src/utils.py") is True


def test_paths_overlap_treats_single_star_glob_as_its_root_directory():
    assert ptt._paths_overlap("src/*.py", "src/utils.py") is True


def test_paths_overlap_normalizes_windows_backslashes():
    assert ptt._paths_overlap("config\\shared.yaml", "config/shared.yaml") is True


def test_paths_overlap_still_false_for_genuinely_unrelated_paths():
    """Regressionsschutz: die neuen Regeln dürfen nicht alles zu einer
    Überlappung machen."""
    assert ptt._paths_overlap("src/parser.py", "docs/notes.md") is False


def test_parse_files_recognizes_explicit_rename_line():
    block = (
        "\n**Files:**\n"
        "- Rename: `helpers.py` -> `utils.py`\n"
        "\n**Interfaces:**\n- Consumes: nichts Neues\n- Produces: nichts Neues\n"
        "\n- [ ] **Step 1: x**\n"
    )
    refs, files_unknown = ptt._parse_files(block)
    assert files_unknown is False
    assert {r.path for r in refs} == {"helpers.py", "utils.py"}


def test_parse_files_rename_creates_real_overlap_with_touching_task():
    """Reproduziert den 'schwersten' Fall aus D2: Task 1 benennt helpers.py in
    utils.py um, Task 2 modifiziert utils.py — das muss jetzt als echte
    Datei-Überlappung erkannt werden, nicht stillschweigend übersehen."""
    plan = """## Global Constraints

- x

---

### Task 1: Rename helpers

**Files:**
- Rename: `helpers.py` -> `utils.py`

**Interfaces:**
- Consumes: nichts Neues
- Produces: nichts Neues

- [ ] **Step 1: x**

### Task 2: Touch utils

**Files:**
- Modify: `utils.py`

**Interfaces:**
- Consumes: nichts Neues
- Produces: nichts Neues

- [ ] **Step 1: x**
"""
    doc = ptt.parse_plan(plan)
    overlap = ptt.build_overlap_graph(doc.tasks)
    assert overlap[1] == {2}
    assert overlap[2] == {1}


def test_parse_files_unrecognized_verb_forces_files_unknown():
    """Sicherheitsnetz: eine Bullet-Zeile im Files:-Block mit einem Verb, das
    kein bekanntes Muster erfüllt, macht die ganze Task-Files-Liste unsicher —
    selbst wenn andere Zeilen im selben Block sauber geparst wurden."""
    block = (
        "\n**Files:**\n"
        "- Modify: `config.py`\n"
        "- Touch: `weird.py`\n"
        "\n**Interfaces:**\n- Consumes: nichts Neues\n- Produces: nichts Neues\n"
        "\n- [ ] **Step 1: x**\n"
    )
    refs, files_unknown = ptt._parse_files(block)
    assert files_unknown is True
    # Die erkannte Zeile wird trotzdem übernommen — files_unknown ist die
    # Sicherung, kein Grund, bereits Geparstes wegzuwerfen.
    assert any(r.path == "config.py" for r in refs)


# --------------------------------------------------------------------------
# Fix-Runde: D3 — Interface-Prosa ohne Backtick-Symbol macht die Task unsicher
# --------------------------------------------------------------------------


def test_has_unrecognized_prose_flags_plain_prose():
    assert ptt._has_unrecognized_prose("die Parse-Funktion aus Task 1, um Zeilen zu verarbeiten") is True


def test_has_unrecognized_prose_accepts_nichts_neues():
    assert ptt._has_unrecognized_prose("nichts Neues") is False
    assert ptt._has_unrecognized_prose("(nichts Neues)") is False
    assert ptt._has_unrecognized_prose("") is False


def test_has_unrecognized_prose_accepts_text_with_backtick_symbol():
    assert ptt._has_unrecognized_prose("`parse(line: str) -> dict` aus Task 1") is False


def test_gate_verdict_forces_serialization_when_consumes_is_unrecognized_prose():
    """Reproduziert D3: vier dateiseitig disjunkte Tasks, aber Task 2s
    Consumes:-Feld nennt eine echte Abhängigkeit in reiner Prosa ohne
    Backticks. Vorher: verdict='parallel' mit der aktiv falschen Begründung
    'Keine ... überlappt'. Jetzt: die Prosa macht Task 2 sicherheitshalber
    mit jeder anderen Task überlappend."""
    plan = """## Global Constraints

- x

---

### Task 1: Parser

**Files:**
- Create: `a.py`

**Interfaces:**
- Consumes: nichts Neues
- Produces:
  - `parse(line: str) -> dict`

- [ ] **Step 1: x**

### Task 2: Consumer

**Files:**
- Create: `b.py`

**Interfaces:**
- Consumes: die Parse-Funktion aus Task 1, um Zeilen zu verarbeiten
- Produces: nichts Neues

- [ ] **Step 1: x**

### Task 3: C

**Files:**
- Create: `c.py`

**Interfaces:**
- Consumes: nichts Neues
- Produces: nichts Neues

- [ ] **Step 1: x**

### Task 4: D

**Files:**
- Create: `d.py`

**Interfaces:**
- Consumes: nichts Neues
- Produces: nichts Neues

- [ ] **Step 1: x**
"""
    doc = ptt.parse_plan(plan)
    task2 = next(t for t in doc.tasks if t.id == 2)
    assert task2.interfaces_unknown is True

    overlap = ptt.build_overlap_graph(doc.tasks)
    assert overlap[2] == {1, 3, 4}

    result = ptt.gate_verdict(doc.tasks, overlap)
    # Task 2 überlappt jetzt mit allem -> nur Tasks 1, 3, 4 sind Singleton-
    # Kandidaten, das sind lediglich drei, und Task 2 selbst ist blockiert.
    assert 2 not in result.parallel_group


# --------------------------------------------------------------------------
# Fix-Runde: L2 — check_produces verwechselt keine gleichnamigen Definitionen
# unterschiedlichen Scopes mehr stillschweigend
# --------------------------------------------------------------------------


def test_check_produces_reports_ambiguous_when_no_definition_matches_and_several_exist(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(
        "def parse(line, extra):\n    return {}\n\n\nclass A:\n    def helper(self, x, y):\n        pass\n\n\nclass B:\n    def helper(self, x, y, z):\n        pass\n",
        encoding="utf-8",
    )
    results = ptt.check_produces(tmp_path, ["src/a.py"], [("helper", 1)])
    assert results[0]["status"] == "ambiguous"
    assert "2 unterschiedliche" in results[0]["detail"] or "unterschiedliche Definitionen" in results[0]["detail"]


def test_check_produces_present_with_note_when_one_of_several_definitions_matches(tmp_path):
    """Der Top-Level-Fall aus L2: eine drifted Top-Level-Funktion (Arity 2)
    UND eine unabhängige, richtig-signierte innere Funktion (Arity 1)
    desselben Namens. check_produces darf das Symbol nicht länger anhand der
    zufällig zuletzt besuchten Definition beurteilen, sondern muss die
    Mehrdeutigkeit im Detail-Text offenlegen."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(
        "def parse(line, extra):\n    def parse(line):\n        return {}\n    return parse(line)\n",
        encoding="utf-8",
    )
    results = ptt.check_produces(tmp_path, ["src/a.py"], [("parse", 1)])
    assert results[0]["status"] == "present"
    assert "weitere Definitionen" in results[0]["detail"]


# --------------------------------------------------------------------------
# Fix-Runde: L3 — check_allowlist parst uncommittete Umbenennungen korrekt
# --------------------------------------------------------------------------


def test_check_allowlist_handles_uncommitted_rename_within_allowlist(tmp_path):
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "old_name.py").write_text("def old():\n    return 1\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()

    git(tmp_path, "mv", "src/old_name.py", "src/new_name.py")

    # Allowlist enthält beide Pfade, wie plan_to_tasks.py sie aus einer
    # 'Rename:'-Zeile ableiten würde (D2).
    violations = ptt.check_allowlist(tmp_path, base, ["src/old_name.py", "src/new_name.py"])
    assert violations == []


def test_check_allowlist_uncommitted_rename_outside_allowlist_is_a_legible_violation(tmp_path):
    """Vorher: 'src/old_name.py -> src/new_name.py' als EIN Pfad, der mit
    nichts matchen kann. Jetzt: zwei echte, einzeln nachvollziehbare Pfade."""
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "old_name.py").write_text("def old():\n    return 1\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()
    git(tmp_path, "mv", "src/old_name.py", "src/new_name.py")

    violations = ptt.check_allowlist(tmp_path, base, ["src/unrelated.py"])
    assert " -> " not in " ".join(violations)
    assert set(violations) == {"src/old_name.py", "src/new_name.py"}
