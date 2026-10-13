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
validiert über `evalkit.schema.load_evals`; alle vier inzwischen mindestens
einmal real gefahren, siehe „Fix-Runde 2" unten — Stand: 4 von 4 bestehen):
1. `artifact-context-degrades-visibly` (contract, zuerst gebaut) — Fixture
   `empty-dir`. Bestand real: `verify.py` meldet Exit-Code 2,
   `status: "ungeprüft"`, vollständige Sechs-Punkte-Checkliste.
2. `google-labs-prompt-yields-single-highlight-storyboard` (behavior) — drei
   Judge-Claims zum Ein-Höhepunkt-Storyboard, Fixture `empty-dir`. Fiel im
   ersten realen Voll-Lauf an Claim 1, wegen einer Harness-Grenze, nicht eines
   Skill-Defekts (siehe „Fix-Runde 2"); nach dem Fix real bestanden.
3. `cls-trap-hero-gets-fixed-to-transform` (contract) — neue Fixture
   `evals/fixtures/cls-trap-hero/`. Bestand real.
4. `reduced-motion-scene-shows-static-content-not-frozen-hidden` — ursprünglich
   contract, in Fix-Runde 1 auf **behavior** umgebaut (siehe unten) — neue
   Fixture `evals/fixtures/frozen-reduced-motion/`. Bestand real, inklusive
   des neuen Judge-Claims.

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
(letzter Lauf vor diesem Bericht, unverändert nach Fix-Runde 2).
Eval-Schema weiterhin mechanisch gültig (`evalkit.schema.load_evals`, 4
Evals). Realer Eval-Stand nach Fix-Runde 2: 4 von 4 bestanden (ein Voll-Lauf
durch den Koordinator plus zwei gezielte Diagnose-Läufe von mir für
`google-labs-prompt-yields-single-highlight-storyboard`, Details unten).

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
Diese Liste galt bis Fix-Runde 2: Alle vier Evals liefen inzwischen real
(einmal durch den Koordinator, einmal gezielt durch mich zur Diagnose) und
bestehen — siehe „Fix-Runde 2" unten für den Verlauf und den einen
gefundenen, harness-bedingten Fehlschlag.

Alle diese Punkte stehen mit Details in `docs/known-limits.md`, Abschnitt
„motion-landing". Real geprüft wurde ursprünglich ausschließlich der
Degradationszweig von `verify.py` (Toolchain-Erkennung, Degradations-Report,
`main()` mit echt fehlender Toolchain) — genau der Teil, den der Auftrag als
hier verifizierbar benannt hat. Der Erfolgspfad von `verify.py`
(Playwright/Lighthouse) bleibt weiterhin ungetestet, auch nach Fix-Runde 2.

## Fix-Runde 1 (Nachtrag)

Der Koordinator hat nach dem ersten Durchlauf einen echten Defekt gefunden,
keinen dokumentierbaren Randfall: `reduced-motion-scene-shows-static-content-not-frozen-hidden`
akzeptierte als `must` `opacity: 1` ODER `animation: none` im
`reduce`-Block. Der naheliegendste Fix überhaupt —
`@media (prefers-reduced-motion: reduce) { .panel { animation: none; } }` —
erfüllte damit `must` und verletzte kein `must_not`, obwohl die Basisregel
`.panel { opacity: 0; }` unverändert blieb und der Inhalt weiterhin
unsichtbar war. Der Eval wurde grün, während genau der Fehler durchging,
den er fangen sollte. Grund: Sichtbarkeit ist eine Eigenschaft der
CSS-Kaskade, keine Texteigenschaft einer Datei — eine engere Regex hätte
das Loch nur verschoben (siehe Begründung des Koordinators, übernommen in
`docs/known-limits.md`).

**Behoben:** Der Eval ist jetzt `class: behavior`. Die Sichtbarkeit trägt
ein Judge-Claim, der die Kaskade als Ganzes bewertet und ausdrücklich den
gefundenen defekten Fix als Negativbeispiel nennt. Die vier
`must_not`-Muster (`display: none`, `visibility: hidden`, ergänzt um
`height: 0` und `clip-path`) bleiben als billige mechanische Vorfilter.
Mechanisch nachgestellt (Scratch-Skript, nicht committet): Der defekte Fix
erfüllt jetzt keine mechanische `must`-Bedingung mehr, die ihn fälschlich
grün machen würde — die Erkennung hängt vollständig vom (noch nie real
gelaufenen) Judge-Urteil ab.

Zweiter, kleinerer Punkt: `cls-trap-hero-gets-fixed-to-transform` prüfte die
`must_not`-Muster nur gegen `styles.css`. Ein Fix, der `transform` sauber
dort einbaut, die verbotene `margin-top`-Animation aber zusätzlich inline
nach `index.html` verschiebt, wäre durchgekommen. Die beiden Muster laufen
jetzt gegen beide Dateien; mechanisch mit einem simulierten Mischfall
bestätigt.

## Fix-Runde 2 (Nachtrag): der reale Voll-Lauf und die Diagnose

Der Koordinator hat die vier Evals zum ersten Mal real fahren lassen: 3 von 4
bestanden. Beide in Fix-Runde 1 reparierten Evals (`cls-trap-hero-gets-fixed-to-transform`,
`reduced-motion-scene-shows-static-content-not-frozen-hidden`) bestanden real,
ebenso `artifact-context-degrades-visibly`. Gefallen war
`google-labs-prompt-yields-single-highlight-storyboard`, und zwar präzise an
Claim 1 („Storyboard-Block vor jeder Implementierung") — Claims 2 und 3 (ein
Höhepunkt, keine Effekt-Häufung) waren nicht als gefallen gemeldet.

**Diagnose statt Raten**, wie aufgetragen: Eine Wegwerf-Eval-Sammlung mit
genau diesem einen Eval gebaut (`fixtures/empty-dir` kopiert,
`evals/motion-landing/evals.json` auf den einen Eval reduziert) und mit
`python3 run_evals.py --evals-dir <wegwerf-dir> --skills-dir skills --skill
motion-landing --keep-workspace` real gefahren — reproduzierte denselben
Fehlschlag. Der behaltene Workspace zeigte: Der Agent hatte eine vollständige,
formkorrekte Landing Page gebaut — `scenes.json` mit fünf typisierten Szenen
und exakt einem `"highlight": true`, HTML-Kommentare je Szene mit Typ und
Status (`<!-- Szene 1 — hero-reveal (ruhig) -->` usw.), `verify.py` real
gelaufen mit dem korrekten Degradations-Ergebnis. Kein Hinweis auf
Effekt-Konfetti oder ein übersprungenes Storyboard.

Da `run_evals.py` kein Transcript persistiert (bekannte Grenze), reichte das
allein nicht — ich musste den Agentenlauf mit demselben Aufruf, den
`evalkit.dispatch.run_agent` benutzt, direkt wiederholen und `stdout` selbst
mitschneiden. Ergebnis: 15 Zeilen, ausschließlich eine Abschlusszusammen-
fassung, die auf ein „Storyboard oben" **verweist**, es aber nicht
wiederholt. Um zwischen (a) SKILL.md verlangt den Block zu schwach/spät und
(b) der Block entsteht, ist aber für den Judge nicht erkennbar, zu
unterscheiden, habe ich die tatsächliche Ursache des Harnesses empirisch
geprüft: `claude -p` (Default `--output-format text`, genau das, was
`run_agent` benutzt) wurde mit einer expliziten Drei-Schritt-Anweisung
getestet (Marker-Text schreiben → Tool benutzen → zweiter Marker-Text
schreiben). Nur der **letzte** Marker erschien in `stdout` — der erste war
spurlos verschwunden, obwohl er wörtlich verlangt war.

**Diagnose-Ergebnis: keine der beiden vorgeschlagenen Ursachen trifft es
exakt — es ist ein Harness-Effekt, keiner der Skill.** SKILL.md wurde befolgt
(a trifft nicht zu — der Storyboard-Contract lief, nicht schwach), und der
Block war auch nicht in falscher *Form* im sichtbaren Text (b trifft nicht
wörtlich zu — es gab dort gar keinen Text zu erkennen). Der eigentliche
Befund: `evalkit.dispatch.run_agent`s `Transcript.stdout` enthält
strukturell nur die letzte Assistant-Nachricht, nie frühere
Gesprächsrunden — ein Claim über „vor dem Code" ist damit für den Judge
grundsätzlich unbeobachtbar, unabhängig von der Qualität von Skill oder
SKILL.md. Näher an (b) im Effekt (der Judge sieht die geforderte Form
nicht), aber mit einer anderen, tieferen Ursache als vermutet.

**Fix, in der Wirkung wie (a):** SKILL.md verlangt jetzt (Ablauf, Schritt 6)
ausdrücklich, dass die Abschlussmitteilung das Storyboard als Liste
wiederholt statt nur zu referenzieren — mit der Begründung im Text selbst,
dass ein Aufrufer im nicht-interaktiven Modus nur die letzte Nachricht
sieht. Das behebt nicht nur den Eval: Ein echter Nutzer, der die Skill via
`claude -p` oder Skript aufruft, hätte dasselbe Problem gehabt und das
Storyboard nie zu Gesicht bekommen. Der Claim selbst wurde parallel
umformuliert, um das zu prüfen, was der Harness tatsächlich beobachten kann
(Abschlussantwort plus Datei-Diff), statt eine über Turns hinweg
unbeobachtbare Reihenfolge zu verlangen. Ein erneuter realer Lauf mit
Fix bestand. Details und die vollständige Herleitung stehen in
`docs/known-limits.md`, Abschnitte „Betrieb" (die geteilte Harness-Grenze)
und „motion-landing" (der konkrete Fall).

Beiläufig geprüft, wie vom Koordinator verlangt: `~/.skills/` enthält nach
allen Diagnose-Läufen dieser Runde weiterhin nur `visual-summary/`, kein
`motion-landing/` — die bei `visual-summary` gefundene Klasse von Fehler
(Fixture ohne `git` → Artefakt landet unter `$HOME`, außerhalb jeder
Assertion) trifft meine Fixtures nach dieser Stichprobe nicht, weil
`verify.py`s Ausgabepfad relativ zum Arbeitsverzeichnis bleibt statt bei
fehlendem `.git` auf `$HOME` auszuweichen. Details in `docs/known-limits.md`.

## Offene Sorgen

- Der reale Voll-Lauf deckte nur einen von vier Evals als fehlerhaft auf,
  aber ein einzelner Lauf pro Eval ist keine Serienprüfung — LLM-Agentenläufe
  sind nicht deterministisch. Dass alle vier jetzt einmal real bestanden
  haben, heißt nicht, dass sie es bei jeder plausiblen Formulierung des
  Agenten tun.
- Die tiefere Harness-Grenze, die die Diagnose freigelegt hat
  (`Transcript.stdout` enthält nur die letzte Nachricht, nie frühere Turns),
  betrifft vermutlich nicht nur motion-landing — jede `behavior`-Eval einer
  anderen Skill, deren Claim etwas über eine frühere Gesprächsrunde behauptet
  („X, bevor Y passiert"), hat dieselbe blinde Stelle. Ich habe das nur in
  `docs/known-limits.md` dokumentiert (Abschnitt „Betrieb", geteilt), nicht
  behoben — ein Fix (`--output-format stream-json`) würde `evalkit/dispatch.py`
  ändern, eine Datei außerhalb meiner Skill, und lag außerhalb dieses
  Auftrags.
- Die `must_not`-Regexe in `cls-trap-hero-gets-fixed-to-transform` (jetzt auch
  gegen `index.html`) und die vier Vorfilter-Muster in
  `reduced-motion-scene-shows-static-content-not-frozen-hidden` fangen die
  Umgehungen, die ich mir ausgedacht und durchprobiert habe — nicht jede
  denkbare. Ein drittes File bei ersterem, oder eine fünfte Verstecken-Technik
  bei letzterem, entgeht ihnen weiterhin. Dokumentiert, nicht vollständig
  geschlossen — dieselbe Grenze, die `dev-report`s
  `release-notes-filter-internals` schon hat.
- React-Demos sind ungebaut/ungerendert geblieben. Ich habe sie sorgfältig
  nach der Vanilla-Mechanik und dem Adapter-Mapping geschrieben, aber ohne
  jede Ausführung ist ein Tippfehler oder ein Hook-Dependency-Fehler nicht
  ausgeschlossen.
- Der Erfolgspfad von `verify.py` (echtes Playwright/Lighthouse) bleibt
  ungetestet — auch der reale Voll-Lauf lief in einer Umgebung ohne diese
  Toolchain, `artifact-context-degrades-visibly` bestätigt nur den
  Degradationszweig.
- Die `~/.skills`-Stichprobe war eine Beobachtung aus einer Handvoll Läufen,
  kein Beweis für jeden denkbaren Prompt oder jede künftige Erweiterung der
  Skill.
- Die Gegenrichtung des Routings (`ui-architect`/`enterprise-ui` → Verweis
  auf `motion-landing`) wurde absichtlich **nicht** angefasst — das übernimmt
  die zentrale Pflege der Routing-Matrix, wie im Auftrag verlangt.
