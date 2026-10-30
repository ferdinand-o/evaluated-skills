<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# subagent-dev-checkpoints Implementation Plan

**Goal:** subagent-dev reviewt einen Plan nicht mehr nach jeder Task, sondern an
Prüfpunkten, die `generate` aus `Produces`/`Consumes` und Risikopfaden setzt; jede Task
läuft mit einem begründeten Modell, eine Vorleistung startet keinen Abnehmer, bevor ihre
Signaturen geprüft sind — und die Ersparnis an Review-Tokens ist an gemergter Historie
gemessen.

**Architecture:** Tier 1, aller Code in `skills/subagent-dev/scripts/plan_to_tasks.py`
(Stdlib). Neu: Abnehmer, Modellregeln M0–M3, Prüfpunkte C1–C4 in `generate` (über den
ganzen Plan, auch mit `--tasks`), `consumer_check` und `hints` in `verify`, die Unterbefehle
`checkpoint init|status|mark`, `fix-task` und `log`. Das Review am Prüfpunkt ist
`/code-review` über den Bereich seit dem letzten Prüfpunkt, weil deep-review (Spec 26)
pausiert ist; die Übergabe sagt dann „Review ohne Abdeckungsnachweis". Dispatch mit Modell,
Haiku-Vertragsprüfung, Review und Fix verlangt die SKILL.md (G1).

**Lesson aus dem Bau von Spec 26:** Die Task-Dateien trugen nur die Step-Titel, der Inhalt
musste von Hand nachgereicht werden. Task 1 behebt das zuerst, damit alle weiteren
Dispatches dieses Plans die volle Task-Datei bekommen. Und: Eine Fixture mit `commits` braucht
mindestens eine Datei neben `fixture.json`, sonst bricht `evalkit.workspace` ab.

**Tech Stack:** Python 3.11+ Stdlib für Skript und Tests; Markdown für Skill, References,
Evals; `claude -p` für Basislinie und Report.

**Spec:** `specs/Spec 27 – subagent-dev-checkpoints.md`

## Global Constraints

- **E1 — Tier 1, nur Stdlib.** `plan_to_tasks.py` bleibt eine Datei, importiert nichts
  außerhalb der Stdlib; Aufruf in der SKILL.md über `${CLAUDE_SKILL_DIR}/scripts/`.
- **E2 — Gate-Sprache:** Modell, Prüfpunkte, Abnehmer-Check, Hinweise und Größen-Trigger
  fällt bzw. meldet das Skript (G2); Dispatch mit Modell, Vertragsprüfung, Review und Fix
  verlangt die SKILL.md (G1). Kein Hook.
- **E3 — Kopfzeile je Artefakt:** `gate.json`, `review-state.json`, `checkpoint.json` per
  `_meta`; `runlog.jsonl` mit `_meta` in Zeile 1; Task-Dateien und `contract-task-<N>.md`
  mit Kopfzeile.
- **E4 — SKILL.md ≤ 150 Zeilen** (heute 123); Kostentabelle und die Zeile „Review pro Task
  ist zu teuer" entfallen.
- **E5 — Anti-Zeremonie-Eval** `anti-ceremony-mini-plan-gets-only-final-checkpoint`,
  gebunden an `file_matches` auf `gate.json`.
- **E6 — Abwärtskompatibel:** alle bisherigen Schlüssel in `gate.json` mit unveränderten
  Werten, Schema bleibt 1; je Task die Reihenfolge `id`, `title`, `files`, `files_unknown`,
  `interfaces_unknown`, `model`, `model_reason`, `consumers`; Prüfpunkte mit `kind`, `task`,
  `profile`, `reasons`.
- **E7 — Ein übersprungener Check meldet nie Erfolg:** `unchecked` macht `verify` höchstens
  `unverified`; ohne `review-state.json` ist ein Prüfpunkt fällig.
- **E8 — Grenzwerte als Konstanten** mit den Werten der Spec: `SIZE_TRIGGER_LINES = 400`,
  `BREADTH_MIN_FILES = 5`, `CONSUMERS_FOR_OPUS = 2`, `MAX_FIX_ROUNDS = 2`, dazu die
  Risikowörter und Pflicht-Titel als Tupel.

## Skill-Struktur

