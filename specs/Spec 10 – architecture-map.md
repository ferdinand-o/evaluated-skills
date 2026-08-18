# Spec 10: architecture\-map — Generierte Architektur\-Aufschlüsselung

Skill\-Spezifikation · Zyklus 10/14 · Entscheidung: Verstehen \+ Kritik, committed mit Drift\-Check, Mermaid im Markdown · Abgeglichen mit Spec 00

## Problem

Architektur\-Dokumentation aus LLM\-Hand hat einen Kardinalfehler: Das Modell rät die Struktur aus stichprobenartig gelesenen Dateien statt sie zu parsen — mit erfundenen Klassen und fehlenden Abhängigkeiten in großen Codebasen. Handgezeichnete Diagramme verrotten ab dem ersten Commit; Kontext\-, Modul\- und Klassenebene landen in einem überladenen Bild; und Auffälligkeiten (Zyklen, God\-Classes, Schichtverletzungen) fallen nur auf, wenn sie zufällig im gelesenen Ausschnitt liegen.

## Constraints

Sprachen: Python (pyreverse/pydeps) und TypeScript (ts\-morph/dependency\-cruiser). Zweck ist beides — narrative Landkarte fürs Onboarding *und* Befunde mit Schweregrad. Das Ergebnis lebt als `ARCHITECTURE.md` im Repo und wird per Drift\-Check wahr gehalten. Diagramme ausschließlich als generiertes Mermaid im Markdown (diffbar, GitHub\-/IDE\-renderbar); jedes Diagramm trägt sein Erzeugungskommando im Header\-Kommentar. Portables Frontmatter.

## Approach

**Arbeitsteilung als Doktrin: Skripte extrahieren die Wahrheit, das LLM erzählt und bewertet sie.** Claude zeichnet nie selbst einen Graphen und behauptet nie eine Beziehung, die nicht im extrahierten Graphen steht.

**Skill\-Struktur:**

```
architecture-map/
├── SKILL.md                (Doktrin, Ebenen-Modell, Workflow, Contract)
├── references/
│   ├── narration.md        (wie man Schichten benennt und Verantwortung erklärt)
│   ├── findings.md         (Befund-Katalog: Zyklus, God-Class, Schichtverletzung,
│   │                        tote Module — je mit Erkennungsregel und Schweregrad-Leitfaden)
│   └── c4-levels.md        (die drei Ebenen und was auf welche gehört)
├── scripts/
│   ├── extract_py.py       (Tier 2: pyreverse/pydeps → Graph-JSON in .skills/cache/)
│   ├── extract_ts.py       (Tier 3: ts-morph/dependency-cruiser → dito)
│   ├── to_mermaid.py       (Tier 1; Graph-JSON → Mermaid-Blöcke, deterministisch sortiert)
│   ├── analyze_graph.py    (Zyklen, Fan-in/Fan-out-Ausreißer, Schichtverletzungen
│   │                        gegen deklarierte Schichten → Befund-JSON)
│   └── drift_check.py      (Graphen neu generieren, mit ARCHITECTURE.md-Stand diffen)
└── evals/evals.json
```

**Drei Ebenen (C4\-angelehnt), strikt getrennt:** (1) **Kontext** — was das System ist, externe Abhängigkeiten, Einstiegspunkte; (2) **Module** — Paket\-/Verzeichnisgraph mit Abhängigkeitsrichtung und benannten Schichten; (3) **Klassen** — nur für die vom Nutzer gewählten Hotspot\-Module (nie die ganze Codebase: der Vollgraph auf Klassenebene ist unlesbar und der Hauptgrund, warum Architektur\-Diagramme scheitern). Jede Ebene ist ein eigener Abschnitt mit eigenem generiertem Diagramm.

**Workflow:** Extraktion (Skripte, sprachweise) → deklarierte Schichten erfragen oder aus Verzeichniskonvention ableiten (als `.skills/architecture-map/layers.yaml` abgelegt — Konfigurationsklasse nach Spec 00 und die einzige manuelle Zutat; dort leben auch die Schwellenwerte für die Fan\-in/Fan\-out\-Befunde, denn konfigurierbar gehört in die Konfiguration) → `analyze_graph.py` erzeugt Befunde deterministisch → Claude schreibt: Narration je Ebene (Verantwortlichkeiten, warum die Struktur so aussieht, Einstiegspfade für Neue) und pro Befund eine Einschätzung (real problematisch vs. bewusste Ausnahme — mit Begründung, denn nicht jeder Zyklus ist ein Notfall) → `ARCHITECTURE.md` mit Ebenen\-Sektionen, Befunde\-Sektion mit Schweregrad, Generierungs\-Fußzeile (Datum, Kommandos, Graph\-Hash).

