# Scroll-Telling-Sequenz — Text-/Bild-Wechsel an Scroll-Fortschritt

Demo: `assets/scenes/scroll-telling/vanilla/index.html` (primär, CSS
Scroll-Driven Animations mit Fallback), `assets/scenes/scroll-telling/react/ScrollTelling.jsx`
(React-Adapter). Erklärt die Mechanik, verweist auf die Demo — kein
eingebetteter Code (Sync-Regel).

## Mechanik

Eine Abfolge von Text-/Bild-Paaren wechselt, während der Nutzer durch eine
lange Sektion scrollt — der Scroll-Fortschritt selbst treibt die Animation,
nicht ein Timer.

- **Technik zuerst:** `animation-timeline: scroll()` auf einer Sequenz von
  `@keyframes`, die Opacity zwischen den Panels kreuzblendet. Trägt den
  Grundfall (zwei bis drei Panels, einfacher linearer Wechsel).
- **Eskaliert zu GSAP/ScrollTrigger**, sobald die Sequenz mehrere Elemente
  *relativ zueinander* koordinieren muss (Text A verschwindet exakt, wenn
  Bild B erscheint, während Text C schon vorbereitet wird) — siehe
  `references/tech-tree.md`, Stufe 2.
- Animiert werden `opacity` und `transform` (leichter Parallax-Versatz
  zwischen Text und Bild ist erlaubt, solange er nicht auf Textblöcken
  selbst liegt — siehe NEVER-Liste in SKILL.md).

## Parameter

- Anzahl der Panels: so viele, wie die Erzählung braucht, nicht so viele,
  wie Platz ist.
- Scroll-Distanz pro Panel: lang genug, dass der Wechsel nicht als Ruckeln
  wahrgenommen wird, kurz genug, dass die Sektion nicht als endlos wirkt.

## Fallstricke

- **Scroll-Hijacking-Optik.** Auch ohne echtes Kapern der Scroll-
  Geschwindigkeit kann eine zu lange Sektion mit zu wenig visueller
  Veränderung sich so anfühlen. Jedes Panel braucht sichtbaren Fortschritt.
- **CSS Scroll-Driven Animations ohne Fallback.** `CSS.supports('animation-timeline: scroll()')`
  muss geprüft werden (siehe `references/tech-tree.md`) — sonst ist die
  Sequenz auf älteren Browsern leer statt lesbar.
- **Text nur während der Animation lesbar.** Verstößt gegen „Inhalte sind
  ohne JS lesbar" (SKILL.md-Budget): Ohne Scroll-Trigger (JS deaktiviert,
  Crawler, Screenreader ohne Scroll-Events) muss der Text trotzdem im DOM
  und zugänglich sein.

## reduced-motion

Alle Panels stehen statisch untereinander, kein Scroll-getriebener
Übergang — der Inhalt bleibt vollständig, nur ohne die
Crossfade-Choreografie. Siehe Demo für die konkrete Umsetzung.
