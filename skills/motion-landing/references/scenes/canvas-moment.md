# Canvas-Moment — Partikel/generative Fläche als der eine Höhepunkt

Demo: `assets/scenes/canvas-moment/vanilla/index.html` (primär),
`assets/scenes/canvas-moment/react/CanvasMoment.jsx` (React-Adapter).
Erklärt die Mechanik, verweist auf die Demo — kein eingebetteter Code
(Sync-Regel).

## Mechanik

Ein 2D-`<canvas>` mit einem `requestAnimationFrame`-Loop, der eine
generative Fläche zeichnet (Partikel, ein reagierendes Muster). Reserviert
für **den einen Höhepunkt** einer Seite — der Storyboard-Contract erlaubt
ohnehin nur einen, und Canvas ist die teuerste Technik im Tech-Tree
(siehe `references/tech-tree.md`, Stufe 3).

- Kein Three.js/WebGL — reines 2D-Canvas (`getContext('2d')`).
- Der Loop läuft nur, während die Szene im Viewport ist
  (`IntersectionObserver` pausiert/stoppt `requestAnimationFrame`
  außerhalb) — sonst kostet die Szene Main-Thread-Zeit, auch wenn sie
  längst aus dem Blickfeld gescrollt ist.
- Partikelzahl und Frame-Arbeit sind bewusst begrenzt, damit die Szene
  auf einem gedrosselten Profil (siehe Budgets in SKILL.md) nicht selbst
  zur INP-Falle wird — ein Canvas-Loop, der jeden Frame zu viel Zeit
  braucht, blockiert nachfolgende Interaktionen genauso wie jeder andere
  teure JS-Task.

## Parameter

- Partikelzahl/Musterdichte: an das gedrosselte Profil angepasst, nicht an
  die Entwicklungsmaschine.
- Trigger: Viewport-Eintritt (`IntersectionObserver`), nicht Seitenladen —
  der Höhepunkt soll ankommen, wenn der Nutzer ihn sieht, nicht vorher
  schon verpuffen.

## Fallstricke

- **Loop läuft, obwohl die Szene unsichtbar ist.** Häufigste Ursache für
  unnötigen Main-Thread-Verbrauch weit weg von der eigentlichen Szene —
  immer mit `IntersectionObserver` pausieren.
- **Canvas ohne reduzierten reduced-motion-Pfad.** Ein Canvas-Loop lässt
  sich nicht per CSS-Media-Query stoppen — das JS selbst muss
  `matchMedia('(prefers-reduced-motion: reduce)')` prüfen, vor Loop-Start
  und bei Änderungen zur Laufzeit (`change`-Event auf dem `MediaQueryList`).
- **Zweiter Höhepunkt neben dem Canvas-Moment.** Wenn eine andere Szene
  auf derselben Seite ebenfalls stark animiert ist, verletzt das die
  Choreografie-Doktrin — Canvas-Moment ist der Höhepunkt, alles andere
  bleibt ruhiger.

## reduced-motion

Kein laufender Loop. Ein einzelner, statischer Frame des Musters wird
gezeichnet (nicht: leere Canvas, nicht: `display: none`) — der visuelle
Moment bleibt als Standbild erhalten, nur ohne Bewegung.
