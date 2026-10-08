<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# plugin-split Implementation Plan

**Goal:** Die Sammlung lässt sich in drei Plugins getrennt an- und abschalten, jede
Projekt-Kopie unter `.claude/skills/` gleicht ihrem Original vor dem Commit, und
superpowers kann abgelöst werden, sobald die Abschaltbedingung erfüllt ist.

**Architecture:** Tier 1. Neuer Code liegt an zwei Stellen: `scripts/sync_skills.py`
(Repo-Werkzeug, Stdlib) spiegelt die Skills der Projekt-Tabelle nach
`.claude/skills/<name>/`, prüft mit `--check` und zählt mit `--report`
`superpowers:`-Verweise; `skills/skill-forge/scripts/lint_skill.py` bekommt die
vierzehnte Regel `plugin-membership`, die die `skills`-Listen im Manifest liest. Die
Plugins sind drei Manifest-Einträge mit `source: "./"` und `skills`-Liste, ohne Kopien.
Alles andere sind Doktrin-Änderungen in skill-forge, zwei Descriptions, Evals und Doku.

**Tech Stack:** Python 3.13 Stdlib für Skripte und Tests; Markdown für Skill,
References, Evals; `claude plugin validate` und `claude plugin install` mit einem
Wegwerf-`CLAUDE_CONFIG_DIR` für die Manifest-Prüfung.

**Spec:** `specs/Spec 20 – plugin-split.md`

## Global Constraints

- **E1 — Tier 1, nur Stdlib** (Spec 00 §3). `sync_skills.py --check` endet mit Exit 1
  bei Befund; `--report` endet mit Exit 2 bei kaputtem Manifest oder `excluded.json` und
  meldet nie Erfolg, wenn es nicht prüfen konnte. `plugin-membership` ist ohne Manifest
  `unchecked`, nie `pass`.
- **E2 — Gate-Sprache** (Spec 00 §4): G1 „verlangt", G2 „meldet". Kein Hook, nichts
  blockiert; der Sync-Check in skill-forge Schritt 4 ist G1, der Test G2.
- **E3 — Kopfzeile je Artefakt** (`docs/artifact-header.md`): `lint.json` per `_meta`
  wie bisher. `.claude-plugin/excluded.json` ist Repo-Konfiguration ohne `_meta`;
  Schlüssel mit `_` am Anfang ignorieren Test und Regel.
- **E4 — SKILL.md ≤ 150 Zeilen** für skill-forge (heute 112) und impl-plan (heute 103).
- **E5 — Anti-Zeremonie-Eval bleibt Pflicht** (Spec 00 §2):
  `anti-ceremony-one-sentence-change-lints-only` bleibt an `lint.json` gebunden.
- **E6 — Kopien nie von Hand ändern.** Alles unter `.claude/skills/` schreibt nur
  `sync_skills.py`; eine Task, die das Original einer Projekt-Skill ändert, fährt danach
  `python scripts/sync_skills.py` und `--check`.
- **E7 — Kein Eval auf `.claude/`.** Der Harness schließt den Ordner aus; Projekt-Kopien
  prüfen Test und Sync-Check.

## Skill-Struktur

```
scripts/sync_skills.py
.claude/skills/…  (generiert)
.claude/settings.json
.claude-plugin/marketplace.json, .claude-plugin/excluded.json

skills/skill-forge/SKILL.md
skills/skill-forge/references/checklist.md, references/reviewer-prompt.md
skills/skill-forge/scripts/lint_skill.py
skills/feature-spec/SKILL.md, skills/debug-ledger/SKILL.md, skills/impl-plan/SKILL.md
skills/visual-summary/references/charts.md

evals/skill-forge/evals.json
evals/fixtures/sf-existing/, sf-spec/, sf-plugin-orphan/
tests/test_marketplace.py, tests/test_skill_forge_lint.py, tests/test_skill_forge_evals_schema.py
tests/test_project_skills_copy.py  (entfällt)

specs/Spec 00 – skill-foundation.md, README.md, docs/known-limits.md
docs/superpowers/validation/2026-10-08-plugin-split-sync.md
docs/superpowers/reports/skill-forge-report.md
```

### Task 1: Sync-Weg messen

Erledigt am 2026-10-08. Die Messung endete mit Stopp, weil der Nutzer nur über die CLI
anbindet; Spec 20 wurde darauf auf `source: "./"` mit `skills`-Liste umgestellt und
dieser Plan überarbeitet.

**Files:**
- Create: `docs/superpowers/validation/2026-10-08-plugin-split-sync.md`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `token:Ergebnis:`

