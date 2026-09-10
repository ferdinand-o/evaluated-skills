<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# skill-forge Implementation Plan

**Goal:** Wer in dieser Sammlung eine Skill baut oder ändert, bekommt den Hausablauf zum
richtigen Zeitpunkt in den Kontext und ein Skript, das dreizehn Regeln mechanisch prüft —
und ein geänderter Satz bleibt ein geänderter Satz.

**Architecture:** Tier 1. Der einzige Code ist `skills/skill-forge/scripts/lint_skill.py`
(Stdlib, importiert kein anderes Skill-Skript und nicht `evalkit`): dreizehn Regeln mit
`pass | finding | hint | unchecked`, `lint.json` mit festem Zeilenvertrag, Diff-Modus mit
`--base` (nur neue Befunde zählen) und `evals_due`. Dazu ein Repo-Test mit eingefrorenem
Register über alle Skills, vier References, ein Skill-Template, fünf Evals, drei
Spec-00-Änderungen.

**Tech Stack:** Python 3.13 Stdlib für Skript und Tests; Markdown für Skill, References,
Evals.

**Spec:** `specs/Spec 17 – skill-forge.md`

## Global Constraints

- **E1 — Tier 1, nur Stdlib** (Spec 00 §3). Ohne Git oder unbekannte Revision endet der
  Diff-Modus mit Exit 2 und Grund; er zählt nie stillschweigend alle Befunde als neu.
- **E2 — Gate-Sprache** (Spec 00 §4): G1 „verlangt", G2 „meldet". Nichts blockiert.
- **E3 — Kopfzeile je Artefakt** (`docs/artifact-header.md`): `lint.json` per `_meta`;
  `evals.json` und `report.md` im Template tragen sie, das SKILL.md-Gerüst nicht.
- **E4 — SKILL.md ≤ 150 Zeilen**, Frontmatter nur `name` und `description`, Description
  mit Trigger und Abgrenzung und ohne Prozessverb — die eigene Regel gilt zuerst hier.
- **E5 — Anti-Zeremonie-Eval ist Pflicht** (Spec 00 §2), gebunden an `lint.json`.
- **E6 — `unchecked` und `hint` zählen nie als `pass`.** Jede Regel sagt, was sie nicht
  sehen konnte.
- **E7 — Selbstbezug:** Der Repo-Test lintet `skills/skill-forge` mit leerem Register.
  Ein eigener Befund wird behoben, nicht eingetragen.

## Skill-Struktur

```
skills/skill-forge/
├── SKILL.md
├── references/checklist.md, form-selection.md, evals.md, reviewer-prompt.md
├── assets/skill-template/SKILL.md, evals.json, report.md
└── scripts/lint_skill.py

evals/skill-forge/evals.json, evals/fixtures/sf-existing, sf-gate, sf-noanti, sf-spec
tests/test_skill_forge_lint.py, tests/test_skills_lint.py, tests/test_skill_forge_evals_schema.py
```

### Task 1: Lint-Regeln und lint.json

Das Skript ohne Diff-Modus: dreizehn Regeln, Statusmodell, Artefakt, CLI. Jede Regel
ist eine Funktion mit derselben Signatur, damit Task 2 und der Repo-Test sie einzeln
aufrufen können.

