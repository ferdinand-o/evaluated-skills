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
evals/testing-strategy/evals.json       4 Evals: 2 class "contract", 2 class
                                         "behavior" (siehe Fix-Runde unten)
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

## Test- und Validierungsstand (nach der Fix-Runde)

- Volle Suite: **184 von 184 Tests grün** (146 Basis + 29 erste Runde für
  `detect_stack.py` + 9 Fix-Runde: 5 Legacy-Score-Tests ersetzt/ergänzt
  (notwendig-und-hinreichend-Semantik), 6 Kommentar-/Abschnitts-Tests inkl.
  zweier expliziter Gegenproben, netto +9 — reine Funktionen und Verdrahtung,
  u. a. ein expliziter Test, dass ein mehrdeutiger Fund beide Kandidaten samt
  Signalen im Endergebnis trägt, nicht nur in den Einzel-Scannern).
- `evals/testing-strategy/evals.json`: 4 Evals, Schema-Validierung ohne
  Agentenlauf bestanden. **2× `class: "contract"`** (Routing-Trap,
  Anti-Zeremonie — vollständig mechanisch, der Pflicht-Anti-Zeremonie-Eval
  liegt bewusst in `contract`, nicht wie bei `handoff` in `behavior`, das den
  bekannten Fehler aus `docs/known-limits.md` wiederholt hätte). **2×
  `class: "behavior"`** (Legacy-Trap, Extension-Trap — seit der Fix-Runde
  mit einer Judge-Assertion für die inhaltliche „Begründung je Schicht"-Prüfung,
  die `class: contract` laut Spec 00 §2 nicht erlaubt; die reine
  Blockstruktur-Prüfung bleibt trotzdem mechanisch über `output_matches`).
- Alle datei-basierten `must`/`must_not`-Assertionen mechanisch gegen echte
  Fixture-Workspaces gegenprüft (siehe oben) — kein Assertion-Typ, der
  gegen den tatsächlichen `detect_stack.json`-Output der jeweiligen Fixture
  anders ausgefallen wäre als erwartet.
- Die geschärften `output_matches`-Muster für den Test-Plan-Block zusätzlich
  gegen zwei von Hand konstruierte Beispieltexte geprüft: ein „gegamter" Text
  ohne Block (fällt jetzt bei allen vier Feldmarken-Assertions durch) und ein
  vollständiger Block (besteht alle sieben must-Assertions).

## Fix-Runde (unabhängiger Review)

Vier Befunde, alle behoben:

1. **Test-Plan-Evals prüften Stichworte statt des Contracts.** Eine Antwort
   ganz ohne Test-Plan-Block bestand Legacy-Trap und Extension-Trap. Fix:
   Beide Evals verlangen jetzt mechanisch die volle Blockstruktur aus dem
   SKILL.md-Contract (`## Test-Plan` plus alle vier Feldmarken `Repo-Typ:`,
   `Runner:`, `Schichten:`, `Ausgelassen:` als eigene Bullet-Zeilen). Die
   inhaltliche Prüfung „Schichten mit Begründung" braucht ein Urteil und ist
   jetzt eine Judge-Assertion — beide Evals liegen deshalb neu in
   `class: behavior`, nicht mehr `contract`. Gegenprobe: Ein von Hand
   konstruierter „gegamter" Text, der nur die alten Stichworte trifft, aber
   keinen Block hat, scheitert jetzt an allen vier Feldmarken-Assertions
   (`/tmp/.../verify_gamed_answer.py`, nicht Teil des Commits, nur zur
   Verifikation genutzt); ein Text mit vollständigem Block besteht.
