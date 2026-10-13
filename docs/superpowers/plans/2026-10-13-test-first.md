<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# test-first Implementation Plan

**Goal:** Ein neues Verhalten entsteht in jedem Repo erst nach einem roten Test, und das
steht mit Befehl und Exit-Code in `.skills/cache/test-first/log.md` — ein sofort grüner
Test steht dort als solcher; kein Verweis zeigt mehr auf `test-driven-development`.

**Architecture:** Tier 1. `scripts/tdd_log.py` (Stdlib) führt den übergebenen Testbefehl
aus wie `verify_stop.py` (Vorprüfung per `shlex` und `shutil.which`, Shell an der
Repo-Wurzel, 300 s, UTF-8 mit Ersetzung) und schreibt je Aufruf höchstens eine
Tabellenzeile nach dem Zustandsmodell der Spec; das Log wird vor jedem Schreiben neu
gelesen und atomar ersetzt. SKILL.md ist der Zyklus je Verhalten, `references/cycle.md`
das Zustandsmodell und die Einschränkung auf einen Test je Runner. Dazu die Verweise in
testing-strategy, debug-ledger und work-plan.

**Lesson aus Spec 23:** Eval-Fixtures nicht mit Werten bauen, die als Beispiel in der
Skill selbst stehen — sonst diskriminiert der Eval nicht. Und Eval-Prompts gegen die
eigene Ausnahme-Regel der Skill prüfen, bevor der erste Lauf das tut.

**Tech Stack:** Python 3.11+ Stdlib für Skript und Tests; pytest in den Fixtures.

**Spec:** `specs/Spec 24 – test-first.md`

## Global Constraints

- **E1 — Tier 1, nur Stdlib.** `tdd_log.py` importiert nichts außerhalb der Stdlib,
  Docstring nennt „Tier 1"; Aufruf `python "${CLAUDE_SKILL_DIR}/scripts/tdd_log.py"`.
- **E2 — Gate-Sprache:** Rot vor Grün verlangt die SKILL.md (G1), das Skript meldet
  (G2); kein Hook, nichts nennt sich härter.
- **E3 — Kopfzeile:** `log.md` trägt `<!-- skill: test-first | schema: 1 | … -->` in
  Zeile 1.
- **E4 — SKILL.md ≤ 150 Zeilen**, portables Frontmatter.
- **E5 — Anti-Zeremonie-Eval** `anti-ceremony-doc-typo-runs-no-cycle`, gebunden an
  `output_matches` und `file_absent`.
- **E6 — Muster mit `\x7c`** für das Tabellenzeichen; `test_eval_patterns_match_only_real_cycles`
  misst sie an echten Logs aus `tdd_log.py`.

## Skill-Struktur

```
skills/test-first/
├── SKILL.md
├── references/cycle.md
└── scripts/tdd_log.py

evals/test-first/evals.json, evals/fixtures/tf-docs/, tf-feature/, tf-existing/
tests/test_test_first_log.py, tests/test_test_first_fixtures.py
```

### Task 1: tdd_log.py

