# testing-strategy Implementation Plan

**Goal:** Eine Kern-plus-Adapter-Skill für Testplanung: `detect_stack.py` klassifiziert
das Repo, eine harte Routing-Tabelle in der SKILL.md bestimmt genau eine
Adapter-Referenz, und ein verbindlicher Test-Plan-Block macht die Entscheidung vor
dem ersten Test sichtbar. Doktrin: Regressions-Fang pro Wartungskosten, nicht
Coverage-Prozente.

**Spec:** `specs/Spec 05 – testing-strategy.md`, gebunden an `specs/Spec 00 –
skill-foundation.md`. Auftragsentscheidungen R4–R7 aus dem Dispatch sind bindend,
siehe unten.

## Bindende Entscheidungen (nicht verhandelbar)

- **R4:** `test-design.md` trägt Python und TypeScript vollständig. Java erscheint
  nur in `legacy-monolith.md`.
- **R5:** `detect_stack.py` klassifiziert bei jedem expliziten Aufruf neu.
  `.skills/cache/detect_stack.json` ist reine Ephemera, nie Voraussetzung.
- **R6:** Die Playwright-Fixture in `chrome-extension.md` wird geschrieben, aber
  nirgends als „getestet"/„erprobt" bezeichnet. `docs/known-limits.md` bekommt
  den Hinweis.
- **R7:** `detect_stack.py` versucht zuerst Tier 1. Ergebnis dieser Prüfung (siehe
  unten): **Tier 1 reicht** — keine PyPI-Abhängigkeit nötig. Manifest-Dateien
  werden über stdlib `json` gelesen; `pyproject.toml` wird als Text nach
  Substrings durchsucht (keine echte TOML-Semantik nötig, da nur Namens- und
  Abschnitts-Erkennung gebraucht wird — vermeidet zusätzlich eine
  Python-Versionsabhängigkeit auf `tomllib`, das erst ab 3.11 in der Stdlib ist).
  Git-Aufrufe über die `subprocess`-CLI gelten hier wie bei `dev-report` als
  Tier 1 (etablierter Präzedenzfall in `collect.py`).

## Architektur

```
skills/testing-strategy/
├── SKILL.md                 Doktrin, Routing-Tabelle, Test-Plan-Contract, Promotion-Regel
├── references/
│   ├── test-design.md       querliegend: gute Tests, Anti-Patterns, Flakiness (Python + TS)
│   ├── legacy-monolith.md   Characterization/Golden-Master, Seams, Approval-Tests (+ Java)
│   ├── rest-api.md          Contract-Tests, Schema-Validierung, Testcontainers
│   ├── chrome-extension.md  vier Schichten, Playwright-Fixture (ungetestet, siehe R6)
│   ├── frontend-spa.md      Component-/E2E-Schnitt, Testing-Library-Disziplin
│   └── cli-library.md       Snapshot von CLI-Output, Public-API-Tests
└── scripts/
    └── detect_stack.py      Tier 1: Repo-Klassifikation → .skills/cache/detect_stack.json
tests/test_testing_strategy_detect.py
evals/testing-strategy/evals.json
evals/fixtures/legacy-monolith/       (kanonischer Name aus Spec 00 §2)
evals/fixtures/chrome-extension/      (kanonischer Name aus Spec 00 §2)
evals/fixtures/ambiguous-extension-api/
evals/fixtures/well-tested-repo/
```

## detect_stack.py — Design

Signale, pro Ort (Repo-Wurzel plus direkte Unterordner, Tiefe 1 — deckt die
verlangten Monorepo-Fälle ab, ohne unbeschränkt zu rekursieren):

| Signal | Typ-Punkte | Quelle |
| --- | --- | --- |
| `manifest.json` mit Schlüssel `manifest_version` | chrome-extension +3 | JSON |
| `openapi.yaml/yml`, `swagger.*` | rest-api +3 | Datei-Existenz |
| Router-Muster (`@app.get(`, `@RestController`, …) in bekannten Entry-Files | rest-api +2 | Text-Scan, begrenzte Dateiliste |
| Flask/FastAPI/Django/Express/… in `package.json`/`pyproject.toml`/`requirements.txt`/`pom.xml` | rest-api +1 | Substring |
| React/Vue/Svelte/Angular in `package.json` | frontend-spa +2 | Substring |
| `bin`-Feld in `package.json`, `[project.scripts]` in `pyproject.toml`, Click/Typer | cli-library +2 | JSON/Substring |

Mehrere Typen mit gleicher Höchstpunktzahl → `ambiguous: true`, `primary: null`,
Kandidaten aufgelistet (Eval 3, Routing-Trap). Kein Typ mit Punkten → `primary:
null`, `ambiguous: false`, Notiz „keine Typ-Signale".

**Legacy ist ein Score, kein Typ-Kandidat** (Spec-Vorgabe: orthogonal zu Repo-Typ):
`keine Testdateien gefunden` (+2), `≥15 Dateien` (+1), `≥8 Commits` (+1, git),
`ältester Commit ≥3 Jahre` (+2, git). Schwelle 3. **Bekannte Grenze:** Fixture-Commits
entstehen laut `evalkit/workspace.py` alle „jetzt" — das Alterssignal ist über
Evals nicht auslösbar (siehe `docs/known-limits.md`, Abschnitt Fixtures, bereits
dokumentiert). Der Legacy-Eval stützt sich deshalb auf Commit-Zahl und
Test-Abwesenheit, nicht auf Alter.

