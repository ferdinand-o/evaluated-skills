"""Unit-Tests für skills/skill-forge/scripts/lint_skill.py (Spec 17).

Je Regel ein Skill-Ordner, der sie reißt, und einer, der sie besteht — und für die
Repo-Regeln der Fall ohne Repo-Kontext, der `unchecked` sein muss und nie `pass`.
"""

import json
import subprocess
from pathlib import Path

import pytest
from conftest import git, load_script

ls = load_script("skills/skill-forge/scripts/lint_skill.py")

GOOD_DESC = 'Use when a note needs one house tag before it is filed. Not for writing the note itself (use handoff).'
GOOD_SKILL_MD = f"""---
name: note-tag
description: {GOOD_DESC}
---

# note-tag

## Ablauf

1. Tag wählen.

## Contract

- Genau ein Tag. Das Skript meldet, ein Hook fehlt — nichts blockiert hier.

## Abgrenzung

- **handoff** — Sitzungsende, nicht Notiz.
"""

GOOD_EVALS = {"evals": [
    {"id": "anti-ceremony-one-note-stays-one-line", "class": "contract", "fixture": "nt-one",
     "prompt": "Tagge diese Notiz.", "must": [{"type": "output_matches", "pattern": "^#(idea|task|ref)"}],
     "must_not": [], "notes": "Diskriminator: Hausvokabular."},
]}


def make_repo(tmp_path: Path, skill_md: str = GOOD_SKILL_MD, evals: dict | None = GOOD_EVALS,
              name: str = "note-tag", with_docs: bool = True) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    skill = root / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(skill_md, encoding="utf-8")
    (root / "specs").mkdir()
    (root / "specs" / "Spec 00 – skill-foundation.md").write_text(
        "# Spec 00\n\n### 5 · Routing\n\n| Anlass | zuständig | nicht |\n| --- | --- | --- |\n"
        f"| Notiz taggen | {name} (21) | handoff |\n", encoding="utf-8")
    (root / "README.md").write_text(
        "| Anlass | zuständig | nicht |\n| --- | --- | --- |\n" f"| Notiz taggen | {name} | handoff |\n",
        encoding="utf-8")
    if evals is not None:
        (root / "evals" / name).mkdir(parents=True)
        (root / "evals" / name / "evals.json").write_text(json.dumps(evals, ensure_ascii=False), encoding="utf-8")
        (root / "evals" / "fixtures" / "nt-one").mkdir(parents=True)
        (root / "evals" / "fixtures" / "nt-one" / "fixture.json").write_text('{"git": false}', encoding="utf-8")
    else:
        (root / "evals").mkdir()
    if with_docs:
        (root / "docs" / "superpowers" / "reports").mkdir(parents=True)
        (root / "docs" / "artifact-header.md").write_text("# Kopfzeile\n\n## Begründete Ausnahme: `handoff.md`\n", encoding="utf-8")
        (root / "docs" / "known-limits.md").write_text(f"# Grenzen\n\n## {name}\n\nnichts.\n", encoding="utf-8")
        (root / "docs" / "superpowers" / "reports" / f"{name}-report.md").write_text(
            "# Report\n\n## Was NICHT gemessen wurde\n\n- Evals.\n", encoding="utf-8")
    # der Nachbar handoff nennt note-tag zurück
    other = root / "skills" / "handoff"
    other.mkdir()
    (other / "SKILL.md").write_text(f"---\nname: handoff\ndescription: Use when a session ends. Not for {name}.\n---\n", encoding="utf-8")
    return root, skill


def status_of(report, rule_id: str) -> tuple[str, str]:
    r = next(r for r in report.rules if r.id == rule_id)
    return r.status, r.reason


# --- Grundzustand -----------------------------------------------------------------

def test_good_skill_passes_every_rule(tmp_path):
    root, skill = make_repo(tmp_path)
    report = ls.lint_skill(skill, root)
    assert [r.status for r in report.rules] == ["pass"] * len(ls.RULES), [(r.id, r.reason) for r in report.rules]


