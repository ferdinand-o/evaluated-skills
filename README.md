# cc-skills

Persönliche Claude-Skills und ihre Spezifikationen.

## Aufbau

| Ordner | Inhalt |
| --- | --- |
| `skills/` | die gebauten Skills (je ein Ordner mit `SKILL.md`) |
| `specs/` | Spezifikationen, Spec 00 ist die gemeinsame Grundlage |
| `evals/` | Eval-Definitionen und Fixtures |
| `evalkit/` | der geteilte Eval-Harness |
| `docs/` | Konventionen und Pläne |
| `.claude/skills/` | generierte Projekt-Kopien für die Arbeit an diesem Repo, nie von Hand ändern |
| `scripts/` | Repo-Werkzeuge, darunter `sync_skills.py` für die Projekt-Kopien |

## Als Plugins installieren

Das Repo ist ein Claude-Code-Marketplace (`.claude-plugin/marketplace.json`) mit drei
Plugins. Alle nehmen die Repo-Wurzel als Quelle und laden nur die Skills ihrer
`skills`-Liste; installiert heißen sie mit dem Plugin als Namensraum, etwa
`cc-dev:handoff`. Ab Claude Code 2.1.275 installiert je Plugin eine Zeile Marketplace
und Plugin zusammen:

- `/plugin install cc-dev --marketplace ferdinand-o/cc-skills` — Entwicklung, immer an:
  architecture-map, debug-ledger, dev-report, feature-spec, handoff,
  rest-api-architect, review-context, setup-repo, setup-user, sql-schema-architect,
  subagent-dev, testing-strategy. setup-user und setup-repo laufen nur als
  `/cc-dev:setup-user` und `/cc-dev:setup-repo`.
- `/plugin install cc-ui --marketplace ferdinand-o/cc-skills` — UI, **standardmäßig
  aus** (`defaultEnabled: false`): enterprise-ui, mobile-audit, motion-landing,
  ui-architect. Je
  Frontend-Repo in dessen `.claude/settings.json` einschalten, mit
  `"enabledPlugins": {"cc-ui@cc-skills": true}`; die Projekt-Einstellung gewinnt
  gegen das `false`, das die Installation in die User-Settings schreibt.
- `/plugin install cc-knowledge --marketplace ferdinand-o/cc-skills` — Wissen, immer
  an: exercise-forge, explain, human-prose, learning-coach, verified-research,
  visual-summary.

Mit älteren Versionen erst `/plugin marketplace add ferdinand-o/cc-skills`, dann
`/plugin install cc-dev@cc-skills` und so weiter. Neue Commits holt
`/plugin marketplace update cc-skills`, danach `/reload-plugins`.

**Umstieg vom alten Plugin `cc-skills`.** Bis Spec 20 war die ganze Sammlung ein Plugin
`cc-skills@cc-skills`. Das Manifest führt es unter `renames` als entfernt
(`"cc-skills": null`); `/plugin marketplace update cc-skills` nimmt es deshalb heraus.
Danach die neuen Plugins installieren:

```
/plugin marketplace update cc-skills
/plugin install cc-dev@cc-skills
/plugin install cc-ui@cc-skills
/plugin install cc-knowledge@cc-skills
```

**In keinem Plugin** stehen drei Skills, je mit Grund in `.claude-plugin/excluded.json`:

- impl-plan und skill-forge gelten nur für Specs und Skills dieser Sammlung. Sie liegen
  nur als Projekt-Kopie unter `.claude/skills/` und laden, wenn Claude Code in diesem
  Repo läuft.
- cad-parts ist ausgeschlossen, weil es einen stl-cad-server als MCP-Server braucht.

**Projekt-Kopien.** `.claude/skills/` hält zehn Skills für die Arbeit an diesem Repo:
impl-plan, skill-forge und acht aus `cc-dev` ohne rest-api-architect und
sql-schema-architect. Original ist immer `skills/<name>/`; `scripts/sync_skills.py`
spiegelt die Skills seiner Tabelle `PROJECT_SKILLS` dorthin, und
`python3 scripts/sync_skills.py --check` meldet jede abweichende Kopie. Die committete
`.claude/settings.json` schaltet `cc-dev@cc-skills` in diesem Repo aus, damit die acht
nicht doppelt erscheinen.

`tests/test_marketplace.py` hält Manifest, `excluded.json` und Kopien mit `skills/`
synchron: Eine neue Skill steht in genau einer `skills`-Liste oder mit Grund in
`.claude-plugin/excluded.json`, sonst ist der Test rot; dieselbe Zuordnung prüft die
Lint-Regel `plugin-membership` von skill-forge.

