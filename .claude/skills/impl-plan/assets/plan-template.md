<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# … Implementation Plan

**Goal:** … — ein Satz, der sagt, was danach anders ist, nicht was gebaut wird.

**Architecture:** … — welche Dateien, welcher Tier, wo der einzige Code liegt und
warum. Wer das liest, weiß, ob ein Skript entsteht und was es mechanisch prüft.

**Tech Stack:** Python 3.13 Stdlib für Skripte und Tests; Markdown für Skill,
References, Evals.

**Spec:** `specs/Spec 00 – skill-foundation.md` — hier den Pfad der eigenen Spec
eintragen; die Datei muss existieren, der Lint prüft das.

## Global Constraints

- **E1 — Tier je Skript** (Spec 00 §3): welcher Tier, und die Degradationszeile, falls
  ein Werkzeug fehlen kann. Ein übersprungenes Gate meldet nie Erfolg.
- **E2 — Gate-Sprache** (Spec 00 §4): G1 „verlangt", G2 „meldet", G3 „blockiert" —
  nur mit Hook. Nichts nennt sich härter, als sein Mechanismus ist.
- **E3 — Kopfzeile je Artefakt** (`docs/artifact-header.md`), auch für JSON per `_meta`.
- **E4 — SKILL.md ≤ 150 Zeilen**, portables Frontmatter, alles Weitere in `references/`.
- **E5 — Anti-Zeremonie-Eval ist Pflicht** (Spec 00 §2), mit einer artefaktgebundenen
  Assertion, nie mit einem Stimmungsurteil.
- **E6 — Bei Tier 0 stehen die Evals vor der SKILL.md** — sie sind dort das einzige
  Messinstrument (`references/task-patterns.md`).

## Skill-Struktur

```
skills/…/
├── SKILL.md
├── references/…
└── scripts/…            (nur, falls Tier ≥ 1)

evals/…/evals.json
tests/test_….py
```

### Task 1: …

Ein Code-Task: fünf Steps, weil der Zyklus fünf Zustände hat. Prosa wie diese steht
**vor** dem Files-Block, nie zwischen Interfaces und Step 1. In `Interfaces:` stehen
Beispielnamen statt `…` — ein Symbol muss ein Bezeichner sein, sonst ist die Task für das
Gate unbekannt.

**Files:**
- Create: `skills/…/scripts/….py`
- Test: `tests/test_….py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `fn:collect(repo)`

- [ ] **Step 1: Test schreiben** — …
- [ ] **Step 2: Rot sehen** — `pytest tests/test_….py -k …`.
- [ ] **Step 3: Implementieren** — …
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 2: …

Ein Doktrin-Task: Datei, mechanische Prüfung, Commit. Kein roter Test, aber nie ohne
den mechanischen Step.

**Files:**
- Create: `skills/…/SKILL.md`

**Interfaces:**
- Consumes: `fn:collect(repo)`
- Produces: `token:Next:`

- [ ] **Step 1: Schreiben** — …
- [ ] **Step 2: Prüfen** — `wc -l` unter 150, Sprachprüfung nach Spec 00 §4,
      Schema-Test der Evals grün.
- [ ] **Step 3: Commit.**

### Task 3: Evals

Bei einer Tier-0-Skill rückt dieser Task vor den SKILL.md-Task (E6).

**Files:**
- Create: `evals/…/evals.json`
- Create: `evals/fixtures/…/fixture.json`
- Create: `tests/test_…_evals_schema.py`

**Interfaces:**
- Consumes: `token:Next:`
- Produces: `evals_json`

- [ ] **Step 1: Fixtures** — minimal-synthetisch, die Falle enthalten, nicht Realismus
      beweisen (Spec 00 §2).
- [ ] **Step 2: Evals** — jede ID aus der Eval-Tabelle der Spec; in `notes` je Eval die
      Diskriminator-Frage: Könnte das Basismodell ohne die Skill dieselbe Ausgabe erzeugen?
- [ ] **Step 3: Schema-Test** — `evalkit.schema.load_evals` lädt sie; Commit.

### Task 4: Nachbarn

**Files:**
- Modify: `specs/Spec 00 – skill-foundation.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `token:Next:`
- Produces: (nichts Neues)

- [ ] **Step 1: Routing-Matrix** an beiden Orten — Spec 00 §5 und README.
- [ ] **Step 2: Abgrenzungssätze** der Nachbar-Skills, die auf die neue Skill zeigen
      müssen. Commit.

### Task 5: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `evals_json`
- Produces: (nichts Neues)

- [ ] **Step 1: Abschnitt** — was ungemessen bleibt und warum, mit dem konkreten Fall,
      in dem die Grenze beißt. Commit.

### Task 6: Report

**Files:**
- Create: `docs/superpowers/reports/…-report.md`

**Interfaces:**
- Consumes: `evals_json`
- Produces: (nichts Neues)

- [ ] **Step 1: Report** mit der Sektion „Was nicht gemessen wurde" — ungefahrene Evals,
      ungemessene Trigger, übersprungene Gates. Commit.

## Variante: Sammel-Task für den Anti-Zeremonie-Fall

Bei einer Änderung an ein, zwei Dateien einer bestehenden Skill ersetzen die vier
Pflicht-Tasks oben **einen** Task mit je einer Zeile pro Punkt — nicht null. Der Kopf
schrumpft mit: kein Skill-Struktur-Block, nur die betroffenen Global Constraints:

```markdown
### Task 3: Pflicht

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: (nichts Neues)

- [ ] **Step 1: Evals** — bestehende bleiben gültig, keine neue Datei.
- [ ] **Step 2: Nachbarn** — keine, oder welcher.
- [ ] **Step 3: known-limits** — ein Satz, falls sich eine Grenze verschiebt.
- [ ] **Step 4: Report** — Commit-Message genügt; Commit.
```
