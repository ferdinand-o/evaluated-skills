# Abschlussbericht: Skill `motion-landing` (Spec 06)

Branch `feat/motion-landing`, abgezweigt von `specs/skill-foundation`
(`0831fb7`). Plan: `docs/superpowers/plans/2026-08-15-motion-landing.md`.

## Was gebaut wurde

**Skill-Paket** `skills/motion-landing/`:
- `SKILL.md` (104 Zeilen, ≤ 150) — Storyboard-Contract, Budget-Contract,
  NEVER-Liste, Szenen-Grammatik-Tabelle, beidseitiges Routing zu
  `ui-architect`/`enterprise-ui` in der Description.
- `references/tech-tree.md`, `references/choreography.md`,
  `references/adapters.md` — Entscheidungsbaum, Dramaturgie-Doktrin,
  Vanilla↔React-Mapping.
- `references/scenes/*.md` — sieben Rezepte. Vier verweisen auf eine echte
  Demo (`hero-reveal`, `scroll-telling`, `sticky-pin`, `canvas-moment`); drei
  (`marquee`, `stagger-grid`, `closing-cta`) markieren in der ersten Zeile
  explizit, dass die Demo fehlt und die Szene von Hand gebaut werden muss —
  wie im Auftrag entschieden. Kein Rezept bettet Code aus einer Demo ein
  (Sync-Regel durchgehalten).
- `assets/scenes/<typ>/vanilla/index.html` — vier eigenständige
  Single-File-HTML-Demos (laufen auch als claude.ai-Artifact), animieren
  ausschließlich `transform`/`opacity`, tragen je einen
  `prefers-reduced-motion`-Pflichtblock. `scroll-telling` und `sticky-pin`
  prüfen `CSS.supports('animation-timeline: scroll()'/'view()')` und fallen
  auf einen statischen, vollständig sichtbaren Grundzustand zurück —
  entsprechend der getroffenen Entscheidung: dokumentierter Verzicht statt
  GSAP-Pflichtpfad.
- `assets/scenes/<typ>/react/*.jsx` (+ `.css`) — React-Adapter derselben vier
  Szenen, gleiche Animationstechnik, React-idiomatisch als Hooks mit
  Cleanup.
- `scripts/verify.py` (Tier 3, G2) — vollständig geschrieben, inklusive
  Erfolgspfad. Architektur trennt reine Logik (Szenen-Geometrie,
  Storyboard-Contract-Validierung, Toolchain-Erkennung, Budget-Auswertung
  aus gelesenem Lighthouse-JSON, Degradations-Meldung) von der
  Playwright-/Lighthouse-Ansteuerung, deren Importe lokal in den jeweiligen
  Funktionen liegen — das Modul bleibt ohne installiertes Playwright
  importierbar.

**Evals** `evals/motion-landing/evals.json` (4 Evals, Schema mechanisch
validiert über `evalkit.schema.load_evals`, nicht über `run_evals.py`
ausgeführt):
1. `artifact-context-degrades-visibly` (contract, zuerst gebaut) — Fixture
   `empty-dir`. Der einzige Eval, dessen Mechanik hier real geprüft wurde:
   `verify.py` gegen diese tatsächlich Playwright-/Lighthouse-lose Umgebung
   laufen lassen (Smoke-Test während der Entwicklung, siehe unten) bestätigt
   Exit-Code 2, `status: "ungeprüft"`, vollständige Sechs-Punkte-Checkliste.
2. `google-labs-prompt-yields-single-highlight-storyboard` (behavior) — drei
   Judge-Claims zum Ein-Höhepunkt-Storyboard, Fixture `empty-dir`.
3. `cls-trap-hero-gets-fixed-to-transform` (contract) — neue Fixture
   `evals/fixtures/cls-trap-hero/`.
4. `reduced-motion-scene-shows-static-content-not-frozen-hidden` (contract) —
   neue Fixture `evals/fixtures/frozen-reduced-motion/`.

