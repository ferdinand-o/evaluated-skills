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

## exercise-forge

Vier Fix-Runden (Details in `docs/superpowers/reports/exercise-forge-report.md`).
Runde 1: ein unabhängiger Review fand zwei Defekte, die inzwischen behoben sind
(`export.py` glaubte eine von Hand geschriebene `"status": "verified"`;
`verify_open` verifizierte Aufgaben mit leerer `criteria`-Liste, weil `all([])`
in Python `True` ist). Runde 2: zusammengesetzte Judge-Claims zerlegt. Runde 3:
die Zerlegung deckte einen dritten, echten Defekt auf — ein G1-Doktrin-Fix
(SKILL.md verbietet Hand-Edits) wurde versucht. Runde 4: ein zweiter echter
Lauf zeigte, dass die Doktrin allein nicht reichte; gebaut wurde stattdessen
ein G2-Mechanismus (`status` wird beim Export abgeleitet, nicht gelesen —
unten). Was aus diesen Runden als Grenze bleibt, statt behoben zu werden:

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
- **G1-Doktrin gegen Hand-editiertes `verification` wurde ausprobiert und
  gemessen für unzureichend befunden — deshalb jetzt G2.** Nach der
  Zerlegung der drei zusammengesetzten Judge-Claims (Fix-Runde 3) fielen
  `mc-distractor-trap-is-caught` und `narrow-criteria-on-open-question-are-flagged`
  in einem echten `run_evals.py`-Lauf **mechanisch** an der neuen
  `must_not`-Assertion (`"status": "verified"` stand im Aufgaben-JSON, obwohl
  die Fixture absichtlich einen Konflikt enthält); `overspecified-coding-tests-are-flagged`
  fiel im selben Lauf noch als Ganzes am (damals noch zusammengesetzten)
  Judge-Claim. Fix-Runde 3 reagierte mit einer verschärften SKILL.md-Doktrin
  („Melden ersetzt nicht Markieren", G1, Selbstauskunft) — **und ein zweiter
  echter `run_evals.py`-Lauf zeigte danach: alle drei Evals fielen immer noch,
  an derselben `must_not`-Assertion.** Die Doktrin allein trug nicht; das ist
  jetzt gemessen, nicht vermutet. Nach Spec 00 §4 gehört an eine Stelle, an
  der eine G1-Selbstauskunft nachweislich versagt, ein G2-Mechanismus.
  **Fix-Runde 4 baut G2, und zwar die stärkere der zwei möglichen Fassungen
  (Ableiten statt Validieren):** `export.py` liest `verification.status` beim
  Rendern nicht mehr. Jeder Blind-Lauf schreibt jetzt zusätzlich
  `verification.protocol` — die Rohdaten des Vergleichs (z. B. `chosen_index`
  bei MC, `criteria_met` bei offenen Fragen, `model_passed`/`blind_passed`
  bei Coding). `export.derive_status_from_protocol()` berechnet den
  angezeigten Status ausschließlich aus diesem Protokoll, neu gegen die
  Aufgabendaten (Optionen, Kriterien) geprüft — ein von Hand gesetztes
  `status: verified` hat dadurch keine Wirkung mehr auf `[geprüft]`, egal ob
  `method`/`checked_at` echt aussehen oder nicht: das Protokoll entscheidet,
  das Wort wird gar nicht gelesen. Die alte `has_verified_provenance()`
  (Fix-Runde 1) prüfte nur *Vorhandensein* von `method`/`checked_at`, nicht
  *Stimmigkeit* mit `status` — genau diese Lücke war die wahrscheinlichste
  Erklärung für das gemessene Versagen der Doktrin und ist mit der Ableitung
  geschlossen. **Was auch damit nicht geschlossen ist:** `protocol` selbst
  bleibt eine JSON-Datei, die ein Editor-Werkzeug ändern kann. Wer nicht nur
  `status`, sondern auch ein vollständig konsistentes `protocol` von Hand
  fälscht (bei MC z. B. `chosen_index` auf die tatsächlich korrekte Option
  setzen), bekommt weiterhin `[geprüft]` — das ist aber eine deutlich
  aufwändigere, gezieltere Fälschung als ein einzelnes Wort zu ändern, und sie
  fällt bei MC/offenen Fragen zusätzlich gegen die Aufgabendaten selbst auf
  (die Optionen/Kriterien müssten mitgefälscht werden, was `validate_exercise()`
  an anderer Stelle wieder einschränkt). Eine Signatur oder ein Audit-Log, das
  `protocol` kryptographisch an den tatsächlichen Lauf bindet, wäre der
  nächste Schritt und wurde nicht gebaut.
- **Drei der ursprünglich sechs Judge-Claims waren zusammengesetzt und
  dadurch unzuverlässig — siehe der neue Punkt im Abschnitt „Judge" oben.**
  `mc-distractor-trap-is-caught`, `narrow-criteria-on-open-question-are-flagged`
  und `overspecified-coding-tests-are-flagged` verlangten je drei Bedingungen
  in einem Satz. Alle drei wurden in je eine mechanische Prüfung „Gate lief"
  (`method`-Feld im Aufgaben-JSON), eine mechanische Prüfung „nicht verified"
  (`must_not` auf `"status": "verified"`) und einen einzigen, einzeln
  entscheidbaren Judge-Claim „Konflikt sichtbar benannt" zerlegt.
- **Vier der sechs Evals sind gegen einen echten Agenten bestätigt**
  (`single-flashcard-stays-single`, `twenty-cards-stay-atomic`,
  `one-step-harder-changes-the-vector-not-just-wording`, sowie die
  Zerlegung selbst über zwei Läufe hinweg). Die drei „Gate findet ein
  Problem"-Evals sind seit dem G2-Fix (Fix-Runde 4, Ableiten statt
  Validieren) nicht erneut gegen einen echten Agenten gefahren worden — nur
  schema-validiert. Anders als nach Fix-Runde 3 ist die Erwartung diesmal
  nicht mehr „eine Doktrin, die hoffentlich reicht", sondern ein mechanischer
  Ausschluss (`status` wird gar nicht gelesen) — aber auch ein G2-Mechanismus
  ist erst bewiesen, wenn er gegen einen echten Lauf bestanden hat, nicht
  vorher.

## Verweise

[README](../README.md) · [Spec 00](../specs/Spec%2000%20%E2%80%93%20skill-foundation.md) ·
[Plan](superpowers/plans/2026-08-14-eval-harness.md)
