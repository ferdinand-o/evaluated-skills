"""`plan_to_tasks.py lint-spec` — Formprüfung einer Skill-Spec vor dem Plan
(docs/assessment-brainstorming.md §6 Punkt 3). Jede Regel hat einen roten und die
saubere Spec einen grünen Fall; dazu die drei echten Specs 15–17 als Kalibrierung."""

import json
from pathlib import Path

from conftest import REPO_ROOT, load_script

ptt = load_script("skills/subagent-dev/scripts/plan_to_tasks.py")

CLEAN_SPEC = """# Spec 18: probe — eine Skill zum Prüfen

Skill-Spezifikation · Zyklus 18 · Entscheidung: Tier 1 · Abgeglichen mit Spec 00 · Überarbeitet nach unabhängigem Review

## Problem

Etwas fehlt.

## Constraints

Tier 1. Der Lint meldet, er blockiert nicht.

## Approach

### Skill-Struktur

```
skills/probe/
├── SKILL.md                 Ablauf, Contract
└── scripts/check.py         Tier 1
```

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| prüfen | probe | impl-plan (der Plan), superpowers:writing-skills (Disziplin) |

### Evals

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-one-line-stays-small` | contract | empty-dir | file_exists | nur diese Skill schreibt die Datei |
| 2 | `probe-writes-artifact` | contract | empty-dir | file_matches | Kopfzeile trägt den Skill-Namen |

## Alternatives considered

Keine Skill, nur ein Dokument — verworfen.

## Out of scope

Alles andere.

## Open questions

*Annahme:* Tier 1 reicht.

## Next steps

Plan mit impl-plan.
"""


def _rules(text: str, **kw) -> set[str]:
    return {f.rule for f in ptt.lint_spec(text, repo_root=REPO_ROOT, **kw)}


def test_clean_spec_has_no_findings():
    assert ptt.lint_spec(CLEAN_SPEC, repo_root=REPO_ROOT) == []


def test_missing_header_is_reported_and_review_note_not_duplicated():
    text = CLEAN_SPEC.replace("Skill-Spezifikation · Zyklus 18", "Zyklus 18")
    assert _rules(text) == {"header"}


def test_missing_review_note_is_reported():
    text = CLEAN_SPEC.replace(" · Überarbeitet nach unabhängigem Review", "")
    assert _rules(text) == {"review-note"}


def test_missing_and_misordered_sections():
    assert _rules(CLEAN_SPEC.replace("## Out of scope\n\nAlles andere.\n\n", "")) == {"sections"}
    swapped = CLEAN_SPEC.replace("## Problem\n\nEtwas fehlt.\n\n## Constraints", "## Constraints").replace(
        "## Approach", "## Problem\n\nEtwas fehlt.\n\n## Approach")
    assert "sections" in _rules(swapped)


def test_eval_table_rules():
    assert _rules(CLEAN_SPEC.replace("### Evals", "### Prüfszenarien")) == {"eval-table"}
    no_cols = CLEAN_SPEC.replace("| # | id | Klasse | Fixture | Assertions | Diskriminator |", "| # | id | Klasse | Prüft | Mechanismus | Notiz |")
    msgs = [f.message for f in ptt.lint_spec(no_cols, repo_root=REPO_ROOT)]
    assert any("fixture" in m and "diskriminator" in m for m in msgs)
    no_anti = CLEAN_SPEC.replace("`anti-ceremony-one-line-stays-small`", "`one-line-stays-small`")
    assert any("anti-ceremony-" in f.message for f in ptt.lint_spec(no_anti, repo_root=REPO_ROOT))
    bare_id = CLEAN_SPEC.replace("`probe-writes-artifact`", "probe-writes-artifact")
    assert any("Backtick" in f.message for f in ptt.lint_spec(bare_id, repo_root=REPO_ROOT))


def test_structure_block_and_tier():
    assert _rules(CLEAN_SPEC.replace("├── SKILL.md                 Ablauf, Contract\n", "")) == {"skill-structure"}
    assert _rules(CLEAN_SPEC.replace("scripts/check.py         Tier 1", "scripts/check.py         prüft")) == {"tier"}


