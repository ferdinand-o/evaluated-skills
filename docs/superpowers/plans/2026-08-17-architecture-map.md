# architecture-map Implementation Plan

**Goal:** Eine Skill, die Architektur-Landkarten (Kontext/Module/Klassen, C4-angelehnt)
aus statisch extrahierten Import-/Vererbungsgraphen generiert — nie aus einer Stichprobe
geraten. Committed als `ARCHITECTURE.md` pro Service mit generiertem, deterministisch
sortiertem Mermaid, plus einem Drift-Check, der Abweichungen zwischen Doku-Stand und
aktuellem Code meldet, ohne selbst zu schreiben.

**Spec:** `specs/Spec 10 – architecture-map.md`, `specs/Spec 00 – skill-foundation.md`
(Artefakt-/Eval-Vertrag), verbindliche Vorab-Entscheidungen aus `rulings-final-four.md`
(Abschnitt „Für alle vier" + „Spec 10").

## Abweichungen von der Spec-Textfassung (durch Rulings vorgegeben)

- **C1 — `extract_py.py` ist Tier 1, nicht Tier 2.** Spec 10s Skript-Tabelle nennt
  pyreverse/pydeps; beide sind in dieser Umgebung nicht installiert (A1) und für einen
  reinen Import-Graphen auch nicht nötig — `ast` aus der Stdlib liest Import-Knoten
  direkt. Kein Fremdcode wird importiert (A3), nur geparst.
- **C2 — `extract_ts.py` wird als Tier-1-Textsuche gebaut, nicht als Tier-3-ts-morph-
  Skript.** ts-morph/`npx` sind nicht installiert und nicht zu installieren (A1). Die
  Alternative aus der Spec wird gezogen: Regex-Suche nach `import`/`require`/
  `export ... from`. Das ist **ungenauer als ein echter Parser** — keine
  Typ-Auflösung, keine tsconfig-Pfad-Aliase, anfällig für Treffer in Strings/Kommentaren,
  keine Klassenebene für TypeScript in v1. Das wird in SKILL.md und im Bericht explizit
  benannt, nicht stillschweigend als „erprobt" verkauft (A1).
- **C3 — `ARCHITECTURE.md` liegt pro Service, nicht einmal pro Repo.** Ein Service ist,
  was einen eigenen Einstiegspunkt hat; `--root` an den Extraktions-Skripten bestimmt die
  Grenze, `ARCHITECTURE.md` landet im jeweiligen Service-Verzeichnis.
- **C4 — Mermaid wird immer generiert, nie von Hand editiert; deterministisch sortiert**
  (Knoten nach `id`, Kanten nach `(from, to)`), sonst rauscht jeder Diff.
- **A2 — `layers.yaml` aus der Spec-Textfassung wird `layers.json`.** Die Stdlib kennt
  kein YAML; `analyze_graph.py` liest diese Datei direkt.
- **A6 — Eval-Vertrag folgt der bereits gebauten Harness** (`evalkit/`, Schema aus
  `evalkit/schema.py`), nicht der Skizze `evals/evals.json` in Spec 10s Baumdiagramm.
  Reale Ablage: `evals/architecture-map/evals.json` + `evals/fixtures/<name>/`, analog zu
  `evals/dev-report/`. Jede Assertion hängt an einem Artefakt, das nur diese Skill
  erzeugt (`ARCHITECTURE.md`, Graph-JSON, Mermaid-Header).

`brief-common.md` war unter dem genannten Scratchpad-Pfad nicht auffindbar (nur
`rulings-final-four.md` existierte). Als Fundament-Contract dient stattdessen
`specs/Spec 00 – skill-foundation.md` direkt, plus das bereits gebaute Referenzbeispiel
`skills/dev-report/` (Kopfzeilen-Format, `.skills/cache/`-Konvention, Eval-Harness-Nutzung).

## Architecture

**Drei Skript-Phasen, streng getrennt, dazwischen liest/schreibt Claude nie den Graphen
selbst um:**

1. **Extraktion** (`extract_py.py`, `extract_ts.py`, beide Tier 1) — Quellcode → Graph-JSON
   nach `.skills/cache/architecture-map/<service>-<level>.json` (Ephemera, gitignored).