```
skills/subagent-dev/
├── SKILL.md
├── references/checkpoints.md, contract-check.md, task-file.md, merge-protocol.md
└── scripts/plan_to_tasks.py

skills/work-plan/references/task-patterns.md, skills/impl-plan/references/task-patterns.md
skills/test-first/SKILL.md
evals/subagent-dev/evals.json
evals/fixtures/plan-fanout/, plan-fanout-override/, plan-fanout-dispatched/, cp-size/
tests/test_subagent_dev_plan_to_tasks.py, tests/test_skills_lint.py
docs/known-limits.md, docs/superpowers/reports/subagent-dev-report.md
.claude/skills/subagent-dev/, .claude/skills/impl-plan/
```

### Task 1: Step-Text in der Task-Datei

**Files:**
- Modify: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Modify: `skills/subagent-dev/references/task-file.md`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`
- Modify: `.claude/skills/subagent-dev/`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `fn:parse_step_texts(block)`

- [ ] **Step 1: Test schreiben** — `test_task_file_keeps_step_text`: Akzeptanzkriterien
      tragen je Step den Titel und den Text bis zum nächsten Step, auch über mehrere
      eingerückte Zeilen; ein Step ohne Text bleibt eine Zeile; der JSON-Block ist
      unverändert.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_subagent_dev_plan_to_tasks.py -k keeps_step_text`.
- [ ] **Step 3: Implementieren** — `parse_step_texts` liefert je Step Titel und Text;
      `render_task_file` schreibt beides; `_parse_steps` bleibt für den Lint unverändert.
      `task-file.md` beschreibt die neue Form. `python scripts/sync_skills.py`.
- [ ] **Step 4: Grün sehen**, volle Suite; `sync_skills.py --check` sauber.
- [ ] **Step 5: Commit.**

### Task 2: Basislinie auf gemergter Historie

Die Spec misst die Basislinie an drei fertigen Plänen, deren Tasks als eigene Commits
`<skill> Task N: …` vorliegen, statt drei Pläne neu zu bauen. Kostendeckel: höchstens
30 Review-Läufe.

**Files:**
- Modify: `docs/superpowers/reports/subagent-dev-report.md`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `token:Basislinie Spec 27`, `token:Was nicht gemessen wurde`

- [ ] **Step 1: Pläne wählen** — drei Pläne unter `docs/superpowers/plans/`, deren Tasks
      sich eindeutig Commits zuordnen lassen (`git log --format='%h %s' | grep "Task "`), mit
      zusammen höchstens 30 Tasks; je Task der Bereich `<commit>^..<commit>`.
- [ ] **Step 2: Messen** — je Task `claude -p "/code-review <bereich>" --output-format json`
      in einem frischen Worktree mit `--detach` am Commit; notiert werden `total_cost_usd`,
      Tokens aus `usage` und die Funde (Datei, Zeile, Kurzfassung). Rohantworten unter
      `.skills/cache/`, nicht im Repo.
- [ ] **Step 3: Report** — Abschnitt „Basislinie Spec 27" mit Tabelle je Plan und Task,
      Summen je Plan; Abschnitt „## Was nicht gemessen wurde" ergänzt (Fix-Kreislauf nicht
      wiederholt, Stufe von `/code-review` headless). Commit.

### Task 3: Abnehmer

**Files:**
- Modify: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: `fn:parse_step_texts(block)`
- Produces: `fn:consumers_of(tasks)`, `fn:is_mandatory_title(title)`

- [ ] **Step 1: Test schreiben** — `test_consumers_exclude_mandatory_tasks`: Abnehmer sind
      spätere Tasks, deren `Consumes` ein `Produces`-Symbol nennt (Logik von
      `_interface_dependency`) mit der erwarteten Arity; `Verifikation`, `Evals`,
      `Nachbarn`, `known-limits`, `Report` und `Report — …` zählen nicht, „Report und
      Runner-CLI" zählt; `interfaces_unknown` hat keine Abnehmer.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_subagent_dev_plan_to_tasks.py -k consumers_exclude`.
- [ ] **Step 3: Implementieren** — `consumers_of` liefert je Task-ID eine Liste
      `{task, symbols}`; Pflicht-Titel als Tupel nach E8.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 4: Modell je Task

