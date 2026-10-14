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
  Flaggen-Kombination, die nur die Projekt-Skill stehen lässt. Nachgemessen am
  2026-09-15 (CLI 2.1.272, Spec 18): 19 globale Einträge im `skills`-Feld statt 16,
  und **keine** der 17 Skills aus `~/.claude/skills/synced/`, die gleich heißen wie
  Ordner unter `skills/` — die Profil-Skills bleiben unter `--setting-sources project`
  unsichtbar, die eingebauten nicht. Seit Spec 18 liest der Runner dieses Feld
  (`evalkit/dispatch.py::visible_skills`) und macht daraus einen Befund je Lauf, statt
  es einmal zu messen.

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
- **Behoben (Commit `a1417b3`): Assertion-Pfade dürfen Glob-Muster sein.**
  `file_exists`/`file_matches`/`file_max_lines`/`artifact_header` lösen `path`
  jetzt über `Path.glob()` auf, wenn er `*`/`?`/`[` enthält — Skills, deren
  Artefaktname aus Freitext plus Laufzeitdatum entsteht (z. B. `debug-ledger`s
  `new_ledger.py`), können ihn damit mechanisch statt per `judge` prüfen
  (`docs/debugging/[0-9]*.md` trifft jede datierte Ledger-Datei, nie
  `INDEX.md`). `file_unchanged` lehnt Globs ab, weil die Baseline nur exakte
  Pfade kennt.
- **Restlücke am selben Primitiv: „alphabetisch erster Treffer" ist nicht
  „neuester Treffer".** Bei mehreren Glob-Treffern liest `resolve_target()` für
  `file_matches`/`artifact_header`/`file_max_lines` immer den alphabetisch
  ersten — sinnvoll für Determinismus, aber falsch, wenn eine Fixture bereits
  eine Datei mitbringt, deren Name vor jedem neu erzeugten Namen sortiert.
  Konkreter Fall: `evals/debug-ledger/evals.json`s `archive-hit-tested-first`
  bringt ein Archiv mit vorab vorhandener `docs/debugging/2026-07-01-…-haengt.md`
  mit; ein vom Agenten neu angelegtes Ledger trägt zwangsläufig ein späteres
  Datum und sortiert danach. `file_matches` auf `docs/debugging/[0-9]*.md`
  würde deshalb strukturell **immer** die alte Archiv-Datei lesen, nie die neue
  — der Eval bliebe bei `class: behavior` und einem `judge`-Claim für den
  Ledger-Inhalt. Es gibt kein Primitiv für „neuester Treffer" oder „Treffer
  außer Pfad X".
- **Geändert (Spec 22, Abschnitt A, 2026-10-12): `.claude/` ist prüfbar, außer
  `.claude/skills/` und `.claude/worktrees/`.** `EXCLUDED_PREFIXES` war
  `(".git/", ".claude/")`; jede Assertion auf `.claude/settings.json`, Rules oder Hooks
  endete als Harness-Fehler. Jetzt `(".git/", ".claude/skills/", ".claude/worktrees/")`.
  Ein Glob wie `.claude/**/*.md` trifft die installierte Skill nie, auch wenn er mit
  keinem ausgenommenen Präfix beginnt. Folge für den Judge: Der Dump geänderter Dateien
  zeigt jetzt auch, was ein Agent unter `.claude/` außerhalb dieser beiden Ordner
  schreibt, etwa `settings.local.json`.
- **Gemessen statt gefahren: die Contract-Evals nach der Grenzänderung.** Spec 22
  verlangt, nach Abschnitt A alle Contract-Evals einmal zu fahren. Der Runner läuft unter
  root nicht. Gemessen wurde stattdessen deterministisch: für alle 113 Evals Workspace
  mit alter und neuer Grenze vorbereiten, danach `settings.local.json` und einen
  Worktree unter `.claude/` anlegen, jede mechanische Assertion prüfen. Ergebnis:
  Baseline und Urteile gleich, 0 Abweichungen. Ein Agentenlauf kann nur über den
  Judge-Dump anders ausgehen, und den gibt es nur bei Evals mit Judge-Claims. Ein
  echter Lauf im Harness steht aus.

## Betrieb

- **Der Harness läuft als root, seit 2026-10-14.** Die CLI verweigert
  `bypassPermissions` unter uid 0 („--dangerously-skip-permissions cannot be used with
  root/sudo privileges"); bis zum 2026-10-13 endete deshalb jeder Lauf in einem
  Root-Container mit `[SKIP] … Agent exit 1` und „0 bestanden, 0 gefallen, N
  übersprungen". Seit dem Gegenbefund vom 2026-10-12 ist bekannt, dass `claude -p` als
  root läuft, wenn man stattdessen `--allowedTools` mit `--permission-mode acceptEdits`
  setzt; Skript-Aufrufe über Bash laufen damit ohne Verweigerung. `run_evals.py` hat
  dafür `--permissions {auto,bypass,allowed-tools}`; `auto` (Default) nimmt
  `allowed-tools` unter root und sonst `bypassPermissions` wie bisher. Die freigegebenen
  Werkzeuge stehen in `evalkit/dispatch.py` (`ALLOWED_TOOLS`: Dateien, Bash, Skill,
  Agent/Task, TodoWrite, WebFetch, WebSearch, NotebookEdit). Was nicht in der Liste
  steht, verweigert `-p` — ein Eval, der ein anderes Werkzeug braucht, wird rot, ohne
  dass das etwas über die Skill sagt. Verweigert die CLI den Modus doch, meldet der Runner
  das laut auf stderr mit der Abhilfe statt eines stillen SKIP. Gemessen am 2026-10-14:
  die fünf test-first-Evals als root, mit Skill 5 von 5 bestanden, ohne Skill
  0 von 5 — der Harness meldete alle fünf „rot ohne Skill". Ältere Abschnitte, die „nicht im Harness gefahren (root,
  `bypassPermissions`)" sagen, beschreiben den Stand ihres Baus.
- **Kein Transcript wird persistiert.** Spec 00 §2 verlangt „`run_evals.py` …
  protokolliert den Verlauf" — der Harness hält die Agent-Ausgabe nur im
  Prozessspeicher (`Transcript.stdout`) und schreibt sie nirgends auf Platte. Ein
  Fehlschlag lässt sich nach dem Lauf nicht mehr nachvollziehen, nur mit
  `--keep-workspace` grob rekonstruieren.
