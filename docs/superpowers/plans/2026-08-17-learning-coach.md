# learning-coach Implementation Plan

**Goal:** Eine Skill, die Lernen als festen Loop erzwingt statt als Erklär-Persona:
Abruf vor Input, harte Hinweis-Leiter, eine Lernstandsdatei, die Fälligkeit trägt statt
sie zu erraten.

**Architecture:** `due_topics.py` (Tier 1, nur Stdlib) ist der einzige Code-Teil. Er
liest `learner.md`, berechnet fällige Themen aus dem dort stehenden Datum (nicht aus
Vermutung) und liefert einen deterministischen Vorschlag für das nächste Spacing-
Intervall. Das eigentliche Führen der Session — Abruf-Quiz, Fehleranalyse, Hinweis-
Leiter, Selbsterklärung, Datei-Update — ist Doktrin in SKILL.md, kein Skript: Ein
Sokratischer Dialog lässt sich nicht durch ein Python-Skript ersetzen, nur durch harte
Regeln stützen, die ein Skript mechanisch nachprüfen kann.

**Tech Stack:** Python 3.13 (Stdlib), Markdown-Datei als Persistenz, kein DB/YAML.

**Spec:** `specs/Spec 14 – learning-coach.md`, gebunden an
`specs/Spec 00 – skill-foundation.md`. Entscheidungen aus
`rulings-final-four.md` (Abschnitte „Für alle vier" und „Spec 14") sind bindend.
`brief-common.md` (Fundament-Contract/Arbeitsweise) war unter dem angegebenen Pfad
nicht auffindbar (nicht im Repo, nicht im Scratchpad) — als Ersatz dienen
`specs/Spec 00 – skill-foundation.md` (das Konventions-Dokument, auf das die Rulings
mehrfach verweisen) und die bereits gebauten Geschwister-Skills (`dev-report`,
`verified-research`) als gelebte Konvention. Das ist im Abschlussbericht vermerkt.

## Global Constraints

- **E1.** `due_topics.py` ist Tier 1 (Stdlib only).
- **E2.** `learner.md` liegt unter `~/.skills/learning-coach/learner.md`, projektlokal
  überschreibbar nach demselben Muster wie `verified-research/scripts/registry.py::resolve_base_dir`
  (Override greift, sobald `.skills/learning-coach/` im Projekt existiert). Eine Datei,
  kein Themenbaum (A5). Artefakt-Kopfzeile nach `docs/artifact-header.md`.
- **E3.** Schnittstelle zu exercise-forge (Spec 13, wird parallel gebaut): ausschließlich
  der Pfad `~/.skills/verified-research/research/<thema>.exercises.json` (projektlokal
  nach demselben Muster). `due_topics.py` prüft nur **Existenz** dieser Datei, parst sie
  nicht — Feldnamen des Aufgaben-Schemas sind nicht bekannt (A4-Vorsicht: was nicht
  sicher bekannt ist, wird nicht angenommen). Fehlt die Datei, ist das normal; SKILL.md
  schlägt dann exercise-forge vor, wörtlich mit der Phrase „Keine verifizierten Aufgaben
  gefunden", damit das mechanisch prüfbar bleibt (A6/Konsumenten-Regel).
- **E4.** Fälligkeit aus `learner.md` berechnen. Fehlt oder ist ein Datum unlesbar, gilt
  das Thema als fällig — nie stillschweigend als „nicht fällig" behandeln.
- **A1–A6** (siehe `rulings-final-four.md`): Tier 1 bevorzugt, JSON statt YAML für
  Skript-lesbare Daten, kein Import fremden Codes nötig hier, Null-Ergebnisse aus
  nicht-leerer Eingabe sind ein Befund, flach bleiben ohne Auto-Umgliederung, Pflicht-
  Anti-Zeremonie-Eval mit artefaktgebundenen Assertions.
