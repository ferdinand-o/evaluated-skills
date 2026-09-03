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
    assert {"kind": "fn", "name": "parse", "arity": 1} in block["produces"]


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
    symbols = [(n, a) for _, n, a in ptt.extract_symbols("- Produces:\n  - `parse(line: str) -> dict`\n  - `Config`")]
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


# --- Fail-Closed für Backtick-Ausdrücke ohne Bezeichner + Lint (Einsatz an Spec 15) ---

def _task_block(interfaces: str) -> str:
    return (
        "### Task 1: X\n\n**Files:**\n- Create: `a.py`\n\n**Interfaces:**\n"
        + interfaces + "\n\n- [ ] **Step 1: tun**\n"
    )


def test_backtick_span_without_identifier_makes_interfaces_unknown():
    """Das Fail-Open aus known-limits: `Unverified:` liefert kein Symbol, wurde
    aber nicht als unbekannt markiert, weil ein Backtick vorhanden war."""
    doc = ptt.parse_plan(_task_block("- Consumes: (nichts Neues)\n- Produces: `Unverified:`, `token_next`"))
    assert doc.tasks[0].interfaces_unknown is True
    assert ptt.unextractable_backtick_spans("`Unverified:`, `token_next`") == ["Unverified:"]


def test_valid_identifier_symbols_keep_interfaces_known():
    doc = ptt.parse_plan(_task_block("- Consumes: (nichts Neues)\n- Produces: `marker_unverified`, `token_next`"))
    assert doc.tasks[0].interfaces_unknown is False


def test_sub_bullets_under_produces_are_symbols_not_prose():
    """Die übliche Form im Repo: `- Produces:` allein, darunter je Symbol ein
    eingerückter Bullet. Muss Symbole liefern, keine Prosa-Befunde."""
    block = _task_block(
        "- Consumes: `evalkit`\n- Produces:\n  - `collect.commits(repo, rev)`\n  - `collect.main(argv)`"
    )
    consumes, produces, stray = ptt._interface_lines(block)
    assert stray == []
    assert [n for _, n, _ in ptt.extract_symbols(produces)] == ["collect.commits", "collect.main"]
    assert ptt.parse_plan(block).tasks[0].interfaces_unknown is False


def test_prose_paragraph_after_produces_is_stray_not_swallowed():
    """Der zweite Defekt aus known-limits: Prosa unter dem Interfaces-Block lief
    in Produces hinein und machte die Task unbekannt — sequential mit falscher
    Begründung."""
    block = _task_block("- Consumes: (nichts Neues)\n- Produces: `token_next`\nOhne diesen Task ist nichts erreichbar.")
    consumes, produces, stray = ptt._interface_lines(block)
    assert produces == "`token_next`"
    assert stray == ["Ohne diesen Task ist nichts erreichbar."]
    assert ptt.parse_plan(block).tasks[0].interfaces_unknown is False


HEADER = "<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->"

CLEAN_PLAN = HEADER + """

# P

**Goal:** x
**Spec:** `spec.md`

### Task 1: A

**Files:**
- Create: `a.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `parse(line)`

- [ ] **Step 1: tun**
"""

DIRTY_PLAN = """# P

**Goal:** x
**Spec:** `fehlt.md`

### Task 1: A

**Files:**
- Create: `a.py`
- Touch: `b.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `Unverified:`
Prosa hier.

- [ ] **Step 1: tun** TBD

### Task 2: B

**Files:**
- Create: `c.py`

**Interfaces:**
- Consumes: `parse(line)`
- Produces: (nichts Neues)

- [ ] ohne Step-Format
"""


def test_lint_clean_plan_has_no_findings(tmp_path):
    (tmp_path / "spec.md").write_text("s", encoding="utf-8")
    plan = tmp_path / "plan.md"
    plan.write_text(CLEAN_PLAN, encoding="utf-8")
    assert ptt.lint_plan(CLEAN_PLAN, plan) == []