- [x] **Step 1: Vorher messen** — `/context` aus der lokalen Session des Nutzers ins
      Protokoll übernommen.
- [x] **Step 2: Wegwerf-Branch bauen** — `claude/plugin-split-sync-probe`, validiert,
      CLI-Weg als Vergleichswert gemessen.
- [x] **Step 3: In claude.ai einbinden** — entfällt; Begründung des Nutzers im Protokoll.
- [x] **Step 4: Protokoll abschließen** — Ergebnis Stopp mit Grund; den Probe-Branch
      löscht der Nutzer auf GitHub, weil der Proxy der Cloud-Session das nicht erlaubt.
- [x] **Step 5: Commit.**

### Task 2: sync_skills.py

**Files:**
- Create: `scripts/sync_skills.py`
- Test: `tests/test_marketplace.py`

**Interfaces:**
- Consumes: `token:Ergebnis:`
- Produces: `fn:sync(repo_root, check)`, `fn:superpowers_report(repo_root)`, `fn:main(argv)`

- [x] **Step 1: Tests schreiben** — `test_sync_mirrors_and_ignores_pycache`: in einem
      Temp-Repo kopiert `sync` neue und geänderte Dateien nach `.claude/skills/`, löscht
      in der Kopie eine im Original gelöschte Datei, kopiert `__pycache__/` und `*.pyc`
      nicht; `check=True` schreibt nichts und meldet je Datei `fehlend`, `überzählig`
      oder `abweichend`. `test_superpowers_report_counts_descriptions`: Fundstelle in
      der Description einer Skill aus der `skills`-Liste eines Plugins mit
      `defaultEnabled: true` zählt, in einem mit `false` und in einer ausgeschlossenen
      Skill nicht. Dazu: Manifest, das kein JSON ist, und `excluded.json`, das kein
      Objekt ist → `main` mit `--report` endet mit 2.
- [x] **Step 2: Rot sehen** — `pytest tests/test_marketplace.py -k "sync or superpowers_report"`.
- [x] **Step 3: Implementieren** — Modul-Docstring „Tier 1: nur Stdlib"; Tabelle
      `PROJECT_SKILLS` mit den zehn Skills aus `REPO_DEV_SKILLS` in
      `tests/test_project_skills_copy.py`; `sync` vergleicht Bytes und schreibt nach
      `.claude/skills/<name>/`; `--check` gibt Exit 1 bei Befund; `superpowers_report`
      liest `defaultEnabled` und `skills`-Listen aus dem Manifest und die Descriptions
      aus dem Frontmatter der Originale; `main` mit `--check`, `--report`, `--repo`.
- [x] **Step 4: Grün sehen**, volle Suite; `python scripts/sync_skills.py --check` gegen
      das echte Repo meldet keinen Befund, weil die Kopien aus PR #16 dem Original
      gleichen.
- [x] **Step 5: Commit.**

### Task 3: Manifest und Repo-Tests umstellen

**Files:**
- Modify: `.claude-plugin/marketplace.json`
- Create: `.claude-plugin/excluded.json`
- Create: `.claude/settings.json`
- Modify: `tests/test_marketplace.py`
- Delete: `tests/test_project_skills_copy.py`

**Interfaces:**
- Consumes: `fn:sync(repo_root, check)`
- Produces: `token:cc-knowledge`, `token:cc-dev@cc-skills`

- [x] **Step 1: Tests umschreiben** — `test_every_skill_in_exactly_one_plugin` (liest die
      `skills`-Listen), `test_project_copies_match_originals` (ruft
      `sync(repo_root, check=True)` und ersetzt `tests/test_project_skills_copy.py`),
      `test_plugin_entries_are_fixed` (genau `cc-dev`, `cc-ui`, `cc-knowledge`; `source`
      `./`; sortierte `skills`-Liste mit existierenden Ordnern; kein `version`, keine
      `dependencies`; `defaultEnabled` true, false, true; `renames` erlaubt),
      `test_excluded_json_names_existing_skills_with_reason` (liest `excluded.json`
      statt `EXCLUDED`), `test_repo_disables_cc_dev_for_project_copies`;
      `test_no_plugin_json_that_would_conflict_with_strict_false` und
      `test_descriptions_carry_no_angle_bracket_tags` bleiben.
- [x] **Step 2: Rot sehen** — `pytest tests/test_marketplace.py`.
- [x] **Step 3: Umbauen** — Manifest mit drei Einträgen nach der Zuschnitt-Tabelle der
      Spec, je `source: "./"`, `strict: false`, `skills`-Liste mit `./skills/<name>`, und
      `renames: {"cc-skills": null}`; `excluded.json` mit `cad-parts`, `impl-plan`,
      `skill-forge` und je dem Grund aus der Spec; `.claude/settings.json` mit
      `enabledPlugins` `cc-dev@cc-skills` auf `false`; `tests/test_project_skills_copy.py`
      löschen.