def test_rule_ids_are_stable_and_unique():
    assert len(set(ls.RULE_IDS)) == 13


def test_repo_root_is_found_upwards_and_missing_root_means_unchecked(tmp_path):
    root, skill = make_repo(tmp_path)
    assert ls.find_repo_root(skill) == root.resolve()
    lonely = tmp_path / "lonely" / "note-tag"
    lonely.mkdir(parents=True)
    (lonely / "SKILL.md").write_text(GOOD_SKILL_MD, encoding="utf-8")
    report = ls.lint_skill(lonely)
    for rule_id in ("evals-exist", "anti-ceremony-eval", "judge-claims", "fixture-git", "routing", "report-section"):
        status, _ = status_of(report, rule_id)
        assert status == "unchecked", rule_id
    # neighbors: Abschnitt vorhanden, aber keine Nachbarn im Workspace
    assert status_of(report, "neighbors")[0] == "unchecked"
    # asset-headers: ohne Assets gibt es nichts zu prüfen — das ist ein echtes pass
    assert status_of(report, "asset-headers")[0] == "pass"
    assert report.summary()["pass"] == 6 and report.summary()["unchecked"] == 7


# --- Regeln 1–5 (immer prüfbar) ---------------------------------------------------

def test_frontmatter_rejects_foreign_fields_and_missing_description(tmp_path):
    root, skill = make_repo(tmp_path, GOOD_SKILL_MD.replace("name: note-tag\n", "name: note-tag\nmodel: opus\n"))
    status, reason = status_of(ls.lint_skill(skill, root), "frontmatter")
    assert status == "finding" and "model" in reason
    (skill / "SKILL.md").write_text("---\nname: note-tag\n---\n# x\n", encoding="utf-8")
    status, reason = status_of(ls.lint_skill(skill, root), "frontmatter")
    assert status == "finding" and "description" in reason


def test_skill_md_line_limit(tmp_path):
    root, skill = make_repo(tmp_path, GOOD_SKILL_MD + "\n" * 160)
    status, reason = status_of(ls.lint_skill(skill, root), "skill-md-lines")
    assert status == "finding" and "150" in reason


@pytest.mark.parametrize("desc, expected", [
    ("Runs the tagger and writes a tag line. Not for notes.", "Prozessverben"),
    ("Use when a note needs a tag.", "Abgrenzung"),
    ("Tags notes. Not for writing them.", "Trigger"),
])
def test_description_needs_trigger_and_boundary_without_process_verbs(tmp_path, desc, expected):
    root, skill = make_repo(tmp_path, GOOD_SKILL_MD.replace(GOOD_DESC, desc))
    status, reason = status_of(ls.lint_skill(skill, root), "description")
    assert status == "finding" and expected in reason, reason


def test_description_verb_check_ignores_case(tmp_path):
    root, skill = make_repo(tmp_path, GOOD_SKILL_MD.replace(GOOD_DESC, "Use when tagging. Generates a tag. Not for notes."))
    status, reason = status_of(ls.lint_skill(skill, root), "description")
    assert status == "finding" and "generates" in reason


def test_gate_language_is_paragraph_aware(tmp_path):
    negated = GOOD_SKILL_MD  # „nichts blockiert hier" im selben Absatz wie „meldet"
    root, skill = make_repo(tmp_path, negated)
    assert status_of(ls.lint_skill(skill, root), "gate-language")[0] == "pass"
    table = GOOD_SKILL_MD + "\n| Regel | Wirkung |\n| --- | --- |\n| Lint | blockiert den Commit |\n| Hinweis | nicht blockierend |\n"
    (skill / "SKILL.md").write_text(table, encoding="utf-8")
    status, reason = status_of(ls.lint_skill(skill, root), "gate-language")
    assert status == "finding" and "blockiert" in reason
    (skill / "assets" / "hooks").mkdir(parents=True)
    assert status_of(ls.lint_skill(skill, root), "gate-language")[0] == "pass"


