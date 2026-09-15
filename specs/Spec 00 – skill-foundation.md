# Spec 00: skill-foundation — Artefakt-Vertrag, Evals, Tiers und Routing

Skill-Spezifikation · Zyklus 0/14 (nachgezogen) · Entscheidung: Konventions-Dokument statt Skill, meinungsstarke Defaults, Gate-Ehrlichkeit als Sprachregelung

## Problem

Die vierzehn Specs setzen stillschweigend eine gemeinsame Grundlage voraus, die keine von ihnen definiert. Sechs Skills schreiben Artefakte in fremde Repos, drei lesen die Artefakte der anderen — Pfade, Formate, Besitz und Erstanlage stehen aber nur als Open Question in je einzelnen Specs, sodass die Kopplung erst zur Laufzeit auffällt. Jede Spec endet mit „die vier Evals bauen" und verweist auf `evals/evals.json`, ohne dass Schema, Runner, Fixtures oder Bestehens-Kriterium irgendwo existieren: rund sechzig adversariale Szenarien als unbepreister Posten. Jede Spec betont „portables Frontmatter" und hängt zugleich an Playwright, Lighthouse, Spectral, oasdiff, sqlfluff, pyreverse oder Alembic, ohne zu sagen, was passiert, wenn das Werkzeug fehlt. Jede Spec nennt ihre Skripte „Gate" und „Blocker", obwohl der Aufruf freiwillig bleibt. Und jede Spec delegiert das Trigger-Problem an ein „Description schärfen" im letzten Absatz, während niemand die Routing-Matrix über alle Skills plus die installierten Fremd-Skills besitzt.

## Constraints

Kein Skill, sondern ein Konventions-Dokument plus wenige geteilte Werkzeuge — es gibt nichts, was Claude hier „ausführen" soll. Bestehende Pfadentscheidungen der vierzehn Specs werden ratifiziert, nicht neu erfunden; Spec 00 füllt nur Lücken und löst Widersprüche. Die Konventionen müssen für Skills gelten, die auch außerhalb von Claude Code laufen (Cursor, Codex, Gemini CLI lesen dasselbe SKILL.md) — deshalb kein `.claude/`-gebundener Zustand. Durchsetzung per Hook bleibt opt-in: Die Skills liefern Snippets, installieren aber nie selbst in fremde `settings.json`. Deutsch als Dokumentsprache, englische Bezeichner in Dateien und Schemata.

## Approach

**Vier Verträge und eine Sprachregelung. Alles andere bleibt bei den Einzel-Specs.**

### 1 · Artefakt-Vertrag

Drei Klassen mit verschiedenen Lebensdauern, statt eines Sammelordners:

| Klasse | Ort | Beispiele | committed |
| --- | --- | --- | --- |
| **Wissen** (menschenlesbar, überlebt die Skill) | `docs/`, Repo-Root nach Konvention | `docs/debugging/INDEX.md` + Ledger (01), `docs/decisions.md` (03), `docs/specs/wip/` (03), `docs/reports/` (02), `ARCHITECTURE.md` (10), `api/openapi.yaml` (07), `docs/schema/` (08) | ja |
| **Konfiguration** (nutzergepflegt, maschinenlesbar) | `.skills/<skill>/` | `conventions.yaml` (07, 08), `layers.yaml` (10), `registry.yaml` (12) | ja |
| **Ephemera** (Zwischenstand, jederzeit regenerierbar) | `.skills/cache/` | `facts.json` (02), `detect_stack.json` (05), Graph-JSON (10), Task-Dateien (09) | nein, gitignored |

*Annahme:* `.skills/` statt `.claude/`, weil Portabilität über Agenten hinweg erklärtes Ziel ist — widersprich, falls du alles unter `.claude/` willst.

Nicht projektgebundene Artefakte (`learner.md` aus 14, `research/<thema>.md` aus 12, das globale Register aus 12) leben unter `~/.skills/` mit optionalem Projekt-Override — dasselbe Muster wie persönliche vs. Projekt-Skills.

