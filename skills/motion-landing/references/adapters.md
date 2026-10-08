# Adapter: Vanilla ↔ React

Die Szenen-Grammatik ist framework-neutral. Vanilla ist primär — CSS
Scroll-Driven Animations laufen ohne Build-Schritt und funktionieren auch
als claude.ai-Artifact (ein einzelnes HTML-File). React ist der zweite
Adapter für Projekte, die es ohnehin einsetzen. Beide Varianten jeder
Kern-Demo liegen unter `assets/scenes/<typ>/{vanilla,react}/` — dieses
Dokument beschreibt das Mapping, es dupliziert keinen Code daraus.

## Mapping-Tabelle

| Konzept | Vanilla | React |
| --- | --- | --- |
| Feature-Detection | `CSS.supports('animation-timeline: scroll()')` beim Laden, Klasse auf `<html>`/`<body>` | Dasselbe, in `useEffect` beim Mount, als State statt Klasse |
| Scroll-Trigger (CSS) | `animation-timeline: scroll()` direkt im Stylesheet | Dieselbe CSS-Regel, importiert als `.css`-Datei — React ändert an der Animationstechnik nichts |
| Scroll-Trigger (GSAP) | `ScrollTrigger.create({...})` in einem `<script type="module">` | `useEffect` registriert/killt den `ScrollTrigger` beim Mount/Unmount — Cleanup ist hier Pflicht, sonst akkumulieren Listener bei jeder Navigation |
| reduced-motion | `@media (prefers-reduced-motion: reduce)` im Stylesheet | Dieselbe Media Query im importierten Stylesheet — kein JS-Zweig nötig, außer eine Szene braucht es für Canvas (siehe unten) |
| Canvas-Loop | `requestAnimationFrame` in einem `<script>`-Block, `matchMedia('(prefers-reduced-motion: reduce)')` prüft vor Loop-Start | Derselbe Loop in `useEffect` mit `useRef` auf das `<canvas>`-Element; `cancelAnimationFrame` im Cleanup |
| Sticky-Pin | `position: sticky` im Stylesheet, kein JS für das Pinning selbst | Identisch — Sticky ist reines CSS in beiden Welten |

## Was sich nicht überträgt

- **Kein 1:1-Kopieren von DOM-Struktur in JSX.** React-Komponenten
  strukturieren Kinder als Props/Children, nicht als starres HTML-Abbild der
  Vanilla-Demo. Die Animationstechnik überträgt sich, die Komponentengrenzen
  nicht zwangsläufig.
- **Kein globaler `<script>`-Zustand in React.** Was in Vanilla ein
  Modul-Top-Level-`let` ist, wird in React ein `useRef` oder `useState` —
  sonst überlebt Zustand fälschlich zwischen Mounts/Unmounts derselben Route.
- **Framer Motion ist kein Pflicht-Ersatz für CSS Scroll-Driven Animations.**
  Wenn die Vanilla-Demo mit reinem CSS auskommt, tut es die React-Variante
  auch — Framer Motion kommt nur ins Spiel, wo GSAP in Vanilla ohnehin nötig
  wäre (Stufe 2 im Tech-Tree), als React-idiomatische Alternative zu
  `ScrollTrigger`.

## Die Sync-Regel gilt auch hier

Dieses Dokument beschreibt das *Muster* des Mappings. Der tatsächliche Code
lebt ausschließlich in `assets/scenes/<typ>/vanilla/` und
`assets/scenes/<typ>/react/`. Ändert sich eine Demo, ändert sich nichts an
diesem Dokument, solange sich das Muster nicht ändert — und umgekehrt: Wer
hier einen Codeblock einfügt, hat die Sync-Regel schon gebrochen.
