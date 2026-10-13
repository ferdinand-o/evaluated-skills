# Marquee — endlos scrollende Logo-/Text-Reihe

**Die Demo für diesen Szenen-Typ fehlt noch.** `assets/scenes/` enthält nur
Demos für `hero-reveal`, `scroll-telling`, `sticky-pin` und `canvas-moment`
(Entscheidung im Auftrag: vier real getestete Demos statt sieben halb
geprüfte). Wer eine `marquee`-Szene braucht, baut sie von Hand nach diesem
Rezept — ohne die Absicherung durch einen bereits gelaufenen `verify.py`-
Durchlauf gegen diese konkrete Demo.

## Mechanik

Eine horizontal endlos laufende Reihe (Logos, Zitate, Keywords), die sich
nahtlos wiederholt — kein Reset-Sprung am Ende der Sequenz.

- **Technik:** `animation-timeline: scroll()` für eine an den Scroll-
  Fortschritt gekoppelte Variante, oder ein reines zeitbasiertes
  `@keyframes translateX`-Loop für eine kontinuierliche Marquee ohne
  Scroll-Kopplung — beide sind reines CSS, kein JavaScript nötig.
- Die Inhaltsreihe wird verdoppelt (zweimal identisch hintereinander) und
  exakt um 50 % ihrer eigenen Breite verschoben, damit der Loop-Punkt
  unsichtbar ist.
- Animiert wird ausschließlich `transform: translateX(...)`.

## Parameter

- Geschwindigkeit: langsam genug, dass einzelne Elemente lesbar bleiben.
- Richtung: konsistent mit der Leserichtung der übrigen Seite, sofern kein
  bewusster Kontrast gewünscht ist.

## Fallstricke

- **Sichtbarer Reset-Sprung.** Passiert, wenn die verdoppelte Reihe nicht
  exakt 50 % Versatz hat oder die beiden Kopien unterschiedlich breit sind
  (z. B. durch dynamisch geladene Inhalte nach dem ersten Layout).
- **Marquee mit Text, der wichtige Information trägt.** Eine endlos
  laufende Reihe ist für Screenreader und schnelles Scannen ungeeignet —
  wichtige Inhalte gehören nicht ausschließlich in eine Marquee.

## reduced-motion

Die Reihe steht still, einmal (nicht verdoppelt) dargestellt — kein
laufender Loop, aber der Inhalt bleibt vollständig lesbar.
