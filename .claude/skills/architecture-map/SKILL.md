---
name: architecture-map
description: Use when the user wants an architecture overview, diagram, or documentation of a codebase's structure — "erklär mir die Architektur", "dokumentiere die Architektur", "zeig mir die Abhängigkeiten", "wo sind die Zyklen", "Klassenstruktur von X", or when ARCHITECTURE.md exists and might be stale ("ist die Doku noch aktuell?"). Generates import/inheritance graphs statically (ast for Python, text search for TS/JS) into a committed, deterministic ARCHITECTURE.md with a drift check — never a hand-drawn or guessed diagram. Not for executing refactors the findings suggest (use work-plan) and not for runtime/sequence diagrams (out of scope).
---

# architecture-map — generierte Architektur-Landkarten

**Skripte extrahieren die Wahrheit, du erzählst und bewertest sie.** Du zeichnest nie
selbst einen Graphen und behauptest nie eine Beziehung, die nicht im extrahierten
Graph-JSON steht.

## Die eiserne Regel

```
KEIN DIAGRAMM OHNE ERZEUGUNGSKOMMANDO IM HEADER. KEINE STRUKTUR-BEHAUPTUNG OHNE GRAPH-BELEG.
```

Ein handgezeichnetes oder von Hand nachbearbeitetes Mermaid ohne Kommando-Header ist ein
Regelverstoß, kein Stilmittel.

## Ablauf

1. **Service-Grenze bestimmen.** Ein Service ist, was einen eigenen Einstiegspunkt hat.
   Im Monorepo: ein `ARCHITECTURE.md` je Service-Verzeichnis, nie eines fürs ganze Repo.
2. **Extrahieren** (Tier 1, nur Stdlib):
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/extract_py.py" --root <service> \
     --out .skills/cache/architecture-map/<service>-module.json
   python "${CLAUDE_SKILL_DIR}/scripts/extract_ts.py" --root <service> \
     --out .skills/cache/architecture-map/<service>-module-ts.json
   ```
   `extract_ts.py` ist eine **Textsuche, kein echter Parser** — ts-morph/`npx` sind in
   dieser Umgebung nicht installiert (Ruling C2). Sag das im Dokument, wenn TS/JS
   analysiert wurde: keine Typauflösung, keine tsconfig-Pfad-Aliase, String-/
   Kommentar-Rauschen als bekannte Fehlerquelle.
3. **Layers erfragen oder ableiten.** `.skills/architecture-map/layers.json` (Format
   siehe unten) steuert Schichtverletzungen und Ausreißer-Schwellen. Fehlt sie, frag
   einmal nach oder biete an, sie aus der Verzeichnisstruktur abzuleiten — leg sie nie
   ungefragt an (Bootstrap-Regel, Spec 00 §1). Ohne sie läuft die Analyse trotzdem,
   meldet aber `layer_violations: null` — das heißt „ungeprüft", nicht „sauber".
   `analyze_graph.py`s Befund-JSON trägt dafür `layers_summary`, einen fertigen Satz
   ("ungeprüft (keine layers.json gefunden)" / "geprüft: keine Schichtverletzungen
   gefunden" / "geprüft: N Schichtverletzung(en) gefunden") — **übernimm ihn wörtlich**
   in die Befunde-Sektion, statt selbst zu formulieren. Das ist der Unterschied
   zwischen „niemand hat hingesehen" und „geprüft, für gesund befunden".
4. **Analysieren:**
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/analyze_graph.py" \
     --graph .skills/cache/architecture-map/<service>-module.json \
     --layers .skills/architecture-map/layers.json \
     --out .skills/cache/architecture-map/<service>-findings.json
   ```
5. **Hotspots für die Klassenebene wählen** (aus Ausreißern oder Nutzerwunsch, nie die
   ganze Codebase):
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/extract_py.py" --root <service> \
     --level class --files pfad/a.py pfad/b.py \
     --out .skills/cache/architecture-map/<service>-classes.json
   ```
6. **Mermaid rendern**, unverändert übernehmen:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/to_mermaid.py" \
     --graph .skills/cache/architecture-map/<service>-module.json
   ```
