# Sticky-Pin — Element bleibt, Inhalt wandert

Demo: `assets/scenes/sticky-pin/vanilla/index.html` (primär),
`assets/scenes/sticky-pin/react/StickyPin.jsx` (React-Adapter). Erklärt die
Mechanik, verweist auf die Demo — kein eingebetteter Code (Sync-Regel).

## Mechanik

Ein Element (Bild, Zahl, Diagramm) bleibt fixiert im Viewport, während
begleitender Text daneben oder darüber vorbeiscrollt.

- **Technik:** `position: sticky` mit einem `top`-Offset — reines CSS, kein
  JavaScript für das Pinning selbst. Das ist der Unterschied zu
  Scroll-Hijacking: Der Nutzer scrollt weiterhin normal, nur ein Element
  hält seine Position innerhalb eines begrenzten Containers.
- Begleitende Textänderungen (welcher Absatz gerade „aktiv" ist) nutzen
  `animation-timeline: view()` auf den Text-Blöcken, um Opacity je nach
  Sichtbarkeit im Viewport zu steuern — dieselbe Feature-Detection wie bei
  `scroll-telling`.
- Der gepinnte Container hat eine definierte Höhe, die die Scroll-Strecke
  bestimmt, über die das Pinning aktiv bleibt.

## Parameter

- Höhe des Containers: bestimmt, wie lange das Element gepinnt bleibt —
  zu kurz wirkt abgehackt, zu lang wirkt wie Hijacking, obwohl technisch
  keins vorliegt.
- `top`-Offset: meist an Header-Höhe oder Viewport-Rand ausgerichtet.

## Fallstricke

- **Sticky ohne begrenzenden Container wirkt wie Hijacking.** Ohne
  definierte Container-Höhe bleibt das Element für die gesamte
  Restseite gepinnt — das fühlt sich an wie Kontrollverlust über den
  Scroll, obwohl technisch reines CSS. Immer einen begrenzten
  Eltern-Container mit fester Höhe verwenden.
- **CLS beim Wechsel von `sticky` zu `static`.** Passiert, wenn der
  Container die Höhe ändert, sobald das Element „loslässt" — die Höhe muss
  vorab feststehen, nicht durch den Animationszustand bestimmt werden.
- **Gepinntes Element überdeckt Text auf kleinen Viewports.** Sticky-Pin
  ist eine Breitbild-Szene; auf schmalen Viewports oft besser als
  gestapeltes, nicht gepinntes Layout — das ist eine Design-Entscheidung
  von `ui-architect`, nicht von dieser Skill.

## reduced-motion

Das Pinning selbst (reines CSS-Layout) bleibt bestehen — `position: sticky`
ist keine Bewegung im Sinne von `prefers-reduced-motion`. Was entfällt, ist
die Opacity-Choreografie der Text-Blöcke: Sie sind bei reduzierter
Bewegung alle direkt sichtbar, kein sequenzielles Ein-/Ausblenden.
