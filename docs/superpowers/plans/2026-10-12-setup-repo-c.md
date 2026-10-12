<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# setup-repo Implementation Plan (Abschnitt C — Ziele)

**Goal:** Ein eingerichtetes Repo führt seine Ziele in `docs/goals.md`, eine immer
geladene Regel lässt Claude entdeckte Arbeit in vier Klassen einordnen, und ein
Bereichs-Hook meldet Dateiänderungen außerhalb der Bereiche aktiver Ziele — sichtbar für
den Nutzer sofort, für Claude beim nächsten Prompt, ohne je ein Turn-Ende anzuhalten.

**Architecture:** Tier 1, nur Stdlib. Neu ist ein Laufzeitskript im Zielrepo,
`assets/runtime/goal_scope.py`, an zwei Ereignissen (`UserPromptSubmit` hält die Basis
des Turns fest und gibt eine offene Meldung als `additionalContext` aus; `Stop`
vergleicht gegen die Basis und meldet per `systemMessage`). Dazu drei Assets (Ledger-Gerüst,
Zielregel, Hook-Fragment), eine Reference, und die Einbindung in `plan_repo.py` (Ledger,
Regel, Hook vorausgewählt und abwählbar) und `apply_repo.py` (eigener Hook erkannt, Probe
mit Beispiel-Payload in einem Temp-Zustand, `check` prüft die Ledger-Kopfzeile). Die
Fixtures der Evals werden neu erzeugt, Eval 1 und 4 bekommen ihre Assertions auf Ziele
zurück. Die Vorlagen-Messung liegt außerhalb des Eval-Vertrags in `evals-templates/`.
Abschnitt D (Ziel-Reviewer) ist nicht Teil dieses Plans.

Drei Entscheidungen, die die Spec offen lässt:

- **Der Hook-Zustand für die Probe liegt in einem Temp-Verzeichnis.** `goal_scope.py`
  liest den Pfad aus `SETUP_REPO_GOAL_STATE`, sonst `.skills/cache/setup-repo/goal-scope.json`;
  `apply` und `check` proben mit einer Temp-Datei, damit eine Probe nie einen echten
  Session-Zustand anlegt.
- **Ein Bereich mit Schrägstrich am Ende** (`src/`) gilt als `src/**`. Die Spec nennt den
  Fall nicht; ohne Regel passte er auf keine Datei.
- **Abwählen heißt `--without-goal-hook`.** Ledger und Regel kommen immer mit; die Regel
  schweigt ohne aktives Ziel, der Ledger entsteht leer.

**Lesson aus Abschnitt B:** Jedes neue Skript trägt „Tier 1" im Modul-Docstring
(Lint `script-tier`).

**Tech Stack:** Python 3.11+ Stdlib für Skripte und Tests; `git` als Unterprozess;
Markdown für Assets, Reference, Evals.

**Spec:** `specs/Spec 22 – setup-repo.md`

## Global Constraints

- **E1 — Tier 1, nur Stdlib, keine Imports zwischen Skripten.** Fehlt `git` oder scheitert
  ein Aufruf, meldet `goal_scope.py` das einmal je Session per `systemMessage` und
  schweigt sonst.
- **E2 — Gate-Sprache:** Die Zielregel verlangt die vier Klassen (G1); der Bereichs-Hook
  meldet (G2) und hält nichts an — nie `decision`, nie Exit 2, kein Folgeturn.
- **E3 — Kopfzeile je Artefakt:** `docs/goals.md` und `.claude/rules/goals.md` in Zeile 1,
  der Hook-Zustand per `_meta`. Konsumenten-Regel: Wer `docs/goals.md` liest, prüft die
  Kopfzeile zuerst.
- **E4 — SKILL.md ≤ 150 Zeilen**, Zielregel ≤ 25 Zeilen, Budget weiter ≤ 150.
- **E5 — Sichtbar oder gar nicht:** Jede Meldung des Stop-Hooks geht über
  `systemMessage`; nichts landet nur im Debug-Log.
- **E6 — Laufzeitskripte enden immer mit 0** (`goal_scope.py`), jede Ausnahme gefangen,
  stdin als Bytes mit UTF-8-Ersetzung, Zustand atomar, Einträge älter als sieben Tage
  fallen weg.
- **E7 — Pfade relativ zur Repo-Wurzel** (`git rev-parse --show-toplevel`), auch wenn die
  Session in einem Unterordner läuft; git immer mit `-z`.

## Skill-Struktur