**Bootstrap-Regel:** Keine Skill legt ungefragt Dateien in fremden Repos an. Der erste Lauf kündigt die Anlage an und nennt den Pfad. **Degradations-Regel:** Keine Skill *setzt* ein Artefakt voraus — Spec 02s „falls vorhanden, nie vorausgesetzt" gilt für alle Konsumenten. **Kopf-Regel:** Jedes erzeugte Artefakt trägt eine Kopfzeile mit erzeugender Skill, Schema-Version und Erzeugungskommando (Spec 10 macht das für Diagramme bereits vor; hier wird es allgemein). **Konsumenten-Regel:** Ein Konsument nimmt nie ein Format an, sondern liest die Kopfzeile; bei fehlender oder unbekannter Version degradiert er sichtbar („`docs/decisions.md` v2 erwartet, v1 gefunden — Scan übersprungen") statt zu raten. Das ist der eigentliche Schutz gegen die Kopplung der Skills untereinander.

### 2 · Eval-Vertrag

Ein Schema, ein Runner, geteilte Fixtures — nicht vierzehn Insellösungen.

```
evals/
├── run_evals.py        (ein Runner für alle Skills)
├── fixtures/           (geteilt: legacy-monolith/, chrome-extension/,
│                        brownfield-api/, cyclic-imports/, big-table/ …)
└── <skill>/evals.json  (die Szenarien der jeweiligen Skill)
```

Ein Eval ist ein Objekt aus: `id`, `class` (siehe unten), `fixture` (optional), `prompt` (was der Nutzer wörtlich sagt), `must` (beobachtbare Muss-Assertions), `must_not` (Verbots-Assertions), `notes`. Assertions sind **falsifizierbare Beobachtungen**, nie Stimmungsurteile — dieselbe Härte, die Spec 04 für Findings verlangt („kein Finding ohne Failure-Szenario"), gilt hier für Evals. `run_evals.py` startet pro Eval einen Subagent mit frischem Kontext auf einem Fixture-Worktree, protokolliert den Verlauf und lässt einen zweiten Subagent als Judge gegen `must`/`must_not` urteilen. **Bestanden = alle `must` erfüllt und kein `must_not` verletzt.**

Zwei Klassen halten die Kosten beherrschbar: **Contract-Evals** prüfen mechanisch (ist Datei X entstanden? hat das Gate ein Urteil geloggt? trägt das Artefakt seine Kopfzeile?) und laufen billig bei jeder Änderung. **Verhaltens-Evals** sind die Trap-Szenarien der Einzel-Specs, brauchen den Judge und laufen vor Release.

**Pflicht-Eval für jede Skill:** mindestens ein **Anti-Zeremonie-Eval** — der triviale Fall, bei dem die Skill klein bleiben muss (Spec 01s Tippfehler-Bug, Spec 05s Einzeltest, Spec 04s Mini-Diff). Seine ID beginnt mit `anti-ceremony-`; daran erkennt ihn `skill-forge`s Lint (Spec 17), kein Schema-Zwang in `evalkit` — ältere `evals.json` ohne das Präfix stehen im Register des Repo-Tests. Zeremonie ist das systemische Risiko dieser Sammlung, weil jede einzelne Skill ihre eigene Gründlichkeit für gerechtfertigt hält. Fixtures sind minimal-synthetisch (10–50 Dateien), nicht echte Repos — sie sollen die Falle enthalten, nicht Realismus beweisen.

### 3 · Dependency-Tiers

Jedes Skript deklariert im Kopf seinen Tier; jede SKILL.md nennt pro Skript ab Tier 2 eine benannte Degradationszeile.

| Tier | Bedeutung | Läuft in | Specs |
| --- | --- | --- | --- |
| **0** | kein Skript, reine Doktrin | überall, auch claude.ai/Cowork | Teile von 03, 11, 14 |
| **1** | Python-Stdlib | überall mit Shell | 01, 02, 03, 09, 14 |
| **2** | Python + PyPI | nach Installation | 05, 08 (sqlfluff), 12, 13 |
| **3** | fremde Toolchain (Node, Browser, DB) | projektabhängig | 06 (Playwright/Lighthouse), 07 (Spectral/oasdiff), 10 (dependency-cruiser), 08 (laufende DB) |

**Regel:** Tier 1 wird bevorzugt; wer Tier 3 braucht, begründet es in den Constraints seiner Spec. **Sichtbarkeits-Regel:** Ein übersprungenes Gate wird nie stillschweigend übersprungen — das Ergebnis trägt „geprüft" oder „ungeprüft (Werkzeug X fehlt)". Spec 06s vierter Eval (Artifact-Kontext ohne Playwright) wird damit zum Muster für alle: Degradation ist dokumentiert, nicht implizit.

### 4 · Gate-Ehrlichkeit

Drei Durchsetzungsgrade, die jede Skill pro Gate deklariert — und eine Sprachregelung, die verhindert, dass Specs mehr versprechen, als der Mechanismus hält:

- **G1 Selbstauskunft** — die SKILL.md verlangt es. Formulierung: „verlangt".
- **G2 Maschinelles Urteil** — ein Skript fällt das Urteil, der Aufruf bleibt freiwillig. Formulierung: „meldet Verstoß". Das ist der Normalfall in allen vierzehn Specs.
- **G3 Hook** — `PreToolUse`/`Stop` in `settings.json` erzwingt es unabhängig vom Modell. Formulierung: „blockiert".

**Kein G2-Gate darf sich „blockiert" nennen.** Die Specs 06, 07, 08 und 09 tun das derzeit („Blocker", „blockieren", „Abnahme-Blocker") und überschätzen damit ihre eigene Härte. Lohnend ist G3 nur dort, wo der Schaden irreversibel ist: `migration_gate.py` (08) und `check_ledger.py` (01) bekommen ein Hook-Snippet unter `assets/hooks/`, das der Nutzer bewusst installiert. Alles andere bleibt G2 und sagt das auch.