2. **Analyse** (`analyze_graph.py`, Tier 1) — Graph-JSON (+ optional `layers.json`) →
   Befund-JSON: Zyklen, Fan-in/Fan-out-Ausreißer, Schichtverletzungen, tote Module.
   Alles deterministisch aus dem Graphen ableitbar, kein LLM-Urteil an dieser Stelle.
3. **Rendering** (`to_mermaid.py`, Tier 1) — Graph-JSON → Mermaid-Textblock, sortiert,
   mit Erzeugungskommando im `%%`-Kommentar-Header. Claude übernimmt den Block
   unverändert in `ARCHITECTURE.md` und schreibt Narration/Befund-Einschätzung drumherum.
4. **Drift-Check** (`drift_check.py`, Tier 1) — regeneriert Graphen frisch, vergleicht
   Hash gegen den in `ARCHITECTURE.md` abgelegten Footer-Block; bei Abweichung parst es
   die vorhandenen Mermaid-Blöcke zurück in Knoten/Kanten (da `to_mermaid.py`s Format
   deterministisch und verlustfrei für Knoten-IDs/Kanten ist) und diffed gegen den
   frischen Graphen. Meldet nur, schreibt nie (Bootstrap-/Degradations-Regel).

**Graph-JSON-Schema (Version 1)**, gemeinsam für beide Sprachen:

```json
{
  "_meta": {"skill": "architecture-map", "schema": 1, "generated": "<vollständiges Kommando>"},
  "language": "python|typescript",
  "level": "module|class",
  "root": "<relativer Service-Pfad>",
  "nodes": [{"id": "...", "path": "...", "kind": "module|class"}],
  "edges": [{"from": "...", "to": "...", "kind": "import|inherits"}],
  "external": ["..."]
}
```

Modul-IDs: Dateipfad relativ zu `--root`, `/`→`.`, `.py`/`.ts` gestrippt, `__init__`
entfernt (Python) bzw. `index` entfernt (TS). Klassen-IDs: `<modul_id>.<Klassenname>`.

## Global Constraints

- Tier 1 für alle fünf Skripte (Rulings C1/C2 + A1). Kein Skript importiert fremden
  Code — nur `ast.parse`/Text (A3).
- Konfiguration (`layers.json`) ist JSON (A2), liegt unter `.skills/architecture-map/`
  (Konfigurationsklasse, Spec 00 §1) und wird nicht ungefragt angelegt — fehlt sie, läuft
  die Layer-Prüfung sichtbar „ungeprüft (keine layers.json)", nicht stillschweigend leer
  (A4).
- Null Kanten/Knoten aus einer nicht-leeren Eingabe ist ein Befund, kein stiller Erfolg
  (A4) — `extract_py.py`/`extract_ts.py` melden das über den Exit-Code und eine Zeile auf
  stderr.
- `ARCHITECTURE.md` ist Wissen (Spec 00 §1: committed), Graph-JSON ist Ephemera
  (gitignored), `layers.json` ist Konfiguration (committed, nutzergepflegt).
- Frontmatter: nur `name`/`description`. SKILL.md ≤ 150 Zeilen.
- Dokumentsprache Deutsch, Bezeichner in Code/JSON Englisch.
- Bestehende 146 Tests bleiben grün; neue Tests folgen dem `tests/conftest.py::load_script`-
  Muster aus `dev-report`.

---

## Task 1: `extract_py.py` — Python-Import-Graph via `ast`

**Files:** Create `skills/architecture-map/scripts/extract_py.py`,
`tests/test_architecture_map_extract_py.py`

**Interfaces:**
- `discover_modules(root: Path) -> dict[str, Path]` — Modul-ID → Dateipfad, `.py`-Dateien
  unter `root`, `.git`/`__pycache__`/`node_modules`/venv-Ordner ausgeschlossen.
- `module_id_for(path: Path, root: Path) -> str`
- `extract_imports(path: Path) -> list[tuple[str, int]]` — `(dotted_name, relative_level)`
  je `Import`/`ImportFrom`-Knoten, per `ast.walk` (auch verschachtelt in Funktionen/
  Klassen — Abhängigkeit ist eine Abhängigkeit unabhängig von der Verschachtelung).
