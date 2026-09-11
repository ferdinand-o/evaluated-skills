"""Repo-Test für das Spec-Format (docs/assessment-brainstorming.md §6 Punkt 3): Jede
Spec unter specs/ ab Nummer SPEC_LINT_CUTOFF ist für `plan_to_tasks.py lint-spec`
sauber — Kopfzeile mit Review-Vermerk, sieben Abschnitte, Eval-Tabelle mit
Pflichtspalten, Skill-Struktur, Tier, Abgrenzung. Ältere Specs sind Historie ohne
Konsumenten und werden nicht gelintet; ein Nummern-Cutoff ist ehrlicher als ein
Register für Dateien, die niemand mehr ändert. G2 — der Test meldet, ein Hook fehlt."""

from pathlib import Path

import pytest
from conftest import REPO_ROOT, load_script

ptt = load_script("skills/subagent-dev/scripts/plan_to_tasks.py")

SPECS_DIR = REPO_ROOT / "specs"
SPEC_TEMPLATE = REPO_ROOT / "skills" / "skill-forge" / "assets" / "spec-template.md"
CUTOFF = 18


def _numbered_specs() -> list[Path]:
    out = []
    for path in sorted(SPECS_DIR.glob("*.md")):
        number = ptt.spec_number(path)
        if number is not None and number >= CUTOFF:
            out.append(path)
    return out


def test_cutoff_matches_script_default():
    assert ptt.SPEC_LINT_CUTOFF == CUTOFF


@pytest.mark.parametrize("path", _numbered_specs() or [None], ids=lambda p: p.name if p else "keine Spec ab Cutoff")
def test_spec_is_clean(path):
    if path is None:
        pytest.skip(f"noch keine Spec ab {CUTOFF} — der Test greift mit der nächsten")
    findings = ptt.lint_spec(path.read_text(encoding="utf-8"), path)
    assert findings == [], [f.render() for f in findings]


def test_template_lints_up_to_the_review_note():
    """Das Spec-Gerüst von skill-forge trägt alles außer dem Review-Vermerk — der
    entsteht erst nach Schritt 1 und darf nicht vorab im Template stehen."""
    findings = ptt.lint_spec(SPEC_TEMPLATE.read_text(encoding="utf-8"), Path("specs/Spec 99 – muster.md"), repo_root=REPO_ROOT)
    assert [f.rule for f in findings] == ["review-note"], [f.render() for f in findings]


def test_legacy_specs_still_parse_without_crash():
    """Kein Abbruch an einer der 18 Alt-Specs — Befunde sind dort erlaubt, Exceptions nicht."""
    for path in sorted(SPECS_DIR.glob("*.md")):
        ptt.lint_spec(path.read_text(encoding="utf-8"), path)