def test_gate_word_in_prose_paragraph_without_negation_is_a_finding(tmp_path):
    root, skill = make_repo(tmp_path, GOOD_SKILL_MD + "\nDas Skript erzwingt das mechanisch.\n")
    assert status_of(ls.lint_skill(skill, root), "gate-language")[0] == "finding"


def test_script_tier_first_mention_sibling_imports_and_foreign_imports(tmp_path):
    root, skill = make_repo(tmp_path)
    scripts = skill / "scripts"
    scripts.mkdir()
    (scripts / "helper.py").write_text('"""Helfer. Tier 1: nur Stdlib. Ein Nebensatz nennt Tier 2 nur beiläufig."""\nimport json\n', encoding="utf-8")
    (scripts / "main.py").write_text('"""Haupt. Tier 1.\n"""\nimport re\nimport helper\n', encoding="utf-8")
    assert status_of(ls.lint_skill(skill, root), "script-tier")[0] == "pass"
    (scripts / "bad.py").write_text('"""Tier 1"""\nimport requests\n', encoding="utf-8")
    status, reason = status_of(ls.lint_skill(skill, root), "script-tier")
    assert status == "finding" and "requests" in reason
    (scripts / "bad.py").write_text('"""Tier 2: braucht requests."""\nimport requests\n', encoding="utf-8")
    assert status_of(ls.lint_skill(skill, root), "script-tier")[0] == "pass"
    (scripts / "none.py").write_text('import os\n', encoding="utf-8")
    status, reason = status_of(ls.lint_skill(skill, root), "script-tier")
    assert status == "finding" and "none.py" in reason


# --- Regeln 6–9 (Evals) -----------------------------------------------------------

def test_evals_exist_reports_missing_and_malformed(tmp_path):
    root, skill = make_repo(tmp_path, evals=None)
    assert status_of(ls.lint_skill(skill, root), "evals-exist")[0] == "finding"
    (root / "evals" / "note-tag").mkdir()
    (root / "evals" / "note-tag" / "evals.json").write_text('{"evals": [{"id": "x", "class": "judge", "prompt": "p"}]}', encoding="utf-8")
    status, reason = status_of(ls.lint_skill(skill, root), "evals-exist")
    assert status == "finding" and "class" in reason and "must" in reason


def test_anti_ceremony_eval_needs_the_id_prefix(tmp_path):
    evals = {"evals": [dict(GOOD_EVALS["evals"][0], id="mini-case-is-anti-ceremony")]}
    root, skill = make_repo(tmp_path, evals=evals)
    status, reason = status_of(ls.lint_skill(skill, root), "anti-ceremony-eval")
    assert status == "finding" and "anti-ceremony-" in reason


def test_judge_claims_with_conjunction_are_a_hint_never_a_finding(tmp_path):
    evals = {"evals": [dict(GOOD_EVALS["evals"][0], **{"class": "behavior", "must": [
        {"type": "judge", "claim": "Kurz und ohne Überschrift und ohne Beispiel."}]})]}
    root, skill = make_repo(tmp_path, evals=evals)
    report = ls.lint_skill(skill, root)
    assert status_of(report, "judge-claims")[0] == "hint"
    assert report.findings == [] and report.summary()["hint"] == 1


def test_fixture_git_checks_existence_and_git_precondition(tmp_path):
    evals = {"evals": [dict(GOOD_EVALS["evals"][0], must=[{"type": "git_head_unchanged"}])]}
    root, skill = make_repo(tmp_path, evals=evals)
    status, reason = status_of(ls.lint_skill(skill, root), "fixture-git")
    assert status == "finding" and '"git": true' in reason
    (root / "evals" / "fixtures" / "nt-one" / "fixture.json").write_text('{"git": true}', encoding="utf-8")
    assert status_of(ls.lint_skill(skill, root), "fixture-git")[0] == "pass"
    evals["evals"][0]["fixture"] = "nt-missing"
    (root / "evals" / "note-tag" / "evals.json").write_text(json.dumps(evals), encoding="utf-8")
    status, reason = status_of(ls.lint_skill(skill, root), "fixture-git")
    assert status == "finding" and "nt-missing" in reason


