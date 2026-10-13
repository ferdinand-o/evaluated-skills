# rest-api-architect — Implementierungsplan

**Spec:** `specs/Spec 07 – rest-api-architect.md`, abgeglichen mit `specs/Spec 00 – skill-foundation.md`.
**Auftrag:** `docs/superpowers/reports/rest-api-architect-report.md` (Abschlussbericht).
**Sechs verbindliche Entscheidungen** aus dem Dispatch (R1–R6) sind unten je an der Stelle
vermerkt, wo sie greifen — sie werden hier nicht neu verhandelt.

## Ziel

Die OpenAPI ist das Artefakt, die Konventionsdatei ist das Gesetz, die Skripte sind die
Polizei. Zwei Modi (Greenfield/Brownfield), kein Codegen. Drei Skripte, alle ohne die
Zielanwendung auszuführen:

- `gen_ruleset.py` (Tier 1) — `conventions.json` → `spectral-ruleset.json`, beides JSON (R1).
- `extract_openapi.py` (Tier 1) — statische Analyse (ast für FastAPI, Textsuche für
  Express/Hono), importiert die Zielanwendung **nicht** (R2, Sicherheitsgrund, nicht nur
  Abhängigkeitsfrage).
- `gate.py` (Tier 3) — Spectral-Lint + oasdiff-Breaking-Change-Check, G2. Spectral/oasdiff/npx
  sind hier nicht installiert; nur der Degradationszweig ist in dieser Umgebung verifizierbar
  (R3). Der Erfolgspfad wird trotzdem vollständig geschrieben und über gemockte
  `subprocess`-Aufrufe unit-getestet — das prüft die Parsing-/Auswertungslogik, nicht die
  echte Toolchain. Das bleibt in `docs/known-limits.md` vermerkt.

## Referenzarchitektur

`skills/dev-report/` ist das Vorbild für Aufbau und Tonfall. `evalkit/schema.py` und
`evalkit/assertions.py` definieren, was Evals prüfen können — Assertions binden ausschließlich
an Artefakte, die diese Skill erzeugt (OpenAPI-Datei, `x-verified`/`x-deviation`-Einträge,
generiertes Ruleset, `gate.py`-Textausgabe über den Agenten-Output).

## Artefakt-Pfade (Spec 00 §1)

| Artefakt | Klasse | Pfad | committed |
| --- | --- | --- | --- |
| Ist-/Soll-OpenAPI | Wissen | `api/openapi.yaml` (pro Service, R4) | ja |
| Projekt-Override Preset | Konfiguration | `.skills/rest-api-architect/conventions.json` | ja |
| generiertes Ruleset (aus Override) | Konfiguration | `.skills/rest-api-architect/spectral-ruleset.json` | ja |
| Brownfield-Audit-Bericht | Wissen | `docs/api-audit-<service>.md` | ja |
| Shipped Default-Preset + -Ruleset | Skill-Asset | `skills/rest-api-architect/assets/*.json` | ja (Teil der Skill) |

`api/openapi.yaml` und der Audit-Bericht tragen die Kopfzeile aus `docs/artifact-header.md`
(YAML-Kommentar bzw. Markdown-Kommentar). `conventions.json` (Default wie Override) trägt
**keine** Kopfzeile — es ist ein Preset zum Ausfüllen/Überschreiben, kein generiertes Artefakt,
analog zu `openapi-skeleton.yaml`. `spectral-ruleset.json` ist generiert und trägt `_meta`
(JSON-Konvention); ob echtes Spectral einen unbekannten Top-Level-Schlüssel toleriert, ist hier
nicht prüfbar (Node/Spectral fehlt) und gehört nach `known-limits.md`.

## Tasks

### Task 1 — `assets/conventions.json` + `references/conventions.md`

Preset: RFC 9457 `problem+json` mit zentraler Fehlercode-Registry (R6, Warnschwelle 50, keine
Selbst-Gliederung), Cursor-Paginierung, Pfadversionierung `/v{n}` mit Deprecation-Headern,
Idempotency-Key-Pflicht für unsichere POSTs, snake_case/Plural/keine Verben in Pfaden (mit
definierten Aktions-Ausnahmen), RFC 3339 UTC Zeitstempel. `conventions.md` erklärt das Preset
(*warum* RFC 9457 etc.), wiederholt die Werte nicht — eine Quelle, kein Drift.