**Files:**
- Create: `skills/skill-forge/scripts/lint_skill.py`
- Test: `tests/test_skill_forge_lint.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `fn:lint_skill(skill_dir, repo_root)`, `fn:render_lint_json(report, meta)`, `fn:main(argv)`, `token:unchecked`, `token:hint`

- [x] **Step 1: Tests schreiben** — je Regel ein Skill-Ordner in `tmp_path`, der sie
      reißt, und einer, der sie besteht; dazu: `gate-language` mit Negation im selben
      Absatz ist `pass`, in einer Tabellenzeile ohne Negation `finding`; `script-tier`
      nimmt die erste Nennung und erlaubt Sibling-Importe; `neighbors` ohne
      Abgrenzungsabschnitt ist `unchecked`, nie `pass`; `judge-claims` ist höchstens
      `hint`; ohne `docs/` sind `asset-headers`, `routing`, `report-section` `unchecked`;
      `lint.json` hat je Regel die Zeile `{"id": "…", "status": "…", "reason": "…"}` in
      dieser Reihenfolge; Exit 0/1/2.
- [x] **Step 2: Rot sehen** — `pytest tests/test_skill_forge_lint.py`.
- [x] **Step 3: Implementieren** — Modul-Docstring „Tier 1: nur Stdlib"; `RULES` als
      Liste `(id, fn)`; jede `fn(skill_dir, repo_root) -> RuleResult(id, status, reason)`;
      `repo_root` ist der nächste Elternordner mit `specs/` oder `evals/`, sonst `None`
      und alle Repo-Regeln `unchecked`; `render_lint_json` schreibt `_meta` nach
      `docs/artifact-header.md`, dann die Regelzeilen; `main` mit `skill_dir`, `--out`.
- [x] **Step 4: Grün sehen**, volle Suite; Skript einmal gegen `skills/impl-plan` fahren
      und die Ausgabe von Hand gegen die Regeltabelle der Spec lesen.
- [x] **Step 5: Commit.**

### Task 2: Diff-Modus und evals_due

**Files:**
- Modify: `skills/skill-forge/scripts/lint_skill.py`
- Modify: `tests/test_skill_forge_lint.py`

**Interfaces:**
- Consumes: `fn:lint_skill(skill_dir, repo_root)`, `fn:render_lint_json(report, meta)`
- Produces: `fn:lint_at_base(skill_dir, repo_root, rev)`, `fn:evals_due(diff_lines, skill_dir)`, `token:evals_due`, `token:findings_mode`, `token:new_findings`

- [x] **Step 1: Tests schreiben** — Git-Repo in `tmp_path` mit einer Skill und einem
      Commit: ein geänderter Satz im Body → `new_findings` leer, `evals_due: false`,
      Exit 0, obwohl die Skill an der Basis einen Altbefund trägt; eine geänderte Zeile
      im Frontmatter → `evals_due: true`; eine Zeile im Abschnitt `## Der Contract` →
      `true` (Regex `^## .*Contract`); eine Zeile, auf die ein `must_not`-Pattern mit
      `\s*` greift → `true`; ohne `--base` → `findings_mode: "all"`, `evals_due:
      "unchecked"`; `--base` ohne Git → Exit 2.
- [x] **Step 2: Rot sehen.**
- [x] **Step 3: Implementieren** — `lint_at_base` liest den Ordner per
      `git show <rev>:<pfad>` in ein Temp-Verzeichnis und lintet ihn dort;
      `new_findings` = Befunde des Arbeitsstands minus Befunde der Basis (nach Regel-ID);
      `evals_due` über `git diff <rev> -- <skill_dir>`, Zeilen mit `+`/`-`, gegen
      Frontmatter-Bereich, Contract-Bereich und `re.search` je Pattern aus `file_matches`
      und `output_matches` in `must` und `must_not`; Exit-Code folgt `new_findings`.
- [x] **Step 4: Grün sehen**, volle Suite.
- [x] **Step 5: Commit.**

### Task 3: Repo-Test mit Register

**Files:**
- Create: `tests/test_skills_lint.py`

**Interfaces:**
- Consumes: `fn:lint_skill(skill_dir, repo_root)`
- Produces: `known_findings`

- [x] **Step 1: Ersten Lauf messen** — `lint_skill` über jeden Ordner unter `skills/`,
      Befund-IDs je Skill notieren; Erwartung laut Spec: `description` 18,
      `anti-ceremony-eval` 14, `evals-exist` 3, `report-section` 19, `neighbors` 13,
      `routing` 7, `asset-headers` 2, `gate-language` 1. Abweichungen sind entweder ein
      Skript-Fehler (zurück zu Task 1) oder eine Korrektur der Spec-Zahl — beides wird
      im Commit benannt.