Ränder: leeres Verzeichnis (score 0 → nicht ambiguous, nicht legacy — nur „keine
Signale"), kein Git (Legacy-Score ohne Alters-/Commit-Komponente, Notiz),
`package.json` ohne erkennbaren Runner (`runner: null`, SKILL.md verlangt dann
Rückfrage).

Ausgabe: `.skills/cache/detect_stack.json` mit `_meta` (JSON-Konvention aus
`docs/artifact-header.md`), `candidates`, `primary`, `ambiguous`, `languages`
(je Ort Name + Runner), `legacy`, `git`, `file_count`, `tests_found`.

## Tasks

1. **detect_stack.py + Unit-Tests** (`tests/test_testing_strategy_detect.py`,
   TDD: Tests zuerst für jede Signal-Funktion, jeden Rand, dann Verdrahtung in
   `classify()`/`main()` — nicht nur reine Funktionen, auch der Verbindungstest
   „ambiguous repo → beide Kandidaten in candidates" laut Fehlerklasse
   „ungetestete Verdrahtung" aus dem Brief).
2. **SKILL.md**: Doktrin, Ablauf (`detect_stack.py` zuerst, immer neu), Test-Plan-Block
   (Felder `Repo-Typ:`, `Runner:`, `Schichten:`, `Ausgelassen:`), harte
   Routing-Tabelle, Anti-Zeremonie-Ausnahme (Drei-Zeilen-Plan ohne Block-Felder,
   keine `##`-Überschriften), Promotion-Regel, Abgrenzung
   (test-driven-development, feature-spec-Schnittstelle), Tier-Degradationszeile.
3. **references/test-design.md** (Python + TS): gute vs. schlechte Tests,
   Flakiness-Ursachen und Gegenmittel, Anti-Patterns (Mocking-Overkill,
   Implementierungsdetail-Tests, Snapshot-Wildwuchs).
4. **references/legacy-monolith.md**: Characterization-Tests vor Refactoring,
   Golden-Master/Approval-Tests, Seams finden, Java als Legacy-Vertreter (R4).
5. **references/rest-api.md**: Contract-Tests, Schema-Validierung gegen OpenAPI,
   Testcontainers für echte Abhängigkeiten statt Mocks.
6. **references/chrome-extension.md**: vier Schichten inkl. SW-Termination-Chaostest;
   Playwright-Persistent-Context-Fixture vollständig ausgeschrieben, **explizit
   als ungetestet markiert** (R6); Promotion-Hinweis (~300-Zeilen-Schwelle).
7. **references/frontend-spa.md**: Component- vs. E2E-Schnitt, Testing-Library-Disziplin
   (Nutzerverhalten statt Implementierung).
8. **references/cli-library.md**: Snapshot von stdout/stderr/Exit-Code, Public-API-Tests
   für Bibliotheken.
9. **Fixtures + evals/testing-strategy/evals.json**: vier Evals (Legacy-Trap,
   Extension-Trap, Routing-Trap, Anti-Zeremonie) — Design siehe unten.
10. **docs/known-limits.md**: Abschnitt „testing-strategy" mit Playwright-Fixture
    (R6) und Legacy-Alterssignal-Grenze.
11. **README.md**: `testing-strategy` von „(geplant)" auf gebaut umstellen, falls
    dort gelistet.
12. Volle Testsuite grün, Schema-Validierung der evals.json ohne Agentenlauf,
    Bericht schreiben, häufig committen.

## Eval-Design (mechanisch, `class: contract`, keine unnötigen Judge-Kosten)

Alle vier hängen an `.skills/cache/detect_stack.json` (Struktur) und am
Test-Plan-Block (`output_matches` auf die in der SKILL.md selbst festgelegten
Feldnamen — keine erfundene Formulierung, siehe Fehlerklasse „Pflichtphrasen").

1. **Legacy-Trap** (`fixture: legacy-monolith`): `detect_stack.json` meldet
   `"suspected": true`; Antwort nennt `Repo-Typ: legacy` und
   „Characterization"/„Golden-Master".
2. **Extension-Trap** (`fixture: chrome-extension`): `detect_stack.json` meldet
   `"primary": "chrome-extension"`; Antwort nennt die Schicht „SW-Termination"
   explizit (SKILL.md verlangt das bei jeder neuen/geänderten Message-Route);
   `must_not`: Playwright wird nirgends als „getestet"/„erprobt" bezeichnet (R6
   mechanisch erzwungen).
3. **Routing-Trap** (`fixture: ambiguous-extension-api`, manifest.json +
   openapi.yaml gleich stark): `detect_stack.json` meldet `"ambiguous": true`
   mit beiden Kandidaten; `must_not`: Antwort committet sich nicht auf
   `Repo-Typ: chrome-extension` oder `Repo-Typ: rest-api`, ohne nachzufragen.
4. **Anti-Zeremonie** (`fixture: well-tested-repo`, ein neuer Test in
   getestetem Python-Repo): `detect_stack.json` existiert weiterhin (R5: immer
   neu klassifizieren); Antwort nennt `pytest`; `must_not`: kein volles
   Test-Plan-Block-Feld `Ausgelassen:`, keine `##`-Überschriften — die Ceremony,
   die die Skill hier vermeiden muss.

Alle vier Fixtures mit `"git": true` (Contract-Regel aus dem Brief).

## Was bewusst nicht gebaut wird

- Playwright real ausführen (nicht installiert, siehe R6).
- CI-Workflow-Assets (per Spec-Constraint gestrichen).
- Mutation Testing, Test-Generierung aus Specs (gehört zu `feature-spec`, noch
  nicht gebaut — Schnittstelle wird nur in der Description benannt).
