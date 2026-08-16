# Abschlussbericht: `rest-api-architect`

Spec: `specs/Spec 07 – rest-api-architect.md`, abgeglichen mit `specs/Spec 00 –
skill-foundation.md`. Branch `feat/rest-api-architect`, Basis `0831fb7`
(`specs/skill-foundation`).

## Was gebaut wurde

```
skills/rest-api-architect/
├── SKILL.md                  (92 Zeilen — Doktrin, Modi, Contract, Anti-Rationalisierung,
│                               Gate-Ehrlichkeit, Leerfälle, Abgrenzung)
├── references/
│   ├── conventions.md        (erklärt das Preset, wiederholt es nicht)
│   ├── resource-modeling.md  (Ressourcen schneiden, Beziehungen, Aktion vs. Ressource)
│   └── evolution.md          (Deprecation-Playbook, Breaking-Change-Definitionen)
├── assets/
│   ├── conventions.json      (Preset, kein Kopfzeilen-Artefakt — Vorlage, kein Generat)
│   ├── spectral-ruleset.json (generiert aus conventions.json, trägt _meta)
│   └── openapi-skeleton.yaml (von Hand gepflegte YAML-Vorlage, kein Code parst sie)
└── scripts/
    ├── gen_ruleset.py        (Tier 1, 14 Tests)
    ├── extract_openapi.py    (Tier 1, statisch, 19 Tests)
    └── gate.py               (Tier 3/G2, 28 Tests)

evals/rest-api-architect/evals.json   (5 Evals: 4 aus der Spec + Pflicht-Anti-Zeremonie)
evals/fixtures/{rename-trap,brownfield-api,spec-drift,exotic-framework,compliant-endpoint}/
tests/test_rest_api_architect_{gen_ruleset,extract_openapi,gate}.py  (61 neue Tests)
```

Alle sechs verbindlichen Entscheidungen (R1–R6) wurden wie vorgegeben übernommen, nicht neu
verhandelt:

- **R1** — `conventions.json`/`spectral-ruleset.json` sind JSON, `gen_ruleset.py` bleibt Tier 1
  ohne PyYAML. `openapi-skeleton.yaml` bleibt YAML als reine Vorlage.
- **R2** — `extract_openapi.py` importiert die Zielanwendung nie. FastAPI: `ast`-Walk über
  Dekoratoren, mit Unterscheidung „direkt registriert" (`x-verified: true`) vs. „hinter
  `if` versteckt" (`x-verified: false`, Grund benannt) vs. „Pfad kein String-Literal"
  (eigener `unresolved`-Eintrag). Express/Hono: Textsuche, **jeder** Treffer bekommt
  `x-verified: false` — Textsuche hat keinen Kontrollfluss-Begriff.
- **R3** — `gate.py` ist vollständig geschrieben, inklusive Erfolgspfad (echte
  `subprocess`-Aufrufe an Spectral/oasdiff, JSON-Parsing der Ausgabe). In dieser Umgebung
  echt verifiziert ist nur der Degradationszweig: Toolchain-Erkennung, die Konventions-
  Checkliste (reine Textprüfung, läuft immer) und die Meldung `ungeprüft
  (Spectral/oasdiff nicht verfügbar)` (bzw. einzeln benannt, wenn nur ein Werkzeug fehlt).
  Der Erfolgspfad ist zusätzlich mit **gemocktem** `subprocess.run` getestet — das prüft die
  Parsing-/Auswertungslogik, nicht die echte Toolchain-Integration. Nirgends in Code oder
  Doku steht „erprobt" dafür.
- **R4** — eine OpenAPI pro Service unter `api/openapi.yaml`, im Monorepo eine Spec je
  Service-Verzeichnis (SKILL.md, Greenfield-Schritt 2).
- **R5** — das Brownfield-Audit schreibt einen Bericht (`docs/api-audit-<service>.md`), plant
  nicht. SKILL.md verweist für die Zerlegung explizit an `superpowers:writing-plans`.