- [x] **Step 4: Grün sehen**, volle Suite; `claude plugin validate .` grün; mit einem
      Wegwerf-`CLAUDE_CONFIG_DIR` Marketplace aus dem Arbeitsverzeichnis hinzufügen,
      alle drei Plugins installieren, `claude plugin list` zeigt `cc-ui` deaktiviert;
      `python scripts/sync_skills.py --report` meldet 6 Fundstellen in `cc-dev`.
- [x] **Step 5: Commit.**

### Task 4: Lint-Regel plugin-membership

Lesson aus dem Bau: Die neue Regel macht `test_sf_existing_is_clean_at_base` rot, weil die
Fixture `sf-existing` ohne Manifest `unchecked` liefert. Ihr Manifest stand zuerst in
Task 9; es gehört in die Task, die die Regel einführt, sonst ist die Suite zwischen Task 4
und Task 9 rot.

**Files:**
- Modify: `skills/skill-forge/scripts/lint_skill.py`
- Modify: `.claude/skills/skill-forge/`
- Create: `evals/fixtures/sf-existing/.claude-plugin/`
- Test: `tests/test_skill_forge_lint.py`

**Interfaces:**
- Consumes: `token:cc-knowledge`
- Produces: `fn:rule_plugin_membership(skill_dir, repo_root)`

- [x] **Step 1: Tests schreiben** — `test_plugin_membership_rule`: `make_repo` legt ein
      Manifest an; `pass` bei genau einer `skills`-Liste und bei Ausschluss; `finding`
      bei null Listen, bei zwei Listen und bei ausgeschlossen plus gelistet; `unchecked`
      ohne Manifest, bei einem Eintrag ohne `skills`-Liste und bei `excluded.json`, das
      kein Objekt ist. Regelzahl 14; die `unchecked`-Zahl im Eval-Workspace-Fall steigt
      um eins; die Lint-Ausgabe nennt `sync_skills.py --check`. Die Fixture `sf-existing`
      bekommt ein Manifest mit note-tag und handoff in einer `skills`-Liste, damit sie
      ohne `unchecked` bleibt.
- [x] **Step 2: Rot sehen** — `pytest tests/test_skill_forge_lint.py -k "plugin_membership or rule_count"`.
- [x] **Step 3: Implementieren** — `rule_plugin_membership` liest
      `.claude-plugin/marketplace.json` und `excluded.json` unter der Repo-Wurzel und
      zählt Einträge, deren `skills`-Liste `./skills/<name>` enthält; Eintrag in `RULES`;
      Kopfzeile und Docstring „dreizehn" → „vierzehn"; Hinweiszeile auf
      `sync_skills.py --check` am Ende der Textausgabe.
- [x] **Step 4: Grün sehen**, volle Suite; `python skills/skill-forge/scripts/lint_skill.py
      skills/handoff` meldet `plugin-membership` `pass`; danach
      `python scripts/sync_skills.py` und `--check`, weil `lint_skill.py` in
      `.claude/skills/skill-forge/` gespiegelt ist.
- [x] **Step 5: Commit.**

### Task 5: Kein Dateiverweis über eine Plugin-Grenze

**Files:**
- Modify: `skills/visual-summary/references/charts.md`
- Modify: `tests/test_marketplace.py`

**Interfaces:**
- Consumes: `token:cc-knowledge`
- Produces: `fn:test_no_file_refs_across_plugins()`

- [x] **Step 1: Test schreiben** — `test_no_file_refs_across_plugins`: für jede Skill in
      einer `skills`-Liste kein `skills/<andere>/` in ihren Dateien, wenn die andere in
      einer anderen Liste oder in `excluded.json` steht.
- [x] **Step 2: Rot sehen** — der Test meldet `skills/visual-summary/references/charts.md`
      Zeile 6 mit Verweis auf `skills/enterprise-ui/references/charts.md`.
- [x] **Step 3: Beheben** — die A11y-Prinzipien, auf die Zeile 6 verweist, aus
      `skills/enterprise-ui/references/charts.md` in eigenen Worten nach
      `skills/visual-summary/references/charts.md` übernehmen und den Verweis streichen.
- [x] **Step 4: Grün sehen**, volle Suite; `lint_skill.py --base HEAD skills/visual-summary`
      zeigt, ob `evals_due` entsteht; falls ja, steht das im Commit-Text und in Task 12.
