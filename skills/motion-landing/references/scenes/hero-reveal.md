# Hero-Reveal — Ladeorchestrierung

Demo: `assets/scenes/hero-reveal/vanilla/index.html` (primär),
`assets/scenes/hero-reveal/react/HeroReveal.jsx` (React-Adapter). Dieses
Dokument erklärt die Mechanik und verweist auf die Demo — es enthält keinen
Codeblock daraus (Sync-Regel, siehe SKILL.md).

## Mechanik

Der Hero ist die erste Sektion, die der Nutzer sieht — sie orchestriert
sich beim Laden statt alles gleichzeitig einzublenden. Überschrift,
Unterzeile und CTA erscheinen nacheinander, mit kurzem Versatz
(`animation-delay`), nicht als eine einzige Fade-In-Gruppe.

- Technik: CSS Scroll-Driven Animations kommen hier **nicht** zum Einsatz —
  Hero-Reveal ist ladezeit-, nicht scrollgetrieben. Reines
  `@keyframes`/`animation-delay`, kein `animation-timeline`.
- Ausschließlich `transform` (z. B. `translateY`) und `opacity` animiert —
  nie `margin`/`top`, das würde Layout-Kosten pro Frame verursachen und
  CLS riskieren.
- Der reservierte Platz für jedes Element steht von Anfang an fest (kein
  Höhenwechsel während der Animation) — das ist der Kern, wie diese Szene
  CLS vermeidet: Sie animiert nur `transform`, nie eine Eigenschaft, die
  Layout neu berechnet.

## Parameter

- Versatz zwischen den Elementen: kurz genug, dass die Sequenz nicht als
  Warten wahrgenommen wird (siehe die Demo für den konkreten Wert).
- Gesamtdauer der Sequenz: kürzer als die Zeit, die ein ungeduldiger Nutzer
  bis zum ersten Scroll wartet.

## Fallstricke

- **CLS durch reservierten falschen Platz.** Wenn ein Element vor der
  Animation `display: none` oder `height: 0` hat und erst durch JS seine
  echte Höhe bekommt, zählt der Sprung als Layout-Shift, obwohl nur
  `opacity`/`transform` animiert wurden. Der reservierte Platz muss von
  Anfang an im Layout-Fluss stehen (`opacity: 0` plus `visibility` je nach
  Bedarf, nicht `display: none`).
- **Zu viele Elemente in der Sequenz.** Hero-Reveal ist keine ruhige
  Szene, aber auch kein Höhepunkt (Choreografie-Doktrin) — mehr als drei,
  vier orchestrierte Elemente wirken schnell wie Zeremonie statt Auftakt.

## reduced-motion

Alle Elemente erscheinen sofort, ohne Versatz, ohne Transform-Ausgangs­-
zustand — der Endzustand direkt, kein „eingefroren auf halbem Weg". Siehe
die Demo für die konkrete Media Query.
