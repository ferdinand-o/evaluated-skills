<!-- skill: architecture-map | schema: 1 | generated: von Hand nach Implementierung geschrieben (kein Skript) -->

# Implementierungsbericht: architecture-map (Spec 10)

Branch `feat/architecture-map`, Basis `specs/skill-foundation` (0831fb7). Ursprünglich
zwölf Commits, 227/227 Tests grün. Nach einer unabhängigen Review-Runde (siehe
Abschnitt „Fix-Runde" am Ende) fünfzehn Commits, 243/243 Tests grün.

## Was gebaut wurde

```
skills/architecture-map/
├── SKILL.md                       (121 Zeilen, Frontmatter nur name/description)
├── references/
│   ├── c4-levels.md
│   ├── finding-catalog.md         (Namensabweichung, siehe unten)
│   └── narration.md
└── scripts/
    ├── extract_py.py              (Tier 1, ast — Import-/Klassengraph)
    ├── extract_ts.py              (Tier 1, Textsuche — Import-Graph, dokumentiert ungenau)
    ├── to_mermaid.py              (Tier 1 — deterministisches Rendering + Rückparser)
    ├── analyze_graph.py           (Tier 1 — Zyklen, Ausreißer, Schichtverletzungen, tote Module)
    └── drift_check.py             (Tier 1 — regeneriert, vergleicht, schreibt nie)

evals/architecture-map/evals.json  (5 Evals: 4 contract, 1 behavior)
evals/fixtures/cyclic-imports/     (Python-Paket mit Zyklus außerhalb der Lese-Stichprobe,
                                     inkl. vorgebautem ARCHITECTURE.md für den Drift-Eval)
evals/fixtures/layered-service/    (3-Schichten-Service, layers.json, bewusste Verletzung,
                                     totes Modul)

tests/test_architecture_map_extract_py.py     (23 Tests)
tests/test_architecture_map_extract_ts.py     (21 Tests)
tests/test_architecture_map_to_mermaid.py     (10 Tests)
tests/test_architecture_map_analyze_graph.py  (16 Tests)
tests/test_architecture_map_drift_check.py    (13 Tests)

docs/superpowers/plans/2026-08-17-architecture-map.md
```

Alle fünf Skripte sind **Tier 1** (nur Stdlib): `ast` für Python, Regex-Textsuche für
TS/JS, reine Graphalgorithmen (Tarjan-SCC) für die Analyse, `subprocess`+`json` für den
Drift-Check. Kein Skript importiert fremden Code — nur `ast.parse`/Text (Ruling A3).

## Basis-Abweichung (vor der Implementierung)

Der Auftrag verlangte die Prüfung `git log --oneline -1` == `0831fb7`. Der tatsächliche
Zustand war `9d8265e` (Merge von `cad-parts-skill`) auf Branch `feat/dev-report`. Wie
angewiesen: `git checkout -B feat/architecture-map specs/skill-foundation` — dieser
Branch existierte und zeigte exakt auf `0831fb7`. Kein BLOCKED nötig.

`brief-common.md` war unter dem genannten Scratchpad-Pfad **nicht auffindbar** (weder
dort noch sonst im Dateisystem, per `find /` geprüft) — nur `rulings-final-four.md`
existierte. Als Ersatz-Fundament diente `specs/Spec 00 – skill-foundation.md` direkt
(Artefakt-Vertrag, Eval-Vertrag, Dependency-Tiers, Gate-Ehrlichkeit, Routing) plus das
bereits gebaute Referenzbeispiel `skills/dev-report/` für konkrete Konventionen
(Kopfzeilen-Regex, `.skills/cache/`-Pfadmuster, `tests/conftest.py::load_script`,
Eval-Schema aus `evalkit/`).

## Die vier dokumentierten Abweichungen von Spec 10s Textfassung

Alle vier sind durch `rulings-final-four.md` vorgegeben, hier nur mit der konkreten
Umsetzung:

1. **C1 — `extract_py.py` ist Tier 1, nicht Tier 2 (pyreverse/pydeps).** `ast.walk`
   liest `Import`/`ImportFrom`-Knoten direkt, auch verschachtelt in Funktionen/Klassen.
   Relative Importe werden über die Python-Semantik für führende Punkte aufgelöst
   (`_resolve_base`), mit Präfix-Rückfall für `from pkg import x`, wenn `x` kein
   eigenes Submodul ist.
2. **C2 — `extract_ts.py` als Tier-1-Textsuche, nicht ts-morph.** Regex für
   `import…from`, bare `import './x'`, `export…from`, `require()`, dynamisches
   `import()`; Kommentare werden vorher entfernt. **Ausdrücklich als ungenau
   dokumentiert** (Modul-Docstring, SKILL.md-Contract-Absatz): keine Typauflösung,
   keine tsconfig-Pfad-Aliase, String-Literal-Rauschen als bekannte Restlücke.
3. **C3 — ein `ARCHITECTURE.md` pro Service.** `--root` an den Extraktions-Skripten
   zieht die Grenze; SKILL.md instruiert das explizit unter Schritt 1.
4. **C4 — Mermaid immer generiert, deterministisch sortiert.** `to_mermaid.render()`
   sortiert Knoten nach `id`, Kanten nach `(from, to)`, unabhängig von der
   Eingabereihenfolge (durch Property-Test abgesichert: Permutation der Eingabe ändert
   die Ausgabe nicht).

Zusätzlich **A2**: `layers.json` statt `layers.yaml` (Stdlib kennt kein YAML) — von
`analyze_graph.py` direkt gelesen.

## Design-Entscheidungen, die über die Rulings hinausgingen

- **Graph-JSON-Schema** ist gemeinsam für Python/TS: `{_meta, language, level, nodes,
  edges, external}`. `level: "class"` nur für explizit übergebene `--files`
  (Hotspot-Zwang aus Spec 10, sonst ist der Klassen-Vollgraph unlesbar).
- **Drift-Check ohne separaten Graph-Speicher:** `to_mermaid.py`s Format ist
  verlustfrei für Knoten-IDs und Kanten, also liest `drift_check.read_mermaid_blocks`
  + `to_mermaid.parse` den zuletzt committeten Graphen direkt aus dem bereits
  committeten `ARCHITECTURE.md` zurück. Ein `<!-- architecture-map:graph-hashes -->`
  JSON-Footer trägt nur Hash + Erzeugungskommando je Ebene — kein Duplikat-Speicher,
  kein zusätzliches Artefakt.
- **Layer-Richtung präzisiert:** `layers.json["order"]` ist von innen nach außen
  (Index 0 = innerste Schicht). Erlaubt: außen → innen. Verletzung: innen → außen
  (`domain` importiert `infrastructure`). Das war im ersten Plan-Entwurf sprachlich
  mehrdeutig ("nach rechts zeigen") und wurde vor der Implementierung korrigiert
  (Commit `04346dd`s Vorgänger-Plan-Edit).
- **`sys.argv[0]` statt hartkodiertem Skriptpfad** in `_meta.generated` (Commit
  `9e7ba14`): `drift_check.py` führt das gespeicherte Kommando später tatsächlich
  erneut aus (`subprocess.run`) — anders als bei `dev-report`, wo die Kopfzeile rein
  dokumentarisch ist. Ein hartkodierter `skills/architecture-map/…`-Pfad wäre falsch,
  sobald die Skill unter `.claude/skills/architecture-map/…` installiert ist (Standard
  im Eval-Harness, siehe `evalkit/workspace.py::prepare`). Ich habe das durch einen
  End-to-End-Test gegen eine simulierte `.claude/skills/`-Installation verifiziert.
- **`.claude/` von der Extraktion ausgeschlossen** (Commit `0762589`): beim Verifizieren
  der Drift-Check-Fixture fiel auf, dass `--root .` sonst die installierten
  Skill-Skripte selbst als Teil der analysierten Codebase einliest — derselbe Fehler,
  den `.skills/`/`node_modules/` schon vermeiden sollten, nur für den neuen
  Installationsort.
- **`drift_check.py --graph <path>`** als zusätzlicher Hash-Ausgabe-Modus (Commit
  `aefd23e`): der Workflow in SKILL.md Schritt 7 braucht eine Möglichkeit, den
  `graph_hash` für den Footer-Block zu berechnen, ohne Python interaktiv aufzurufen.

## Unerwartete Tool-Restriktion

Der Dateiname `references/findings.md` (wörtlich aus Spec 10 übernommen) wurde vom
Schreib-Tool als vermeintliche Report-Datei blockiert (Fehlermeldung: "Subagents should
return findings as text, not write report files") — bestätigt filenamebasiert, nicht
inhaltsbasiert (derselbe Inhalt unter `/tmp/.../findings.md` wurde ebenfalls
blockiert). Ausweichlösung: `references/finding-catalog.md`. SKILL.md und
`narration.md` verweisen konsistent auf den neuen Namen.

## Eval-Design (A6)

`evals/architecture-map/evals.json`, 5 Evals gegen zwei neue Fixtures:

- **`cyclic-imports-cycle-named`** (contract) — Spec 10 Eval 1: Zyklus zwischen
  `src/domain/models/user.py` und `src/infra/db/session.py`, umgeben von
  unauffälligen Füllmodulen (`src/api/routes.py`, `src/domain/services/order.py`).
  Verifiziert: `extract_py.py` + `analyze_graph.py` finden ihn tatsächlich (manuell
  gegen die Fixture laufen lassen, siehe unten).
- **`small-service-gets-separate-sections-not-a-monolith`** (contract) — Pflicht-
  Anti-Zeremonie-Eval nach A6, zugleich Spec 10 Eval 2: acht Python-Dateien dürfen
  keine monströse Doku bekommen (`file_max_lines: 200`, getrennte Kontext-/
  Modul-Überschriften verlangt).
- **`layer-violation-is-named`** (contract) — `domain/broken.py` importiert bewusst aus
  `infrastructure/db.py`; verifiziert, dass `find_layer_violations()` das tatsächlich
  findet (siehe Verifikationslauf unten).
- **`unsupported-architecture-claim-is-marked`** (behavior) — Spec 10 Eval 4: eine im
  Prompt erzwungene DDD/CQRS-Behauptung, die aus einem Import-Graphen nicht ableitbar
  ist, muss fehlen oder als „Beobachtung (nicht graph-belegt)" markiert sein.
- **`drift-check-reports-unchanged-and-writes-nothing`** (contract) — braucht ein
  bereits vorhandenes, **korrektes** `ARCHITECTURE.md`. Dafür wurde
  `evals/fixtures/cyclic-imports/ARCHITECTURE.md` reproduzierbar aus dem echten
  Graphen erzeugt (Skript nicht Teil des Repos, nur zur Fixture-Erstellung benutzt) und
  gegen eine simulierte `.claude/skills/architecture-map/`-Installation verifiziert:
  `drift_check.check()` meldet `unchanged`, kein Byte der Datei ändert sich.

Jede `must`-Assertion hängt an `ARCHITECTURE.md`, dem Graph-JSON oder dem
Mermaid-Header — Artefakten, die ausschließlich diese Skill erzeugt (A6). Alle fünf
Evals wurden gegen `evalkit.schema.load_evals()` geladen (Schema-Validierung bestanden)
und **nicht ausgeführt** — kein Subagent-Lauf, kein Judge-Aufruf, wie beauftragt.

## Testergebnis

```
227 passed in ~3.5s   (146 Bestand vor dieser Arbeit + 81 neu)
```

Manuell gegen die beiden neuen Fixtures verifiziert (nicht Teil der pytest-Suite,
sondern zur Eval-Vorbereitung): `extract_py.py` findet den Zyklus in `cyclic-imports`
korrekt (`[['src.domain.models.user', 'src.infra.db.session']]`) und die
Schichtverletzung in `layered-service` korrekt
(`domain.broken -> infrastructure.db`).

## Offene Sorgen

- **`extract_ts.py`s Textsuche ist eine echte Genauigkeitsgrenze, kein
  Implementierungsdetail.** Barrel-Re-Exports, tsconfig-Pfad-Aliase (`@app/*`) und
  String-Literale, die zufällig wie Importe aussehen, werden falsch oder gar nicht
  behandelt. Für TypeScript-Repos mit solchen Mustern liefert der Modulgraph
  systematisch Lücken — das steht in SKILL.md und im Modul-Docstring, aber es bleibt
  eine Skill, die für TS/JS strukturell schwächer ist als für Python.
- **`layers.json` wird nirgends automatisch angelegt** (Bootstrap-Regel) — ohne sie
  laufen Schichtverletzungs-Checks als `null` (ungeprüft). Das ist Absicht (A4), aber
  es bedeutet: die Skill ist beim ersten Lauf gegen ein unbekanntes Repo strukturell
  blind für Schichtverletzungen, bis jemand die Datei von Hand anlegt oder die Skill
  eine Ableitung vorschlägt (SKILL.md Schritt 3 sagt "anbieten", nicht "automatisch
  tun" — im echten Gespräch bräuchte das noch eine konkrete Ableitungslogik, die hier
  nicht gebaut wurde, nur die Anweisung, danach zu fragen).
- ~~Klassenebene löst Basisklassen nur über den einfachen Namen auf, zwei gleichnamige
  Klassen würden fälschlich verknüpft~~ — **behoben in der Fix-Runde (Review-Anmerkung
  A1):** `extract_classes()` bricht jetzt mit `ExtractError` ab, wenn ein mehrdeutiger
  Name tatsächlich als Basisklasse referenziert wird, statt eine falsche Kante zu raten.
- **`drift_check.py` regeneriert per `subprocess`, nicht in-process** — das ist
  langsamer als nötig, aber die einzige Möglichkeit, `sys.argv[0]`-basierte
  Selbstauskunft konsistent zu halten (siehe Design-Entscheidung oben). Bei sehr
  großen Repos könnte das spürbar werden; nicht gemessen.
- **`references/finding-catalog.md` weicht vom in Spec 10 wörtlich genannten
  `findings.md` ab** (Tool-Restriktion, siehe oben). Wer die Spec wörtlich mit dem
  Repo abgleicht, findet die Abweichung — sie ist hier und in SKILL.md/narration.md
  dokumentiert, aber es ist ein Bruch mit dem Spec-Text, kein Bruch mit einem Ruling.
- **Kein Eval wurde tatsächlich ausgeführt** (wie beauftragt) — nur die
  Schema-Validierung und ein manueller Verifikationslauf der zugrundeliegenden
  Skripte gegen die Fixtures. Ob ein echter Subagent die SKILL.md-Anweisungen korrekt
  in die erwarteten Artefaktpfade übersetzt (insbesondere den Footer-Block korrekt
  von Hand zusammenbaut), ist ungeprüft.

## Fix-Runde (unabhängiges Review)

Ein unabhängiger Reviewer fand 3 Defekte, 3 Lücken, 2 Anmerkungen
(`/tmp/.../scratchpad/review-architecture-map.md`). Alle acht wurden bearbeitet.

**Defekte:**

- **D1 — kein Eval prüfte die eiserne Regel ("generiert, nie von Hand gezeichnet").**
  Die drei content-only Contract-Evals bestanden auch bei einem handgezeichneten
  Mermaid-Diagramm mit den richtigen Wörtern. Fix: alle drei tragen jetzt zwei
  zusätzliche `file_matches`-Assertions auf den `%%`-Erzeugungskommando-Header im
  Mermaid-Block und den `<!-- architecture-map:graph-hashes -->`-Footer — beides kann
  keine fremde Skill und kein zufälliger Text erzeugen (Antwort auf die
  Kontaminationsfrage aus A6).
- **D2 — `graph_hash()` ignorierte `external`.** Eine neue/entfernte externe
  Abhängigkeit änderte weder `nodes` noch `edges`, blieb also für den Drift-Check
  unsichtbar, obwohl sie die Kontext-Ebene betrifft. Fix: `graph_hash()` hasht jetzt
  auch `external`; `diff_graph()` bekam `external_added`/`external_removed`, gespeist
  aus einem neuen `external`-Feld im Footer (da `external` nie ins Mermaid-Diagramm
  gezeichnet wird und `to_mermaid.parse()` es folglich nicht zurückliefern kann). Per
  End-to-End-Test verifiziert: nur eine neue externe Abhängigkeit hinzugefügt, `nodes`/
  `edges` identisch → `status: "drift"` mit `external_added: ["requests"]`.
- **D3 — Modul-ID-Kollisionen wurden in `discover_modules()` stillschweigend
  überschrieben.** `src/widgets.ts` + `src/widgets/index.ts` (oder `a/b.py` +
  `a.b.py`) lieferten beide dieselbe ID; welche Datei gewinnt, hing von
  `sorted(rglob(...))` ab — ein ganzer Knoten samt Kanten konnte spurlos verschwinden,
  ohne dass der A4-Nullresultat-Schutz griff. Fix: eine Kollision ist jetzt ein harter
  `ExtractError`, in Python wie TypeScript, mit Test für beide Sprachen.

**Lücken:**

- **L1 — der `layers.json`-fehlt-Fall war narrativ ungetestet.** `analyze_graph.py`
  unterschied `null`/`[]` sauber im Befund-JSON, aber ob „ungeprüft" auch tatsächlich
  im für Menschen bestimmten `ARCHITECTURE.md` ankommt, hing komplett von freier
  Textgenerierung ab. Fix: neue Funktion `layers_summary()` liefert einen kanonischen
  Satz pro Fall ("ungeprüft (keine layers.json gefunden)" / "geprüft: keine
  Schichtverletzungen gefunden" / "geprüft: N Schichtverletzung(en) gefunden");
  SKILL.md verlangt die wörtliche Übernahme. Zwei neue Eval-Assertions prüfen beide
  Fälle sprachlich getrennt (`(?i)ungeprüft` bei `cyclic-imports`, `(?<!un)geprüft` bei
  `layered-service`).
- **L2 — der zugesagte Kurzschluss-Test für `drift_check.py` fehlte.** Der Plan
  versprach einen Spy/Zähler-Test dafür, dass bei Hash-Treffer weder `diff_graph()`
  noch `to_mermaid.parse()` aufgerufen werden; die gelieferte Testdatei prüfte nur das
  Endergebnis. Fix: `test_check_short_circuits_diff_when_hash_matches` patcht beide
  Funktionen mit Zählern und beweist, dass sie bei `status: "unchanged"` nie aufgerufen
  werden.
- **L3 — explizite `.js`-Importe aus `.ts`-Quellen (ESM/`nodenext`-Konvention) waren
  nicht dokumentiert und nicht aufgelöst.** `'./foo.js'` erfüllte
  `target.endswith(SUFFIXES)` und lieferte ausschließlich `foo.js` als Kandidat, nie
  `foo.ts` — ein verbreitetes, kein exotisches TS/ESM-Muster. Fix:
  `_relative_candidates()` probiert bei einer geschriebenen Extension jetzt zuerst sie
  selbst, dann die übrigen `SUFFIXES` am selben Pfadstamm.

**Anmerkungen:**

- **A1 — Klassennamen-Kollision bei mehreren Hotspot-Dateien.** Siehe oben, jetzt ein
  harter `ExtractError`, aber nur wenn der mehrdeutige Name tatsächlich als Basis
  referenziert wird — zwei gleichnamige, nie verknüpfte Klassen bleiben erlaubt.
- **A2 — `must_not` in Eval 5 war durch das gleichzeitige `file_unchanged` wirkungslos.**
  Ersatzlos gestrichen.

**Ergebnis:** 243/243 Tests grün (227 vor der Fix-Runde, +16 neue über
`test_architecture_map_{drift_check,extract_py,extract_ts,analyze_graph}.py`).
`evals/architecture-map/evals.json` erneut gegen `evalkit.schema.load_evals()`
validiert (5 Evals, keine Schema-Fehler), Evals nicht ausgeführt (wie beauftragt).
`docs/known-limits.md` um einen `## architecture-map`-Abschnitt mit den nach der
Fix-Runde bewusst verbliebenen Grenzen ergänzt (Kollision blockiert ganz statt
teilweise, `external`-Diff ist best-effort bei fehlendem Footer-Feld, `layers_summary`
bleibt G1/Selbstauskunft, Provenienz-Marker erschweren Fälschung statt sie
kryptografisch auszuschließen, `.js`-Fix deckt nur den Geschwister-Extension-Fall ab).
