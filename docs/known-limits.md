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

## Verweise

[README](../README.md) · [Spec 00](../specs/Spec%2000%20%E2%80%93%20skill-foundation.md) ·
[Plan](superpowers/plans/2026-08-14-eval-harness.md)
