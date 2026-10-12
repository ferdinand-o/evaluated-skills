<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# setup-repo Implementation Plan (Abschnitt B — Kern)

**Goal:** Ein Repo lässt sich mit einem gezeigten, gehashten Plan so einrichten, dass
Claude dort einen belegten Verifikationsbefehl, eine knappe CLAUDE.md und aus dem Repo
geerntete Regeln vorfindet — in jeder Session, auch in der Cloud, ohne Plugin.

**Architecture:** Tier 1, nur Stdlib. Vier Werkzeuge, keines importiert ein anderes:
`scripts/detect_repo.py` schreibt `detect.json`, `scripts/harvest_rules.py` schreibt
`candidates.json`, `scripts/plan_repo.py` schreibt `plan.md` mit kanonischem JSON-Block
und Hash, `scripts/apply_repo.py` prüft den Hash, mischt, schreibt `apply.md` und mit
`--check` den Prüfbericht `check.md`. Ein Laufzeitskript, das ins Zielrepo kopiert wird:
`assets/runtime/verify_stop.py`, der optionale Stop-Hook. Dazu zwei References, das
CLAUDE.md-Gerüst, das Hook-Fragment, fünf Evals. Abschnitt C (Ledger, Zielregel,
Bereichs-Hook, Vorlagen-Messung) und D (Ziel-Reviewer) sind nicht Teil dieses Plans.

Vier Entscheidungen, die die Spec offen lässt:

- **check liegt in `apply_repo.py --check`.** Die Skill-Struktur nennt kein Skript, das
  `check.md` schreibt, Eval 1 bindet aber daran (bei setup-user dieselbe Lücke, dort
  erst in einer Fix-Runde geschlossen). check ist ein trockener apply gegen den Bestand:
  Wären alle Operationen des letzten Plans No-ops, heißt es „keine Abweichung".
- **Klassen über `plan_repo.py --classes '<json>'`.** Claude trägt je Kandidat
  `ableitbar`, `werkzeug` oder `regel` (mit optionalen `paths`) ein, ohne JSON von Hand
  zu bearbeiten. Ein Kandidat ohne Klasse steht im Plan als „offen".
- **`verify_stop.py` liest den Befehl aus der Zeile `Verifikation:` der CLAUDE.md.** Eine
  Quelle statt zwei; fehlt die Zeile oder heißt sie „keine", endet der Hook mit 0 und
  „ungeprüft — kein Verifikationsbefehl".
- **Die Kopfzeilen-Ausnahme kommt schon mit B,** für die Rules mit `paths`, die
  `plan_repo.py` erzeugt. Abschnitt D ergänzt sie um `assets/agents/reviewer.md`.

**Tech Stack:** Python 3.13 Stdlib für Skripte und Tests; `git` als Unterprozess;
Markdown für Skill, References, Evals; `bash -c` nur für den Starter-Test.

**Spec:** `specs/Spec 22 – setup-repo.md`

## Global Constraints

- **E1 — Tier 1, nur Stdlib** (Spec 00 §3). Kein Skript importiert ein anderes; den
  Plan-Hash berechnen `plan_repo.py` und `apply_repo.py` je selbst, ein Test hält beide
  gleich. Fehlt `git`, meldet `apply_repo.py` „ungeprüft — kein git" und schreibt nichts.
- **E2 — Gate-Sprache** (Spec 00 §4): G1 „verlangt" (Plan gezeigt und bestätigt), G2
  „meldet" (Hash und Budget in den Skripten), G3 nur für den Verifikations-Hook, der
  opt-in ist. Die Skill committet nie.
- **E3 — Kopfzeile je Artefakt** (`docs/artifact-header.md`): `plan.md`, `apply.md`,
  `check.md` und die neue CLAUDE.md in Zeile 1, erzeugte Rules mit `paths` in der ersten
  Zeile nach dem Frontmatter; `detect.json`, `candidates.json` und der Hook-Zustand per
  `_meta`. `.claude/settings.json` und `.claude/hooks/*.py` ohne Kopfzeile (Spec 22,
  Constraint 4).
- **E4 — SKILL.md ≤ 150 Zeilen**, Frontmatter `name`, `description` und
  `disable-model-invocation: true` (`CLAUDE_CODE_ONLY` enthält `setup-repo` schon).
