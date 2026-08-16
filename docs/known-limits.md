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

## review-context

- **Der Uncommitted-Modus ist im Eval-Harness nicht prüfbar.** `collect_context.py` kann ohne
  `--range` das Arbeitsverzeichnis gegen HEAD reviewen (der realistischste Fall: „review meine
  gerade gemachte, noch nicht committete Änderung"), aber `evalkit.workspace.prepare()`
  hinterlässt nach jedem Fixture-Aufbau einen sauberen Baum — dieselbe Grenze, die oben bei
  `dirty-worktree` schon steht. Alle vier Evals in `evals/review-context/evals.json` nutzen
  deshalb `--range HEAD~1..HEAD`; der Uncommitted-Pfad ist nur durch Unit-Tests
  (`test_uncommitted_mode_reads_worktree`, `test_main_writes_cache_file`-Nachbarn) abgedeckt,
  nicht durch einen echten Agenten-Lauf.
- **Die „ab zwei Commits zählt die Commit-Message als Soll"-Regel ist eine eigene Entscheidung,
  nicht aus Spec 04 oder dem Auftrag zwingend ableitbar.** R13 nennt „Commit-Messages des
  Bereichs" als dritte Soll-Quelle, ohne eine Mindestanzahl zu nennen. Ohne diese Schwelle wäre
  „Diff ohne jedes Soll" (der wichtigste Eval, R13) nicht deterministisch erzeugbar, weil ein
  Range mit genau einem Commit sonst immer dessen eigene Subject-Zeile als Soll zählen würde
  (Tautologie: die Message beschreibt den Diff, nicht das Ziel dahinter). Wer stattdessen jede
  Commit-Message zählen lassen will, muss `MIN_COMMITS_FOR_MESSAGE_SOLL` in
  `skills/review-context/scripts/collect_context.py` auf `1` setzen und Eval 1 neu bauen.
- **Aufrufer-Suche ist namensbasiert, ohne Scope- oder Import-Analyse.** `find_callers()` grept
  `\bname\s*\(` über den ganzen Baum. Zwei unabhängige Funktionen mit demselben Namen in
  verschiedenen Modulen werden nicht unterschieden (falsch-positiv), und ein Aufruf über
  `self.name(...)`, eine Methode gleichen Namens auf einem anderen Objekt, oder ein Import-Alias
  (`from x import name as anders`) wird nicht erkannt (falsch-negativ). Dokumentierte Grenze,
  keine stille.
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

## Verweise

[README](../README.md) · [Spec 00](../specs/Spec%2000%20%E2%80%93%20skill-foundation.md) ·
[Plan](superpowers/plans/2026-08-14-eval-harness.md)