- `resolve_import(importer_id: str, dotted_name: str, level: int, known: dict[str, Path]) -> str | None`
  — internes Zielmodul oder `None` (extern). Löst absolute und relative Imports auf, mit
  Präfix-Rückfall (`from a.b import c` zeigt auf `a.b`, wenn `a.b.c` keine Datei ist).
- `build_module_graph(root: Path) -> dict` — vollständiges Graph-JSON, `level: "module"`.
- `extract_classes(paths: list[Path], root: Path) -> dict` — Graph-JSON `level: "class"`,
  Knoten = `ast.ClassDef`, Kanten = Basisklassen (`kind: "inherits"`), nur für die
  übergebenen Dateien (Hotspot-Beschränkung aus der Spec, keine Vollgraph-Klassenebene).
- CLI: `--root PATH [--level module|class] [--files ...] --out PATH`.
- Exit-Code 2 + stderr-Zeile, wenn `discover_modules` nicht-leer ist, aber 0 Kanten
  entstehen (A4 — kein stiller Erfolg für „nichts gefunden").

**Test-Fälle (mindestens):** einfache Kette A→B→C; Zyklus A→B→A; relativer Import
(`from . import x`, `from ..pkg import y`); `from pkg import missing_submodule` fällt auf
Paket zurück; externe Imports (`os`, `numpy`) landen in `external`, nicht in `edges`;
verschachtelter Import in einer Funktion wird gefunden; Klassenebene mit Einfach- und
Mehrfachvererbung; leeres Verzeichnis → Exit 0 mit leerem Graphen (kein Fehlerfall, A4
gilt für nicht-leere Eingabe mit Null-Ergebnis, nicht für eine leere Eingabe selbst).

- [ ] Implementieren, Tests grün, committen: `feat(architecture-map): extract_py.py liest Python-Import- und Klassengraphen`

---

## Task 2: `extract_ts.py` — TS/JS-Import-Graph via Textsuche (Tier 1, dokumentiert ungenau)

**Files:** Create `skills/architecture-map/scripts/extract_ts.py`,
`tests/test_architecture_map_extract_ts.py`

**Interfaces:**
- `discover_modules(root: Path) -> dict[str, Path]` — `.ts`/`.tsx`/`.js`/`.jsx`,
  `node_modules`/`.git`/`dist`/`build` ausgeschlossen.
- `extract_specifiers(text: str) -> list[str]` — Regex für
  `import ... from '...'`, `export ... from '...'`, `require('...')`,
  `import('...')` (dynamisch); Kommentarzeilen (`//`, `/* */`) werden vorher entfernt,
  um die dokumentierte Haupt-Fehlerquelle (Treffer in Kommentaren) zu senken — String-
  Treffer außerhalb echter Imports bleiben eine bekannte Grenze (SKILL.md nennt sie).
- `resolve_specifier(importer_path: Path, specifier: str, known: dict[str, Path]) -> str | None`
  — nur relative Pfade (`./`, `../`) werden aufgelöst, Paket-Imports sind extern.
- `build_module_graph(root: Path) -> dict`.
- Gleiche CLI-Form wie `extract_py.py`, ohne `--level class` (TS-Klassenebene ist Out of
  Scope für v1, in SKILL.md benannt).

**Test-Fälle:** relativer Import ohne/mit Extension, `index`-Auflösung
(`./util` → `util/index.ts`), `require()`, dynamisches `import()`, Paket-Import bleibt
extern, Kommentar mit `import`-Wortlaut erzeugt keine Kante.

- [ ] Implementieren, Tests grün, committen: `feat(architecture-map): extract_ts.py als Tier-1-Textsuche, Ungenauigkeit dokumentiert`

---

## Task 3: `to_mermaid.py` — deterministisches Rendering (+ Rückparser für Task 5)

**Files:** Create `skills/architecture-map/scripts/to_mermaid.py`,
`tests/test_architecture_map_to_mermaid.py`

**Interfaces:**
- `sanitize_id(node_id: str) -> str` — Mermaid-taugliche ID (`[^A-Za-z0-9_]` → `_`,
  Kollisionen werden durch Suffix `__2` etc. aufgelöst, deterministisch nach
  sortierter Eingabereihenfolge).
- `render(graph: dict) -> str` — vollständiger ` ```mermaid ` -Block: `%%`-Header-
  Kommentar mit `_meta.generated`, `flowchart LR`, Knoten sortiert nach `id`
  (`sane_id["<original id>"]`), Kanten sortiert nach `(from, to)`
  (`sane_from --> sane_to`). Zwei Läufe über denselben Graphen erzeugen exakt denselben
  Text (Property-Test: Eingabe-Knotenreihenfolge permutiert, Ausgabe identisch).
- `parse(mermaid_text: str) -> tuple[set[str], set[tuple[str, str]]]` — liest das eigene
  Format zurück (sanitierte ID + Original-Label aus `[...]`, Kanten aus `-->`), genutzt
  von `drift_check.py`, um den zuletzt committeten Graphen ohne Zusatzspeicher
  zurückzugewinnen.

**Test-Fälle:** leerer Graph → gültiger, leerer Block; zwei Knoten mit kollidierenden
sanitierten IDs bekommen unterscheidbare IDs; Determinismus-Test (Permutation der
Eingabe-Listen ändert die Ausgabe nicht); `render` → `parse` liefert dieselben
Original-IDs und Kanten zurück (Rundreise-Test).

- [ ] Implementieren, Tests grün, committen: `feat(architecture-map): to_mermaid.py rendert deterministisch und ist rückparsbar`

---

## Task 4: `analyze_graph.py` — Zyklen, Ausreißer, Schichtverletzungen, tote Module

**Files:** Create `skills/architecture-map/scripts/analyze_graph.py`,
`tests/test_architecture_map_analyze_graph.py`

**Interfaces:**
- `find_cycles(graph: dict) -> list[list[str]]` — starke Zusammenhangskomponenten
  (Tarjan, reine Stdlib), nur Komponenten mit ≥2 Knoten oder Selbstkante, Ergebnis
  sortiert (kleinster Knoten pro Zyklus zuerst, Zyklen lexikografisch sortiert).
- `fan_in_out(graph: dict) -> dict[str, dict]` — je Knoten `{"in": n, "out": n}`.
- `find_outliers(graph: dict, layers_cfg: dict | None) -> list[dict]` — Schwellenwerte
  aus `layers_cfg.get("thresholds", {"fan_in": 10, "fan_out": 10})` (Default, falls keine
  Konfiguration vorhanden — degradiert sichtbar, siehe unten).
- `find_layer_violations(graph: dict, layers_cfg: dict) -> list[dict]` — `layers_cfg`
  bildet Pfadpräfix → Schicht-Index über `"order"`, **von innen nach außen** sortiert
  (z. B. `"order": ["domain", "application", "infrastructure"]`, Index 0 = innerste
  Schicht). Erlaubt ist nur eine Kante von einer äußeren zu einer inneren oder
  gleichen Schicht (höherer oder gleicher Index → niedrigerer Index); eine Kante, die
  nach außen zeigt (niedrigerer Index → höherer Index, z. B. `domain` importiert aus
  `infrastructure`), ist die gemeldete Schichtverletzung — das ist die konventionelle
  Dependency Rule, nicht willkürlich gewählt.
- `find_dead_modules(graph: dict, entry_patterns: list[str]) -> list[str]` — Fan-in 0 und
  kein Treffer gegen `entry_patterns` (Default `["__main__", "main", "cli"]`).
- `analyze(graph: dict, layers_cfg: dict | None) -> dict` — Befund-JSON:
  `{"_meta": ..., "cycles": [...], "outliers": [...], "layer_violations": [...] | None,
  "dead_modules": [...], "layers_config_status": "used"|"missing"}`. Fehlt `layers_cfg`,
  ist `layer_violations` `null` (nicht `[]` — A4: „nicht geprüft" ist kein „sauber") und
  `layers_config_status` ist `"missing"`.

**Test-Fälle:** Zwei-Knoten-Zyklus wird gefunden, Nicht-Zyklus nicht; Selbstkante zählt
als Zyklus; Fan-in-Ausreißer über Schwelle wird gemeldet, darunter nicht; Schicht-
verletzung (Kante von `infrastructure` zurück zu `domain`) wird erkannt, erlaubte
Richtung nicht; fehlende `layers_cfg` → `layer_violations is None`, nicht `[]`; totes
Modul ohne Fan-in und ohne Entry-Pattern wird gemeldet, `__main__`-Modul trotz Fan-in 0
nicht.

- [ ] Implementieren, Tests grün, committen: `feat(architecture-map): analyze_graph.py findet Zyklen, Ausreißer, Schichtverletzungen, tote Module`

---

## Task 5: `drift_check.py` — Graphen neu generieren, mit `ARCHITECTURE.md` diffen

**Files:** Create `skills/architecture-map/scripts/drift_check.py`,
`tests/test_architecture_map_drift_check.py`

**Interfaces:**
- `graph_hash(graph: dict) -> str` — sha256 über kanonisiertes JSON (Knoten/Kanten
  vorsortiert wie in `to_mermaid.py`, `_meta` ausgenommen — sonst ändert sich der Hash
  bei jedem Lauf allein durch den Zeitstempel im Kommando).
- `read_footer(architecture_md_text: str) -> dict | None` — liest den
  `<!-- architecture-map:graph-hashes ... -->`-Block (JSON darin), `None` wenn keiner da
  ist.
- `read_mermaid_blocks(architecture_md_text: str) -> dict[str, str]` — Level →
  Mermaid-Quelltext, aus ` ```mermaid `-Fences mit passendem `%%`-Header.
- `diff_graph(old: tuple[set, set], new_graph: dict) -> dict` — `{"nodes_added": [...],
  "nodes_removed": [...], "edges_added": [...], "edges_removed": [...]}`, alle Listen
  sortiert.
- `check(architecture_md_path: Path, extractor_cmd: list[str]) -> dict` — Kommando aus
  dem Footer erneut ausführen (`subprocess`, dasselbe Skript wie beim ursprünglichen
  Lauf), Hash vergleichen; bei Abweichung `read_mermaid_blocks` + `to_mermaid.parse` auf
  den alten Text anwenden und gegen den frischen Graphen diffen.
- CLI: `--doc PATH`, Exit 0 = kein Drift, Exit 1 = Drift gefunden (Meldung auf stdout,
  **kein Schreibzugriff** — Bootstrap-/Degradations-Regel, Spec 10 §Drift-Check).

**Test-Fälle:** kein Drift (Hash gleich) → Exit 0, keine Diff-Berechnung nötig (Kurzschluss
getestet via Spy/Zähler); Knoten hinzugefügt wird als `nodes_added` gemeldet; Kante
entfernt wird als `edges_removed` gemeldet; fehlender Footer-Block → klare Fehlermeldung,
kein Rateversuch; Aufruf verändert `ARCHITECTURE.md` nachweislich nicht (Datei-Hash vor/
nach Lauf identisch).

- [ ] Implementieren, Tests grün, committen: `feat(architecture-map): drift_check.py meldet Graph-Abweichungen, schreibt nie`

---

## Task 6: SKILL.md + references (`c4-levels.md`, `findings.md`, `narration.md`)

**Files:** Create `skills/architecture-map/SKILL.md`,
`skills/architecture-map/references/c4-levels.md`,
`skills/architecture-map/references/findings.md`,
`skills/architecture-map/references/narration.md`

**Inhalt (keine Code-Schnittstelle, Vertrag für Evals in Task 7):**
- SKILL.md: Frontmatter (`name`, `description` mit Trigger-Stichworten „erkläre/
  dokumentiere die Architektur", „Klassenstruktur", „Abhängigkeiten", „Zyklen finden" und
  Abgrenzung gegen Refactoring-Ausführung → `superpowers:writing-plans`), die Doktrin
  „Skripte extrahieren, Claude erzählt/bewertet", Workflow (Extraktion → `layers.json`
  erfragen/ableiten → Analyse → Narration+Befund-Einschätzung → `ARCHITECTURE.md`
  schreiben), Contract-Absatz (jedes Diagramm generiert mit Kommando-Header; jede
  Struktur-Behauptung graph-belegt; ergänzte Befunde als „Beobachtung (nicht
  graph-belegt)" markiert; ein Service = ein `ARCHITECTURE.md`), Anti-Rationalisierungs-
  Tabelle aus der Spec, Abgrenzung (dependency-cruiser/pyreverse nicht installiert →
  Tier-1-Wahl benennen).
- `c4-levels.md`: die drei Ebenen, was auf welche gehört, warum Klassenebene nur
  Hotspots bekommt.
- `findings.md`: Befund-Katalog (Zyklus, God-Class per Fan-in/out-Schwelle, Schicht-
  verletzung, totes Modul) — Erkennungsregel (Verweis auf `analyze_graph.py`-Funktion)
  + Schweregrad-Leitfaden + Hinweis „nicht jeder Zyklus ist ein Notfall, aber jeder
  bekommt eine Einschätzung".
- `narration.md`: wie man Schichten benennt, Einstiegspfade für Neue beschreibt, den
  Unterschied zwischen Fakt (graph-belegt) und Einschätzung markiert.

- [ ] Schreiben, Zeilenzahl/Frontmatter prüfen (`wc -l`, `head`), committen:
  `feat(architecture-map): SKILL.md, C4-Ebenen, Befund-Katalog, Narrations-Leitfaden`

---

## Task 7: Fixtures + Evals (schreiben, nicht ausführen)

**Files:** Create `evals/fixtures/cyclic-imports/` (Python-Paket mit Zyklus außerhalb
einer plausiblen Lese-Stichprobe — Spec 10s erster Eval verlangt genau das), Create
`evals/fixtures/layered-service/` (drei Schichten, eine bewusste Verletzung, ein totes
Modul), Create `evals/architecture-map/evals.json`

**Fixture-Design:**
- `cyclic-imports`: `git: true`, kleines Python-Paket, Zyklus zwischen einem tief
  verschachtelten Modul (`src/infra/db/session.py`) und einem weit entfernten
  (`src/domain/models/user.py`) — kein Reviewer läse beide zufällig zusammen.
- `layered-service`: drei Verzeichnisse (`domain/`, `application/`, `infrastructure/`),
  eine Datei in `domain/` importiert aus `infrastructure/` (Verletzung der üblichen
  Richtung), ein Modul ganz ohne Importeure (totes Modul), passende `layers.json`
  mitgeliefert.

**Evals (Anti-Zeremonie-Pflicht nach A6 + Spec 00 §2):**
1. `contract`, Fixture `cyclic-imports`: Graph-JSON + `ARCHITECTURE.md` entstehen,
   Zyklus erscheint im Befund-Abschnitt (Regex auf beide beteiligten Modulnamen).
2. `contract`, Fixture `layered-service`: drei getrennte Diagramm-Abschnitte
   (Kontext/Module/Klassen-Überschriften) statt eines Monolithen — Anti-Zeremonie-Eval:
   ein kleines Repo darf kein aufgeblähtes Klassendiagramm der ganzen Codebase bekommen.
3. `contract`, Fixture `layered-service`: die Schichtverletzung erscheint benannt.
4. `behavior`, Fixture `layered-service`: Judge prüft, ob eine im Prompt vorgeschlagene,
   graph-unbelegte Struktur-Behauptung entweder fehlt oder als „Beobachtung (nicht
   graph-belegt)" markiert ist — Contract 44 aus Spec 10 Eval 4.
5. `contract`, Fixture `cyclic-imports`, zweiter Lauf nach `drift_check.py`: unveränderter
   Code → Exit 0 ohne Änderung an `ARCHITECTURE.md` (`file_unchanged`).

Jede `must`-Assertion hängt an `ARCHITECTURE.md`, dem Graph-JSON-Pfad oder dem
Mermaid-Header — Artefakte, die ausschließlich diese Skill erzeugt (A6).

- [ ] Fixtures + `evals.json` schreiben, mit `evalkit.schema.load_evals` lokal gegen
  Schema-Fehler prüfen (nur Laden, **nicht** den vollen Eval-Lauf — der bräuchte
  API-Zugriff und ist nicht Teil dieses Auftrags), committen:
  `test(architecture-map): Fixtures und Evals für Zyklus-, Schicht- und Anti-Zeremonie-Fall`

---

## Task 8: Vollständiger Testlauf + Bericht

- [ ] `python3 -m pytest -q` — alle bisherigen 146 plus neue Tests grün.
- [ ] `docs/superpowers/reports/architecture-map-report.md` schreiben: was gebaut wurde,
  die vier dokumentierten Abweichungen (C1–C4/A2) mit Begründung, offene Sorgen
  (insbesondere: `extract_ts.py`s Textsuche-Grenzen, `layers.json` fehlt standardmäßig,
  Klassenebene nur für explizit gewählte Dateien).
- [ ] Committen: `docs(architecture-map): Implementierungsbericht`