```
skills/setup-repo/
├── references/goals.md
├── assets/goals.md, assets/rules/goals.md
├── assets/runtime/goal_scope.py
├── assets/hooks/goal-scope.json
└── scripts/plan_repo.py, apply_repo.py        (erweitert)

evals/setup-repo/evals.json, evals/fixtures/sr-*/        (neu erzeugt, Eval 1 und 4 ergänzt)
evals-templates/setup-repo/evals.json, evals-templates/fixtures/sr-goals-seeded/
tests/test_setup_repo_goal_scope.py, _plan.py, _apply.py, _fixtures.py, _templates.py
skills/handoff/SKILL.md, README.md
```

### Task 1: Reference goals.md

**Files:**
- Create: `skills/setup-repo/references/goals.md`
- Modify: `skills/setup-repo/references/plan-format.md`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `token:Fertig wenn`, `token:goal_hook`

- [x] **Step 1: goals.md** — Ledger-Schema mit drei Tabellen (*Aktiv*: `id`, Ziel, Fertig
      wenn, Bereich, seit; *Kandidaten*: `id`, Kandidat, entdeckt bei, Grund, am;
      *Erledigt*: `id`, Ziel, Beleg, am, die letzten zehn); ID-Vergabe `G<n>` über alle
      drei Tabellen, vor jedem Schreiben neu lesen und nur anhängen; „Fertig wenn" nach der
      `/goal`-Doku (Endzustand, Prüfung, was sich nicht ändern darf); Glob-Dialekt (`**`,
      `*`, `?`, `/`, Groß- und Kleinschreibung, keine Klammern, Komma-Liste, `src/` gleich
      `src/**`, leere Zelle ohne Bereich); die vier Klassen mit Beispielen; ausgenommene
      Pfade des Hooks; Merge-Konflikte fragen.
- [x] **Step 2: plan-format.md** — Option `goal_hook` (Standard `true`, abwählbar mit
      `--without-goal-hook`), Operationen für `docs/goals.md`, `.claude/rules/goals.md`,
      `.claude/hooks/goal_scope.py`; eigener Hook auch am Suffix
      `.claude/hooks/goal_scope.py` erkannt.
- [x] **Step 3: Prüfen** — beide Dateien unter 200 Zeilen, die Tokens wörtlich. Commit.

### Task 2: Assets für Ziele

**Files:**
- Create: `skills/setup-repo/assets/goals.md`
- Create: `skills/setup-repo/assets/rules/goals.md`
- Create: `skills/setup-repo/assets/hooks/goal-scope.json`
- Test: `tests/test_setup_repo_goal_assets.py`

**Interfaces:**
- Consumes: `token:Fertig wenn`
- Produces: `token:Kandidaten`, `token:UserPromptSubmit`

- [x] **Step 1: Tests schreiben** — `test_goal_assets_shape`: Ledger mit Kopfzeile
      `schema: 1` und den drei Tabellenköpfen ohne Zeilen; Regel ≤ 25 Zeilen, Kopfzeile in
      Zeile 1, kein `paths`-Frontmatter, nennt die vier Klassen; Fragment mit genau einem
      Eintrag je `UserPromptSubmit` und `Stop`, beide mit dem Starter und
      `$CLAUDE_PROJECT_DIR/.claude/hooks/goal_scope.py`.
- [x] **Step 2: Rot sehen** — `pytest tests/test_setup_repo_goal_assets.py`.
- [x] **Step 3: Schreiben** — die drei Dateien; die Regel gilt nur, solange *Aktiv*
      mindestens ein Ziel hat, und sagt, was `[setup-repo]`-Meldungen bedeuten.
- [x] **Step 4: Grün sehen**, `lint_skill.py skills/setup-repo` ohne Befund für
      `asset-headers`.
- [x] **Step 5: Commit.**

### Task 3: goal_scope.py

**Files:**
- Create: `skills/setup-repo/assets/runtime/goal_scope.py`
- Test: `tests/test_setup_repo_goal_scope.py`

**Interfaces:**
- Consumes: `token:UserPromptSubmit`, `token:Kandidaten`
- Produces: `fn:on_prompt(payload, root)`, `fn:on_stop(payload, root)`, `fn:glob_match(pattern, path)`

- [x] **Step 1: Tests schreiben** — `test_goal_scope_turn_baseline` (vorher uncommittete,
      unveränderte Datei → keine Meldung; im Turn committete, gestagete, ungestagete und
      gelöschte Datei außerhalb → je eine Meldung; Nicht-ASCII-Name; Session im
      Unterordner), `test_goal_scope_reports_each_file_once_and_defers_context`,
      `test_goal_scope_globs`, `test_goal_scope_ignores_house_artifacts`,
      `test_goal_scope_silent_or_visible` (kein Ledger, kein aktives Ziel, Repo ohne
      Commit → nichts; fremde Kopfzeile oder git-Fehler → einmal `systemMessage`; kaputter
      Zustand → Neustart), `test_goal_scope_output_shape` (Stop nur `systemMessage`, nie
      `decision` oder `additionalContext`; UserPromptSubmit mit `hookEventName` und
      `additionalContext`, Text beginnt mit `[setup-repo]`; Exit immer 0); alle als
      Unterprozess in Mini-Repos mit git.
