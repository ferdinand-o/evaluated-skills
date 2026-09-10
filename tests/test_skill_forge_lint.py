"""Unit-Tests für skills/skill-forge/scripts/lint_skill.py (Spec 17).

Je Regel ein Skill-Ordner, der sie reißt, und einer, der sie besteht — und für die
Repo-Regeln der Fall ohne Repo-Kontext, der `unchecked` sein muss und nie `pass`.
"""

import json
import subprocess
from pathlib import Path

import pytest
from conftest import load_script

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
