# Spec 06: motion\-landing — Szenen\-Grammatik für animierte Landing Pages

Skill\-Spezifikation · Zyklus 6/14 · Entscheidung: A\+B\+C kombiniert (Rezepte \+ lauffähige Demos \+ Verifikations\-Harness) · Abgeglichen mit Spec 00

## Problem

Der Google\-Labs\-/Antigravity\-Look — Scroll\-getriebene Erzählung, Sticky\-Szenen, Canvas\-Momente, federnde Mikrointeraktionen — ist ein Handwerk mit eigenen Fallstricken (Main\-Thread\-Jank, CLS durch einfliegende Elemente, Motion\-Sickness, Seiten, die ohne JS leer sind), das keine existierende Skill als System kodiert. frontend\-design bleibt bei Motion vage, GSAP\-Skills sind API\-Referenzen ohne Choreografie\-Wissen. Ergebnis heute: statische Seiten oder ruckelige Effekt\-Sammlungen, deren Qualität niemand misst.

## Constraints

Szenen\-Grammatik framework\-neutral; zwei Adapter: Vanilla (primär — CSS Scroll\-Driven Animations zuerst, läuft auch als claude.ai\-Artifact) und React (Framer Motion/GSAP). 2D \+ Canvas\-Momente; **kein Three.js/WebGL** (bewusst begrenzt). Rollenteilung in der Skill\-Familie: ui\-architect liefert Stil und Tokens der Seite, motion\-landing choreografiert die Bewegung darüber — beide Descriptions routen aufeinander. `prefers-reduced-motion` ist Pflicht\-Gate, kein Feature. Sync\-Regel: References erklären und verweisen auf Demo\-Dateien; sie betten nie Code ein (Drift\-Schutz). Portables Frontmatter.

## Approach

Drei Schichten mit klarer Arbeitsteilung: **Rezept erklärt, Demo verkörpert, Harness beweist.**

**Skill\-Struktur:**

```
motion-landing/
├── SKILL.md                  (Grammatik-Überblick, Entscheidungsbaum, Budgets, NEVER-Liste)
├── references/
│   ├── scenes/               (je Szenen-Typ ein Rezept: Mechanik, Parameter, Fallstricke,
│   │                          → verweist auf die Demo-Datei, kein eingebetteter Code)
│   ├── tech-tree.md          (CSS Scroll-Driven → GSAP/ScrollTrigger → 2D-Canvas; wann was)
│   ├── choreography.md       (Dramaturgie: Spannungsbogen, Pacing, ein Höhepunkt pro Seite)
│   └── adapters.md           (Vanilla ↔ React: Mapping der Szenen auf beide Welten)
├── assets/
│   └── scenes/               (lauffähige Demos, Vanilla primär + React-Variante:
│   │                          hero-reveal, scroll-telling, sticky-pin, canvas-moment,
│   │                          marquee, stagger-grid, closing-cta)
├── scripts/
│   └── verify.py             (Tier 3: Playwright + Lighthouse; G2 — headless Durchscrollen,
│                              Screenshots an Szenen-Grenzen, Lighthouse-Budget,
│                              reduced-motion-Lauf)
└── evals/evals.json
```

**Szenen\-Grammatik:** Benannte, kombinierbare Szenen\-Typen — Hero\-Reveal (Ladeorchestrierung), Scroll\-Telling\-Sequenz (Text\-/Bild\-Wechsel an Scroll\-Fortschritt), Sticky\-Pin (Element bleibt, Inhalt wandert), Canvas\-Moment (Partikel/generative Fläche als ein Höhepunkt), Stagger\-Grid, Closing\-CTA. Choreografie\-Doktrin: eine Seite hat *einen* Höhepunkt; Szenen dazwischen sind ruhig; Bewegung folgt der Erzählung, nie umgekehrt. Der Technologie\-Entscheidungsbaum wählt die leichteste Technik, die die Szene trägt: CSS Scroll\-Driven Animations zuerst, GSAP/ScrollTrigger wenn Timeline\-Logik nötig, 2D\-Canvas nur für den Höhepunkt.

