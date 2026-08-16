# Bericht: Skill `testing-strategy` (Spec 05)

Branch `feat/testing-strategy`, Basis `0831fb7` (specs/skill-foundation).

## Was gebaut wurde

```
skills/testing-strategy/
├── SKILL.md                 122 → 126 Zeilen, Doktrin, Routing-Tabelle,
│                             Test-Plan-Contract, Anti-Zeremonie-Ausnahme,
│                             Promotion-Regel, Tier-Begründung, Abgrenzung
├── references/
│   ├── test-design.md       querliegend, Python + TypeScript (R4)
│   ├── legacy-monolith.md   Characterization/Golden-Master, Seams,
│   │                        Approval-Tests, Java als Legacy-Vertreter (R4)
│   ├── rest-api.md          Contract-Tests, OpenAPI-Schema-Validierung,
│   │                        Testcontainers
│   ├── chrome-extension.md  194 Zeilen, vier Schichten inkl.
│   │                        SW-Termination-Chaostest, Playwright-Fixture
│   │                        vollständig ausgeschrieben, R6 markiert
│   ├── frontend-spa.md      Component-/E2E-Schnitt, Testing-Library-Disziplin
│   └── cli-library.md       CLI-Output-Snapshots, Public-API-Tests
└── scripts/
    └── detect_stack.py      Tier 1, Repo-Klassifikation →
                              .skills/cache/detect_stack.json

tests/test_testing_strategy_detect.py   29 Tests (reine Funktionen + Verdrahtung)
evals/testing-strategy/evals.json       4 Evals, alle class "contract"
evals/fixtures/legacy-monolith/         (kanonischer Name aus Spec 00 §2)
evals/fixtures/chrome-extension/        (kanonischer Name aus Spec 00 §2)
evals/fixtures/ambiguous-extension-api/
evals/fixtures/well-tested-repo/
docs/superpowers/plans/2026-08-16-testing-strategy.md
docs/known-limits.md                    Abschnitt "testing-strategy" ergänzt
README.md                               Routing-Matrix aktualisiert
```

Sieben Commits, jeweils ein zusammenhängender Baustein (Plan, `detect_stack.py`
+ Tests, SKILL.md, sechs Referenzen, Fixtures + Evals, Docs-Nachzug).

## Zusätzliche Entscheidungen, die im Auftrag nicht vorgegeben waren

- **R7 aufgelöst zugunsten Tier 1.** Geprüft und verworfen: `pyproject.toml`
  wird nicht per `tomllib` geparst (das läge erst ab Python 3.11 in der
  Stdlib), sondern als Text nach Substrings durchsucht (Abhängigkeitsnamen,
  `[project.scripts]`). Das reicht für die geforderten Signale vollständig —
  `detect_stack.py` braucht keine echte TOML-Semantik, nur Namens- und
  Abschnittserkennung. `manifest.json`/`package.json` sind ohnehin JSON
  (Stdlib). git-Aufrufe über `subprocess` gelten wie bei
  `dev-report/collect.py` als Tier 1 (etablierter Präzedenzfall im Repo).
  **Ergebnis: keine PyPI-Abhängigkeit, `detect_stack.py` ist Tier 1**, nicht
  wie in Spec 05 vorgesehen Tier 2. Begründet im Skriptkopf und im
  SKILL.md-Abschnitt „Tier".
