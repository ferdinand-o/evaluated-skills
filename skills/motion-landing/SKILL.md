---
name: motion-landing
description: Use when building or choreographing an animated landing/marketing page — scroll storytelling, hero reveals, sticky-pin sections, canvas moments, the "Google Labs"/Antigravity motion look. Produces a one-highlight storyboard first, wires proven demo scenes second, then verifies LCP/CLS/INP and reduced-motion with verify.py. Routes to ui-architect first for visual style and design tokens — motion-landing choreographs movement on top of that system, it never invents the look itself; ui-architect should in turn route motion/scroll requests here. For dense product/app UI (dashboards, tables, admin panels, forms) use enterprise-ui instead, not this skill. Triggers include "Landing Page wie Google Labs", "Scroll-Animation", "Hero-Reveal", "Sticky Section", "Canvas-Hintergrund", "Motion Design für die Startseite".
---

# motion-landing — Szenen-Grammatik für animierte Landing Pages

**Rezept erklärt, Demo verkörpert, Harness beweist.** Drei Schichten mit
klarer Arbeitsteilung — Prosa in `references/` erklärt Mechanik und
**verweist** auf die Demo-Datei, sie bettet nie Code ein. Sobald eine
Referenz einen Codeblock aus einer Demo dupliziert, driftet sie davon weg,
und niemand merkt mehr, welche Version gilt.

## Ablauf

1. **Stil klären** — Tokens von `ui-architect` oder ein vorhandenes
   Design-System. Diese Skill erfindet keine Farben, Fonts oder Abstände.
2. **Storyboard-Contract ausgeben**, vor jeder Implementierung: eine
   Szenenliste mit Typ, Technik und markiertem Höhepunkt. **Genau ein**
   Höhepunkt pro Seite — Szenen dazwischen sind ruhig, Bewegung folgt der
   Erzählung, nie umgekehrt. Format:
   ```
   1. hero-reveal      — CSS Scroll-Driven Animations   (ruhig)
   2. scroll-telling   — CSS Scroll-Driven Animations   (ruhig)
   3. canvas-moment     — 2D Canvas                       (★ Höhepunkt)
   4. closing-cta      — CSS Scroll-Driven Animations   (ruhig)
   ```
3. **Szenen adaptieren, nicht neu erfinden** — aus `assets/scenes/`
   (`references/scenes/<typ>.md` nennt den Pfad je Typ).
4. **`scripts/verify.py` laufen lassen** (siehe unten).
5. **Befund-Review vor Auslieferung**: Screenshots an den Szenen-Grenzen
   selbst ansehen — Szene sichtbar? Layout-Sprung? Höhepunkt dort, wo
   geplant? „Ruckelt nicht" ist ein Befund, keine Behauptung.