def test_lint_names_every_reason(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text(DIRTY_PLAN, encoding="utf-8")
    messages = [f.render() for f in ptt.lint_plan(DIRTY_PLAN, plan)]
    joined = "\n".join(messages)
    assert "fehlt.md" in joined and "nicht gefunden" in joined
    assert "Platzhalter 'TBD'" in joined
    assert "Touch:" in joined and "files_unknown" in joined
    assert "`Unverified:`" in joined and "fail-closed" in joined
    assert "Prosa im Interfaces-Block" in joined and "Prosa hier." in joined
    assert "Task 2: keine Steps" in joined
    assert "Kopfzeile fehlt" in joined


def test_main_lint_exit_codes(tmp_path, capsys):
    (tmp_path / "spec.md").write_text("s", encoding="utf-8")
    clean = tmp_path / "clean.md"; clean.write_text(CLEAN_PLAN, encoding="utf-8")
    dirty = tmp_path / "dirty.md"; dirty.write_text(DIRTY_PLAN, encoding="utf-8")
    broken = tmp_path / "broken.md"; broken.write_text("# kein Task\n", encoding="utf-8")
    out = tmp_path / "lint.json"

    assert ptt.main(["lint", str(clean)]) == 0
    assert "Keine Befunde" in capsys.readouterr().out
    assert ptt.main(["lint", str(dirty), "--out", str(out)]) == 1
    assert "nicht umformulieren, bis es 'parallel' sagt" in capsys.readouterr().out
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "findings"
    assert ptt.main(["lint", str(broken)]) == 2
    assert "nicht parsbar" in capsys.readouterr().err


# --- Spec 16: Interface-Vokabular, Kopfzeile, Spec-Coverage, _meta --------------

def test_prefixed_symbols_are_extracted_with_kind():
    got = ptt.extract_symbols("`fn:parse(line)`, `token:Next`, `file:docs/x.md`, `bare_name`")
    assert ("fn", "parse", 1) in got
    assert ("token", "Next", None) in got
    assert ("file", "docs/x.md", None) in got
    assert ("fn", "bare_name", None) in got


def test_unknown_prefix_stays_fail_closed():
    assert ptt.symbol_kind("foo:bar") is None
    assert ptt.unextractable_backtick_spans("`foo:bar`") == ["foo:bar"]
    assert ptt.unextractable_backtick_spans("`token:Next`, `file:a.md`") == []


def test_token_with_trailing_colon_is_matched_as_dependency():
    """`Unverified:` endet auf ein Nicht-Wortzeichen — ein \\b-Muster griffe nie."""
    plan = (
        "### Task 1: A\n\n**Files:**\n- Create: `a.md`\n\n**Interfaces:**\n"
        "- Consumes: (nichts Neues)\n- Produces: `token:Unverified:`\n\n- [ ] **Step 1: x**\n"
        "### Task 2: B\n\n**Files:**\n- Create: `b.md`\n\n**Interfaces:**\n"
        "- Consumes: `token:Unverified:`\n- Produces: (nichts Neues)\n\n- [ ] **Step 1: y**\n"
    )
    doc = ptt.parse_plan(plan)
    assert 2 in ptt.build_overlap_graph(doc.tasks)[1]


def test_file_consumption_overlaps_with_the_task_that_writes_it():
    plan = (
        "### Task 1: A\n\n**Files:**\n- Create: `docs/x.md`\n\n**Interfaces:**\n"
        "- Consumes: (nichts Neues)\n- Produces: (nichts Neues)\n\n- [ ] **Step 1: x**\n"
        "### Task 2: B\n\n**Files:**\n- Create: `other.md`\n\n**Interfaces:**\n"
        "- Consumes: `file:docs/x.md`\n- Produces: (nichts Neues)\n\n- [ ] **Step 1: y**\n"
    )
    doc = ptt.parse_plan(plan)
    assert doc.tasks[1].consumed_files == ["docs/x.md"]
    assert doc.tasks[1].interfaces_unknown is False
    assert 1 in ptt.build_overlap_graph(doc.tasks)[2]


def test_check_produces_token_by_text_search(tmp_path):
    (tmp_path / "SKILL.md").write_text("Teil 3 beginnt mit `Next:`.\n", encoding="utf-8")
    present, missing = ptt.check_produces(tmp_path, ["SKILL.md"], [("token", "Next:", None), ("token", "Absent:", None)])
    assert present["status"] == "present"
    assert missing["status"] == "missing"


def test_check_produces_accepts_legacy_pairs_as_fn(tmp_path):
    (tmp_path / "a.py").write_text("def parse(line):\n    return 1\n", encoding="utf-8")
    assert ptt.check_produces(tmp_path, ["a.py"], [("parse", 1)])[0]["status"] == "present"


def test_machine_block_carries_kind_and_verify_reads_it_back(tmp_path, monkeypatch):
    """Die Verdrahtung: kind aus dem Plan landet im Maschinenblock und verify
    prüft einen token per Textsuche — nicht per ast, das ihn nie fände."""
    plan = tmp_path / "plan.md"
    plan.write_text(
        "### Task 1: Doktrin\n\n**Files:**\n- Create: `SKILL.md`\n\n**Interfaces:**\n"
        "- Consumes: (nichts Neues)\n- Produces: `token:Next:`\n\n- [ ] **Step 1: x**\n",
        encoding="utf-8",
    )
    out = tmp_path / "tasks"
    assert ptt.main(["generate", str(plan), "--out-dir", str(out)]) == 0
    task_file = next(out.glob("task-1-*.md"))
    assert ptt.parse_task_machine_block(task_file.read_text(encoding="utf-8"))["produces"] == [
        {"kind": "token", "name": "Next:", "arity": None}
    ]
    worktree = tmp_path / "wt"
    worktree.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=worktree, check=True)
    (worktree / "SKILL.md").write_text("Teil 3: `Next:`\n", encoding="utf-8")
    result_file = tmp_path / "verify.json"
    ptt.main(["verify", "--task-file", str(task_file), "--worktree", str(worktree), "--out", str(result_file)])
    result = json.loads(result_file.read_text(encoding="utf-8"))
    assert result["produces"] == [{"name": "Next:", "status": "present", "detail": result["produces"][0]["detail"]}]
    assert result["verdict"] == "unverified"  # kein --base: Allowlist ungeprüft, nie "pass"

    (worktree / "SKILL.md").write_text("Teil 3 ohne den Token\n", encoding="utf-8")
    ptt.main(["verify", "--task-file", str(task_file), "--worktree", str(worktree), "--out", str(result_file)])
    result = json.loads(result_file.read_text(encoding="utf-8"))
    assert result["produces"][0]["status"] == "missing" and result["verdict"] == "fail"