- [x] **Step 2: Register** — `KNOWN_FINDINGS: dict[str, frozenset[str]]` aus dem Lauf,
      `KNOWN_FINDINGS_MAX_PAIRS` als Paarzahl, Kommentar mit Datum und dem Satz „darf
      nur schrumpfen".
- [x] **Step 3: Vier Tests** — kein Befund außerhalb des Registers; Register nennt nur
      existierende Skills und existierende Regel-IDs; Paarzahl ≤ Maximum; `skill-forge`
      hat ein leeres Register (bis Task 10 existiert der Ordner nur mit Skript — der Test
      überspringt fehlende Ordner nicht, er erwartet ihn).
- [x] **Step 4: Grün sehen**, volle Suite. Commit.

### Task 4: references/checklist.md

**Files:**
- Create: `skills/skill-forge/references/checklist.md`

**Interfaces:**
- Consumes: `token:unchecked`
- Produces: `checklist_md`

- [ ] **Step 1: Schreiben** — die 19 Punkte der Prüfung §4.3 nach Bauphase gruppiert
      (Spec, Plan, Bau, Evals, Report/Nachbarn), je Punkt die Quelle (Spec 00 §, Pitfalls,
      known-limits-Abschnitt) und die Markierung „mechanisch: Regel-ID" für die dreizehn,
      die `lint_skill.py` prüft; die sechs Ermessenspunkte mit der Frage, die man sich
      stellt, nicht mit einem Appell.
- [ ] **Step 2: Prüfen** — jede genannte Regel-ID existiert im Skript (`grep` gegen
      `RULES`); kein Platzhalterwort. Commit.

### Task 5: references/form-selection.md

**Files:**
- Create: `skills/skill-forge/references/form-selection.md`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `form_selection_md`

- [ ] **Step 1: Schreiben** — „Match the Form to the Failure" aus
      `superpowers:writing-skills`, übersetzt: Verbot, Rezept, Pflichtslot, Konditional,
      je nach Fehlerart; mit der Beobachtung, dass Verbote bei Form-Fehlern nach hinten
      losgehen; ergänzt um die Fälle aus `docs/skill-building-pitfalls.md` („Beispiele
      schlagen Vorschriften", „Wo meldet etwas Erfolg, ohne geprüft zu haben").
- [ ] **Step 2: Prüfen** — jeder Pitfalls-Fall ist mit seinem Abschnitt zitiert; kein
      Platzhalterwort. Commit.

### Task 6: references/evals.md

**Files:**
- Create: `skills/skill-forge/references/evals.md`

**Interfaces:**
- Consumes: `token:hint`
- Produces: `evals_md`

- [ ] **Step 1: Schreiben** — Diskriminator-Frage mit dem Muster aus
      `evals/explain/evals.json` und `evals/impl-plan/evals.json`; Judge-Zerlegung nach
      known-limits „Judge" (ein Claim, eine Zahl statt Adjektiv; warum die Konjunktion
      nur ein `hint` ist); Fixture-Vorbedingungen (`"git": true`, nichts unter dem Glob,
      den die Skill schreibt); Trigger-Eval-Set nach `skill-creator` (20 Anfragen, 8–10
      Beinahe-Treffer) als Vorgehen für den Tag, an dem der Harness außerhalb eines
      Root-Containers läuft; der Baseline-Lauf ohne Skill als Forderung an eine eigene Spec.
- [ ] **Step 2: Prüfen** — kein Platzhalterwort; jede zitierte known-limits-Überschrift
      existiert. Commit.

### Task 7: references/reviewer-prompt.md

**Files:**
- Create: `skills/skill-forge/references/reviewer-prompt.md`

**Interfaces:**
- Consumes: `file:skills/impl-plan/references/reviewer-prompt.md`
- Produces: `reviewer_prompt_md`