- **R6** — die Fehlercode-Registry lebt zentral in `conventions.json.errors.registry`, mit
  `warn_threshold: 50`. Die Skill gliedert bei Überschreitung nicht selbst um.

## Zusätzliche Entscheidungen, die im Auftrag nicht standen

- **`@dataclass` vermieden.** `tests/conftest.py::load_script` lädt Skill-Skripte per
  `importlib` ohne Registrierung in `sys.modules`. Unter Python 3.13 wirft
  `dataclasses._process_class` dann `AttributeError: 'NoneType' object has no attribute
  '__dict__'`, weil es `sys.modules.get(cls.__module__)` erwartet. Betroffen war zuerst
  `extract_openapi.py`s `ExtractionResult`; behoben durch eine einfache Klasse mit
  `__init__`. `gate.py` und `gen_ruleset.py` verwenden aus demselben Grund durchgehend
  dicts statt Datenklassen. Das ist eine Eigenart dieses Test-Ladewegs, keine allgemeine
  Python-3.13-Regression — `evalkit/schema.py` und `evalkit/assertions.py` nutzen
  `@dataclass` unverändert, weil sie als reguläre Pakete importiert werden.
- **Ruleset-Generierung ohne Regel für `naming.no_verbs_in_paths`.** Eine generische
  Verb-Liste als Spectral-`pattern`-Funktion nachzubilden wäre eine Rate-Heuristik mit
  vorgetäuschter Sicherheit. Diese Prüfung übernimmt ausschließlich der textbasierte
  Checklisten-Fallback in `gate.py` (dort mit einer kleinen, dokumentierten
  Verb-Kandidatenliste). `references/conventions.md`/`gen_ruleset.py`-Docstring nennen den
  Grund.
- **Konventions-Checkliste in `gate.py` ist textbasiert (Regex), nicht strukturell.** Ohne
  PyYAML kann `gate.py` die vom Nutzer/Claude editierte OpenAPI-YAML nicht zuverlässig
  strukturell parsen (kein fester Dialekt garantiert). Die Checkliste läuft deshalb als
  Substring-/Regex-Prüfung über den Rohtext — gröber als echtes Lint, aber ehrlich als das
  benannt, was sie ist, und unabhängig von jeder externen Toolchain immer lauffähig.
- **Eigener, minimaler YAML-Dumper in `extract_openapi.py`** statt eines Parsers: Strings
  werden immer doppelt gequotet (keine Sonderfall-Erkennung, dafür immer gültig). Bewusst
  nur für die selbst erzeugten, kontrollierten Strukturen gedacht.
- **Fixture-Namensgebung `brownfield-api`** folgt der in Spec 00 §2 selbst genannten Liste
  erwarteter geteilter Fixtures.

## Was nicht verifiziert werden konnte (gehört nach `docs/known-limits.md`, dort auch so
eingetragen)

1. **`gate.py`s Spectral-/oasdiff-Erfolgspfad** — nur mit gemocktem `subprocess` getestet,
   nie gegen ein echtes, installiertes Werkzeug. Spectral, oasdiff und `npx` sind hier nicht
   installiert (Node ja, `npx` nein) — exakt wie im Auftrag angekündigt.
2. **Ob echtes Spectral den `_meta`-Schlüssel im generierten Ruleset toleriert.** Die
   JSON-Artefakt-Konvention aus `docs/artifact-header.md` verlangt ihn; ob Spectrals
   Ruleset-Ladelogik einen unbekannten Top-Level-Schlüssel klaglos akzeptiert, ist offen.
3. ~~Der YAML-Dumper wurde nur mit golden-string-Tests geprüft, nie mit einem echten
   YAML-Parser gegengelesen.~~ **Überholt durch die Fix-Runde unten:** ein unabhängiger
   Reviewer hat ihn extern gegen echtes PyYAML 6.0.3 geprüft und für tragfähig befunden, eine
   reale Lücke (rohes CR) gefunden und hier behoben. PyYAML bleibt in keiner Python-Installation
   dieses Repos verfügbar — künftige Änderungen laufen weiterhin nur gegen golden-string-Tests.