2. **Substring-Suche klassifizierte an Kommentaren.** Ein Kommentar wie
   `# früher haben wir django evaluiert` reichte, ein reines Click-Tool als
   `rest-api` einzustufen. Fix: `_strip_toml_line_comments` entfernt
   `#`-Kommentare zeilenweise (ohne `#` in Anführungszeichen zu werten),
   `_extract_toml_dependency_text` beschränkt die Suche zusätzlich auf die
   Abschnitte, in denen Abhängigkeitsnamen laut TOML-Struktur stehen können
   (`dependencies = [...]` im `[project]`-Wurzelabschnitt,
   `[project.optional-dependencies]`, `[tool.poetry.(dev-)dependencies]`);
   `[project.scripts]`/`[tool.poetry.scripts]` wird nur noch als echte
   Abschnitts-Kopfzeile erkannt, nicht als Substring. `requirements.txt`
   bekam Kommentar-Stripping, `pom.xml` XML-Kommentar-Stripping (Bonus-Fix,
   gleiche Fehlerklasse, vom Reviewer nicht explizit verlangt). Sechs neue
   Tests, davon zwei explizite Gegenproben (echte Abhängigkeit trotz
   unrelated Kommentaren weiterhin erkannt). **Nicht behoben:**
   `build.gradle`s `//`-Zeilenkommentare werden nicht gestrippt — dieselbe
   Fehlerklasse, außerhalb des geprüften Falls, in `docs/known-limits.md`
   vermerkt.
3. **Legacy-Score triggerte ohne Alterssignal.** „Keine Tests + ≥8 Commits"
   reichte, jedes junge, aktive, ungetestete Repo als Legacy einzustufen.
   **Neu geschnitten:** `suspected` ist keine Summe über eine Schwelle mehr,
   sondern eine notwendig-und-hinreichend-Bedingung: „keine Tests" **UND**
   (Altersignal **ODER** Umfangssignal). Die Umfangsschwellen wurden dabei
   angehoben, damit sie nicht mehr von den ersten Commits eines frischen
   Projekts erreicht werden: `LEGACY_FILE_COUNT_THRESHOLD` 15→20,
   `LEGACY_COMMIT_COUNT_THRESHOLD` 8→25 (Altersschwelle unverändert 3 Jahre).
   Ein Repo mit Tests ist jetzt nie mehr suspected, unabhängig vom Umfang —
   Umfang ersetzt Tests nicht, er ersetzt nur das Alterssignal, das der
   Harness nicht simulieren kann. Die `legacy-monolith`-Fixture wuchs von 10
   auf 24 Commits/Module, um die neuen Schwellen zu überschreiten (weiterhin
   mechanisch gegen den echten Fixture-Workspace verifiziert:
   `legacy.suspected: true`, Gründe „keine Testdateien gefunden", „25 Commits
   Historie", „25 Dateien im Repo"). Fünf neue/ersetzte Unit-Tests, darunter
   `test_legacy_no_tests_alone_is_not_sufficient` als direkte Kodierung des
   Reviewer-Falls und eine Gegenprobe mit Tests trotz großem Umfang.
4. **`chrome-extension.md` bei 194 Zeilen.** Kein Handlungsbedarf laut
   Review. Bleibt der erste Kandidat für die Promotion-Regel — vermerkt im
   SKILL.md-Abschnitt „Promotion-Regel" und in `chrome-extension.md` selbst.

Nach der Fix-Runde: **184 von 184 Tests grün** (175 vorher + 9 neu:
5 Legacy-Score-Tests ersetzt/ergänzt, 6 Kommentar-/Abschnitts-Tests, netto
+9). `evals/testing-strategy/evals.json` weiterhin schema-valide, jetzt 2
`contract`- und 2 `behavior`-Evals (vorher 4× `contract`) — bewusst, weil
zwei der vier Evals jetzt eine Judge-Assertion für die inhaltliche
„mit Begründung"-Prüfung brauchen, die `class: contract` laut Spec 00 §2
nicht erlaubt.

## Fix-Runde 2 (echter Agentenlauf — Diagnose, keine Vermutung)

Vor dieser Runde galt: „Die vier Evals sind nie mit einem echten Agenten
gelaufen." Sie sind es jetzt. Erstes reales Ergebnis: **1 von 4 bestanden**
(nur `routing-trap-asks-instead-of-guessing`). Die drei Fehlschläge sahen aus
wie „die Skill wurde nie geladen" — genau dieser Verdacht wurde geprüft,
nicht übernommen (Präzedenzfall in dieser Sammlung: `visual-summary`, wo zwei
Runden Textänderungen wirkungslos blieben, weil die Ursache in der
Frontmatter-`description` lag, nicht im Ablauftext).