- **E5 — Anti-Zeremonie-Eval ist Pflicht** (Spec 00 §2):
  `anti-ceremony-check-on-aligned-repo-changes-nothing`, gebunden an `check.md`.
- **E6 — Laufzeitskripte enden kontrolliert.** `verify_stop.py` endet mit 0 oder 2, nie
  mit einem Traceback; jede Meldung geht über `systemMessage`, nichts nur ins Debug-Log.
- **E7 — Pfade relativ zur Repo-Wurzel, LF-normalisiert, ohne `.claude/skills/`** im
  Block und in der Basis; der Hash kennt weder Ort noch HEAD noch Zeilenenden.
- **E8 — Nie ins echte Home.** Tests setzen `CLAUDE_CONFIG_DIR`, `HOME` und
  `USERPROFILE` auf ein Temp-Verzeichnis; Plugin-IDs kommen aus Fake-Config-Verzeichnissen.

## Skill-Struktur

```
skills/setup-repo/
├── SKILL.md
├── references/plan-format.md, rules-harvest.md
├── assets/CLAUDE.md.tmpl
├── assets/runtime/verify_stop.py
├── assets/hooks/verify-stop.json
└── scripts/detect_repo.py, harvest_rules.py, plan_repo.py, apply_repo.py

evals/setup-repo/evals.json
evals/fixtures/sr-aligned/, sr-fresh/, sr-notests/, sr-planned/, sr-tampered/
tests/test_setup_repo_detect.py, _harvest.py, _plan.py, _apply.py, _verify_stop.py, _fixtures.py
docs/artifact-header.md, .claude-plugin/marketplace.json
```

### Task 1: References

**Files:**
- Create: `skills/setup-repo/references/plan-format.md`
- Create: `skills/setup-repo/references/rules-harvest.md`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `token:setup-repo-plan`, `token:werkzeug`

- [x] **Step 1: plan-format.md** — Aufbau von `.skills/cache/setup-repo/plan.md`
      (Kopfzeile, Ansicht, Codeblock mit Info-String `json setup-repo-plan`); Felder des
      Blocks: `schema`, `verification` (`command`, `source`, `derived`), `candidates`
      (je `id`, `text`, `source`, `class`, `paths`), `operations` (je `path` relativ zur
      Repo-Wurzel, `action` aus `create`, `append`, `merge-json`, `copy`, `gitignore`),
      `options` (`verify_hook`, `deny_secrets`), `plugins` (je ID und `true`/`false`),
      `budget`, `base` (je Pfad SHA-256 des LF-normalisierten Bestands, `null` wenn
      fehlend, ohne `.claude/skills/`), `hash`; Hash = SHA-256 über
      `json.dumps(block ohne hash, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`.
      Mischregeln für `.claude/settings.json` (Listen vereinigt, fremde Schlüssel
      bleiben, eigener Hook erkannt am Suffix `.claude/hooks/verify_stop.py`) und
      `.claude/settings.local.json` (nur `enabledPlugins`).
- [x] **Step 2: rules-harvest.md** — Quellen der Kandidaten (Linter-, Formatter- und
      Typprüfer-Konfiguration, `.editorconfig`, `CONTRIBUTING*`, Commit-Betreffs der
      letzten 50 Commits); die drei Klassen `ableitbar` (fällt weg), `werkzeug` (keine
      Regelzeile, im Bericht als Werkzeug) und `regel` (mit `paths`, wo sie nur einen
      Teil betrifft); Aufruf `plan_repo.py --classes`; je Regel die Quelle; Budget 150
      immer geladene Zeilen samt Importen.
- [x] **Step 3: Prüfen** — beide Dateien unter 200 Zeilen, ohne Kopfzeile wie alle
      References im Repo, die Tokens `setup-repo-plan` und `werkzeug` wörtlich. Commit.

### Task 2: detect_repo.py

