# exercise-forge Implementation Plan

**Goal:** Eine Skill, die Lernaufgaben (Multiple Choice, offene Fragen, Coding,
Flashcards) zu einem Thema erzeugt und jede davon durch einen unabhängigen
Blind-Löser prüfen lässt, bevor sie den Lernenden erreicht — statt Aufgaben mit
falschen Musterlösungen oder kaputten Distraktoren auszuliefern.

**Architecture:** Drei Skripte, drei Verantwortungen. `verify_blind.py` (Tier 1)
orchestriert den Blind-Löser über die `claude`-CLI (Subprozess, wie
`evalkit.dispatch.run_agent` — hier eigenständig dupliziert, kein Import aus
`evalkit`, weil Skill-Skripte portabel und unabhängig vom Eval-Harness bleiben
müssen) und schreibt das Ergebnis in das `verification`-Feld der geprüften
Aufgabe zurück. Für Typ `coding` ruft es zusätzlich `run_coding.py` (Tier 2,
pytest) als Subprozess auf, das die Testsuite gegen Musterlösung und
Blind-Lösung laufen lässt. `export.py` (Tier 1) ist reines Rendering: liest das
Aufgaben-JSON, validiert die Pflichtfelder und schreibt ein
Markdown-Übungsblatt (Aufgaben/Lösungen getrennt) plus eine Anki-CSV. Claude
selbst erzeugt die Aufgabenobjekte nach dem Schema in
`references/task-schemas.md` — kein Generator-Skript dafür, das Autorenwerkzeug
ist die Skill-Doktrin.

Das Aufgaben-JSON ist die Schnittstelle zu Spec 14 (`learning-coach`, parallel
gebaut): `~/.skills/verified-research/research/<thema>.exercises.json`, mit
einem repo-lokalen Override unter `.skills/verified-research/research/` — legt
ein Projekt dieses Verzeichnis selbst an (oder eine Fixture bringt es mit),
gewinnt der Projekt-Pfad vor dem Home-Pfad. Das ist zugleich der Mechanismus,
der die Evals aus dem echten `$HOME` heraushält (siehe `docs/known-limits.md`,
Abschnitt Isolation: `$HOME` wird von `evalkit` nicht umgebogen).

**Tech Stack:** Python 3.13 (Stdlib) für `verify_blind.py` und `export.py`;
`run_coding.py` startet `python -m pytest` als Subprozess und degradiert
sichtbar, wenn pytest fehlt (D1 aus den Rulings — im Eval-Workspace nicht
garantiert). `claude`-CLI als Subprozess für den Blind-Löser (G2: das Urteil
ist maschinell, der Aufruf bleibt freiwillig).