- [x] **Step 5: Commit.**

### Task 6: Descriptions von feature-spec und debug-ledger

**Files:**
- Modify: `skills/feature-spec/SKILL.md`
- Modify: `skills/debug-ledger/SKILL.md`
- Modify: `.claude/skills/feature-spec/`
- Modify: `.claude/skills/debug-ledger/`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `token:use debug-ledger`

- [x] **Step 1: Schreiben** — feature-spec: Description „use systematic-debugging" →
      „use debug-ledger", Abgrenzung **systematic-debugging** → **debug-ledger**;
      debug-ledger: Description ohne den nackten Namen `systematic-debugging`, die
      Abgrenzung behält `superpowers:systematic-debugging` als Herkunft.
- [x] **Step 2: Prüfen** — `lint_skill.py --base HEAD` für beide ohne neuen Befund;
      `evals_due` ist für beide `true`; `pytest tests/test_marketplace.py -k angle`;
      `python scripts/sync_skills.py` und `--check`.
- [x] **Step 3: Evals fahren** — `python run_evals.py --skill feature-spec --class contract`
      und dasselbe für debug-ledger; läuft der Runner hier nicht (known-limits, root),
      steht „ungeprüft — Runner nicht lauffähig" im Commit-Text und in Task 12.
- [x] **Step 4: Commit.**

### Task 7: skill-forge SKILL.md

**Files:**
- Modify: `skills/skill-forge/SKILL.md`
- Modify: `.claude/skills/skill-forge/`

**Interfaces:**
- Consumes: `fn:rule_plugin_membership(skill_dir, repo_root)`, `fn:sync(repo_root, check)`
- Produces: `token:Lint, Sync-Check, Commit`, `token:Prüfen ändert nichts`

- [x] **Step 1: Schritt 4** — nach dem Lint `python scripts/sync_skills.py --check`, bei
      Befund `sync_skills.py` und erneut `--check`; Anti-Zeremonie-Satz wird
      „Lint, Sync-Check, Commit — sonst nichts".
- [x] **Step 2: Schritt 7 und Contract** — Plugin-Zuordnung in der `skills`-Liste genau
      eines Plugins mit der Frage „mit welchen Skills wird sie an- und abgeschaltet?",
      sonst `excluded.json` mit Grund, Tabelle `PROJECT_SKILLS` für Skills der
      Repo-Arbeit; Satz „Prüfen ändert nichts: Befunde werden gemeldet, nicht behoben";
      „Dreizehn Regeln" → „Vierzehn"; „Sieben Regeln unchecked" → „Acht"; der Satz zu
      `unchecked` im Eval-Workspace nennt `plugin-membership`.
- [x] **Step 3: Prüfen** — `wc -l` unter 150; `lint_skill.py skills/skill-forge` ohne
      Befund; `pytest tests/test_skills_lint.py`; `python scripts/sync_skills.py` und
      `--check`.
- [x] **Step 4: Commit.**

### Task 8: skill-forge references

**Files:**
- Modify: `skills/skill-forge/references/checklist.md`
- Modify: `skills/skill-forge/references/reviewer-prompt.md`
- Modify: `.claude/skills/skill-forge/`

**Interfaces:**
- Consumes: `fn:rule_plugin_membership(skill_dir, repo_root)`
- Produces: `token:die 20 Punkte`

- [x] **Step 1: Schreiben** — `checklist.md`: Punkt Plugin-Zuordnung in der Phase
      „Report und Nachbarn", Titel „die 19 Punkte" → „die 20 Punkte", Nummerierung
      fortlaufend; `reviewer-prompt.md`: „dreizehn Regeln" → „vierzehn".
- [x] **Step 2: Prüfen** — `grep -ci` auf „dreizehn" in `skills/skill-forge` ist 0;
      `lint_skill.py skills/skill-forge` ohne Befund; `python scripts/sync_skills.py`
      und `--check`.
- [x] **Step 3: Commit.**

### Task 9: Evals

**Files:**
- Modify: `evals/skill-forge/evals.json`
- Create: `evals/fixtures/sf-spec/.claude-plugin/marketplace.json`
- Create: `evals/fixtures/sf-plugin-orphan/`
- Modify: `tests/test_skill_forge_evals_schema.py`

**Interfaces:**
- Consumes: `token:Prüfen ändert nichts`, `fn:rule_plugin_membership(skill_dir, repo_root)`
- Produces: `token:skill-outside-any-plugin-is-reported`