**Files:**
- Create: `skills/setup-repo/scripts/detect_repo.py`
- Test: `tests/test_setup_repo_detect.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `fn:detect(repo_root, config_dir)`, `token:detect.json`

- [x] **Step 1: Tests schreiben** — `test_detect_python_ts_delphi_frontend_none`
      (Mini-Repos in `tmp_path`: Python mit `pyproject.toml` und ruff, TypeScript mit
      `package.json`-Scripts und React, Delphi über `.dproj`, leeres Repo; Runner-Ziele
      aus `Makefile`, `package.json`, `pyproject.toml`, `justfile`; Tests vorhanden ja
      oder nein; alle drei CLAUDE-Dateien und `AGENTS.md`; Projekt-Skills unter
      `.claude/skills/`) und `test_detect_plugin_ids` (Fake-Config-Verzeichnis mit
      `plugins/installed_plugins.json` und `installPath`, dessen Manifest die Skills je
      Plugin nennt; ein Plugin unter `plugins/synced/`; kein Eintrag → leere Liste).
- [x] **Step 2: Rot sehen** — `pytest tests/test_setup_repo_detect.py`.
- [x] **Step 3: Implementieren** — `detect` liest nur, ruft höchstens `git rev-parse` auf;
      `main` schreibt `.skills/cache/setup-repo/detect.json` mit `_meta`; Config-Verzeichnis
      aus `--config-dir`, sonst `CLAUDE_CONFIG_DIR`, sonst `~/.claude`; Plugin-IDs als
      `<name>@<marketplace>` oder `<name>@synced` mit ihren Skill-Namen.
- [x] **Step 4: Grün sehen**, volle Suite.
- [x] **Step 5: Commit.**

### Task 3: harvest_rules.py

**Files:**
- Create: `skills/setup-repo/scripts/harvest_rules.py`
- Test: `tests/test_setup_repo_harvest.py`

**Interfaces:**
- Consumes: `token:detect.json`
- Produces: `fn:harvest(repo_root, detect)`

- [ ] **Step 1: Test schreiben** — `test_harvest_marks_tool_rules`, erster Teil:
      `line-length = 100` unter `[tool.ruff]` in `pyproject.toml` wird ein Kandidat mit
      Quelle `pyproject.toml` und dem Hinweis, dass ruff ihn prüft; dazu ein Kandidat aus
      `CONTRIBUTING.md` und einer aus wiederkehrenden Commit-Präfixen; IDs stabil
      (`c1`, `c2`, … in Quellreihenfolge).
- [ ] **Step 2: Rot sehen** — `pytest tests/test_setup_repo_harvest.py`.
- [ ] **Step 3: Implementieren** — Kandidaten aus den Quellen in `rules-harvest.md`;
      `main` liest `detect.json`, schreibt `candidates.json` mit `_meta`; keine Klasse —
      die trägt Claude ein.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 4: verify_stop.py

**Files:**
- Create: `skills/setup-repo/assets/runtime/verify_stop.py`
- Create: `skills/setup-repo/assets/hooks/verify-stop.json`
- Test: `tests/test_setup_repo_verify_stop.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `fn:run_stop(payload, repo_root)`, `fn:selftest(repo_root)`