**Drift\-Check:** `drift_check.py` regeneriert die Graphen und vergleicht mit dem im Dokument abgelegten Graph\-Hash: Abweichung → Meldung mit Diff der Kanten/Knoten (was kam hinzu, was verschwand). Läuft skill\-invoked („ist die Doku noch wahr?") und optional als CI\-Schritt. Er **meldet nur und committet nichts von selbst** — die Bootstrap\-Regel aus Spec 00 §1 verbietet ungefragte Schreibzugriffe, und ein Auto\-Commit von Diagrammen wäre genau das. Die Narration wird nur dort aktualisiert, wo der Graph sich geändert hat — kein Volltext\-Rewrite pro Commit.

**Contract:** Jedes Diagramm ist generiert (Kommando im Header — ein handgezeichnetes Mermaid ohne Kommando\-Header ist ein Regelverstoß); jede Struktur\-Behauptung in der Narration muss im Graph\-JSON belegbar sein; jeder Befund stammt aus analyze\_graph.py — das LLM darf Befunde einordnen und ergänzen, aber ergänzte tragen die Markierung „Beobachtung (nicht graph\-belegt)".

**Anti\-Rationalisierungs\-Tabelle (Auszug):** „Ich sehe die Struktur doch beim Lesen" → Stichprobe ist kein Graph; extrahieren. „Das Klassendiagramm der ganzen App wäre beeindruckend" → unlesbar ist nicht beeindruckend; Hotspots wählen. „Der Zyklus ist bestimmt Absicht" → dann als bewusste Ausnahme dokumentieren, nicht verschweigen. „Diagramm schnell von Hand anpassen" → dann lügt es ab dem nächsten Commit; Skript anpassen.

**Evals:** (1) Codebase mit bekanntem Import\-Zyklus außerhalb der gelesenen Stichprobe — findet ihn die Extraktion? (2) Frage „erkläre mir die Architektur" auf großem Repo — entstehen drei getrennte Ebenen statt eines Monster\-Diagramms? (3) Nach einem strukturändernden Commit — meldet drift\_check.py präzise die neuen/entfallenen Kanten? (4) Provozierte Behauptung ohne Graph\-Beleg in der Narration — wird sie als Beobachtung markiert oder als Fakt ausgegeben?

## Alternatives considered

Reines LLM\-Lesen (audit\-context\-building\-Stil) bleibt fürs schnelle Einlesen nützlich, skaliert aber nicht zur wahrheitsfähigen Doku — verworfen als Fundament, erlaubt als Ergänzung für Narration. Interaktives HTML zusätzlich zu Mermaid vertagt (Nutzerentscheidung: Mermaid reicht; nachrüstbar als Renderer über dem Graph\-JSON, ohne Strukturänderung). Nur\-Review\-Variante ohne committete Doku verworfen — der Drift\-Check ist der eigentliche Mehrwert gegenüber allem Existierenden. UML\-Vollständigkeit (Sequenz\-, Zustandsdiagramme) bewusst nicht Ziel: statische Struktur zuerst; Laufzeit\-Sichten wären eine eigene Erweiterung mit anderem Werkzeug (Tracing).

## Out of scope

Laufzeit\-/Sequenzdiagramme, weitere Sprachen (Java/Go — Adapter\-Muster wie Spec 05 möglich), automatische Refactoring\-Durchführung (Befunde können in `superpowers:writing-plans` münden), Metrik\-Dashboards, drawio/PNG\-Export.

## Open questions

Granularität der Modul\-Ebene im Monorepo (pro Package ein eigenes ARCHITECTURE.md vs. eines mit Sub\-Sektionen)? — Spec 07 stellt dieselbe Monorepo\-Frage für die OpenAPI; beide gehören gemeinsam entschieden. Lohnt `extract_ts.py` (Tier 3) in v1 überhaupt, oder trägt eine Python\-only\-Fassung den Beweis billiger?

## Next steps

extract\_py.py \+ to\_mermaid.py zuerst (der deterministische Kern), gegen ein bekanntes Repo verifizieren; analyze\_graph.py mit Zyklen\- und Ausreißer\-Erkennung; c4\-levels.md und findings.md schreiben; drift\_check.py mit Graph\-Hash\-Verfahren; Eval 1 (Zyklus außerhalb der Stichprobe) als ersten Härtetest; Description schärfen (triggert bei „erkläre/dokumentiere die Architektur", „Klassenstruktur", „Abhängigkeiten" — routet Refactoring\-Ausführung aus).