**Diagnosemethode:** Harness-Dateien (`evalkit/dispatch.py`, `runner.py`,
`judge.py`, `assertions.py`, `schema.py`) von `feat/dev-report` übernommen
(Commit `d250b5f`) — die vorige Kopie sah nur den letzten Assistant-Zug, nicht
alle. Danach je einen fehlschlagenden Eval isoliert über eine
Wegwerf-`--evals-dir` mit `--keep-workspace` gefahren, und den Agenten
zusätzlich direkt im aufbewahrten Workspace mit
`--output-format stream-json --verbose` aufgerufen, um den Ereignisstrom auf
einen `Skill`-Tool-Aufruf zu prüfen.

**Befund: kein Routing-Defekt.** Sowohl für `legacy-trap` als auch für
`extension-trap` zeigte der Ereignisstrom einen echten
`Skill {"skill": "testing-strategy", ...}`-Aufruf, gefolgt von einem echten
Lauf von `detect_stack.py` und dem Lesen der passenden Referenz. Die Skill
wurde zuverlässig geladen — die Frontmatter-`description` brauchte keine
Änderung.

**Zwei echte, unterschiedliche Ursachen gefunden:**

1. **Formatdefekt (Assertions, nicht SKILL.md).** Der reale Output trug einen
   vollständigen, inhaltlich korrekten Test-Plan-Block — aber mit den vier
   Feldmarken teils als Markdown-Fettschrift (`- **Repo-Typ:** legacy` statt
   `- Repo-Typ: legacy`). Meine `output_matches`-Muster verlangten die Marke
   direkt nach `-\s*`, ohne Markdown-Dekoration zu erlauben. Fix: alle vier
   Feldmarken-Muster (must, und die entsprechenden must_not in
   `routing-trap`/`anti-ceremony`) tolerieren jetzt `[*_`]*` um Label und
   Doppelpunkt. Gegen die beiden echten Transcripts verifiziert (einmal mit,
   einmal ohne Bold-Formatierung — beide bestehen jetzt), und gegen den
   „gegamten", blocklosen Text aus Fix-Runde 1 (fällt weiterhin durch).
2. **Fixture/Prompt-Inkonsistenz (Eval-Design, nicht Skill).** Drei Prompts
   behaupten eine bereits vorgenommene Änderung, die nie in der zugehörigen
   Fixture existierte: `anti-ceremony` behauptet `strip_punct()` sei ergänzt
   (war es nie), `extension-trap` behauptet `HANDLE_SYNC` sei ergänzt (war es
   nie), `legacy-trap` verlangt, Stornierungen zu „erweitern" (es gab keine
   Stornierungslogik). Für `anti-ceremony` erklärt das den kompletten
   Ausfall: Der Agent untersuchte per `grep`/`git log -S`/Rückfrage erst die
   falsche Prämisse und rief die Skill nie auf — der eigentliche Trap-Fall
   (ein Test in einem gut getesteten Repo) kam nie zum Tragen. Fix: alle drei
   Fixtures um die im Prompt behauptete Änderung ergänzt.

**Zusätzlich, unabhängig vom Befund:** SKILL.md trug bisher keine explizite
R6-Regel — nur `docs/known-limits.md` und eine Randnotiz in
`chrome-extension.md` wussten, dass die Playwright-Fixture ungeprüft ist. Der
reale `extension-trap`-Lauf zeigte genau die vorhergesagte Folge: ein
gefeuertes `must_not`, weil die Playwright-Fixture als „real ausgeführt"
dargestellt wurde. SKILL.md hat jetzt einen eigenen, unmissverständlichen
Abschnitt „Die Playwright-Fixture ist ungeprüft" im immer geladenen Body.

**Bestätigungslauf, teilweise:** Ein erneuter Lauf aller vier Evals mit den
Fixes wurde durch ein Session-Limit mitten in der Ausführung unterbrochen.
Sichtbares Zwischenergebnis: `extension-trap` und `routing-trap` **PASS**;
`legacy-trap` und `anti-ceremony` **SKIP** mit Harness-Fehlern
(„embedded null byte" bzw. „Agent exit 1", leere stderr) — beides sieht nach
einer abgeschnittenen Subprocess-Ausgabe durch die Unterbrechung selbst aus,
nicht nach einem Fehler in Fixture oder Skill, aber das ist eine Vermutung,
keine verifizierte Ursache. Der volle, saubere Bestätigungslauf ist laut
Koordinator zentral vorgesehen und wurde hier bewusst nicht wiederholt
(„sei sparsam" — keine wiederholten Vierer-Läufe).

## Fix-Runde 3 (Koordinator-Bestätigungslauf: 3/4 — echter Skill-Defekt in der `description`)

Der zentrale Bestätigungslauf des Koordinators bestand `legacy-trap`,
`extension-trap` und `routing-trap`. Der „embedded null byte"-Fehler bei
`legacy-trap` war entgegen meiner Vermutung **kein Unterbrechungsartefakt**,
sondern ein echter Harness-Bug: Ein `__pycache__/*.pyc` im Workspace lässt
`dump_changed_files` eine Binärdatei als Text lesen, `errors="replace"`
lässt Nullbytes durch, und `subprocess` verbietet sie im Judge-Argument.
Behoben in `evalkit/workspace.py` (Commit `e186556` auf `feat/dev-report`,
übernommen). Meine eigene Vermutung „sieht nach Session-Limit-Artefakt aus"
war damit falsch — der Koordinator hat es korrekt als Harness-Bug
identifiziert statt meine Vermutung zu übernehmen.

**Offen blieb `anti-ceremony-single-test-stays-short`**, auch nach der
Fixture-Korrektur aus Fix-Runde 2. Diagnose nach derselben Methode
(Einzellauf über `--evals-dir` mit `--keep-workspace`, dann direkter Aufruf
mit `--output-format stream-json --verbose`) — mit einer Selbstkorrektur
unterwegs: Der erste direkte Aufruf lief versehentlich im selben
`--keep-workspace`-Verzeichnis, das `run_evals.py` bereits einmal benutzt
hatte — der zweite Lauf fand den vom ersten (echten, gewerteten) Lauf bereits
geschriebenen Test vor (`git status` zeigte `M tests/test_case.py`
uncommitted) und bestätigte ihn nur, ohne selbst etwas Neues zu zeigen. Nach
einem frischen `evalkit.workspace.prepare()`-Aufruf (kein vorheriger
Agentenlauf im selben Verzeichnis) zeigte der Ereignisstrom eindeutig: **kein
`Skill`-Tool-Aufruf.** Der Agent las `case.py` und `tests/test_case.py` und
schrieb den Test direkt, ohne die Skill je zu laden.

**Ursache: ein echter Skill-Defekt — aber in der `description`, nicht im
Body.** Der Prompt „Ich hab … eine kleine neue Funktion strip_punct()
ergänzt, brauche dafür einen Test" passt fast wörtlich auf die eigene
Abgrenzungsklausel der SKILL.md: „Not for the red-green-refactor cycle while
implementing a single already-planned test (use test-driven-development)".
Die Description hat sich damit selbst von genau dem Fall ausgeschlossen, den
Spec 00 §2 als Pflicht-Anti-Zeremonie-Trap vorschreibt (Spec 05s Einzeltest).
Kein Widerspruch zu Fix-Runde 2s Befund „kein Routing-Defekt" — dort ging es
um `legacy-trap`/`extension-trap`, wo die Skill zuverlässig lud; hier ist der
Prompt so nah an der eigenen TDD-Abgrenzung formuliert, dass er sie triggert.

**Fix:** Die `description` unterscheidet jetzt schärfer zwischen den beiden
Fällen — TDD ist der *Zyklus* aus fehlschlagendem Test und Code während aktiver
Implementierung, testing-strategy deckt auch das *Zumessen* eines einzelnen
neuen Tests für bereits existierenden Code ab. Trigger-Liste um ein Beispiel
nahe am tatsächlichen Prompt ergänzt („ich hab eine Funktion ergänzt, brauche
einen Test"). Verifiziert mit demselben Diagnoseschritt: frischer Workspace,
ein einziger direkter Aufruf, Ereignisstrom zeigt jetzt `Skill
{"skill": "testing-strategy", ...}`, `detect_stack.py` lief
(`primary: "cli-library"`), `.skills/cache/detect_stack.json` existiert, die
Antwort nennt `pytest` und trägt weder einen vollen Test-Plan-Block noch eine
`##`-Überschrift — alle drei Assertions bestehen gegen den echten Output. Kein
erneuter Lauf über `run_evals.py` (weder Einzel- noch Vierer-Batch) — der
Bestätigungslauf bleibt beim Koordinator zentral, wie angewiesen.

## Offene Sorgen

0. **(Fix-Runde 3)** Der zentrale Bestätigungslauf für
   `anti-ceremony-single-test-stays-short` mit der geschärften `description`
   steht noch aus — nur der direkte, ungewertete Diagnoselauf hat die
   Assertions bestanden, nicht `run_evals.py` selbst. Sollte die Description
   in einem anderen Kontext (z. B. bei Konkurrenz mit einer echten
   TDD-Anfrage) wieder zu breit oder zu eng greifen, ist das eine Folge dieser
   Schärfung und sollte hier zuerst geprüft werden.
1. **(Fix-Runde 2)** Der finale, ununterbrochene Bestätigungslauf aller vier
   Evals mit den aktuellen Fixes steht noch aus — die beiden SKIP-Ergebnisse
   oben sind nicht als „Fixtures kaputt" bestätigt, nur als plausibel auf die
   Unterbrechung zurückgeführt. Überholt durch Fix-Runde 3: `legacy-trap` war
   ein echter Harness-Bug (behoben), `anti-ceremony` ein echter
   Description-Defekt (behoben) — beide SKIP/FAIL-Ergebnisse sind damit erklärt,
   nicht mehr offen.
2. Vor Fix-Runde 2 waren die vier Evals nur mechanisch (Schema +
   Datei-Assertionen) geprüft, nie mit einem echten Agentenlauf — das ist
   jetzt nachgeholt (siehe oben), zuletzt mit 3 von 4 im zentralen Lauf plus
   einem bestätigenden Diagnoselauf für den vierten. Ein sauberer, kompletter
   Viererlauf am Stück nach der Description-Schärfung aus Fix-Runde 3 steht
   noch aus (siehe Punkt 0).
3. Die Legacy-Umfangsschwellen (20 Dateien, 25 Commits) sind nach der
   Fix-Runde meine eigene, zweite Kalibrierung — plausibler begründet als die
   erste (notwendig-und-hinreichend statt Summe), aber immer noch ohne
   Gegenprobe an einem echten, gewachsenen Repository. Ob 20/25 der richtige
   Punkt ist, an dem „viele frühe Commits" in „echter Umfang" übergeht, bleibt
   eine Annahme.
4. Die Kommentar-/Abschnitts-Erkennung in `_extract_toml_dependency_text` ist
   ein zeilenbasierter Heuristik-Ansatz, kein echter TOML-Parser — mehrzeilige
   Inline-Tabellen (`dependencies = [{name = "x", version = "..."}]` über
   mehrere Zeilen mit verschachtelten Klammern) sind nicht unit-getestet und
   könnten die einfache Klammer-Zählung in `in_dep_array` verwirren. Ebenso
   ungetestet: `build.gradle`s `//`-Kommentare (siehe `docs/known-limits.md`).
5. `chrome-extension.md` liegt mit 194 Zeilen bereits recht nah an der in der
   eigenen Promotion-Regel genannten ~300-Zeilen-Schwelle; laut Review kein
   Handlungsbedarf jetzt, aber der nächste Promotion-Kandidat. Ein Ausbau
   (z. B. ein echtes CDP-Hilfsskript) würde die Beförderung zur
   Geschwister-Skill auslösen, wie im Dokument selbst vermerkt.
6. Die Diagnose-Selbstkorrektur aus Fix-Runde 3 (verunreinigter
   `--keep-workspace`-Zweitlauf) ist ein methodischer Hinweis für künftige
   Diagnosen in dieser Sammlung: Ein `--keep-workspace`-Verzeichnis, das
   `run_evals.py` bereits einmal bespielt hat, darf für einen zweiten,
   diagnostischen Direktaufruf nicht wiederverwendet werden, sobald der
   Prompt Schreibzugriffe auslösen kann (anders als bei reinen
   Planungs-Prompts wie `legacy-trap`/`extension-trap`, wo das nicht auffiel).
   Ein frischer `evalkit.workspace.prepare()`-Aufruf ist in diesem Fall
   Pflicht, kein optionaler Vorsichtsschritt.
