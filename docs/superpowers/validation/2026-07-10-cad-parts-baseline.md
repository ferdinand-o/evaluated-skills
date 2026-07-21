# cad-parts — RED-Baseline (ohne Skill)

Server-Alias: stl-cad-server-http. Datum: 2026-07-10.
Alle Proben: frische Subagenten (Modell: **sonnet** — GREEN in Task 11 nutzt
dasselbe Modell für fairen Vergleich), nur MCP-Tools + Aufgabentext, kein
Skill-Zugriff. Protokoll je Teil: Anzahl render_model-Aufrufe, Fehlertypen,
gescheiterte Checks je Iteration, wörtliche Zitate charakteristischer
Denkfehler, Endstatus, finaler Code.

Nach Ehrlichkeits-Gate (Teile A–C bestanden ohne räumliche Fehler) wurden mit
Nutzer-Freigabe zwei härtere Proben ergänzt: D (Spec selbst schreiben),
E (Sechskant-Emulation).

## Teil A — Wandhalter

- **Renders:** 2. **Endstatus:** pass (9/9 Checks, V=22785,6, bbox 60×40×60).
- **Fehler:** Iteration 1: `runtime_error` — „name 'Pos' is not defined".
- **Gescheiterte Checks:** keine (einziger Fehlschlag war der Import-Fehler).
- **Zitat (Iteration 1→2):** „Der erste Versuch nutzte `Pos(...)` und
  `box(...)` ohne Imports […] ich habe `from build123d import Pos, Rot` und
  `from cadkit import box, through_hole` ergänzt, da die Sandbox offenbar
  keine impliziten globalen Namen bereitstellt."
- **Räumliches Denken:** fehlerfrei — Zentrierung (`Pos(0, 20, 2)`,
  `Pos(0, 2, 30)`), Überlappung und alle 4 Lochpositionen auf Anhieb korrekt.
- Finaler Code: siehe Benchmark-Fälle (Validierungs-Dokument, Task 11).

## Teil B — Buchse

- **Renders:** 4. **Endstatus:** pass (7/7 Checks).
- **Fehler:** 3× `runtime_error`: „name 'through_hole' is not defined",
  2× „name 'cylinder' is not defined".
- **Gescheiterte Checks:** keine.
- **Zitat (Iteration 1):** „gemäß cadkit://reference sollten
  box/cylinder/through_hole direkt im Namespace verfügbar sein, laut
  Referenz-Dokument ohne Import-Hinweis." — 3 Renders für die
  Import-Diagnose verbrannt, inkl. Minimaltest-Render (Iteration 3) nur zur
  Namespace-Klärung.
- Geometrie (1 Zeile) auf Anhieb korrekt.

## Teil C — Gehäuseschale

- **Renders:** 3. **Endstatus:** pass (6/6 Checks, V=10312,5 exakt).
- **Fehler:** `runtime_error` „name 'box' is not defined", dann
  „name 'Box' is not defined".
- **Gescheiterte Checks:** keine.
- **Räumliches Denken:** fehlerfrei — Kavität mit Bodenoffset `Pos(0,0,2.5)`
  und Überschuss nach +Z korrekt begründet konstruiert.

## Teil D — Flansch-Adapter (Spec selbst schreiben)

- **Renders:** 8 (5 Import-Fehlschläge, 3 ok). **check_model:** 2 (1 fail,
  1 pass). **Endstatus:** pass (11/11) — nach Spec-Korrektur.
