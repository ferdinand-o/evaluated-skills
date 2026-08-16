# Bekannte Grenzen des Eval-Harness

Der Schluss-Review vor dem Merge des Eval-Harness (`evalkit/`, 15 Commits ab
`62a23a0`) hat mehr Befunde ergeben als für diesen Merge blockierend waren.
Was nicht in Code floss, steht hier — sonst verschwindet es mit dem
gitignoreten `.superpowers/`-Ledger, sobald der Branch gemerged ist. Jede
Grenze nennt den konkreten Fall, in dem sie beißt.

## Isolation

- **Die Prozessumgebung des Agenten ist nicht isoliert.** `evalkit.dispatch.run_agent`
  erzwingt nur das Arbeitsverzeichnis, `--setting-sources project` und
  `--strict-mcp-config` — nicht `HOME` oder den Rest von `os.environ`. Ein Versuch,
  `HOME`/`XDG_*` auf ein Unterverzeichnis des Workspace umzubiegen, wurde
  smoke-getestet und verworfen: Die CLI findet ihre Anmeldedaten
  (`~/.claude/.credentials.json`, `~/.claude.json`) dann nicht mehr und meldet „Not
  logged in". Ein Agent, der bewusst oder unbewusst `$HOME` liest oder beschreibt,
  trifft auf das echte Home-Verzeichnis des Aufrufers.

## Assertion-Vokabular

- **Negative Strukturprüfung fehlt.** Es gibt kein Primitiv für „keine anderen
  Sektionen als diese sechs". Eine `handoff.md` mit einer siebten, nicht
  autorisierten `##`-Sektion fällt bei keinem bestehenden Eval auf.
- **Keine Beobachtung außerhalb des Workspace.** `snapshot()` sieht nur Dateien
  unter der Workspace-Wurzel. Ein Verbot wie „legt kein Memory-Verzeichnis
  außerhalb des Projekts an" ist mit den vorhandenen Primitiven nicht prüfbar, weil
  ein solches Verzeichnis per Definition außerhalb liegt.
- **Keine inhaltliche Formprüfung.** Eine Vorgabe wie „nennt Dateipfade statt
  Prosa" lässt sich nicht mechanisch prüfen — nur ein Judge-Claim könnte das, und
  auch der nur mit den Grenzen weiter unten.
- **`output_matches` ist eine spröde Keyword-Regex.** Ein Muster, das auf
  `git|code|projekt|handoff|anlegen|erstellen|übergabe` prüft, fällt bei einer
  legitimen Rückfrage durch, die keines dieser Wörter benutzt. Inhärente Grenze
  des Ansatzes, kein Implementierungsfehler.

## Betrieb

- **Kein Transcript wird persistiert.** Spec 00 §2 verlangt „`run_evals.py` …
  protokolliert den Verlauf" — der Harness hält die Agent-Ausgabe nur im
  Prozessspeicher (`Transcript.stdout`) und schreibt sie nirgends auf Platte. Ein
  Fehlschlag lässt sich nach dem Lauf nicht mehr nachvollziehen, nur mit
  `--keep-workspace` grob rekonstruieren.
- **Kein Wiederaufnehmen eines abgebrochenen Batches.** Bricht `run_evals.py` bei
  Eval 40 von 60 ab (Absturz, Ctrl-C, Timeout der Umgebung), beginnt der nächste
  Lauf wieder bei Eval 1. Kein Checkpoint, kein `--resume`.
- **Kein `--eval`-Filter.** `--skill` und `--class` filtern grob; eine einzelne
  Eval-ID lässt sich nicht gezielt anwählen, was das Nachvollziehen eines
  einzelnen Fehlschlags während der Entwicklung verlangsamt.

## Spec-Lücken

- **Die Sichtbarkeits-Regel aus §3 ist für Evals nicht etabliert.** Spec 00 §3
  verlangt, dass ein übersprungenes Gate nie stillschweigend übersprungen wird,
  sondern „geprüft" oder „ungeprüft (Werkzeug X fehlt)" trägt. Der Eval-Harness
  hat kein Äquivalent dafür — ein Eval, der wegen fehlendem Tier-3-Werkzeug nicht
  läuft, würde einfach nicht im Report auftauchen, nicht als sichtbar
  übersprungen.
- **Die Gate-Ehrlichkeit G1/G2/G3 aus §4 ist nicht etabliert.** Es gibt keine
  Stelle im Harness, die deklariert, welchen Durchsetzungsgrad ein Eval hat oder
  durchsetzt — die Unterscheidung existiert nur als Text in Spec 00, nicht als
  geprüfte Eigenschaft eines Evals.
