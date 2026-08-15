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
  Judge-Urteil ab, das nie gegen einen echten Agentenlauf geprüft wurde
  (siehe nächster Punkt).
- **Eval 1 und Eval 3 laufen nie ohne `run_evals.py`.** Beide sind
  `class: behavior` mit Judge-Claims
  (`google-labs-prompt-yields-single-highlight-storyboard`:
  Ein-Höhepunkt-Storyboard statt Effekt-Konfetti;
  `reduced-motion-scene-shows-static-content-not-frozen-hidden`: Sichtbarkeit
  des Panel-Inhalts unter der CSS-Kaskade). Keiner der Claims wurde gegen
  einen echten Agentenlauf verifiziert — nur das Schema wurde mechanisch
  geprüft (`evalkit.schema.load_evals`). Ob die Claims tatsächlich zwischen
  einem korrekten und einem defekten Fix unterscheiden, zeigt sich erst
  beim ersten echten Judge-Lauf — insbesondere für Eval 3, dessen
  Judge-Claim genau den in dieser Fix-Runde gefundenen Defekt auffangen
  soll und dessen Formulierung deshalb noch ungeprüft ist.
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

## Verweise

[README](../README.md) · [Spec 00](../specs/Spec%2000%20%E2%80%93%20skill-foundation.md) ·
[Plan](superpowers/plans/2026-08-14-eval-harness.md) ·
[Plan motion-landing](superpowers/plans/2026-08-15-motion-landing.md)
