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

## Verweise

[README](../README.md) · [Spec 00](../specs/Spec%2000%20%E2%80%93%20skill-foundation.md) ·
[Plan](superpowers/plans/2026-08-14-eval-harness.md)