- **Der Pflicht-Anti-Zeremonie-Eval aus §2 ist nirgends erzwungen.** Spec 00 §2
  verlangt „mindestens ein Anti-Zeremonie-Eval" pro Skill. Nichts im Schema oder
  Runner prüft, dass eine `evals.json` einen solchen Eval enthält — es ist reine
  Konvention. `handoff`s Anti-Zeremonie-Eval
  (`anti-ceremony-invents-nothing`) liegt außerdem in der Klasse `behavior`,
  läuft also nicht im billigen `--class contract`-Routine-Gate mit, obwohl gerade
  dieser Eval typischerweise bei jeder Änderung laufen sollte.

## Fixtures

- **`dirty-worktree` ist nach `prepare()` entgegen ihrem Namen sauber.** Der Name
  suggeriert einen Workspace mit uncommitteten Änderungen; tatsächlich committet
  `_init_git()` per `git add -A` alles, was die Fixture mitbringt. Ein Eval, der
  echtes „dirty worktree"-Verhalten prüfen will, testet derzeit gegen einen
  frisch committeten, sauberen Stand.
- **Fixture-Historie ist deklarativ, nicht aufgezeichnet.** Das `commits`-Feld im
  Manifest erzeugt eine Commit-Folge aus Textinhalten (`touch`/`delete`/`tag`).
  Was sich damit nicht bauen lässt: echte Merge-Topologien, Autorenwechsel,
  auseinanderliegende Zeitstempel. Ein Contract, der auf Commit-Daten oder
  Branch-Verzweigungen beruht, ist weiterhin nicht prüfbar.
- **`stale-handoff/handoff.md` ist nicht regenerierbar.** Das Skript, das diese
  Fixture-Datei erzeugt hat, liegt nicht im Repo. Ändert sich das Kopfzeilen- oder
  Sektionsformat, muss die Datei von Hand angepasst werden statt neu generiert.

## Judge

- **Urteile werden über exakte Claim-String-Gleichheit zugeordnet.**
  `evalkit.judge.judge()` matcht die Antwort des Judge-Agenten gegen die
  Behauptungen aus der `evals.json` per `dict`-Lookup auf dem wörtlichen
  Claim-Text. Normalisiert der Judge dabei ein Anführungszeichen oder einen
  Leerraum, fehlt der Claim im Ergebnis-Dict — `judge()` wirft dann `JudgeError`,
  und `run_one()` fängt das als Harness-Fehler ab (`skipped=True`). Der Eval wird
  damit nicht falsch bewertet, sondern verschwindet aus dem regulären
  PASS/FAIL-Bild in die Harness-Fehler-Spalte — bei mehreren Claims pro Eval ein
  stiller Totalausfall für alle, nicht nur den einen betroffenen Claim.

## dev-report

- **`must_not`-Muster auf konkrete Formulierungen lassen sich durch Umschreiben
  umgehen.** `release-notes-filter-internals` prüft mit `(?i)nach utils
  verschoben` und `(?i)typ-?annotation`, dass die beiden internen Refactorings
  aus der `release-range`-Fixture nicht im Kundentext auftauchen. Beide Muster
  fangen nur die Formulierungen, die sie kennen — ein Report, der dasselbe
  Refactoring mit anderen Worten ausplaudert („interne Aufräumarbeiten im
  Hilfsmodul" statt „nach utils verschoben"), rutscht am `must_not` vorbei und
  der Eval bleibt fälschlich grün. Keine Regex-Erweiterung behebt das
  grundsätzlich; nur ein Judge-Claim könnte den Inhalt statt den Wortlaut
  prüfen, und der bräuchte dieselbe Sorgfalt, die die beiden jetzigen Muster
  schon an ihrer Grenze zeigen (siehe nächster Punkt).
- **`(?i)typ-?annotation` ist umgekehrt zu breit für erweiterte Fixtures.** Das
  Muster wurde in Fix-Runde 3 von `(?i)typannotation` auf `(?i)typ-?annotation`
  erweitert, um die Bindestrich-Schreibweise „Typ-Annotation(en)" zu fangen.
  Träfe eine künftige, breitere `release-range`-Fixture eine legitime,
  kundensichtbare Formulierung wie „Typsichere Annotation für die neue API",
  würde dasselbe Muster fälschlich einen Verstoß gegen das `must_not` melden —
  der Eval würde aus dem falschen Grund rot. Aktuell folgenlos, weil die
  bestehende Fixture keine solche Formulierung enthält, aber eine Falle für
  jede Erweiterung der Fixture-Commits.