# --- Regeln 10–13 (Repo-Kontext) --------------------------------------------------

def test_asset_headers_exempt_skill_md_and_documented_exceptions(tmp_path):
    root, skill = make_repo(tmp_path)
    assets = skill / "assets" / "skill-template"
    assets.mkdir(parents=True)
    (assets / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    (assets / "report.md").write_text("<!-- skill: note-tag | schema: 1 | generated: von Hand -->\n# R\n", encoding="utf-8")
    assert status_of(ls.lint_skill(skill, root), "asset-headers")[0] == "pass"
    (skill / "assets" / "ledger-template.md").write_text("## Symptom\n", encoding="utf-8")
    status, reason = status_of(ls.lint_skill(skill, root), "asset-headers")
    assert status == "finding" and "ledger-template.md" in reason
    header_doc = root / "docs" / "artifact-header.md"
    header_doc.write_text(header_doc.read_text(encoding="utf-8") + "\n## Begründete Ausnahme: `skills/note-tag/assets/ledger-template.md`\n", encoding="utf-8")
    assert status_of(ls.lint_skill(skill, root), "asset-headers")[0] == "pass"
    (root / "docs" / "artifact-header.md").unlink()
    assert status_of(ls.lint_skill(skill, root), "asset-headers")[0] == "unchecked"


def test_routing_counts_only_the_responsible_column(tmp_path):
    root, skill = make_repo(tmp_path)
    (root / "README.md").write_text(
        "| Anlass | zuständig | nicht |\n| --- | --- | --- |\n| Notiz taggen | handoff | note-tag |\n", encoding="utf-8")
    status, reason = status_of(ls.lint_skill(skill, root), "routing")
    assert status == "finding" and "README.md" in reason and "Spec 00" not in reason


def test_neighbors_unchecked_without_section_and_finding_when_not_reciprocated(tmp_path):
    root, skill = make_repo(tmp_path, GOOD_SKILL_MD.replace("## Abgrenzung", "## Nachbarn"))
    assert status_of(ls.lint_skill(skill, root), "neighbors")[0] == "unchecked"
    root, skill = make_repo(tmp_path / "b")
    (root / "skills" / "handoff" / "SKILL.md").write_text("---\nname: handoff\ndescription: Use when a session ends. Not for tags.\n---\n", encoding="utf-8")
    status, reason = status_of(ls.lint_skill(skill, root), "neighbors")
    assert status == "finding" and "handoff" in reason


def test_report_section_is_case_insensitive_and_needs_known_limits(tmp_path):
    root, skill = make_repo(tmp_path)
    assert status_of(ls.lint_skill(skill, root), "report-section")[0] == "pass"
    (root / "docs" / "known-limits.md").write_text("# Grenzen\n\n## note-tagger\n", encoding="utf-8")
    status, reason = status_of(ls.lint_skill(skill, root), "report-section")
    assert status == "finding" and "known-limits" in reason
    (root / "docs" / "superpowers" / "reports" / "note-tag-report.md").write_text("# R\n\n## Was ich nicht verifizieren konnte\n", encoding="utf-8")
    status, reason = status_of(ls.lint_skill(skill, root), "report-section")
    assert "Was nicht gemessen wurde" in reason


# --- Artefakt und CLI -------------------------------------------------------------

def test_lint_json_rule_lines_follow_the_contract(tmp_path):
    root, skill = make_repo(tmp_path, GOOD_SKILL_MD + "\nDas Skript erzwingt das mechanisch.\n")
    out = tmp_path / "lint.json"
    rc = ls.main([str(skill), "--repo-root", str(root), "--out", str(out)])
    assert rc == 1
    text = out.read_text(encoding="utf-8")
    assert '{"id": "gate-language", "status": "finding", "reason": ' in text
    assert '{"id": "frontmatter", "status": "pass", "reason": ' in text
    data = json.loads(text)
    assert data["_meta"]["skill"] == "skill-forge" and "lint_skill.py" in data["_meta"]["generated"]
    assert data["findings_mode"] == "all" and data["new_findings"] == ["gate-language"]
    assert data["evals_due"] == "unchecked"
    assert [r["id"] for r in data["rules"]] == list(ls.RULE_IDS)
    assert data["summary"]["finding"] == 1


def test_main_exit_codes(tmp_path, capsys):
    root, skill = make_repo(tmp_path)
    assert ls.main([str(skill), "--repo-root", str(root)]) == 0
    assert ls.main([str(tmp_path / "nope")]) == 2
    assert "nicht lesbar" in capsys.readouterr().err


def test_unchecked_is_reported_loudly_and_never_counted_as_pass(tmp_path, capsys):
    lonely = tmp_path / "lonely" / "note-tag"
    lonely.mkdir(parents=True)
    (lonely / "SKILL.md").write_text(GOOD_SKILL_MD, encoding="utf-8")
    rc = ls.main([str(lonely)])
    out = capsys.readouterr().out
    assert rc == 0 and "UNGEPRÜFT" in out and "routing" in out


# --- Diff-Modus (Task 2) ----------------------------------------------------------

VERB_DESC = "Use when a note needs a tag. Generates the tag. Not for writing the note (use handoff)."


_git = git


def make_git_repo(tmp_path: Path, skill_md: str, evals: dict | None = GOOD_EVALS) -> tuple[Path, Path]:
    root, skill = make_repo(tmp_path, skill_md, evals=evals)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "basis")
    return root, skill


