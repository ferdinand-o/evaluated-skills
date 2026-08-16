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
3. **Der YAML-Dumper wurde nur mit golden-string-Tests geprüft, nie mit einem echten
   YAML-Parser gegengelesen.** PyYAML ist in keiner der drei geprüften Python-Installationen
   (Projekt-venv, System-`python3`, Miniconda) vorhanden.
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
  echtes Modellverhalten. Insbesondere `rename-triggers-deprecation-path` hängt an der
  Erwartung, dass ein Modell „deprecat" irgendwo erwähnt — eine sprachlich enge, aber
  bewusst gewählte Formulierung, die in SKILL.md tatsächlich vorkommt.