### 5 · Routing

Frontmatter: `name` und `description` verpflichtend, `license`/`version`/`metadata`/`allowed-tools` optional, nichts Harness-Spezifisches — das ist die Auflösung des in allen Specs zitierten „portablen Frontmatters". SKILL.md ≤ 150 Zeilen (die drei gebauten Skills liegen bei 73–103, die Konvention ist also gelebt); alles Weitere in `references/`.

Jede Description trägt eine explizite Abgrenzungsklausel gegen ihre zwei stärksten Konkurrenten. Sie nennt Trigger und Abgrenzung, **keine Prozessbeschreibung** — was die Skill *tut*, steht im Body, nicht in der Description; sonst folgt der Agent der Description statt dem Body (Spec 17, Entscheidung 1; bestehende Descriptions mit Prozessverben stehen im Register von `tests/test_skills_lint.py`). Die zentrale Matrix lebt hier und im Plugin-README, nicht verteilt in vierzehn „Next steps":

| Anlass | zuständig | nicht |
| --- | --- | --- |
| neues Feature, Codebase existiert | feature-spec (03) | brainstorming — die eigene Profil-Skill, nicht superpowers (kein Codebase-Bezug), writing-plans (das *Wie* danach) |
| Bug, Testfehler | systematic-debugging (01) | feature-spec |
| Testplan, Repo-Typ-Frage | testing-strategy (05) | test-driven-development (Zyklus *während* der Implementierung) |
| Diff prüfen | `/code-review` (mitgeliefert) | Spec 04 — nur noch als Kontextpaket-Lieferant, siehe unten |
| Sicherheit | `/security-review`, trailofbits | alle eigenen Skills |
| Landing-Page-Bewegung | motion-landing (06) | ui-architect (Stil/Tokens), enterprise-ui (Produktoberfläche) |
| ad-hoc „fass zusammen" | visual-summary (11) | dev-report (periodisch), handoff (Sitzungsende) |
| Konzept/Thema erklären (kein Code) | explain (15) | learning-coach (Session mit Abruf), visual-summary (verdichtet Vorliegendes), architecture-map (Codebase) |
| Implementierungsplan zu einer Spec | impl-plan (16) | superpowers:writing-plans (fremde Repos), brainstorming — die eigene Profil-Skill, nicht superpowers (die Spec davor), subagent-dev (zerlegt und dispatcht den fertigen Plan) |
| Skill bauen oder ändern | skill-forge (17) | skill-creator (außerhalb dieser Sammlung, eigenes Eval-Schema), superpowers:writing-skills (Disziplin-Skills mit Druckszenarien), impl-plan (nur der Plan) |

