# motion-landing Implementierungsplan

**Ziel:** Skill `motion-landing` (Spec 06) — Szenen-Grammatik für animierte Landing
Pages, mit drei Schichten (Rezept, Demo, Harness) nach klarer Arbeitsteilung.

**Basis:** `feat/motion-landing`, abgezweigt von `specs/skill-foundation` (`0831fb7`).

**Bindende Vorentscheidungen** (aus dem Auftrag, nicht verhandelbar):
1. Vier Demos zum Start (`hero-reveal`, `scroll-telling`, `sticky-pin`,
   `canvas-moment`), je Vanilla + React. `marquee`, `stagger-grid`,
   `closing-cta` bekommen nur ein Rezept, das seine erste Zeile als „Demo fehlt"
   kennzeichnet.
2. `verify.py`: Screenshots immer, Video nur mit `--video`.
3. CSS Scroll-Driven Animations mit `CSS.supports(...)`-Feature-Detection;
   statischer, vollständig sichtbarer Fallback statt GSAP-Pflichtpfad.

**Umgebungs-Constraint:** Playwright und Lighthouse sind hier nicht installiert
und werden nicht installiert. `verify.py` wird vollständig geschrieben
(inklusive Erfolgspfad), aber nur der Degradationszweig ist hier verifizierbar.
Die reine Logik (Toolchain-Erkennung, Budget-Auswertung, Szenen-Grenzen,
Degradations-Meldung) wird von der Playwright-Ansteuerung getrennt und ohne
Browser getestet.

---

## Task 1: `verify.py` — reine Logik (Tier-3-Skript, browserfreier Kern)

**Files:** Create `skills/motion-landing/scripts/verify.py`,
`tests/test_motion_landing_verify.py`

**Test zuerst**, dann Implementierung. Abgedeckt:
- `Scene`/`SceneBoundary`/`SceneError`: `load_scenes()`, `validate_single_highlight()`
  (Storyboard-Contract: genau ein Höhepunkt), `compute_scene_boundaries()`
  (Pixel- und Prozent-Grenzen aus Szenenhöhen).
- `ToolchainStatus`, `detect_toolchain()` mit injizierbaren `find_spec`/`which`
  für deterministische Tests ohne echte Systemabfrage.
- `BudgetCheck`/`BudgetReport`, `evaluate_budgets()` — liest ein Lighthouse-JSON
  (als `dict`), vergleicht LCP/CLS/INP gegen die Budgets aus SKILL.md,
  `status` ist `pass`/`fail`/`missing` (nie stillschweigend `pass` bei fehlendem
  Audit). INP-Fallback: fehlt `interaction-to-next-paint`, wird `total-blocking-time`
  als dokumentierter Näherungswert verwendet, mit `note`.
- `degradation_report()` — die Checkliste aus allen sechs Contract-Punkten
  (LCP, CLS, INP, transform/opacity-only, JS-frei lesbar, reduced-motion je
  Szene), jeder Punkt trägt „ungeprüft (Werkzeug X fehlt)", nichts wird
  ausgelassen.

**Commit:** `test(motion-landing): verify.py Kernlogik — Szenen, Budgets, Toolchain-Erkennung`

## Task 2: `verify.py` — CLI und Playwright/Lighthouse-Pfad

**Files:** Modify `skills/motion-landing/scripts/verify.py`,
`tests/test_motion_landing_verify.py`

- `run_playwright_capture()`, `run_lighthouse()`: Playwright-Import lokal in der
  Funktion (Modul bleibt ohne Playwright importierbar); Docstring markiert
  „UNGETESTET in dieser Umgebung — siehe docs/known-limits.md".
- `main()`: parst `--scenes`, `--url`, `--out`, `--video`; prüft zuerst den
  Storyboard-Contract (Exit 3 bei Verstoß), dann `detect_toolchain()`. Fehlt
  die Toolchain → `degradation_report()` schreiben, Exit 2, sichtbare Ausgabe
  auf stdout/stderr. Ist sie da → Erfolgspfad (Exit 0/1). Playwright-/Lighthouse-
  Aufrufe hängen an Modul-Attributen, damit Tests sie per `monkeypatch`
  ersetzen und den Erfolgspfad *strukturell* (Report-Zusammenbau, Exit-Codes)
  prüfen können, ohne echten Browser.
- Test, der `main()` real in dieser Umgebung laufen lässt (kein Mock von
  `detect_toolchain`) und beweist: Degradationszweig greift, Report trägt
  „ungeprüft (Playwright/Lighthouse nicht verfügbar)", nichts wird still
  übersprungen. Das ist der einzige hier real geprüfte Ast.

**Commit:** `feat(motion-landing): verify.py CLI mit Degradations- und Erfolgspfad`

## Task 3: SKILL.md und References