def _run(root: Path, skill: Path, out: Path, *extra: str) -> tuple[int, dict]:
    rc = ls.main([str(skill), "--repo-root", str(root), "--out", str(out), *extra])
    return rc, json.loads(out.read_text(encoding="utf-8"))


def test_diff_mode_counts_only_new_findings(tmp_path):
    """Ein Altbefund (Prozessverb in der Description) steht an der Basis und danach —
    ein geänderter Satz im Body ist kein neuer Befund und macht keine Evals fällig."""
    root, skill = make_git_repo(tmp_path, GOOD_SKILL_MD.replace(GOOD_DESC, VERB_DESC))
    md = skill / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8").replace("1. Tag wählen.", "1. Tag wählen, ohne Rückfrage."), encoding="utf-8")
    rc, data = _run(root, skill, tmp_path / "lint.json", "--base", "HEAD")
    assert rc == 0
    assert data["findings_mode"] == "new-vs-base"
    assert data["findings_at_base"] == ["description"] and data["new_findings"] == []
    assert data["evals_due"] is False
    assert '"evals_due": false' in (tmp_path / "lint.json").read_text(encoding="utf-8")


def test_diff_mode_reports_a_finding_the_change_introduced(tmp_path):
    root, skill = make_git_repo(tmp_path, GOOD_SKILL_MD)
    md = skill / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8") + "\nDas Skript erzwingt das mechanisch.\n", encoding="utf-8")
    rc, data = _run(root, skill, tmp_path / "lint.json", "--base", "HEAD")
    assert rc == 1 and data["new_findings"] == ["gate-language"] and data["findings_at_base"] == []


def test_frontmatter_change_makes_evals_due(tmp_path):
    root, skill = make_git_repo(tmp_path, GOOD_SKILL_MD)
    md = skill / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8").replace("name: note-tag", "name: note-tag\nversion: 2"), encoding="utf-8")
    rc, data = _run(root, skill, tmp_path / "lint.json", "--base", "HEAD")
    assert data["evals_due"] is True and "Frontmatter" in data["evals_due_reason"]


def test_contract_section_change_makes_evals_due_with_any_contract_heading(tmp_path):
    root, skill = make_git_repo(tmp_path, GOOD_SKILL_MD.replace("## Contract", "## Der Contract"))
    md = skill / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8").replace("- Genau ein Tag.", "- Genau ein Tag, nie zwei."), encoding="utf-8")
    rc, data = _run(root, skill, tmp_path / "lint.json", "--base", "HEAD")
    assert data["evals_due"] is True and "Contract" in data["evals_due_reason"]


