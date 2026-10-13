# Technologie-Entscheidungsbaum: die leichteste Technik, die die Szene trägt

Drei Stufen, in dieser Reihenfolge geprüft. Jede höhere Stufe braucht eine
Begründung — „es geht auch so" reicht nicht, „die Szene braucht Timeline-
Logik, die CSS allein nicht ausdrücken kann" reicht.

## Stufe 1 — CSS Scroll-Driven Animations (Standard)

`animation-timeline: scroll()` bzw. `view()`. Kein JavaScript für die
Animation selbst, läuft auf dem Compositor-Thread, blockiert den Main
Thread nicht. Trägt: Hero-Reveal, Marquee, Stagger-Grid, Closing-CTA, und
den Grundfall von Scroll-Telling und Sticky-Pin.

**Feature-Detection ist Pflicht, nicht optional:**

```js
const supportsScrollDriven = CSS.supports('animation-timeline: scroll()');
```

Liefert `false`: Der Inhalt bleibt statisch und vollständig sichtbar. Nicht
animiert, nicht kaputt, nicht leer — siehe SKILL.md, Abschnitt „CSS
Scroll-Driven Animations statt GSAP-Pflichtpfad". Jede der vier Kern-Demos
prüft das selbst; siehe die jeweilige Demo-Datei für die konkrete Umsetzung.

## Stufe 2 — GSAP/ScrollTrigger (nur bei echter Timeline-Logik)

Wenn eine Szene mehrere Elemente relativ zueinander sequenzieren muss
(Text erscheint, dann verschwindet, während ein Bild dahinter wechselt —
`scroll-telling`), reicht deklaratives CSS nicht mehr aus: Es gibt keine
CSS-native Möglichkeit, mehrere `animation-timeline`-Sequenzen mit
Abhängigkeiten zwischen Elementen zu koordinieren. GSAP/ScrollTrigger
übernimmt dann die Orchestrierung — bewusst gewählt für die eine Szene, die
es braucht, kein Pflicht-Unterbau für alle.

*Warum keine Tier-Eskalation für die ganze Skill:* GSAP ist ein
npm-Paket, das eine Demo einbindet, nicht ein Python-Abhängigkeitstier
(Spec 00 §3 gilt für Skripte in `scripts/`, nicht für Frontend-Libraries
in den Demos selbst). `scripts/verify.py` bleibt Tier 3 wegen
Playwright/Lighthouse, unabhängig davon, ob eine einzelne Demo GSAP lädt.

## Stufe 3 — 2D Canvas (nur für den einen Höhepunkt)

Partikel, generative Flächen, alles, was pixelweise Kontrolle statt
DOM-Elemente braucht. Reserviert für **einen** `canvas-moment` pro Seite —
der Storyboard-Contract erlaubt ohnehin nur einen Höhepunkt, und Canvas ist
die teuerste Technik hier (eigener Rendering-Loop, `requestAnimationFrame`,
manuelles reduced-motion-Handling statt CSS-Media-Query).

**Kein Three.js/WebGL.** Bewusst begrenzt auf 2D-Canvas — siehe Spec 06,
„Alternatives considered". Ein WebGL-Adapter ist nachrüstbar, aber kein Teil
dieser Skill.

## Entscheidungsregel in einem Satz

Frag zuerst: „Reicht `animation-timeline`?" Wenn nein: „Braucht es
Koordination zwischen Elementen über die Zeit?" → GSAP. Wenn nein, aber es
braucht Pixel-Kontrolle statt DOM: → Canvas, und nur für den Höhepunkt.
