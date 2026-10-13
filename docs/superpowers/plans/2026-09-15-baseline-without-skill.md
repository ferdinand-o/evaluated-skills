<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# Baseline ohne Skill Implementation Plan

**Goal:** Ein Eval, der ohne installierte Skill genauso grün ist, wird als „misst
nichts" sichtbar — und kein Eval-Ergebnis entsteht mehr, ohne dass der Runner weiß,
ob der Agent die Skill überhaupt sah.

**Architecture:** Tier 1, nur Stdlib. Der Code liegt im geteilten Harness:
`evalkit/dispatch.py` liest das `skills`-Feld aus dem `system.init`-Ereignis des
stream-json-Transcripts, `evalkit/workspace.py` baut einen Workspace ohne Skill,
`evalkit/report.py` kennt einen Baseline-Modus mit umgekehrtem Exit-Code, und
`evalkit/runner.py` verbindet das zu `run_evals.py --without-skill` plus einer
Sichtbarkeitsprüfung in beide Richtungen. Kein neues Skript unter `skills/`; die
Doktrin dazu steht in `skill-forge` (Schritt 5, `references/evals.md`, Report-Gerüst).

**Tech Stack:** Python 3.13 Stdlib für Harness und Tests; Markdown für Skill,
References, Report.

**Spec:** `specs/Spec 18 – baseline-without-skill.md`

## Global Constraints

- **E1 — Tier 1** (Spec 00 §3): `evalkit` bleibt Stdlib; ohne `skills`-Feld im
  Transcript bleibt das Verdikt wie heute und der Report sagt „Sichtbarkeit ungeprüft".
  Ein übersprungenes Gate meldet nie Erfolg.
- **E2 — Gate-Sprache** (Spec 00 §4): `skill-forge` *verlangt* den Baseline-Lauf (G1),
  der Runner *meldet* (G2). Nichts blockiert.
- **E3 — Kein Artefakt auf Platte**: der Report bleibt stdout; keine Kopfzeile nötig.
- **E4 — SKILL.md ≤ 150 Zeilen** (`skill-forge` hat 107).
- **E5 — `evals_due: true` ist erwartet**, weil `references/evals.md` das Wort
  „Diskriminator" in einer geänderten Zeile trägt; die fünf bestehenden Evals werden
  gefahren, keine neue geschrieben. Zeile 100 der SKILL.md (`expected_output`) bleibt
  unberührt, damit `evals_due_reason` genau den einen erwarteten Treffer nennt.
- **E6 — Abwärtskompatibel**: alle bestehenden Tests in `tests/test_dispatch.py`,
  `test_workspace.py`, `test_runner.py`, `test_report.py` bleiben ohne Änderung grün.

## Skill-Struktur

```
skills/skill-forge/
├── SKILL.md                         Schritt 5 ergänzt
├── references/evals.md              „Baseline ohne Skill": Anleitung statt Forderung
└── assets/skill-template/report.md  Baseline in „Was gemessen wurde" und „Was nicht gemessen wurde"

run_evals.py, evalkit/runner.py, evalkit/dispatch.py, evalkit/workspace.py, evalkit/report.py
tests/test_dispatch.py, tests/test_workspace.py, tests/test_report.py, tests/test_runner.py
```

### Task 1: visible_skills aus dem init-Ereignis

Der Parser neben `assistant_text`: derselbe zeilenweise JSON-Durchlauf, der das
`skills`-Feld des Ereignisses `type: system, subtype: init` liefert — oder `None`,
wenn es kein solches Ereignis oder kein Feld gibt. `Transcript` trägt das Ergebnis.

**Files:**
- Modify: `evalkit/dispatch.py`
- Test: `tests/test_dispatch.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `fn:visible_skills(raw)`, `skills`

- [x] **Step 1: Tests schreiben** — `skills`-Feld hinter führenden Fremd-Ereignissen
      (`active_goal`, `autocompact_state`) wird als `frozenset` gelesen; Stream ohne
      `init` liefert `None`; `init` ohne Feld liefert `None`; kaputte Zeilen werden
      übersprungen; `run_agent` füllt `Transcript.skills` aus dem Stream und lässt es
      bei einem Klartext-Fake-CLI auf `None`.
- [x] **Step 2: Rot sehen** — `pytest tests/test_dispatch.py -k visible_skills`.
- [x] **Step 3: Implementieren** — `visible_skills(raw) -> frozenset[str] | None`;
      `Transcript.skills: frozenset[str] | None = None`; `run_agent` setzt es in beiden
      Rückgabepfaden (normal und Timeout).
- [x] **Step 4: Grün sehen**, volle Suite.
- [x] **Step 5: Commit.**

### Task 2: Workspace ohne Skill

**Files:**
- Modify: `evalkit/workspace.py`
- Test: `tests/test_workspace.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `fn:prepare(dest, skill_dir, fixture_dir)`