7. **`ARCHITECTURE.md` schreiben:** drei getrennte Abschnitte (Kontext/Module/Klassen,
   siehe `references/c4-levels.md`), Narration nach `references/narration.md`, Befunde
   nach `references/finding-catalog.md` mit Einschätzung je Befund (die
   Schichtverletzungs-Zeile ist `layers_summary` wörtlich, siehe Schritt 3), und am Ende
   ein Footer-Block, den `drift_check.py` später liest — `external` gehört mit rein,
   sonst bleibt eine geänderte externe Abhängigkeit für den Drift-Check unsichtbar:
   ```
   <!-- architecture-map:graph-hashes
   {"module": {"command": "<_meta.generated aus dem Graph-JSON>", "graph_hash": "<via --graph berechnet>", "external": ["<external aus dem Graph-JSON>"]}}
   -->
   ```
   Hash je Ebene: `python "${CLAUDE_SKILL_DIR}/scripts/drift_check.py" --graph <graph.json>`.
8. **Drift-Check** (auf Wunsch oder als CI-Schritt, meldet nur, schreibt nie):
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/drift_check.py" --doc <service>/ARCHITECTURE.md
   ```

## `layers.json`

```json
{
  "order": ["domain", "application", "infrastructure"],
  "layers": {"domain": "domain/", "application": "application/", "infrastructure": "infrastructure/"},
  "thresholds": {"fan_in": 10, "fan_out": 10}
}
```

`order` ist von innen nach außen. Erlaubt: Kanten von außen nach innen oder innerhalb
derselben Schicht. Eine Kante nach außen (`domain` importiert `infrastructure`) ist die
gemeldete Verletzung.

## Contract

- Jedes Diagramm ist generiert, mit Kommando im `%%`-Header — nie von Hand editiert.
- Jede Struktur-Behauptung in der Narration ist im Graph-JSON belegbar; ist sie es
  nicht, steht sie als „Beobachtung (nicht graph-belegt)".
- Jeder Befund stammt aus `analyze_graph.py`. Ergänzte Befunde tragen dieselbe Markierung.
- Ein Service bekommt ein `ARCHITECTURE.md`, nie das ganze Repo eines.
- Nullkanten/-knoten aus einer nicht-leeren Extraktion sind ein Befund (Exit 2), kein
  stiller Erfolg — dann root/files prüfen, nicht weiterschreiben.
- `drift_check.py` schreibt nie auf `ARCHITECTURE.md`. Es meldet Abweichungen; die
  Aktualisierung bleibt ein bewusster, von dir ausgeführter Schritt.
- Klassenebene nur für explizit gewählte Hotspot-Dateien; zwei gleichnamige Klassen
  in verschiedenen Hotspot-Dateien, die als Basis referenziert werden, bricht
  `extract_py.py` hart ab statt eine falsche Kante zu raten.
- Der Footer-Hash geht über `nodes`, `edges` **und** `external` — eine neue oder
  entfernte externe Abhängigkeit ist Drift, auch ohne neue interne Kante.
- Fehlt `layers.json`, steht das als „ungeprüft" (`layers_summary`) im Dokument, nie
  als stillschweigende Leere, die wie „sauber" aussieht.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Ich sehe die Struktur doch beim Lesen" | Eine Stichprobe ist kein Graph. Extrahieren. |
| „Das Klassendiagramm der ganzen App wäre beeindruckend" | Unlesbar ist nicht beeindruckend. Hotspots wählen. |
| „Der Zyklus ist bestimmt Absicht" | Dann als bewusste Ausnahme dokumentieren, mit Begründung — nicht verschweigen. |
| „Diagramm schnell von Hand anpassen" | Dann lügt es ab dem nächsten Commit. Skript anpassen, neu generieren. |
| „pyreverse/dependency-cruiser wären genauer" | Sind hier nicht installiert (Ruling A1/C1/C2). `ast` bzw. Textsuche sind die tatsächlich verfügbare Wahrheit — Grenzen benennen, nicht verschweigen. |
| „Keine layers.json, also gibt's wohl keine Verletzungen" | `null` heißt ungeprüft. Sag das, behaupte nicht „sauber". |

## Abgrenzung

- **work-plan** — Befunde münden in einen Refactoring-Plan, aber diese
  Skill führt keine Refactorings aus.
- Laufzeit-/Sequenzdiagramme, weitere Sprachen als Python/TS/JS, automatischer
  Export nach drawio/PNG: out of scope.
- Diese Skill braucht Lesezugriff auf Quellcode. Kein Fremdcode wird importiert oder
  ausgeführt — nur `ast.parse` bzw. Textsuche.
