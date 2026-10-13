# Die drei Ebenen: was auf welche gehört

C4-angelehnt, aber vereinfacht auf das, was aus einem Import-/Vererbungsgraphen
tatsächlich ableitbar ist. Jede Ebene ist ein eigener Abschnitt in `ARCHITECTURE.md`
mit einem eigenen generierten Diagramm — nie zu einem Bild zusammengelegt.

## 1 · Kontext

Was das System ist, externe Abhängigkeiten, Einstiegspunkte. Quelle: `external` aus dem
Graph-JSON (Top-Level-Pakete, die importiert, aber nicht selbst extrahiert wurden) plus
die von `find_dead_modules`/Entry-Pattern-Liste erkannten Einstiegspunkte. Diese Ebene
bekommt kein eigenes Mermaid-Flowchart, sondern eine kurze Aufzählung — ein Diagramm für
drei bis zehn externe Pakete wäre Ballast, keine Klärung.

## 2 · Module

Der vollständige Paket-/Verzeichnisgraph unter dem gewählten `--root`, mit
Abhängigkeitsrichtung und benannten Schichten (falls `layers.json` vorhanden). Das ist
der Hauptgraph: `extract_py.py`/`extract_ts.py --level module` → `to_mermaid.py` →
Mermaid-Flowchart. Narration hier: Verantwortlichkeiten je Schicht/Verzeichnis, warum
die Struktur so aussieht, Einstiegspfade für Neue ("wenn du X ändern willst, fang bei Y
an").

## 3 · Klassen

**Nur für vom Nutzer gewählte Hotspot-Module**, nie für die ganze Codebase — ein
Vollgraph auf Klassenebene ist unlesbar, das ist laut Spec 10 der Hauptgrund, warum
Architektur-Diagramme in der Praxis scheitern. Ein Hotspot ist typischerweise: ein
Modul mit vielen Klassen, ein Modul mit einem gemeldeten Fan-in-/Fan-out-Ausreißer, oder
ein Modul, das der Nutzer explizit nennt ("erklär mir die Vererbung in `models/`").

`extract_py.py --level class --files <hotspot-dateien>` liefert Klassenknoten und
Vererbungskanten (nur Basisklassen innerhalb derselben Dateimenge — externe Basen wie
`Exception` bleiben unverknüpft, siehe Modul-Docstring). TypeScript hat in v1 keine
Klassenebene (Out of scope, siehe SKILL.md).

## Warum die Trennung strikt ist

Ein Diagramm, das Kontext, Module und Klassen mischt, beantwortet keine der drei
Fragen gut: zu grob für "wie hängen diese fünf Klassen zusammen", zu detailliert für
"was ist das System". Drei Diagramme mit klarer Frage pro Diagramm schlagen ein
Monster-Diagramm — das ist Spec 10s zweiter Eval.