**Tests** `tests/test_motion_landing_verify.py` — 30 Tests, decken Storyboard-
Contract-Validierung, Szenen-Grenzen-Berechnung (Pixel + Prozent),
Toolchain-Erkennung (mit injizierbaren `find_spec`/`which` für
deterministische Fälle, plus ein Test gegen die echte Umgebung), Budget-
Auswertung aus einem `dict` (Lighthouse-JSON-Form, inklusive INP→TBT-
Fallback und „fehlendes Audit ≠ still bestanden"), die Degradations-Meldung,
und `main()` End-to-End: Degradationszweig real, Storyboard-Verstoß (Exit 3),
Erfolgspfad strukturell über `monkeypatch`-Doubles für
`run_playwright_capture`/`run_lighthouse`.

**Nebenbei behoben:** `tests/conftest.py::load_script` registrierte geladene
Module nicht in `sys.modules` — jede `frozen dataclass` (wie in `verify.py`)
scheitert beim Laden per `importlib`, weil `dataclasses` intern
`sys.modules.get(cls.__module__)` auflöst. Ein Ein-Zeilen-Fix
(`sys.modules[spec.name] = module` vor `exec_module`), rückwirkungsfrei für
`dev-report`s Tests (kein `dataclasses`-Gebrauch dort).

## Testergebnis

`146` bestehende Tests blieben grün, `+30` neue: `176 passed` insgesamt
(letzter Lauf vor diesem Bericht).

## Zusätzliche Entscheidungen, die ich treffen musste

- **INP-Ersatzwert.** Lighthouse liefert ohne echte Nutzerinteraktion kein
  belastbares `interaction-to-next-paint`-Audit. `evaluate_budgets()` fällt
  auf `total-blocking-time` zurück, markiert das aber explizit über
  `BudgetCheck.note` als „Näherungswert, nicht gleichwertig" statt es
  stillschweigend als INP auszugeben.
- **Degradations-Checkliste mit sechs statt drei Punkten.** Der Auftrag
  verlangt „die Budgets werden als Checkliste abgearbeitet" — ich habe das
  auf alle sechs Contract-Punkte aus SKILL.md ausgelegt (LCP, CLS, INP, nur
  transform/opacity, JS-frei lesbar, reduced-motion je Szene), nicht nur die
  drei numerischen Lighthouse-Metriken, weil sonst drei Punkte des Contracts
  beim Degradieren unerwähnt blieben.
- **Report-Zielpfad** `.skills/cache/motion-landing/verify-report.json` —
  Ephemera-Klasse nach Spec 00 §1 (analog zu `dev-report`s
  `.skills/cache/facts.json`), nicht explizit in Spec 06 festgelegt.
- **Eval-Fixtures für Eval 2/3 neu gebaut** (`cls-trap-hero`,
  `frozen-reduced-motion`), Eval 1/4 nutzen die bestehende `empty-dir`-
  Fixture wieder, um die Zahl neuer Fixtures klein zu halten.

## Was nicht verifiziert werden konnte

Playwright und Lighthouse sind in dieser Umgebung nicht installiert und
wurden auftragsgemäß nicht installiert. Konkret ungetestet:

- **`run_playwright_capture` und `run_lighthouse`** — kein echter
  Browser-Lauf, kein echter Node/Lighthouse-Aufruf. Der Erfolgspfad von
  `main()` ist nur strukturell getestet (Report-Zusammenbau, Exit-Codes)
  über Test-Doubles dieser beiden Funktionen.
- **Die vier Vanilla-Demos** wurden nie in einem echten Browser gerendert —
  insbesondere, ob `animation-timeline: scroll()`/`view()` und die
  `animation-range`-Werte tatsächlich wie geplant wirken.
- **Die vier React-Adapter** wurden nie gebaut oder gerendert — kein
  Node/React-Tooling in diesem Repo. Syntaxfehler oder gebrochene Hooks
  wären hier nicht aufgefallen.
- **Eval 1** (Judge-Claims) und **Eval 2/3** (mechanisch, aber nur gegen
  simulierte Fix-Varianten in einem Scratch-Verzeichnis durchprobiert, nie
  gegen einen echten Agentenlauf) wurden nicht mit `run_evals.py`
  ausgeführt.

Alle diese Punkte stehen mit Details in `docs/known-limits.md`, Abschnitt
„motion-landing". Real geprüft wurde ausschließlich der Degradationszweig
von `verify.py` (Toolchain-Erkennung, Degradations-Report, `main()` mit
echt fehlender Toolchain) — genau der Teil, den der Auftrag als hier
verifizierbar benannt hat.

## Offene Sorgen

- Die `must_not`-Regexe in `cls-trap-hero-gets-fixed-to-transform` und
  `reduced-motion-scene-shows-static-content-not-frozen-hidden` fangen die
  Umgehungen, die ich mir ausgedacht und durchprobiert habe (Wert ändern
  statt Eigenschaft wechseln; `visibility: hidden` statt `display: none`) —
  nicht jede denkbare. Ein Fix, der die Trap-Datei umbenennt oder auf
  `height`/`clip-path`/`max-height` ausweicht, entgeht ihnen. Dokumentiert,
  nicht behoben — dieselbe Grenze, die `dev-report`s
  `release-notes-filter-internals` schon hat.
- React-Demos sind ungebaut/ungerendert geblieben. Ich habe sie sorgfältig
  nach der Vanilla-Mechanik und dem Adapter-Mapping geschrieben, aber ohne
  jede Ausführung ist ein Tippfehler oder ein Hook-Dependency-Fehler nicht
  ausgeschlossen.
- Eval 1 ist der einzige Eval mit Judge-Assertions und wurde nie gegen einen
  echten Agentenlauf geprüft — ob die drei Claims wirklich zwischen einem
  disziplinierten Storyboard und Effekt-Konfetti unterscheiden, zeigt sich
  erst beim ersten echten Judge-Urteil.
- Die Gegenrichtung des Routings (`ui-architect`/`enterprise-ui` → Verweis
  auf `motion-landing`) wurde absichtlich **nicht** angefasst — das übernimmt
  die zentrale Pflege der Routing-Matrix, wie im Auftrag verlangt.