- [ ] **Step 1: Schreiben** — Bau-Review durch einen Subagenten mit frischem Kontext:
      Eingaben Spec, Plan, Skill-Ordner, `lint.json`; Kategorien Spec-Abgleich,
      Diskriminator je Eval, Gate-Ehrlichkeit, Nachbarn, Zahlen nachmessen; Kalibrierung
      und Ausgabeformat wie in `impl-plan`s Reviewer-Prompt.
- [ ] **Step 2: Prüfen** — Prompt verlangt Belege (Datei:Zeile) und eigene Messung; kein
      Platzhalterwort. Commit.

### Task 8: assets/skill-template

**Files:**
- Create: `skills/skill-forge/assets/skill-template/SKILL.md`
- Create: `skills/skill-forge/assets/skill-template/evals.json`
- Create: `skills/skill-forge/assets/skill-template/report.md`

**Interfaces:**
- Consumes: `fn:lint_skill(skill_dir, repo_root)`
- Produces: `skill_template`

- [ ] **Step 1: SKILL.md-Gerüst** — Frontmatter mit Beispiel-Description (Trigger,
      Abgrenzung, kein Prozessverb), die fünf Hausabschnitte: Eiserne Regel, Ablauf,
      Contract, Anti-Rationalisierung, Abgrenzung; Auslassungen als `…`.
- [ ] **Step 2: evals.json-Gerüst** — Kopfzeile per `_meta`, ein Eval mit ID-Präfix
      `anti-ceremony-`, gültige Beispielwerte (lädt über `evalkit.schema.load_evals`).
- [ ] **Step 3: report.md-Gerüst** — Kopfzeile, Sektion „Was nicht gemessen wurde".
- [ ] **Step 4: Prüfen** — das Template in ein `tmp_path`-Skill kopiert besteht die
      Regeln 1–5 und `anti-ceremony-eval`; `load_evals` lädt die `evals.json`. Commit.

### Task 9: Evals

**Files:**
- Create: `evals/skill-forge/evals.json`
- Create: `evals/fixtures/sf-existing/fixture.json`
- Create: `evals/fixtures/sf-gate/fixture.json`
- Create: `evals/fixtures/sf-noanti/fixture.json`
- Create: `evals/fixtures/sf-spec/fixture.json`
- Create: `tests/test_skill_forge_evals_schema.py`

**Interfaces:**
- Consumes: `token:evals_due`, `token:findings_mode`
- Produces: `skill_forge_evals`

- [ ] **Step 1: Fixtures** — `sf-existing`: Mini-Skill `note-tag` mit `evals.json`
      (ID-Präfix `anti-ceremony-`, Pattern `Untagged:`), Report mit Pflichtsektion,
      `docs/known-limits.md` mit `## note-tag`, `"git": true`, ein Commit — an der Basis
      lint-sauber, gemessen mit dem Skript; `sf-gate`: Skill `gate-demo` mit „blockiert
      den Commit" im Contract, ohne `assets/hooks/`, ohne `evals/` und `docs/`;
      `sf-noanti`: Skill mit `evals.json` ohne Präfix; `sf-spec`: gekürzte Spec 00 (§3–§5,
      ohne §2, ohne Eval-Vokabular) und `specs/Spec 30 – reminder.md`, nichts unter
      `evals/`. Keine Fixture bringt `.skills/cache/` mit.
- [ ] **Step 2: Fünf Evals** wie in Spec 17, alle `contract`, ein Prompt je Eval,
      `notes` mit Diskriminator: `anti-ceremony-one-sentence-change-lints-only`,
      `token-change-makes-evals-due`, `gate-word-without-hook-is-reported`,
      `missing-anti-ceremony-eval-is-reported`, `routing-new-skill-gets-house-evals`.
      Die `file_matches`-Muster escapen Klammern und Anführungszeichen; jedes Muster wird
      gegen eine vom Skript erzeugte `lint.json` getestet, nicht gegen eine von Hand
      geschriebene.