- **Die Zielgruppen-Dimension ist ungetestet.** Alle fünf Prompts in
  `evals/dev-report/evals.json` sagen „für mich selbst" (mit Ausnahme von
  `release-notes-filter-internals`, das explizit „an Kunden" adressiert).
  `skills/dev-report/references/audience-guide.md` unterscheidet drei
  Zielgruppen mit eigenen Tabu-Regeln — insbesondere, was gegenüber
  Vorgesetzten und Team anders formuliert oder weggelassen wird als im
  Eigenreport. Kein Eval ruft den Modus mit Zielgruppe „Team" oder
  „Vorgesetzte" auf; die Tabu-Regeln aus dem Audience-Guide haben damit keine
  Eval-Deckung und könnten unbemerkt verletzt werden.

## testing-strategy

- **Fix-Runde 2 (echter Agentenlauf): Der erste reale Lauf bestand 1 von 4 —
  Ursache war ein Format- und ein Fixture-Defekt, keine Routing-Lücke.** Ein
  direkter Aufruf mit `--output-format stream-json --verbose` gegen
  `legacy-trap` und `extension-trap` zeigte für beide einen echten
  `Skill`-Tool-Aufruf für `testing-strategy`, einen echten Lauf von
  `detect_stack.py` und einen inhaltlich korrekten, vollständigen
  Test-Plan-Block — die Skill wurde also zuverlässig geladen. Der Fehlschlag
  lag an der Assertion: Das Modell formatiert die vier Feldmarken teils mit
  Markdown-Fettschrift (`- **Repo-Typ:** legacy`), das die ursprüngliche
  Regex (`^-\s*Repo-Typ:`) nicht zuließ. Behoben durch eine Zeichenklasse
  `[*_`]*` um Label und Doppelpunkt, in allen vier Feldmarken-Mustern sowie
  den entsprechenden `must_not`-Mustern in `routing-trap` und
  `anti-ceremony`. Für `anti-ceremony` zeigte derselbe direkte Aufruf einen
  echten zweiten Defekt: Der Prompt behauptete, `strip_punct()` sei bereits
  ergänzt worden, aber die Fixture enthielt die Funktion nie — der Agent
  untersuchte first die falsche Prämisse (`grep`, `git log -S`, Rückfrage ans
  Nutzer) und rief die Skill nie auf. Dieselbe Inkonsistenz steckte auch in
  `extension-trap` (HANDLE_SYNC nie im Fixture-`background.js`) und
  `legacy-trap` (der Prompt verlangt, „Stornierungen zu erweitern", aber
  `orders.py` hatte keine Stornierungslogik). Alle drei Fixtures wurden
  erweitert, damit ihr Inhalt die Prämisse des jeweiligen Prompts stützt.
  **Zusätzlich verstärkt:** SKILL.md trug bisher keine explizite R6-Regel —
  nur `known-limits.md` und die Randnotiz in `chrome-extension.md` wussten,
  dass die Playwright-Fixture ungeprüft ist. Ein Agent, der den Body lädt,
  aber die Referenz nicht liest, kannte die Regel nicht — genau das erklärte
  den gefeuerten `must_not` in `extension-trap`s erstem echten Lauf. SKILL.md
  hat jetzt einen eigenen Abschnitt „Die Playwright-Fixture ist ungeprüft".
  Ein erneuter Teil-Lauf (2 von 4, unterbrochen durch ein Session-Limit) ist
  im Bericht (`docs/superpowers/reports/testing-strategy-report.md`)
  festgehalten; der volle Bestätigungslauf war zum Zeitpunkt dieses Commits
  noch nicht abgeschlossen.
- **Die Playwright-Fixture in `chrome-extension.md` ist geschrieben, aber nicht
  real ausgeführt.** Playwright ist in dieser Umgebung nicht installiert und
  wurde für diese Arbeit nicht installiert (bewusste Vorgabe, siehe R6 des
  Implementierungsauftrags). Die Persistent-Context-Fixture, die
  SW-Termination-Chaostest-Vorlage und das Content-Script-Beispiel gegen
  Fixture-Seiten sind vollständig ausgeschrieben, aber kein einziges davon
  hat je in einem echten Browser gelaufen. Insbesondere die
  `ServiceWorker.stopWorker`-CDP-Sequenz im Chaostest ist ein Muster, keine
  verifizierte Implementierung — die `versionId`-Ermittlung ist im Kommentar
  als offen markiert. Wer diese Fixture zum ersten Mal einsetzt, sollte mit
  einem einzigen trivialen Message-Handler beginnen, bevor echte Routen
  darauf aufbauen, und mit dem Auftreten realer Fehler rechnen, die erst der
  erste echte Einsatz zeigt.
- **Das Legacy-Alterssignal (`erster Commit vor N Jahren`) ist über
  Eval-Fixtures nicht auslösbar.** `detect_stack.py`s Legacy-Score hat eine
  Komponente für das Alter des ersten Commits (≥3 Jahre). Der bestehende
  Punkt „Fixture-Historie ist deklarativ, nicht aufgezeichnet" weiter oben
  beschreibt die Ursache bereits allgemein: `evalkit/workspace.py` erzeugt
  jeden deklarierten Fixture-Commit zum Zeitpunkt des Eval-Laufs, nicht mit
  einem frei wählbaren Datum. Für `testing-strategy` heißt das konkret: Der
  Legacy-Trap-Eval (`legacy-trap-characterization-not-invented-behavior`)
  kann `legacy.suspected: true` nur über das Umfangssignal erreichen (Datei-
  oder Commit-Zahl über der Schwelle, siehe unten), nie über das
  Alterssignal — dieser Codepfad in `_legacy_score()` ist unit-getestet,
  aber nie unter Eval-Bedingungen durchlaufen worden.
- **Fix-Runde: „keine Tests" allein durfte ursprünglich Legacy bedeuten —
  behoben, dokumentiert als Warnung für künftige Schwellenänderungen.** Die
  erste Fassung von `_legacy_score()` summierte Punkte über eine feste
  Schwelle (3), erreichbar allein über „keine Testdateien" (+2) plus „≥8
  Commits" (+1) — damit galt jedes frische, gerade erst begonnene, noch
  ungetestete Projekt fälschlich als Legacy. Ein unabhängiger Reviewer hat
  das gefunden. Behoben: `suspected` ist jetzt eine notwendig-und-hinreichend-
  Bedingung, keine Summe — „keine Tests" ist notwendig, aber erst zusammen
  mit einem Alters- **oder** Umfangssignal hinreichend, dessen Schwellen
  bewusst über das hinausgehen, was ein Projekt in seinen ersten Commits
  ansammelt (`LEGACY_FILE_COUNT_THRESHOLD = 20`,
  `LEGACY_COMMIT_COUNT_THRESHOLD = 25`, unverändert `LEGACY_AGE_DAYS_THRESHOLD
  = 3 Jahre`). Die `legacy-monolith`-Fixture wurde von 10 auf 24 Commits/Module
  erweitert, um die geschärften Schwellen zu überschreiten. Wer diese
  Schwellen künftig weiter absenkt, sollte `test_legacy_no_tests_alone_is_not_sufficient`
  in `tests/test_testing_strategy_detect.py` im Kopf behalten — der Test
  scheitert, sobald ein kleines, frisches Repo wieder als Legacy gilt.
- **Fix-Runde: Die Substring-Suche in `pyproject.toml`/`requirements.txt`
  klassifizierte ursprünglich auch an Kommentaren — behoben.** Ein
  Kommentar wie `# früher haben wir django evaluiert` reichte, ein reines
  Click-CLI-Tool als `rest-api` zu klassifizieren, weil der komplette
  Rohtext durchsucht wurde. Behoben: `_strip_toml_line_comments`/
  `_extract_toml_dependency_text` entfernen Kommentare zeilenweise und
  beschränken die Suche auf die Abschnitte, in denen Abhängigkeitsnamen laut
  TOML-Struktur überhaupt stehen können (`dependencies = [...]` im
  `[project]`-Wurzelabschnitt, `[project.optional-dependencies]`,
  `[tool.poetry.(dev-)dependencies]`); `requirements.txt` und `pom.xml`
  bekamen dieselbe Kommentar-Bereinigung mit ihrer jeweiligen Syntax (`#`
  bzw. `<!-- -->`). Weiterhin kein echter Parser — `build.gradle`s
  `//`-Zeilenkommentare werden **nicht** entfernt (nur die für pom.xml
  ergänzte XML-Kommentarbereinigung greift dort), eine bekannte Lücke
  derselben Fehlerklasse, die der Review nicht explizit geprüft hat.
- **Der Router-Muster-Scan ist ein bewusst enger Textabgleich, keine
  Code-Analyse.** `detect_stack.py` durchsucht nur eine feste Liste bekannter
  Entry-Point-Dateinamen (`app.py`, `main.py`, `server.js`, …) nach wenigen
  Regex-Mustern (`@app.get(`, `@RestController`, …), nicht das ganze Repo und
  nicht mit echtem Parsing. Ein REST-Backend mit unüblichem Einstiegsdateinamen
  oder einem Framework außerhalb der bekannten Muster liefert dann `primary:
  null` statt `rest-api` — durch Unit-Tests wie
  `test_router_pattern_in_entry_file_signals_rest_api` nur für die bekannten
  Fälle abgesichert, nicht als Vollständigkeitsgarantie.

## Verweise

[README](../README.md) · [Spec 00](../specs/Spec%2000%20%E2%80%93%20skill-foundation.md) ·
[Plan](superpowers/plans/2026-08-14-eval-harness.md)
