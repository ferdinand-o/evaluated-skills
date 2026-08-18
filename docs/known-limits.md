# Bekannte Grenzen des Eval-Harness

Der Schluss-Review vor dem Merge des Eval-Harness (`evalkit/`, 15 Commits ab
`62a23a0`) hat mehr Befunde ergeben als für diesen Merge blockierend waren.
Was nicht in Code floss, steht hier — sonst verschwindet es mit dem
gitignoreten `.superpowers/`-Ledger, sobald der Branch gemerged ist. Jede
Grenze nennt den konkreten Fall, in dem sie beißt.

## Stand der Verifikation (2026-08-15)

Bis zu diesem Datum war der Harness nie gegen echte Agentenläufe gefahren
worden — alles darunter Stehende beruhte auf Unit-Tests und Codelektüre. Das
ist inzwischen nachgeholt, und zwar in beide Richtungen, weil ein Harness, der
nur bestehen kann, nichts beweist:

- Die vier `contract`-Evals von dev-report laufen durch (4 bestanden), ebenso
  der eine `behavior`-Eval (1 bestanden). Damit sind Dispatch, Workspace-Aufbau,
  Fixture-Anwendung, mechanische Assertions, Judge-Pfad und Report einmal
  vollständig durchlaufen.
- **Gegenprobe mechanisch:** Ein Eval, der eine Datei fordert, die der Lauf
  nachweislich nicht anlegt, wird korrekt als FAIL gemeldet, mit benannter
  Ursache („… existiert nicht").
- **Gegenprobe Judge:** Ein Judge-Claim, der etwas nachweislich nicht
  Geschehenes behauptet, wird korrekt verneint und der Eval fällt.

Beide Gegenproben liefen über eine Wegwerf-Eval-Sammlung via `--evals-dir` und
sind nicht im Repo — sie sind Nachweis, nicht Regressionsschutz. Wer dem
Harness nach einer Änderung wieder trauen will, wiederholt sie.

Was das **nicht** zeigt: dass die Assertions der einzelnen Skills scharf genug
sind. Die Abschnitte weiter unten nennen mehrere, die es nachweislich nicht
sind.

## Ein Eval-Ergebnis ist eine Stichprobe, kein Beweis

**Ob eine Skill überhaupt geladen wird, ist nicht deterministisch.** Gemessen am
Eval `anti-ceremony-single-test-stays-short` von testing-strategy (2026-08-16):
Zwei aufeinanderfolgende Läufe über denselben Commit, dieselbe Fixture und
denselben Prompt lieferten **einmal FAIL und einmal PASS**. Im roten Lauf fehlte
`.skills/cache/detect_stack.json`, die Skill wurde also gar nicht aufgerufen; im
grünen lief sie durch.

Das ist keine Eigenheit dieser einen Skill, sondern der Auswahl: Der Agent
entscheidet anhand der Descriptions, und diese Entscheidung schwankt — verschärft
dadurch, dass 16 fremde Skills mitkonkurrieren (siehe „Isolation" unten).

**Zweiter Beleg, andere Skill, anderer Mechanismus** (2026-08-16): debug-ledgers
`env-var-layers-instruments-boundaries` fiel im ersten Lauf durch — das Ledger
war angelegt, blieb aber im Mini-Modus ohne Hypothesen-Tabelle, die Eskalation
zum vollen Prozess hatte nicht gegriffen. Zweite Stichprobe über denselben
Commit: bestanden. Es schwankt also nicht nur, *ob* eine Skill geladen wird,
sondern auch, *wie weit* sie ihren eigenen Ablauf durchläuft. Eine Skill kann
denselben Auslöser einmal erkennen und einmal übergehen.

Konsequenzen für die Lesart jedes Ergebnisses in diesem Repo:

- **Ein grüner Lauf beweist nicht, dass die Skill zuverlässig triggert.** Alle in
  den Berichten genannten Zahlen sind Einzelstichproben, sofern nicht ausdrücklich
  anders vermerkt.
- **Ein roter Lauf beweist keinen Defekt.** Vor jeder Fix-Runde gehört ein zweiter
  Lauf — sonst repariert man eine Skill, die funktioniert. Bei testing-strategy ist
  genau das um Haaresbreite passiert.
- **Ein Diagnoselauf, der besteht, belegt eine Description-Korrektur nicht.** Er
  zeigt, dass Triggern *möglich* ist, nicht dass es verlässlich geschieht.
- Wer Verlässlichkeit wirklich messen will, braucht denselben Eval mehrfach und
  eine Quote statt eines Urteils. Der Runner kennt dafür heute kein Primitiv.

## Isolation

- **Fremde Skills sind im Eval-Agenten sichtbar — `--setting-sources project` hält sie
  nicht heraus.** Gemessen am `system.init`-Ereignis (2026-08-15): In einem leeren
  Verzeichnis ohne jede Projektkonfiguration sieht der Agent **16 global installierte
  Skills** (`deep-research`, `dataviz`, `code-review`, `debug`, `verify`, `simplify`,
  `claude-api` und weitere). Mit installierter Projekt-Skill sind es 17 — die eigene
  plus dieselben 16. `--strict-mcp-config` schaltet MCP-Server korrekt ab, für Skills
  gibt es keine Entsprechung: `--disable-slash-commands` entfernt **alle** Skills
  einschließlich der zu testenden und ist damit unbrauchbar. Es existiert keine
  Flaggen-Kombination, die nur die Projekt-Skill stehen lässt.

  Das beschädigt Eval-Ergebnisse in **beide** Richtungen, und die zweite ist die
  gefährlichere:
  - *Falsch rot:* Eine fremde Skill fängt den Prompt ab, die getestete kommt nie zum
    Zug. Genau das ist bei `visual-summary` passiert — der Eval `bare-request-triggers-triage`
    fiel durch, weil der Agent bei „Fass das zusammen." gar nicht erst die Skill
    aufrief. Zwei Runden Textänderungen am Ablauf blieben wirkungslos, weil der Body
    nie geladen wurde; die Ursache saß in der Frontmatter-`description`.
  - *Falsch grün:* Eine fremde Skill erledigt die Arbeit, und der Eval schreibt sie der
    getesteten gut. Von außen ist das nicht unterscheidbar.

  **Konsequenz für den Eval-Entwurf:** Assertions müssen an Artefakten hängen, die
  *nur* die getestete Skill erzeugt — ihre Ledger-Datei, ihr Registereintrag, ihre
  Kopfzeile, ihr Ablagepfad — nie an generischer Ergebnisqualität. Besonders betroffen
  sind Skills mit einem global installierten Gegenstück: `debug-ledger` gegen `debug`,
  `verified-research` gegen `deep-research` (von dem es ein Fork ist), `code-review`
  gegen `code-review`.

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
  dieser Eval typischerweise bei jeder Änderung laufen sollte. `learning-coach`s
  Anti-Zeremonie-Eval (`nothing-due-stays-honest`) liegt aus demselben Grund
  ebenfalls in `behavior` (siehe unten, Abschnitt „learning-coach") — SKILL.md
  mandatiert für den „nichts fällig"-Fall keine exakte Phrase, eine rein
  mechanische `output_matches`-Regex wäre also zwangsläufig zu eng.

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

## learning-coach

- **Fix-Runde 1 (vor jedem echten Agentenlauf, per Review):** Ein unabhängiger
  Review fand vor der ersten Ausführung von `run_evals.py` zwei strukturelle
  Fehler in `evals/learning-coach/evals.json`: (1)
  `frustration-moves-one-rung-not-to-solution` verlangte anhand eines Prompts,
  der mit „sag's mir einfach" endete, dass die Skill *nicht* zur Lösung geht —
  `hint-ladder.md` nennt genau diese Formulierung aber als sanktionierten
  Auslöser für Stufe 4. Behoben, indem der Prompt Frustration ohne explizite
  Lösungs-Bitte formuliert. (2) Der Pflicht-Anti-Zeremonie-Eval
  `nothing-due-stays-honest` prüfte mit einer zu engen `output_matches`-Regex
  (Assertion-Vokabular-Grenze oben) — behoben durch Umstellung auf
  `class: behavior` mit Judge-Claim.
- **Fix-Runde 2 (Schnittstelle gegen den echten Erzeuger geprüft):**
  `due_topics.py::exercises_status()` hatte ein Top-Level-JSON-*Array* für
  `*.exercises.json` angenommen, abgeleitet aus dem Spec-13-Text, nicht
  bestätigt — `learning-coach` und `exercise-forge` wurden parallel gebaut, jede
  Testsuite lief nur gegen die eigene Annahme grün. Der Koordinator prüfte
  gegen den echten Code (`exercise-forge`s `export.py`: `data.get("exercises",
  [])`) und fand: die reale Form ist ein JSON-**Objekt** mit
  `"exercises"`-Liste. Mit der ursprünglichen Annahme hätte `due_topics.py`
  **jede** real erzeugte Aufgabendatei als `malformed` gemeldet. Korrigiert.
- **Fix-Runde 3 (erste echte Agentenläufe — zwei reproduzierte Defekte):**
  Der Koordinator ließ `evals/learning-coach/evals.json` gegen echte
  Agentenläufe laufen (ich selbst durfte das für die Diagnose nachvollziehen,
  siehe unten). Zwei Evals fielen in zwei aufeinanderfolgenden Läufen identisch:
  1. `abrupt-end-still-updates` (mechanisch, `file_unchanged`-Prüfung auf
     `learner.md`): Bei einem abrupten Sitzungsende schrieb die Skill nichts.
     Ursache, per direktem `evalkit.dispatch.run_agent`-Aufruf reproduziert: Der
     Contract band das Update an einen „Abschluss"-Schritt und an eine formal
     *gestellte* Abruf-Frage — ein vom Lernenden **unaufgefordert** geäußertes,
     inhaltlich verwertbares Statement („ich glaube range(n) läuft von 0 bis
     n-1") triggerte den Update-Mechanismus nicht, der Agent bestätigte nur
     kurz und verabschiedete sich. Behoben: SKILL.md bindet die Persistenz jetzt
     an jedes inhaltliche Statement zu einem fälligen Thema, unabhängig davon,
     ob es auf eine gestellte Frage antwortet oder unaufgefordert kommt, und
     unabhängig vom Sitzungsende.
  2. `multi-due-session-starts-with-quiz` (Judge): Der erste Diagnoselauf zeigte
     einen echten Skill-Defekt — die Skill blockierte den gesamten Abruf-Schritt,
     wenn keine exercise-forge-Aufgaben vorlagen, und bot stattdessen eine
     Optionsliste („Wie möchtest du weitermachen?") an, statt selbst zu
     quizzen. Ursache: Der Contract-Satz „Aufgaben stammen aus exercise-forge,
     nie aus eigener Erfindung" wurde vom Agenten so gelesen, dass er auch die
     eigene, offene Abruf-Frage verbietet, wenn keine formale Aufgabe existiert
     — SKILL.md unterschied das nicht klar genug. Behoben, mit einer expliziten
     zweiten Quiz-Quelle (eigene offene Abruf-Fragen aus Thema/„Typische
     Fehler", falls keine exercise-forge-Aufgaben vorliegen) und einer klaren
     Abgrenzung „formale, als verifiziert ausgegebene Aufgabe" vs. „eigene
     Gesprächsfrage". Nach dieser Korrektur blieb ein *zweiter*, kleinerer
     Defekt: Die Skill quizzt jetzt korrekt, aber SKILL.md mandatiert selbst
     eine kurze Themen-Übersicht plus die Pflichtphrase „Keine verifizierten
     Aufgaben gefunden" vor der ersten Frage (E3-Contract) — der ursprüngliche
     Judge-Claim verlangte aber „beginnt mit" im wörtlichen Sinn und schloss
     jede Zusammenfassung aus. Das war ein Claim-Problem, kein Skill-Defekt:
     Der Claim wurde angepasst, um genau diesen mandatierten, nicht-lehrenden
     Vorlauf zu akzeptieren, verbietet aber weiterhin Optionslisten und
     inhaltliche Erklärungen vor der ersten Frage.

  **Für die Diagnose wurde `evalkit/` von `feat/dev-report` übernommen**
  (`assertions.py`, `dispatch.py`, `judge.py`, `runner.py`, `schema.py`,
  `workspace.py`, plus die zugehörigen Harness-Unit-Tests) — der Stand in
  diesem Branch war sonst älter und hätte an einer bekannten Grenze
  diagnostiziert: `--output-format text` liefert nur die *letzte*
  Assistant-Nachricht, ein mehrzügiges Tool-Use-Gespräch (wie ein
  Lern-Session-Start mit `due_topics.py`-Aufruf) wäre für den Judge nur
  teilweise sichtbar gewesen. Beide Diagnosen liefen über den neuen
  `assistant_text()`-Pfad (alle Assistant-Züge in Reihenfolge). Nicht
  ausgeschlossen: dass ein Teil der ursprünglich gemeldeten Fehlschläge
  tatsächlich auf diese Harness-Grenze zurückging statt auf die beiden hier
  behobenen Skill-Defekte — beide Ursachen wurden aber unabhängig voneinander
  bestätigt (Defekt 1 durch reproduzierten Dateizustand, Defekt 2 durch
  reproduzierten Antworttext mit Optionsliste), nicht nur vermutet.
- **Fix-Runde 3 war unvollständig: der Auslöser wurde ersetzt, nicht
  erweitert.** Der Fix in Runde 3 band die Persistenz an „jedes inhaltliche
  Statement zu einem fälligen Thema" — das reparierte `abrupt-end-still-updates`
  (dreimal grün), riss aber `short-session-still-updates` auf: Reproduziert,
  zweimal, gleicher Commit — bei der Kurzform-Anfrage („Ich hab nur 10 Minuten.
  Lern-Session bitte, Kurzform.") gab es in einem Ein-Zug-Austausch gar kein
  „inhaltliches Statement" im engen Sinn, nur eine gestellte Frage ohne Antwort,
  also blieb `learner.md` unverändert. Vorher `abrupt-end` rot, `short-session`
  grün; nach dem Fix umgekehrt — derselbe Fehler wie beim ersten Mal (E4-Regel
  „ein einzelner Auslöser repariert einen Fall und reißt einen anderen auf"),
  nur an einer anderen Stelle.
- **Fix-Runde 4 — Regel von der Zusage her formuliert, nicht vom Auslöser.**
  Die drei Persistenz-Evals (`nothing-due-stays-honest`,
  `short-session-still-updates`, `abrupt-end-still-updates`) beschreiben
  zusammen eine einzige Bedingung: `learner.md` wird aktualisiert, sobald die
  Sitzung ein fälliges Thema *in irgendeiner Form* berührt hat — eine gestellte
  Frage genügt bereits, eine beantwortete erst recht, ebenso ein
  unaufgefordertes Statement. Der Umfang des Eintrags skaliert mit der
  Berührung (eine gestellte, unbeantwortete Frage bekommt mindestens ein
  aktualisiertes „Letzte Abfrage"-Datum); „kein Update" bleibt nur für den
  Fall richtig, den `nothing-due-stays-honest` prüft (wirklich nichts fällig).
  SKILL.md trägt die Regel jetzt als eiserne Regel direkt nach der Kernaussage
  (Codeblock-Imperativ, nach dem Muster von `dev-report`s „KEIN SATZ ÜBER DAS
  PROJEKT, BEVOR collect.py GELAUFEN IST.") — eine Formulierung mitten in
  Schritt 2 allein hatte für den Kurzform-Fall nicht genügt. **Alle drei Evals
  gemeinsam** (ein Lauf, nicht nacheinander) liefen danach synchron im
  Vordergrund grün. Eine einzelne frühere Stichprobe (asynchron, vor der
  finalen Bestätigung) zeigte `nothing-due-stays-honest` einmal rot — der
  Agent hängte eine Randbemerkung zu einem verdächtig weit in der Zukunft
  liegenden Fälligkeitsdatum plus ein Freiwilligkeits-Angebot an, was die im
  Claim geforderte Kürze verletzte. Das ist keine Persistenz-Frage (die Datei
  blieb korrekt unverändert) und nicht Gegenstand dieser Fix-Runde — als
  eigener, unbehobener Befund unten festgehalten, nicht in die Persistenzregel
  eingearbeitet.
- **Verbleibender, unbehobener Befund:** `nothing-due-stays-honest` kann bei
  Gelegenheit ausführlicher antworten als „wenige Sätze" (z. B. mit einer
  Anmerkung zu einem auffälligen Fälligkeitsdatum plus einem Angebot, freiwillig
  zu quizzen) — inhaltlich korrekt und `learner.md` bleibt unangetastet, aber
  der Judge-Claim verlangt ausdrücklich Kürze. SKILL.md enthält bislang keine
  explizite Kürze-Anweisung für genau diesen Fall (nur „keine Pflicht-Session
  herbeireden"); nicht behoben, weil außerhalb des Scopes dieser Fix-Runde
  (Persistenz-Trigger) und weil `SKILL.md` an der 150-Zeilen-Grenze aus Spec 00
  §5 liegt.
- **Doppelte Themen-Slugs in `learner.md` werden erkannt, aber nicht aufgelöst.**
  `parse_learner()` warnt bei doppeltem Slug, behält aber beide Sektionen. Weder
  `due_topics.py` noch `SKILL.md` legen fest, welche der beiden Sektionen ein
  Agent aktualisieren soll, wenn beide denselben Slug tragen — beide zeigen auf
  denselben Aufgaben-Pfad (`exercises_path_for()` kennt nur den Slug, keine
  Sektion). Kein Eval deckt diesen Fall ab. Aus einem unabhängigen Review als
  Anmerkung eingestuft (kein beobachtbares Fehlverhalten des Skripts selbst,
  das Thema verschwindet nicht), aber ein unterspezifizierter Update-Fall.

## Verweise

[README](../README.md) · [Spec 00](../specs/Spec%2000%20%E2%80%93%20skill-foundation.md) ·
[Plan](superpowers/plans/2026-08-14-eval-harness.md)