### Task 2 — `scripts/gen_ruleset.py` + Tests

Reine Funktionen: `resolve_conventions_path`, `resolve_output_path`, `build_rules(conventions)
-> dict`, `build_ruleset(conventions) -> dict`, `main(argv)`. Pfad-Auflösung: `--conventions`
explizit > `.skills/rest-api-architect/conventions.json` (Projekt-Override) >
`assets/conventions.json` (Skill-Default). `--out` Default: gleiches Verzeichnis wie die
aufgelöste Konventionsdatei. Tests: Auflösung, Rule-Generierung pro Preset-Dimension,
`_meta`-Kopf im Output, Override ändert generierte Regel.

### Task 3 — `scripts/extract_openapi.py` + Tests

FastAPI: `ast`-Walk über `--src`, findet `@app.<method>(...)`/`@router.<method>(...)`-Decorators
mit String-Literal-Pfad. Direkt im Modul registriert → `x-verified: true`; hinter `ast.If`
verschachtelt → `x-verified: false` mit Grund „hinter Bedingung registriert"; Pfad kein
String-Literal (f-String/Variable) → eigener `x-extraction.unresolved`-Eintrag, keine
Pfad-Erfindung. Cross-File-Router-Komposition (`include_router` mit Prefix aus anderer Datei)
wird nicht aufgelöst — dokumentierte Grenze, betroffene Routen `x-verified: false`.

Express/Hono: Regex-Textsuche (`router\.(get|post|...)\(['"\`]...`) über `--src`. **Jeder**
Treffer bekommt `x-verified: false` — Textsuche ohne Kontrollfluss ist strukturell unsicherer
als AST, das wird nicht unterschlagen (R2).

Ausgabe: eigener, minimaler YAML-Dumper (Tier 1, kein PyYAML installiert) — Strings immer
doppelt gequotet, das ist immer gültiges YAML, auch ohne Sonderfall-Erkennung. Kopfzeile als
erste Zeile. Kein Import, kein Ausführen der Zielanwendung — nur `ast.parse`/Text.

Tests: FastAPI direkte Route (verified), Route hinter `if` (unverified), dynamischer Pfad
(unresolved-Liste), Express-Treffer (immer unverified), YAML-Dumper-Rundtrip auf
Sonderzeichen, `main()` schreibt Datei mit Kopfzeile.

### Task 4 — `scripts/gate.py` + Tests

