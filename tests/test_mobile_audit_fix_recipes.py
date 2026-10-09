"""Jeder Befund verweist auf ein Rezept — und jedes Rezept muss existieren.

Der Findings-Contract der Skill sagt: „Ein Befund ohne Rezept ist eine Beschwerde,
kein Audit." Beim Bau von Stufe 2 waren vier der acht Verweise tot (`#horizontal-overflow`,
`#tap-target-size`, `#safe-area`, `#keyboard-overlay`) — die Skripte lieferten Rezept-Links
in einen Abschnitt, den es noch nicht gab. Dieselbe Fehlerklasse hatte der Testlauf vom
2026-08-20 an `docs/artifact-header.md` gefunden: ein Verweis, dem niemand folgen kann.

Dieser Test macht die Klasse zu einem roten Test statt zu einer Hoffnung — in beide
Richtungen: kein toter Verweis, und kein Rezept, das niemand ausliefert.
"""

import re

import pytest

from conftest import REPO_ROOT

SKILL = REPO_ROOT / "skills" / "mobile-audit"
FIXES = SKILL / "references" / "fixes.md"
ANCHOR_RE = re.compile(r"fixes\.md#([a-z-]+)")
HEADING_RE = re.compile(r"^## ([a-z-]+)\s*$", re.M)


def referenced_anchors():
    anchors = set()
    for script in sorted((SKILL / "scripts").glob("*.py")):
        anchors |= set(ANCHOR_RE.findall(script.read_text(encoding="utf-8")))
    return anchors


def recipe_headings():
    return set(HEADING_RE.findall(FIXES.read_text(encoding="utf-8")))


def test_scripts_reference_recipes_at_all():
    """Schutz vor einem gruenen Test, der nichts prueft: Wenn die Verweise verschwinden,
    ist das kein bestandener Test, sondern ein verlorener Contract."""
    assert len(referenced_anchors()) >= 8, "weniger Rezept-Verweise als Checks — Contract verloren?"


@pytest.mark.parametrize("anchor", sorted(referenced_anchors()))
def test_every_referenced_recipe_exists(anchor):
    assert anchor in recipe_headings(), (
        f"fixes.md#{anchor} wird von einem Skript verwiesen, aber es gibt keine "
        f"Ueberschrift '## {anchor}' — der Befund liefert ein Rezept ins Leere"
    )


def test_every_recipe_is_reachable_from_a_check():
    """Die Gegenrichtung: ein Rezept, das kein Check je erwaehnt, wird nie gelesen."""
    orphans = recipe_headings() - referenced_anchors()
    assert not orphans, f"Rezepte ohne zugehoerigen Befund: {sorted(orphans)}"


def test_recipe_anchors_cover_every_check_the_scripts_can_emit():
    """Der Abgleich, der die Luecke von Stufe 2 gefunden haette: jeder Schluessel in den
    FIX_HINT-Tabellen beider Skripte braucht sein Rezept."""
    from conftest import load_script

    keys = set()
    for rel in ("skills/mobile-audit/scripts/audit_static.py",
                "skills/mobile-audit/scripts/audit_devices.py"):
        keys |= set(load_script(rel).FIX_HINT)
    missing = keys - recipe_headings()
    assert not missing, f"Checks ohne Rezept: {sorted(missing)}"