- [x] **Step 1: Tests schreiben** — `prepare(dest, None, fixture)` legt kein
      `.claude/skills/` an, die Baseline enthält keinen Schlüssel mit diesem Präfix,
      die Fixture liegt wie bisher an der Wurzel; `prepare(dest, None, None)` liefert
      einen leeren Workspace; ein fehlendes Skill-Verzeichnis wirft weiterhin.
- [x] **Step 2: Rot sehen** — `pytest tests/test_workspace.py -k without_skill`.
- [x] **Step 3: Implementieren** — `skill_dir: Path | None`; die SKILL.md-Prüfung und
      der Kopierschritt laufen nur mit Skill; Git-Baseline und Snapshot unverändert.
- [x] **Step 4: Grün sehen**, volle Suite.
- [x] **Step 5: Commit.**

### Task 3: Baseline-Modus im Report

**Files:**
- Modify: `evalkit/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `baseline`, `fn:format_report(results)`, `fn:exit_code(results)`

- [x] **Step 1: Tests schreiben** — `EvalResult(baseline=True)` wird als
      `[GRÜN OHNE SKILL] <id> — misst nichts` bzw. `[ROT OHNE SKILL] <id>` gerendert,
      SKIP bleibt SKIP; die Summenzeile zählt „grün ohne Skill — messen nichts", „rot
      ohne Skill", „übersprungen"; `exit_code` liefert 1, sobald ein Baseline-Ergebnis
      grün ist, 0 bei nur roten, 2 bei `skipped` mit `failures`; Ergebnisse ohne
      `baseline` verhalten sich wie heute (bestehende Tests unverändert).
- [x] **Step 2: Rot sehen** — `pytest tests/test_report.py -k baseline`.
- [x] **Step 3: Implementieren** — Feld `baseline: bool = False` an `EvalResult`;
      `format_report` und `exit_code` lesen es; keine neuen Parameter.
- [x] **Step 4: Grün sehen**, volle Suite.
- [x] **Step 5: Commit.**

### Task 4: --without-skill und Sichtbarkeitsprüfung im Runner

**Files:**
- Modify: `evalkit/runner.py`
- Modify: `run_evals.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `fn:visible_skills(raw)`, `skills`, `fn:prepare(dest, skill_dir, fixture_dir)`, `baseline`
- Produces: `fn:run_one(ev, skill_name, skill_dir, fixtures_dir, cli, timeout, keep, without_skill)`, `token:--without-skill`

- [x] **Step 1: Tests schreiben** — Fake-CLI, das ein `init`-Ereignis mit dem
      Skill-Namen schreibt, liefert mit `without_skill=True` ein `skipped`-Ergebnis mit
      „Baseline unmöglich" in `failures`; ein `init`-Ereignis ohne den Namen lässt
      `grade()` laufen und setzt `baseline=True`; im Normalmodus ist ein fehlender Name
      `skipped` mit „Skill nicht sichtbar" in `failures`; ein Klartext-Fake-CLI ohne
      Feld ergibt in beiden Modi das Verdikt wie heute mit Note „Sichtbarkeit
      ungeprüft"; `main(["--without-skill", …])` gibt mit einem grünen Baseline-Lauf
      Exit 1 zurück; Judge-Aufrufe bleiben unberührt (kein Judge-Transcript wird
      geprüft).