6. **Storyboard in der Abschlussmitteilung wiederholen** — als Liste, nicht
   als Verweis („wie oben geplant" reicht nicht). Im nicht-interaktiven
   Modus (`claude -p`, Skripte, dieser Eval-Harness) sieht der Aufrufer nur
   die letzte Nachricht; ein Storyboard, das nur in einer früheren Runde
   stand, kommt dort nie an.

## Szenen-Grammatik

**Mobil ist der Regelfall, nicht die Variante.** Eine Landing Page wird ueberwiegend auf Telefonen gesehen: Vor der Choreografie gilt das Handwerk aus `references/mobile.md` (schmal zuerst, `dvh/svh` statt `100vh`, Safe-Areas, kein Hover-only-Pfad), und nach dem Bauen prueft die `mobile-audit`-Skill, ob es gehalten hat.

| Typ | Technik zuerst | Demo | Rezept |
| --- | --- | --- | --- |
| hero-reveal | CSS Scroll-Driven / Load-Orchestrierung | ja | `references/scenes/hero-reveal.md` |
| scroll-telling | CSS Scroll-Driven → GSAP/ScrollTrigger | ja | `references/scenes/scroll-telling.md` |
| sticky-pin | CSS `position: sticky` + Scroll-Driven | ja | `references/scenes/sticky-pin.md` |
| canvas-moment | 2D Canvas | ja | `references/scenes/canvas-moment.md` |
| marquee | CSS Scroll-Driven | **nein, noch zu bauen** | `references/scenes/marquee.md` |
| stagger-grid | CSS Scroll-Driven | **nein, noch zu bauen** | `references/scenes/stagger-grid.md` |
| closing-cta | CSS Scroll-Driven | **nein, noch zu bauen** | `references/scenes/closing-cta.md` |

Details zum Technologie-Entscheidungsbaum in `references/tech-tree.md`,
zur Dramaturgie in `references/choreography.md`, zum Vanilla↔React-Mapping
in `references/adapters.md`.

## Budgets — der Contract, den `verify.py` prüft (G2)

- LCP < 2,5 s, CLS < 0,1, INP < 200 ms, auf gedrosseltem Profil.
- Animiert werden ausschließlich `transform` und `opacity`.
- Inhalte sind ohne JS lesbar — Animation ist Enhancement, nie Bedingung.
- Jede Szene hat einen definierten reduced-motion-Zustand. **Pflicht-Gate,
  kein Feature**: eine Szene ohne definierten reduced-motion-Zustand ist
  unfertig, nicht „noch ohne Extra".

Ein Verstoß meldet `scripts/verify.py` (G2 nach Spec 00 §4: das Skript fällt
das Urteil, der Aufruf bleibt Teil des Workflows — kein Hook erzwingt ihn).

```bash
python "${CLAUDE_SKILL_DIR}/scripts/verify.py" --scenes scenes.json --url http://localhost:8000
python "${CLAUDE_SKILL_DIR}/scripts/verify.py" --scenes scenes.json --url http://localhost:8000 --video
```

**Fehlt die Toolchain** (Playwright und/oder Lighthouse nicht installiert),
schreibt `verify.py` einen Report mit `"status": "ungeprüft"` und arbeitet
die sechs Contract-Punkte oben als Checkliste ab — nie stilles Überspringen.
Das ist der Regelfall in Umgebungen ohne Browser-Toolchain (claude.ai-
Artifact-Kontext eingeschlossen): Sag das dem Nutzer, statt „geprüft" zu
behaupten.

## CSS Scroll-Driven Animations statt GSAP-Pflichtpfad

Jede Demo prüft `CSS.supports('animation-timeline: scroll()')`. Fehlt die
Unterstützung, ist der Inhalt statisch und vollständig sichtbar — nicht
animiert, nicht kaputt, nicht leer. GSAP bleibt eine bewusste Wahl für
Szenen mit echter Timeline-Logik (`scroll-telling`), keine Pflicht-Krücke
für alte Browser: ein statisch lesbarer Fallback ist ohnehin das geforderte
Verhalten aus dem Budget-Contract oben.

## NEVER-Liste

- Scroll-Hijacking (Scroll-Geschwindigkeit kapern).
- Animation von `width`/`height`/`top`/`left` — nur `transform`/`opacity`.
- Autoplay-Sound.
- Parallax auf Textblöcken.
- Animation ohne reduced-motion-Pfad.
- Effekt ohne erzählerische Funktion („weil es geht").
- Mehr als ein Höhepunkt pro Seite.
- Code-Duplikat einer Demo in einer Referenz — verweisen, nie einbetten.

## Abgrenzung

- **ui-architect** — liefert Stil und Design-Tokens der Seite. Motion-landing
  choreografiert Bewegung *über* diesem System, ersetzt es nicht.
- **enterprise-ui** — Produktoberflächen (Dashboards, Tabellen, Formulare).
  Keine Landing-Page-Dramaturgie, kein Storyboard-Contract.
- Kein Three.js/WebGL — bewusst auf 2D-Canvas begrenzt.
- Ohne Playwright/Lighthouse liefert diese Skill trotzdem ein Storyboard und
  Demos, aber `verify.py` bleibt ehrlich „ungeprüft" statt „geprüft" zu
  behaupten.