- **Frontmatter:** nur `name` und `description`. SKILL.md ≤ 150 Zeilen.
- **Dokumentsprache Deutsch**, Bezeichner in Code/JSON/Markdown-Schlüsselwörtern englisch
  wo etabliert (z. B. `_meta`, Feldnamen bleiben aber deutsch, weil `learner.md` ein
  vom Menschen editiertes Wissens-Artefakt ist, kein Interop-JSON — Abweichung von der
  reinen "englische Bezeichner"-Regel aus Spec 00, begründet im Bericht).

## Offene Fragen aus Spec 14, hier entschieden

- **Granularität der Themen:** eine Ebene, freier Slug (`## <slug>: <Name>`) — der
  Nutzer wählt selbst, ob das Konzept- oder Gebiets-Ebene ist. Keine erzwungene
  Zweistufigkeit, weil das echte Themen vor Inhalt erfinden hieße (A5-Geist).
- **Herabstufung bei Fehlversuchen:** ein falscher Abruf senkt den Grad sofort um genau
  eine Stufe (kein Toleranz-Zähler) — konsistent mit „im Zweifel erinnern statt
  vergessen" (E4) und einfacher als ein Fehlversuchs-Zähler, den `learner.md` ohnehin
  nicht separat führt.

## Skill-Struktur

```
skills/learning-coach/
├── SKILL.md
├── references/
│   ├── learner-schema.md
│   ├── hint-ladder.md
│   └── methods.md
├── assets/
│   └── learner-template.md
└── scripts/
    └── due_topics.py
evals/learning-coach/evals.json
evals/fixtures/lc-*/               (mehrere, je mit .skills/learning-coach/learner.md)
tests/test_learning_coach_due_topics.py
docs/superpowers/reports/learning-coach-report.md
```

---

### Task 1: `due_topics.py` — Parsen, Fälligkeit, Intervall

**Interfaces:**
- `resolve_base_dir(repo: Path, skill_name: str, home: Path | None = None) -> tuple[Path, bool]`
  — generische Fassung von `registry.py::resolve_base_dir`, parametrisiert über den
  Skill-Namen (gebraucht für `learning-coach` UND für `verified-research`, siehe E3).
- `learner_path_for(base_dir: Path) -> Path`
- `ensure_learner(repo, assets_path, home=None) -> tuple[Path, bool]` — Bootstrap wie
  `registry.py::ensure_registry`, kündigt Neuanlage an.
- `Topic` (dataclass): `slug, name, gebiet, grade, last_query, next_due, typical_errors,
  open_questions, warnings`.
- `parse_learner(text: str) -> tuple[list[Topic], list[str]]` — tolerant: fehlende/
  unlesbare Felder erzeugen Warnungen, keinen Absturz (A4).
- `is_due(topic: Topic, today: date) -> bool`
- `due_topics(topics: list[Topic], today: date) -> list[Topic]` — sortiert, am
  überfälligsten zuerst; `next_due=None` zählt als „heute fällig".
- `exercises_path_for(repo, slug, home=None) -> Path` — Pfad nach E3, keine Existenzprüfung
  eingebaut (Aufrufer prüft).
- `INTERVAL_DAYS: dict[int, int]` — `{0: 0, 1: 1, 2: 3, 3: 7, 4: 14}`.
- `next_grade(grade: int, result: str) -> int`
- `next_interval(grade: int, result: str, today: date) -> tuple[int, date]`
- `main(argv) -> int` mit Subcommands `due` und `interval`.

- [ ] Tests zuerst (`tests/test_learning_coach_due_topics.py`): Parsing (vollständiges
  Thema, fehlendes Datum, unlesbares Datum, mehrere Themen), Fälligkeitssortierung,
  `resolve_base_dir` projektlokal vs. Home, Bootstrap kündigt an und kopiert Template,
  Intervall-Tabelle (Erfolg erhöht, Fehler senkt, Grenzen 0/4 geklemmt), CLI `due`
  und `interval` End-to-End über `main()`.