## Evals laufen lassen

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest                                  # Harness-Unit-Tests
.venv/bin/python run_evals.py --class contract    # billige Contract-Evals
.venv/bin/python run_evals.py --skill handoff     # alles für eine Skill
.venv/bin/python run_evals.py --skill handoff --without-skill   # Baseline: dieselben Evals, nichts installiert
```

Exit-Codes: `0` alles grün, `1` mindestens ein Eval gefallen, `2` Harness-Fehler.
Mit `--without-skill` umgekehrt: `1`, sobald ein Eval ohne Skill grün ist (er misst
nichts, was die Skill beiträgt), `0`, wenn alle rot sind. Ein Lauf, in dem der Agent
die Skill nicht sah (mit Skill) oder trotzdem sah (ohne Skill), ist `2`, kein Ergebnis.

## Routing

Welche Skill für welchen Anlass — die zentrale Matrix aus Spec 00 §5. Jede
Description trägt zusätzlich eine Abgrenzungsklausel gegen ihre zwei stärksten
Konkurrenten. Mit `(geplant)` markierte Skills sind spezifiziert, aber noch
nicht gebaut — die Matrix beschreibt den Zielzustand.

| Anlass | zuständig | nicht |
| --- | --- | --- |
| neues Feature, Codebase existiert | feature-spec | brainstorming — die eigene Profil-Skill, nicht superpowers (kein Codebase-Bezug), writing-plans (das *Wie* danach) |
| Bug, Testfehler | debug-ledger | feature-spec |
| Testplan, Repo-Typ-Frage | testing-strategy | test-driven-development (Zyklus *während* der Implementierung), feature-spec *(geplant)* (erzeugt die Test-Stubs, testing-strategy implementiert sie aus) |
| Diff prüfen | `/code-review` (mitgeliefert) | eigene Review-Skill — siehe Spec 04, Zuschnitt offen |
| Sicherheit | `/security-review`, trailofbits | alle eigenen Skills |
| UI: Stil und Tokens | ui-architect | enterprise-ui (Produktoberfläche), motion-landing (Bewegung) |
| UI: Produktoberfläche, Tabellen, Formulare | enterprise-ui | ui-architect (Marketing/Brand) |
| Landing-Page-Bewegung | motion-landing *(geplant)* | ui-architect (Stil/Tokens), enterprise-ui |
| mobil kaputt, „geht das auf dem Handy?" | mobile-audit | enterprise-ui/ui-architect/motion-landing — die *bauen* mobil mit `references/mobile.md`, mobile-audit prueft nur |
| ad-hoc „fass zusammen" | visual-summary | dev-report (periodisch), handoff (Sitzungsende) |
| Konzept/Thema erklären (kein Code) | explain | learning-coach (Session mit Abruf), visual-summary (verdichtet Vorliegendes), architecture-map (Codebase) |
| Implementierungsplan zu einer Spec | impl-plan | superpowers:writing-plans (fremde Repos), brainstorming — die eigene Profil-Skill, nicht superpowers (die Spec davor), subagent-dev (zerlegt und dispatcht den fertigen Plan) |
| Skill bauen oder ändern | skill-forge | skill-creator (außerhalb dieser Sammlung, eigenes Eval-Schema), superpowers:writing-skills (Disziplin-Skills mit Druckszenarien), impl-plan (nur der Plan) |
| Text schreiben oder überarbeiten, der nicht nach Modell klingen soll | human-prose | setup-writing-style (baut das Stimmprofil, im Nutzerprofil), visual-summary (verdichtet, ändert keinen Stil), explain (erklärt mit eigenem Antwortvertrag) |
| Sitzungsende, Übergabe | handoff | visual-summary, dev-report |
| eigenen Claude-Code-User-Scope einrichten oder prüfen | setup-user | `/statusline` (Statusline nach Wunsch), setup-repo (Repo, Cloud, CI), handoff (sichert den Stand) |
| ein Repo für Claude Code einrichten oder prüfen | setup-repo | setup-user (persönlicher User-Scope), testing-strategy (welche Tests fehlen), `/init` (CLAUDE.md ohne Beleg) |

## Konventionen

- [Artefakt-Kopfzeile und Konsumenten-Regel](docs/artifact-header.md)
- [Spec 00 — Artefakt-Vertrag, Evals, Tiers und Routing](specs/Spec%2000%20%E2%80%93%20skill-foundation.md)
- [Bekannte Grenzen des Eval-Harness](docs/known-limits.md)
