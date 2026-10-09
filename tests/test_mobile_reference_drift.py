"""`references/mobile.md` liegt als Kopie in drei Familien-Skills — dieser Test hält sie zusammen.

Warum Kopien statt einer geteilten Datei: Eine Referenz außerhalb des Skill-Bundles ist
installiert tot. Der Testlauf vom 2026-08-20 hat das an `docs/artifact-header.md` gezeigt,
auf das debug-ledger und visual-summary verwiesen und das in keinem installierten Bundle
lag (`find ~/.claude/skills -name artifact-header.md` → kein Treffer). Ein gemeinsames
Plugin wäre neue Infrastruktur für eine Datei; drei Kopien plus dieser Test sind billiger
und machen das Drift-Risiko zu einem roten Test statt zu einer Hoffnung.

Bei einer Änderung: eine Kopie bearbeiten, diesen Test laufen lassen, in die anderen
beiden kopieren.
"""

import hashlib

import pytest

from conftest import REPO_ROOT

FAMILY = ("enterprise-ui", "ui-architect", "motion-landing")
RELPATH = "references/mobile.md"


def path_for(skill):
    return REPO_ROOT / "skills" / skill / RELPATH


@pytest.mark.parametrize("skill", FAMILY)
def test_every_family_skill_ships_the_reference(skill):
    """Ein Verweis auf eine Datei, die nicht mitgeliefert wird, ist installiert tot."""
    assert path_for(skill).is_file(), f"{skill} hat keine eigene Kopie von {RELPATH}"


def test_all_copies_are_byte_identical():
    digests = {skill: hashlib.sha256(path_for(skill).read_bytes()).hexdigest() for skill in FAMILY}
    assert len(set(digests.values())) == 1, (
        "Kopien von mobile.md sind auseinandergelaufen:\n"
        + "\n".join(f"  {skill}: {digest[:12]}" for skill, digest in digests.items())
    )


@pytest.mark.parametrize("skill", FAMILY)
def test_skill_md_points_at_the_reference(skill):
    """Eine mitgelieferte Datei, auf die niemand verweist, wird nie gelesen."""
    text = (REPO_ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    assert "references/mobile.md" in text, f"{skill}/SKILL.md verweist nicht auf {RELPATH}"


def test_reference_does_not_contradict_the_family_tap_target_floor():
    """24×24 px ist Familienrecht (a11y-floor.md). Ein abweichender Boden in mobile.md
    würde regelkonform gebaute Views als Verstoß melden lassen — genau der Fehler, den
    Spec 15 an der 44-px-Annahme des Entwurfs korrigiert hat."""
    text = path_for("enterprise-ui").read_text(encoding="utf-8")
    assert "24×24 px (WCAG 2.2 AA)" in text
    assert "44×44 px is the comfortable size" in text, "44px muss Ziel bleiben, nicht Schwelle"
