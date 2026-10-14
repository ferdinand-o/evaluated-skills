<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# setup-repo Abschnitt D Implementation Plan

**Goal:** `apply` installiert im Zielrepo `.claude/agents/reviewer.md`, einen Subagenten,
der vor dem Abschluss eines Ziels prüft, ob der Diff „Fertig wenn" erfüllt, im Bereich
bleibt und die Konformitäts-Prüfpunkte des erkannten Stacks einhält — jeder Prüfpunkt
mit Quelle, ein Stack ohne Prüfpunkte als „ungeprüft".

**Architecture:** Daten unter `references/review/<stack>.md` (eine Zeile je Prüfpunkt:
ID, Text, Quelle). `plan_repo.py` setzt die Prüfpunkte der erkannten Sprachen und die
allgemeinen in das Asset `assets/agents/reviewer.md` ein und plant ein `create`; ein
vorhandener `reviewer.md` bleibt unberührt. Die Zielregel nennt den Reviewer vor
*Erledigt*. Delphi-Prüfpunkte fehlen bewusst (Entscheidung des Nutzers vom 2026-10-14):
`delphi.md` ist leer, der Reviewer meldet den Stack als ungeprüft.

**Lesson aus Spec 22 C:** Ein geändertes Asset, das Fixtures byte-gleich tragen
(`rules/goals.md`), und die Pläne der Fixtures werden im selben Task neu erzeugt.

**Tech Stack:** Python 3.11+ Stdlib; Markdown.

**Spec:** `specs/Spec 22 – setup-repo.md`

## Global Constraints

- **E1 — Prüfpunkt mit Quelle.** Jede Zeile in `references/review/*.md` nennt eine
  Quelle; der Test lehnt eine ohne ab.
- **E2 — Kein Überschreiben.** Ein vorhandener `.claude/agents/reviewer.md` bekommt keine
  Operation; der Plan sagt es.
- **E3 — Kopfzeile nach dem Frontmatter** (Ausnahme in `docs/artifact-header.md`).
- **E4 — Zielregel ≤ 25 Zeilen.**
- **E5 — Anti-Zeremonie unverändert:** `check` auf `sr-aligned` meldet „keine Abweichung".

## Skill-Struktur

```
skills/setup-repo/
├── references/review/python.md, typescript.md, delphi.md, generic.md   neu
├── assets/agents/reviewer.md                                          neu
├── assets/rules/goals.md                                              Reviewer vor Erledigt
├── scripts/plan_repo.py                                               Operation für reviewer.md
└── SKILL.md, references/goals.md                                      Reviewer im Ablauf
tests/test_setup_repo_review.py, evals/setup-repo/evals.json, evals/fixtures/sr-*
```

### Task 1: Prüfpunkte

**Files:**
- Create: `skills/setup-repo/references/review/python.md`
- Create: `skills/setup-repo/references/review/typescript.md`
- Create: `skills/setup-repo/references/review/delphi.md`
- Create: `skills/setup-repo/references/review/generic.md`
- Test: `tests/test_setup_repo_review.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `token:Quelle:`

- [x] **Step 1: Test schreiben** — `test_checkpoints_have_sources`: jede Zeile unter
      `## Prüfpunkte` hat ID, Text und Quelle; IDs eindeutig; `delphi.md` ohne Zeile, mit
      Hinweis, dass die Punkte vom Nutzer kommen.
- [x] **Step 2: Rot sehen.**
- [x] **Step 3: Schreiben** — Python und TypeScript je Test für Neues und Abhängigkeit im
      Manifest (Quellen: Spec 22, PEP 621, npm-Doku), dazu PEP 8; generic: „Fertig
      wenn" belegt, Bereich, Verifikation grün.
- [x] **Step 4: Grün sehen.**
- [x] **Step 5: Commit.**

### Task 2: reviewer.md

**Files:**
- Create: `skills/setup-repo/assets/agents/reviewer.md`
- Modify: `tests/test_setup_repo_review.py`

**Interfaces:**
- Consumes: `token:Quelle:`
- Produces: `token:{{checkpoints}}`

- [x] **Step 1: Test schreiben** — Frontmatter mit `name: reviewer`, `description`,
      `tools`; Kopfzeile in der ersten Zeile danach; Platzhalter `{{checkpoints}}` genau
      einmal; Befunde mit Failure-Szenario verlangt; „/code-review" als Abgrenzung.
- [x] **Step 2: Rot sehen.**
- [x] **Step 3: Schreiben** — Eingaben (Ziel-ID, Diff-Bereich, optional Kontextpaket von
      review-context), drei Prüfungen, Ausgabeformat mit Urteil je Prüfpunkt.
- [x] **Step 4: Grün sehen.**
- [x] **Step 5: Commit.**

### Task 3: reviewer.md im Plan