**Files:**
- Modify: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: `fn:consumers_of(tasks)`
- Produces: `fn:choose_model(task, consumers)`, `fn:risk_words(path)`

- [ ] **Step 1: Test schreiben** — `test_model_rules`: M0 schlägt M1 bis M3; M0 nur direkt
      unter dem Titel vor `**Files:**`; M1 ab zwei Abnehmern; M2 trifft `auth_service.py`,
      `LoginForm.pas`, `x.sql`, nicht `authors.py`; M3 ab fünf `Create`/`Modify`-Pfaden
      ohne `Test`-Zeilen; ungültiger Wert hinter `**Modell:**` → Lint-Befund und Rückfall
      auf M1 bis M3; `model_reason` mit den Texten der Spec.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_subagent_dev_plan_to_tasks.py -k model_rules`.
- [ ] **Step 3: Implementieren** — `parse_plan` liest die Modellzeile in `PlanTask`;
      `risk_words` zerlegt an `/`, `_`, `-`, `.` und Großbuchstaben; der Lint meldet den
      ungültigen Wert.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 5: Prüfpunkte und gate.json

**Files:**
- Modify: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Modify: `skills/subagent-dev/references/task-file.md`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: `fn:consumers_of(tasks)`, `fn:choose_model(task, consumers)`
- Produces: `fn:place_checkpoints(tasks, consumers, gate)`

- [ ] **Step 1: Tests schreiben** — `test_checkpoint_placement` (C1 vor dem ersten
      Abnehmer; C2 nach Risikotask; C3 nur bei `parallel`, `task` = höchste ID der Gruppe;
      C4 vor der Verifikations-Task oder am Ende mit `task: null`; Zusammenfallen mit allen
      Gründen und höherem Profil); `test_rules_use_whole_plan_with_tasks_filter` (`--tasks
      3,4` ändert weder Modell noch Abnehmer noch Prüfpunkte; C3 aus dem Gate über den
      ganzen Plan); `test_gate_json_keys_backward_compatible` (bisherige Schlüssel und Werte
      an den bestehenden Fixtures, neue Schlüssel in der Reihenfolge aus E6).
- [ ] **Step 2: Rot sehen** — `pytest tests/test_subagent_dev_plan_to_tasks.py -k "checkpoint_placement or whole_plan or backward_compatible"`.
- [ ] **Step 3: Implementieren** — `write_tasks` rechnet Regeln über den ganzen Plan und
      filtert erst danach; Task-Datei mit Abschnitt „Modell und Abnehmer", Maschinenblock
      mit `model` und `consumers`; `task-file.md` beschreibt beides.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 6: checkpoint init, status, mark

**Files:**
- Modify: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: `fn:place_checkpoints(tasks, consumers, gate)`
- Produces: `fn:checkpoint_init(repo, base)`, `fn:checkpoint_status(repo, after_task, tests_red)`, `fn:checkpoint_mark(repo, commit, run, tasks)`

- [ ] **Step 1: Test schreiben** — `test_checkpoint_command`: init löst Tags auf und
      schreibt `runs: []`; status nimmt Refs aus `review-state.json`; fällig an geplantem
      Prüfpunkt, bei `group` nach der höchsten ID, ab `SIZE_TRIGGER_LINES`, mit
      `--tests-red`, sonst nicht; Binärdateien zählen 0 und stehen in `binary_files`;
      `.skills/` zählt nicht; ohne `review-state.json` fällig ohne Bereich; mark setzt Commit
      und hängt den Lauf an `runs`, `--run none` hängt nichts an; am finalen Prüfpunkt
      stehen alle Läufe in `since_runs`.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_subagent_dev_plan_to_tasks.py -k checkpoint_command`.
- [ ] **Step 3: Implementieren** — Unterbefehl `checkpoint` mit `init --base`,
      `status --after-task [--tests-red]`, `mark --commit --run --tasks`; Zählung per
      `git diff --numstat <last_reviewed>..HEAD -- . ':(exclude).skills'`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 7: verify mit consumer_check

**Files:**
- Modify: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: `fn:consumers_of(tasks)`
- Produces: `fn:arity_matches(node, expected)`, `fn:check_consumers(worktree, allowlist, consumers)`