def test_pattern_hit_on_changed_line_makes_evals_due(tmp_path):
    evals = {"evals": [dict(GOOD_EVALS["evals"][0], must_not=[{"type": "output_matches", "pattern": "Untagged:\\s*$"}])]}
    root, skill = make_git_repo(tmp_path, GOOD_SKILL_MD, evals=evals)
    md = skill / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8").replace("1. Tag wählen.", "1. Tag wählen, sonst Untagged:"), encoding="utf-8")
    rc, data = _run(root, skill, tmp_path / "lint.json", "--base", "HEAD")
    assert data["evals_due"] is True and "Pattern" in data["evals_due_reason"]


def test_without_base_everything_counts_and_evals_due_is_unchecked(tmp_path):
    root, skill = make_git_repo(tmp_path, GOOD_SKILL_MD.replace(GOOD_DESC, VERB_DESC))
    rc, data = _run(root, skill, tmp_path / "lint.json")
    assert rc == 1 and data["findings_mode"] == "all" and data["new_findings"] == ["description"]
    assert data["evals_due"] == "unchecked"


def test_base_without_git_or_unknown_revision_is_exit_2(tmp_path, capsys):
    root, skill = make_repo(tmp_path)
    assert ls.main([str(skill), "--repo-root", str(root), "--base", "HEAD"]) == 2
    assert "Diff-Modus nicht möglich" in capsys.readouterr().err
    root, skill = make_git_repo(tmp_path / "g", GOOD_SKILL_MD)
    assert ls.main([str(skill), "--repo-root", str(root), "--base", "nope-rev"]) == 2


def test_base_lint_sees_neighbors_of_the_real_repo(tmp_path):
    """Der Basisstand liegt in einem Temp-Ordner — die Nachbarn kommen trotzdem aus
    dem echten Repo, sonst wäre jeder Nachbarn-Befund an der Basis unsichtbar und
    danach „neu"."""
    root, skill = make_git_repo(tmp_path, GOOD_SKILL_MD)
    (root / "skills" / "handoff" / "SKILL.md").write_text("---\nname: handoff\ndescription: Use when a session ends. Not for tags.\n---\n", encoding="utf-8")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "nachbar schweigt")
    base = ls.lint_at_base(skill, root, "HEAD")
    assert status_of(base, "neighbors")[0] == "finding"


# --- Fix-Runde nach dem Review ----------------------------------------------------

def test_gate_language_keeps_wrapped_list_items_together_and_ignores_case(tmp_path):
    wrapped = GOOD_SKILL_MD + "\n- Nichts in dieser Skill\n  blockiert den Commit; das Skript meldet nur.\n"
    root, skill = make_repo(tmp_path, wrapped)
    assert status_of(ls.lint_skill(skill, root), "gate-language")[0] == "pass"
    (skill / "SKILL.md").write_text(GOOD_SKILL_MD + "\nBlockiert den Commit, wenn die ID fehlt.\n", encoding="utf-8")
    assert status_of(ls.lint_skill(skill, root), "gate-language")[0] == "finding"
    (skill / "SKILL.md").write_text(GOOD_SKILL_MD + "\nDer Hook blockiert den Push ohne Rückfrage.\n", encoding="utf-8")
    assert status_of(ls.lint_skill(skill, root), "gate-language")[0] == "finding", "„ohne\" ist keine Negation"