**Files:**
- Modify: `skills/setup-repo/scripts/plan_repo.py`
- Modify: `skills/setup-repo/assets/rules/goals.md`
- Modify: `skills/setup-repo/references/plan-format.md`
- Modify: `tests/test_setup_repo_review.py`
- Modify: `evals/fixtures/sr-aligned/`
- Modify: `evals/fixtures/sr-planned/`
- Modify: `evals/fixtures/sr-tampered/`
- Modify: `evals-templates/fixtures/sr-goals-seeded/`

**Interfaces:**
- Consumes: `token:{{checkpoints}}`
- Produces: `fn:reviewer_content(detect)`, `token:.claude/agents/reviewer.md`

- [x] **Step 1: Test schreiben** — Python-Repo → `create` mit Python- und allgemeinen
      Prüfpunkten; Delphi-Repo → „ungeprüft — keine Prüfpunkte für delphi"; ohne erkannte
      Sprache nur allgemeine; vorhandener `reviewer.md` → keine Operation; Option
      `reviewer: false` → keine Operation; Zielregel nennt den Reviewer und bleibt ≤ 25
      Zeilen.
- [x] **Step 2: Rot sehen.**
- [x] **Step 3: Implementieren** — `reviewer_content(detect)`; Option `reviewer`
      (Default an) im Block; Ansicht nennt den Reviewer; Zielregel ergänzen; Fixtures mit
      dem Generator neu erzeugen, `sr-goals-seeded` gleichziehen.
- [x] **Step 4: Grün sehen**, alle `tests/test_setup_repo_*.py`.
- [x] **Step 5: Commit.**

### Task 4: SKILL.md und goals.md

**Files:**
- Modify: `skills/setup-repo/SKILL.md`
- Modify: `skills/setup-repo/references/goals.md`
- Modify: `docs/artifact-header.md`

**Interfaces:**
- Consumes: `token:.claude/agents/reviewer.md`
- Produces: `token:Ziel-Reviewer`

- [x] **Step 1: Schreiben** — Ablauf nennt den Reviewer und `reviewer: false`; goals.md:
      Reviewer vor *Erledigt*; artifact-header: Satz zu den Ausnahmen nennt reviewer.md.
- [x] **Step 2: Prüfen** — `wc -l` ≤ 150; `lint_skill.py skills/setup-repo --base HEAD`
      ohne neuen Befund, `evals_due` notieren. Commit.

### Task 5: Evals

**Files:**
- Modify: `evals/setup-repo/evals.json`
- Modify: `tests/test_setup_repo_fixtures.py`

**Interfaces:**
- Consumes: `token:Ziel-Reviewer`
- Produces: `token:py-test-for-public`

- [x] **Step 1: Assertion** — `apply-executes-plan-faithfully` prüft zusätzlich
      `.claude/agents/reviewer.md` auf `py-test-for-public` (nur der Plan trägt die ID);
      Diskriminator in `notes` ergänzen.
- [x] **Step 2: Test** — Replay der Evals besteht weiter, auch
      `anti-ceremony-check-on-aligned-repo-changes-nothing`. Commit.

### Task 6: Nachbarn

**Files:**
- Modify: `skills/review-context/SKILL.md`
- Modify: `.claude/skills/review-context/`

**Interfaces:**
- Consumes: `token:py-test-for-public`
- Produces: (nichts Neues)

- [x] **Step 1: Rückverweis** — review-context: der Ziel-Reviewer von setup-repo liest das
      Kontextpaket, wenn es im selben Lauf erzeugt wurde. Plugin-Zuordnung und Routing
      unverändert. `sync_skills.py`, `--check`, Lint ohne neuen Befund. Commit.

### Task 7: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `token:py-test-for-public`
- Produces: (nichts Neues)

- [x] **Step 1: Abschnitt setup-repo** — „Abschnitt D fehlt" ersetzen: Delphi ohne
      Prüfpunkte, ob der Reviewer aufgerufen wird und ob Prüfpunkte greifen, misst nichts;
      Agent-Frontmatter nach Doku, nicht gemessen. Commit.

### Task 8: Report

**Files:**
- Modify: `docs/superpowers/reports/setup-repo-report.md`

**Interfaces:**
- Consumes: `token:py-test-for-public`
- Produces: (nichts Neues)

- [x] **Step 1: Report** — Abschnitt D: was entstanden ist, Entscheidung zu Delphi,
      Eval-Läufe mit `claude -p` für die Evals mit geänderter Wirkung
      (`anti-ceremony-check-on-aligned-repo-changes-nothing`,
      `plan-from-repo-writes-only-report`, `plan-without-tests-says-unverified`,
      `apply-executes-plan-faithfully`, `apply-refuses-tampered-plan`), „Was nicht
      gemessen wurde". Commit.
