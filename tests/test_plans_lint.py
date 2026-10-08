"""Repo-Test für Spec 16 (impl-plan): Jeder Plan unter docs/superpowers/plans/,
der nicht im Legacy-Register steht, ist lint-sauber. G2 — der Test meldet, ein
Hook fehlt (kein CI in dieser Sammlung)."""

from pathlib import Path

import pytest
from conftest import REPO_ROOT, load_script

ptt = load_script("skills/subagent-dev/scripts/plan_to_tasks.py")

PLANS_DIR = REPO_ROOT / "docs" / "superpowers" / "plans"
PLAN_TEMPLATE = REPO_ROOT / "skills" / "impl-plan" / "assets" / "plan-template.md"

# Schuldenregister: die 16 Pläne, die vor Spec 15 (explain) ohne Lint entstanden
# sind. Bewusst eine Konstante und keine Datei — die Menge darf nur schrumpfen,
# wenn ein Plan nachträglich lint-sauber gemacht wird. Neue Pläne kommen nie hinzu.
LEGACY_PLANS = frozenset({
    "2026-07-10-cad-parts-skill.md",
    "2026-08-14-eval-harness.md",
    "2026-08-15-dev-report.md",
    "2026-08-15-feature-spec.md",
    "2026-08-15-motion-landing.md",
    "2026-08-15-review-context.md",
    "2026-08-15-verified-research.md",
    "2026-08-15-visual-summary.md",
    "2026-08-16-debug-ledger.md",
    "2026-08-16-rest-api-architect.md",
    "2026-08-16-sql-schema-architect.md",
    "2026-08-16-testing-strategy.md",
    "2026-08-17-architecture-map.md",
    "2026-08-17-exercise-forge.md",
    "2026-08-17-learning-coach.md",
    "2026-08-17-subagent-dev.md",
})
LEGACY_PLANS_MAX_SIZE = 16


def _all_plans() -> list[Path]:
    return sorted(PLANS_DIR.glob("*.md"))


def _linted_plans() -> list[Path]:
    return [p for p in _all_plans() if p.name not in LEGACY_PLANS]


def _findings(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [f.render() for f in ptt.lint_plan(text, plan_path=path)]


def test_plans_dir_has_non_legacy_plans():
    assert _linted_plans(), "kein Plan außerhalb des Legacy-Registers — Test prüft nichts"


@pytest.mark.parametrize("plan", _linted_plans(), ids=lambda p: p.name)
def test_non_legacy_plan_is_lint_clean(plan: Path):
    findings = _findings(plan)
    assert findings == [], "\n".join([f"{plan.name}:"] + findings)


def test_legacy_register_only_names_existing_plans():
    missing = sorted(name for name in LEGACY_PLANS if not (PLANS_DIR / name).is_file())
    assert missing == [], f"Legacy-Register nennt Pläne, die es nicht gibt: {missing}"


def test_legacy_register_never_grows():
    assert len(LEGACY_PLANS) <= LEGACY_PLANS_MAX_SIZE, (
        "Das Legacy-Register darf nur schrumpfen. Ein neuer Plan wird lint-sauber "
        "geschrieben, nicht eingetragen."
    )


def test_plan_template_is_lint_clean():
    findings = _findings(PLAN_TEMPLATE)
    assert findings == [], "\n".join(["plan-template.md:"] + findings)