def test_file_in_produces_is_a_lint_finding(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text(
        HEADER + "\n\n**Goal:** x\n**Spec:** `spec.md`\n\n### Task 1: A\n\n**Files:**\n- Create: `a.md`\n\n"
        "**Interfaces:**\n- Consumes: (nichts Neues)\n- Produces: `file:a.md`\n\n- [ ] **Step 1: x**\n",
        encoding="utf-8",
    )
    (tmp_path / "spec.md").write_text("s", encoding="utf-8")
    msgs = [f.message for f in ptt.lint_plan(plan.read_text(encoding="utf-8"), plan)]
    assert any("gehört in **Files:**" in m for m in msgs)


def test_check_header_variants():
    assert ptt.check_header(HEADER + "\n# P\n") is None
    assert "fehlt" in ptt.check_header("# P\n")
    assert "fremd" in ptt.check_header("<!-- skill: subagent-dev | schema: 1 | generated: x -->\n")


SPEC_WITH_TABLE = """# Spec

## Contract

| Feld | id | Typ |
| --- | --- | --- |
| Nutzer | `user_id` | int |

### Evals

| # | id | Klasse | Fixture |
| --- | --- | --- | --- |
| 1 | `alpha-eval` | contract | `f` |
| 2 | `beta-eval` | contract | `f` |
"""


def test_spec_eval_ids_reads_id_column_under_the_evals_heading_only():
    """Die Contract-Tabelle mit `user_id` davor zählt nicht — sonst meldete der Lint
    `user_id` als fehlenden Task und prüfte die echten IDs nie."""
    assert ptt.spec_eval_ids(SPEC_WITH_TABLE) == ["alpha-eval", "beta-eval"]
    assert ptt.spec_eval_ids("# Spec\n\n**Evals:** (1) … (2) …\n") is None
    no_heading = SPEC_WITH_TABLE.replace("### Evals", "### Tabelle")
    assert ptt.spec_eval_ids(no_heading) is None


def test_spec_eval_table_reports_id_cells_without_backticks():
    spec = SPEC_WITH_TABLE + "| 3 | gamma-eval | contract | `f` |\n"
    ids, malformed = ptt.spec_eval_table(spec)
    assert ids == ["alpha-eval", "beta-eval"] and malformed == ["gamma-eval"]


def _plan_with_steps(step_text: str, spec_ref: str = "spec.md") -> str:
    return (
        HEADER + f"\n\n**Goal:** x\n**Spec:** `{spec_ref}`\n\n### Task 1: Evals\n\n**Files:**\n- Create: `e.json`\n\n"
        "**Interfaces:**\n- Consumes: (nichts Neues)\n- Produces: `evals`\n\n" + step_text
    )


def test_lint_resolves_coverage_from_the_plans_own_spec_line(tmp_path):
    """Coverage ist eine Eigenschaft des Plans, nicht des Aufrufs: ohne --spec
    zählt die Datei aus der **Spec:**-Zeile — so sieht der Repo-Test sie auch."""
    (tmp_path / "spec.md").write_text(SPEC_WITH_TABLE, encoding="utf-8")
    plan = tmp_path / "plan.md"
    plan.write_text(_plan_with_steps("- [ ] **Step 1: alpha-eval anlegen**\n"), encoding="utf-8")
    report = ptt.lint_report(plan.read_text(encoding="utf-8"), plan)
    assert report.coverage["status"] == "checked" and report.coverage["ids_checked"] == 2
    assert any("`beta-eval` aus der Spec hat keinen Task" in f.message for f in report.findings)


def test_lint_coverage_counts_whole_ids_inside_task_blocks_only(tmp_path):
    (tmp_path / "spec.md").write_text(SPEC_WITH_TABLE, encoding="utf-8")
    plan = tmp_path / "plan.md"
    text = _plan_with_steps("- [ ] **Step 1: stale-alpha-eval-foo anlegen**\n")
    text = text.replace("**Goal:** x", "**Goal:** x — beta-eval steht hier im Kopf, nicht in einem Task")
    plan.write_text(text, encoding="utf-8")
    msgs = [f.message for f in ptt.lint_plan(plan.read_text(encoding="utf-8"), plan)]
    assert any("`alpha-eval` aus der Spec hat keinen Task" in m for m in msgs)
    assert any("`beta-eval` aus der Spec hat keinen Task" in m for m in msgs)


def test_lint_malformed_id_row_is_a_finding(tmp_path):
    (tmp_path / "spec.md").write_text(SPEC_WITH_TABLE + "| 3 | gamma-eval | contract | `f` |\n", encoding="utf-8")
    plan = tmp_path / "plan.md"
    plan.write_text(_plan_with_steps("- [ ] **Step 1: alpha-eval, beta-eval, gamma-eval**\n"), encoding="utf-8")
    msgs = [f.message for f in ptt.lint_plan(plan.read_text(encoding="utf-8"), plan)]
    assert any("id-Zelle ohne Backtick-Wert" in m and "gamma-eval" in m for m in msgs)


def test_lint_skill_without_any_spec_is_a_finding_not_silence(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text(_plan_with_steps("- [ ] **Step 1: x**\n", spec_ref="missing.md"), encoding="utf-8")
    msgs = [f.message for f in ptt.lint_plan(plan.read_text(encoding="utf-8"), plan, skill="x")]
    assert any("--skill x ohne Spec" in m for m in msgs)


def test_lint_out_json_marks_unchecked_coverage_and_full_command(tmp_path):
    (tmp_path / "spec ohne tabelle.md").write_text("# Spec\n\nEvals in Prosa.\n", encoding="utf-8")
    plan = tmp_path / "plan.md"
    plan.write_text(_plan_with_steps("- [ ] **Step 1: x**\n", spec_ref="spec ohne tabelle.md"), encoding="utf-8")
    out = tmp_path / "lint.json"
    assert ptt.main(["lint", str(plan), "--spec", str(tmp_path / "spec ohne tabelle.md"), "--skill", "x", "--out", str(out)]) == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["coverage"]["status"] == "unchecked" and "keine Eval-Tabelle" in data["coverage"]["reason"]
    assert "--spec" in data["_meta"]["generated"] and "--skill x" in data["_meta"]["generated"]
    assert "tabelle.md'" in data["_meta"]["generated"]  # Pfad mit Leerzeichen ist shell-quotiert
    assert any("evals/x/evals.json nicht gefunden" in f["message"] for f in data["findings"])


def test_lint_reports_uncovered_spec_eval_ids(tmp_path):
    (tmp_path / "spec.md").write_text(SPEC_WITH_TABLE, encoding="utf-8")
    plan = tmp_path / "plan.md"
    plan.write_text(
        HEADER + "\n\n**Goal:** x\n**Spec:** `spec.md`\n\n### Task 1: Evals\n\n**Files:**\n- Create: `e.json`\n\n"
        "**Interfaces:**\n- Consumes: (nichts Neues)\n- Produces: `evals`\n\n- [ ] **Step 1: alpha-eval anlegen**\n",
        encoding="utf-8",
    )
    msgs = [f.message for f in ptt.lint_plan(plan.read_text(encoding="utf-8"), plan, spec_path=tmp_path / "spec.md")]
    assert any("`beta-eval` aus der Spec hat keinen Task" in m for m in msgs)
    assert not any("`alpha-eval`" in m for m in msgs)


def test_lint_skill_flag_reports_ids_missing_from_spec(tmp_path):
    (tmp_path / "spec.md").write_text(SPEC_WITH_TABLE, encoding="utf-8")
    (tmp_path / "evals" / "x").mkdir(parents=True)
    (tmp_path / "evals" / "x" / "evals.json").write_text(
        json.dumps({"evals": [{"id": "alpha-eval"}, {"id": "gamma-eval"}]}), encoding="utf-8"
    )
    plan = tmp_path / "plan.md"
    plan.write_text(
        HEADER + "\n\n**Goal:** x\n**Spec:** `spec.md`\n\n### Task 1: Evals\n\n**Files:**\n- Create: `e.json`\n\n"
        "**Interfaces:**\n- Consumes: (nichts Neues)\n- Produces: `evals`\n\n- [ ] **Step 1: alpha-eval, beta-eval**\n",
        encoding="utf-8",
    )
    msgs = [f.message for f in ptt.lint_plan(plan.read_text(encoding="utf-8"), plan, spec_path=tmp_path / "spec.md", skill="x")]
    assert any("`gamma-eval` aus evals/x/evals.json fehlt in der Spec" in m for m in msgs)


def test_lint_out_json_carries_meta(tmp_path, capsys):
    (tmp_path / "spec.md").write_text("s", encoding="utf-8")
    plan = tmp_path / "plan.md"
    plan.write_text(CLEAN_PLAN, encoding="utf-8")
    out = tmp_path / "lint.json"
    assert ptt.main(["lint", str(plan), "--out", str(out)]) == 0
    meta = json.loads(out.read_text(encoding="utf-8"))["_meta"]
    assert meta["skill"] == "subagent-dev" and meta["schema"] == 1 and "lint" in meta["generated"]