4. **Die fünf Evals sind nicht gelaufen.** Nur `load_evals()` (Schema) und
   `evalkit.workspace.prepare()` (baut für alle fünf Fixtures erfolgreich einen Workspace,
   inklusive installierter Skill) wurden mechanisch geprüft — beides manuell verifiziert,
   nicht Teil der committeten Test-Suite. `run_evals.py` wurde absprachegemäß nicht
   ausgeführt.
5. **Cross-File-Router-Komposition** (`include_router` mit Prefix aus anderer Datei) wird von
   `extract_openapi.py` nicht aufgelöst — dokumentierte, bewusste Grenze.

## Testergebnis

```
207 passed in 3.24s
```

(146 zuvor bestehende plus 61 neue: 14 `gen_ruleset`, 19 `extract_openapi`, 28 `gate`.) Kein
bestehender Test wurde verändert oder entfernt.

## Commits (chronologisch)

```
bd92f28 docs(rest-api-architect): Implementierungsplan für Spec 07
6e82ae9 feat(rest-api-architect): Konventions-Preset als JSON plus Erklärung (R1, R6)
d0bb548 feat(rest-api-architect): gen_ruleset.py erzeugt Spectral-Ruleset aus conventions.json (Tier 1)
ec7af9b feat(rest-api-architect): extract_openapi.py analysiert FastAPI/Express statisch (R2, Tier 1)
ac0711e feat(rest-api-architect): gate.py mit Spectral/oasdiff-Erfolgspfad und geprüftem Degradationszweig (R3)
f124620 feat(rest-api-architect): OpenAPI-Skelett, Ressourcenmodellierung und Evolution-Playbook
97c3bdb feat(rest-api-architect): SKILL.md mit Doktrin, Modi, Contract und Leerfällen
31972ca test(rest-api-architect): fünf Evals plus Fixtures (vier Spec-Fälle + Pflicht-Anti-Zeremonie)
8e039e9 docs: rest-api-architect Known-Limits ergänzt (ungeprüfter Erfolgspfad, YAML-Dumper, Router-Präfixe)
```

## Offene Sorgen

- Der Erfolgspfad von `gate.py` (das eigentliche Herzstück des Breaking-Change-Gates) ruht
  vollständig auf Annahmen über das JSON-Ausgabeformat von `spectral lint -f json` und
  `oasdiff breaking -f json`. Sollte das reale Format abweichen (andere Feldnamen,
  verschachtelte Struktur statt flacher Liste), würde `parse_spectral_output`/
  `parse_oasdiff_output` leer durchlaufen statt zu crashen — ein stiller Fehlschlag statt
  eines lauten. Das ist selbst eine Instanz des in `known-limits.md` beschriebenen Risikos
  „stilles Überspringen" und sollte beim ersten echten Spectral/oasdiff-Lauf geprüft werden.
- Die Konventions-Checkliste in `gate.py` ist Regex-basiert und dadurch grundsätzlich
  gameable (wie jede reine Textprüfung) — z. B. ein `next_cursor`-String, der zufällig in
  einem Kommentar statt im Response-Schema steht, zählt als „gefunden". Das ist eine
  bewusste, dokumentierte Grenze des Degradationswegs, keine versteckte.
- Die fünf Evals sind plausibel konstruiert und mechanisch ladbar, aber ungetestet gegen
  echtes Modellverhalten. (Der ursprüngliche Punkt zu `rename-triggers-deprecation-path` ist
  durch die Fix-Runde unten überholt — siehe dort.)

---

## Fix-Runde (nach unabhängigem Review)

Ein Reviewer hat den Branch gegen den echten Code geprüft (YAML-Fälle mit tatsächlich
installiertem PyYAML, Extraktions-Fälle durch direkten Aufruf von
`extract_fastapi`/`extract_express` gegen Mini-Fixtures) und fünf Defekte plus eine Lücke
gefunden, die drei schwersten durch Ausführung nachgewiesen. Vollständiger Befund:
`<scratchpad>/review-rest-api-architect.md`.