- [x] **Step 2: Rot sehen** — `pytest tests/test_setup_repo_goal_scope.py`.
- [x] **Step 3: Implementieren** — Ereignis aus `hook_event_name`; Basis je Turn aus
      `git rev-parse HEAD` und Inhalts-Hashes der Einträge aus
      `git status --porcelain -z --untracked-files=all`; Stop über
      `git diff <basis> --name-only -z` plus `git ls-files --others --exclude-standard -z`
      plus gelöschte Basis-Dateien; Ausnahmen aus `references/goals.md`; Zustand nach E6
      mit `SETUP_REPO_GOAL_STATE`; „Tier 1" im Docstring.
- [x] **Step 4: Grün sehen**, volle Suite.
- [x] **Step 5: Commit.**

### Task 4: Ziele in plan_repo.py

**Files:**
- Modify: `skills/setup-repo/scripts/plan_repo.py`
- Modify: `tests/test_setup_repo_plan.py`

**Interfaces:**
- Consumes: `fn:on_prompt(payload, root)`, `token:goal_hook`
- Produces: `fn:build_plan(repo_root, detect, candidates, options)`

- [x] **Step 1: Tests schreiben** — `test_plan_adds_goals_by_default` (Ledger und Regel als
      `create`, `goal_scope.py` als `copy`, beide Ereignisse im Settings-Patch, Budget
      zählt die Regel), `test_plan_without_goal_hook` (Regel und Ledger bleiben, Hook und
      Kopie fehlen, Ansicht sagt „aus"), `test_plan_keeps_existing_ledger` (vorhandenes
      `docs/goals.md` wird nicht angefasst).
- [x] **Step 2: Rot sehen** — `pytest tests/test_setup_repo_plan.py -k goal`.
- [x] **Step 3: Implementieren** — Option `goal_hook` (Standard an), `--without-goal-hook`;
      Operationen nach `references/plan-format.md`; Ansicht unter „Hooks (abwählbar)".
- [x] **Step 4: Grün sehen**, volle Suite (Fixture-Test darf hier rot werden; Task 7
      erzeugt die Fixtures neu).
- [x] **Step 5: Commit.**

### Task 5: Ziele in apply_repo.py

**Files:**
- Modify: `skills/setup-repo/scripts/apply_repo.py`
- Modify: `tests/test_setup_repo_apply.py`

**Interfaces:**
- Consumes: `fn:on_stop(payload, root)`, `fn:build_plan(repo_root, detect, candidates, options)`
- Produces: `fn:apply_plan(repo_root, plan_path)`, `fn:check_repo(repo_root)`

- [x] **Step 1: Tests schreiben** — `test_apply_probes_goal_hook_without_touching_state`
      (Probe mit `UserPromptSubmit` und `Stop`, danach kein
      `.skills/cache/setup-repo/goal-scope.json`), `test_apply_merges_goal_hook_once`
      (zweimal anwenden, je Ereignis genau ein eigener Eintrag, fremde bleiben),
      `test_check_reads_ledger_header` (fremde Kopfzeile in `docs/goals.md` → Abweichung).
- [x] **Step 2: Rot sehen** — `pytest tests/test_setup_repo_apply.py -k goal`.
- [x] **Step 3: Implementieren** — eigener Hook an beiden Suffixen; Probe über
      `sys.executable` mit `SETUP_REPO_GOAL_STATE` in einem Temp-Verzeichnis, Exit 0 und
      gültiges JSON oder leere Ausgabe; `check` prüft die Ledger-Kopfzeile.
- [x] **Step 4: Grün sehen**, volle Suite.
- [x] **Step 5: Commit.**

### Task 6: SKILL.md

**Files:**
- Modify: `skills/setup-repo/SKILL.md`

**Interfaces:**
- Consumes: `fn:check_repo(repo_root)`, `token:Fertig wenn`
- Produces: `token:Neue Ziele werden Kandidaten`

- [x] **Step 1: Abschnitt Ziele** — Ledger, Zielregel, Bereichs-Hook in wenigen Zeilen mit
      Verweis auf `references/goals.md`; `--without-goal-hook`; Contract-Zeilen „Neue Ziele
      werden Kandidaten" und „Sichtbar oder gar nicht"; Anti-Zeremonie: ohne aktives Ziel
      schweigen Regel und Hook; **handoff** in der Abgrenzung.
