"""`plan_to_tasks.py lint-spec` — Formprüfung einer Skill-Spec vor dem Plan
(docs/assessment-brainstorming.md §6 Punkt 3, Branch claude/assessment-brainstorming).
Jede Regel hat einen roten und die saubere Spec einen grünen Fall; dazu die drei
echten Specs 15–17 als Kalibrierung. Zwei Fix-Runden nach je zwei Reviews
(Fable-Subagent, /code-review) haben hier ihre Fälle: Gate-Wort mit erwähntem
`assets/hooks/`, Kommando-Zaun vor dem Baum, fremdes Skript, verschachteltes
`scripts/`, eingerückter Zaun, Nachbar ohne Bindestrich, Template-Reste; dann
Tabellen und Listen als eigene Einheiten, Pfad-Token statt Substring, Dateiname
gegen Baumwurzel, Substantiv „Blocker", Singular „Assertion", Shell-Skripte,
Wurzel mit Anhang, offener Zaun."""

import json
from pathlib import Path

from conftest import REPO_ROOT, load_script

ptt = load_script("skills/subagent-dev/scripts/plan_to_tasks.py")

CLEAN_SPEC = """# Spec 18: probe — eine Skill zum Prüfen

Skill-Spezifikation · Zyklus 18 · Entscheidung: Tier 1 · Abgeglichen mit Spec 00 · Überarbeitet nach unabhängigem Review

## Problem

Etwas fehlt.

## Constraints

Tier 1. Der Lint meldet, er blockiert nicht. G3 nur mit `assets/hooks/`.

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


def _findings(text: str, **kw):
    return ptt.lint_spec(text, repo_root=REPO_ROOT, **kw)


def test_clean_spec_has_no_findings():
    assert _findings(CLEAN_SPEC) == []


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
    msgs = [f.message for f in _findings(no_cols)]
    assert any("fixture" in m and "diskriminator" in m for m in msgs)
    # Singular „Assertion" ist dieselbe Spalte
    assert _findings(CLEAN_SPEC.replace("| Assertions |", "| Assertion |")) == []
    no_anti = CLEAN_SPEC.replace("`anti-ceremony-one-line-stays-small`", "`one-line-stays-small`")
    assert any("anti-ceremony-" in f.message for f in _findings(no_anti))
    bare_id = CLEAN_SPEC.replace("`probe-writes-artifact`", "probe-writes-artifact")
    assert any("Backtick" in f.message for f in _findings(bare_id))


def test_structure_block_is_the_tree_not_a_command_fence():
    assert _rules(CLEAN_SPEC.replace("├── SKILL.md                 Ablauf, Contract\n", "")) == {"skill-structure"}
    command = CLEAN_SPEC.replace("### Skill-Struktur", "```bash\ncat skills/probe/SKILL.md\npython skills/probe/scripts/check.py --help\n```\n\n### Skill-Struktur")
    assert _findings(command) == []
    assert _rules(command.replace("scripts/check.py         Tier 1", "scripts/check.py         prüft")) == {"tier"}
    # Wurzel mit Anhang bleibt Wurzel
    assert _findings(CLEAN_SPEC.replace("skills/probe/\n", "skills/probe/            die neue Skill\n")) == []


def test_tier_rule_flat_nested_foreign_and_shell():
    assert _rules(CLEAN_SPEC.replace("scripts/check.py         Tier 1", "scripts/check.py         prüft")) == {"tier"}
    nested = CLEAN_SPEC.replace("└── scripts/check.py         Tier 1", "└── scripts/\n    └── check.py             prüft")
    assert _rules(nested) == {"tier"}
    nested_ok = CLEAN_SPEC.replace("└── scripts/check.py         Tier 1", "└── scripts/\n    └── check.py             Tier 1")
    assert _findings(nested_ok) == []
    foreign = CLEAN_SPEC.replace("└── scripts/check.py         Tier 1", "├── scripts/check.py         Tier 1\n└── skills/subagent-dev/scripts/plan_to_tasks.py   (zwei Erweiterungen)")
    assert _findings(foreign) == []
    # Shell-Skripte unter scripts/ tragen ebenfalls einen Tier
    assert _rules(CLEAN_SPEC.replace("└── scripts/check.py         Tier 1", "├── scripts/check.py         Tier 1\n└── scripts/run.sh           startet")) == {"tier"}
    # Kommentare zählen nicht als Pfad: weder ein erwähntes Skript noch ein erwähnter fremder Pfad
    comment = CLEAN_SPEC.replace("├── SKILL.md                 Ablauf, Contract", "├── SKILL.md                 Ablauf, ruft scripts/check.py auf")
    assert _findings(comment) == []
    own_with_foreign_comment = CLEAN_SPEC.replace("└── scripts/check.py         Tier 1", "└── scripts/check.py         ruft skills/subagent-dev/scripts/plan_to_tasks.py auf")
    assert _rules(own_with_foreign_comment) == {"tier"}


def test_own_name_is_filename_and_tree_root():
    """Weicht der Dateiname vom Baum ab, ist die Skill trotzdem nie ihr eigener Nachbar,
    und ihre Skripte sind nie fremd."""
    text = CLEAN_SPEC.replace("skills/probe/", "skills/subagent-dev/").replace(
        "impl-plan (der Plan), superpowers:writing-skills (Disziplin)", "impl-plan (der Plan), subagent-dev (selbst)")
    findings = ptt.lint_spec(text, Path("specs/Spec 18 – subagent-dev-lint.md"), repo_root=REPO_ROOT)
    assert [f.rule for f in findings] == ["abgrenzung"]
    no_tier = text.replace("scripts/check.py         Tier 1", "scripts/check.py         prüft").replace(
        "subagent-dev (selbst)", "superpowers:writing-skills (Disziplin)")
    assert [f.rule for f in ptt.lint_spec(no_tier, Path("specs/Spec 18 – subagent-dev-lint.md"), repo_root=REPO_ROOT)] == ["tier"]


def test_indented_fence_does_not_confuse_the_tree():
    listed = CLEAN_SPEC.replace("## Alternatives considered", "1. Aufruf:\n   ```bash\n   python scripts/check.py\n   ```\n\n## Alternatives considered")
    assert _findings(listed) == []


def test_unclosed_fence_is_named():
    text = CLEAN_SPEC.replace("## Alternatives considered", "```bash\npython scripts/check.py\n\n## Alternatives considered")
    findings = _findings(text)
    assert findings[0].rule == "fence"


def test_abgrenzung_needs_two_known_neighbours():
    assert _rules(CLEAN_SPEC.replace("### Abgrenzung", "### Nachbarn")) == {"abgrenzung"}
    one = CLEAN_SPEC.replace(", superpowers:writing-skills (Disziplin)", "")
    assert _rules(one) == {"abgrenzung"}
    unknown = CLEAN_SPEC.replace("impl-plan (der Plan)", "no-such-skill (der Plan)")
    assert _rules(unknown) == {"abgrenzung"}
    plain = CLEAN_SPEC.replace("impl-plan (der Plan), superpowers:writing-skills (Disziplin)", "explain (erklärt), handoff (Übergabe)")
    assert _findings(plain) == []
    assert ptt.lint_spec(unknown, repo_root=None) == []
    findings = ptt.lint_spec(plain, repo_root=None)
    assert [f.rule for f in findings] == ["abgrenzung"] and "ohne Repo-Root" in findings[0].message


def test_gate_words_need_hook_in_tree_or_negation_in_unit():
    hard = CLEAN_SPEC.replace("Der Lint meldet, er blockiert nicht.", "Der Lint blockiert den Commit.")
    assert _rules(hard) == {"gate-language"}
    # Substantiv nach Spec 00 §4
    assert _rules(CLEAN_SPEC.replace("Der Lint meldet, er blockiert nicht.", "Der Lint ist ein Abnahme-Blocker.")) == {"gate-language"}
    with_hook = hard.replace("└── scripts/check.py         Tier 1", "├── scripts/check.py         Tier 1\n└── assets/hooks/pre-commit.sh")
    assert _findings(with_hook) == []
    nested_hook = hard.replace("└── scripts/check.py         Tier 1", "├── scripts/check.py         Tier 1\n└── assets/\n    └── hooks/\n        └── pre-commit.sh")
    assert _findings(nested_hook) == []
    # ein erwähntes assets/hooks/ im Baum-Kommentar ist kein Hook
    mentioned = hard.replace("└── scripts/check.py         Tier 1", "├── scripts/check.py         Tier 1\n└── assets/                  Gerüste (kein assets/hooks/, G2)")
    assert _rules(mentioned) == {"gate-language"}
    rejected = CLEAN_SPEC.replace("Keine Skill, nur ein Dokument — verworfen.", "Ein Hook, der jeden Commit mit rotem Lint blockiert und die\nLänge erzwingt — verworfen, weil er in fremden Repos nichts verloren hat.")
    assert _findings(rejected) == []
    negated_next_line = CLEAN_SPEC.replace("Der Lint meldet, er blockiert nicht.", "Der Lint blockiert den Commit\nnicht, er meldet nur.")
    assert _findings(negated_next_line) == []
    # Tabellen- und Listenzeilen sind eigene Einheiten: die Spalte „nicht" im Kopf negiert nichts
    table = CLEAN_SPEC.replace("| prüfen | probe |", "| prüfen, blockiert den Commit | probe |")
    assert _rules(table) == {"gate-language"}
    bullets = CLEAN_SPEC.replace("Alles andere.", "- Der Lint blockiert den Commit.\n- Kein Hook.")
    assert _rules(bullets) == {"gate-language"}


def test_placeholders_but_not_mentions():
    assert _rules(CLEAN_SPEC.replace("Alles andere.", "TBD")) == {"placeholders"}
    mention = CLEAN_SPEC.replace("Alles andere.", "Der Lint meldet `TBD` und „TODO\" als Platzhalter.")
    assert _findings(mention) == []
    stray = mention.replace("Etwas fehlt.", "Etwas ` fehlt.")
    assert _findings(stray) == []


def test_template_residues_in_header_and_eval_ids():
    residue = CLEAN_SPEC.replace("Zyklus 18", "Zyklus NN").replace("`probe-writes-artifact`", "`<zusage>-appears-verbatim`")
    findings = _findings(residue)
    assert [f.rule for f in findings] == ["placeholders"]
    assert "Zyklus NN" in findings[0].message and "<zusage>" in findings[0].message
    convention = CLEAN_SPEC.replace("Alles andere.", "Aufruf: `lint-spec specs/<name>.md`.")
    assert _findings(convention) == []


def test_real_specs_are_calibration_not_noise():
    """Die drei bisher reviewten Specs: höchstens die bekannten Restbefunde — nichts
    Erfundenes. Teilmenge, nicht Gleichheit: Wer Spec 17 die Kopfzeile gibt, macht
    den Test nicht rot."""
    def rules(n):
        path = next((REPO_ROOT / "specs").glob(f"Spec {n} *.md"))
        return {f.rule for f in ptt.lint_spec(path.read_text(encoding="utf-8"), path)}
    assert rules(15) <= {"eval-table"}            # Tabelle ohne Fixture-/Diskriminator-Spalte
    assert rules(16) == set()                     # erweitert subagent-devs Skript — nicht ihr Tier
    assert rules(17) <= {"header", "abgrenzung"}  # beginnt mit ## Problem, Abgrenzung in Prosa


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
    assert data["_meta"]["skill"] == "subagent-dev" and "lint-spec" in data["_meta"]["generated"] and "--repo-root" in data["_meta"]["generated"]
    assert [f["rule"] for f in data["findings"]] == ["review-note"]
    assert ptt.main(["lint-spec", str(new), "--repo-root", str(REPO_ROOT), "--cutoff", "19"]) == 0
    assert ptt.main(["lint-spec", str(tmp_path / "fehlt.md")]) == 2


def test_artifact_meta_is_shared():
    assert ptt.lint_meta("p.md", spec="s.md", skill="x")["generated"].endswith("lint p.md --spec s.md --skill x")
    assert ptt.spec_lint_meta("s.md")["generated"].endswith("lint-spec s.md")


def test_spec_number():
    assert ptt.spec_number(Path("specs/Spec 17 – skill-forge.md")) == 17
    assert ptt.spec_number(Path("specs/foo.md")) is None
    assert ptt.spec_number(None) is None


def test_eval_table_locator_is_shared():
    """Eine Definition der Eval-Tabelle für `spec_eval_table` und `lint-spec`."""
    lines = ptt._mask_fenced_blocks(CLEAN_SPEC).splitlines()
    located = ptt._locate_eval_table(lines)
    assert located is not None and located[1][:2] == ["#", "id"]
    assert ptt.spec_eval_table(CLEAN_SPEC) == (["anti-ceremony-one-line-stays-small", "probe-writes-artifact"], [])