- [ ] **Step 1: Tests schreiben** — `test_verify_stop_counts_and_missing_tool` (Mini-Repo
      mit CLAUDE.md-Zeile `Verifikation: \`python -c "..."\``: grün → 0; rot → 2 mit
      Grund auf stderr bis zum dritten Mal je `session_id`, danach 0 mit `systemMessage`
      „rot nach drei Versuchen"; grün setzt den Zähler zurück; fehlendes Programm → 0
      mit `systemMessage` „ungeprüft — … fehlt"; keine Zeile → 0 mit „ungeprüft — kein
      Verifikationsbefehl"; `--selftest` startet den Befehl nicht) und
      `test_launcher_command_runs` (das Kommando aus `verify-stop.json` läuft unter
      `bash -c` mit `CLAUDE_PROJECT_DIR` auf dem Mini-Repo, einmal mit `python3` im
      `PATH`, einmal mit nur `python`).
- [ ] **Step 2: Rot sehen** — `pytest tests/test_setup_repo_verify_stop.py`.
- [ ] **Step 3: Implementieren** — stdin als Bytes mit UTF-8-Ersetzung; Repo-Wurzel aus
      `CLAUDE_PROJECT_DIR`; Zustand `.skills/cache/setup-repo/verify-stop.json` mit
      `_meta`, atomar geschrieben; Timeout 300 Sekunden; jede Ausnahme gefangen. Fragment
      mit `Stop`-Hook und dem Starter
      `command -v python3 >/dev/null 2>&1 && exec python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/verify_stop.py" || exec python "$CLAUDE_PROJECT_DIR/.claude/hooks/verify_stop.py"`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 5: Assets

**Files:**
- Create: `skills/setup-repo/assets/CLAUDE.md.tmpl`

**Interfaces:**
- Consumes: `token:setup-repo-plan`
- Produces: `token:Verifikation:`

- [ ] **Step 1: Schreiben** — Gerüst ≤ 40 Zeilen: Kopfzeile, Platz für `@AGENTS.md`,
      Zeile `Verifikation: …` mit den beiden Formen „`<befehl>`" und „keine — ungeprüft",
      Abschnitt für Regeln ohne `paths`, Verweis auf `.claude/rules/`; Platzhalter in
      doppelten geschweiften Klammern, wie in setup-user.
- [ ] **Step 2: Prüfen** — `wc -l`; `lint_skill.py skills/setup-repo` ohne Befund für
      `asset-headers`. Commit.

### Task 6: plan_repo.py

**Files:**
- Create: `skills/setup-repo/scripts/plan_repo.py`
- Test: `tests/test_setup_repo_plan.py`
- Modify: `tests/test_setup_repo_harvest.py`

**Interfaces:**
- Consumes: `fn:detect(repo_root, config_dir)`, `fn:harvest(repo_root, detect)`, `token:Verifikation:`, `token:werkzeug`
- Produces: `fn:build_plan(repo_root, detect, candidates, options)`, `fn:plan_hash(block)`, `fn:render_plan(block)`, `fn:choose_verification(detect)`

- [ ] **Step 1: Tests schreiben** — `test_budget_counts_unscoped_rules_and_imports`,
      `test_plan_hash_is_path_head_and_eol_neutral` (dasselbe Repo an zwei Orten, mit
      verschiedenem HEAD, mit CRLF-Bestand und installierter Skill → gleicher Hash),
      `test_agents_md_is_imported`, `test_choose_verification` (`make check` vor
      zusammengesetztem `make lint && make test`; Delphi abgeleitet und nicht in
      `permissions.allow`; nichts → „keine — ungeprüft" mit Verweis auf
      testing-strategy), `test_plan_enables_plugins_per_repo` (Frontend → `cc-ui` an;
      Plugin mit Projekt-Kopie unter `.claude/skills/` → aus; keine ID → keine Operation
      und „ungeprüft — Plugin-ID nicht gefunden"), `test_plan_writes_only_cache`; in
      `tests/test_setup_repo_harvest.py` den zweiten Teil von
      `test_harvest_marks_tool_rules`: Klasse `werkzeug` ergibt keine Regelzeile, aber
      eine Kandidatenzeile mit „Werkzeug".
- [ ] **Step 2: Rot sehen** — `pytest tests/test_setup_repo_plan.py tests/test_setup_repo_harvest.py`.
- [ ] **Step 3: Implementieren** — `--classes`, `--with-verify-hook`, `--deny-secrets`;
      Operationen nach `references/plan-format.md`; Ansicht mit Diff, je Kandidat
      „Kandidat · Quelle · Klasse", Budget, abwählbare Hooks, Hinweis, dass
      `.skills/cache/` bis `apply` unversioniert sichtbar ist; Budget > 150 als Befund.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 7: apply_repo.py

**Files:**
- Create: `skills/setup-repo/scripts/apply_repo.py`
- Test: `tests/test_setup_repo_apply.py`

**Interfaces:**
- Consumes: `fn:build_plan(repo_root, detect, candidates, options)`, `fn:plan_hash(block)`, `fn:selftest(repo_root)`
- Produces: `fn:apply_plan(repo_root, plan_path)`, `fn:canonical_hash(block)`

- [ ] **Step 1: Tests schreiben** — `test_hash_functions_agree`,
      `test_apply_refuses_dirty_target_and_changed_plan` (uncommittete versionierte
      Zieldatei oder geänderter Block → Abbruch mit Grund in `apply.md`, keine andere
      Datei berührt; unversionierter `.claude/skills/` stört nicht),
      `test_apply_backs_up_local_settings_and_ignores_them`,
      `test_apply_merges_existing_settings` (vorhandene `hooks.Stop` und `permissions`
      bleiben, Listen vereinigt, kein doppelter eigener Eintrag), `test_apply_is_idempotent`,
      `test_apply_never_commits` (HEAD unverändert).
- [ ] **Step 2: Rot sehen** — `pytest tests/test_setup_repo_apply.py -k apply`.
- [ ] **Step 3: Implementieren** — Block lesen, Hash und Basis prüfen, `git status
      --porcelain -z` für versionierte Ziele, Backups unter
      `.skills/cache/setup-repo/backups/<JJJJMMTT-hhmmss>/`, Hook-Skripte nach
      `.claude/hooks/` kopieren, `.claude/settings.json` zuletzt; danach je Hook die
      Probe (`verify_stop.py --selftest`); `apply.md` mit Kopfzeile und „angewendet"
      oder dem Abbruchgrund, in jedem Fall.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 8: check in apply_repo.py

**Files:**
- Modify: `skills/setup-repo/scripts/apply_repo.py`
- Modify: `tests/test_setup_repo_apply.py`

**Interfaces:**
- Consumes: `fn:apply_plan(repo_root, plan_path)`
- Produces: `fn:check_repo(repo_root)`, `token:keine Abweichung`

- [ ] **Step 1: Tests schreiben** — `test_check_aligned_reports_no_deviation` (nach
      `apply` ändert `--check` nur `check.md`, Text „keine Abweichung"),
      `test_check_reports_drift` (geänderte CLAUDE.md, fehlendes Hook-Skript, Budget
      überschritten → je eine Abweichung), `test_check_without_plan_is_unverified`
      (klassenabhängige Punkte „ungeprüft — kein Plan"), `test_check_keeps_cc_skills_switch`
      (`cc-dev` in der committeten Datei ist keine Abweichung).
- [ ] **Step 2: Rot sehen** — `pytest tests/test_setup_repo_apply.py -k check`.
- [ ] **Step 3: Implementieren** — `--check`: Hash des letzten Plans prüfen, jede
      Operation trocken gegen den Bestand anwenden, Budget, Hook-Probe; schreibt nur
      `check.md` mit Kopfzeile.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 9: SKILL.md

**Files:**
- Create: `skills/setup-repo/SKILL.md`

**Interfaces:**
- Consumes: `fn:detect(repo_root, config_dir)`, `fn:build_plan(repo_root, detect, candidates, options)`, `fn:apply_plan(repo_root, plan_path)`, `fn:check_repo(repo_root)`
- Produces: `token:Belegt oder ungeprüft`

- [ ] **Step 1: Frontmatter** — `name`, Description mit Triggern und Abgrenzung gegen
      setup-user und testing-strategy, ohne `<…>`, `disable-model-invocation: true`.
- [ ] **Step 2: Rumpf** — Eiserne Regel, Modi plan (Default), apply, check mit den
      Aufrufen über `${CLAUDE_SKILL_DIR}`, Klassifikation per `--classes`, Plugins je
      Repo, Verifikations-Hook opt-in, Contract mit „Belegt oder ungeprüft",
      Anti-Rationalisierung, Abgrenzung mit **testing-strategy** und **review-context**
      fett, setup-user unfett.
- [ ] **Step 3: Prüfen** — `wc -l` unter 150; `lint_skill.py skills/setup-repo` ohne
      Befund außer `report-section`, `routing`, `neighbors` und `plugin-membership`, die
      Task 11 bis 13 schließen. Commit.

### Task 10: Evals

**Files:**
- Create: `evals/setup-repo/evals.json`
- Create: `evals/fixtures/sr-aligned/`
- Create: `evals/fixtures/sr-fresh/`
- Create: `evals/fixtures/sr-notests/`
- Create: `evals/fixtures/sr-planned/`
- Create: `evals/fixtures/sr-tampered/`
- Create: `tests/test_setup_repo_fixtures.py`

**Interfaces:**
- Consumes: `token:Belegt oder ungeprüft`, `token:keine Abweichung`
- Produces: `token:anti-ceremony-check-on-aligned-repo-changes-nothing`

- [ ] **Step 1: Fixtures** — je `fixture.json` mit `"git": true`; `sr-fresh` mit
      `Makefile`-Ziel `check` und `line-length = 100` in `pyproject.toml`; `sr-notests`
      ohne Runner und Tests; `sr-planned` mit einem Plan, den `plan_repo.py` erzeugt hat;
      `sr-tampered` mit demselben Plan, im Block nach dem Hashen eine Zeile geändert;
      `sr-aligned` nach `apply` dieses Plans, mit dem Plan und ohne offene Kandidaten.
      Abschnitt B: keine Zielregel, kein Ledger, kein Bereichs-Hook in den Fixtures.
- [ ] **Step 2: Evals** — `anti-ceremony-check-on-aligned-repo-changes-nothing`,
      `plan-from-repo-writes-only-report`, `plan-without-tests-says-unverified`,
      `apply-executes-plan-faithfully`, `apply-refuses-tampered-plan` mit den Assertions
      der Spec, ohne die drei `file_unchanged` auf Zielregel, Bereichs-Hook und Ledger in
      Eval 1 und ohne `goal_scope` in Eval 4 (Spec 22, Evals: Abschnitt C ergänzt sie);
      je die Diskriminator-Frage in `notes`.
- [ ] **Step 3: Schema-Test** — `load_evals` lädt fünf Evals;
      `test_fixture_plans_are_current` (Blöcke in `sr-planned`, `sr-aligned` und
      `sr-tampered` gleichen neu erzeugten, `sr-tampered` bis auf die eine Änderung;
      Bestand in `sr-aligned` gleich dem Ergebnis von `apply`) und
      `test_replayed_eval_passes_its_own_assertions` (jeder Eval mit den Skripten
      nachgespielt, gemessen mit evalkit). Commit.

### Task 11: Nachbarn

**Files:**
- Modify: `skills/testing-strategy/SKILL.md`
- Modify: `skills/review-context/SKILL.md`
- Modify: `skills/feature-spec/SKILL.md`
- Modify: `.claude/skills/testing-strategy/`
- Modify: `.claude/skills/review-context/`
- Modify: `.claude/skills/feature-spec/`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `specs/Spec 00 – skill-foundation.md`
- Modify: `README.md`
- Modify: `docs/artifact-header.md`

**Interfaces:**
- Consumes: `token:Belegt oder ungeprüft`
- Produces: (nichts Neues)

- [ ] **Step 1: Abgrenzungen** — je ein Halbsatz mit dem Wort setup-repo in
      testing-strategy, review-context und feature-spec; handoff kommt mit Abschnitt C
      (`docs/goals.md`). `python scripts/sync_skills.py` und `--check`; `lint_skill.py
      --base HEAD` je Skill ohne neuen Befund.
- [ ] **Step 2: Plugin-Zuordnung** — `./skills/setup-repo` in die `skills`-Liste von
      `cc-dev`; die Tabelle in `scripts/sync_skills.py` bleibt unverändert;
      `pytest tests/test_marketplace.py`.
- [ ] **Step 3: Matrix und Kopfzeile** — Spec 00 §5 und README je eine Zeile setup-repo,
      README setup-repo in der Liste von `cc-dev`; in `docs/artifact-header.md` die
      Begründete Ausnahme „Kopfzeile nach dem Frontmatter" für Rules mit `paths` aus
      `skills/setup-repo/scripts/plan_repo.py` und den Satz über die Zahl der Ausnahmen
      nachziehen. `lint_skill.py skills/setup-repo` meldet `routing`, `neighbors` und
      `plugin-membership` grün. Commit.

### Task 12: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `token:anti-ceremony-check-on-aligned-repo-changes-nothing`
- Produces: (nichts Neues)

- [ ] **Step 1: Abschnitt** — `## setup-repo`: Starter unter Windows ungemessen (Platzhalter
      `python3` aus dem Store), `-p` nutzt keine Projekt-Freigaben, `--bare` lädt weder
      CLAUDE.md noch Hooks, Plugin-IDs unter `plugins/synced/` beim Nutzer nicht
      vorhanden, Klassifikation nur über Eval 2 gemessen, Abschnitt C und D fehlen.
      Commit.

### Task 13: Report

**Files:**
- Create: `docs/superpowers/reports/setup-repo-report.md`

**Interfaces:**
- Consumes: `token:anti-ceremony-check-on-aligned-repo-changes-nothing`
- Produces: (nichts Neues)

- [ ] **Step 1: Report** — was entstanden ist, Testzahl, Eval-Läufe außerhalb des Harness
      oder „ungefahren" mit Grund, Ende-zu-Ende-Lauf auf einer Kopie dieses Repos, und
      die Sektion „Was nicht gemessen wurde": Windows-Starter, Läufe mit
      `--without-skill`, Abschnitt C und D. `lint_skill.py skills/setup-repo` ganz
      sauber. Commit.
