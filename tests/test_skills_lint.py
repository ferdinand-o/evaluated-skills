"""Repo-Test für Spec 17 (skill-forge): jeder Skill-Ordner unter skills/ durch
lint_skill.py, mit eingefrorenem Register der Altbefunde. G2 — der Test meldet,
sobald jemand pytest fährt; ein Hook fehlt (kein CI in dieser Sammlung)."""

from pathlib import Path

import pytest
from conftest import REPO_ROOT, load_script

ls = load_script("skills/skill-forge/scripts/lint_skill.py")

SKILLS_DIR = REPO_ROOT / "skills"

# Schuldenregister, gemessen am 2026-09-10 beim Bau von skill-forge: Skill → Regel-IDs,
# die damals rot waren. Bewusst nach Regel-ID eingefroren, nicht nach Zahl, und als
# Konstante — die Menge darf nur schrumpfen (ein Skill verlässt sie, wenn ihn jemand
# sauber macht), nie wachsen. Ein neuer Skill kommt nie hinein. Mengen-Semantik: Ein
# zweiter Befund derselben Regel an einem registrierten Skill bleibt verdeckt
# (docs/known-limits.md, skill-forge).
KNOWN_FINDINGS: dict[str, frozenset[str]] = {
    "architecture-map": frozenset({"anti-ceremony-eval", "description", "report-section", "routing"}),
    "cad-parts": frozenset({"description", "evals-exist", "report-section", "routing"}),
    "debug-ledger": frozenset({"anti-ceremony-eval", "asset-headers", "description", "neighbors", "report-section", "routing"}),
    "dev-report": frozenset({"anti-ceremony-eval", "asset-headers", "description", "neighbors", "report-section", "routing"}),
    "enterprise-ui": frozenset({"description", "evals-exist", "report-section", "routing"}),
    "exercise-forge": frozenset({"anti-ceremony-eval", "neighbors", "report-section", "routing"}),
    "explain": frozenset({"neighbors", "report-section"}),
    "feature-spec": frozenset({"anti-ceremony-eval", "description", "report-section"}),
    "handoff": frozenset({"description", "report-section", "routing"}),
    "impl-plan": frozenset({"description", "neighbors"}),
    "learning-coach": frozenset({"anti-ceremony-eval", "description", "neighbors", "report-section", "routing"}),
    "motion-landing": frozenset({"anti-ceremony-eval", "description", "neighbors", "report-section"}),
    "rest-api-architect": frozenset({"description", "neighbors", "report-section", "routing"}),
    "review-context": frozenset({"anti-ceremony-eval", "description", "report-section", "routing"}),
    "sql-schema-architect": frozenset({"anti-ceremony-eval", "description", "report-section", "routing"}),
    "subagent-dev": frozenset({"description", "routing"}),
    "testing-strategy": frozenset({"description", "neighbors", "report-section"}),
    "ui-architect": frozenset({"description", "evals-exist", "report-section", "routing"}),
    "verified-research": frozenset({"description", "gate-language", "neighbors", "report-section", "routing"}),
    "visual-summary": frozenset({"anti-ceremony-eval", "description", "neighbors", "report-section"}),
}
KNOWN_FINDINGS_MAX_PAIRS = 77


def _skills() -> list[Path]:
    """Ein Skill ist ein Ordner mit SKILL.md. Ein Ordner, der nur Skripte trägt, ist
    noch keiner — er wird gelintet, sobald seine SKILL.md existiert."""
    return sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def _report(skill: Path):
    return ls.lint_skill(skill, REPO_ROOT)


@pytest.mark.parametrize("skill", _skills(), ids=lambda p: p.name)
def test_no_finding_outside_the_register(skill: Path):
    report = _report(skill)
    allowed = KNOWN_FINDINGS.get(skill.name, frozenset())
    new = [f"{r.id}: {r.reason}" for r in report.findings if r.id not in allowed]
    assert new == [], "\n".join([f"{skill.name}: neuer Befund außerhalb des Registers"] + new)


@pytest.mark.parametrize("skill", _skills(), ids=lambda p: p.name)
def test_nothing_is_unchecked_for_lack_of_repo_context(skill: Path):
    """Im Repo sind alle Dateien sichtbar. `unchecked` darf hier nur aus dem Skill
    selbst kommen (kein Abgrenzungsabschnitt, keine evals.json), nie aus dem Workspace."""
    report = _report(skill)
    workspace_gaps = [r.id for r in report.rules if r.status == "unchecked" and "nicht im Workspace" in r.reason]
    assert workspace_gaps == [], workspace_gaps


def test_register_names_only_existing_skills_and_rules():
    unknown_skills = sorted(name for name in KNOWN_FINDINGS if not (SKILLS_DIR / name / "SKILL.md").is_file())
    assert unknown_skills == [], f"Register nennt Skills, die es nicht gibt: {unknown_skills}"
    unknown_rules = sorted({rule for rules in KNOWN_FINDINGS.values() for rule in rules} - set(ls.RULE_IDS))
    assert unknown_rules == [], f"Register nennt Regeln, die es nicht gibt: {unknown_rules}"


def test_register_never_grows():
    pairs = sum(len(rules) for rules in KNOWN_FINDINGS.values())
    assert pairs <= KNOWN_FINDINGS_MAX_PAIRS, (
        "Das Register darf nur schrumpfen. Ein neuer Befund wird behoben, nicht eingetragen."
    )


def test_skill_forge_itself_is_clean_with_an_empty_register():
    """Selbstbezug (Spec 17): die Skill besteht ihren eigenen Lint ohne Register."""
    assert "skill-forge" not in KNOWN_FINDINGS
    skill = SKILLS_DIR / "skill-forge"
    assert (skill / "SKILL.md").is_file()
    report = _report(skill)
    assert report.findings == [], [f"{r.id}: {r.reason}" for r in report.findings]
