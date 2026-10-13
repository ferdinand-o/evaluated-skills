"""Vorlagen-Messung der Zielregel (Spec 22, Abschnitt C), außerhalb des Eval-Vertrags.

Läuft keinen Agenten. Geprüft wird: die beiden Fälle laden; die Fixture trägt Zielregel
und Bereichs-Hook byte-gleich zu den Assets und ein aktives Ziel mit Bereich; die
Kandidaten-Assertion trifft eine Zeile unter Kandidaten und keine unter Aktiv."""

import json
import re

from conftest import REPO_ROOT
from evalkit.schema import load_evals

TEMPLATES = REPO_ROOT / "evals-templates"
FIXTURE = TEMPLATES / "fixtures" / "sr-goals-seeded"
ASSETS = REPO_ROOT / "skills" / "setup-repo" / "assets"


def test_template_evals_load_and_fixture_carries_assets():
    evals = {ev.id: ev for ev in load_evals(TEMPLATES / "setup-repo" / "evals.json")}
    assert set(evals) == {"goal-rule-records-unrelated-bug-as-candidate", "goal-rule-leaves-requested-change-alone"}
    assert all(ev.fixture == "sr-goals-seeded" for ev in evals.values())
    assert json.loads((FIXTURE / "fixture.json").read_text(encoding="utf-8"))["git"] is True
    assert (FIXTURE / ".claude/rules/goals.md").read_bytes() == (ASSETS / "rules/goals.md").read_bytes()
    assert (FIXTURE / ".claude/hooks/goal_scope.py").read_bytes() == (ASSETS / "runtime/goal_scope.py").read_bytes()
    ledger = (FIXTURE / "docs/goals.md").read_text(encoding="utf-8")
    assert re.search(r"^\| G1 \| Tippfehler in greet\.py beheben \|.*\| src/greet\.py \|", ledger, re.MULTILINE)
    assert "Halo" in (FIXTURE / "src/greet.py").read_text(encoding="utf-8")


def test_candidate_pattern_hits_only_the_candidates_table():
    ev = next(e for e in load_evals(TEMPLATES / "setup-repo" / "evals.json")
              if e.id == "goal-rule-records-unrelated-bug-as-candidate")
    pattern = next(a.pattern for a in ev.must if a.path == "docs/goals.md")
    ledger = (FIXTURE / "docs/goals.md").read_text(encoding="utf-8")
    assert not re.search(pattern, ledger, re.MULTILINE)
    row = "| G2 | Schaltjahr in dates.py falsch | Tippfehler G1 | nicht verlangt | 2026-10-12 |\n"
    anchor = "| id | Kandidat | entdeckt bei | Grund | am |\n| --- | --- | --- | --- | --- |\n"
    assert re.search(pattern, ledger.replace(anchor, anchor + row), re.MULTILINE)
    aktiv = "| id | Ziel | Fertig wenn | Bereich | seit |\n| --- | --- | --- | --- | --- |\n"
    assert not re.search(pattern, ledger.replace(aktiv, aktiv + "| G2 | dates | x | src/dates.py | heute |\n"),
                         re.MULTILINE)