**Budgets als Contract (in SKILL.md, von verify.py geprüft):** LCP \< 2,5 s, CLS \< 0,1, INP \< 200 ms auf gedrosseltem Profil; animiert werden nur transform/opacity; Inhalte sind ohne JS lesbar (Animation ist Enhancement); jede Szene hat einen definierten reduced\-motion\-Zustand (Opacity\-Fade oder statisch). Ein Verstoß stoppt die Auslieferung, statt als Stilhinweis durchzugehen — Durchsetzungsgrad **G2** nach Spec 00 §4: verify.py fällt das Urteil, der Aufruf bleibt Teil des Workflows. Fehlt die Toolchain (Tier 3), trägt das Ergebnis „ungeprüft (Playwright/Lighthouse nicht verfügbar)" und die Budgets werden als Checkliste abgearbeitet — nie stilles Überspringen. Eval 4 prüft genau das.

**Harness (`verify.py`):** Baut/serviert die Seite, scrollt headless mit Playwright durch, nimmt an jeder Szenen\-Grenze Screenshots (plus Video der Gesamtstrecke), fährt einen zweiten Lauf mit `prefers-reduced-motion: reduce`, und prüft das Lighthouse\-Budget. Claude begutachtet die Aufnahmen selbst (Szene sichtbar? Layout\-Sprung? Höhepunkt dort, wo geplant?), bevor es liefert — „ruckelt nicht" wird von Behauptung zu Befund.

**NEVER\-Liste (Auszug):** Scroll\-Hijacking (Scroll\-Geschwindigkeit kapern); Animation von width/height/top/left; Autoplay\-Sound; Parallax auf Textblöcken; Animation ohne reduced\-motion\-Pfad; Effekt ohne erzählerische Funktion („weil es geht").

**Workflow:** ui\-architect (oder vorhandene Tokens) liefert das visuelle System → motion\-landing plant die Dramaturgie als Szenen\-Abfolge (Output\-Contract: ein Storyboard\-Block — Szenenliste mit Typ, Technik, Höhepunkt\-Markierung — vor jeder Implementierung) → Demos werden adaptiert, nicht neu erfunden → verify.py läuft → Befund\-Review → Auslieferung.

**Evals:** (1) „Mach die Seite wie Google Labs" ohne weitere Angaben — entsteht ein Storyboard mit *einem* Höhepunkt statt Effekt\-Konfetti? (2) Seite mit CLS\-Falle (einfliegender Hero) — schlägt verify.py an und wird gefixt? (3) reduced\-motion\-Lauf — ist jede Szene definiert statt einfach eingefroren\-kaputt? (4) Artifact\-Kontext ohne Playwright — degradiert die Skill dokumentiert (Budgets als Checkliste) statt den Harness stillschweigend zu überspringen?

## Alternatives considered

Nur Rezepte (A): pflegeleicht, aber Claude rekonstruiert Szenen fehleranfällig aus Prosa. Nur Demos (B): funktionierender Code ohne Warum — Anpassungen brechen die Mechanik. Nur Harness auf freiem Code (C allein): misst gut, hebt aber die Qualität des Erstwurfs nicht. Die Kombination ist gewählt, weil die Schichten disjunkte Aufgaben haben; die Sync\-Regel (Prosa dupliziert nie Code) neutralisiert das Drift\-Risiko der Kombination. Three.js/WebGL\-Szenen verworfen (Umfang/Performance\-Risiko; nachrüstbar als eigener Adapter). Eigenständige Landing\-Skill inkl. Design verworfen — Rollenteilung mit ui\-architect ist sauberer.

## Out of scope

Three.js/Shader\-Szenen, Scroll\-Hijacking\-Patterns, Lottie/After\-Effects\-Pipelines, A/B\-Testing der Seiten, CMS\-Integration, Copywriting der Landing Page (eigene Skills vorhanden).

## Open questions

Wie viele Szenen\-Typen zum Start (die sieben gelisteten vs. minimal vier)? Video\-Aufnahme in verify.py immer oder nur auf Anforderung (Speicher/Zeit)? Browser\-Support\-Grenze für CSS Scroll\-Driven Animations — Fallback\-Pflicht via GSAP oder dokumentierter Verzicht?

## Next steps

Die vier Kern\-Demos bauen und real testen (hero\-reveal, scroll\-telling, sticky\-pin, canvas\-moment) — Vanilla zuerst; verify.py mit Scroll\-/Screenshot\-/reduced\-motion\-Läufen implementieren; Rezepte zu den vier Demos schreiben (mit Verweis\- statt Code\-Regel); Storyboard\-Contract in SKILL.md formulieren; Eval 1 und 2 zuerst fahren; Description mit beidseitigem Routing zu ui\-architect/enterprise\-ui schärfen.
