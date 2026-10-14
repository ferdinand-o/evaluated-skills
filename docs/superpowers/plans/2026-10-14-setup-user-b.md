<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# setup-user Abschnitt B Implementation Plan

**Goal:** `/setup-user check` meldet je Config-Verzeichnis die aktiven Plugins, ihre
SessionStart-Hooks, Namenskollisionen, `superpowers:`-Verweise und den Stand der
Abschaltbedingung aus Spec 20; `plan` schlägt das Plugin-Profil in `enabledPlugins` vor
und schaltet superpowers erst aus, wenn die Bedingung erfüllt ist und der Nutzer einen
gesetzten Wert ausdrücklich freigibt.

**Architecture:** Tier 1. Neues Skript `route_check.py` liest den installierten Bestand
(`plugins/installed_plugins.json` mit `installPath`, Cache-Fallback auch über
`CLAUDE_CODE_PLUGIN_CACHE_DIR`, `plugins/synced/`, `enabledPlugins`, `defaultEnabled`
aus dem Marketplace-Eintrag) und die Lückentabelle `references/superpowers-gaps.json`.
`inspect_config.py` und `verify_install.py` rufen es als Unterprozess auf (kein Import):
der Plan bekommt das Profil, `check.md` einen Abschnitt `## Plugins`, der informiert und
keine Abweichung zählt. `apply_config.py` mischt `enabledPlugins`.