### Entwarnung zuerst: der YAML-Dumper

Die im ersten Bericht formulierte Sorge um den handgerollten YAML-Dumper war unbegründet.
Gegen echtes PyYAML 6.0.3 geprüft (Doppelpunkte in Werten, führende/folgende Leerzeichen,
`yes`/`no`/`on`/`1.0`/`null`-artige Strings, mehrzeilige Beschreibungen, Sonderzeichen, lange
Zeilen, Tabs, Unicode) läuft er für seinen tatsächlichen Einsatzbereich korrekt durch. Eine
reale, schmale Lücke blieb: ein rohes Carriage-Return (`\r`) wurde nicht escaped und wäre von
echten YAML-Loadern still zu einem Leerzeichen gefaltet worden. Behoben in `_yaml_quote`
(`skills/rest-api-architect/scripts/extract_openapi.py`), mit Test. Die Umstellung auf
JSON-Ausgabe, die zwischenzeitlich erwogen wurde, entfällt damit.

### Behoben

1. **Defekt 1 — `path=`-Keyword-Argument ließ Routen spurlos verschwinden.**
   `_extract_functiondef` prüfte `call.args` vor jeder Berücksichtigung von Keywords. Neue
   Hilfsfunktion `_path_argument()` prüft zuerst positional, dann das `path=`-Keyword.
2. **Defekt 2 — `app.add_api_route()`/`app.add_route()` wurden nie besucht.** `_walk_fastapi_body`
   kannte keinen `ast.Expr`-Zweig. Neue Funktion `_handle_registration_call()` erkennt beide
   Registrierungsformen, liest `methods=[...]` (Default `["get"]`, dokumentierte Annahme) und
   den Endpoint-Funktionsnamen.
3. **Defekt 3 — Express-Regex kannte nur `app`/`router` als Variablennamen.** `_EXPRESS_ROUTE_RE`
   akzeptiert jetzt jeden gültigen JS-Bezeichner vor dem Methodennamen. Kosten bewusst in Kauf
   genommen: höheres False-Positive-Risiko bei generischen `.get()`-Aufrufen (z. B.
   Cache-/Map-Zugriffe) — hingenommen, weil jeder Treffer ohnehin `x-verified: false` trägt.
4. **Defekt 4 — Testassertion bewachte nichts.** `"dynamic_route" in str(entry) or
   entry["reason"]` war wegen Operatorpriorität für praktisch jeden nichtleeren
   `unresolved`-Eintrag wahr. Ersetzt durch eine Prüfung auf den konkreten Eintrag
   (Funktion + exakter Grund). Grep über alle drei Testdateien bestätigt: dieselbe Konstruktion
   kam nirgends sonst vor.
