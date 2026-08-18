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

## Verweise

[README](../README.md) · [Spec 00](../specs/Spec%2000%20%E2%80%93%20skill-foundation.md) ·
[Plan](superpowers/plans/2026-08-14-eval-harness.md) ·
[Plan feature-spec](superpowers/plans/2026-08-15-feature-spec.md) ·
[Plan motion-landing](superpowers/plans/2026-08-15-motion-landing.md)
[Plan verified-research](superpowers/plans/2026-08-15-verified-research.md)
