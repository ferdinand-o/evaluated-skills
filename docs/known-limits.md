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

## Verweise

[README](../README.md) · [Spec 00](../specs/Spec%2000%20%E2%80%93%20skill-foundation.md) ·
[Plan](superpowers/plans/2026-08-14-eval-harness.md)