- **Fehler:** 5× `runtime_error` (Pos/cylinder/box „is not defined").
- **Gescheiterte Checks (Spec v1):** `hole[1..4]`: expected
  `must_be_through: true`, actual `{"through": false, "length_mm": 5.0}` —
  „Durchgängigkeit stimmt nicht". Die 4 Schraubenbohrungen gehen nur durch
  den 5-mm-Flansch, der Checker misst aber gegen die globale Z-Ausdehnung
  (20 mm).
- **Zitat (Spec-Fix):** „Der Checker definiert must_be_through offenbar als
  ‚Bohrkanal-Länge entspricht der gesamten Bauteilausdehnung entlang der
  Achse' […] nicht ‚geht durch das lokal vorhandene Material'." → Spec v2
  setzte `must_be_through: null` für die Flansch-Bohrungen; Code unverändert.
- **Positiv:** analytisches Volumen selbständig vorgerechnet (17981,65 mm³,
  ±5 % Tesselations-Toleranz, gemessen 17974,2); Wandstärken-Schwelle
  analytisch begründet; Lochkreis via `math.cos/sin` korrekt.

## Teil E — M5-Muttern-Tasche (Sechskant-Emulation)

- **Renders:** 4 (1 Import-Fehler, 1 Namespace-Diagnose, 1 Hauptmodell,
  1 A/B-Kontrolle). **Endstatus:** fail — **verursacht durch einen Fehler in
  der von uns gestellten Spec**, nicht durch den Agenten.
- **Gescheiterter Check:** `hole[0]`: expected `must_be_through: true`,
  actual `{"through": false, "length_mm": 3.5}` — die Tasche (Tiefe 4,5)
  verkürzt die zylindrische Pilotloch-Fläche auf 8−4,5=3,5 mm.
- **A/B-Beweis des Agenten:** identisches Fail auch mit offiziellem
  `cadkit.counterbore_hole` (5,3/8,3/4,5) → **jede gestufte Bohrung
  (Senkung, Tasche) macht must_be_through unerfüllbar**, unabhängig von der
  Konstruktion. Zitat: „Ein ‚pass' auf exakt diese Spec ist mit einer
  physikalisch korrekten Mutternfalle nach meiner Analyse nicht erreichbar."
- **Positiv (stark):** Sechskant-Emulation selbständig gefunden — 3 Slabs
  0°/60°/120°, Schnittmenge via `A − (A − B)`; Volumen 6854,34 im Fenster
  (analytische Vorhersage 6854,3 — Treffer); ehrliches Stoppen statt
  Spec-Gaming.

## Musteranalyse

1. **Imports sind der dominante Fehlermodus (12 verschwendete Renders in 5
   Proben; jede Probe betroffen).** `cadkit://reference` zeigt keine
   Import-Zeilen; alle Agenten nahmen anfangs globale Namen an. Wörtlich:
   „laut Referenz-Dokument ohne Import-Hinweis". → Skill muss die exakte
   Import-Präambel vorgeben.
2. **Spec-Schreiben hat reproduzierbare Fallen:** (a) `must_be_through`
   misst gegen die globale Ausdehnung (D, 4 Checks fail); (b) gestufte
   Bohrungen (Senkung/Tasche) teilen die Zylinderfläche → nie
   `must_be_through` setzen (E, per A/B bewiesen — auch der geplante
   Montageplatten-Rezept-Spec des Plans war davon betroffen und wurde
   korrigiert). → Skill braucht normative Spec-Schreibregeln.
3. **Räumliches Denken war in allen 5 Proben fehlerfrei** (Zentrierung,
   Überlappung, Kavitäten-Offsets, Lochkreis-Trigonometrie, sogar
   Schnittmengen-Emulation). → Der Skill-Schwerpunkt verschiebt sich von
   „räumliches Denken beibringen" zu „Vorhersage-Disziplin absichern +
   API-/Check-Semantik-Wissen bereitstellen"; die Denk-Referenz bleibt als
   Absicherung für komplexere Teile, wird aber nicht als Haupt-Painpoint
   verkauft.
4. **Kein Agent hat vor dem Render eine Volumen-/BBox-Vorhersage
   aufgeschrieben** (nur D rechnete, weil die Aufgabe es verlangte). Bei den
   einfachen Teilen folgenlos; Restrisiko für komplexe Teile bleibt —
   GREEN-Kriterium „Vorhersagetabelle vorhanden" bleibt bestehen.