- [ ] **Step 1: Test schreiben** — `test_verify_consumer_check`: `present`, `missing`,
      `arity_mismatch`, `ambiguous`; Default-Parameter, posonly und `*args` passen,
      kwonly ohne Default passt nicht; ohne Arity nur Präsenz; Nicht-Python → `unchecked`
      und Verdikt höchstens `unverified`; Task-Datei ohne `consumers` → `unchecked`; der
      `Produces`-Check nutzt `arity_matches`, und das bestehende Eval zur
      Signaturabweichung bleibt `fail`.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_subagent_dev_plan_to_tasks.py -k consumer_check`.
- [ ] **Step 3: Implementieren** — `consumer_check` in der Form von `produces`;
      `missing`, `arity_mismatch`, `ambiguous` → `fail`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 8: verify mit hints

**Files:**
- Modify: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: `fn:check_consumers(worktree, allowlist, consumers)`
- Produces: `fn:collect_hints(worktree, base)`

- [ ] **Step 1: Test schreiben** — `test_verify_hints`: Platzhalter (Muster des Plan-Lints)
      und `print(`, `console.log(`, `Writeln(`, `OutputDebugString(` nur in hinzugefügten
      Zeilen; `sofort-grün` und fehlendes Log aus `.skills/cache/test-first/log.md`;
      Verdikt unverändert.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_subagent_dev_plan_to_tasks.py -k verify_hints`.
- [ ] **Step 3: Implementieren** — `hints` als Liste `{kind, path, line, text}` im
      Ergebnis von `verify`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 9: fix-task

**Files:**
- Modify: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: `fn:checkpoint_status(repo, after_task, tests_red)`
- Produces: `fn:fix_task_from_verdicts(verdicts_path, out_dir)`

- [ ] **Step 1: Test schreiben** — `test_fix_task_from_verdicts`: Allowlist aus `path` und
      `related` der Funde mit `bestätigt`/`plausibel`; `widerlegt` und `offen` nicht;
      Akzeptanz je Fund „behoben und mit Test belegt"; Task-Datei mit Kopfzeile und
      Maschinenblock.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_subagent_dev_plan_to_tasks.py -k fix_task`.
- [ ] **Step 3: Implementieren** — `fix-task --verdicts <datei> [--out-dir]`; liest das
      Format von `verdicts.jsonl` aus Spec 26 und eine Liste von Funden aus `/code-review`
      (`file`, `line`, `summary`) für den Ersatzpfad.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 10: log

**Files:**
- Modify: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: `fn:fix_task_from_verdicts(verdicts_path, out_dir)`
- Produces: `fn:append_log(path, entry)`

- [ ] **Step 1: Test schreiben** — `test_log_line`: `_meta` in Zeile 1, je Aufruf eine
      Zeile mit festen Schlüsseln (Plan, Task oder Prüfpunkt, Modell, Grund, Verdikte,
      `subagent_tokens`, Funde, betroffene Task); fehlende `subagent_tokens` als `null`.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_subagent_dev_plan_to_tasks.py -k log_line`.
- [ ] **Step 3: Implementieren** — `log` schreibt nach `.skills/subagent-dev/runlog.jsonl`
      mit `ensure_ascii=False`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 11: references/checkpoints.md

**Files:**
- Create: `skills/subagent-dev/references/checkpoints.md`

**Interfaces:**
- Consumes: `fn:place_checkpoints(tasks, consumers, gate)`, `fn:checkpoint_mark(repo, commit, run, tasks)`, `fn:append_log(path, entry)`
- Produces: `token:Review ohne Abdeckungsnachweis`

- [ ] **Step 1: Schreiben** — Regeln M0–M3 und C1–C5 als Tabellen, Abnehmer, Ablauf mit
      `review-state.json`, Review am Prüfpunkt über `last_reviewed..HEAD` mit
      `/code-review` (deep-review pausiert, Aufruf mit `--profile`/`--depth` und
      `--since` für später beschrieben), Soll als Datei unter `.skills/cache/tasks/`,
      Fix-Pfad mit höchstens zwei Runden, runlog.
- [ ] **Step 2: Prüfen** — jede Regel-ID und Konstante steht gleich im Skript (grep);
      kein `${CLAUDE_SKILL_DIR}` mit `python` in der Datei. Commit.

### Task 12: references/contract-check.md

**Files:**
- Create: `skills/subagent-dev/references/contract-check.md`

**Interfaces:**
- Consumes: `fn:collect_hints(worktree, base)`
- Produces: `token:Vertrag geprüft`

- [ ] **Step 1: Schreiben** — Auftrag an den Haiku-Agenten: Task-Datei, Diff,
      `verify`-Ergebnis; je Step `erledigt` oder `fehlt`, Änderungen ohne Bezug zu einem
      Step, Hinweise aus `verify`; Ausgabe `contract-task-<N>.md` mit Kopfzeile; das
      Ergebnis heißt „Vertrag geprüft", nie „reviewed".
- [ ] **Step 2: Prüfen** — Wortwahl nach E2; Beispiel ohne Werte aus den Fixtures. Commit.

### Task 13: references/merge-protocol.md

**Files:**
- Modify: `skills/subagent-dev/references/merge-protocol.md`

**Interfaces:**
- Consumes: `token:Review ohne Abdeckungsnachweis`, `token:Vertrag geprüft`
- Produces: `token:finaler Prüfpunkt`

- [ ] **Step 1: Schreiben** — Zeile 3 „mechanisch + `/code-review`" wird `verify`,
      Vertragsprüfung, `checkpoint status`, Review nur am Prüfpunkt; Abschluss mit dem
      finalen Prüfpunkt; Fix-Runden je Task mit Opus-Versuch in frischem Worktree.
- [ ] **Step 2: Prüfen** — kein Satz verlangt mehr ein Review je Task (grep
      `code-review`). Commit.

### Task 14: SKILL.md

**Files:**
- Modify: `skills/subagent-dev/SKILL.md`
- Modify: `.claude/skills/subagent-dev/`

**Interfaces:**
- Consumes: `token:Review ohne Abdeckungsnachweis`, `token:Vertrag geprüft`, `token:finaler Prüfpunkt`, `fn:checkpoint_init(repo, base)`
- Produces: `token:Eiserne Regel`

- [ ] **Step 1: Rumpf** — Eiserne Regel der Spec; Schritt 2 mit Modell, Prüfpunkten und
      `checkpoint init`; Schritt 4 Dispatch mit `model`; Schritt 5 `verify`,
      Vertragsprüfung, `checkpoint status`, Review nur am Prüfpunkt; Fix-Pfad; Eskalation
      zu Opus; Kostentabelle und Zeile „Review pro Task ist zu teuer" entfallen; Contract
      und Abgrenzung nach der Spec (deep-review in Backticks, solange es keine SKILL.md hat).
- [ ] **Step 2: Prüfen** — `wc -l` ≤ 150; `lint_skill.py skills/subagent-dev --base HEAD`
      ohne neuen Befund, `evals_due` notieren; `sync_skills.py`, dann `--check`. Commit.

### Task 15: Evals

**Files:**
- Modify: `evals/subagent-dev/evals.json`
- Create: `evals/fixtures/plan-fanout/fixture.json`
- Create: `evals/fixtures/plan-fanout/README.md`
- Create: `evals/fixtures/plan-fanout-override/fixture.json`
- Create: `evals/fixtures/plan-fanout-override/README.md`
- Create: `evals/fixtures/plan-fanout-dispatched/fixture.json`
- Create: `evals/fixtures/plan-fanout-dispatched/README.md`
- Create: `evals/fixtures/cp-size/fixture.json`
- Create: `evals/fixtures/cp-size/README.md`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: `fn:place_checkpoints(tasks, consumers, gate)`, `fn:check_consumers(worktree, allowlist, consumers)`, `fn:checkpoint_status(repo, after_task, tests_red)`, `token:Eiserne Regel`
- Produces: `token:anti-ceremony-mini-plan-gets-only-final-checkpoint`

- [ ] **Step 1: Fixtures** — nach der Spec: `.gitignore` mit `.skills/cache/` und
      `.claude/` und alle Dateien unter `.skills/cache/` als `touch`-Einträge in `commits`;
      `plan-fanout` (Task 1 liefert `parse_order`, Task 3 und 4 verwenden es, Task 2
      unabhängig, Task 5 `Verifikation`), `plan-fanout-override` mit `**Modell:** sonnet`
      unter Task 1, `plan-fanout-dispatched` mit Tag `base` und Task 1 als
      `parse_order(line, strict)` ohne Default, `cp-size` mit Tag `reviewed` und genau 430
      neuen Zeilen in `src/`; je eine `README.md` im Fixture-Ordner.
- [ ] **Step 2: Evals** — `anti-ceremony-mini-plan-gets-only-final-checkpoint`,
      `fanout-producer-gets-opus-and-checkpoint`, `plan-model-line-overrides-rules`,
      `consumer-check-catches-arity-drift`, `checkpoint-due-by-size` mit Assertions und
      Prompts der Spec (`|` statt `\|`), Diskriminator-Frage in `notes`; die bisherigen vier
      Evals bleiben.
- [ ] **Step 3: Test** — `test_evals_and_fixtures_spec27`: `load_evals` lädt neun Evals; die
      Muster aus Eval 1 bis 5 treffen die Ausgabe von `generate`, `verify` und
      `checkpoint status` an den echten Fixtures und nicht an einer Variante ohne die
      Falle. Commit.

### Task 16: Nachbarn

Plugin-Zuordnung: unverändert (subagent-dev in `evaluated-dev`, impl-plan wie bisher).

**Files:**
- Modify: `skills/work-plan/references/task-patterns.md`
- Modify: `skills/impl-plan/references/task-patterns.md`
- Modify: `skills/test-first/SKILL.md`
- Modify: `.claude/skills/impl-plan/`
- Modify: `tests/test_skills_lint.py`

**Interfaces:**
- Consumes: `token:anti-ceremony-mini-plan-gets-only-final-checkpoint`
- Produces: (nichts Neues)

- [ ] **Step 1: Rückverweise** — work-plan und impl-plan: optionale Zeile `**Modell:**`
      unter dem Task-Titel, Abnehmer-Task beginnt mit einem Test gegen die Vorleistung, mit
      dem Wort subagent-dev; test-first: Abgrenzung „subagent-dev liest das Log nur als
      Hinweis". `sync_skills.py`, `--check`; `lint_skill.py --base HEAD` je Skill ohne
      neuen Befund, `evals_due` notieren.
- [ ] **Step 2: Register** — subagent-dev ohne `anti-ceremony-eval` und `report-section`,
      `KNOWN_FINDINGS_MAX_PAIRS = 77`; `pytest tests/test_skills_lint.py`. Commit.

### Task 17: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `token:anti-ceremony-mini-plan-gets-only-final-checkpoint`
- Produces: (nichts Neues)

- [ ] **Step 1: Abschnitt** — unter `## subagent-dev`: Risikowörter, Breite und
      Pflicht-Titel gesetzt, nicht gemessen; `interfaces_unknown` bekommt weder M1 noch C1
      (cad-parts: 11 von 12 Tasks), nur der Größen-Trigger; Arity nur für Python;
      `model` und `subagent_tokens` nur in Claude Code beobachtet; Review am Prüfpunkt ohne
      Abdeckungsnachweis, solange Spec 26 pausiert. Commit.

### Task 18: Report

**Files:**
- Modify: `docs/superpowers/reports/subagent-dev-report.md`

**Interfaces:**
- Consumes: `token:Basislinie Spec 27`, `token:Eiserne Regel`
- Produces: (nichts Neues)

- [ ] **Step 1: Messung** — `generate` über die drei Pläne aus Task 2; `/code-review` nur an
      deren Prüfpunkten über dieselbe Historie; Tokens und Funde gegen die Basislinie;
      Funde, die nur eine Seite hat, am Code nachprüfen. Abnahme nach der Spec (mindestens
      40 % weniger Review-Tokens je Plan, mindestens gleich viele nachgeprüfte Funde).
- [ ] **Step 2: Evals** — die fünf neuen mit Skill und einmal ohne (Spec 18), die vier
      bisherigen erneut, dazu die Evals von work-plan, impl-plan und test-first, wo
      `evals_due` `true` war.
- [ ] **Step 3: Report** — Ergebnis, Prüfpunkte je Plan, Grenzwerte aus E8, „## Was nicht
      gemessen wurde" aktualisiert; `lint_skill.py skills/subagent-dev` meldet nur noch
      `description` und `routing`. Commit.