- **`Transcript.stdout` enthält nur die letzte Assistant-Nachricht, nicht den
  Gesprächsverlauf.** Empirisch bestätigt (motion-landing-Diagnose, Fix-Runde 2):
  `evalkit.dispatch.run_agent` startet `claude -p` ohne `--output-format`, also mit
  dem Default `text`. Ein Kontrolllauf, der den Agenten explizit anwies, erst einen
  Markertext zu schreiben, dann ein Tool zu benutzen, dann einen zweiten
  Markertext zu schreiben, lieferte in `stdout` ausschließlich den zweiten Marker
  — der erste, vor dem Tool-Aufruf geschriebene Text war spurlos verschwunden.
  Jede `judge`-Assertion, die etwas über eine frühere Gesprächsrunde behauptet
  („die Antwort enthält, *bevor* Code gebaut wird, X") ist damit strukturell
  ungeprüft, unabhängig davon, wie gut Skill oder SKILL.md sind — der Judge sieht
  nur, was in der letzten Nachricht steht, plus den Diff der geänderten Dateien
  (`dump_changed_files`, ein Endzustand ohne Chronologie). Betraf real
  `evals/motion-landing/evals.json::google-labs-prompt-yields-single-highlight-storyboard`:
  Der Agent hatte ein korrektes Storyboard erzeugt, die Abschlussantwort verwies
  nur darauf, statt es zu wiederholen — der Judge sah es nie und verneinte den
  Claim. Fix dort: Der Claim prüft jetzt die Abschlussantwort selbst, und die
  Skill wiederholt das Storyboard darin (siehe `## motion-landing` unten). Für den
  Harness insgesamt bleibt es eine offene Lücke: `--output-format stream-json`
  würde den vollen Verlauf liefern, ist hier aber nicht eingebaut.
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

- **Zusammengesetzte Claims (mehrere Bedingungen in einem Satz verkettet)
  sind unzuverlässig — eine Eigenschaft der Kette, kein Einzelfall — und sie
  können echte Defekte verdecken, nicht nur Rauschen erzeugen.** Bei
  `exercise-forge` bestanden drei Judge-Claims, die je drei Bedingungen in
  einem Satz verlangten (etwa „Gate lief UND Konflikt wurde benannt UND
  Aufgabe ist nicht verified"), bei identischem Commit und identischer
  Fixture über mehrere `run_evals.py`-Läufe hinweg abwechselnd rot und grün —
  Lauf 1 verwarf Claim A und akzeptierte Claim B, Lauf 2 genau umgekehrt.
  Sieht der Judge zwei von drei Bedingungen erfüllt und die dritte nicht
  eindeutig, verneint er den ganzen Claim; bei einer Drei-Glieder-Kette genügt
  ein wackliges Glied, um alles zu kippen, und welches Glied gerade wackelt,
  variiert zwischen Läufen.
  **Der schärfere Befund kam erst nach der Zerlegung:** Sobald „Gate lief"
  und „Aufgabe ist nicht verified" als eigene, mechanische Assertionen dastanden
  (statt Teil derselben Judge-Kette zu sein), fielen zwei der drei Evals an
  genau der mechanischen „nicht verified"-Assertion — mechanisch, nicht als
  Judge-Urteil. Der Grund: `status` blieb `verified`, obwohl das Blind-Gate
  einen Konflikt gefunden und (laut vorherigen, noch zusammengesetzten Läufen)
  auch benannt hatte. In der verketteten Fassung hatte der Judge diesen
  Widerspruch **überstimmt** — er sah „Konflikt benannt" erfüllt, urteilte
  wohlwollend über die Kette als Ganzes, und der eigentliche Defekt (ein
  gefundener Konflikt, der den Status nicht erreichte) blieb hinter grünen
  Einzelläufen verborgen, bis die Kette in Einzelteile zerlegt war. Eine
  zusammengesetzte Prüfung ist damit nicht nur unzuverlässiger als drei
  einzelne — sie kann *milder* sein als die Summe ihrer Teile, weil der Judge
  bei überwiegender Erfüllung eher nachsichtig als strikt urteilt. Der Fix:
  jede Bedingung als eigener, einzeln entscheidbarer Claim (oder, wo
  mechanisch prüfbar, als mechanische Assertion statt Judge — „Aufgabe X ist
  nicht als verified ausgewiesen" steht im Artefakt und braucht kein Urteil).
  Drei einzeln geprüfte Bedingungen sind dabei strenger als eine Kette, die
  schon an ihrer eigenen Länge scheitert: ein Fehlschlag benennt jetzt, welches
  Glied fehlte, statt nur „irgendetwas stimmte nicht" — und genau das machte
  den verdeckten Defekt erst sichtbar. Diese Beobachtung gilt für jede Skill,
  die Judge-Claims formuliert, nicht nur für `exercise-forge` — siehe
  `evals/exercise-forge/evals.json` (`mc-distractor-trap-is-caught`,
  `narrow-criteria-on-open-question-are-flagged`,
  `overspecified-coding-tests-are-flagged`) für ein durchgeführtes Beispiel
  der Zerlegung, und den `exercise-forge`-Abschnitt unten für den damit
  aufgedeckten Skill-Defekt selbst.
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

## feature-spec

- **`_code_lines()` in `export_stubs.py` ist kein echter Python-Parser.** Der
  Überschreibschutz erkennt Docstrings naiv über die Parität von `'''`/`"""`
  pro Zeile, um einen aktiven `@pytest.mark.skip(...)`-Marker von einem zu
  unterscheiden, der nur als Text in einem Docstring zitiert wird
  (Fix-Runde, Defekt 1). Grenzfälle, die diese naive Erkennung verwirren
  könnten: String-Konkatenation über mehrere Zeilen mit ungerader
  Anführungszeichen-Verteilung, gemischte `'''`/`"""` in derselben Datei,
  oder ein einzeiliges String-Literal mit einer ungeraden Zahl von
  Anführungszeichen (z. B. ein escaptes `\"\"\"` mitten im Text). Alle drei
  Fälle sind für von `export_stubs.py` selbst generierte Stubs
  ausgeschlossen (das Skript erzeugt immer genau einen sauberen
  Docstring-Block), betreffen also nur eine Datei, die jemand von Hand stark
  vom generierten Format abweichend umgeschrieben hat, bevor der
  Skip-Marker entfernt wurde.
- **Nur noch ein `contract`-Eval nach der Reklassifizierung von
  `decisions-conflict-is-surfaced`.** Der Eval war ursprünglich `contract`
  mit drei unabhängigen Regex-Treffern, die auch bei bloß beiläufiger
  Erwähnung der Begriffe grün geworden wären, ohne dass der Widerspruch
  substantiell aufgegriffen wird (Fix-Runde, Defekt 2). Jetzt `behavior`
  mit Judge-Claim. Von den vier Evals aus Spec 03 ist damit nur noch
  `prose-criteria-refuses-export` mechanisch und ohne Judge-Kosten prüfbar
  — die übrigen drei brauchen einen echten Agentenlauf plus Judge, was den
  vollen Eval-Durchlauf dieser Skill teurer macht als ursprünglich geplant.
- **Erster echter Lauf: 2 von 4 Evals bestanden, 2 an Eval-Defekten
  gescheitert — nicht an der Skill.** `run_evals.py` lief zentral koordiniert
  gegen alle vier Evals. `decisions-conflict-is-surfaced` und
  `hidden-scope-risk-lands-in-non-goals` bestanden unverändert. Die beiden
  anderen fielen an zu strengen Assertionen, nicht an Skill-Verhalten
  (Fix-Runde 2): `prose-criteria-refuses-export` verlangte mit zwei
  `file_absent`-Assertionen fälschlich, dass der Lauf nach der Verweigerung
  stehenbleibt, obwohl die Skill korrekt weiterarbeitete (Prosa-Kriterium
  nach Given/When/Then überführt, dann erfolgreich exportiert) — Spec 03
  verlangt nur die Verweigerung samt Given/When/Then-Forderung, keinen
  Abbruch. `vague-request-drafts-with-marked-assumptions` prüfte
  `output_matches` auf `(?i)annahme:` gegen die Agent-Ausgabe (stdout), der
  Entwurf mit markierten Annahmen entstand aber korrekt als Datei, nur ohne
  stdout-Spiegelung, die Spec 03 nirgends verlangt. Beide Assertionen sind
  jetzt auf `file_matches` gegen das tatsächliche Artefakt umgestellt; dafür
  musste der Ablageort des Entwurfs erstmals mechanisch vorhersagbar gemacht
  werden (SKILL.md Schritt 3: Dateiname = slugifizierter Feature-Titel,
  vorher frei). **Die beiden korrigierten Evals wurden seit dem Fix noch
  nicht erneut real gelaufen** — die Korrektur ist durch Nachvollzug der
  inspizierten Workspaces begründet, nicht durch einen bestätigenden
  Wiederholungslauf. Der neu formulierte Dreifach-Judge-Claim für
  `decisions-conflict-is-surfaced` („benennt UND erkennt den Widerspruch UND
  trifft eine Wahl") bestand bereits im echten Lauf, ist also nicht mehr rein
  hypothetisch.
- **Kein Pflicht-Anti-Zeremonie-Eval.** Spec 00 §2 verlangt „mindestens ein
  Anti-Zeremonie-Eval" pro Skill; Spec 03 nennt aber vier feste, andere
  Evals. Keiner der vier deckt den trivialen Fall ab (eine Anfrage, die
  schon vollständig als Given/When/Then vorformuliert ankommt und keinen
  großen Entwurf braucht).
## motion-landing

- **Der Erfolgspfad von `verify.py` ist komplett ungetestet.** Playwright und
  Lighthouse sind in der Entwicklungsumgebung dieser Skill nicht installiert
  und wurden absichtlich nicht installiert (Auftragsbeschränkung). Konkret
  ungeprüft: `run_playwright_capture` (echtes Scrollen, echte Screenshots an
  den Szenen-Grenzen, echte `prefers-reduced-motion`-Emulation über einen
  Browser-Context, echte Video-Aufnahme mit `--video`), `run_lighthouse`
  (echter Node/Lighthouse-CLI-Aufruf) und der Teil von `main()`, der beide
  zusammenführt und daraus `all_budgets_pass` ableitet. Getestet ist nur die
  *Struktur* dieses Pfads — über Doubles für beide Funktionen
  (`tests/test_motion_landing_verify.py::test_main_success_path_*`), nie mit
  echtem Browser. Real geprüft ist ausschließlich der Degradationszweig, weil
  diese Umgebung die Toolchain tatsächlich nicht hat
  (`test_main_degrades_visibly_when_toolchain_is_missing`).
- **Die vier Vanilla-Demos wurden nie in einem Browser gerendert.** Kein
  Playwright, kein manueller Browser-Test in dieser Umgebung möglich. Die CSS
  Scroll-Driven Animations (`animation-timeline: scroll()`/`view()`) sind nach
  Spezifikation geschrieben, aber ihr tatsächliches Laufzeitverhalten —
  insbesondere `animation-range`-Werte, das Zusammenspiel von
  `scroll(nearest)` mit verschachtelten Containern, und ob der
  Feature-Detection-Umschlag (`CSS.supports(...)` → Klasse/Attribut) wirklich
  greift, bevor der erste Repaint sichtbar wird — ist unverifiziert.
- **Die vier React-Adapter wurden nie gebaut oder gerendert.** Dieses Repo hat
  keine Node-/React-Toolchain (kein `npm`, kein installiertes React/JSX-
  Tooling). Die `.jsx`-Dateien sind von Hand nach der Vanilla-Demo und dem in
  `references/adapters.md` beschriebenen Mapping geschrieben, aber nie durch
  einen Compiler, Linter oder Browser gelaufen — Syntaxfehler oder ein
  gebrochener Hook (z. B. eine vergessene Dependency in `useEffect`) wären
  hier nicht aufgefallen.
- **INP wird ohne echte Interaktion nur über einen dokumentierten Näherungswert
  geschätzt.** Lighthouse liefert in einem reinen Lab-Lauf ohne simulierte
  Nutzerinteraktion kein belastbares `interaction-to-next-paint`-Audit.
  `evaluate_budgets()` fällt in diesem Fall auf `total-blocking-time` zurück
  und markiert das über `BudgetCheck.note` — aber ob `run_playwright_capture`
  im Erfolgspfad überhaupt eine Interaktion simuliert, die ein echtes
  INP-Audit auslösen würde, ist ungeklärt und ungetestet (siehe Punkt eins).
- **`cls-trap-hero-gets-fixed-to-transform`: der Mischfall ist seit der
  Fix-Runde geschlossen, ein Restloch bleibt.** Die `must_not`-Muster
  (`@keyframes[\s\S]{0,300}?margin-top`, `@keyframes[\s\S]{0,300}?\btop\s*:`)
  laufen jetzt gegen `styles.css` *und* `index.html` — ein Fix, der
  `transform: translateY` sauber in `styles.css` einbaut, die verbotene
  `margin-top`-Animation aber zusätzlich inline nach `index.html`
  verschiebt, wird jetzt korrekt als Verstoß erkannt (vorher entging er der
  Assertion, weil nur `styles.css` geprüft wurde — mechanisch nachgestellt
  und bestätigt, siehe Commit-Historie). Was bleibt: Ein drittes, in der
  Fixture nicht vorhandenes File (z. B. ein vom Fix selbst neu angelegtes
  `<link>`-Stylesheet), landet außerhalb dieser beiden Pfade weiterhin
  ungeprüft — dieselbe Grenzklasse wie dev-reports
  `release-notes-filter-internals` oben, nur enger eingegrenzt.
- **`reduced-motion-scene-shows-static-content-not-frozen-hidden` war ein
  echter Defekt, kein dokumentierbarer Randfall — inzwischen auf `behavior`
  umgebaut.** Die ursprüngliche `must`-Assertion akzeptierte `opacity: 1`
  ODER `animation: none` im `reduce`-Block als Beleg für einen korrekten
  Fix. Der naheliegendste Fix überhaupt —
  `@media (prefers-reduced-motion: reduce) { .panel { animation: none; } }`
  — erfüllte damit `must`, verletzte keines der `must_not`-Muster, ließ aber
  die Basisregel `.panel { opacity: 0; }` unverändert stehen: Der Inhalt
  blieb unsichtbar, der Eval wurde trotzdem grün. Der Grund war keine zu
  lockere Regex, sondern die falsche Prüfebene — Sichtbarkeit ist eine
  Eigenschaft der CSS-*Kaskade* (Basisregel plus Media-Query-Override
  zusammen), keine Texteigenschaft, die sich an einer Stelle der Datei
  ablesen lässt. Der Eval ist deshalb jetzt `class: behavior`: die vier
  `must_not`-Muster (`display: none`, `visibility: hidden`, `height: 0`,
  `clip-path`) bleiben als billige mechanische Vorfilter für die
  eindeutigen Verstecken-Fälle, das eigentliche Sichtbarkeits-Urteil trägt
  ein Judge-Claim, der die Kaskade als Ganzes bewertet. Mechanisch
  nachgestellt (siehe Commit-Historie): Der defekte Fix erfüllt keines der
  vier `must_not`-Muster mehr — die Erkennung hängt jetzt vollständig vom
  Judge-Urteil ab. Ein echter Voll-Lauf (siehe nächster Punkt) hat diesen
  Judge-Claim inzwischen bestanden — ein einzelner Durchlauf, keine
  Serienprüfung gegen mehrere Fix-Varianten.
- **Alle vier Evals sind inzwischen mindestens einmal real gelaufen — mit einem
  gefundenen und behobenen Defekt.** Ein Voll-Lauf durch den Koordinator ergab
  zunächst 3 von 4 bestanden: `artifact-context-degrades-visibly`,
  `cls-trap-hero-gets-fixed-to-transform` und
  `reduced-motion-scene-shows-static-content-not-frozen-hidden` bestanden real
  (auch mit der in dieser Fix-Runde neu geschriebenen Judge-Claim-Fassung des
  letzteren, siehe oben). Gefallen war
  `google-labs-prompt-yields-single-highlight-storyboard`, und zwar genau am
  ersten Claim („Storyboard-Block vor jeder Implementierung"). Diagnose per
  Wegwerf-Eval-Sammlung (`--evals-dir`, `--keep-workspace`, zwei reale Läufe)
  ergab: Der Agent hatte ein korrektes, formvollständiges Storyboard erzeugt
  (`scenes.json` mit fünf typisierten Szenen, exakt ein `highlight: true`,
  HTML-Kommentare je Szene mit Typ und Status) — SKILL.md wurde also befolgt,
  nicht umgangen. Die Ursache lag im Harness, nicht in der Skill: siehe
  `## Betrieb` oben, `Transcript.stdout` enthält nur die letzte
  Assistant-Nachricht, das Storyboard stand aber in einer früheren Runde. Fix:
  SKILL.md verlangt jetzt (Ablauf, Schritt 6), dass die Abschlussmitteilung
  die Szenenliste wiederholt statt nur zu referenzieren; der erste Claim
  prüft entsprechend die Abschlussantwort. Ein erneuter realer Lauf desselben
  Evals bestand danach. Das ist trotzdem keine Stabilitätsgarantie — ein
  einzelner bestandener Lauf zeigt, dass die Formulierung in diesem einen Fall
  trug, nicht dass sie es bei jeder möglichen Formulierung des Agenten tut;
  LLM-Agentenläufe sind nicht deterministisch.
- **Beiläufig geprüft: `~/.skills`-Schreibzugriffe.** Der Koordinator wies auf
  den bei `visual-summary` gefundenen Fehler hin (Fixture ohne `"git": true` →
  Skill schreibt regelkonform nach `~/.skills/<skill>/`, außerhalb jeder
  Assertion). Nachgesehen: `~/.skills/` enthält nach den Diagnose-Läufen dieser
  Fix-Runde nur `visual-summary/`, kein `motion-landing/`. Plausibler Grund:
  `verify.py`s `DEFAULT_OUT` (`.skills/cache/motion-landing/`) ist ein relativer
  Pfad zum Arbeitsverzeichnis (dem Workspace-Root, in dem `dispatch.run_agent`
  den Agenten startet), keine Pfadauflösung, die bei fehlendem `.git` auf
  `$HOME` ausweicht — anders als offenbar bei `visual-summary`. Die
  `empty-dir`-Fixture (`"git": false`, von zwei meiner vier Evals genutzt) ist
  davon also nicht betroffen; mangels einer zweiten, unabhängigen Codeprüfung
  bleibt das eine Beobachtung aus einer Handvoll Läufen, kein Beweis für jeden
  denkbaren Prompt.
- **Die drei Szenen ohne Demo (`marquee`, `stagger-grid`, `closing-cta`) sind
  reine Prosa.** Ihre Rezepte beschreiben Technik und Fallstricke, aber ohne
  eine lauffähige Demo dahinter ist nichts davon gegen einen echten Browser
  geprüft — anders als bei den vier Kern-Demos, wo zumindest der Code
  existiert, auch wenn er ungerendert blieb (siehe oben).
- **Der Storyboard-Contract ist nur teilweise mechanisch erzwungen.**
  `verify.py` prüft `validate_single_highlight()` ausschließlich gegen eine
  `scenes.json`, die *nach* der Storyboard-Entscheidung entsteht — der
  Storyboard-*Text* in der Chat-Antwort selbst (das, was SKILL.md als
  Pflicht-Output vor jeder Implementierung verlangt) hat keine mechanische
  Prüfung, nur Eval 1s Judge-Claims.
## mobile-audit

Gebaut nach Spec 15 (2026-08-20/21): Stufe 1 `audit_static.py` (Tier 1, nur Stdlib),
Stufe 2 `audit_devices.py` (Tier 3, Playwright mit Chromium). Spec 15 verlangte diesen
Abschnitt; er fehlte und ist am 2026-10-12 aus Spec, Docstrings und Commit-Historie
nachgetragen.

- **Hover-Menüs per JavaScript bleiben unerkannt.** `mouseenter`-Listener sind aus dem
  Quelltext nicht verlässlich zu erkennen und aus der laufenden Seite nicht aufzählbar
  (`getEventListeners` gibt es nur in der DevTools-Konsole). Der Hover-Check sieht nur
  CSS-Regeln unter `:hover`, die Sichtbarkeit oder Position ändern, und rät nicht.
- **Die Tastatur ist modelliert, nicht gemessen.** Im Spike schrumpfte
  `Emulation.setDeviceMetricsOverride` Layout- und visuellen Viewport gemeinsam, und
  `Emulation.setVisibleSize` tat nichts. Der Check nimmt deshalb an, dass die Tastatur
  die unteren K Pixel verdeckt (K je Profil in `assets/audit-config.json`), und meldet
  „modelliert". Ob die Seite beim Fokus richtig scrollt, prüft er nicht.
- **Bedienelemente aus `div` ohne `role` zählen nicht als interaktiv.** Stufe 2 erkennt
  `a[href]`, `button`, Formularfelder, `[role=button]`, `[role=link]` und `[onclick]`;
  ein `div` mit per JavaScript angehängtem Klick-Handler fällt durch Hit-Area- und
  Tastatur-Check.
- **Stufe 2 braucht Playwright mit Chromium.** Fehlt es, steht im Bericht
  `stage_2: ungeprüft`, nie „grün"; die e2e-Tests überspringen sich dann. Gemessen wird
  Overflow gegen `window.visualViewport`, weil Chromium im mobilen Modus
  `window.innerWidth` auf die Inhaltsbreite dehnt (gemessen 700 statt 360).
- **Die Evals messen nur Stufe 1.** Alle sechs sind `contract` und laufen ohne Browser;
  Stufe 2 prüfen nur Unit-Tests mit synthetischen Messwerten und drei e2e-Tests.
- **Drei Geräteprofile.** Das Phablet trägt keinen eigenen Check und ist gestrichen,
  ebenso CPU- und Netzdrosselung (Performance gehört zu motion-landing). PWA und React
  Native liegen außerhalb.

## visual-summary

- **HTML-Budget ist nur sichtprüfbar, nicht mechanisch.** `references/formats.md`
  nennt harte Zeilenbudgets für die Markdown-Fassung jedes Formats (mechanisch
  über `file_max_lines` prüfbar), aber für die HTML-Fassung gibt es kein
  Äquivalent — die Zeilenzahl einer Markup-Datei sagt nichts über die gerenderte
  Länge (Whitespace, eingebettetes CSS, Slot-Füllung variieren stark). Das
  HTML-Budget bleibt Teil des Selbst-Audits aus `SKILL.md` und ist damit G1
  (Selbstauskunft), nicht mechanisch erzwungen — keiner der sechs Evals prüft es.
- **`tokens.css` ist in vier HTML-Templates dupliziert, nicht per Build
  zusammengeführt.** Jedes der vier `assets/*.html`-Templates bettet den
  vollständigen Inhalt von `assets/tokens.css` in ein eigenes `<style>`-Tag ein
  (Entscheidung für Selbstenthaltenheit ohne Build-Schritt, siehe
  `docs/superpowers/plans/2026-08-15-visual-summary.md`). Eine künftige
  Token-Änderung muss von Hand in allen fünf Dateien (`tokens.css` plus vier
  Templates) synchron gehalten werden — nichts erzwingt das mechanisch, ein
  Auseinanderlaufen fiele nur bei einer visuellen Stichprobe auf.
- **Der Ausgabepfad ist ohne Nutzer-Slug nicht vorhersagbar.** Ohne Sammel-Skript
  gibt es keine deterministische Pfadberechnung wie bei dev-reports
  `report_path`. Die Skill leitet ohne Vorgabe einen Slug aus der Kernthese ab —
  das ist für echte Nutzung gewollt, macht den Pfad für einen externen
  Konsumenten (ein Skript, das `docs/summaries/` durchsucht) aber nur nach dem
  Muster `<format>-<slug>` vorhersagbar, nie nach einem konkreten Dateinamen. Alle
  sechs Evals in `evals/visual-summary/evals.json` umgehen das, indem der Prompt
  den Slug ausdrücklich nennt — ein Prompt ohne Slug-Vorgabe ist damit
  eval-seitig ungetestet.
- **Referenzmarken-Adjazenz und -Legitimität sind nur für einen Fall über einen
  Judge geprüft, nicht generell mechanisch.** Der Contract aus `SKILL.md`
  verlangt, dass jede Zahl unmittelbar eine Referenzmarke mit einer echten
  Fundstelle trägt. Mechanisch geprüft wird das nur indirekt (Existenz von Zahl
  und Seitenreferenz getrennt in `buried-number-gets-page-ref`) bzw. strukturell
  über einen Judge-Claim im einen behavior-Eval
  (`unsupported-number-needs-a-reference-mark`). Fix-Runde 2 hat diesen einen
  Judge-Claim geschärft, damit er nicht nur die Form (Zahl+Marke+Listeneintrag),
  sondern auch die Legitimität des Listeneintrags prüft (eine Pseudo-Referenz
  wie „Nutzerangabe, nicht geprüft" besteht die Form, aber nicht mehr den
  Claim) — das gilt aber weiterhin nur für diesen einen Eval-Fall. Ein
  genereller Regex-Check „jede Zahl im Dokument braucht eine unmittelbar
  folgende Marke" wurde bewusst nicht gebaut — er träfe legitime
  Nicht-Beleg-Zahlen wie Jahreszahlen in Überschriften oder das Datum in der
  Meta-Zeile falsch positiv. Die Lücke ist eine bewusste Entscheidung, aber eine
  echte Grenze der Eval-Abdeckung: eine zweite unbelegte oder unecht belegte
  Zahl in einem sonst korrekten Dokument hat keinen zweiten Eval, der sie fängt.
- **Das Inhaltsmodell ist kein eigenständiges Artefakt.** Tier 0 ohne Skript
  bedeutet: Es gibt kein `model.json`, das Kernthese, Belege, Datenpunkte und
  offene Punkte vor dem Rendern festhält. Die Quellenbindung wird erst im
  gerenderten Output sichtbar (Referenzmarken plus Quellenliste). Ein Konsument,
  der das Modell selbst lesen wollte — unabhängig vom gewählten Medium — hat
  dafür kein Artefakt, nur die beiden Renderings.
- **Die dokumentweite Referenzmarken-Nummerierung ist nur als Regel dokumentiert,
  nicht mechanisch erzwungen.** Ein unabhängiger Review (Fix-Runde 2) fand: Der
  Platzhalter `{{REF_ID}}` tauchte in mehreren unabhängigen REPEAT-Blöcken auf
  (Belege, Chart-Zeilen, Quellenliste), ohne dass irgendwo stand, dass es ein
  einziger, blockübergreifender Zähler ist — ein gutgläubig ausfüllender Agent
  hätte plausibel pro Block bei 1 neu gezählt, dann zeigen Referenzmarken ins
  Leere. Behoben durch einen expliziten Kommentar am ersten REPEAT-Block in
  allen acht Templates, eine Contract-Zeile in `SKILL.md` und eine neue
  Gegenprobe im Selbst-Audit. Was damit noch **nicht** existiert: kein Eval
  prüft mechanisch, dass jede vergebene Marke im Text einen Quellenlisten-Eintrag
  hat und umgekehrt — die Gegenprobe ist G1 (Selbstauskunft im Selbst-Audit),
  keiner der sechs Evals verifiziert sie an einem echten, mehrere Belege
  tragenden Dokument. Ein Agent, der die neue Regel liest, aber trotzdem pro
  Block neu zählt, würde von keinem der sechs Evals auffällig.
- **`chat-distills-three-decisions` ist seit Fix-Runde 2 class `behavior` statt
  `contract`.** Ursprünglich fing ein `must_not` nur das Wort „Kaffee" aus der
  Rausch-Fixture — jede andere Rausch-Nachricht (Wetter, Meeting-Logistik,
  Feierabendbier, Urlaub) wäre ungehindert durchgerutscht, ohne den Eval rot zu
  machen (dieselbe Fehlerklasse wie dev-reports `must_not`-Regexe). Der Eval
  läuft jetzt mit einem Judge-Claim, der Vollständigkeit und Abwesenheit von
  Rauschen strukturell verlangt — kostet damit einen Judge-Aufruf mehr und läuft
  nicht mehr im billigen `--class contract`-Routine-Gate mit.
- **Fünf Fixtures trugen `"git": false`, obwohl ihre Evals einen Repo-Pfad
  prüften — der erste echte Lauf ging deshalb 0 von 6 bestanden durch.**
  `SKILL.md` legt fest: Repo (`.git` im cwd oder Elternverzeichnis) →
  `docs/summaries/…`, sonst `~/.skills/visual-summary/summaries/…`. Fünf der
  sechs Fixtures (`buried-number-doc`, `chat-three-decisions`, `unbelegt-draft`,
  `budget-trap-doc`, `trivial-note`) trugen `"git": false`, während ihre
  Assertions durchweg Pfade unter `docs/summaries/` erwarteten. Die Skill hat
  sich korrekt verhalten — ohne `.git` im Workspace griff der Nicht-Repo-Zweig,
  und jede Zusammenfassung landete im echten Home-Verzeichnis des ausführenden
  Nutzers, außerhalb jeder Workspace-Beobachtung (`evalkit.workspace.snapshot()`
  sieht nur Dateien unter der Workspace-Wurzel, siehe oben). Kein einziger
  `file_exists`/`file_matches`/`file_max_lines` konnte das je erreichen. Behoben
  durch `"git": true` in allen fünf Fixture-Manifesten — `empty-dir` (für
  `bare-request-triggers-triage`, das absichtlich keinen Repo-Pfad erwartet)
  bleibt `false`.
  **Die Lehre, allgemein für künftige Skills dieser Sammlung:** Eine
  Fixture, die einen conditionalen Ablageort prüft (Repo vs. kein Repo, wie hier;
  ebenso denkbar bei anderen Skills mit ähnlicher Verzweigung), muss die
  **Vorbedingung** dieses Zweigs selbst herstellen. Assertions und Fixture
  beschrieben hier zwei verschiedene Welten — der Eval-Autor sah beim Schreiben
  der Assertions „wir sind im Repo-Fall" vor Augen und beim Schreiben der
  Fixture „kein Grund für ein Repo, die Skill braucht ja nur eine Datei" —, und
  weil jede Seite für sich gelesen plausibel wirkte, fiel die Lücke beim
  Selbst-Review nicht auf. Erst der reale Agentenlauf zeigte es. Eine Prüfung,
  die das mechanisch vorab abfangen würde (z. B. ein Schema-Lint, der bei
  `file_exists`-Pfaden unter einem repo-typischen Präfix wie `docs/` ein
  `"git": true` in der referenzierten Fixture verlangt), existiert im
  Eval-Harness nicht — auch das eine Lücke für später.
- **`bare-request-triggers-triage`s `output_matches`-Regex war zu eng an
  Schlüsselwörter gebunden — ebenfalls erst im echten Lauf aufgefallen.** Die
  ursprüngliche Regex verlangte beide Themen (Publikum, Zweck) über feste
  Wortlisten (`wer\s+liest|leser|zielgruppe|adressat|publikum` bzw.
  `entscheidung|handlung|zweck|wofür|folgen\s+soll`) plus ein Fragezeichen. Die
  tatsächliche Formulierung der Skill traf keines der Publikums-Schlüsselwörter
  (plausibel z. B. „Für wen ist das gedacht?"), obwohl inhaltlich beide Fragen
  gestellt wurden — dieselbe „spröde Keyword-Regex"-Grenze von `output_matches`,
  die weiter oben unter „Assertion-Vokabular" bereits als inhärent (nicht als
  Implementierungsfehler) geführt wird, hier aber trotzdem produktiv zugeschlagen
  hat. Fix-Runde 3: Eval auf class `behavior` umgestellt, die Regex durch einen
  Judge-Claim ersetzt, der die beiden Themen inhaltlich statt wortwörtlich
  prüft. Das `must_not` (`file_absent`) bleibt als mechanischer, wortunabhängiger
  Riegel bestehen.
- **`bare-request-triggers-triage`s `must_not: file_absent` hatte die Polung
  verkehrt herum — der Eval verlangte damit sein eigenes Gegenteil.**
  `must_not` + `file_absent` heißt „es darf nicht sein, dass die Datei fehlt",
  also *muss* sie existieren. Der Eval soll aber belegen, dass die Skill bei
  „Fass das zusammen." erst fragt statt zu schreiben — er verlangte also exakt
  das Gegenteil seines eigenen Zwecks, und ein korrektes Nicht-Schreiben wurde
  als Verstoß gemeldet. `evalkit/runner.py` warnt im Code-Kommentar zu `grade()`
  ausdrücklich vor genau dieser Polungsfalle bei Judge-Claims in `must_not` —
  dieselbe Logik gilt unverändert für mechanische Typen wie `file_absent`.
  Behoben: `file_absent` jetzt in `must`. Zusätzlich, auch am echten Lauf
  verifiziert: selbst mit korrigierter Polung hätte die Assertion nichts
  bewacht, weil die verwendete Fixture `empty-dir` `"git": false` trägt — ohne
  `.git` ist `docs/summaries/…` unabhängig vom Skill-Verhalten immer abwesend
  (siehe Repo-Vorbedingungs-Lehre oben), dieselbe Fehlerklasse ein drittes Mal.
  Neue eigene Fixture `bare-request-repo` (`git: true`, ohne jedes Material)
  macht das Nicht-Vorhandensein wieder aussagekräftig. `empty-dir` blieb
  unangetastet — die Fixture gehört laut ihrer eigenen Beschreibung `handoff`
  und wird von dessen Evals mitbenutzt.
- **Der dritte, tiefste Fund: Die Skill wurde für den bare „Fass das
  zusammen."-Prompt anfangs gar nicht erst aufgerufen — kein Body-Text-Problem,
  sondern ein Routing-Problem.** Diagnose per `--evals-dir` mit einer
  Wegwerf-Sammlung und `--keep-workspace`, dann der Agent erneut direkt mit
  `--output-format stream-json --verbose` im selben Workspace gestartet, um
  Tool-Aufrufe statt nur der Endantwort zu sehen: Der Judge verneinte den
  Triage-Claim, weil im Transcript **kein einziger `Skill`-Tool-Aufruf**
  vorkam — der Agent ging direkt zu `Bash`/`Read` (Verzeichnis auflisten,
  README lesen) und lieferte eine generische Rückfrage nach dem Material,
  ohne je `visual-summary`s SKILL.md zu laden. Zwei Runden Textänderungen an
  `SKILL.md`s Ablauf-Abschnitt (kombinierte Rückfrage statt „erst Material,
  dann Triage", inklusive wörtlichem Beispieltext) hatten dadurch **keine**
  Wirkung — der Body wird nie gelesen, wenn die Skill nicht aufgerufen wird.
  Erst eine Ergänzung der Frontmatter-`description` (expliziter Hinweis, dass
  auch ein material-loser „fass das zusammen" ohne offensichtlichen Inhalt im
  Arbeitsverzeichnis in diese Skill routet, statt in generische
  Verzeichnis-Exploration) brachte den Agenten dazu, den `Skill`-Tool-Aufruf
  zu machen — danach griff der bereits korrigierte Ablauf-Text sofort und
  fehlerfrei (beide Fragen in einer Antwort, mit Format-Tabelle). **Lehre:**
  Ein Verhaltensdefekt bei Skills mit natürlichsprachlichem Routing kann in
  der `description` sitzen, nicht im SKILL.md-Body — und ein Body-Fix, der im
  echten Lauf wirkungslos bleibt, ist kein Beweis, dass der Body falsch war;
  es kann heißen, dass er nie gelesen wurde. `--output-format stream-json
  --verbose` (statt nur `text`) macht diesen Unterschied sichtbar, indem es
  Tool-Aufrufe statt nur die Endantwort zeigt.
- **Der Diagnose-Lauf zeigte zusätzlich, dass die Prozessisolation lückenhafter
  ist als der bestehende Isolation-Abschnitt oben vermuten lässt.** Das
  `system.init`-Event des CLI-Laufs listete unter `skills` nicht nur
  `visual-summary` aus dem Projekt-Workspace, sondern auch gut ein Dutzend
  offensichtlich persönliche, global installierte Skills (`deep-research`,
  `dataviz`, `update-config`, `code-review`, `schedule`, `run-skill-generator`
  u. a.), obwohl der Runner `--setting-sources project` setzt. Konsistent mit
  der bereits dokumentierten Grenze „Die Prozessumgebung des Agenten ist nicht
  isoliert" (siehe oben, `$HOME` wird nicht umgebogen) — hier aber am
  `skills`-Feld eines echten Laufs sichtbar bestätigt, nicht nur vermutet:
  Ein Eval kann in einer Umgebung mit vielen konkurrierenden, dem Skill fremden
  Skills laufen, was Routing-Entscheidungen zusätzlich beeinflusst.
## review-context

- **Der Uncommitted-Modus ist im Eval-Harness nicht prüfbar.** `collect_context.py` kann ohne
  `--range` das Arbeitsverzeichnis gegen HEAD reviewen (der realistischste Fall: „review meine
  gerade gemachte, noch nicht committete Änderung"), aber `evalkit.workspace.prepare()`
  hinterlässt nach jedem Fixture-Aufbau einen sauberen Baum — dieselbe Grenze, die oben bei
  `dirty-worktree` schon steht. Alle vier Evals in `evals/review-context/evals.json` nutzen
  deshalb `--range HEAD~1..HEAD`; der Uncommitted-Pfad ist nur durch Unit-Tests
  (`test_uncommitted_mode_reads_worktree`, `test_main_writes_cache_file`-Nachbarn) abgedeckt,
  nicht durch einen echten Agenten-Lauf.
- **Ob eine Commit-Message als Soll zählt, wird am Inhalt gemessen, nicht an der Anzahl der
  Commits im Range — eine eigene Entscheidung, nicht aus Spec 04 oder R13 zwingend ableitbar.**
  (Fix-Runde: Die erste Fassung nutzte eine Mindestanzahl von zwei Commits als Proxy und wurde
  live widerlegt — eine ausführliche, klar zielbeschreibende Message wurde als „nicht reviewbar"
  gemeldet, nur weil sie allein stand. Die Anzahl der Commits sagt nichts über die Aussagekraft
  ihrer Messages.) Die jetzige Regel (`_is_meaningful_commit_message()`): eine Message zählt,
  wenn sie einen Body jenseits der Betreffzeile hat, oder wenn ihre um ein Conventional-Commit-
  Präfix bereinigte Betreffzeile mindestens `MIN_SUBJECT_CHARS` (20) Zeichen hat und kein reiner
  Platzhalter ist (`GENERIC_COMMIT_SUBJECTS`: `wip`, `fix`, `tmp`, `misc`, …). Diese Schwellen
  sind selbst wieder eine Heuristik — eine 19 Zeichen lange, aber inhaltsreiche Betreffzeile
  zählt nicht, ein 20 Zeichen langes Füllwort ohne Aussage schon, solange es nicht im
  Platzhalter-Set steht.
- **Aufrufer-Suche ist namensbasiert, ohne Scope- oder Import-Analyse — und übersieht deshalb
  nicht zu wenige, sondern zu viele Treffer.** (Fix-Runde: Der ursprüngliche Text hier behauptete
  das Gegenteil — `self.name(...)`-Aufrufe seien falsch-negativ, würden also übersehen. Live
  widerlegt: `find_callers()` grept `\bname\s*\(` über den ganzen Baum, und der Wortgrenzen-Test
  `\b` steht bereits zwischen einem `.` und dem folgenden Namen — `self.add(x)` **matcht**, wird
  also mitgezählt. Reproduziert am eigenen Skript: Ein Review von `add()` zählt
  `seen_dirs.add(dir_rel)` aus `gather_conventions()` als Treffer mit, obwohl es `set.add()` ist,
  nicht die berührte Funktion.) Echte falsch-negative Fälle bleiben ein Import-Alias
  (`from x import name as anders`) und ein Aufruf, dessen öffnende Klammer durch einen
  Zeilenumbruch vom Funktionsnamen getrennt ist. Die Deckelung auf 20 Treffer wirkt bei
  falsch-positiven Treffern schädlicher als bei falsch-negativen: Füllt Rauschen (fremde
  `.add()`-artige Aufrufe) die ersten 20 Plätze, verdrängt es echte Aufrufer aus der gezeigten
  Liste, statt nur zu fehlen — der Reviewer sieht eine volle, aber irreführende Liste statt einer
  ehrlich unvollständigen.
- **`_has_meaningful_spec_content()` prüft jetzt Inhalt statt Existenz, aber mit einer eigenen
  Magic-Number-Grenze.** (Fix-Runde: Die erste Fassung von `find_feature_spec()` prüfte nur, ob
  überhaupt eine `.md`-Datei unter `docs/specs/wip/` lag — eine leere Datei genügte, um
  `resolve_soll()` `source == "feature_spec"` melden zu lassen und damit den Kernbefund
  „nicht reviewbar" fälschlich zu unterdrücken. Live reproduziert, jetzt behoben.) Die Behebung
  selbst bringt eine neue, kleinere Grenze mit: `MIN_SPEC_CONTENT_CHARS = 40` ist eine
  Schätzung, keine gemessene Größe. Eine legitime, aber knapp und präzise formulierte Spec unter
  40 Zeichen Prosa (ohne Given/When/Then) würde fälschlich als „nicht tragfähig" verworfen; eine
  40 Zeichen lange, aber inhaltsleere Platzhalter-Zeile („TODO: Diese Spec noch ausfüllen, bitte
  nicht vergessen") zählt umgekehrt fälschlich als Soll. Wortzahl ist kein Aussagekraft-Maß,
  nur ein billiger Proxy dafür.
- **`_extract_signature()` zählt Klammertiefe zeilenweise, ohne Strings zu berücksichtigen.**
  Ein Default-Wert wie `sep: str = "("` würde die Tiefenzählung verfälschen und die Signatur zu
  früh oder zu spät abschneiden. In der Praxis selten, aber eine Heuristik, kein Parser für
  diesen einen Aspekt — `ast.parse()` selbst ist exakt, nur die Rückübersetzung in Quelltext
  nicht.
- **Symbol- und Aufrufer-Erkennung entfällt für gelöschte Dateien.** Eine gelöschte Datei hat
  keinen „Nachher"-Zustand, aus dem `ast` oder die TS-Regex Symbolgrenzen ableiten könnten. Wer
  wissen will, wer ein jetzt entferntes Symbol noch aufruft, bekommt das aus diesem Paket nicht
  — eine bewusste Lücke (siehe SKILL.md-Referenz), keine überprüfte.
- **TS/JS-Symbolerkennung sieht nur die Deklarationszeile, keine Body-Änderungen.** Anders als
  bei Python (Zeilenbereich-Überlappung über den ganzen Funktionskörper) zählt eine TS/JS-
  Funktion nur als „berührt", wenn sich ihre eigene Signaturzeile im geänderten Bereich
  befindet. Eine reine Body-Änderung ohne Signaturänderung wird für TS/JS nicht erkannt — R16
  erlaubt die grep-basierte TS-Suche ausdrücklich, diese konkrete Asymmetrie zu Python ist aber
  ungetestet gegen eine echte TS-Fixture (alle vier Evals nutzen Python).
- **`docs/decisions.md` hat noch keine reale Instanz zum Testen.** `read_decisions()` folgt der
  Konsumenten-Regel aus Spec 00 §1 (Header fehlt oder Schema passt nicht → sichtbar
  übersprungen), aber die Skill, die diese Datei mit Kopfzeile erzeugt (feature-spec, Spec 03),
  ist noch nicht gebaut. Der Regelfall in jedem echten Repo dieser Sammlung ist aktuell
  `missing`; `no_header`/`schema_mismatch`/`read` sind nur durch Unit-Tests mit synthetischem
  Inhalt geprüft, nicht gegen ein reales `docs/decisions.md`.
- **`gather_conventions()` prüft nur Existenz, nie Inhalt.** Konventions-Marker
  (`pyproject.toml`, `tsconfig.json`, …) werden nur als vorhanden/fehlend gemeldet; ob ein
  `ruff.toml` z. B. Line-Length-Regeln enthält, die für die Vereinfachungslinse relevant wären,
  bleibt ungelesen. Absichtlich Tier-1-minimal, aber eine Grenze der Simplification-Paket-Tiefe.
- **Die Aufrufer-Deckelung (20, benannte Grenze) ist nur unit-getestet, nicht eval-getestet.**
  `test_find_callers_caps_with_named_limit` deckt den Fall mechanisch ab; ein echter
  Agenten-Lauf gegen eine Fixture mit > 20 Aufrufern existiert nicht — der Eval-Umfang war laut
  Auftrag auf vier Evals begrenzt, und die anderen drei Ränder (kein Soll, Spec-Kriterien,
  Anti-Zeremonie) wogen dafür schwerer.
## verified-research

- **Die Quellenauswahl im echten Web bleibt ungeprüft.** Spec 12s Eval 1 verlangt eine
  Frage, „deren Top-Suchtreffer ein SEO-Aggregator mit veralteter Zahl ist" — das hängt
  an lebenden Suchergebnissen und wäre je nach Tagesform grün oder rot, ohne dass sich
  an der Skill etwas geändert hat. `evals/verified-research/evals.json` prüft deshalb
  ausschließlich den *Prozess* mit lokalen Fixtures (Register vor Suche, Tier am Claim,
  Wissensdatei-Update, Delta-Trennung, Registereintrag, spotcheck-Fang) — nie, ob die
  Skill in einer echten Websuche die richtige Quelle unter vielen findet. Das ist eine
  bewusste, aber echte Lücke: Ob `verified-research` in der Praxis tatsächlich
  Primärquellen vor SEO-Aggregatoren bevorzugt, wenn frei gesucht werden muss, ist mit
  diesem Eval-Set nicht belegt.
- **Verzeichnis- statt Datei-Ebene für den Projekt-Override (eigene Entscheidung, keine
  Spec-00-Vorgabe).** Spec 00 §1 sagt für nicht projektgebundene Artefakte nur: Standard
  ist `~/.skills/`, mit optionalem Projekt-Override — „dasselbe Muster wie persönliche
  vs. Projekt-Skills". Sie nennt keine Bedingung dafür, *wann* der Override greift.
  `registry.py resolve_base_dir()` prüft, ob `.skills/verified-research/` im Projekt
  existiert (Verzeichnis-Ebene) — das ist eine eigene Entscheidung dieser
  Implementierung, nicht Spec 00. Begründung: Ein Override auf Datei-Ebene (nur falls
  eine gleichnamige Datei im Projekt schon existiert, wie Spec 12 es für das Register
  nahelegt) würde bei `research/<thema>.md` nie greifen — eine neue Wissensdatei hat bei
  ihrer ersten Recherche naturgemäß noch keine gleichnamige Vorgänger-Datei, der erste
  Schreibzugriff ginge also immer nach `~/.skills/verified-research/` — im Eval-Harness
  das echte Home-Verzeichnis des Aufrufers (siehe „Isolation" oben). Alle sieben
  Fixtures legen deshalb `.skills/verified-research/registry.json` im Workspace an,
  damit dieser Fall im Eval-Set nicht auftritt. Läuft die Skill jedoch in einem Projekt,
  das weder `.skills/verified-research/` noch eine bestehende Wissensdatei hat,
  entscheidet dieselbe Entscheidung, ob der allererste Lauf projektlokal oder global
  landet — das ist eine begründete, aber selbst getroffene Auslegungsentscheidung, die
  ein künftiger Review absegnen oder verwerfen sollte, keine aus Spec 00 zitierte Regel.
- **Script-Pfad-Konvention ungeprüft gegen die tatsächliche Eval-Installation.**
  `evalkit.workspace.prepare()` installiert eine Skill nach
  `<workspace>/.claude/skills/<name>/`, aber SKILL.md (wie auch bei `dev-report`)
  instruiert Kommandos mit dem repo-root-relativen Pfad
  `skills/verified-research/scripts/registry.py`. Ob der Agent im echten Eval-Lauf
  diesen Pfad findet (z. B. weil er nach einem Fehlschlag selbst nach der Datei sucht)
  oder die Skill deshalb an allen sieben Evals scheitert, wurde nicht getestet — dieser
  Auftrag durfte `run_evals.py` nicht ausführen. Das betrifft nicht nur diese Skill,
  sondern denselben Pfad-Kontrakt, den `dev-report` bereits verwendet.
- **Beschreibungs-basiertes Routing gegen `deep-research` ist unbelegt.** Die
  Description in `SKILL.md` grenzt inhaltlich gegen `deep-research` ab (Register,
  Tiers, Gedächtnis über frühere Läufe), aber ob das reicht, damit Claude Code bei einer
  realistischen Nutzeranfrage tatsächlich `verified-research` statt der global
  installierten `deep-research` wählt, ist ungetestet — kein Eval prüft
  Skill-*Auswahl*, nur das Verhalten, nachdem eine Skill bereits aktiv ist (und die
  Prompts benutzen absichtlich Vokabular wie „Quellenregister"/„Tier-Bewertung", das
  die Auswahl in Richtung `verified-research` lenken soll, ohne dass das mechanisch
  erzwungen wäre).
- **`unknown-source-gets-registry-entry`s zweite Assertion ist positionsabhängig.**
  Die Regex verlangt `"pattern"` vor `"notiz"` mit maximal 400 Zeichen dazwischen. Das
  gilt für jeden Eintrag, den `registry.py add_entry()` erzeugt (Schlüsselreihenfolge
  ist durch den Code fixiert), bricht aber, falls ein künftiger Agent das Register von
  Hand statt über `registry.py` bearbeitet und dabei die Feldreihenfolge ändert.
## testing-strategy

- **Fix-Runde 3 (zentraler Bestätigungslauf, 3/4): `legacy-trap` war ein
  echter Harness-Bug, `anti-ceremony` ein echter Description-Defekt.** Der
  „embedded null byte"-Fehler bei `legacy-trap`, den ich in Fix-Runde 2 als
  vermutliches Session-Limit-Artefakt eingestuft hatte, war tatsächlich ein
  Bug in `evalkit/workspace.py`: `dump_changed_files` liest jede geänderte
  Datei als Text, ein `__pycache__/*.pyc` im Workspace enthält aber Nullbytes,
  die `errors="replace"` durchlässt und die `subprocess` im Judge-Argument
  verbietet. Behoben in `evalkit/workspace.py` (Commit `e186556` auf
  `feat/dev-report`, hier übernommen) — kein Fund dieser Skill, aber die
  Nullbyte-Sackgasse hätte jede Skill mit Judge-Assertion getroffen, sobald
  Python im Workspace lief. `anti-ceremony-single-test-stays-short` blieb
  offen: Diagnose zeigte, dass der Prompt „ich hab eine Funktion ergänzt,
  brauche einen Test" fast wörtlich auf die eigene SKILL.md-Abgrenzung gegen
  `test-driven-development` passte („implementing a single already-planned
  test") — die Description schloss sich damit selbst vom
  Pflicht-Anti-Zeremonie-Fall aus Spec 00 §2 aus, obwohl der Body (einmal
  geladen) den Fall korrekt behandelt hätte. Behoben durch schärfere
  Formulierung: TDD ist der *Zyklus* aus fehlschlagendem Test und Code
  während aktiver Implementierung, testing-strategy deckt auch das
  *Zumessen* eines einzelnen neuen Tests für bereits existierenden Code ab.
  **Diagnose-Lehre:** Ein `--keep-workspace`-Verzeichnis, das `run_evals.py`
  bereits einmal bespielt hat, darf für einen zweiten, direkten
  Diagnose-Aufruf nicht wiederverwendet werden, sobald der Prompt
  Schreibzugriffe auslösen kann — der erste Diagnoseversuch für
  `anti-ceremony` lief versehentlich im bereits vom echten Lauf veränderten
  Workspace und bestätigte nur dessen (bereits geschriebene) Testdatei, ohne
  eigenständige Aussagekraft. Ein frischer `evalkit.workspace.prepare()`-Aufruf
  behob das.
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
## rest-api-architect

- **Der Spectral-/oasdiff-Erfolgspfad in `gate.py` ist nur mit gemocktem `subprocess`
  getestet, nie mit einem echten Werkzeug.** Spectral, oasdiff und `npx` sind in dieser
  Umgebung nicht installiert (Node ist vorhanden, `npx` nicht) — `run_lint` und
  `run_breaking_change_check` shellen im Erfolgspfad tatsächlich `spectral lint`/`oasdiff
  breaking` aus und parsen deren JSON-Ausgabe, aber kein Test hat das gegen ein echtes
  Werkzeug verifiziert. Mechanisch geprüft ist: Toolchain-Erkennung, Degradationsmeldung,
  die Konventions-Checkliste, und die Parsing-Logik gegen selbst konstruierte Fake-JSON-
  Ausgaben. Ob das reale CLI-Format (Flags, Exit-Codes, JSON-Struktur von `spectral lint -f
  json` und `oasdiff breaking -f json`) tatsächlich so aussieht wie hier angenommen, ist
  unverifizierte Annahme, kein Befund. Nirgends in Code oder Doku dieser Skill steht
  „erprobt" für diesen Pfad.
- **Ob echtes Spectral den `_meta`-Schlüssel im generierten Ruleset toleriert, ist
  ungeprüft.** `docs/artifact-header.md` verlangt für JSON-Artefakte einen `_meta`-Schlüssel;
  `spectral-ruleset.json` trägt ihn entsprechend der Konvention. Ob Spectrals
  Ruleset-Schema-Validierung einen unbekannten Top-Level-Schlüssel klaglos akzeptiert oder
  den Ladevorgang verweigert, konnte hier nicht getestet werden (kein Spectral installiert).
- **Der YAML-Dumper in `extract_openapi.py` wurde extern gegen echtes PyYAML geprüft und ist
  für seinen Einsatzbereich tragfähig — mit einer Lücke, die jetzt geschlossen ist.** Ein
  unabhängiger Reviewer hat ihn mit installiertem PyYAML 6.0.3 gegen Doppelpunkte in Werten,
  führende/folgende Leerzeichen, `yes`/`no`/`on`/`1.0`/`null`-artige Strings, mehrzeilige
  Beschreibungen (via `\n`-Escape), Sonderzeichen (`: [ ] { } # & * | > % @` Backtick), sehr
  lange Zeilen, Tabs und Unicode geprüft — alle liefen korrekt durch. Eine reale Lücke wurde
  gefunden und behoben: ein rohes Carriage-Return (`\r`) wurde nicht escaped und wäre von
  echten YAML-Loadern gemäß Flow-Scalar-Regeln still zu einem Leerzeichen gefaltet worden
  (kein Parse-Fehler, eine stille Verfälschung) — `_yaml_quote` escaped `\r` jetzt wie `\\`,
  `"` und `\n`, mit Test. **Restliche Grenze:** PyYAML ist in keiner der Python-Installationen
  dieses Repos verfügbar (Projekt-venv, System-`python3`, Miniconda-`python3`); die Prüfung
  gegen echtes PyYAML war ein einmaliger externer Check des Reviewers, kein Teil dieser
  Test-Suite oder CI. Künftige Änderungen am Dumper laufen hier weiterhin nur gegen
  golden-string-Tests, nicht automatisch gegen einen echten YAML-Loader.
- **Cross-File-Router-Komposition wird von `extract_openapi.py` nicht aufgelöst.**
  `app.include_router(sub_router, prefix="/v1")`, wenn `sub_router` in einer anderen Datei
  definiert ist, wird nicht verfolgt — Pfade aus einem so gemounteten Sub-Router erscheinen
  ohne das Präfix. Bewusste Aufwand-Nutzen-Grenze, keine False-Positive-Gefahr (kein Pfad
  wird erfunden), aber eine Lücke in der Vollständigkeit.
- **Express/Hono-Routen sind strukturell immer `x-verified: false`, auch bei korrekt
  passender Textsuche.** Beabsichtigt (R2: Textsuche kennt keinen Kontrollfluss), bedeutet
  aber auch: Eine vollständig saubere Express-Codebasis bekommt von diesem Skript nie ein
  `x-verified: true` — echtes AST-Parsing für JS/TS wäre eine neue Abhängigkeit und ist
  out of scope.
- **Express-Routen-Erkennung akzeptiert seit dem Fix-Review jeden Variablennamen vor
  `.get()`/`.post()`/... (vorher nur `app`/`router`), um drei per Ausführung nachgewiesene
  Fälle stillen Routen-Verlusts zu schließen — das erhöht das False-Positive-Risiko bei
  generischen `.get()`-Aufrufen auf Nicht-Router-Objekten** (z. B. Cache-/Map-Zugriffe wie
  `cache.get('key')`). Hingenommen, weil jeder Treffer ohnehin `x-verified: false` trägt und
  nie stillschweigend als geprüft gilt — mehr sichtbare, niedrig-vertrauenswürdige Treffer
  sind hier der bewusst gewählte Fehler, nicht stille Vollständigkeitslücken.
- **`.route(path).method(handler)`-Chaining (Express-Idiom) wird von `extract_express()` nicht
  erkannt.** Neu identifiziert beim Fix-Review, nicht behoben (außerhalb der drei konkret
  nachgewiesenen Defekte dieser Runde) — die Regex verlangt Pfad und Methode im selben
  `.method('/pfad', ...)`-Aufruf; ein vorangestelltes `.route('/pfad')` mit separat
  angehängtem `.get(handler)` liefert keinen Treffer, keine Warnung.
- **`extract_openapi.py`s Auffangnetz für FastAPI-Registrierungs-„Lookalikes" ist selbst eine
  Heuristik, kein Beweis von Vollständigkeit.** Der Abgleich „wie viele Decorator-/
  `add_api_route`/`add_route`-artige Zeilen im Rohtext" gegen „wie viele davon hat der
  AST-Walk tatsächlich zugeordnet" (`extract_fastapi()`) deckt aliasierte Decorator-Funktionen
  ab (`get = app.get`, `@get(...)`), aber nicht jedes denkbare Registrierungsmuster — z. B.
  Router, die mehrfach über Fabrikfunktionen weitergereicht werden, oder Decorators, die über
  `functools.partial`/`functools.wraps`-Konstrukte gebaut werden. Der fehlende Treffer wäre in
  diesen Restfällen wieder ein stilles Verschwinden, keine sichtbare Markierung.
- **Die fünf rest-api-architect-Evals sind nicht gelaufen.** `load_evals()` bestätigt nur
  Schema-Gültigkeit und dass die Fixtures einen Workspace aufbauen (per
  `evalkit.workspace.prepare()` geprüft). Ob die Prompts die beschriebenen Verhaltensweisen
  tatsächlich provozieren (Umbenennungs-Versuchung, Massen-Refactoring-Versuchung, stille
  Spec-Drift), zeigt erst ein echter `run_evals.py`-Lauf. `rename-triggers-deprecation-path`
  wurde beim Fix-Review von `contract` auf `behavior` umklassifiziert (Judge-Assertion nötig,
  um an skill-eigenes Vokabular statt an generisches REST-Wissen zu binden) — die allgemeinen
  Judge-Grenzen aus dem Abschnitt „Judge" oben gelten damit jetzt auch für diesen Eval.
## sql-schema-architect

Ein unabhängiges Review nach dem ersten Merge-Kandidaten fand drei Defekte,
die dazu führten, dass eine gefährliche Migration als unbedenklich
durchging — bei dieser Skill die einzige Fehlerrichtung, die zählt. Alle
drei sind in einer Fix-Runde behoben (Commits ab dem Review); was danach
bleibt, steht hier.

- **Der Mehrschritt-Plan-Marker prüft Struktur, nicht Wahrheitsgehalt.**
  Behoben wurde der konkrete Bypass — ein Marker wie
  `# Mehrschritt-Plan: siehe unten unten` erfüllte vorher nur eine
  Längenschwelle (>10 Zeichen) und ließ eine tatsächlich rote Migration als
  `pass` durch. Die Prüfung verlangt jetzt mindestens zwei unterschiedliche
  Begriffe aus einem Vokabular (`nullable`, `backfill`, `batch`,
  `constraint`, `valid`, `concurrently`, `revision`) — und selbst mit
  erfüllter Struktur wird eine rote Migration nie mehr automatisch `pass`,
  sondern `review_required` mit expliziter Begründung. Was bleibt: die
  Struktur-Prüfung erkennt nur, dass die *richtigen Wörter* vorkommen, nicht
  ob der beschriebene Plan zu den tatsächlichen Operationen der Revision
  passt oder ob die genannten Revisionen existieren. Ein Marker, der zwei
  Vokabeln nennt, ohne dass ein echter Mehrschritt-Plan dahintersteht,
  besteht die mechanische Prüfung weiterhin — er verlangt aber jetzt
  mindestens eine menschliche Freigabe statt eines stillen `pass`, was das
  Risiko deutlich, aber nicht auf null senkt.
- **`op.*`-Aufrufe werden nur bis zu einer bestimmten Grenze verfolgt.**
  Behoben wurde der konkrete Fall: `upgrade()` ruft eine andere,
  modulweite Funktion auf (`def upgrade(): _apply()`), die ihrerseits
  `op.execute(...)` enthält — vorher unsichtbar für den Scanner, jetzt
  rekursiv verfolgt (mit Zyklenschutz). Nicht verfolgt, bewusst: Aufrufe
  über `self.`/Modul-Attribute, Variablen, Klassenmethoden, importierte
  Funktionen, dynamisch aufgelöste Aufrufe (`getattr(...)`). Als
  Sicherheitsnetz für genau diese Grenze meldet `migration_gate.py` jetzt
  „upgrade() enthält Code, aber keine Operation erkennbar" als eigenen
  Kontraktverstoß, sobald `upgrade()` nicht-trivial ist und der Scanner
  null Operationen findet — das fängt auch unbekannte künftige
  Umgehungswege ab, solange sie zu null erkannten Operationen führen.
  Ein Fall, den das **nicht** abfängt: `upgrade()` enthält eine sichtbare,
  grün klassifizierte Operation *und* einen nicht verfolgten Aufruf, der
  intern eine gefährliche Operation versteckt — dann bleibt der
  Gesamtbefund grün/gelb, weil mindestens eine Operation gefunden wurde.
  Dieser Teilsichtbarkeits-Fall wurde bewusst nicht zusätzlich als
  generisches „unresolved calls"-Signal behandelt, weil ein solches Signal
  auf jeden nicht aufgelösten Aufruf anschlagen würde (auch `print(...)`,
  `logging.info(...)`) und harmlose Revisionen unnötig auf
  `review_required` degradieren würde.
- **`add_column` löst nur einfache lokale Variablen auf.** Behoben:
  `col = sa.Column(..., nullable=False); op.add_column(t, col)` wird jetzt
  wie die Inline-Form `op.add_column(t, sa.Column(..., nullable=False))`
  behandelt — vorher fiel die Variablen-Form fälschlich auf „additive
  Spalte, grün". Aufgelöst werden nur Zuweisungen direkt im Funktionsrumpf,
  nicht in `if`/`for`-Blöcken, nicht über mehrere Funktionen hinweg. Ein
  nicht auflösbarer Fall (Rückgabewert eines Funktionsaufrufs, Zuweisung in
  einem verschachtelten Block) wird korrekt `unknown`, nie grün — aber auch
  hier gilt: nur die Spalten-Zuweisung selbst wird verfolgt, nicht beliebig
  komplexer umgebender Kontrollfluss.
- **SQLAlchemy-2.0-Stil (`Mapped[T]`) bleibt für die Typ-Prüfung blind —
  jetzt aber gemeldet statt stillschweigend übergangen.** `id: Mapped[int]
  = mapped_column(primary_key=True)` liefert keinen SQL-Typ-Ausdruck aus
  `Column(...)`/`mapped_column(...)`, weil der reale SQL-Typ oft erst aus
  einer projektspezifischen `type_annotation_map` folgt, die die Skill
  nicht kennt und nicht raten darf. `lint_schema.py` meldet das jetzt als
  eigenen Befund (`type_coverage`) pro betroffener Spalte, statt die
  varchar-/timestamptz-Regeln einfach nichts finden zu lassen; `gen_erd.py`
  zeigt zusätzlich die Python-Annotation als Diagnose-Hinweis
  (`? (Mapped_int)`). Was weiterhin fehlt: eine echte Typ-Herleitung aus
  gängigen `type_annotation_map`-Konventionen (z. B. `str` → `String` vs.
  `Text`) — das wäre Raten, kein Lesen, und bleibt deshalb bewusst
  ungebaut.
- **`--hook-check`s Bash-Muster ist gegen Befehls-Indirektion verwundbar.**
  Die Regex erkennt `alembic upgrade` als Substring, jetzt case-insensitiv
  und dadurch tatsächlich robust gegen `poetry run alembic upgrade head`,
  `python -m alembic upgrade head` und `ALEMBIC UPGRADE HEAD` (verifiziert;
  frühere Selbstauskunft, dass die ersten beiden Formen den Hook umgingen,
  war falsch). Real und unbehoben: ein Makefile-Target (`make migrate`)
  oder ein CI-Skript, dessen Bash-Aufruf den Text „alembic upgrade" nicht
  enthält, weil er woanders in einem separaten Prozess läuft — der Hook
  sieht nur den Bash-Befehl, den der Agent aufruft, nicht was ein Target
  intern tut.
## subagent-dev

Ein unabhängiges Review fand drei Defekte (D1–D3) und vier Lücken (L1–L4),
alle drei Defekte reproduziert. Gemeinsame Form: der Mechanismus meldete
Sicherheit, die er nicht geprüft hatte. Die drei Defekte sind behoben, mit
Regressionstests, die die im Review reproduzierten Fälle nachbauen:

- **D1 (behoben): `verify` meldete PASS für eine übersprungene Prüfung.**
  Fehlte `--base`, wurde die Allowlist-Prüfung stillschweigend übersprungen
  und trotzdem `"ok": true` gemeldet. Jetzt gibt es ein drittes Verdikt,
  `unverified` — ein übersprungenes Gate meldet nie Erfolg (Spec 00 §3).
  `"pass"` verlangt jetzt `allowlist_checked: true` und keine Verstöße.
- **D2 (behoben): Datei-Überlappung übersah Case-Drift, absolut-vs-relativ,
  Globs und Umbenennungen.** `_paths_overlap` normalisiert jetzt
  Groß-/Kleinschreibung und Backslashes, vergleicht per Präfix *und* Suffix
  (deckt absolut gegen relativ ab) und behandelt ein Glob-Muster als seinen
  konkreten Wurzel-Ordner. Eine `Files:`-Bullet-Zeile mit unbekanntem Verb
  (z. B. ein selbst erfundenes `Rename:`) machte die Task vorher spurlos
  files-blind; jetzt erkennt `_parse_files` `Rename: \`alt\` -> \`neu\``
  explizit (beide Pfade in die Allowlist) und markiert jede *andere*
  unerkannte Zeile über ein Sicherheitsnetz als `files_unknown`, selbst wenn
  andere Zeilen im selben Block sauber geparst wurden.
- **D3 (behoben): Interface-Überlappung hatte kein Äquivalent zu
  `files_unknown` und behauptete aktiv „keine Überlappung", obwohl sie nie
  danach gesucht hatte.** `Consumes:`/`Produces:`-Text ohne Backtick-Symbol
  und ohne den Leerfall „nichts Neues" markiert die Task jetzt
  `interfaces_unknown` und damit überlappend mit jeder anderen — sichtbar im
  `gate.json`-Artefakt (`interfaces_unknown`-Feld pro Task, Sichtbarkeits-
  Regel aus Spec 00 §3). Die Begründungstexte im Gate-Urteil sprechen jetzt
  von „erkannter" statt bloß „Überlappung", um nicht mehr zu behaupten, eine
  Prüfung habe stattgefunden, die nur unterblieben ist.

Zusätzlich mitgezogen, weil sie mit denselben Funktionen zusammenhängen und
mit vertretbarem Aufwand behebbar waren:

- **L2 (verbessert, nicht vollständig gelöst): `check_produces` verwechselte
  gleichnamige Symbole aus unterschiedlichem Scope.** `ast.walk` kennt keinen
  Scope; zwei unabhängige Definitionen desselben Namens (Top-Level-Funktion +
  Hilfsfunktion, zwei Klassenmethoden) sammelt das Skript jetzt vollständig
  statt nur die zuletzt besuchte zu behalten. Passt mindestens eine Arity zur
  erwarteten, gilt das Symbol als `present` mit einem Hinweis auf die
  weiteren Definitionen im Detail-Text; passt keine, aber es gibt mehrere
  unterschiedliche, ist das Ergebnis `ambiguous` statt eines geratenen PASS
  oder FAIL. **Restrisiko:** Es gibt weiterhin keinen echten Scope-Abgleich
  (dafür müsste importiert werden, was diese Skill nach Vorab-Entscheidung A3
  nie tut) — passt eine von mehreren Definitionen zufällig zur erwarteten
  Arity, meldet `check_produces` `present`, auch wenn ausgerechnet die
  falsche (z. B. die Top-Level-Funktion) die maßgebliche wäre.
- **L3 (behoben): `check_allowlist` erzeugte eine Fehlmeldung bei
  unkommittierten Umbenennungen.** `git status --porcelain` schreibt eine
  Umbenennung als `"R  alt.py -> neu.py"`; das alte `line[3:]` schnitt nur
  das Statuspräfix ab und behandelte den ganzen Rest als einen Pfad, der mit
  keinem Allowlist-Eintrag matchen konnte. Jetzt wird bei `" -> "` in beide
  Pfade aufgeteilt.

## subagent-dev — Befunde aus dem Einsatz an Spec 15 (2026-09-01)

**Beide Parser-Defekte unten sind behoben** (Fix-Runde nach der Prüfung
`docs/assessment-writing-skills-writing-plans.md`, Schritt 1): Ein
Backtick-Ausdruck ohne gültigen Bezeichner macht die Task jetzt unbekannt
(fail-closed), Prosa unter dem Interfaces-Block wird getrennt geführt statt in
`Produces:` zu laufen, und `plan_to_tasks.py lint` nennt pro Task den Grund.
Gemessen über alle 17 Pläne: **8 parsen nicht** (Exit 2), 8 tragen zwischen 14
und 78 Befunde, einer ist sauber (der explain-Plan, nach Verschieben eines
Prosa-Absatzes). Die Bedienbarkeits-Lehre
steht jetzt als Zeile in der Anti-Rationalisierungs-Tabelle. Was bleibt: Der
Fail-Closed-Fix ist **laut** — beschreibende Backticks in Interfaces
(`\`(git_range, end_label)\``, `\`facts.json\``) machen eine Task unbekannt, obwohl
sie kein Symbol meinen. Das ist die richtige Richtung, aber die saubere Lösung ist
ein erklärtes Interface-Vokabular (`token:`, `file:`, `fn:`), und das gehört zu
Spec 16, nicht in diesen Fix — dort ist es inzwischen gebaut (Abschnitt
`impl-plan`). Der historische Befund darunter bleibt stehen.


Beim ersten produktiven Einsatz des Gates an einem fremden Plan (`explain`) kippte
das Verdikt dreimal — `sequential`, `parallel`, `sequential` — allein durch
Umformulierungen im `**Interfaces:**`-Block, ohne dass sich an der tatsächlichen
Kopplung der Tasks etwas änderte. Zwei benennbare Ursachen:

- **Ein Backtick-Symbol, das kein gültiger Bezeichner ist, öffnet das Gate
  still.** Die Symbol-Extraktion (heute `extract_symbols()`) verlangte `[A-Za-z_][A-Za-z0-9_.]*`;
  Namen mit Doppelpunkt oder Bindestrich (`` `Unverified:` ``, `` `Next:` ``,
  `` `effort-ladder` ``) liefern **null Symbole**. `_has_unrecognized_prose()`
  wiederum meldet sie *nicht* als unsicher, weil ein Backtick vorhanden ist. Die
  Kombination heißt: kein Symbol **und** nichts Unbekanntes, also keine
  Abhängigkeit — obwohl die Tasks über genau dieses Symbol gekoppelt sind. Der
  Contract sagt „Prosa ohne Backtick-Symbol gilt als Abhängigkeit"; die Lücke
  liegt dazwischen: Backtick vorhanden, Symbol trotzdem nicht extrahierbar. Das
  ist ein Fail-Open in einem Gate, dessen erklärte Haltung „im Zweifel keine
  Parallelisierung" ist. Fix-Vorschlag: Wenn ein Backtick-Ausdruck im
  Interfaces-Block zu keinem Symbol führt, `interfaces_unknown=True` setzen statt
  ihn zu ignorieren.
- **Prosa zwischen dem Interfaces-Block und dem ersten Step wird in `Produces:`
  hineingelesen.** `_parse_interfaces()` schneidet erst bei `\n- [ ]`, ein
  erklärender Satz darunter landet also im Produces-Text und macht ihn per
  `_has_unrecognized_prose()` unbekannt. Das ist konservativ (Fail-Closed) und
  damit ungefährlich, erzeugt aber ein `sequential` mit falscher Begründung —
  im ersten Lauf war Task 5 der einzige `interfaces_unknown`, und allein dieses
  Flag koppelte alle sechs Tasks.

**Die eigentliche Lehre ist die Bedienbarkeit, nicht der Parser.** Wer das Gate
bedient, kann durch reines Umformulieren des Interfaces-Blocks auf ein
`parallel`-Urteil hinarbeiten, ohne je die Aufgabenzuschnitte zu ändern — genau
die Sorte Nachziehen, die `docs/skill-building-pitfalls.md` unter „Ein Budget wird
nicht nachgezogen, bis es passt" verbietet. Das Gate ist nur so hart wie die
Disziplin dessen, der die `Files:`/`Interfaces:`-Blöcke schreibt. Ein Hinweis
darauf fehlt in SKILL.md; die Anti-Rationalisierungs-Tabelle deckt „vier Agents
wirken produktiver" ab, nicht „ich formuliere die Interfaces so lange um, bis es
parallel sagt".

## subagent-dev — Fix-Runde 2 (Bestätigungslauf)

Der zentrale Bestätigungslauf nach Fix-Runde 1 bestätigte D1–D3 (drei Evals
grün), fand aber `research-fanout-stays-distilled` weiterhin rot — nicht
schwankend, sondern systematisch: 66 Zeilen in einem Lauf, 64 in einem
zweiten, beide über dem Budget von 60. Nachgerechnet: Drei Funde à drei
Zeilen (Aussage, Beleg, Konfidenz) plus Kopfzeile sind zwölf bis fünfzehn
Zeilen — es standen also rund fünfzig Zeilen Beiwerk in der generierten
Datei, die kein Fund waren. Der damalige `references/research-fanout.md` gab
zwar ein Rückgabe-Schema vor, verbot aber nichts: kein Verbot einer
Einleitung, eines Vorgehensberichts, einer Zusammenfassung der
Zusammenfassung oder wiederholter Pfadangaben. Das Budget wurde **nicht**
angehoben (das wäre dieselbe Fehlerklasse mit umgekehrtem Vorzeichen —
eine Prüfung so lange verbiegen, bis sie besteht). Stattdessen wurde das
Schema in `references/research-fanout.md` und `SKILL.md` verschärft: ein
Fund ist genau drei Zeilen, nichts anderes steht in der Datei, mit
expliziter Verbotsliste und einem durchgerechneten Beispiel (elf Zeilen für
drei Funde, exakt an der Fixture aus `research-scan-target` orientiert).

**Nicht direkt beobachtet:** Der tatsächliche Inhalt der überlangen
Findings-Datei aus dem Bestätigungslauf lag diesem Fix nicht vor (der Lauf
selbst geschah zentral, nicht in dieser Session) — die Diagnose stützt sich
auf die Rechnung (3 Funde × 3 Zeilen ≈ 15, beobachtet 64–66) und auf die
Lücken im vorherigen Schema, nicht auf eine Zeile-für-Zeile-Analyse der
echten Ausgabe. Ob die Verschärfung reicht, zeigt erst der nächste
Bestätigungslauf.

Nicht in dieser Runde behoben, bewusst nur dokumentiert:

- **L1: Eval 4 (`research-fanout-stays-distilled`) prüft größtenteils
  Prompt-Befolgung, nicht die Skill.** Der Prompt buchstabiert Zielpfad und
  Format der Findings-Datei praktisch vollständig vor; ein Agent, der die
  Skill **nicht** benutzt (kein Fan-out, einfach selbst grep't und brav
  formatiert), erfüllt fast alle mechanischen `must`-Assertions ohne jede
  Skill-Logik. Einzig der `judge`-Claim zielt auf das eigentliche
  Unterscheidungsmerkmal. Nicht behoben, weil eine Assertion, die echten
  Subagenten-Dispatch von simuliertem Verhalten mechanisch unterscheidet,
  ohne den Harness selbst zu erweitern (z. B. um sichtbare Subagenten-Spuren
  im Transcript), nicht mit vertretbarem Aufwand nachrüstbar war — siehe
  auch „Keine inhaltliche Formprüfung" oben.
- **L4: Routing gegen die installierte Konkurrenz-Skill ist ungetestet.**
  Alle vier Eval-Prompts nennen `subagent-dev` beim Namen; ob ein Nutzer, der
  nur "ich habe einen Plan, was kann ich parallelisieren?" sagt, tatsächlich
  diese Skill statt der global installierten
  `superpowers:subagent-driven-development` bekommt, ist durch keinen Eval
  abgedeckt. Nicht behoben — ein Routing-Eval ohne expliziten Skill-Namen im
  Prompt ist schwerer vorherzusagen und wollte nicht blind (ohne Eval-Lauf)
  verfasst werden.
- **Restrisiko aus D2 (case-insensitiver Vergleich):** Zwei Pfade, die sich
  nur in der Groß-/Kleinschreibung unterscheiden, gelten jetzt immer als
  überlappend — auf einem case-sensitiven Dateisystem, auf dem `Config.py`
  und `config.py` tatsächlich zwei verschiedene Dateien sein könnten, führt
  das zu einer unnötigen Serialisierung, nie zu einem übersehenen Konflikt
  (bewusst konservativ, B2).

## subagent-dev — `lint-spec` (2026-09-11)

- **`lint-spec` prüft Form über Überschriften und Tokens.** Die sieben Abschnitte
  müssen `## `-Überschriften sein, die mit dem Template-Namen beginnen (`## 1 ·
  Problem` fällt durch); die Abgrenzung braucht eine Überschrift mit dem Wort, und
  als Nachbar zählt nur ein Ordner unter `skills/` oder ein Name mit Namensraum
  (`superpowers:x`) — eine Abgrenzung gegen eine nur im Nutzerprofil installierte
  Skill (`skill-creator`) zählt nicht, das ist derselbe Blindfleck wie bei
  `lint_skill.py` `neighbors`; umgekehrt zählt jedes `wort:wort` als Namensraum.
- **Der Struktur-Block ist der Zaun, der mit `skills/<name>/` beginnt** (ein Anhang
  hinter der Wurzel ist erlaubt). Ein Baum, dessen erste Zeile ein Kommentar ist, wird
  nicht gefunden (`skill-structure`). Jeder Eintrag wird über sein Pfad-Token gelesen,
  das erste Wort nach dem Baum-Präfix; Kommentare dahinter zählen nicht — weder als
  Skript noch als Hook noch als fremder Pfad. Ein Baum, der statt `├──`/`└──` andere
  Zeichen oder Tabs zur Einrückung nutzt, wird falsch verschachtelt. Skripte (`.py`,
  `.sh`) zählen nur unter `scripts/`; Skripte anderer Skills im Baum werden
  übersprungen, auch wenn die Spec sie neu einführt. Als „diese Skill" gelten
  Dateiname und Baumwurzel; weichen beide voneinander ab und ist ein dritter Name
  gemeint, zählt er als Nachbar.
- **Gate-Wörter gelten je Einheit mit Negation** — Absatz, Tabellenzeile oder
  Listenpunkt, wie `_units` in `lint_skill.py`. Ein „blockiert" zwei Absätze nach dem
  „nicht" ist ein Befund, ein „blockiert … verworfen" im selben Absatz keiner — in
  beide Richtungen unscharf. Substantive („Blocker", „Abnahme-Blocker") zählen wie
  Verben. Der Hook zählt nur als Pfad-Token `assets/hooks/…` im Struktur-Baum.
- **Ein offener Zaun** (``` ohne Gegenstück) wird als eigener Befund `fence`
  gemeldet; die übrigen Befunde derselben Spec sind dann unzuverlässig, weil alles
  hinter dem Marker als Code gilt.
- **Platzhalter:** Inline-Code und „…"-Zitate sind maskiert, also geht „TODO:
  nachtragen" in Anführungszeichen durch. Template-Reste werden nur in der Kopfzeile
  (`Zyklus NN`) und in Eval-IDs (`<fall>`) gemeldet; ein `<zusage>` in Prosa nicht.
- **Der Review-Vermerk ist ein String, kein Nachweis.** Specs ohne Nummer im
  Dateinamen gelten als neu (Exit 1 bei Befund).
## architecture-map

Nach der ersten Review-Runde (3 Defekte, 3 Lücken, 2 Anmerkungen behoben — siehe
`docs/superpowers/reports/architecture-map-report.md`) bleiben diese Grenzen bewusst
offen:

- **Eine ID-Kollision blockiert die ganze Extraktion, nicht nur den betroffenen
  Knoten.** `discover_modules()` (Python wie TS) bricht mit `ExtractError` ab, sobald
  zwei Dateien auf dieselbe Modul-ID abbilden (z. B. `a/b.py` und `a.b.py`, oder
  `src/widgets.ts` und `src/widgets/index.ts`) — bewusst so, weil ein still gewählter
  Gewinner einen ganzen Knoten samt Kanten unbemerkt verschwinden ließe (Review-Defekt
  D3). Der Preis: eine einzelne, harmlose Kollision irgendwo in einer sehr großen
  Codebase verhindert die Extraktion des gesamten `--root`, es gibt keinen Teil-Erfolg.
  Dasselbe gilt für `extract_classes()` bei mehrdeutig referenzierten Basisklassen-
  Namen über mehrere Hotspot-Dateien hinweg (Review-Anmerkung A1) — dort nur für die
  jeweils gemeinsam übergebene `--files`-Menge, nicht global.
- **`external` im Drift-Footer ist optional-defensiv, nicht erzwungen.**
  `diff_graph()` liest `entry.get("external", [])` — ein Footer-Eintrag, der (von Hand
  oder durch ein älteres Dokument vor der Review-Fix-Runde) kein `external`-Feld trägt,
  liefert für die externe Abhängigkeitsmenge stillschweigend „keine Änderung", auch
  wenn sich real etwas geändert hat. Der Hash selbst (`graph_hash()`) erkennt die
  Änderung weiterhin zuverlässig (er hasht `graph["external"]` direkt aus der frischen
  Extraktion, nicht aus dem Footer) — nur der **Diff-Text** für externe Pakete kann bei
  einem unvollständigen alten Footer leer bleiben, während `status: "drift"` korrekt
  gemeldet wird.
- **`layers_summary` ist eine Textempfehlung (G1), keine erzwungene Ausgabe (G2/G3).**
  `analyze_graph.py` liefert den kanonischen Satz, SKILL.md verlangt die wörtliche
  Übernahme — nichts im Mechanismus verhindert, dass ein Agent ihn umformuliert oder
  wegkürzt. Die beiden Evals `cyclic-imports-cycle-named` (erwartet „ungeprüft") und
  `layer-violation-is-named` (erwartet „geprüft" ohne „un"-Präfix) sind der einzige
  Schutz, und sie decken nur die zwei gebauten Fixtures ab, nicht jede denkbare
  Formulierungsabweichung.
- **Provenienz-Marker-Assertions erschweren Fälschung, verhindern sie nicht
  kryptografisch.** Die Evals prüfen auf den exakten `%% skill: architecture-map |
  schema: N | generated: ...`-Kommentar und den `<!-- architecture-map:graph-hashes
  -->`-Block (Review-Defekt D1) — ein Agent, der SKILL.md liest und diese Marker
  wortgetreu von Hand nachbaut (inklusive eines plausibel aussehenden 64-stelligen
  Hex-Strings als `graph_hash`), bestünde die Contract-Evals trotzdem. Der Drift-Check
  würde eine falsch berechnete `graph_hash` beim nächsten echten Lauf aufdecken
  (Hash-Mismatch), aber das ist ein späterer, separater Schritt — kein Teil dieser
  drei Contract-Evals.
- **`.js`-Import-Auflösung (Review-Lücke L3) deckt nur den Geschwister-Extension-Fall
  ab.** `_relative_candidates()` probiert bei einer geschriebenen Extension jetzt auch
  die anderen `SUFFIXES` am selben Pfadstamm — das löst `./foo.js` gegen eine
  existierende `foo.ts`. Tsconfig-Pfad-Aliase, Barrel-Re-Exports und eine echte
  `rootDir`/`outDir`-Trennung (kompilierter Pfad zeigt auf ein anderes Verzeichnis als
  die Quelle) bleiben unverändert außerhalb der Reichweite dieser Tier-1-Textsuche.
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

### Fix-Runde 4 (Review nach dem Merge — Schnittstelle, Parser, Tier 0)

- **Behoben: Erzeuger und Leser berechneten verschiedene Pfade.** `due_topics.py`
  hängte den Projekt-Override an die Basis `.skills/verified-research/`,
  exercise-forges `resolve_exercises_path` an das Unterverzeichnis `research/`.
  Existierte die Basis ohne `research/`, schrieb exercise-forge nach `~` und
  learning-coach suchte im Projekt — die Aufgaben galten dauerhaft als „nicht
  gefunden", ohne dass irgendetwas rot wurde. Dieselbe Klasse wie Fix-Runde 2
  (dort die Top-Level-Form, hier der Pfad), erneut nur durch Nebeneinanderlegen
  beider Seiten sichtbar. Vereinheitlicht auf die Basis-Regel, die dem
  Namensraum-Eigentümer `verified-research/scripts/registry.py` gehört; beide
  exercise-forge-Skripte nachgezogen. Ein parametrisierter Test prüft jetzt für
  alle drei Verzeichniszustände, dass Konsument und Erzeuger denselben Pfad
  liefern — die Verdrahtung, nicht nur die zwei Seiten einzeln.
- **Behoben: „gefunden" behauptete Verifikation, die nie geprüft wurde.** Der in
  `exercise-forge` unten festgehaltene Nachzieh-Bedarf (entferntes `status`-Feld)
  war offen: `exercises_status()` gab `ok` für jede nicht-leere `"exercises"`-Liste
  zurück, also auch für lauter frisch erzeugte Aufgaben mit `method: "not_run"`,
  die exercise-forges eigener Exporter überspringt. Die Skill hätte sie als
  bevorzugte, „verifizierte" Quelle angeboten — gegen ihren eigenen Contract.
  `has_verification_evidence()` prüft jetzt den gemeinsamen Vorspann derselben
  Ableitung (echte Blind-Gate-Methode, `checked_at`, `protocol` als Objekt); die
  typspezifische Protokollprüfung bleibt bewusst beim Erzeuger, eine Kopie würde
  auseinanderlaufen. Notwendig, nicht hinreichend — die Richtung stimmt: was hier
  durchfällt, ist dort garantiert nicht verifiziert. Neuer Zustand `unverified`
  mündet in dieselbe mandatierte Phrase; Fixture `lc-unverified-exercises` und der
  Eval `unverified-exercises-are-named-not-hidden` decken ihn ab.
- **Behoben: der Parser verlor „Typische Fehler" stillschweigend.** `learner.md`
  wird per Doktrin freihändig vom Agenten geschrieben — das Skript schreibt nie
  zurück, es gibt also keine Schreibvalidierung. Ein Listeneintrag ohne die zwei
  Leerzeichen Einzug und ein Inline-Wert (`- Typische Fehler: …`) fielen beide
  ersatzlos heraus, ohne Warnung, während jede andere Fehlform eine erzeugt.
  Betroffen war ausgerechnet die Zeile, die `learner-schema.md` selbst „die
  wertvollste" nennt. Beide Formen werden jetzt übernommen **und** gemeldet.
- **Behoben: `--today` mit Müll-Datum warf einen nackten Traceback**, im
  `due`-Pfad erst, nachdem `ensure_learner()` die Datei angelegt hatte — eine
  Bootstrap-Nebenwirkung auf einem abstürzenden Lauf. Datum wird jetzt vor allem
  anderen validiert, `DueTopicsError` + Exit 2 wie jede andere ungültige Eingabe.
- **Ergänzt: zwei mechanisch prüfbare Contracts hatten keinen Eval.** „Ein
  falscher Abruf senkt den Grad sofort um eine Stufe" wird jetzt in
  `wrong-answer-writes-verbatim-mistake` per `file_matches` mitgeprüft (eigene
  Assertion, kein zusammengesetzter Judge-Claim). „Kein Grad-Sprung ohne
  Rückerklärung" hat mit `solution-without-explain-back-keeps-grade` einen eigenen,
  rein mechanischen Eval bekommen: die Datei muss sich ändern (eiserne Regel) und
  der Grad darf dabei nicht steigen — ohne die erste Bedingung würde Nichtstun
  bestehen.
- **Unbelegt geblieben: der Tier-0-Pfad.** SKILL.md verwies auf ihn, spezifizierte
  aber nur die *Ausgabe* (kopierbarer Block). Woher der Lernstand ohne
  `due_topics.py` kommt, stand nirgends — und drei Contract-Regeln („kein Update"
  nur bei null fälligen Themen, „kein Quiz erfinden", die Pflichtphrase zu
  fehlenden Aufgaben) waren wörtlich an die Skriptausgabe gebunden und damit im
  Web undefiniert. `references/tier0-path.md` schreibt jetzt Eingabe, Fälligkeits-
  rechnung, Aufgaben-Fall und Ausgabe aus, nach dem Muster von `motion-landing`s
  Degradationsabschnitt. **Kein Eval prüft das**, und das lässt sich hier auch nur
  schwer nachholen: Der Harness gibt jedem Agenten eine Shell, „kein Dateizugriff"
  ist darin nicht abbildbar. Der Pfad ist damit dokumentiert, aber ungemessen —
  dieselbe Kategorie wie die ungeprüften Degradationspfade von `motion-landing`.
- **Behoben am 2026-10-14 (Spec 25): der Skriptaufruf war repo-relativ.** Die SKILL.md
  ruft `due_topics.py` jetzt über `${CLAUDE_SKILL_DIR}` auf; siehe Abschnitt skill-dir.
## exercise-forge

Fünf Fix-Runden (Details in `docs/superpowers/reports/exercise-forge-report.md`).
Runde 1: ein unabhängiger Review fand zwei Defekte, die inzwischen behoben sind
(`export.py` glaubte eine von Hand geschriebene `"status": "verified"`;
`verify_open` verifizierte Aufgaben mit leerer `criteria`-Liste, weil `all([])`
in Python `True` ist). Runde 2: zusammengesetzte Judge-Claims zerlegt. Runde 3:
die Zerlegung deckte einen dritten, echten Defekt auf — ein G1-Doktrin-Fix
(SKILL.md verbietet Hand-Edits) wurde versucht. Runde 4: ein zweiter echter
Lauf zeigte, dass die Doktrin allein nicht reichte; `export.py` wurde von
`status` entkoppelt (Ableiten statt Validieren), aber die Prüfassertion
(`must_not` gegen die rohe Aufgaben-JSON) fiel weiterhin — die Ableitung
schützte nur das *Rendering*, nicht die Quelle selbst, die auch
`learning-coach` (Zyklus 14) liest. Runde 5: das `status`-Feld wurde
vollständig aus dem Schema entfernt — was ableitbar ist, muss nicht
gespeichert werden, und ein redundantes, frei editierbares Feld war die
eigentliche Fehlerquelle. Was aus diesen Runden als Grenze bleibt, statt
behoben zu werden:

- **Das MC-Blind-Gate markiert jede Fehlwahl identisch als `suspicious`, ohne die
  Begründungsqualität zu bewerten.** Ein einzelner, stochastischer Blind-Löser-Lauf
  ohne Retry oder Mehrheitsvotum: ein funktionierender, absichtlich schwieriger
  Distraktor kann mit einer gewissen Grundwahrscheinlichkeit trotzdem `suspicious`
  auslösen, weil der Blind-Löser einfach falsch geraten hat — von einem echten
  Befund nicht mechanisch unterscheidbar, nur durch Lesen der zitierten Begründung.
  `SKILL.md`s Contract wurde in Fix-Runde 1 auf genau diese Grenze zurückgezogen
  (vorher versprach er implizit ein Urteil über „valide Begründung", das der Code
  nie gefällt hat).
- **Karten-Atomarität („eine Information pro Karte") ist mit den vorhandenen
  Assertion-Primitiven nicht mechanisch prüfbar** — weder im Skill-Code noch im
  Eval-Harness gibt es ein Primitiv, das Kartenzahl oder Inhaltsbündelung zählt
  (dieselbe Grenze wie „Negative Strukturprüfung fehlt" oben). Der Eval
  `twenty-cards-stay-atomic` deckt das deshalb nur als Judge-Claim ab.
- **Drei zunehmend strengere Fixes für dasselbe Problem, jeder gemessen und
  für unzureichend befunden, bevor der nächste kam.** (1, Fix-Runde 3) Eine
  G1-Doktrin gegen Hand-editiertes `verification` („Melden ersetzt nicht
  Markieren") — ein echter `run_evals.py`-Lauf zeigte: alle drei „Gate findet
  ein Problem"-Evals fielen weiterhin, `"status": "verified"` stand im
  Aufgaben-JSON trotz gefundenem und gemeldetem Konflikt. (2, Fix-Runde 4)
  Ein G2-Mechanismus, aber nur am Lesepfad: `export.derive_status_from_protocol()`
  berechnete den angezeigten Status aus `verification.protocol` statt aus
  `status` — ein erneuter echter Lauf zeigte: dieselben drei Evals fielen
  *immer noch*, weil ihre `must_not`-Assertion die **rohe Aufgaben-JSON**
  prüft, nicht `export.py`s Rendering. Die Ableitung machte das Rendering
  korrekt, ließ den Widerspruch aber im Artefakt selbst stehen. (3, Fix-Runde
  5) Das `status`-Feld vollständig aus dem Schema entfernt — `verification`
  trägt nur noch `method`/`detail`/`checked_at`/`protocol`. Ohne ein
  `status`-Feld kann kein Wert mehr geschrieben werden, der dem Protokoll
  widerspricht; die Fehlerklasse ist an der Quelle beseitigt, nicht nur an
  einem Konsumenten davon. Referenzimplementierung der Ableitungsregel:
  `export.derive_status_from_protocol()` bzw. identisch dupliziert
  `verify_blind.derive_status_from_protocol()`; die Regel selbst steht
  code-unabhängig in `skills/exercise-forge/references/task-schemas.md`.
  **Was auch damit nicht geschlossen ist:** `protocol` selbst bleibt eine
  JSON-Datei, die ein Editor-Werkzeug ändern kann. Wer ein vollständig
  konsistentes `protocol` von Hand fälscht (bei MC z. B. `chosen_index` auf
  die tatsächlich korrekte Option setzen), bekommt weiterhin `verified`
  abgeleitet — eine deutlich aufwändigere, gezieltere Fälschung als ein
  einzelnes Feld zu schreiben, und bei MC/offenen Fragen zusätzlich gegen die
  Aufgabendaten selbst geprüft (die Optionen/Kriterien müssten mitgefälscht
  werden, was `validate_exercise()` an anderer Stelle wieder einschränkt).
  Eine Signatur oder ein Audit-Log, das `protocol` kryptographisch an den
  tatsächlichen Lauf bindet, wäre der nächste Schritt und wurde nicht gebaut.
- **`learning-coach` (Zyklus 14) muss auf das entfernte `status`-Feld
  nachgezogen werden — sonst bricht die Schnittstelle still.** *(Erledigt in
  learning-coachs Fix-Runde 4, siehe oben: `has_verification_evidence()`.)* `learning-coach`
  liest dieselben Aufgaben-JSONs und meldet unter anderem „keine verifizierten
  Aufgaben gefunden". Jede Prüfung, die dort `exercise["verification"]["status"]`
  erwartet, muss durch dieselbe Ableitungsregel ersetzt werden, die
  `export.py`/`verify_blind.py` verwenden (dokumentiert in
  `skills/exercise-forge/references/task-schemas.md`, Abschnitt
  `verification`-Objekt). Diese Skill baut nichts an `learning-coach` — der
  Nachzieh-Bedarf ist im Bericht dieser Skill vermerkt, zur Weitergabe an die
  Session, die `learning-coach` baut.
- **Drei der ursprünglich sechs Judge-Claims waren zusammengesetzt und
  dadurch unzuverlässig — siehe der neue Punkt im Abschnitt „Judge" oben.**
  `mc-distractor-trap-is-caught`, `narrow-criteria-on-open-question-are-flagged`
  und `overspecified-coding-tests-are-flagged` verlangten je drei Bedingungen
  in einem Satz. Alle drei wurden in je eine mechanische Prüfung „Gate lief"
  (`method`-Feld im Aufgaben-JSON), eine mechanische Prüfung „nicht verified"
  (`must_not` auf `"status": "verified"`) und einen einzigen, einzeln
  entscheidbaren Judge-Claim „Konflikt sichtbar benannt" zerlegt.
- **Drei der sechs Evals sind gegen einen echten Agenten bestätigt**
  (`single-flashcard-stays-single`, `twenty-cards-stay-atomic`,
  `one-step-harder-changes-the-vector-not-just-wording`). Die drei „Gate
  findet ein Problem"-Evals sind seit dem Fix-Runde-5-Schema-Fix (`status`
  komplett entfernt) nicht erneut gegen einen echten Agenten gefahren worden
  — nur schema-validiert. Zwei vorherige Fixes (Doktrin, dann Ableiten nur
  beim Rendern) hielten der Messung jeweils nicht stand; diesmal ist der
  Ausschluss struktureller (das Feld existiert nicht mehr, es gibt nichts
  mehr zu widersprechen), aber auch das ist erst bewiesen, wenn ein echter
  Lauf es bestätigt, nicht vorher.

## human-prose

- **Die Schwellen sind geschätzt, kein Korpus liegt vor.** Satzlänge, 15 -ung je
  1000, 20 Prozent Passiv, drei Hedges je 300 Wörter stammen aus dem Entwurf v0.1
  (Abschnitt 10, erster Punkt); `measure.py` schreibt `"estimated": true` in jede
  Zeile. Am eigenen Entwurf gemessen (1.530 Wörter ohne Zitate): 25,5 -ung je 1000 und
  35 Doppelpunkte, beides rot — ein Regeldokument ist kein Fließtext, aber die Grenzen
  sind eng. Erst fünf bis zehn eigene Texte des Nutzers machen daraus Messwerte.
- **Vier Heuristiken zählen an den Beispieltexten des Entwurfs falsch, und die Tests
  halten das fest** (`tests/test_human_prose_measure.py`): R2.1 meldet Beispiel 3
  Nachher rot (kein Satz mit zwanzig Wörtern in einer Vier-Satz-Mail — die Regel ist
  für Register `kurz` zu streng); R5.1 meldet Beispiel 2 Nachher rot (englischer
  Fließtext ohne Ziffer, Pfad oder Großwort) und Beispiel 3 Nachher `unchecked` (zwei
  Absätze mit je zwei Sätzen, kein Behauptungsabsatz ab drei Sätzen); Passiv erkennt
  nur `werden`-Form plus Partizip, Fragmente nur Sätze bis fünf Wörter ohne finites
  Verb aus einer kleinen Liste. Deutsche Substantive zählen bei R5.1 nicht als
  konkret, sonst wäre jeder Absatz konkret.
- **Die Phrasenliste trifft wörtlich fast nichts.** Beispiel 1 Vorher enthält aus R4.1
  wörtlich eine Phrase; erst zwei Lückenmuster („spielt (\w+ ){0,2}eine entscheidende
  rolle", „nicht nur .{1,80}, sondern auch") finden drei. Was eine andere Beugung oder
  ein anderes Subjekt hat, geht durch. `robust` und `leverage` zählen immer; der
  Fachkontext, den der Entwurf ausnimmt, ist ein Urteil.
- **Fünf Regeln misst kein Skript** (R3.1, R5.3, R5.4, R2.3 zweiter Punkt, R5.2). Sie
  stehen unter `judgement` im Artefakt; ob eine Zahl erfunden ist, sieht nur, wer
  Original und Auftrag daneben hält.
- **Die Rückfrage erreicht im `-p`-Modus niemanden.** Die Skill wartet nie, schreibt um,
  lässt die Stelle allgemein und fragt am Ende; ohne zweite Runde bleibt die Lücke.
  Das ist gewollt (Spec 19, Review-Befund 2), aber ein Text aus einem einzigen Lauf
  trägt dann offene Stellen.
- **Das Stilprofil ist ungetestet.** `my-writing-style` ist hier nicht installiert;
  „das Profil gewinnt, das Skript bleibt" ist Doktrin ohne Lauf.
- **Die Evals sind nicht im Harness gefahren** (root, `bypassPermissions`, siehe
  „Betrieb"); Nachweis ist ein Lauf mit Subagenten außerhalb des Harness, siehe
  Report. `--without-skill` (Spec 18) steht aus; bei Eval 1 entscheidet dann die
  Register-Zeile, ob er etwas misst.
- **`explain`s Rückverweis nennt die Tokens nicht wörtlich.** Eine Zeile mit `Next:`
  in dessen Abgrenzung hätte `evals_due: true` ausgelöst, ohne dass sich sein Contract
  ändert; der Satz sagt „die drei wörtlichen Tokens" und meint dieselben.

## Marketplace (2026-09-23)

- **Skriptpfade kennen das Plugin — seit Spec 25.** Bis zum 2026-10-14 nannten die
  SKILL.md-Dateien `skills/<name>/scripts/…` und `.claude/skills/<name>/scripts/…`; heute
  steht überall `${CLAUDE_SKILL_DIR}/scripts/…`, das Claude Code im Skill-Text ersetzt
  (Abschnitt skill-dir).
- **Das ganze Repo wird kopiert.** `source: "./"` macht das Repo-Root zum Plugin-Root;
  Claude Code klont es in seinen Plugin-Cache, samt `evals/`, `tests/`, `docs/`,
  `evalkit/`. Die Doku empfiehlt, Tests und Fixtures draußen zu lassen; hier sind sie
  klein, und ein separater `plugins/`-Ordner müsste synchron gehalten werden.
- **`cad-parts` ist ausgeschlossen, nicht versteckt.** Die explizite `skills`-Liste ist
  bei Marketplace-Root-Quelle die vollständige Menge (Doku, „Advanced plugin
  entries"); `tests/test_marketplace.py` hält Liste und `skills/` synchron und nennt
  den Grund je Ausschluss. Gemessen: `claude plugin validate .` grün, lokale
  Installation lädt 21 Skills.
- **17 Skills liegen auch im Nutzerprofil unter gleichem Namen.** Der Namensraum
  `cc-skills:` verhindert die Kollision im Aufruf, nicht die doppelte Sichtbarkeit; die
  Routing-Evals messen nur die Projekt-Installation unter `.claude/skills/`, nie das
  Plugin.
- **Der Web-Loader von claude.ai liest das Manifest anders als die CLI.** Zwei
  Abweichungen, beide am 2026-09-23 auf der Plugin-Seite in den claude.ai-Einstellungen
  gesehen: Er ignoriert die `skills`-Liste und lädt jeden Ordner unter `skills/`, also
  auch `cad-parts` (ein gemeldetes Issue im Claude-Code-Repo beschreibt genau das, die
  CLI filtert korrekt). Und er lässt eine Skill still weg, deren Description `<…>`
  enthält; `learning-coach` und `verified-research` trugen als einzige `<Thema>` und
  fehlten als einzige, die Platzhalter im Body stören nicht. Die Descriptions sind
  umformuliert, `tests/test_marketplace.py` meldet den nächsten Fall. Gemessen danach: vier
  Routing-Läufe mit je drei Konkurrenz-Skills im Workspace, alle vier wählten die richtige
  Skill, zwei davon mit der geänderten Phrase als Begründung. Der Ausschluss von
  `cad-parts` gilt bis zum Fix des Issues nur für die CLI.
- **Kein Release-Prozess.** `version` im Manifest ist von Hand gesetzt; Spec 00 führt
  Versionierung unter Out of scope, und nichts prüft, ob die Zahl zum Stand passt.

## Marketplace — drei Plugins (Spec 20, 2026-10-08)

Ersetzt im Abschnitt davor den Zuschnitt (ein Plugin `cc-skills`), den Namensraum
`cc-skills:` und den Punkt zu `version`. Was ungemessen bleibt und wo es beißt:

- **Nur der CLI-Weg ist abgedeckt.** `cc-dev`, `cc-ui` und `cc-knowledge` haben je
  `source: "./"` und eine `skills`-Liste; die CLI lädt nur die gelisteten Ordner
  (gemessen: 10, 3, 6 Skills, `claude plugin validate .` grün). Der Web-Loader von
  claude.ai ignoriert die Liste (Abschnitt davor) und lüde je Plugin alle Ordner. Der
  Nutzer bindet Plugins nur per CLI an, `plugins/synced/` enthält keine Plugins, und
  Cloud-Sessions laden Plugins gar nicht (gemeldeter Bug); dort helfen nur die
  Projekt-Kopien unter `.claude/skills/`.
- **Skriptpfade in fremden Repos — behoben am 2026-10-14 (Spec 25).** Vorher liefen dort
  die Skripte von 9 der 14 Skills in `cc-dev`, 2 der 4 in `cc-ui` und 4 der 6 in
  `cc-knowledge` nicht. Was bleibt, steht im Abschnitt skill-dir.
- **Projekt-Kopien driften nur bis zum Sync-Check.** `scripts/sync_skills.py --check`
  steht in skill-forge Schritt 4 (G1) und in `tests/test_marketplace.py` (G2). Wer ein
  Original außerhalb von skill-forge ändert und nicht `pytest` fährt, committet eine
  veraltete Kopie; einen Hook gibt es bewusst nicht.
- **`cc-dev` ist in diesem Repo aus.** Die committete `.claude/settings.json` setzt
  `cc-dev@cc-skills` auf `false`, damit die acht Projekt-Kopien nicht doppelt
  erscheinen. rest-api-architect und sql-schema-architect fehlen damit hier; eine
  synchronisierte ID `cc-dev@synced` ist nicht abgedeckt.
- **Kein `version`-Feld.** Updates kommen mit jedem Commit nach
  `/plugin marketplace update cc-skills`; eine Release-Nummer gibt es nicht.
- **Das Listing-Budget ist nur vorher gemessen.** `/context` zeigte am 2026-10-08 mit dem
  alten Ein-Plugin neun Skills mit weniger als 20 Tokens, also ohne Description
  (`docs/superpowers/validation/2026-10-08-plugin-split-sync.md`). Ob die Aufteilung
  das behebt, misst der Nutzer nach dem Merge.
- **Behoben (2026-10-12): `verify` von subagent-dev meldete Nicht-ASCII-Pfade als
  Allowlist-Verstoß.** `check_allowlist` las `git diff --name-only` und
  `git status --porcelain` ohne `-z`; git setzte `specs/Spec 00 – skill-foundation.md`
  und Pfade mit Leerzeichen in Anführungszeichen und escapte sie, sodass sie auf keinen
  Eintrag passten. Beim Bau von Spec 20 und 21 nur mit `core.quotepath=false` und
  vorherigem Commit zu umgehen. Jetzt lesen beide Aufrufe mit `-z` und als UTF-8,
  `git status` dazu mit `--untracked-files=all`, damit ein neuer Ordner seine Dateien
  einzeln zeigt (`test_check_allowlist_reads_non_ascii_and_space_paths_without_quoting`).

## setup-user

Gebaut nach Spec 21, Abschnitt A (2026-10-09) und B (2026-10-14). Tier 1:
`inspect_config.py`, `apply_config.py`, `verify_install.py`, `route_check.py`, dazu zwei
Laufzeitskripte im Config-Verzeichnis.
Was ungemessen bleibt und wo es beißt:

- **Windows ist ungemessen.** Ob `|| true` im Hook-Kommando dort greift, ob `python` oder
  `py -3` der richtige Interpreter ist, ob Claude Code `CLAUDE_CONFIG_DIR` an das
  Statusline-Kommando vererbt und ob `os.replace` bei offenem Leser scheitert, misst erst
  der erste echte Lauf auf dem Windows-PC. Die Skripte lesen stdin als UTF-8-Bytes und
  schreiben stdout als UTF-8, unabhängig von der Codepage.
- **Bei `claude -p` läuft die Statusline nicht** (mit CLI 2.1.292 gemessen). Kopflose
  Läufe bekommen deshalb nie einen Kontext-Hinweis; Limit-Hinweise nur, solange ein
  interaktiver Lauf den Cache frisch hält.
- **Ob Hinweise das Verhalten ändern, misst nichts.** Tests messen, dass der Hook meldet
  und schweigt; kein Eval kann einen Kontextstand von 60 % herbeiführen.
- **Hook-Änderungen wirken ab der nächsten Session.** Ob eine mitten in der Session
  geänderte `settings.json` sofort greift, ist nicht gemessen; die Übergabe sagt es so.
- **Die Prüfung führt nur Asset-Befehle aus.** Eine fremde Statusline bleibt
  „ungeprüft (fremd, nicht ausgeführt)", auch wenn sie richtig wäre. `verify_install.py`
  braucht `bash`; ohne heißt das Ergebnis „ungeprüft — keine bash".
- **Gemessen ist nur das Layout eines lokalen Marketplace.** `route_check.py` folgt dem,
  was `claude plugin install` am 2026-10-14 (CLI 2.1.296) in einem Wegwerf-Verzeichnis
  angelegt hat. Ein Marketplace aus GitHub, ein Plugin unter `plugins/synced/` (beim
  Nutzer leer, hier ein leerer UUID-Ordner) und das Feld `hooks` in `plugin.json` sind
  nach Doku gebaut, nicht gemessen.
- **Jedes per CLI installierte Plugin gilt als gesetzt.** Die Installation schreibt
  `true` nach `enabledPlugins`; das Profil dreht gesetzte Werte nie um. superpowers geht
  deshalb nur aus, wenn der Nutzer es mit `plugins_off` ausdrücklich freigibt — der Plan
  fragt, er schaltet nicht.
- **`defaultEnabled` kommt nur aus dem Marketplace-Eintrag** im Installationsordner. Ein
  Plugin ohne Eintrag und ohne Wert in `enabledPlugins` gilt als an.
- **Teil (b) der Abschaltbedingung prüft den installierten Cache,** nicht das Repo. Ein
  veralteter Cache meldet Verweise, die die Quelle nicht mehr hat; dann hilft
  `claude plugin update`.
- **Projekt-Settings bewertet `route_check.py` nicht.** Ein Projekt, das superpowers
  wieder einschaltet, sieht `check` nicht.
- **Die Statusline-Vorlage stammt vom Nutzer.** Asset und Anzeige-Test bauen auf seiner
  Fassung vom 2026-10-07 auf (`tests/fixtures/setup-user/`); ohne sie gibt es kein Asset
  und keinen Anzeige-Vergleich.

## setup-repo

Gebaut nach Spec 22, Abschnitt B und C (2026-10-12). Tier 1: `detect_repo.py`,
`harvest_rules.py`, `plan_repo.py`, `apply_repo.py` (mit `--check`), dazu im Zielrepo der
opt-in-Hook `verify_stop.py` und der vorausgewählte Bereichs-Hook `goal_scope.py`. Was
ungemessen bleibt und wo es beißt:

- **Der Starter ist unter Windows ungemessen.** `command -v python3 … || exec python …`
  läuft in den Tests unter bash mit `python3` und mit nur `python`. Ob der
  Store-Platzhalter `python3` unter Windows `command -v` besteht und dann scheitert, misst
  erst der erste Lauf auf dem Windows-PC; scheitert er, ist die Exec-Form mit `"args": []`
  der nächste Versuch. Der Verifikationsbefehl läuft dort unter `cmd.exe`.
- **`claude -p` nutzt die Freigaben des Repos nicht** (`permissions.allow` ist dort „Not
  used"), und mit `--bare` lädt es weder CLAUDE.md noch Rules noch Hooks. Eine Pipeline
  auf der Devbox braucht `--allowedTools` oder User-Settings; setup-repo wirkt dort sonst
  nur über die CLAUDE.md.
- **Plugin-IDs sind gegen keine echte Installation gemessen.** `detect_repo.py` liest
  `installed_plugins.json` in beiden bekannten Formen (Objekt oder Liste je ID) und
  `plugins/synced/`; beim Nutzer liegen unter `plugins/synced/` laut Spec 20 keine
  Plugins. Wie `installPath` eines Marketplace mit `source: "./"` aussieht, ist geraten:
  zuerst das Manifest dort, sonst `skills/*/SKILL.md`.
- **Die Klassifikation misst nur Eval 2** — eine Fixture, ein Kandidat (`line-length`).
  Ob Claude `ableitbar` und `regel` sinnvoll trennt, misst nichts.
- **Die Ernte ist grob.** `CONTRIBUTING*` liefert jeden Aufzählungspunkt, auch
  Installationsschritte, höchstens 20; das Commit-Format zählt erst ab 5 Commits und 60 %
  Treffern. Monorepos mit Runnern in Unterordnern erkennt `detect_repo.py` nicht; es
  liest nur die Wurzel.
- **check sieht nur, was der letzte Plan berührt.** Eine Regel, die jemand nach apply
  von Hand ergänzt, ist keine Abweichung, solange das Budget hält. Der Plan liegt unter
  `.skills/cache/` und ist nicht committet; in einem frischen Clone heißt es „ungeprüft —
  kein Plan".
- **Eval-Läufe nur außerhalb des Harness.** `run_evals.py` bricht unter root ab. In
  Abschnitt B liefen die fünf Evals mit je einem Agenten, in Abschnitt C als echte
  kopflose Sessions (`claude -p` mit `--allowedTools`, siehe Betrieb), jeweils mit und
  ohne Skill, bewertet mit `evalkit.runner.grade()` (Report).
- **Der Bereichs-Hook sieht Dateien, nicht Absichten.** Eine neue Aufgabe, die nur Dateien
  im Bereich des Ziels berührt, meldet er nicht; eine verlangte Änderung außerhalb meldet
  er doch. Die Einordnung in die vier Klassen leistet die Zielregel, nicht der Hook.
- **Mit `claude -p` sieht Claude die Meldung nie.** Sie kommt per `systemMessage` beim
  Turn-Ende und als `additionalContext` erst beim nächsten Prompt, den es kopflos nicht
  gibt. Eine Pipeline auf der Devbox bekommt die Bereichsprüfung damit nur im Log.
- **Die Basis gilt je Turn und Session.** Ein Rebase oder Amend, der den Basis-HEAD
  entfernt, lässt `git diff` scheitern; der Hook meldet das einmal je Session und
  schweigt dann. Zwei gleichzeitige Sessions haben je eigene Basis und eigene Meldungen;
  ihre Ledger-Änderungen können beim Mergen kollidieren, und die Regel lässt Claude dann
  fragen statt lösen.
- **Die Ausnahmen sind fest.** `docs/goals.md`, `handoff.md`, `docs/debugging/`,
  `docs/decisions.md`, `docs/specs/wip/`, `docs/plans/` (seit Spec 23), `.claude/`,
  `.skills/`, `CLAUDE.md` und `.gitignore` zählen nie; weitere Hausartefakte eines Repos lassen sich nicht ergänzen.
- **Abschnitt D fehlt.** Kein Ziel-Reviewer; er wartet auf die Delphi-Prüfpunkte des
  Nutzers.

## impl-plan

Gebaut nach Spec 16 (2026-09-02). Tier 1 ohne eigenes Skript: Der einzige Code,
den die Skill braucht, ist `plan_to_tasks.py lint` in `subagent-dev`, und der wird
per Kommando aufgerufen, nie importiert. Was daraus folgt, in vier Punkten:

- **Der Lint ist im Eval-Workspace nicht verfügbar.** `evalkit/workspace.py::prepare()`
  kopiert nur das Skill-Verzeichnis nach `.claude/skills/impl-plan/`; das Skript von
  `subagent-dev` liegt dort nicht. Ein Agent, der die SKILL.md befolgt, landet im
  Eval-Lauf zwangsläufig in der Degradationszeile („Lint nicht verfügbar, Plan
  ungeprüft"). Deshalb hängt **kein Eval an `lint.json`**; alle fünf prüfen die
  Plandatei direkt — Kopfzeile, kanonische Titel, `token:`-Vokabular, Reihenfolge.
  Die Lint-Disziplin selbst wird vom Repo-Test und von `subagent-dev`s 66 Tests
  gemessen, nicht von Agentenläufen. Was ein Eval-Lauf also messen könnte, ist, ob
  die Skill das Template befolgt; ob sie den Lint *benutzt*, misst er strukturell nicht.
- **Das Legacy-Register ist ein Schuldenregister, kein Freibrief.** `tests/test_plans_lint.py`
  friert 16 Pläne vor Spec 15 nach Dateinamen ein; sie werden nicht gelintet. Stand
  heute parsen 8 davon nicht (`PlanParseError`, Exit 2) und die übrigen 8 tragen
  zwischen 15 und 79 Befunde — die Zahlen sind seit dem Befund an Spec 15 um je eins
  gestiegen, weil die Kopfzeilen-Prüfung dazukam. Genau deshalb friert der Test nach
  Namen ein und nicht nach Befund-Zahl: Jede Schärfung des Lints trifft nur neue
  Pläne. Die Menge darf nur schrumpfen; ein Plan verlässt sie, wenn ihn jemand
  lint-sauber macht. Niemand hat das vor, und das ist in Ordnung: Die 16 haben keinen
  Konsumenten mehr.
- **Der Repo-Test ist G2 ohne CI.** Diese Sammlung hat keinen CI-Lauf; `pytest` läuft,
  wenn jemand ihn startet. Ein Plan, der die Regel bricht, wird gemeldet, sobald
  jemand die Suite fährt — nicht beim Commit. Die SKILL.md sagt deshalb „verlangt"
  (G1) und verweist auf den Test als Zähne; sie sagt nirgends „blockiert".
- **Die fünf Evals sind ungefahren** — derselbe Grund wie bei `explain` (Abschnitt
  „Betrieb": `bypassPermissions` unter uid 0). Schema-valide, gegen einen
  templatekonformen Beispielplan regex-geprüft (`tests/test_impl_plan_evals_schema.py`),
  aber ohne einen einzigen Agentenlauf. Der Routing-Eval
  (`routing-house-header-not-superpowers`) ist zudem stochastisch: Ob „schreib mir den
  Implementierungsplan" bei `impl-plan` oder bei `superpowers:writing-plans` landet,
  entscheidet der Harness pro Lauf, und ein grüner Lauf beweist nichts.

**Nach der Fix-Runde (2026-09-03):** Der Lint löst die Spec aus der `Spec:`-Zeile
selbst auf, der Repo-Test prüft damit auch die Coverage jedes nicht eingefrorenen Plans;
`lint.json` trägt `coverage.status`, ein übersprungener Abgleich meldet sich als
`unchecked` mit Grund. Was bleibt: Die Coverage findet eine ID, die irgendwo in einem
Task-Block steht — nicht, ob der Task sie *baut*. Das prüft der Reviewer, kein Regex.
Und die Eval-Tabelle wird nur unter einer Überschrift ab Ebene 2 mit dem Wort
„Eval(s)" gefunden; eine Spec, die ihre Tabelle anders betitelt, gilt als tabellenlos
und bleibt `unchecked` — sichtbar in `lint.json`, aber ohne Befund. Ein Task-Block
endet an der nächsten Überschrift bis Ebene 3; eine ID, die nur in einer
Zwischenüberschrift der Ebene 4 innerhalb eines Tasks steht, zählt deshalb noch.

Dazu eine Lehre aus dem Bau selbst: Das Template musste dreimal umgeschrieben werden,
bis es lint-sauber war — `fn:…(…)` und `evals_…` sind für den Parser keine Bezeichner,
und ein Sammel-Task `Pflicht` im Fließtext wurde als echter Task geparst, bis er in
einen Codeblock wanderte. Ein Template, das der eigene Lint ablehnt, wäre der
peinlichste Fehler dieser Skill gewesen; der Repo-Test lintet es deshalb mit.

## skill-forge

Gebaut nach Spec 17 (2026-09-10). Tier 1: `scripts/lint_skill.py`, seit Spec 20 vierzehn Regeln,
Diff-Modus. Was ungemessen bleibt und wo die Grenzen beißen:

- **Das Register ist ein Schuldenregister.** `tests/test_skills_lint.py` friert je
  Skill die Regel-IDs ein, die beim ersten Lauf rot waren: 20 Skills, 79 Paare.
  Gemessen: `report-section` 19 (Report-Sektion unter anderem Namen oder kein
  known-limits-Abschnitt), `description` 18 (Prozessverben; `cad-parts` und
  `ui-architect` ohne Abgrenzung), `routing` 14 (beide Matrizen gefordert, meist
  fehlt eine), `anti-ceremony-eval` 11 (Eval vorhanden, ID ohne Präfix), `neighbors`
  11 (Nennung ohne Rückverweis), `evals-exist` 3, `asset-headers` 2, `gate-language` 1
  (`verified-research`: „erzwingt das mechanisch" ohne Hook). Die Menge darf nur
  schrumpfen. Niemand räumt sie in dieser Spec auf.
- **Mengen-Semantik verdeckt den zweiten Befund.** Das Register kennt Regel-IDs, keine
  Fundstellen. Bekommt eine registrierte Skill an derselben Regel einen zweiten,
  neuen Befund — ein zweites Prozessverb, eine zweite Kopfzeile ohne Header —, bleibt
  er unsichtbar, bis jemand die Skill aus dem Register nimmt. Der Diff-Modus des Lints
  hat dieselbe Auflösung: `new_findings` vergleicht Regel-IDs, nicht Zeilen.
- **`judge-claims` ist ein Hinweis.** 24 von 47 Judge-Claims im Repo tragen „ und ",
  „ statt " oder „ sowie "; die meisten sind legitim. Die Regel meldet `hint`, nie
  `finding`, und steht nicht im Register — sie prüft nichts, sie erinnert.
- **Die Evals sind einmal gefahren, außerhalb des Harness** (Report, „Erster
  Eval-Lauf"): fünf Workspaces über `prepare()`, Opus-Subagenten mit dem Eval-Prompt,
  Bewertung mit `evalkit.runner.grade()`. Zehn von zehn bestanden, je zwei Läufe (vor
  und nach der Folgerunde) — eine Stichprobe. Der Aufbau nennt den Ort der installierten Skills im Prompt, was der
  Harness implizit tut; ein Subagent sieht zusätzlich die Skills des Nutzerprofils.
  Ob ein Agent den Lint im Diff-Modus *aufruft* statt „schnell alles aufzuräumen", ist
  damit einmal positiv beantwortet, nicht bewiesen.
- **Der Lint parst kein YAML.** `split_frontmatter` liest zeilenweise per Regex und
  prüft seit der Folgerunde die vier Fälle, in denen ein unquotierter Skalar nicht lädt
  („: ", „:" am Ende, „ #", Sonderzeichen am Anfang). Gefunden hat das der Agent in
  Eval 5 an seiner eigenen Skill; nachgemessen mit PyYAML luden `impl-plan` und
  `debug-ledger` nicht — jetzt quotiert. Was der Regex weiterhin nicht sieht:
  mehrzeilige Flow-Skalare, Tabs, Unicode-Sonderfälle. Ob der Skill-Loader von Claude
  Code strikt parst, ist nicht gemessen; der Lint nimmt es an.
- **Der Trigger ist ungemessen.** Ob „bau mir eine Skill" bei `skill-forge` oder bei
  `skill-creator` landet, entscheidet der Harness pro Lauf; Eval 5 ist stochastisch.
  Die Description-Doktrin („keine Prozessbeschreibung") ist eine Entscheidung mit je
  einem Beleg pro Seite, keine Messung; ein Trigger-Eval-Set steht in
  `references/evals.md` für den Tag, an dem der Harness läuft.
- **Der Skriptpfad war eine dokumentierte Zweiform** — bis Spec 25. Heute ruft die SKILL.md
  `lint_skill.py` über `${CLAUDE_SKILL_DIR}` auf, und die Regel `script-paths` meldet jeden
  repo-relativen Aufruf; Punkt 19 der Prüfliste ist mechanisch.
- **Heuristiken mit bekannter Unschärfe.** `description` erkennt zwölf Prozessverben
  und drei Trigger-Formen — „Use when a plan exists" ist eine Prozessbeschreibung ohne
  Verb der Liste und geht durch. `gate-language` entkräftet per Negation im Absatz —
  „nicht nur blockiert, sondern …" ginge ebenfalls durch. `neighbors` erkennt genannte
  Skills nur als `**name**` (die Hausform der Abgrenzung); ein Nachbar in Prosa oder in
  Backticks zählt nicht. Ein
  genannter Name ohne Ordner unter `skills/` ist `unchecked` — im Repo heißt das
  „fremde Skill" (`skill-creator`), im Eval-Workspace „nicht installiert"; der Lint
  kann beides nicht unterscheiden und behauptet deshalb nichts. Beides fängt der
  Reviewer, nicht der Lint.
- **Im Eval-Workspace ist die Hälfte `unchecked`.** `asset-headers`, `routing`,
  `report-section` brauchen `docs/` und `README.md`, `neighbors` fremde Skills,
  `plugin-membership` ein Manifest. Die sechs Evals binden nur an Regeln, die in ihrer
  Fixture geprüft sind; ein Eval, der `routing` prüfen wollte, müsste die Matrix
  mitbringen.
- **`plugin-membership` liest nur die Listen.** Die Regel zählt, in wie vielen
  `skills`-Listen die Skill steht; ob die Projekt-Kopie dem Original gleicht, prüft
  `sync_skills.py --check`, nicht der Lint. Eval 5 bindet an das `pass` aus dem letzten
  Lint-Lauf nach Schritt 7; fährt ein Agent den Lint nur in Schritt 4, steht dort
  `finding`, und der Eval fällt — das ist gewollt, ungefahren ist es aber auch.
- **Die Baseline ohne Skill ist gebaut, aber hier nie gefahren** (Spec 18, 2026-09-15):
  `run_evals.py --without-skill` fährt dieselben Evals ohne Installation und prüft am
  `skills`-Feld des `system.init`-Ereignisses, ob der Agent die Skill sah — in beide
  Richtungen (ohne Skill sichtbar → „Baseline unmöglich", mit Skill unsichtbar → „Skill
  nicht sichtbar", je Exit 2). Nachweis sind Unit-Tests mit Fake-CLI; der Harness läuft
  in diesem Container nicht (siehe „Betrieb"). Drei Grenzen: Das Feld ist nur mit CLI
  2.1.272 gemessen — fehlt es, sagt der Report „Sichtbarkeit ungeprüft" und das Verdikt
  bleibt wie ohne die Prüfung. Ob die 17 gleichnamigen Profil-Skills auf dem Rechner des
  Nutzers unsichtbar bleiben wie im Container, ist ungemessen; der erste echte Lauf
  meldet es sonst als „Baseline unmöglich". Und ein roter Lauf ohne Skill beweist
  nichts (Stichprobe) — nur ein grüner ist ein Befund.
- **Der Spec-Review in Schritt 1 ist G2 nur über einen Token.**
  `plan_to_tasks.py lint-spec` (subagent-dev) meldet ab Spec 18 das Fehlen des
  Kopfzeilen-Vermerks „Überarbeitet nach unabhängigem Review"; ob ein Review hinter
  dem Vermerk liegt, prüft nichts — er ist fälschbar, aber im Diff sichtbar, und der
  Commit-Body mit der Fundliste ist die Konvention dazu. Specs ≤ 17 sind vom Cutoff
  ausgenommen und tragen ihre Restbefunde (`tests/test_subagent_dev_spec_lint.py`
  nennt sie). `spec-brief.md` und `spec-template.md` sind Eingaben, die jemand dem
  Brainstorming mitgeben muss (G1); ob sie benutzt wurden, zeigt nur die Form der
  Spec, die der Lint prüft.
- **`impl-plan`s Description nennt `brainstorming` ohne Zusatz.** Sechs der sieben
  Nennungen sagen „die eigene Profil-Skill, nicht superpowers"; die Description von
  `impl-plan` blieb, weil eine Frontmatter-Änderung dort Evals fällig macht, ohne den
  Trigger zu ändern. Die Description ist aber die Stelle, die der Harness beim Routing
  liest — wer die Routing-Kollision der zwei `brainstorming`-Skills misst, sollte sie
  dort ebenfalls benennen und die impl-plan-Evals mitfahren.

## work-plan

Gebaut nach Spec 23 (2026-10-13). Tier 1 ohne eigenes Skript; der Lint gehört
subagent-dev und kennt seitdem die Kopfzeile `skill: work-plan`. Was ungemessen bleibt und
wo es beißt:

- **In einem fremden Repo reicht der Weg jetzt bis zum Dispatch** (Spec 25): subagent-dev
  ruft `generate` und `verify` über `${CLAUDE_SKILL_DIR}` auf, work-plan den Lint über
  `${CLAUDE_SKILL_DIR}/../subagent-dev/`.
- **`${CLAUDE_SKILL_DIR}` ist nur für die lokale Installation gemessen.** Nach
  `claude plugin marketplace add` mit lokalem Pfad liegt die ganze Repo-Kopie im
  Plugin-Cache, das Nachbarverzeichnis also daneben (CLI 2.1.296). Ob das bei einer
  Installation aus dem GitHub-Marketplace genauso ist, misst nichts; fehlt das Skript,
  sagt die Skill „ungeprüft — Lint nicht verfügbar".
- **Im Eval-Workspace gibt es keinen Lint.** Dort liegt nur work-plan, nicht subagent-dev;
  Eval 3 (`verification-task-uses-repo-command`) macht genau das zur Prüfung des
  Vermerks „ungeprüft". Ob ein Plan aus einem echten Lauf lint-sauber ist, prüft der
  Report von Hand nach.
- **Die Schwelle ist eine Regel, kein Messwert.** Mehr als zwei Dateien, neue öffentliche
  Schnittstelle oder Reihenfolge — die Grenze misst nur der Anti-Zeremonie-Eval
  `anti-ceremony-one-file-change-gets-no-plan` an einem Tippfehler. Ob drei kleine
  Dateien ohne Abhängigkeit einen Plan verdienen, entscheidet Claude.
- **Coverage nur gegen feature-spec-Kriterien.** Zeigt `**Spec:**` auf eine Datei ohne
  Kopfzeile `skill: feature-spec`, bleibt die Coverage `unchecked`; ein Auftrag hat
  keine. Die `- Annahme:`-Zeilen prüft kein Lint.
- **`cc-dev` listet eine Skill mehr.** work-plan lädt mit jeder `cc-dev`-Installation und
  konkurriert im Routing mit impl-plan und dem eingebauten Plan-Modus; die Descriptions
  grenzen ab, gemessen ist die Kollision nicht.
- **Keine Projekt-Kopie in diesem Repo.** Hier gilt impl-plan; work-plan steht nicht in
  `PROJECT_SKILLS` von `scripts/sync_skills.py` und lädt in diesem Repo nur, wenn
  jemand `cc-dev` einschaltet.

## test-first

Gebaut nach Spec 24 (2026-10-13). Tier 1: `tdd_log.py` führt den Testbefehl aus und
schreibt `.skills/cache/test-first/log.md`. Was ungemessen bleibt und wo es beißt:

- **Rot heißt Exit ≠ 0.** Ein Import- oder Sammelfehler zählt als Rot, und so auch ein
  fehlendes Runner-Modul (`python -m pytest` ohne pytest) — das Skript sieht nur, dass
  `python` existiert. Die Skill lässt die Ausgabe vor dem ersten `red` lesen; geprüft
  wird das nicht.
- **Ein Test je Lauf ist Disziplin, kein Mechanismus.** `references/cycle.md` nennt die
  Form je Runner; gemessen ist nur pytest. Wer die ganze Suite übergibt, bekommt ein Rot,
  das ein fremder Test färben kann.
- **Windows:** Die Shell ist `cmd.exe`, Exit 127 heißt dort nichts; deshalb die
  Vorprüfung mit `shutil.which`. Die Prozessgruppe für die Zeitgrenze gibt es nur unter
  POSIX — unter Windows endet bei der Zeitgrenze nur die Shell, und ein Kindprozess, der
  die Pipe offen hält, kann den Aufruf weiter blockieren. Beides ungemessen.
- **Das Log ist der Beleg, nicht der Beweis.** Es hält fest, was `tdd_log.py` ausgeführt
  hat; ob der Befehl wirklich den genannten Test ausführt, prüft nichts. Wer das Log von
  Hand ändert, ändert den Zustand.
- **Nicht committet, nicht regenerierbar.** Das Log liegt unter `.skills/cache/`; geht
  es verloren, fehlt der Beleg dieser Arbeit. Subagenten von subagent-dev schreiben es in
  ihren Worktree, `verify` liest es nicht (Spec 24, Out of scope).
- **Auslösen ungemessen.** Die Evals installieren test-first allein. Ob die Skill bei
  „füge X hinzu" ohne Plan auslöst und ob sie im Listing von `cc-dev` sichtbar bleibt,
  zeigt kein Lauf (Spec 20 hat neun Skills ohne Description im Listing gemessen).
  Der Druckfall (`pressure-still-red-first`) misst nur einen Prompt.
- **Keine Projekt-Kopie.** test-first steht nicht in `PROJECT_SKILLS`; in diesem Repo
  lädt es nur über `cc-dev`, das hier ausgeschaltet ist.

## skill-dir

Spec 25 (2026-10-14): Jeder Skript-Aufruf steht in der SKILL.md als
`python "${CLAUDE_SKILL_DIR}/scripts/…"`; die Lint-Regel `script-paths` (skill-forge) hält
das. Gemessen mit einer Probe-Skill (CLI 2.1.296): Claude Code ersetzt die Variable im Text
der SKILL.md, in der Bash-Umgebung ist sie nicht gesetzt, in einer Reference bleibt sie
wörtlich. Was ungemessen bleibt und wo es beißt:

- **Eine SKILL.md, die mit Read statt über das Skill-Werkzeug geladen wird** (Subagent,
  Cowork, claude.ai), behält `${CLAUDE_SKILL_DIR}` wörtlich; die Shell macht daraus
  `/scripts/…`, und der Aufruf scheitert wie früher der repo-relative.
- **Hook-Vorlagen mit fehlender Kopie** geben eine `systemMessage` aus und enden mit 0. Ob
  Claude Code sie bei `PreToolUse` anzeigt, ist nach Doku angenommen, nicht gemessen;
  setup-repo nutzt denselben Weg für `Stop`.
- **Die Kopie unter `.claude/hooks/` veraltet.** Ein Update der Skill erreicht sie nicht;
  wer das Skript ändert, kopiert es erneut.
- **Nachbarn nur im selben Plugin.** `${CLAUDE_SKILL_DIR}/../<skill>/` trägt nur, wenn beide
  im selben Plugin-Cache oder beide unter `.claude/skills/` liegen; im Eval-Workspace liegt
  kein Nachbar, impl-plan und skill-forge sagen dann „ungeprüft".
- **Kopfzeilen nennen weiter `python skills/<name>/scripts/…`** — Herkunft, kein Aufruf;
  nur architecture-map schreibt `python scripts/<datei>`, weil `drift_check.py` das
  Kommando wieder ausführt.

## Verweise

[README](../README.md) · [Spec 00](../specs/Spec%2000%20%E2%80%93%20skill-foundation.md) ·
[Plan](superpowers/plans/2026-08-14-eval-harness.md) ·
[Plan feature-spec](superpowers/plans/2026-08-15-feature-spec.md) ·
[Plan motion-landing](superpowers/plans/2026-08-15-motion-landing.md)
[Plan verified-research](superpowers/plans/2026-08-15-verified-research.md)
[architecture-map-Plan](superpowers/plans/2026-08-17-architecture-map.md)