def test_neighbors_absent_named_skill_is_unchecked_and_reciprocity_is_word_bounded(tmp_path):
    root, skill = make_repo(tmp_path, GOOD_SKILL_MD.replace("- **handoff** — Sitzungsende, nicht Notiz.",
                                                              "- **handoff** — Sitzungsende.\n- **skill-creator** — außerhalb dieser Sammlung."))
    status, reason = status_of(ls.lint_skill(skill, root), "neighbors")
    assert status == "unchecked" and "skill-creator" in reason and "erwidert von: handoff" in reason
    # Rückverweis nur als ganzes Wort: „unexplained" erwidert „explain" nicht
    root, skill = make_repo(tmp_path / "b", GOOD_SKILL_MD.replace("note-tag", "explain").replace("- **handoff** — Sitzungsende, nicht Notiz.", "- **handoff** — Sitzungsende."), name="explain")
    (root / "skills" / "handoff" / "SKILL.md").write_text("---\nname: handoff\ndescription: Use when a session ends. Not for unexplained notes.\n---\n", encoding="utf-8")
    status, reason = status_of(ls.lint_skill(skill, root), "neighbors")
    assert status == "finding" and "handoff" in reason
    # Prosa oder Backticks ohne **name** nennen niemanden
    root, skill = make_repo(tmp_path / "c", GOOD_SKILL_MD.replace("- **handoff** — Sitzungsende, nicht Notiz.", "Die Übergabe ist Sache von handoff, geprüft mit `evalkit`."))
    assert status_of(ls.lint_skill(skill, root), "neighbors")[0] == "pass"


def test_broken_inputs_yield_findings_never_tracebacks(tmp_path):
    """Pitfalls: ein Lint, der abstürzt, hinterlässt kein Artefakt — und die Übergabe
    „Lint nicht verfügbar\" greift nicht, weil das Skript existiert."""
    root, skill = make_repo(tmp_path)
    (root / "evals" / "fixtures" / "nt-one" / "fixture.json").write_text("[]", encoding="utf-8")
    (skill / "scripts").mkdir()
    (skill / "scripts" / "dir.py").mkdir()
    (skill / "scripts" / "dead.py").symlink_to(skill / "scripts" / "nope.py")
    (skill / "scripts" / "ok.py").write_text('"""Tier 1"""\nimport os\n', encoding="utf-8")
    (skill / "assets").mkdir()
    (skill / "assets" / "dir.md").mkdir()
    (root / "docs" / "artifact-header.md").write_bytes("# Kopfzeile\n\n## Begründete Ausnahme: `x`\n\xe4\xf6\n".encode("latin-1"))
    (skill / "assets" / "t.md").write_text("<!-- skill: note-tag | schema: 1 | generated: x -->\n", encoding="utf-8")
    out = tmp_path / "lint.json"
    rc = ls.main([str(skill), "--repo-root", str(root), "--out", str(out)])
    assert rc in (0, 1) and out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [r["id"] for r in data["rules"]] == list(ls.RULE_IDS)
    assert not any("abgebrochen" in r["reason"] for r in data["rules"]), [r for r in data["rules"] if "abgebrochen" in r["reason"]]


def test_rule_exception_becomes_a_finding_not_a_crash(tmp_path, monkeypatch):
    root, skill = make_repo(tmp_path)
    def boom(skill_dir, repo_root):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(ls, "RULES", [(rid, boom if rid == "routing" else fn) for rid, fn in ls.RULES])
    status, reason = status_of(ls.lint_skill(skill, root), "routing")
    assert status == "finding" and "abgebrochen" in reason and "kaputt" in reason


def test_description_accepts_yaml_block_scalars_and_use_whenever(tmp_path):
    block = GOOD_SKILL_MD.replace(f"description: {GOOD_DESC}", "description: >\n  Use whenever a note needs a tag.\n  Not for writing the note.")
    root, skill = make_repo(tmp_path, block)
    assert status_of(ls.lint_skill(skill, root), "description")[0] == "pass"
    assert status_of(ls.lint_skill(skill, root), "frontmatter")[0] == "pass"


def test_evals_exist_rejects_empty_lists_like_evalkit(tmp_path):
    root, skill = make_repo(tmp_path, evals={"evals": []})
    assert status_of(ls.lint_skill(skill, root), "evals-exist")[0] == "finding"
    root, skill = make_repo(tmp_path / "b", evals={"evals": [dict(GOOD_EVALS["evals"][0], must=[])]})
    status, reason = status_of(ls.lint_skill(skill, root), "evals-exist")
    assert status == "finding" and "must" in reason