- [x] **Step 2: Rot sehen** — `pytest tests/test_runner.py -k "without_skill or visible"`.
- [x] **Step 3: Implementieren** — `run_one` bekommt `skill_name` und
      `without_skill`; `prepare(None, …)` im Baseline-Modus; nach `run_agent` die
      Sichtbarkeitsprüfung auf `transcript.skills` des Eval-Agenten, vor dem Judge;
      `EvalResult(…, baseline=without_skill)`; `main` mit `--without-skill`, Hinweis
      in der Kopfzeile des Laufs („ohne Skill — grün heißt: misst nichts"); Docstring
      von `run_evals.py` um den Aufruf ergänzt.
- [x] **Step 4: Grün sehen**, volle Suite; einmal `python run_evals.py --help` lesen.
- [x] **Step 5: Commit.**

### Task 5: SKILL.md und references von skill-forge

Doktrin-Task: Schritt 5 bekommt den Baseline-Lauf, `references/evals.md` wird von der
Forderung zur Anleitung, das Report-Gerüst nennt die Baseline an beiden Stellen. Die
Ergänzung in Schritt 5 kommt als neue Zeilen hinter „Vor jeder Fix-Runde ein zweiter
Lauf." und trägt weder „Diskriminator" noch `"id": "anti-ceremony-` noch
`expected_output`.

**Files:**
- Modify: `skills/skill-forge/SKILL.md`
- Modify: `skills/skill-forge/references/evals.md`
- Modify: `skills/skill-forge/assets/skill-template/report.md`

**Interfaces:**
- Consumes: `token:--without-skill`
- Produces: `token:GRÜN OHNE SKILL`

- [x] **Step 1: SKILL.md** — Schritt 5: derselbe Aufruf mit `--without-skill`; ein Eval,
      der ohne Skill grün ist, wird umgebaut oder gestrichen; der Report nennt je Eval
      beide Läufe; ein grüner Lauf ohne Skill zeigt die Lücke, ein roter beweist nichts.
- [x] **Step 2: references/evals.md** — Abschnitt „Baseline ohne Skill": Aufruf, Lesart,
      was mit einem grünen Eval passiert (umbauen an ein Artefakt oder streichen), Stichprobe.
- [x] **Step 3: report.md** — „Was gemessen wurde": Zeile „Baseline: … Evals mit
      `--without-skill` gefahren, … davon grün"; „Was nicht gemessen wurde": die
      Baseline, wenn sie nicht lief.
- [x] **Step 4: Prüfen** — `wc -l` unter 150;
      `python skills/skill-forge/scripts/lint_skill.py skills/skill-forge --base main`
      meldet keinen neuen Befund und `evals_due: true` mit genau einem Grund
      (`(?i)diskriminator` in `references/evals.md`); Commit.

### Task 6: Evals

Keine neue Eval-Datei: Das Schema kann den Harness nicht fahren, und der Contract von
`skill-forge` ist unverändert. Gefahren werden die fünf bestehenden Evals, weil
`evals_due: true` ist — außerhalb des Harness (root, `bypassPermissions`), wie beim
dritten Lauf im Report.

**Files:**
- Test: `tests/test_skill_forge_evals_schema.py`

**Interfaces:**
- Consumes: `token:GRÜN OHNE SKILL`
- Produces: `evals_json`

- [x] **Step 1: Schema** — `evals/skill-forge/evals.json` unverändert, Schema-Test grün.
- [x] **Step 2: Fahren** — je Eval ein Subagent mit frischem Kontext in einem
      Workspace aus `prepare()`, bewertet mit `grade()`; Ergebnis je Eval notiert
      (`anti-ceremony-one-sentence-change-lints-only`, `token-change-makes-evals-due`,
      `gate-word-without-hook-is-reported`, `missing-anti-ceremony-eval-is-reported`,
      `routing-new-skill-gets-house-evals`).
- [x] **Step 3: Zweiter Lauf vor jeder Fix-Runde**, falls einer rot ist; Commit der
      Ergebnisse im Report (Task 9).

### Task 7: Nachbarn

**Files:**
- Modify: `specs/Spec 00 – skill-foundation.md`
- Modify: `README.md`
- Modify: `skills/skill-forge/SKILL.md`

**Interfaces:**
- Consumes: `token:--without-skill`
- Produces: (nichts Neues)

- [x] **Step 1: Spec 00 §2** — ein Satz zur Baseline hinter „Bestanden = …", und der
      Runner-Pfad `run_evals.py` statt `evals/run_evals.py` im Baum.
- [x] **Step 2: README** — Aufrufzeile `run_evals.py --skill handoff --without-skill`
      mit der Lesart des Exit-Codes.
- [x] **Step 3: Abgrenzung skill-forge** — eine eigene Zeile hinter dem
      skill-creator-Absatz: seine Baseline-Läufe sind Subagenten, nicht der Harness.
      Zeile mit `expected_output` unverändert. Commit.

### Task 8: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `evals_json`
- Produces: (nichts Neues)

- [x] **Step 1: Abschnitte** — `## skill-forge`: „Gefordert, nicht gebaut" durch die
      Grenzen des Gebauten ersetzen (Feld nur mit CLI 2.1.272 gemessen; Profil-Skills
      auf dem Rechner des Nutzers ungemessen; ein roter Lauf ohne Skill beweist nichts);
      „Isolation": das `skills`-Feld als Messstelle, 19 statt 16 globale Skills am
      2026-09-15. Commit.

### Task 9: Report

**Files:**
- Modify: `docs/superpowers/reports/skill-forge-report.md`

**Interfaces:**
- Consumes: `evals_json`
- Produces: (nichts Neues)

- [x] **Step 1: Folgerunde** — Abschnitt „Folgerunde: Baseline ohne Skill" mit dem
      `lint.json`-Grund für `evals_due`, den Ergebnissen der fünf Läufe und der
      Sektion „Was nicht gemessen wurde" (der Flag selbst lief nicht im Harness). Commit.