def test_abgrenzung_needs_two_known_neighbours():
    assert _rules(CLEAN_SPEC.replace("### Abgrenzung", "### Nachbarn")) == {"abgrenzung"}
    one = CLEAN_SPEC.replace(", superpowers:writing-skills (Disziplin)", "")
    assert _rules(one) == {"abgrenzung"}
    unknown = CLEAN_SPEC.replace("impl-plan (der Plan)", "no-such-skill (der Plan)")
    assert _rules(unknown) == {"abgrenzung"}
    # ohne Repo-Root zählt jeder Name — und der Befund sagt, dass nicht gegen skills/ geprüft wurde
    findings = ptt.lint_spec(unknown, repo_root=None)
    assert findings == []


def test_gate_words_need_hook_or_negation():
    hard = CLEAN_SPEC.replace("Der Lint meldet, er blockiert nicht.", "Der Lint blockiert den Commit.")
    assert _rules(hard) == {"gate-language"}
    with_hook = hard.replace("## Out of scope", "Hook unter `assets/hooks/`.\n\n## Out of scope")
    assert _rules(with_hook) == set()
    rejected = CLEAN_SPEC.replace("Keine Skill, nur ein Dokument — verworfen.", "Ein Hook, der jeden Commit blockiert — verworfen.")
    assert _rules(rejected) == set()


def test_placeholders_but_not_mentions():
    assert _rules(CLEAN_SPEC.replace("Alles andere.", "TBD")) == {"placeholders"}
    mention = CLEAN_SPEC.replace("Alles andere.", "Der Lint meldet `TBD` und „TODO\" als Platzhalter.")
    assert _rules(mention) == set()
    # ein einzelner Backtick weiter oben darf die Paarung nicht verschieben
    stray = mention.replace("Etwas fehlt.", "Etwas ` fehlt.")
    assert _rules(stray) == set()


def test_real_specs_are_calibration_not_noise():
    """Die drei bisher reviewten Specs: bekannte, benannte Restbefunde — nichts Erfundenes."""
    def rules(n):
        path = next((REPO_ROOT / "specs").glob(f"Spec {n} *.md"))
        return {f.rule for f in ptt.lint_spec(path.read_text(encoding="utf-8"), path)}
    assert rules(15) == {"eval-table"}          # Tabelle ohne Fixture/Diskriminator-Spalte
    assert rules(16) == {"tier"}                # nennt subagent-devs Skript ohne Tier
    assert rules(17) == {"header", "abgrenzung"}  # beginnt mit ## Problem, Abgrenzung in Prosa


def test_cli_cutoff_and_artifact(tmp_path):
    old = tmp_path / "Spec 17 – x.md"
    old.write_text(CLEAN_SPEC.replace(" · Überarbeitet nach unabhängigem Review", ""), encoding="utf-8")
    new = tmp_path / "Spec 18 – y.md"
    new.write_text(old.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "lint.json"
    assert ptt.main(["lint-spec", str(old), "--repo-root", str(REPO_ROOT)]) == 0
    assert ptt.main(["lint-spec", str(new), "--repo-root", str(REPO_ROOT), "--out", str(out)]) == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "findings" and data["number"] == 18 and data["cutoff"] == 18
    assert data["_meta"]["skill"] == "subagent-dev" and "lint-spec" in data["_meta"]["generated"]
    assert [f["rule"] for f in data["findings"]] == ["review-note"]
    assert ptt.main(["lint-spec", str(new), "--repo-root", str(REPO_ROOT), "--cutoff", "19"]) == 0
    assert ptt.main(["lint-spec", str(tmp_path / "fehlt.md")]) == 2


def test_spec_number():
    assert ptt.spec_number(Path("specs/Spec 17 – skill-forge.md")) == 17
    assert ptt.spec_number(Path("specs/foo.md")) is None
    assert ptt.spec_number(None) is None