**Files:**
- Create: `skills/test-first/scripts/tdd_log.py`
- Test: `tests/test_test_first_log.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `fn:main(argv)`, `fn:record(root, action, test_id, command)`, `token:sofort-grün`, `token:Vollständige Zyklen:`

- [x] **Step 1: Tests schreiben** — `test_state_model` (jede Zeile der Zustandstabelle,
      `red` nach `grün` beginnt einen neuen Zyklus), `test_sofort_gruen_never_counts_as_red`,
      `test_unverified_runs` (fehlendes Programm, Exit 127, Zeitgrenze per
      `monkeypatch` auf `TIMEOUT`), `test_log_format` (Kopfzeile, ID mit Leerzeichen
      oder `|` → Exit 2, `|` → `¦`, zehn Zeilen, Nicht-ASCII, UTF-8),
      `test_start_and_status`.
- [x] **Step 2: Rot sehen** — `pytest tests/test_test_first_log.py`.
- [x] **Step 3: Implementieren** — Unterbefehle `start`, `red`, `green`, `refactor`,
      `status`; Befehl nach `--`; Zustand je ID aus dem letzten Abschnitt des Logs
      gelesen, nicht aus einer zweiten Datei; `missing_program` wie in
      `verify_stop.py`; Zeile `Vollständige Zyklen: <n>` bei jedem Schreiben neu.
- [x] **Step 4: Grün sehen**, dann die ganze Suite.
- [x] **Step 5: Commit.**

### Task 2: references/cycle.md

**Files:**
- Create: `skills/test-first/references/cycle.md`

**Interfaces:**
- Consumes: `token:sofort-grün`, `token:Vollständige Zyklen:`
- Produces: `token:Zustandsmodell`

- [x] **Step 1: Schreiben** — Zustandsmodell als Tabelle (wörtlich aus der Spec), was
      ein Verhalten ist (ein Satz, eine Eigenschaft), sofort grün und was dann zu tun
      ist, Einschränkung auf einen Test je Runner (pytest Knoten-ID und `-k`,
      vitest/jest `-t`, go `-run`), die Grenze „fehlendes Runner-Modul zählt als Rot".
- [x] **Step 2: Prüfen** — jede Phase der Tabelle steht auch in `tdd_log.py`; der
      pytest-Aufruf aus dem Beispiel läuft gegen eine Fixture. Commit.

### Task 3: SKILL.md

**Files:**
- Create: `skills/test-first/SKILL.md`

**Interfaces:**
- Consumes: `fn:main(argv)`, `token:Zustandsmodell`
- Produces: `token:Kein Test-Zyklus nötig`, `token:ungetestet auf Wunsch`

- [x] **Step 1: Frontmatter** — Description mit Triggern („test first", „TDD",
      „rot-grün", „schreib erst den Test") und Abgrenzung gegen testing-strategy,
      debug-ledger und, solange installiert, `superpowers:test-driven-development`.
- [x] **Step 2: Rumpf** — Eiserne Regel, Ablauf in sieben Schritten mit den Aufrufen,
      Ausnahmen mit „Kein Test-Zyklus nötig", Verzicht mit „ungetestet auf Wunsch",
      „Druck ist kein Verzicht", Bootstrap-Satz zu `.skills/cache/`, Übergabe aus
      `status`; Contract; Anti-Rationalisierung; Abgrenzung mit **testing-strategy**,
      **debug-ledger**, **work-plan**.
- [x] **Step 3: Prüfen** — `wc -l` unter 150; `lint_skill.py skills/test-first` ohne
      Befund außer `evals-exist`, `routing`, `neighbors`, `report-section`,
      `plugin-membership`. Commit.

### Task 4: Evals

**Files:**
- Create: `evals/test-first/evals.json`
- Create: `evals/fixtures/tf-docs/`
- Create: `evals/fixtures/tf-feature/`
- Create: `evals/fixtures/tf-existing/`
- Create: `tests/test_test_first_fixtures.py`

**Interfaces:**
- Consumes: `fn:record(root, action, test_id, command)`, `token:Kein Test-Zyklus nötig`, `token:ungetestet auf Wunsch`
- Produces: `token:anti-ceremony-doc-typo-runs-no-cycle`

- [x] **Step 1: Fixtures** — je `fixture.json` mit `"git": true`, pytest-Konfiguration
      und `tests/`; `tf-docs` mit README-Tippfehler „Helo"; `tf-feature` ohne `slugify`;
      `tf-existing` mit `slugify` samt Umlaut-Verhalten, ohne Test dafür. Kein Wert in
      den Fixtures, der wörtlich als Beispiel in SKILL.md oder `cycle.md` steht, außer
      dem Funktionsnamen aus dem Prompt.
- [x] **Step 2: Evals** — `anti-ceremony-doc-typo-runs-no-cycle`,
      `red-before-green-is-recorded`, `green-on-first-run-is-flagged`,
      `pressure-still-red-first`, `explicit-waiver-says-untested` mit den Assertions und
      Prompts der Spec, Diskriminator-Frage in `notes`.
- [x] **Step 3: Test** — `test_eval_patterns_match_only_real_cycles`: Logs aus echten
      `tdd_log.py`-Läufen in einem Temp-Repo; die Muster treffen Rot-Grün derselben ID
      und nicht `sofort-grün` → `green`, nicht zwei IDs, nicht `ungeprüft`. Dazu: fünf
      Evals laden, Fixtures mit `"git": true`. Commit.

### Task 5: Nachbarn

**Files:**
- Modify: `skills/test-first/SKILL.md`
- Modify: `skills/testing-strategy/SKILL.md`
- Modify: `skills/debug-ledger/SKILL.md`
- Modify: `skills/work-plan/references/task-patterns.md`
- Modify: `.claude/skills/testing-strategy/`
- Modify: `.claude/skills/debug-ledger/`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `specs/Spec 00 – skill-foundation.md`
- Modify: `README.md`
- Modify: `tests/test_marketplace.py`

**Interfaces:**
- Consumes: `token:Kein Test-Zyklus nötig`
- Produces: (nichts Neues)

- [x] **Step 1: Test erweitern** — `test_no_superpowers_routing_targets` sucht zusätzlich
      `test-driven-development` unter `skills/`. Rot sehen.
- [x] **Step 2: Verweise** — die Description von test-first grenzt sich gegen die
      TDD-Skill von superpowers ohne das Präfix `superpowers:` ab (sonst zählt `--report`
      wieder 1); testing-strategy Description und Abgrenzung auf test-first;
      debug-ledger Abgrenzung (Regressionstest nach der Diagnose über test-first);
      Code-Task in `task-patterns.md` nennt test-first. `sync_skills.py`, `--check`,
      `lint_skill.py --base HEAD` je Skill ohne neuen Befund, `evals_due` notieren.
- [x] **Step 3: Plugin, Routing, README** — `./skills/test-first` in `cc-dev`; Spec 00
      und README: test-driven-development → test-first in der Zeile testing-strategy,
      eigene Zeile test-first; README-Liste von `cc-dev`. `pytest
      tests/test_marketplace.py`; `lint_skill.py skills/test-first` meldet `routing`,
      `neighbors`, `plugin-membership` grün. Commit.

### Task 6: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `token:anti-ceremony-doc-typo-runs-no-cycle`
- Produces: (nichts Neues)

- [ ] **Step 1: Abschnitt** — `## test-first`: Rot heißt Exit ≠ 0 (fehlendes
      Runner-Modul zählt als Rot); Einschränkung auf einen Test nur für pytest geprüft;
      Windows-Shell `cmd.exe`; Auslösen ohne Plan und Listing in `cc-dev` ungemessen;
      Log nicht committet und nicht regenerierbar; keine Projekt-Kopie. Commit.

### Task 7: Report

**Files:**
- Create: `docs/superpowers/reports/test-first-report.md`

**Interfaces:**
- Consumes: `token:anti-ceremony-doc-typo-runs-no-cycle`
- Produces: (nichts Neues)

- [ ] **Step 1: Report** — was entstanden ist, Testzahl, Eval-Läufe mit `claude -p` mit
      und ohne Skill, die Evals von testing-strategy nach der Description-Änderung
      erneut (`evals_due`), und „Was nicht gemessen wurde". `lint_skill.py
      skills/test-first` ganz sauber. Commit.