*Annahme:* `to-tickets` wird nicht gebaut; die Verweise in 03, 07 und 10 zeigen künftig auf `superpowers:writing-plans`. *Annahme:* Spec 04 schrumpft auf `collect_context.py` als Zulieferer für `/code-review` — widersprich, falls du die eigene Linsen-Engine trotzdem willst.

## Alternatives considered

Spec 00 als eigene Skill („scaffold-skill", die Gerüst und Konventionen erzeugt) wurde verworfen: Konventionen, die nur beim Scaffolding gelten, driften ab dem zweiten Handgriff — ein gelesenes Dokument plus geteilter Runner hält länger als ein Generator. Alle Artefakte unter `.claude/` zu legen wäre bequemer, opfert aber die Portabilität über Agenten hinweg und versteckt Wissens-Artefakte, die Menschen lesen sollen. Pro Skill eigene Evals ohne gemeinsamen Runner wäre schneller im Einzelfall und garantiert vierzehn unvergleichbare Ergebnisse. Ein globaler Namens-Präfix gegen Kollisionen (`fo-debugging`) wurde verworfen — hässlich und unnötig, solange nur bei echter Kollision umbenannt wird (`debug-ledger`, `subagent-dev` sind bereits so entstanden). Durchgehende G3-Hook-Durchsetzung wurde verworfen: Hooks in fremden Repos zu installieren ist ein Eingriff, der pro Fall gerechtfertigt sein muss.

## Out of scope

Die vierzehn Einzel-Skills selbst, Plugin-/Marketplace-Packaging und Verteilung, CI-Integration des Eval-Runners, Versionierungs- und Release-Prozess der Skill-Sammlung, Migration bestehender Repos auf die Artefakt-Pfade.

## Open questions

Kollidiert `.skills/` mit etwas in deinen Repos, und soll die Konfigurationsklasse stattdessen unter `docs/` sichtbar liegen? Braucht der Eval-Runner echte Worktrees pro Eval (sauber, langsam) oder reichen Kopien der Fixture-Ordner? Wie viele Fixtures tragen wirklich alle vierzehn Skills — und welche Traps brauchen zwangsläufig ein eigenes? Sollen Contract-Evals bei jedem Commit der Skill-Sammlung laufen (eigener Hook hier im Repo) oder manuell? Schema-Versionierung: Zählnummer pro Artefakt oder ein gemeinsamer Stand für alle?

## Next steps

Artefakt-Tabelle mit den vierzehn Specs abgleichen und die dortigen Open Questions zu Ablageorten streichen, weil sie hier beantwortet sind; `evals/run_evals.py` mit Subagent-Dispatch und Judge implementieren und gegen die vier Evals aus Spec 01 als erste echte Last fahren; zwei Fixtures zuerst bauen (`legacy-monolith`, `cyclic-imports` — sie bedienen 05 und 10); Kopf- und Konsumenten-Regel als kurze `references/artifact-header.md` formulieren, die jede Skill einbindet; die Gate-Sprachregelung in 01, 04, 07, 08 nachziehen; Routing-Matrix ins README heben.