**Gemessen vor dem Plan** (CLI 2.1.296, Wegwerf-Config-Verzeichnis):
`claude plugin install cc-dev@cc-skills` schreibt `"enabledPlugins":
{"cc-dev@cc-skills": true}` in die User-Settings; `installPath` zeigt auf
`plugins/cache/<marketplace>/<plugin>/<sha12>` mit der ganzen Repo-Kopie. Jedes per CLI
installierte Plugin hat also einen gesetzten Wert. Die Regel der Spec („ausdrücklich
gesetzte Werte dreht das Profil nie um") bleibt; der Plan führt sie als Konflikt, und
erst die Antwort `plugins_off` macht daraus einen Patch.

**Lesson aus Spec 23 und 24:** Fixtures, die ein geändertes Skript byte-gleich spiegeln
oder dessen Plan tragen, werden im selben Task neu erzeugt; Eval-Fixtures tragen keinen
Wert, der als Beispiel in der Skill steht.

**Tech Stack:** Python 3.11+ Stdlib.

**Spec:** `specs/Spec 21 – setup-user.md`

## Global Constraints

- **E1 — Tier 1, nur Stdlib, kein Import zwischen Skripten.** Docstrings nennen „Tier 1".
- **E2 — Gate-Sprache:** Plan zeigen G1, Hash in `apply` G2; `route_check.py` meldet nur.
- **E3 — Keine absoluten Pfade im Plan-Block**, damit der Hash orts- und
  zeilenendenneutral bleibt (`plan-format.md`).
- **E4 — Anti-Zeremonie unverändert:** `check` auf `su-aligned` meldet weiter „keine
  Abweichung"; ein fehlender Plugin-Ordner ist ein Hinweis „ungeprüft", keine Abweichung.
- **E5 — SKILL.md ≤ 150 Zeilen.**

## Skill-Struktur

```
skills/setup-user/
├── SKILL.md                          check und plan um Plugins ergänzt
├── references/routing.md             neu
├── references/superpowers-gaps.json  neu
├── references/settings-merge.md      enabledPlugins
├── scripts/route_check.py            neu
├── scripts/inspect_config.py         Profil im Plan
├── scripts/apply_config.py           enabledPlugins mischen
└── scripts/verify_install.py         Abschnitt Plugins in check.md

evals/setup-user/evals.json, evals/fixtures/su-plugins/
tests/test_setup_user_route.py, tests/test_setup_user_fixtures.py, tests/test_setup_user_apply.py
```

### Task 1: superpowers-gaps.json

**Files:**
- Create: `skills/setup-user/references/superpowers-gaps.json`
- Modify: `tests/test_setup_user_fixtures.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `token:"rules"`

- [x] **Step 1: Test schreiben** — `test_gaps_json_names_match_spec_20`: jede Zeile nennt
      in `superpowers` nur Namen aus der Lückentabelle in Spec 20, jede Tabellenzeile
      kommt vor, `status` aus der festen Menge, Zeilen mit `Regel` tragen `rules`.
- [x] **Step 2: Rot sehen.**
- [x] **Step 3: Schreiben** — `_meta` nach `docs/artifact-header.md`; Status nach dem
      Stand von heute: writing-plans → work-plan, test-driven-development → test-first,
      beide `vorhanden`; receiving-code-review und verification-before-completion
      `Regel` mit `rules: ["verification.md"]`.
- [x] **Step 4: Grün sehen.**
- [x] **Step 5: Commit.**

### Task 2: route_check.py

**Files:**
- Create: `skills/setup-user/scripts/route_check.py`
- Test: `tests/test_setup_user_route.py`

**Interfaces:**
- Consumes: `token:"rules"`
- Produces: `fn:main(argv)`, `fn:route_report(config_dir)`, `fn:render_markdown(report)`, `token:SessionStart-Hook`

- [x] **Step 1: Test schreiben** — `test_route_check_layouts_and_condition`: Fake-Plugins
      in Cache (`installPath` gültig und veraltet mit Cache-Fallback, auch über
      `CLAUDE_CODE_PLUGIN_CACHE_DIR`), lokalem Marketplace mit `skills`-Liste und
      `defaultEnabled`, und `synced/`; gemeldet werden SessionStart-Hook mit Matcher,
      `superpowers:`-Verweis, Kollision, alle drei Teile der Abschaltbedingung; `cc-dev`
      nie als engineering; ohne `plugins/` „ungeprüft"; abgeschaltete Plugins zählen nicht.
- [x] **Step 2: Rot sehen.**
- [x] **Step 3: Implementieren** — `route_report` liefert ein JSON-fähiges Dict ohne
      absolute Pfade; `render_markdown` den Abschnitt `## Plugins` mit Zeilen
      `<plugin> · SessionStart-Hook · <matcher>`; CLI `--config-dir`, `--json`,
      `--markdown`.
- [x] **Step 4: Grün sehen.**
- [x] **Step 5: Commit.**

### Task 3: references/routing.md

**Files:**
- Create: `skills/setup-user/references/routing.md`

**Interfaces:**
- Consumes: `fn:route_report(config_dir)`
- Produces: `token:Plugin-Profil`

- [x] **Step 1: Schreiben** — Plugin-Profil (Tabelle der Spec), Bestimmung aktiver
      Plugins, Layout auf der Platte samt Messung vom 2026-10-14, Abschaltbedingung mit
      Quelle je Teil, was `plugins_off` bedeutet.
- [x] **Step 2: Prüfen** — jedes genannte Feld steht in `route_check.py`. Commit.

### Task 4: Profil im Plan

**Files:**
- Modify: `skills/setup-user/scripts/inspect_config.py`
- Modify: `skills/setup-user/scripts/apply_config.py`
- Modify: `skills/setup-user/references/settings-merge.md`
- Modify: `skills/setup-user/references/plan-format.md`
- Modify: `tests/test_setup_user_apply.py`
- Modify: `evals/fixtures/su-planned/`
- Modify: `evals/fixtures/su-own-statusline/`

**Interfaces:**
- Consumes: `fn:main(argv)`, `token:Plugin-Profil`
- Produces: `token:plugins_off`, `token:enabledPlugins`

- [x] **Step 1: Test schreiben** — `test_profile_keeps_explicit_user_values`: gesetzter
      Wert bleibt und steht als Konflikt im Plan; mit `plugins_off` wird er zum Patch;
      ungesetzt und Bedingung erfüllt → `false`; Bedingung nicht erfüllt → superpowers
      bleibt mit Grund; engineering → `false` als Annahme; `apply` mischt
      `enabledPlugins`, fremde Schlüssel bleiben.
- [x] **Step 2: Rot sehen.**
- [x] **Step 3: Implementieren** — Unterprozess `route_check.py --json`; Feld `plugins`
      im Block; Abschnitt `## Plugins` in der Ansicht; `merge_settings` für
      `enabledPlugins`; References nachziehen; Pläne der Fixtures neu erzeugen.
- [x] **Step 4: Grün sehen**, alle `tests/test_setup_user_*.py`.
- [x] **Step 5: Commit.**

### Task 5: Plugins in check.md

**Files:**
- Modify: `skills/setup-user/scripts/verify_install.py`
- Modify: `tests/test_setup_user_verify.py`

**Interfaces:**
- Consumes: `fn:render_markdown(report)`
- Produces: `token:## Plugins`

- [x] **Step 1: Test schreiben** — `check.md` trägt den Abschnitt aus
      `route_check.py --markdown`; fehlt das Skript, steht dort „ungeprüft"; Plugin-Befunde
      zählen nicht als Abweichung.
- [x] **Step 2: Rot sehen.**
- [x] **Step 3: Implementieren** — Unterprozess mit Zeitgrenze, Ausgabe unverändert
      angehängt.
- [x] **Step 4: Grün sehen**, Anti-Zeremonie-Replay auf `su-aligned` weiter „keine
      Abweichung".
- [x] **Step 5: Commit.**

### Task 6: SKILL.md

**Files:**
- Modify: `skills/setup-user/SKILL.md`

**Interfaces:**
- Consumes: `token:plugins_off`, `token:## Plugins`
- Produces: `token:Abschaltbedingung`

- [ ] **Step 1: Ablauf** — plan zeigt das Plugin-Profil; ein Konflikt wird einmal
      gefragt und als `plugins_off` übergeben; check meldet Plugins; Verweis auf
      `references/routing.md`.
- [ ] **Step 2: Prüfen** — `wc -l` ≤ 150; `lint_skill.py skills/setup-user --base HEAD`
      ohne neuen Befund, `evals_due` notieren. Commit.

### Task 7: Evals

**Files:**
- Modify: `evals/setup-user/evals.json`
- Create: `evals/fixtures/su-plugins/`
- Modify: `tests/test_setup_user_fixtures.py`

**Interfaces:**
- Consumes: `token:SessionStart-Hook`, `token:Abschaltbedingung`
- Produces: `token:superpowers-sessionstart-is-reported`

- [ ] **Step 1: Fixture** — `su-plugins` wie `su-aligned`, dazu `cfg/plugins/` mit
      `installed_plugins.json` (veralteter `installPath`, Cache-Fallback), superpowers
      mit SessionStart-Hook und einer Skill, ein `cc-*`-Plugin.
- [ ] **Step 2: Eval** — `superpowers-sessionstart-is-reported`, Prompt
      „/setup-user check --config-dir ./cfg", Assertion `file_matches`
      `cfg/setup-user/check.md` auf `superpowers · SessionStart-Hook`, Diskriminator in
      `notes`.
- [ ] **Step 3: Test** — fünf Evals laden; das Replay von Eval 5 besteht; Eval 1 bleibt
      grün. Commit.

### Task 8: Nachbarn

**Files:**
- Modify: `specs/Spec 21 – setup-user.md`
- Modify: `specs/Spec 20 – plugin-split.md`

**Interfaces:**
- Consumes: `token:superpowers-sessionstart-is-reported`
- Produces: (nichts Neues)

- [ ] **Step 1: Spec 21** — Annahme zu `enabledPlugins` nach der Messung: Installation
      setzt `true`, deshalb Konflikt und `plugins_off`.
- [ ] **Step 2: Spec 20** — die Lückentabelle verweist auf `superpowers-gaps.json` als
      Quelle; Status writing-plans und test-driven-development dort, nicht hier.
- [ ] **Step 3: Prüfen** — Plugin-Zuordnung unverändert (setup-user in `cc-dev`), keine
      neuen Rückverweise, Routing unverändert; `pytest tests/test_marketplace.py`. Commit.

### Task 9: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `token:superpowers-sessionstart-is-reported`
- Produces: (nichts Neues)

- [ ] **Step 1: Abschnitt setup-user ergänzen** — gemessen ist nur das lokale Layout;
      Marketplace aus GitHub und `synced/` ungemessen; jeder per CLI installierte Wert
      gilt als gesetzt; `defaultEnabled` nur aus dem Marketplace-Eintrag; Abschnitt
      „Abschnitt B fehlt" entfernen. Commit.

### Task 10: Report

**Files:**
- Modify: `docs/superpowers/reports/setup-user-report.md`

**Interfaces:**
- Consumes: `token:superpowers-sessionstart-is-reported`
- Produces: (nichts Neues)

- [ ] **Step 1: Report** — Abschnitt B: was entstanden ist, Messung des Layouts, Eval 5
      mit `claude -p` mit und ohne Skill, die Evals 1 bis 4 erneut (`evals_due`):
      `anti-ceremony-check-on-aligned-config-changes-nothing`,
      `plan-is-default-and-writes-only-plan`, `apply-merges-existing-plan-and-backs-up`,
      `foreign-statusline-is-kept-while-hook-is-merged`; dazu
      „Was nicht gemessen wurde". `lint_skill.py skills/setup-user` ohne Befund. Commit.