- [ ] **Step 3: Schema-Test** — `load_evals` lädt fünf contract-Evals; Anti-Zeremonie-Eval
      bindet an `lint.json`; jedes `lint.json`-Muster greift an einer echten Ausgabe des
      Skripts aus `sf-gate` und `sf-noanti` und nicht an der Ausgabe für `sf-existing`;
      keine Fixture enthält `.skills/cache/`; `sf-spec` enthält nichts unter `evals/`.
      Commit.

### Task 10: SKILL.md

**Files:**
- Create: `skills/skill-forge/SKILL.md`

**Interfaces:**
- Consumes: `token:evals_due`, `token:new_findings`, `checklist_md`, `evals_md`, `form_selection_md`, `reviewer_prompt_md`, `skill_template`
- Produces: `skill_forge_skill`

- [ ] **Step 1: Frontmatter** — `name: skill-forge`; Description mit Triggern („bau mir
      eine Skill", „ändere die Skill X", „prüfe die Skill X"), Abgrenzung gegen
      `skill-creator` (außerhalb dieser Sammlung, eigenes Eval-Schema) und
      `superpowers:writing-skills` (Disziplin-Skills mit Druckszenarien), ohne Prozessverb.
- [ ] **Step 2: Body** — Eiserne Regel (neue Befunde, Pflichtsektion), Ablauf in sieben
      Schritten mit beiden Skriptpfaden, Anti-Zeremonie-Regel, Contract (Statusmodell,
      `unchecked` nie `pass`, `--base HEAD` vor dem Commit), Anti-Rationalisierung
      (mindestens: „Der Altbefund ist nicht meiner", „Lint ist rot, ich räume schnell
      alles auf", „Ein Satz braucht keinen Lint"), Abgrenzung inklusive `impl-plan` und
      `subagent-dev`.
- [ ] **Step 3: Prüfen** — `wc -l` unter 150; `lint_skill.py skills/skill-forge` ohne
      Befund außerhalb `report-section` und `routing` (die Task 11–13 schließen);
      Sprachprüfung nach Spec 00 §4. Commit.

### Task 11: Nachbarn

**Files:**
- Modify: `specs/Spec 00 – skill-foundation.md`
- Modify: `README.md`
- Modify: `skills/impl-plan/SKILL.md`

**Interfaces:**
- Consumes: `skill_forge_skill`
- Produces: (nichts Neues)

- [ ] **Step 1: Spec 00** — §5 Description-Satz („keine Prozessbeschreibung"), §2
      ID-Präfix `anti-ceremony-`, Routing-Zeile „Skill bauen oder ändern → skill-forge
      (17), nicht skill-creator, nicht superpowers:writing-skills".
- [ ] **Step 2: README** — dieselbe Routing-Zeile.
- [ ] **Step 3: impl-plan** — „skill-forge (17, geplant)" wird „skill-forge (17)".
      `lint_skill.py skills/skill-forge`: `routing` und `neighbors` jetzt `pass`. Commit.

### Task 12: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `known_findings`, `skill_forge_evals`
- Produces: (nichts Neues)

- [ ] **Step 1: Abschnitt `## skill-forge`** — das Register als Schuldenregister mit den
      gemessenen Zahlen; die Mengen-Semantik (zweiter Befund derselben Regel bleibt
      verdeckt); Evals ungefahren; Trigger ungemessen; `judge-claims` als `hint` mit der
      Trefferzahl; die Skriptpfad-Zweiform; die Forderung nach `--without-skill`. Commit.

### Task 13: Report

**Files:**
- Create: `docs/superpowers/reports/skill-forge-report.md`

**Interfaces:**
- Consumes: `known_findings`, `skill_forge_evals`, `skill_forge_skill`
- Produces: (nichts Neues)

- [ ] **Step 1: Report** — was entstanden ist, die Entscheidungen (Diff-Modus,
      `hint`-Status, Skriptpfad), die Messung des ersten Lint-Laufs über alle Skills mit
      Datum, „Was nicht gemessen wurde". Danach `lint_skill.py skills/skill-forge`
      vollständig sauber. Commit.