- [ ] Implementieren, bis grün.
- [ ] Commit.

### Task 2: SKILL.md + references + assets

- [ ] `assets/learner-template.md` — leere Datei mit Kopfzeile und Titel, keine Themen.
- [ ] `references/learner-schema.md` — exaktes Feldformat, Beispiel-Thema, Beherrschungsgrad
  0–4 operationalisiert.
- [ ] `references/hint-ladder.md` — vier Stufen, Formulierungsbeispiele je Aufgabentyp
  (MC, offene Frage, Coding, Flashcard), Rück-Erklärungspflicht bei Stufe 4.
- [ ] `references/methods.md` — Abrufübung-Doktrin, die Intervall-Tabelle mit Begründung,
  Fehleranalyse-Vorgehen, Interleaving-Hinweis. Destilliert (Spec: „keine
  Lernpsychologie-Vorlesung").
- [ ] `SKILL.md` — Session-Loop (voll + Kurzform), harte Hinweis-Leiter, Contract
  (inkl. „Keine verifizierten Aufgaben gefunden"-Pflichtphrase, Update-am-Ende-Pflicht,
  Tier-0-Pfad), Anti-Rationalisierungs-Tabelle aus Spec 14, Abgrenzung zu exercise-forge/
  verified-research/visual-summary.
- [ ] Commit.

### Task 3: Evals + Fixtures (schreiben, nicht ausführen)

Acht Evals, jede Assertion hängt an `.skills/learning-coach/learner.md` (projektlokal,
damit sie im Workspace bleibt — A6/known-limits „Isolation") oder an einer wörtlichen,
SKILL.md-mandatierten Phrase:

1. **Anti-Zeremonie (Pflicht, contract):** nichts fällig → `learner.md` bleibt
   `file_unchanged`, Antwort sagt das offen, keine erfundene Quiz-Session.
2. **Kurzform-Update (contract):** ein fälliges Thema, 10-Minuten-Bitte →
   `learner.md` NICHT `file_unchanged` (Update fand statt).
3. **Lösungs-Wunsch mitten in der Aufgabe (behavior/judge):** keine nackte Lösung ohne
   Rück-Erklärungsaufforderung.
4. **Frust-Trap (behavior/judge):** eine Stufe weiter, kein Leiter-Kollaps.
5. **Session-Start mit mehreren fälligen Themen (behavior/judge):** Abruf-Quiz zuerst,
   nicht neuer Stoff zuerst.
6. **Abruptes Session-Ende (contract):** Update wird trotzdem nachgeholt —
   `learner.md` NICHT `file_unchanged`.
7. **Fehlende Aufgaben-Datei (contract):** exakte Phrase „Keine verifizierten Aufgaben
   gefunden" erscheint, kein Fehlerton.
8. **Fehleranalyse (behavior/judge):** der geäußerte Denkfehler landet inhaltlich (nicht
   nur „Fehler gemacht") in „Typische Fehler".

- [ ] Fixtures unter `evals/fixtures/lc-*/` mit `"git": true` (A6) und vorab existierendem
  `.skills/learning-coach/learner.md`, damit `resolve_base_dir` projektlokal auflöst und
  kein Zugriff auf das echte `$HOME` des Aufrufers stattfindet (known-limits „Isolation").
- [ ] `evals/learning-coach/evals.json` gegen `evalkit.schema.load_evals` lokal validieren
  (Unit-Test oder `python -c`), aber `run_evals.py` nicht ausführen.
- [ ] Commit.

### Task 4: Report

- [ ] `docs/superpowers/reports/learning-coach-report.md` — was gebaut wurde, jede
  Ruling einzeln abgehakt, eigene Entscheidungen benannt, was nicht verifiziert werden
  konnte, das fehlende `brief-common.md` vermerkt.
- [ ] Volle Testsuite (`pytest -q`) grün bestätigen, Ergebnis im Report.
- [ ] Commit.
