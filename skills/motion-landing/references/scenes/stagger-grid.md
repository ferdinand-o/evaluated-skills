# Stagger-Grid — Karten/Kacheln erscheinen versetzt

**Die Demo für diesen Szenen-Typ fehlt noch.** `assets/scenes/` enthält nur
Demos für `hero-reveal`, `scroll-telling`, `sticky-pin` und `canvas-moment`
(Entscheidung im Auftrag: vier real getestete Demos statt sieben halb
geprüfte). Wer eine `stagger-grid`-Szene braucht, baut sie von Hand nach
diesem Rezept — ohne die Absicherung durch einen bereits gelaufenen
`verify.py`-Durchlauf gegen diese konkrete Demo.

## Mechanik

Ein Grid aus Karten (Features, Team, Preise) blendet nicht gleichzeitig
ein, sondern nacheinander mit kurzem Versatz pro Karte — ähnlich wie
Hero-Reveal, aber scrollgetrieben statt ladezeitgetrieben.

- **Technik:** `animation-timeline: view()` je Karte, mit einem
  `animation-delay`, der aus der Grid-Position berechnet wird (z. B. über
  eine CSS-Custom-Property `--index`, gesetzt via `style` je Karte).
- Animiert werden `opacity` und `transform` (leichtes `translateY`).
- Feature-Detection wie bei allen scrollgetriebenen Szenen:
  `CSS.supports('animation-timeline: view()')`.

## Parameter

- Versatz pro Karte: kurz genug, dass das Grid nicht wie eine Warteschlange
  wirkt, spürbar genug, dass der Staffelungs-Effekt überhaupt auffällt.
- Reihenfolge: meist Lesereihenfolge (links-oben nach rechts-unten), kann
  aber der Dramaturgie folgen, wenn eine Karte besonders betont werden
  soll.

## Fallstricke

- **CLS durch nicht reservierten Platz.** Jede Karte braucht ihre
  Grid-Zelle von Anfang an — animiert wird nur `opacity`/`transform`
  innerhalb der bereits reservierten Fläche, nie die Grid-Struktur selbst.
- **Zu viele Karten mit zu langem Versatz.** Bei zwölf Karten und 150 ms
  Versatz dauert das komplette Einblenden fast zwei Sekunden — der Nutzer
  scrollt in der Zeit oft schon weiter. Versatz an die Kartenzahl anpassen,
  nicht fix lassen.

## reduced-motion

Alle Karten stehen sofort sichtbar im Grid, kein Versatz, kein
Transform-Ausgangszustand.