**Files:** Create `skills/motion-landing/SKILL.md`,
`skills/motion-landing/references/scenes/{hero-reveal,scroll-telling,sticky-pin,canvas-moment,marquee,stagger-grid,closing-cta}.md`,
`skills/motion-landing/references/tech-tree.md`,
`skills/motion-landing/references/choreography.md`,
`skills/motion-landing/references/adapters.md`

- SKILL.md ≤ 150 Zeilen, Frontmatter nur `name`/`description`. Description
  routet beidseitig zu `ui-architect` (Stil/Tokens) und `enterprise-ui`
  (Produktoberfläche) und grenzt sich ab.
- Storyboard-Contract, Budgets, NEVER-Liste, Entscheidungsbaum als Text.
- Die drei ohne-Demo-Rezepte (`marquee`, `stagger-grid`, `closing-cta`) beginnen
  mit einem Satz, der explizit sagt: Demo fehlt, Szene wird von Hand gebaut.
- Sync-Regel durchgehalten: Rezepte referenzieren Pfade unter `assets/scenes/`,
  betten nie Code ein.

**Commit:** `feat(motion-landing): SKILL.md und Referenzen — Grammatik, Budgets, NEVER-Liste`

## Task 4: Vanilla-Demos (die vier Kernszenen)

**Files:** Create `skills/motion-landing/assets/scenes/{hero-reveal,scroll-telling,sticky-pin,canvas-moment}/vanilla/index.html`

- Je Datei eigenständiges Single-File-HTML (läuft als claude.ai-Artifact),
  animiert nur `transform`/`opacity`, `@media (prefers-reduced-motion: reduce)`
  Pflichtblock, Inhalt ohne JS lesbar.
- `scroll-telling`/`sticky-pin` prüfen `CSS.supports('animation-timeline: scroll()')`
  und fallen auf einen statischen, vollständig sichtbaren Zustand zurück.

**Commit:** `feat(motion-landing): vier Vanilla-Demos — hero-reveal, scroll-telling, sticky-pin, canvas-moment`

## Task 5: React-Demos (Adapter der vier Kernszenen)

**Files:** Create `skills/motion-landing/assets/scenes/{hero-reveal,scroll-telling,sticky-pin,canvas-moment}/react/*.jsx` (+ ggf. `.css`)

- Gleiche Mechanik wie die Vanilla-Demo, React-Idiome (Hooks, Komponenten),
  gleiche reduced-motion- und Feature-Detection-Pflichten.

**Commit:** `feat(motion-landing): React-Adapter der vier Kernszenen`

## Task 6: Evals

**Files:** Create `evals/motion-landing/evals.json`,
`evals/fixtures/cls-trap-hero/{fixture.json,README.md}`,
`evals/fixtures/frozen-reduced-motion/{fixture.json,README.md}`

- Eval 4 zuerst, Klasse `contract`: Artifact-Kontext ohne Playwright,
  Fixture `empty-dir` (wiederverwendet) — prüft, dass der Degradationsbefund
  sichtbar „ungeprüft" trägt und keine falsche Erfolgsbehauptung im Report
  oder in der Ausgabe steht.
- Eval 1, Klasse `behavior`: „Mach die Seite wie Google Labs" ohne weitere
  Angaben, Fixture `empty-dir` — Judge prüft Storyboard mit genau einem
  Höhepunkt.
- Eval 2, Klasse `contract`: CLS-Falle (neue Fixture `cls-trap-hero`) —
  mechanisch: `transform` statt `margin-top`/`top` in den Keyframes danach.
- Eval 3, Klasse `contract`: reduced-motion-Lauf (neue Fixture
  `frozen-reduced-motion`) — mechanisch: reduced-motion-Block zeigt Inhalt
  statisch (kein `display: none`/`visibility: hidden`).
- Schema nur mechanisch validieren (`load_evals`), nicht mit `run_evals.py`
  ausführen.

**Commit:** `feat(motion-landing): Evals — Artifact-Degradation, Storyboard, CLS-Falle, reduced-motion`

## Task 7: known-limits.md und Abschlussbericht

**Files:** Modify `docs/known-limits.md`, Create
`docs/superpowers/reports/motion-landing-report.md`

- Abschnitt „motion-landing" in known-limits.md: Erfolgspfad von `verify.py`
  ungetestet (kein Playwright/Lighthouse hier), was genau ungeprüft bleibt,
  offene Fragilität der `must_not`-Regexe in den neuen Fixtures.
- Bericht nach Vorgabe aus `brief-common.md`.

**Commit:** `docs: motion-landing — bekannte Grenzen, Abschlussbericht`

---

Nach jedem Task: `.../scratchpad/venv/bin/python -m pytest -q` muss grün bleiben
(146 bestehende + neue Tests).