`detect_toolchain() -> ToolchainStatus` (node/npx/spectral/oasdiff via `shutil.which`,
Spectral auch direkt ohne npx). `run_checklist(openapi_text, conventions) ->
list[CheckResult]` — regelbasierte Textprüfung, läuft **immer**, unabhängig von der
Toolchain (das ist der Teil aus R3, der „als Checkliste abgearbeitet" wird). `run_lint(...)`
und `run_breaking_change_check(...)` degradieren sichtbar mit der Zeile
`ungeprüft (Spectral/oasdiff nicht verfügbar)` (bzw. einzeln benannt, wenn nur ein Werkzeug
fehlt) statt stillem Überspringen — Spec 00 §4. Erfolgspfad (echter `subprocess`-Aufruf +
JSON-Parsing) ist vollständig geschrieben, aber nur mit gemocktem `subprocess.run` getestet;
kein Test behauptet echte Spectral-/oasdiff-Integration. `build_gate_report(...)`,
`format_report(...)`, `main(argv)`. Exitcode 0 nur wenn Checkliste (immer geprüft) plus
verfügbare Werkzeuge (falls vorhanden) grün sind; Degradation allein blockiert den Exitcode
nicht — G2, „meldet Verstoß", nie „blockiert".

Tests: Toolchain-Erkennung (gemockt), Checkliste einzeln pro Dimension (Treffer/Kein-Treffer),
Degradationsmeldung exakt bei fehlendem Werkzeug, gemocktes Spectral-JSON → Findings korrekt
gemappt, gemocktes oasdiff-Breaking-Output → Findings korrekt gemappt, kein Vorgänger-Pfad →
„kein Vorgänger, Breaking-Change-Check übersprungen" statt stillem Erfolg.

### Task 5 — `assets/openapi-skeleton.yaml`

Handgeschriebene YAML-Vorlage (kein Code parst sie): `info`, Error-Schema `problem+json`,
Paginierungs-Parameter, Beispiel-Pfad mit `x-deviation`-Platzhalter-Kommentar.

### Task 6 — `references/resource-modeling.md`, `references/evolution.md`

Ressourcen schneiden, Beziehungen, Aktionen-vs-Ressourcen-Grenzfälle. Deprecation-Playbook:
Feld hinzufügen statt umbenennen, `Deprecation`/`Sunset`-Header, Versions-Sunset-Fristen,
Breaking-Change-Definition (Feld entfernt/umbenannt, Pflichtfeld ergänzt, Statuscode geändert).

### Task 7 — `SKILL.md`

≤150 Zeilen. Frontmatter mit Routing zu `feature-spec` (Soll-Lieferant), `testing-strategy`
(Contract-Tests, `rest-api.md`-Adapter existiert bereits dort), `superpowers:writing-plans`
(Zerlegung nach Brownfield-Audit, R5). Abgrenzung: kein Codegen, kein GraphQL/gRPC, keine
Auth-Implementierung, kein Gateway/Deployment. Doktrin, Greenfield-/Brownfield-Ablauf,
Contract, Anti-Rationalisierungs-Tabelle, Gate-Ehrlichkeit (G2, nie „blockiert"),
Leerfälle: kein Vorgänger-Spec (erster Lauf), Brownfield ohne Abweichungen, Fehlercode-Registry
unter/über 50 Einträgen, exotisches Framework mit null extrahierten Routen, fehlende
Toolchain.

### Task 8 — Fixtures + `evals/rest-api-architect/evals.json`

Fixtures unter `evals/fixtures/`, alle mit `"git": true` wo Artefakte im Repo erwartet werden.
Vier Pflicht-Evals aus der Spec plus Pflicht-Anti-Zeremonie-Eval (Spec 00 §2):

1. `rename-triggers-deprecation-path` (behavior o. contract) — Feld-Umbenennungs-Wunsch gegen
   bestehende `api/openapi.yaml`; altes Feld bleibt sichtbar, Deprecation-Hinweis erscheint.
2. `brownfield-audit-reports-not-refactors` (contract) — Mischmasch-Repo, Audit-Bericht
   entsteht, Quellcode bleibt `file_unchanged`.
3. `endpoint-without-spec-update-is-caught` (contract) — neuer Endpoint im Code ohne
   Spec-Änderung provoziert; `api/openapi.yaml` enthält den neuen Pfad danach.
4. `exotic-framework-marks-unverified` (contract) — Framework ohne Introspektions-Support;
   extrahierte Einträge tragen `x-verified: false`.
5. `anti-ceremony-compliant-endpoint` (contract, Pflicht nach Spec 00 §2) — ein winziger,
   bereits konventionskonformer Endpoint löst keinen Audit-Bericht und keine
   `x-deviation`-Einträge aus.

Validierung nur mechanisch: `load_evals()` lädt ohne Fehler, keine `judge`-Assertion in
`contract`-Evals. `run_evals.py` wird nicht ausgeführt.

### Task 9 — `docs/known-limits.md` ergänzen

Abschnitt „rest-api-architect" mit: ungeprüfter Spectral-/oasdiff-Erfolgspfad, offene Frage
zur `_meta`-Verträglichkeit im Spectral-Ruleset, Cross-File-Router-Komposition nicht aufgelöst,
Express/Hono grundsätzlich `x-verified: false`, YAML-Dumper nur für die selbst erzeugten,
kontrollierten Strukturen gedacht (kein General-Purpose-YAML-Writer).

### Task 10 — Bericht

`docs/superpowers/reports/rest-api-architect-report.md` nach Abschluss.

## Reihenfolge & Commits

Task 1 → 2 → 3 → 4 → 5+6 → 7 → 8 → 9 → 10, nach jedem Task ein Commit mit deutscher
Conventional-Commit-Message. `pytest -q` bleibt nach jedem Task grün.