5. **Defekt 5 — `rename-triggers-deprecation-path` bewachte nur generischen Text.** Die vier
   ursprünglichen `must`-Zeilen prüften ausschließlich Substrings (`user_name`, `full_name`,
   `deprecat`), erfüllbar durch ein Modell mit allgemeinem REST-Wissen ohne die Skill je zu
   laden — ein Verstoß gegen die bereits in `docs/known-limits.md` (Abschnitt „Isolation")
   dokumentierte Regel. Eine naheliegende Reparatur — die Assertion an `x-deviation` zu hängen
   — wäre doktrinär falsch gewesen: der Deprecation-Pfad ist preset-*konformes* Verhalten
   (`conventions.json` `breaking_changes.fix`), keine Abweichung vom Preset, die `x-deviation`
   verdient hätte. Stattdessen: Klasse auf `behavior` geändert, ein Judge-Claim verlangt jetzt
   die beiden konkreten, projektspezifischen Header-Namen aus dem Preset (`Deprecation`,
   `Sunset` aus `conventions.json` `versioning.deprecation_headers`) im Kontext des Endpoints —
   Vokabular, das nicht aus generischer API-Kenntnis folgt. Die mechanischen `must`-Zeilen
   bleiben als billiger Vorfilter, jetzt mit einer Näheprüfung (`user_name` gefolgt von
   `deprecated` innerhalb von 400 Zeichen) statt zweier unabhängiger Substring-Checks.
6. **Lücke — rohes CR im YAML-Dumper.** Siehe Entwarnung oben; behoben mit Test.

Zusätzlich (nicht im Review benannt, aber beim Beheben von Defekt 2 als direkte Verbesserung
mitgezogen): `_walk_fastapi_body` rekursiert jetzt auch in `for`/`while`/`try`-Blöcke (vorher
blinde Flecken wie `if` vor der Fix-Runde) und markiert Routen darin konservativ als
`x-verified: false`, statt sie unsichtbar zu lassen. Ein Text-Auffangnetz
(`_DECORATOR_LOOKALIKE_RE`/`_REGISTRATION_LOOKALIKE_RE`) vergleicht pro Datei „wie viele
Registrierungs-Lookalikes im Rohtext" gegen „wie viele hat der AST-Walk tatsächlich
zugeordnet" und meldet die Differenz als dateiweiten `unresolved`-Eintrag — das fängt Fälle wie
eine aliasierte Decorator-Funktion (`get = app.get`, `@get(...)`), die auch nach den
Erweiterungen strukturell unsichtbar bleiben.

### Bewusst nicht behoben (Begründung)

- **Express `.route(path).method(handler)`-Chaining** wird weiterhin nicht erkannt — beim
  Review neu identifiziert, aber nicht einer der drei konkret nachgewiesenen Defekte. Jetzt in
  `docs/known-limits.md` vermerkt statt stillschweigend liegen gelassen.
- **Evals 2–4 und der Anti-Zeremonie-Eval wurden nicht verändert.** Der Reviewer hat sie
  explizit gegen denselben Maßstab geprüft und als sauber befunden (Abschnitt „Was in Ordnung
  ist" im Befund) — sie hängen bereits an `x-verified`, `docs/api-audit-<service>.md` und
  `x-deviation`, alles skill-eigene Konventionen. Eigene erneute Prüfung bestätigt das; keine
  Änderung vorgenommen.
- **Das Auffangnetz für FastAPI-Lookalikes ist selbst eine Heuristik**, kein Vollständigkeits-
  beweis (z. B. Router, die über Fabrikfunktionen mehrfach weitergereicht werden, bleiben
  ungedeckt). Dokumentiert in `docs/known-limits.md`, nicht weiter gejagt — die drei konkret
  nachgewiesenen Defekte sind behoben, das Auffangnetz ist eine zusätzliche Sichtbarkeits-
  verbesserung, kein Vollständigkeits-Versprechen.
- **`gate.py`s Erfolgspfad wurde vom Reviewer nicht bemängelt** (siehe „Was in Ordnung ist") —
  keine Änderung. Die bereits im ersten Bericht genannte Sorge zum unverifizierten
  Ausgabeformat bleibt unverändert bestehen.

### Testergebnis nach der Fix-Runde

```
219 passed in 3.17s
```

(207 vorher plus 12 neue: 11 zusätzliche `extract_openapi`-Tests für die drei behobenen
Defekte, den CR-Fix und das Auffangnetz, plus die reparierte `dynamic_route`-Assertion zählt
nicht doppelt.) `load_evals('evals/rest-api-architect/evals.json')` liefert weiterhin 5.

### Commits der Fix-Runde

```
99231b4 fix(rest-api-architect): extract_openapi.py verliert keine Routen mehr spurlos
f9d10b1 fix(rest-api-architect): rename-triggers-deprecation-path bewacht jetzt Skill-Artefakte
19975dc docs: known-limits.md nach Fix-Runde nachgezogen (YAML-Dumper geprüft, neue Grenzen)
```