- **Legacy-Score-Schwellen fixture-tauglich gewählt.** Spec 05 nennt „10 Jahre
  alter Code" als Bild, aber `evalkit`s deklarative Fixture-Historie kann kein
  Commit-Datum in der Vergangenheit erzeugen (jeder Fixture-Commit entsteht
  „jetzt", dokumentiert in `docs/known-limits.md`). Der Legacy-Score hat eine
  Alterskomponente (≥3 Jahre, +2) und erreicht die Schwelle in Fixtures
  trotzdem — über „keine Testdateien" (+2) kombiniert mit „≥8 Commits Historie"
  (+1). Das Alterssignal selbst ist unit-getestet, aber über keinen Eval
  auslösbar — siehe unten und `docs/known-limits.md`.
- **`Repo-Typ:`-Feld bei Legacy präzisiert.** Die Spec sagt nicht, was im
  Test-Plan-Block steht, wenn `legacy.suspected: true`, aber `primary: null`
  ist (Legacy ist als Score orthogonal zum Typ definiert). Ergänzt:
  `Repo-Typ:` beginnt in diesem Fall mit `legacy`, optional mit dem
  erkannten Typ in Klammern. Ohne diese Präzisierung wäre der
  Legacy-Trap-Eval eine erfundene Anforderung gewesen (Fehlerklasse
  „Pflichtphrasen sind spröde" aus dem Brief).
- **`well-tested-repo`-Fixture bekam einen `[project.scripts]`-Abschnitt.**
  Ohne ihn wäre `primary: null` gewesen (keine CLI-/Framework-Signale), und
  die SKILL.md-Routing-Zeile „`primary: null` → fragen, was geplant ist"
  hätte den Anti-Zeremonie-Fall verfälscht (die Skill hätte nach dem Repo-Typ
  fragen müssen, statt den Drei-Zeilen-Plan zu liefern). Mit dem
  Scripts-Abschnitt ist `primary: "cli-library"`, eindeutig, kein
  Rückfrage-Zwang.
- **Monorepo-Scan auf Tiefe 1 begrenzt** (Repo-Wurzel plus direkte
  Unterordner). Deckt die in der Spec genannten Fälle ab, ohne unbegrenzt zu
  rekursieren — mit Unit-Test (`test_monorepo_detects_languages_in_subdirectories`).

## Was ich nicht verifizieren konnte

- **Die Playwright-Fixture in `chrome-extension.md` läuft nie in einem echten
  Browser.** Playwright ist hier nicht installiert und wurde nicht
  installiert (R6, bewusste Vorgabe). Persistent-Context-Fixture,
  SW-Termination-Chaostest-Muster und das Content-Script-Beispiel sind
  vollständig ausgeschrieben, aber ungetestet — im Dokument selbst mehrfach
  als solches markiert, nirgends als „getestet"/„erprobt" bezeichnet. Der
  Extension-Trap-Eval erzwingt das zusätzlich mechanisch über `must_not`
  (`playwright ... getestet/erprobt/verifiziert`, in beiden Wortstellungen).
  Ergänzt in `docs/known-limits.md`.
- **Das Legacy-Alterssignal ist über keinen Eval auslösbar** (siehe oben) —
  eine bekannte Grenze des Eval-Harness selbst (`evalkit/workspace.py`), nicht
  meiner Implementierung. Unit-getestet über direkte Aufrufe von
  `_legacy_score()` mit synthetischen `git_info`-Werten, aber nie unter
  echten Eval-Bedingungen durchlaufen. Ergänzt in `docs/known-limits.md`.
- **Die vier Evals selbst wurden nicht mit einem echten Agenten gefahren**
  (Auftrag: `run_evals.py` läuft zentral). Ich habe stattdessen alle
  dateibasierten `must`/`must_not`-Assertionen mechanisch gegen echte, per
  `evalkit.workspace.prepare()` aufgebaute Fixture-Workspaces verifiziert
  (`.skills/cache/detect_stack.json` trägt in jedem der vier Fälle exakt die
  erwarteten Werte — `suspected: true`, `primary: "chrome-extension"`,
  `ambiguous: true` mit beiden Kandidaten, `primary: "cli-library"`). Die
  `output_matches`-Assertionen (die einzigen ohne Dateibezug) konnte ich nur
  gegen von Hand konstruierte Beispieltexte gegenprüfen, nicht gegen eine
  echte Modell-Antwort.
- **Der Router-Muster-Scan** ist ein enger Textabgleich auf eine feste Liste
  von Entry-Point-Dateinamen, keine echte Code-Analyse. Für unübliche
  Einstiegsdateinamen oder Frameworks außerhalb der bekannten Muster liefert
  `detect_stack.py` `primary: null` statt `rest-api`. Ergänzt in
  `docs/known-limits.md`.

## Test- und Validierungsstand

- Volle Suite: **175 von 175 Tests grün** (146 vorher + 29 neu für
  `detect_stack.py`, reine Funktionen und Verdrahtung — u. a. ein expliziter
  Test, dass ein mehrdeutiger Fund beide Kandidaten samt Signalen im
  Endergebnis trägt, nicht nur in den Einzel-Scannern).
- `evals/testing-strategy/evals.json`: 4 Evals, Schema-Validierung ohne
  Agentenlauf bestanden, alle `class: "contract"` (bewusst — der
  Pflicht-Anti-Zeremonie-Eval liegt hier in `contract`, nicht wie bei
  `handoff` in `behavior`, das den bekannten Fehler aus `docs/known-limits.md`
  wiederholt hätte).
- Alle datei-basierten `must`/`must_not`-Assertionen mechanisch gegen echte
  Fixture-Workspaces gegenprüft (siehe oben) — kein Assertion-Typ, der
  gegen den tatsächlichen `detect_stack.json`-Output der jeweiligen Fixture
  anders ausgefallen wäre als erwartet.

## Offene Sorgen

1. Die vier Evals sind bisher nur mechanisch (Schema + Datei-Assertionen)
   geprüft, nie mit einem echten Agentenlauf. Die `output_matches`-Muster
   (SW-Termination, HANDLE_SYNC, Repo-Typ-Feld, `##`-Verbot,
   `Ausgelassen:`-Verbot) sind bewusst eng an Formulierungen gebunden, die in
   der SKILL.md selbst als Contract stehen — aber ob ein echtes Modell diese
   Formulierungen tatsächlich so trifft, ist ungeprüft.
2. Der Legacy-Score-Schwellenwert (3) und die Einzelgewichte sind meine eigene
   Kalibrierung, nicht aus der Spec abgeleitet — plausibel begründet, aber
   ohne Gegenprobe an einem echten alten Repository.
3. `chrome-extension.md` liegt mit 194 Zeilen bereits recht nah an der in der
   eigenen Promotion-Regel genannten ~300-Zeilen-Schwelle; ein Ausbau (z. B.
   ein echtes CDP-Hilfsskript) würde die Beförderung zur Geschwister-Skill
   auslösen, wie im Dokument selbst vermerkt.