- [x] **Step 2: Prüfen** — `wc -l` unter 150; `lint_skill.py skills/setup-repo` ohne
      Befund außer `neighbors`, den Task 9 schließt. Commit.

### Task 7: Evals

**Files:**
- Modify: `evals/setup-repo/evals.json`
- Modify: `evals/fixtures/sr-aligned/`
- Modify: `evals/fixtures/sr-planned/`
- Modify: `evals/fixtures/sr-tampered/`
- Modify: `tests/test_setup_repo_fixtures.py`

**Interfaces:**
- Consumes: `token:Neue Ziele werden Kandidaten`
- Produces: `token:anti-ceremony-check-on-aligned-repo-changes-nothing`

- [x] **Step 1: Fixtures** — `sr-planned` und `sr-tampered` mit neu erzeugtem Plan (Ziele
      vorausgewählt), `sr-aligned` nach `apply` mit Ledger, Regel und Hook.
- [x] **Step 2: Evals** — `anti-ceremony-check-on-aligned-repo-changes-nothing` bekommt
      `file_unchanged` auf `.claude/rules/goals.md`, `.claude/hooks/goal_scope.py` und
      `docs/goals.md`; `apply-executes-plan-faithfully` bekommt `file_matches`
      `.claude/settings.json` auf `goal_scope`; `plan-from-repo-writes-only-report`,
      `plan-without-tests-says-unverified` und `apply-refuses-tampered-plan` bleiben.
- [x] **Step 3: Schema- und Nachspiel-Test** — `test_fixture_plans_are_current`,
      `test_aligned_fixture_matches_apply`, `test_replayed_eval_passes_its_own_assertions`
      grün. Commit.

### Task 8: Vorlagen-Messung

**Files:**
- Create: `evals-templates/setup-repo/evals.json`
- Create: `evals-templates/fixtures/sr-goals-seeded/`
- Test: `tests/test_setup_repo_templates.py`

**Interfaces:**
- Consumes: `token:Kandidaten`
- Produces: `token:sr-goals-seeded`

- [x] **Step 1: Fixture** — eingerichtetes Repo mit Ledger (aktives Ziel G1 „Tippfehler in
      greet.py beheben", Bereich `src/greet.py`), Regel, CLAUDE.md, Tippfehler in
      `src/greet.py`, offensichtlichem Fehler in `src/dates.py`, „Helo" im README.
- [x] **Step 2: Evals** — zwei Fälle aus der Spec: Prompt mit Ziel G1 → Zeile unter
      *Kandidaten* mit `dates`, `src/dates.py` unverändert; README-Prompt → keine neue Zeile
      unter *Aktiv* und *Kandidaten*.
- [x] **Step 3: Test** — `load_evals` lädt beide; die Fixture trägt die Assets
      byte-gleich. Commit.

### Task 9: Nachbarn

**Files:**
- Modify: `skills/handoff/SKILL.md`
- Modify: `.claude/skills/handoff/`
- Modify: `README.md`

**Interfaces:**
- Consumes: `token:Kandidaten`
- Produces: (nichts Neues)

- [x] **Step 1: handoff** — unter den Inhaltsregeln: existiert `docs/goals.md` mit
      lesbarer Kopfzeile von setup-repo, nennt die Übergabe es unter „Einstiegspunkte";
      `python scripts/sync_skills.py` und `--check`; `lint_skill.py --base HEAD
      skills/handoff` ohne neuen Befund.
- [x] **Step 2: README** — „Aufbau" nennt `evals-templates/` (Vorlagen-Messungen außerhalb
      des Eval-Vertrags). Plugin-Zuordnung unverändert. Commit.

### Task 10: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `token:sr-goals-seeded`
- Produces: (nichts Neues)

- [x] **Step 1: Abschnitt setup-repo ergänzen** — der Hook sieht nur Dateien, nicht
      Absichten; mit `-p` sieht Claude die Meldung nie; gleichzeitige Sessions und
      Merge-Konflikte im Ledger; Windows ungemessen; „Abschnitt C fehlt" streichen.
      Commit.

### Task 11: Report

**Files:**
- Modify: `docs/superpowers/reports/setup-repo-report.md`

**Interfaces:**
- Consumes: `token:sr-goals-seeded`
- Produces: (nichts Neues)

- [ ] **Step 1: Report** — Abschnitt C: was entstanden ist, Testzahl, Eval-Läufe mit und
      ohne Skill, Vorlagen-Messung als Quote oder „ungefahren" mit Grund, und „Was nicht
      gemessen wurde". `lint_skill.py skills/setup-repo` ganz sauber. Commit.
