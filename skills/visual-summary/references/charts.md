# Charts: wann, welcher Typ, wie erzeugt

Ein Chart in dieser Skill ist ein Beleg, kein Schmuck. Er erscheint nur, wenn er
eine Frage beantwortet, die die Kernthese aufwirft — sonst entfällt der
Chart-Slot ausdrücklich (`references/formats.md`).

## Farbe, Zurückhaltung, Zugänglichkeit

- **Farbe trägt nie allein Bedeutung.** Rauf/runter oder „anders als" braucht
  zusätzlich ein Vorzeichen (`+2,4 %`), einen Pfeil (▲/▼), die Lage zur
  Nulllinie oder eine Linienart (gestrichelt/durchgezogen) — sonst liest
  ein Teil der Leser (etwa jeder zwölfte Mann) es nicht.
- **Wenige Farben.** Für eine Größe von niedrig nach hoch ein Farbton in
  Abstufungen, nie ein Regenbogen; für Kategorien nur so viele Farben, wie man
  im Kopf behält, danach direkt beschriften.
- **Nichts, was keinen Wert lesbar macht:** kein 3D, keine Schatten, Verläufe
  oder Deko-Icons; Gitterlinien nur leise und nur auf der Werteachse; Achsen in
  gedämpfter Textfarbe.
- **Direkt beschriften statt Legende**, wo Platz ist (Linie am Endpunkt, Balken
  an der Spitze).
- **Einheit einmal im Achsentitel**, nicht an jedem Tick.

## Welcher Typ

| Frage | Chart |
| --- | --- |
| Wie verändert sich das über Zeit? | Linie |
| Wie vergleichen sich Kategorien? | Balken |
| Welchen Anteil hat etwas am Ganzen? | Balken zuerst; ein einzelner Anteilswert notfalls als große Zahl, nie als Donut mit mehr als zwei-drei Segmenten |

Das sind die einzigen drei Typen, die diese Skill rendert (These-plus-Beleg
braucht selten mehr). Verlangt das Material einen anderen Typ (Streudiagramm,
Histogramm), ist das ein Signal, dass die Anfrage kein Ad-hoc-Summary mehr ist,
sondern eigenständige Datenanalyse — außerhalb dieser Skill.

## Keine Bibliothek — selbst generiertes Inline-SVG

Charts sind handgebautes `<svg>` direkt im HTML-Template, aus den Datenpunkten
des Inhaltsmodells berechnet (Balkenhöhen/-breiten oder Polyline-Punkte). Kein
Chart-Framework, kein CDN-Import:

- **Selbstenthaltenheit:** Die HTML-Ausgabe muss ohne externen Host funktionieren
  — eine eingebettete Bibliothek bricht unter strengen CSPs und bläht jede
  einzelne, sonst kleine Datei auf.
- Farben kommen aus `tokens.css` (`var(--accent)`, `var(--up)`/`var(--down)` für
  Richtung), nie als literale Hex-Werte im SVG.
- `tabular-nums` für jede gerenderte Zahl im Chart (Achsenticks, Datenlabels).

## Referenzbindung gilt auch für Datenpunkte

Jeder Datenpunkt trägt denselben Locator wie eine Zahl im Fließtext
(`references/evidence.md`). Im HTML steht das als versteckte, für Screenreader
erreichbare Datentabelle neben dem SVG (`<table class="sr-only">`, nie
`display: none`), deren Zeilen dieselben Referenzmarken tragen wie die
Chart-Punkte selbst.

## Markdown bekommt nie ein Bild

Ein Chart im Markdown-Skelett ist immer eine Tabelle der zugrunde liegenden
Datenpunkte mit Referenzmarken — nie ein eingebettetes oder verlinktes Bild.
Ein totes Bild in einem Repo/Notizen-Kontext veraltet unsichtbar und ist ohne
Renderer nicht lesbar; eine Tabelle ist es immer.

## A11y-Fallback

Jedes Chart-SVG trägt ein `aria-label` mit einer knappen Textzusammenfassung
dessen, was es zeigt (z. B. „Balkendiagramm: Kundenbindung nach Quartal,
steigend von 78 % auf 91 %") — der visuelle Plot ist nie die einzige
Repräsentation der Daten.
