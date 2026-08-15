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
- **Verzeichnis- statt Datei-Ebene für den Projekt-Override (Abweichung von Spec 00 §1).**
  `registry.py resolve_base_dir()` prüft, ob `.skills/verified-research/` im Projekt
  existiert — nicht, ob eine gleichnamige Datei existiert, wie Spec 00 §1 wörtlich sagt.
  Grund: Eine neue `research/<thema>.md` hat bei ihrer ersten Recherche naturgemäß noch
  keine gleichnamige Vorgänger-Datei; wörtlich genommen würde der Override nie greifen
  und der erste Schreibzugriff ginge nach `~/.skills/verified-research/` — im
  Eval-Harness das echte Home-Verzeichnis des Aufrufers (siehe „Isolation" oben). Alle
  sieben Fixtures legen deshalb `.skills/verified-research/registry.json` im Workspace
  an, damit dieser Fall im Eval-Set nicht auftritt. Läuft die Skill jedoch in einem
  Projekt, das weder `.skills/verified-research/` noch eine bestehende Wissensdatei hat,
  entscheidet dieselbe Abweichung, ob der allererste Lauf projektlokal oder global
  landet — das ist keine Spec-00-Konformität, sondern eine dokumentierte,
  begründete Ausnahme, die ein künftiger Review absegnen oder verwerfen sollte.
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
[Plan verified-research](superpowers/plans/2026-08-15-verified-research.md)