- [x] **Step 1: Fixtures** — `sf-existing` hat sein Manifest seit Task 4; `sf-spec`
      bekommt ein Manifest mit zwei Plugins; `sf-plugin-orphan` neu mit `specs/` als
      Repo-Marker, Manifest mit einer Skill, `skills/orphan-x/` in keiner Liste und
      `fixture.json` mit `"git": true`.
- [x] **Step 2: Evals** — `anti-ceremony-one-sentence-change-lints-only` bekommt
      `file_matches` auf `lint.json` mit `"id": "plugin-membership", "status": "pass"` und
      `file_unchanged` `.claude-plugin/marketplace.json`;
      `routing-new-skill-gets-house-evals` bekommt `file_matches`
      `.claude-plugin/marketplace.json` auf `"\./skills/reminder"` und das `pass` von
      `plugin-membership`; `skill-outside-any-plugin-is-reported` neu mit Prompt
      „Prüfe die Skill orphan-x mit skill-forge.", `file_matches` auf `"status": "finding"`
      für `plugin-membership`, `file_unchanged` auf Manifest und `excluded.json`. In
      `notes` je Eval die Diskriminator-Frage aus der Spec.
      `token-change-makes-evals-due`, `gate-word-without-hook-is-reported` und
      `missing-anti-ceremony-eval-is-reported` bleiben im Wortlaut unverändert.
- [x] **Step 3: Schema-Test** — `len(evals) == 6`, Grip-Tests: die Muster der Evals 1, 5
      und 6 treffen ein von `lint_skill.py` in der jeweiligen Fixture erzeugtes
      `lint.json`; das Muster von `token-change-makes-evals-due` trifft weiter in der
      geänderten `sf-existing`, und in `sf-gate` und `sf-noanti` ist `plugin-membership`
      `unchecked`, sodass `gate-word-without-hook-is-reported` und
      `missing-anti-ceremony-eval-is-reported` unberührt bleiben;
      `pytest tests/test_skill_forge_evals_schema.py`; Commit.

### Task 10: Nachbarn

**Files:**
- Modify: `skills/impl-plan/SKILL.md`
- Modify: `.claude/skills/impl-plan/`
- Modify: `specs/Spec 00 – skill-foundation.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `token:cc-knowledge`
- Produces: `token:Plugin-Zuordnung`

- [x] **Step 1: impl-plan** — die Pflicht-Task „Nachbarn" nennt die Plugin-Zuordnung;
      `wc -l` unter 150; `python scripts/sync_skills.py` und `--check`.
- [x] **Step 2: Spec 00** — §5 Zeile „Bug, Testfehler" → debug-ledger (01); Out of scope
      ohne „Plugin-/Marketplace-Packaging"; keine Plugin-Spalte.
- [x] **Step 3: README** — „Aufbau" nennt `.claude/skills/` und `scripts/`; Installation
      je Plugin als Liste mit Skills, keine Tabelle; Umstieg von `cc-skills` über
      `renames` nach `/plugin marketplace update` und die drei `/plugin install`-Befehle.
      `pytest tests/test_skills_lint.py`; Commit.

### Task 11: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `token:skill-outside-any-plugin-is-reported`
- Produces: (nichts Neues)

- [ ] **Step 1: Abschnitt** — Marketplace: drei Einträge mit Root-Quelle und
      `skills`-Liste, nur der CLI-Weg ist abgedeckt, Plugins laden in Cloud-Sessions
      nicht, Namensraum `cc-dev:`; in fremden Repos laufen die Skripte von 9 der 10
      Skills in `cc-dev` und 4 der 6 in `cc-knowledge` nicht, weil die Pfade relativ zum
      Arbeitsverzeichnis sind; skill-forge: vierzehn Regeln, sechs Evals, der Sync-Check
      ist G1 und fängt keine Änderung außerhalb von skill-forge. Commit.

### Task 12: Report

**Files:**
- Modify: `docs/superpowers/reports/skill-forge-report.md`

**Interfaces:**
- Consumes: `token:skill-outside-any-plugin-is-reported`
- Produces: (nichts Neues)

- [ ] **Step 1: Report** — Abschnitt zu dieser Runde mit den Zeichen vorher und nachher,
      `/context` vorher aus dem Protokoll, dem Ergebnis der Sync-Messung, den Eval-Läufen
      der Evals 1, 5 und 6 und der Evals von feature-spec und debug-ledger, und der
      Sektion „Was nicht gemessen wurde": `/context` nach dem Merge (misst der Nutzer),
      ungefahrene Evals, die Trefferquote des Routings, `Skill(...)`-Deny für
      Plugin-Skills. Commit.