def test_asset_header_exception_needs_the_path_not_just_the_name(tmp_path):
    root, skill = make_repo(tmp_path)
    (skill / "assets").mkdir()
    (skill / "assets" / "handoff.md").write_text("# kein Header\n", encoding="utf-8")
    status, reason = status_of(ls.lint_skill(skill, root), "asset-headers")
    assert status == "finding" and "handoff.md" in reason  # der Name steht in artifact-header.md, der Pfad nicht


def test_diff_mode_works_when_repo_root_is_below_the_git_toplevel(tmp_path):
    outer = tmp_path / "outer"
    outer.mkdir()
    _git(outer, "init", "-q"); _git(outer, "config", "user.email", "t@x"); _git(outer, "config", "user.name", "t")
    root, skill = make_repo(outer / "sub")
    # make_repo legt "sub/repo" an
    root = outer / "sub" / "repo"; skill = root / "skills" / "note-tag"
    _git(outer, "add", "-A"); _git(outer, "commit", "-q", "-m", "basis")
    md = skill / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8").replace("name: note-tag", "name: note-tag\nversion: 2"), encoding="utf-8")
    rc, data = _run(root, skill, tmp_path / "lint.json", "--base", "HEAD")
    assert data["findings_mode"] == "new-vs-base" and data["evals_due"] is True and "Frontmatter" in data["evals_due_reason"]


def test_diff_mode_content_lines_starting_with_dashes_do_not_shift_line_numbers(tmp_path):
    root, skill = make_git_repo(tmp_path, GOOD_SKILL_MD.replace("## Contract\n", "## Contract\n\n-- Vorbemerkung --\n"))
    md = skill / "SKILL.md"
    text = md.read_text(encoding="utf-8").replace("-- Vorbemerkung --\n", "").replace("- Genau ein Tag.", "- Genau ein Tag, nie zwei.")
    md.write_text(text, encoding="utf-8")
    rc, data = _run(root, skill, tmp_path / "lint.json", "--base", "HEAD")
    assert data["evals_due"] is True and "Contract" in data["evals_due_reason"]


def test_untracked_and_renamed_files_count_in_evals_due(tmp_path):
    evals = {"evals": [dict(GOOD_EVALS["evals"][0], must_not=[{"type": "output_matches", "pattern": "Untagged:"}])]}
    root, skill = make_git_repo(tmp_path, GOOD_SKILL_MD, evals=evals)
    (skill / "references").mkdir()
    (skill / "references" / "x.md").write_text("Untagged: wenn nichts passt\n", encoding="utf-8")
    rc, data = _run(root, skill, tmp_path / "lint.json", "--base", "HEAD")
    assert data["evals_due"] is True and "Pattern" in data["evals_due_reason"]
    (skill / "references" / "x.md").unlink(); (skill / "references").rmdir()
    _git(root, "mv", "skills/note-tag/SKILL.md", "skills/note-tag/SKILL2.md")
    rc, data = _run(root, skill, tmp_path / "lint.json", "--base", "HEAD")
    assert data["evals_due"] is True and "SKILL.md gelöscht" in data["evals_due_reason"]


def test_invalid_regex_pattern_is_reported_not_swallowed(tmp_path):
    evals = {"evals": [dict(GOOD_EVALS["evals"][0], must=[{"type": "output_matches", "pattern": "^#(idea"}])]}
    root, skill = make_git_repo(tmp_path, GOOD_SKILL_MD, evals=evals)
    md = skill / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8").replace("1. Tag wählen.", "1. Tag wählen, sonst nichts."), encoding="utf-8")
    rc, data = _run(root, skill, tmp_path / "lint.json", "--base", "HEAD")
    assert data["evals_due"] is False and "ungültigem Regex" in data["evals_due_reason"]