**Spec:** `specs/Spec 13 – exercise-forge.md`, abgeglichen mit `specs/Spec 00 –
skill-foundation.md` und den Rulings in `rulings-final-four.md` (Abschnitte
„Für alle vier" und „Spec 13"). `brief-common.md` war im Scratchpad nicht
vorhanden (siehe Bericht, „Offene Sorgen") — Spec 00 plus die bereits gebaute
`dev-report`-Skill dienen als Ersatz-Referenz für Konventionen.

## Global Constraints

- **Kein Aufgaben-Generator-Skript.** Claude erzeugt die Aufgabenobjekte direkt
  nach Schema; die drei Skripte prüfen, orchestrieren den Blind-Check oder
  rendern — sie erfinden keine Aufgaben.
- **Blind-Gate ist Pflicht, keine Ausnahme (Constraint aus Spec 13).** Jede
  Aufgabe trägt ein `verification`-Objekt. Fehlt ein Nachweis oder weicht der
  Blind-Löser ab, ist der Status `unverified` bzw. `suspicious` — nie
  stillschweigend `verified`. Das gilt für `export.py` genauso wie für
  `verify_blind.py`: eine Aufgabe ohne (oder mit widersprüchlichem) Nachweis
  wird in Markdown und CSV sichtbar als ungeprüft markiert.
- **A4 (Rulings):** Ein nicht parsebares Blind-Ergebnis, ein fehlendes `claude`-
  CLI oder fehlendes pytest sind eigene, benannte Befunde — nie ein stilles
  „passt schon".
- **A3 (Rulings):** Kein Skript importiert fremden Code. `run_coding.py` führt
  Musterlösung und Blind-Lösung nur über eine eigene pytest-Subprozess-Grenze
  aus, nie über `import`.
- **A2 (Rulings):** Konfigurationsdateien, die Python liest, sind JSON. Das
  Aufgaben-JSON ist das einzige maschinengelesene Artefakt dieser Skill;
  `references/*.md` sind reine Vorlagen für Claude.
- **Tier-Deklaration im Kopf jedes Skripts** (Spec 00 §3), mit benannter
  Degradationszeile für `run_coding.py`.
- **Frontmatter:** nur `name` und `description`. SKILL.md ≤ 150 Zeilen.
- **Dokumentsprache Deutsch**, Bezeichner in Code und JSON englisch.
- **Artefakt-Kopfzeile (Spec 00 §1 / `docs/artifact-header.md`):** Das
  Markdown-Übungsblatt trägt die Kommentar-Kopfzeile. Die Anki-CSV bewusst
  **nicht** (begründete Ausnahme wie `handoff.md`): Anki interpretiert
  `#`-Zeilen als Import-Direktiven; eine Kopfzeile könnte den Import stören.
  Die Ausnahme wird in `docs/artifact-header.md` nach demselben Muster wie die
  `handoff.md`-Ausnahme ergänzt.

## Aufgaben-JSON-Schema (schema 1)

```
{
  "_meta": {"skill": "exercise-forge", "schema": 1, "generated": "<Kommando>"},
  "topic": "<thema>",
  "exercises": [
    {
      "id": "mc-01",
      "type": "multiple_choice" | "open_question" | "coding" | "flashcard",
      "learning_objective": "<Lernziel>",
      "bloom_level": "erinnern" | "verstehen" | "anwenden" | "analysieren",
      "difficulty": {"steps": int, "prerequisites": [str], "transfer": "near"|"far", "label": "leicht"|"mittel"|"schwer"},
      "stem": "<Aufgabenstamm>",

      // multiple_choice:
      "options": [{"text": str, "correct": bool}],

      // open_question:
      "model_solution": "<Musterantwort/Lösungsweg>",
      "criteria": [str],

      // coding:
      "model_solution": "<Python-Code, definiert das, was test_suite importiert>",
      "test_suite": "<pytest-Code, 'from solution import ...'>",

      // flashcard:
      "front": str, "back": str,

      "verification": {
        "status": "verified" | "suspicious" | "unverified",
        "method": "blind_solve_mc" | "blind_solve_open" | "blind_solve_coding" | "blind_check_flashcard" | "not_run",
        "detail": "<ein bis zwei Sätze>",
        "checked_at": "<ISO-Datum>" | null
      }
    }
  ]
}
```

Ort: `resolve_exercises_path(topic, repo)` — `repo/.skills/verified-research/research/<topic>.exercises.json`,
falls dieses Verzeichnis existiert (Projekt-Override), sonst
`~/.skills/verified-research/research/<topic>.exercises.json`. Bootstrap-Regel:
Beim ersten Anlegen kündigt die Skill den Pfad an.

---

### Task 1: `references/` — Doktrin für Autoren und Blind-Löser

**Files:** Create `skills/exercise-forge/references/task-schemas.md`,
`skills/exercise-forge/references/distractors.md`, `skills/exercise-forge/references/difficulty.md`

Kein Code — diese drei Dateien sind reine Vorlagen (A2), die Claude beim
Erzeugen der Aufgabenobjekte befolgt:

- `task-schemas.md`: die vier Typen mit Feldliste, Pflichtangaben, Beispielen;
  für `coding` explizit die Konvention „Musterlösung in `solution.py`,
  Testsuite importiert `from solution import ...`".
- `distractors.md`: MC-Distraktor-Handwerk (plausibel, eindeutig falsch, echte
  Denkfehler abbildend, kein „alle Antworten richtig") — mit der
  Blind-Gate-Konsequenz: ein Distraktor, den der Blind-Löser mit
  nachvollziehbarer Begründung wählt, gilt als kaputt.
- `difficulty.md`: der operationalisierte Vektor (Schritte × Vorwissen ×
  Transferdistanz) mit einer Tabelle, die daraus das Label ableitet — Claude
  wendet die Tabelle beim Erzeugen jeder Aufgabe an, kein Skript berechnet sie.

- [ ] Schreiben, Verweise auf Spec 13 §Approach und die Anti-Rationalisierungs-Tabelle aufnehmen.
- [ ] Commit: `feat(exercise-forge): Referenzdoktrin für Aufgabentypen, Distraktoren, Schwierigkeit`

---

### Task 2: `verify_blind.py` — Blind-Gate für MC, offene Fragen, Flashcards

**Files:** Create `skills/exercise-forge/scripts/verify_blind.py`,
`tests/test_exercise_forge_verify_blind.py`

**Interfaces:**
- `resolve_exercises_path(topic: str, repo: Path) -> Path`
- `run_agent(prompt: str, cwd: Path, *, cli="claude", timeout=300) -> Transcript` (dataclass `stdout, stderr, exit_code, timed_out` — eigenständige Kopie des `evalkit.dispatch`-Musters, kein Import)
- `build_mc_prompt(stem, options) -> str`, `parse_mc_letter(output) -> str | None`
- `verify_mc(exercise, cwd, *, cli) -> dict` (liefert das `verification`-Objekt)
- `build_open_prompt(stem) -> str`, `build_grading_prompt(stem, blind_answer, criteria) -> str`,
  `parse_grading_json(output) -> dict | None`, `verify_open(exercise, cwd, *, cli) -> dict`
- `build_flashcard_prompt(front) -> str`, `build_flashcard_grading_prompt(front, back, blind_answer) -> str`,
  `verify_flashcard(exercise, cwd, *, cli) -> dict`
- `verify_one(exercise, cwd, *, cli) -> dict` — dispatcht nach `type`; für `coding` ruft es
  `prepare_coding_blind()` (Task 3) und delegiert den Testlauf an `run_coding.py` per Subprozess.
- `load_exercises(path) / save_exercises(path, data)`, `main(argv) -> int`
  (CLI: `--exercises PATH | --topic NAME`, `--id ID | --all`, schreibt das
  Ergebnis zurück in die Datei, druckt eine Zeile pro geprüfter Aufgabe)

**Testansatz:** wie `tests/test_dispatch.py` — ein `fake-claude`-Bash-Skript
unter `tmp_path`, das feste Antworten liefert (korrekte Wahl, falsche Wahl mit
Begründung, unparsebare Antwort, Timeout, fehlendes CLI). Für die
Grading-Calls: zwei aufeinanderfolgende `fake-claude`-Aufrufe simulieren
(Blind-Antwort, dann Grading-Urteil) — das Fake-Skript liest `$1`/die
Aufrufreihenfolge oder nutzt eine Zähldatei, um bei jedem Aufruf eine andere
Antwort zu liefern.

- [ ] TDD: `resolve_exercises_path` (Projekt-Override vs. Home) zuerst.
- [ ] TDD: MC-Protokoll — korrekte Blind-Wahl → `verified`; Distraktor-Wahl →
      `suspicious` mit zitierter Begründung; unparsebar → `unverified`.
- [ ] TDD: Open-Question-Protokoll — beide Aufrufe (Blind-Antwort, Grading);
      alle Kriterien erfüllt → `verified`; plausible Antwort scheitert an einem
      Kriterium → `suspicious`; unplausible Antwort → `unverified`.
- [ ] TDD: Flashcard-Protokoll analog (Antwort trifft Rückseite → `verified`;
      driftet ab → `suspicious`).
- [ ] TDD: fehlendes `claude`-CLI → `unverified`, benannte Meldung (A4).
- [ ] TDD: `main()` — `--id` aktualisiert nur die eine Aufgabe, `--all` alle
      unverifizierten, Datei wird persistiert, `checked_at` gesetzt.
- [ ] Commit: `feat(exercise-forge): verify_blind.py prüft MC, offene Fragen und Flashcards blind`

---

### Task 3: `run_coding.py` — mechanischer Testlauf für Coding-Aufgaben

**Files:** Create `skills/exercise-forge/scripts/run_coding.py`,
`tests/test_exercise_forge_run_coding.py`

**Interfaces:**
- `pytest_available(python=sys.executable) -> bool` (Vorab-Check: `python -m
  pytest --version`, fängt `ModuleNotFoundError`/nichtnull Exit ab)
- `run_pytest_against(solution_code: str, test_code: str, workdir: Path, *, python=sys.executable) -> dict`
  — schreibt `solution.py` + `test_solution.py` nach `workdir`, führt `python -m
  pytest -q` aus, liefert `{"passed": bool, "detail": str}`
- `verify_coding(exercise: dict, blind_solution: str | None) -> dict` — liefert
  das `verification`-Objekt nach der Wahrheitstabelle aus Spec 13
  (Musterlösung fällt durch → Aufgabenfehler/`unverified`; beide bestehen →
  `verified`; nur Blind-Lösung fällt durch → `suspicious`/„Tests
  überspezifiziert?"; pytest fehlt → `unverified`, benannte Meldung)
- `main(argv) -> int` (CLI: `--exercises PATH --id ID [--blind-file PATH]`,
  druckt JSON-Ergebnis auf stdout, aktualisiert die Datei nur mit `--update`)

**Testansatz:** echtes `pytest` ist im `.venv` dieses Repos vorhanden (Rulings
A1) — Happy-Path-Tests laufen gegen echte Mini-Lösungen/Tests. Die
Degradationszeile wird durch einen `python`-Stellvertreter ohne pytest-Modul
simuliert (z. B. `sys.executable` durch ein Fake-Skript ersetzen, das
`ModuleNotFoundError`-artiges Verhalten nachstellt) oder durch Monkeypatchen
von `pytest_available`.

- [ ] TDD: Musterlösung besteht eigene Tests → `passed=True`.
- [ ] TDD: überspezifizierte Tests + korrekte Blind-Lösung → `suspicious`.
- [ ] TDD: Musterlösung fällt durch → `unverified`, Meldung nennt „Musterlösung".
- [ ] TDD: pytest nicht verfügbar → `unverified`, benannte Meldung, kein Testlauf versucht.
- [ ] Commit: `feat(exercise-forge): run_coding.py testet Muster- und Blind-Lösung mechanisch`

---

### Task 4: `verify_blind.py` — Coding-Anbindung

**Files:** Modify `skills/exercise-forge/scripts/verify_blind.py`, `tests/test_exercise_forge_verify_blind.py`

**Interfaces:**
- `build_coding_prompt(stem, test_suite) -> str`, `extract_code_block(output) -> str | None`
- `verify_coding_task(exercise, cwd, *, cli, python) -> dict` — holt die
  Blind-Lösung per `run_agent`, ruft `run_coding.py` als Subprozess auf
  (`subprocess.run([python, str(run_coding_path), ...], capture_output=True)`),
  parst dessen JSON-Ausgabe.
- `verify_one` um den `coding`-Zweig ergänzt.

- [ ] TDD: Blind-Code wird aus einem Codefence extrahiert.
- [ ] TDD: `verify_coding_task` gibt das `verification`-Objekt von `run_coding.py` durchgereicht zurück (inkl. `suspicious`/`unverified`-Fälle über einen Fake-`run_coding.py`-Stellvertreter oder echten Aufruf mit Fixture-Aufgabe).
- [ ] Commit: `feat(exercise-forge): verify_blind.py bindet run_coding.py für Coding-Aufgaben an`

---

### Task 5: `export.py` — Markdown-Übungsblatt und Anki-CSV

**Files:** Create `skills/exercise-forge/scripts/export.py`, `tests/test_exercise_forge_export.py`

**Interfaces:**
- `resolve_exercises_path` (dupliziert aus Task 2 — Skripte bleiben eigenständig, A3-Konvention)
- `validate_exercise(ex: dict) -> list[str]` — Liste fehlender/falscher Pflichtfelder (leer = ok)
- `render_markdown(topic: str, exercises: list[dict]) -> str` — Kopfzeile,
  Abschnitt „Aufgaben" (ohne verratene Lösung), Abschnitt „Lösungen" getrennt;
  jede Aufgabe trägt sichtbar `[geprüft]` oder `[UNGEPRÜFT: <Grund>]` in
  beiden Abschnitten.
- `render_anki_csv(exercises: list[dict]) -> str` — Spalten `front,back,tags`;
  `tags` enthält immer `verified` oder `unverified` (nie stillschweigend
  weggelassen, siehe D4/Nutzervorgabe).
- `main(argv) -> int` (CLI: `--exercises PATH | --topic NAME`, `--out-dir
  docs/exercises` Default, schreibt `<out-dir>/<topic>.md` und
  `<out-dir>/<topic>-anki.csv`)

- [ ] TDD: `validate_exercise` erkennt fehlendes `difficulty`/`verification`/typspezifische Felder.
- [ ] TDD: `render_markdown` trennt Aufgaben/Lösungen, markiert eine Aufgabe ohne `verification` (oder mit `status: unverified`) sichtbar als ungeprüft — **nie** `[geprüft]`.
- [ ] TDD: `render_anki_csv` — MC verdeckt die Optionen auf der Vorderseite, Flashcards direkt, Tags tragen den Verifikationsstatus.
- [ ] TDD: `main()` schreibt beide Dateien, Markdown trägt die Artefakt-Kopfzeile (Schema aus `docs/artifact-header.md`), CSV bewusst nicht.
- [ ] `docs/artifact-header.md` um die begründete CSV-Ausnahme ergänzen (nach dem `handoff.md`-Muster).
- [ ] Commit: `feat(exercise-forge): export.py rendert Markdown-Übungsblatt und Anki-CSV`

---

### Task 6: SKILL.md

**Files:** Create `skills/exercise-forge/SKILL.md`

Workflow (Lernziel/Bloom klären → Typ wählen → Aufgabe nach Schema erzeugen →
Blind-Gate → Export), Contract (Blind-Gate ist Pflicht, keine Aufgabe ohne
`verification` verlässt die Skill als „geprüft"), Anti-Rationalisierungs-Tabelle
aus Spec 13, Abgrenzung zu `learning-coach` (Zyklus 14 — das Aufgaben-JSON ist
die Schnittstelle, nicht der Session-Zustand) und `visual-summary`. ≤ 150 Zeilen,
Frontmatter nur `name`/`description` mit expliziter Abgrenzungsklausel.

- [ ] Schreiben, Zeilenzahl prüfen (`wc -l`).
- [ ] Commit: `feat(exercise-forge): SKILL.md mit Blind-Gate-Workflow und Contract`

---

### Task 7: Evals schreiben (nicht ausführen)

**Files:** Create `evals/exercise-forge/evals.json`, ggf.
`evals/fixtures/exercise-forge-*` (nur falls eine Fixture Artefakte im Repo
braucht, die keine bestehende Fixture liefert — Rulings A6: `"git": true` für
alles, dessen Artefakte im Workspace erwartet werden).

Fünf Evals aus Spec 13 §Approach, an eigene Artefakte gehängt (A6):
1. **Anti-Zeremonie (Pflicht, Spec 00 §2):** eine einzelne Flashcard-Anfrage
   erzeugt kein aufgeblähtes Set — `class: contract`, prüft Anzahl/Kürze über
   die geschriebene `exercises.json`.
2. **MC-Distraktor-Falle:** eine vorbereitete Aufgabe mit einem versehentlich
   korrekten Distraktor — fängt das Blind-Gate sie (`verification.status !=
   verified` im Ergebnis)? `class: behavior` (Judge, weil der Blind-Lauf selbst
   nicht deterministisch mechanisch prüfbar ist).
3. **Überspezifizierte Coding-Tests:** `class: behavior`.
4. **Zu enge Kriterien bei offener Frage:** `class: behavior`.
5. **„Eine Stufe schwerer":** `class: behavior`, Judge prüft, ob sich der
   Schwierigkeits-Vektor nachvollziehbar ändert.

Jede `evals.json`-Assertion zeigt auf das `exercises.json`/Markdown/CSV, das
**nur** `exercise-forge` erzeugt (A6) — kein Assertion-Pfad, den eine andere
installierte Skill ebenso treffen könnte.

**Wichtig:** Diese Evals werden **geschrieben, nicht ausgeführt** — ein realer
Lauf würde verschachtelte `claude -p`-Aufrufe auslösen und echte Kosten
verursachen. `evalkit.schema.load_evals()` validiert das Schema aber, das läuft
ohne Agentenlauf (`tests/test_exercise_forge_evals_schema.py`: `load_evals()`
auf die neue Datei anwenden, keine `EvalSchemaError`).

- [ ] `evals/exercise-forge/evals.json` schreiben.
- [ ] `tests/test_exercise_forge_evals_schema.py`: `evalkit.schema.load_evals()` lädt die Datei fehlerfrei.
- [ ] Commit: `feat(exercise-forge): fünf Evals inkl. Pflicht-Anti-Zeremonie-Fall (ungelaufen)`

---

### Task 8: Vollständige Testsuite, Bericht

- [ ] `.venv/bin/pytest -q` — alle bestehenden plus neuen Tests grün.
- [ ] `docs/superpowers/reports/exercise-forge-report.md` schreiben: Umsetzung,
  eigene Design-Entscheidungen (Projekt-Override-Mechanismus, Export-Zielpfad
  `docs/exercises/`, CSV-Kopfzeilen-Ausnahme), offene Sorgen (fehlendes
  `brief-common.md`, ungelaufene Evals, Blind-Gate-Grenzen analog zu
  `docs/known-limits.md`).
- [ ] Commit: `docs(exercise-forge): Implementierungsbericht`
