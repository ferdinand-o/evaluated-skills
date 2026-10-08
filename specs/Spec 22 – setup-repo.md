# Spec 22: setup-repo — ein Repo, in dem Claude weiß, wann es fertig ist und wann eine Arbeit ein neues Ziel ist

Skill-Spezifikation · Zyklus 22 · Entscheidung: alles, was in Cloud, CI und jedem Clone gelten muss, liegt im Repo; Ziele leben in einem Ledger plus immer geladener Regel plus Bereichs-Hook, nicht in einer Skill, weil eine Regel immer gilt und eine Skill erst ausgelöst werden muss · Abgeglichen mit Spec 00 · Überarbeitet nach unabhängigem Review

## Problem

Der Nutzer will Repos nach Best Practice einrichten: `.claude`-Ordner, aus dem Repo
erarbeitete Rules, Goal Management, eine Review-Herangehensweise je Tech-Stack
(Gespräch vom 2026-10-07). Beim Goal Management will er beides — Definition of Done
mit Verifikation und Projektziele bzw. Backlog — und dass Claude während der
Entwicklung selbst erkennt, wann eine Arbeit ein neues Ziel ist.

Fünf Messungen aus der Claude-Code-Doku bestimmen den Zuschnitt:

- **Cloud-Sessions lesen nur das Repo, und Plugins laden dort nicht.** In einer Session
  mit einem Repo wird `.claude/settings.json` gelesen, User- und lokale Settings sind
  „not read"; in einer Session mit mehreren Repos nur `enabledPlugins` und
  `extraKnownMarketplaces`. „Cloud sessions additionally load project skills committed
  to the cloned repository's `.claude/skills/`", Plugins aus Repo- oder User-Settings
  „don't load in cloud sessions" (settings, skills).
- **`/goal` gilt nur für eine Session.** „it's active for the current session only";
  „Running `/clear` … also removes any active goal" (goal). Ein Resume stellt ein
  aktives Ziel wieder her. Der Evaluator „doesn't run commands or read files
  independently".
- **CLAUDE.md verdrängt `AGENTS.md`.** „By default, Claude reads `AGENTS.md` only when
  you have no `CLAUDE.md` in your working directory or above it"; mitgezählt werden
  auch `.claude/CLAUDE.md` und `CLAUDE.local.md` (memory, „When Claude Code reads
  AGENTS.md").
- **Zu lange Anweisungen werden ignoriert.** „target under 200 lines per CLAUDE.md
  file"; Regeln mit `paths` laden nur bei passenden Dateien; importierte Dateien laden
  beim Start mit (memory).
- **`claude -p` nutzt Projekt-Hooks, aber keine Projekt-Freigaben.** „a `-p` session
  runs the hooks in a project's `.claude/settings.json` … even in a folder you've never
  trusted" (headless); `permissions.allow` aus dem Repo ist dort „Not used" (permissions,
  „What runs before you trust a folder").

Die Doku stellt eine ausführbare Prüfung als den Hebel für unbeaufsichtigte Arbeit dar:
„Give Claude a check it can run … It's the difference between a session you watch and
one you walk away from" (best-practices). Der Eval-Harness dieser Sammlung schließt
heute alles unter `.claude/` aus (`EXCLUDED_PREFIXES = (".git/", ".claude/")` in
`evalkit/assertions.py`); jede Assertion dorthin endet als Harness-Fehler.

## Constraints

Claude-Code-spezifisch. Fünf Abweichungen von Spec 00, alle hier begründet:

1. `disable-model-invocation: true` im Frontmatter (Liste `CLAUDE_CODE_ONLY`, Spec 21).
2. Ablage unter `.claude/` für Settings, Rules, Agents und Hooks — Claude-Code-Orte,
   keine Skill-Artefakte nach Spec 00 §1. Ephemera liegen unter `.skills/cache/setup-repo/`.
3. Spec 00 sagt: Skills „installieren aber nie selbst in fremde `settings.json`", Hooks
   bleiben opt-in. Diese Skill schreibt die Repo-Settings nur nach gezeigtem und
   bestätigtem Plan, und jeder Hook ist im Plan einzeln abwählbar. Der Bereichs-Hook ist
   vorausgewählt, weil der Nutzer will, dass Claude neue Ziele selbst erkennt; der
   Verifikations-Hook ist abgewählt.
4. `.claude/settings.json` und die kopierten Hook-Skripte tragen keine Kopfzeile; JSON
   hat keinen Platz dafür, und die Skripte erkennt `check` per Inhalts-Hash gegen die
   Assets.
5. `docs/goals.md` ist nutzergepflegt und maschinenlesbar, also nach Spec 00 §1 eher
   Konfiguration; es liegt trotzdem unter `docs/`, weil Menschen es lesen und pflegen
   sollen.

Alle Skripte Tier 1 und plattformübergreifend; Laufzeitskripte werden ins Repo kopiert
(`.claude/hooks/`) und über `"$CLAUDE_PROJECT_DIR"/.claude/hooks/…` aufgerufen (so zeigt
es hooks-guide), damit sie in Cloud-Sessions ohne Plugin laufen. Gate-Grade:
Bestätigung vor `apply` G1; Hash über Plan und Bestand G2 wie Spec 21; der
Bereichs-Hook meldet per `additionalContext`, hält kein Turn-Ende an, löst aber einen
Folgeturn aus; der optionale Verifikations-Hook ist G3. Die Skill committet nie.
Dateien mit Frontmatter in Zeile 1 (Rules mit `paths`, `.claude/agents/reviewer.md`)
tragen die Kopfzeile als erste Zeile nach dem Frontmatter; dafür kommt eine „Begründete
Ausnahme" mit den wörtlichen Asset-Pfaden in `docs/artifact-header.md`. Plugin: `cc-dev`
(Spec 20). Die Erkennung ist eigen (`detect_repo.py`), weil `detect_stack.py` aus
testing-strategy zwar Test-Runner und Frontend-SPAs kennt, aber weder Delphi noch
Makefile oder Agent-Dateien.

## Approach

**Eiserne Regel:** *Kein Verifikationsbefehl und keine aus dem Repo geerntete Regel ohne
Beleg, kein Ziel ohne prüfbares „Fertig wenn" — was fehlt, steht als „ungeprüft" da, nie
erfunden.* Die Zielregel selbst ist Inhalt der Skill, keine geerntete Regel.

### Skill-Struktur

```
skills/setup-repo/
├── SKILL.md                         Modi plan/apply/check, Eiserne Regel, Contract, Abgrenzung
├── references/rules-harvest.md      Kandidat → ableitbar / Werkzeug / Regel; paths wo möglich; Quelle je Regel
├── references/goals.md              Ledger-Schema, Glob-Dialekt der Bereiche, Klassifikation entdeckter Arbeit
├── references/review/python.md      Konformitäts-Prüfpunkte je Stack; fließen beim apply in reviewer.md ein
├── references/review/typescript.md
├── references/review/delphi.md
├── references/review/generic.md
├── assets/CLAUDE.md                 Gerüst: Kopfzeile, Zeile „Verifikation: …", @AGENTS.md falls vorhanden
├── assets/goals.md                  Ledger-Gerüst für docs/goals.md, Kopfzeile schema 1
├── assets/rules/goals.md            immer geladene Zielregel ≤ 25 Zeilen, Kopfzeile in Zeile 1
├── assets/agents/reviewer.md        Ziel-Reviewer: Diff gegen Fertig-wenn, Bereich und Stack-Prüfpunkte; Kopfzeile nach dem Frontmatter
├── assets/runtime/goal_scope.py     Tier 1 — Stop-Hook: Änderungen außerhalb der Bereiche → additionalContext, einmal je Dateimenge
├── assets/runtime/verify_stop.py    Tier 1 — optionaler Stop-Hook: Verifikationsbefehl; höchstens drei Blocks in Folge
├── assets/hooks/goal-scope.json     Fragment für .claude/settings.json; meldet
├── assets/hooks/verify-stop.json    Fragment, opt-in; G3
├── scripts/detect_repo.py           Tier 1 — Sprachen, Frontend, Runner, Linter-/Formatter-Konfiguration, Tests, CI, CLAUDE-Dateien, AGENTS.md
├── scripts/harvest_rules.py         Tier 1 — Regelkandidaten mit Quelle aus Konfigurationen, CONTRIBUTING, Commit-Betreffs → candidates.json
├── scripts/plan_repo.py             Tier 1 — liest candidates.json mit Klasse je Kandidat; Plan mit Hash; Budget samt Importen
└── scripts/apply_repo.py            Tier 1 — wendet nur einen Plan mit passendem Hash an; prüft Hooks mit Beispiel-Payload

evalkit/assertions.py, evalkit/workspace.py   EXCLUDED_PREFIXES (".git/", ".claude/skills/"); Docstrings und Fehlertext nachgezogen
tests/test_assertions.py, tests/test_workspace.py   .claude/settings.json beobachtet, .claude/skills/ nicht
docs/artifact-header.md              Begründete Ausnahme: Kopfzeile nach dem Frontmatter, wörtlich mit skills/setup-repo/assets/agents/reviewer.md
skills/handoff/SKILL.md, skills/testing-strategy/SKILL.md, skills/review-context/SKILL.md, skills/feature-spec/SKILL.md   Rückverweis, der setup-repo wörtlich nennt
scripts/sync_plugins.py, plugins/cc-dev/skills/setup-repo/   Zuordnung zu cc-dev (Spec 20)
.gitignore                           !evals/fixtures/*/.skills/cache/setup-repo/ — Fixture-Pläne sind versioniert
specs/Spec 00 – skill-foundation.md, README.md   Matrixzeile setup-repo; README „Aufbau" nennt evals-templates/
docs/known-limits.md                 Abschnitt setup-repo
docs/superpowers/reports/setup-repo-report.md   Report mit „Was nicht gemessen wurde"
evals/setup-repo/evals.json          sechs Evals, siehe unten
evals/fixtures/sr-aligned/, sr-fresh/, sr-notests/, sr-planned/   je fixture.json mit "git": true
evals-templates/setup-repo/evals.json, evals-templates/fixtures/sr-goals-seeded/   Vorlagen-Messung der Zielregel
tests/test_setup_repo_*.py           siehe Tests (Repo)
```

Im Zielrepo entsteht nach `apply`:

```
CLAUDE.md                            neu mit Kopfzeile, oder bestehende nur um bestätigte Abschnitte ergänzt
.claude/settings.json                gemischt: permissions (allow: Verifikation, Tests, Lint; deny: Secrets), hooks
.claude/settings.local.json          enabledPlugins für dieses Repo (persönlich, nicht committet)
.claude/rules/goals.md, weitere aus Belegen
.claude/agents/reviewer.md           mit den Prüfpunkten des erkannten Stacks
.claude/hooks/goal_scope.py, optional verify_stop.py
docs/goals.md
.gitignore                           Zeile .skills/cache/
```

### Ablauf

1. **Erkennen.** `detect_repo.py` schreibt `.skills/cache/setup-repo/detect.json`.
2. **plan (Default).** `harvest_rules.py` schreibt `candidates.json`; Claude trägt je
   Kandidat die Klasse ein: ableitbar aus dem Code (fällt weg), schon durch ein
   konfiguriertes Werkzeug geprüft (keine Regel, im Bericht als „Werkzeug"), sonst Regel —
   mit `paths`, wo sie nur einen Teil betrifft. `plan_repo.py` schreibt
   `.skills/cache/setup-repo/plan.md`: Diff, Quelle und Klasse je Kandidat, Budget,
   abwählbare Hooks, Hash. Der Hash läuft über Plantext und Inhalte der Zieldateien, mit
   Pfaden relativ zur Repo-Wurzel, ohne HEAD-SHA, ohne `.claude/skills/`.
3. **Verifikation festlegen.** Aus vorhandenen Einträgen (`Makefile`, `package.json`-
   Scripts, `pyproject.toml`, `justfile`): der Befehl, der Lint, Typprüfung und schnelle
   Tests verbindet, notfalls zusammengesetzt aus vorhandenen Zielen (`make lint && make
   test`). Bei Delphi wird der Build aus der `.dproj` abgeleitet und im Bericht als
   „abgeleitet" markiert. Gibt es nichts, steht in der CLAUDE.md „Verifikation: keine —
   ungeprüft", und der Bericht nennt `testing-strategy`. Neue Runner-Ziele legt die Skill
   nicht an.
4. **apply** in einem späteren Aufruf nach Bestätigung: `apply_repo.py --plan
   .skills/cache/setup-repo/plan.md`. Verweigert wird nur, wenn eine Zieldatei
   uncommittete Änderungen hat. Danach jeden Hook mit Beispiel-Payload ausführen.
   Existiert `AGENTS.md` ohne eine der drei CLAUDE-Dateien, enthält die neue CLAUDE.md
   direkt unter der Kopfzeile `@AGENTS.md`; das Budget zählt die importierten Zeilen mit.
5. **check.** Bestand gegen Plan; Budget; Hooks laufen; Ledger-Kopfzeile lesbar. Liest
   die Klassen aus dem letzten Plan, klassifiziert nicht neu; schreibt `check.md`.

Ohne Antwort auf Rückfragen (`claude -p`) nimmt der Plan Annahmen und führt sie im
Bericht; `apply` wendet nur einen vorhandenen Plan an.

**Ziele.** `docs/goals.md` hat drei Tabellen: *Aktiv* (`id`, Ziel, Fertig wenn, Bereich,
seit), *Kandidaten* (`id`, Kandidat, entdeckt bei, Grund, am), *Erledigt* (`id`, Ziel,
Beleg, am; die letzten zehn, Älteres liegt in Git). *Aktiv* plus *Kandidaten* sind der
Backlog. Der Bereich sind Pfad-Globs mit `**`, getrennt durch Kommas, in einer Zelle.
Beim Einrichten entsteht der Ledger leer; die Skill erfindet keine Ziele. „Fertig wenn"
folgt der `/goal`-Doku: ein messbarer Endzustand, die Prüfung, die ihn zeigt, und was
sich nicht ändern darf.

Die Regel `.claude/rules/goals.md` ordnet jede während der Arbeit entdeckte Aufgabe in
genau eine von drei Klassen:

1. **Teil des Ziels** — nötig, damit „Fertig wenn" eintritt: erledigen.
2. **Trivial** — in einer Datei, die die aktuelle Aufgabe ohnehin ändert, höchstens fünf
   Zeilen, kein geändertes Verhalten: erledigen und im Turn-Ende nennen.
3. **Neues Ziel** — alles andere: nicht umsetzen, als Kandidat eintragen, im Turn-Ende
   nennen. Der Nutzer befördert Kandidaten nach *Aktiv*.

Ein Prompt wird nur dann ein Eintrag unter *Aktiv*, wenn er mehr verlangt als die
Trivial-Schwelle oder der Nutzer ihn ausdrücklich ein Ziel nennt; dann schlägt Claude
die passende `/goal`-Zeile aus „Fertig wenn" vor. Ist ein Ziel erreicht, wandert es mit
Beleg (Befehl und Ergebnis) nach *Erledigt*.

Der Hook `goal_scope.py` macht die dritte Klasse prüfbar, soweit Dateien sie zeigen. Er
merkt sich beim ersten Lauf einer Session den HEAD als Basis — Commits schon im ersten
Turn sieht er deshalb nicht (Zustand
`.skills/cache/setup-repo/goal-scope.json`, Schlüssel `session_id`) und vergleicht am
`Stop`-Ereignis `git diff <basis> --name-only -z` plus unversionierte Dateien
(`git ls-files --others --exclude-standard -z`) mit den Bereichen aller aktiven Ziele;
so sieht er auch Commits der Session. Ausgenommen sind `docs/goals.md`, `handoff.md`,
`docs/debugging/`, `docs/decisions.md`, `docs/specs/wip/`, `.claude/skills/` und
`.skills/` — Artefakte der Sammlung, die keine Zielarbeit sind. Liegen Änderungen
außerhalb und wurden sie für diese Dateimenge noch nicht gemeldet, gibt er
`hookSpecificOutput.additionalContext` aus („[setup-repo] Geändert außerhalb des
Bereichs von G3: src/dates.py. Laut Zielregel ist das Teil des Ziels, trivial,
vom Nutzer verlangt oder ein Kandidat."). Laut Doku setzt das das Gespräch fort (hooks,
„Stop"). Ohne Repo-Commit, ohne `docs/goals.md`, ohne aktives Ziel schweigt er; fehlt
die Kopfzeile des Ledgers oder ist sie unbekannt, schreibt er das auf stderr und
schweigt sonst (Konsumenten-Regel).

**Verifikations-Hook (opt-in).** `verify_stop.py` hält das Turn-Ende an, solange der
Verifikationsbefehl rot ist, höchstens dreimal in Folge je Session (eigener Zähler im
Zustand, unabhängig von `stop_hook_active`); danach lässt er das Ende zu und meldet
„rot nach drei Versuchen". Ist der Befehl nicht ausführbar (Programm fehlt), endet er
mit 0 und „ungeprüft — <Werkzeug> fehlt", etwa beim Delphi-Build auf der Linux-Devbox.
Die Claude-Code-Obergrenze von acht Blocks ohne Tool-Aufruf (hooks-guide) bleibt als
zweites Netz.

**Review.** Der Ziel-Reviewer prüft einen Diff gegen „Fertig wenn" und „Bereich" des
Ziels und gegen die Konformitäts-Prüfpunkte des erkannten Stacks, die `apply` aus
`references/review/` in `reviewer.md` schreibt (etwa: neue öffentliche Funktion hat
einen Test, neue Abhängigkeit steht im Manifest). Jeder Befund trägt ein
Failure-Szenario. Fehler im Code selbst sucht er nicht — das ist `/code-review`,
„reviews the current diff for bugs" (best-practices). Den offenen Zuschnitt von Spec 04
berührt das nicht. Das Kontextpaket von `review-context` liest er nur, wenn der
Hauptagent es im selben Lauf erzeugt und den Pfad übergeben hat: Die Datei trägt `_meta`,
aber nur einen symbolischen Bereich wie `HEAD~1..HEAD`, keinen SHA.

**Plugins je Repo.** `enabledPlugins` nach Spec 20 kommt in `.claude/settings.local.json`,
nicht in die committete Datei — die Plugins stammen aus der persönlichen Sammlung des
Nutzers und laden in der Cloud ohnehin nicht. `cc-ui` an, wenn `detect_repo.py` ein
Frontend erkennt; `cc-meta` an im Repo `cc-skills`.

### Contract

- **Belegt oder ungeprüft.** Jeder Verifikationsbefehl stammt aus vorhandenen
  Runner-Einträgen oder ist als abgeleitet markiert; jede geerntete Regel hat im Bericht
  Quelle und Klasse; ohne Beleg „ungeprüft".
- **Werkzeug vor Prosa.** Was ein schon konfigurierter Linter, Formatter oder Typprüfer
  prüft, wird keine Regelzeile — weder in Rules noch in der CLAUDE.md.
- **Budget.** Immer geladene Zeilen (CLAUDE.md samt Importen plus Rules ohne `paths`)
  ≤ 150; `plan_repo.py` meldet Überschreitung als Befund (G2).
- **AGENTS.md bleibt lesbar.** Eine neue CLAUDE.md neben `AGENTS.md` importiert es.
- **Mischen, nie überschreiben; kein Commit.** Bestehende `.claude/settings.json` wird
  gemischt wie in Spec 21; `apply` verweigert Zieldateien mit uncommitteten Änderungen und
  committet nie.
- **Neue Ziele werden Kandidaten.** Die Regel verlangt die Dreiteilung (G1); der Hook
  meldet Dateien außerhalb der Bereiche und löst damit einen Folgeturn aus, blockiert aber
  nichts.
- **Anti-Zeremonie-Fall:** `check` auf ein eingerichtetes Repo ändert nur `check.md` und
  meldet „keine Abweichung"; ein Repo ohne Tests bekommt keinen erfundenen Testbefehl; ein
  Tippfehler-Prompt erzeugt keine Ledger-Zeile (Vorlagen-Messung).

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| welche Tests fehlen, Teststrategie | **testing-strategy** | setup-repo übernimmt nur vorhandene Befehle |
| Kontextpaket für einen Diff | **review-context** | setup-repo richtet nur den Ziel-Reviewer ein, der es liest |
| Fehler im Code eines Diffs finden | `/code-review` | der Ziel-Reviewer prüft Zielerfüllung, Bereich und Konformität |
| Sitzungsstand übergeben | **handoff** | `docs/goals.md` ist Zielstand über Sitzungen, `handoff.md` der Stand einer Sitzung |
| neues Feature spezifizieren | **feature-spec** | ein Ziel nennt Fertig-wenn und Bereich, keine Spec |
| eigenen User-Scope einrichten | setup-user (21) | setup-repo — was nur für mich gilt, gehört nicht ins committete Repo |

Rückverweise beim Bau, je mit dem Wort setup-repo: `handoff` nennt `docs/goals.md` unter
„Einstiegspunkte", wenn es existiert (Konsumenten-Regel, Kopfzeile lesen);
`testing-strategy`, `review-context` und `feature-spec` bekommen je einen Halbsatz in
ihrer Abgrenzung. Kein Eval-Pattern dieser vier trifft einen solchen Halbsatz (im Review
geprüft), `evals_due` entsteht also nicht.

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_claude_dir_observed_except_skills` | `tests/test_assertions.py`, `tests/test_workspace.py` | `.claude/settings.json` im Snapshot und prüfbar; `.claude/skills/` weiter ausgenommen; Fehlertext nennt `.claude/skills/` |
| `test_detect_python_ts_delphi_frontend_none` | `tests/test_setup_repo_detect.py` | Sprache, Frontend, Runner und Tests in Mini-Fixtures; Delphi über `.dproj`; alle drei CLAUDE-Dateien |
| `test_harvest_marks_tool_rules` | `tests/test_setup_repo_harvest.py` | `line-length` aus ruff-Konfiguration wird Kandidat mit Quelle; `plan_repo.py` macht bei Klasse Werkzeug keine Regelzeile daraus |
| `test_budget_counts_unscoped_rules_and_imports` | `tests/test_setup_repo_plan.py` | Rules mit `paths` zählen nicht, importiertes `AGENTS.md` zählt |
| `test_plan_hash_is_path_and_head_neutral` | dito | dasselbe Repo an zwei Orten, mit verschiedenem HEAD und installierter Skill → gleicher Hash |
| `test_agents_md_is_imported` | dito | `AGENTS.md` ohne CLAUDE-Datei → Plan enthält `@AGENTS.md` unter der Kopfzeile |
| `test_apply_refuses_dirty_target_and_changed_plan` | `tests/test_setup_repo_apply.py` | uncommittete Zieldatei oder geänderter Plan → Abbruch; unversionierter `.claude/skills/` stört nicht |
| `test_apply_merges_existing_settings` | dito | vorhandene `hooks.Stop` und `permissions` bleiben, Listen vereinigt |
| `test_fixture_plans_are_current` | `tests/test_setup_repo_fixtures.py` | versionierte Pläne in `sr-planned` und `sr-aligned` gleichen neu erzeugten Plänen; die Bestandsdateien in `sr-aligned` gleichen den Assets |
| `test_goal_scope_reports_once_incl_staged_and_committed` | `tests/test_setup_repo_goal_scope.py` | gestagete, ungestagete, committete Datei außerhalb → eine Meldung; gleiche Dateimenge erneut → keine; Nicht-ASCII-Name |
| `test_goal_scope_ignores_house_artifacts` | dito | nur `docs/goals.md`, `handoff.md`, `.claude/skills/`, `.skills/` geändert → keine Meldung |
| `test_goal_scope_silent_without_goals_or_commit` | dito | kein `docs/goals.md`, kein aktives Ziel, Repo ohne Commit, fremde Kopfzeile → keine Meldung, stderr bei fremder Kopfzeile |
| `test_goal_scope_output_shape` | dito | `hookSpecificOutput.additionalContext`, Text beginnt mit `[setup-repo]` |
| `test_verify_stop_counts_and_missing_tool` | `tests/test_setup_repo_verify_stop.py` | grün → 0; rot → 2 bis zum dritten Mal, dann 0 mit „rot nach drei Versuchen"; fehlendes Programm → 0 mit „ungeprüft" |

### Evals

Voraussetzung: die Harness-Änderung oben. Die Plan-Evals laufen auf Fixtures ohne Plan
und prüfen den Bericht; nur Eval 6 wendet einen versionierten Plan an. Ohne installierte
Skill ändert ein Agent auf `/setup-repo` nichts (für `/setup-user` im Review gemessen,
hier übertragen), deshalb bindet jeder Eval an ein Artefakt, das nur die Skill erzeugt.
In der Tabelle steht `\|` für ein Regex-`|`; in `evals.json` wird es ein einfaches `|`.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-check-on-aligned-repo-changes-nothing` | contract | `sr-aligned` | `file_exists` und `artifact_header` auf `.skills/cache/setup-repo/check.md`; `file_matches` dort `keine Abweichung`; `file_unchanged` einzeln auf `CLAUDE.md`, `.claude/settings.json`, `.claude/rules/goals.md`, `.claude/agents/reviewer.md`, `.claude/hooks/goal_scope.py`, `docs/goals.md`; `git_head_unchanged` | `check.md` mit Kopfzeile entsteht nur durch die Skill; die Fixture hat keine offenen Kandidaten, damit die Klassen des letzten Plans genügen |
| 2 | `plan-is-default-and-writes-only-report` | contract | `sr-fresh` | `file_exists` `.skills/cache/setup-repo/plan.md` und `detect.json`; `file_absent` `CLAUDE.md` und `.claude/settings.json` | ohne Skill entsteht weder Plan noch `detect.json` |
| 3 | `plan-takes-verify-command-from-the-repo` | contract | `sr-fresh` | `file_matches` Plan auf `Verifikation:.*make check` | schwach: ein Agent, der das Makefile liest, nennt auch `make check`; es unterscheidet, dass der Satz im Plan der Skill steht |
| 4 | `plan-without-tests-says-unverified` | contract | `sr-notests` | `file_matches` Plan auf `Verifikation: keine` | ohne Skill kein Plan; mit Skill der Wortlaut der Doktrin statt eines erfundenen Befehls |
| 5 | `plan-classifies-configured-tool-rule` | contract | `sr-fresh` | `file_matches` Plan auf `(?i)line.?length.{0,120}Werkzeug` — der Plan führt je Kandidat eine Zeile „Kandidat · Quelle · Klasse" in dieser Reihenfolge | die Fixture trägt `line-length = 100` in `pyproject.toml`; nur die Klassifikation der Skill schreibt „Werkzeug" daneben |
| 6 | `apply-executes-plan-faithfully` | contract | `sr-planned` | `file_matches` `CLAUDE.md` auf `Verifikation:.*make check`; `must_not` `file_matches` `CLAUDE.md` auf `(?i)line.?length\|100 Zeichen`; `file_max_lines` `CLAUDE.md` 125; `file_matches` `.claude/settings.json` auf `make check` und auf `goal_scope`; `file_exists` und `artifact_header` auf `docs/goals.md`; `file_matches` `docs/goals.md` auf `## Kandidaten`; `file_matches` `.claude/rules/goals.md` auf `Kandidat`; `git_head_unchanged` | ohne Skill bleibt die Fixture unverändert; gemessen wird, dass `apply_repo.py` den versionierten Plan treu umsetzt, nicht die Klassifikation (die messen 3 bis 5) |

Prompts: 1 „/setup-repo check", 2 bis 5 „/setup-repo", 6 „/setup-repo apply — den Plan
in .skills/cache/setup-repo/plan.md habe ich gelesen und bestätige ihn". Das Budget in
Eval 6 ist 150 minus die 25 Zeilen der Zielregel. `sr-planned` bringt den Plan unter
`.skills/cache/setup-repo/plan.md` mit; die `.gitignore`-Ausnahme oben versioniert ihn.

### Vorlagen-Messung der Zielregel (außerhalb des Eval-Vertrags)

Ob Claude entdeckte Arbeit tatsächlich als Kandidat einträgt, misst kein Eval dieser
Skill: Rules laden beim Sessionstart, die Regel muss also schon in der Fixture liegen.
Ein solcher Lauf wäre ohne installierte Skill genauso grün und misst nach Spec 18 nichts
über die Skill — er misst die Vorlage. Deshalb liegt er in
`evals-templates/setup-repo/evals.json` mit Fixture
`evals-templates/fixtures/sr-goals-seeded/` und läuft mit `run_evals.py --evals-dir
evals-templates`, von Hand, Ergebnis als Quote im Report. Fixture: eingerichtetes Repo,
aktives Ziel „Tippfehler in greet.py beheben" mit Bereich `src/greet.py`, ein
offensichtlicher, nicht verwandter Fehler in `src/dates.py`. Zwei Fälle:

- Prompt „Behebe den Tippfehler in greet.py (Ziel G1)." — erwartet: Zeile unter
  *Kandidaten* mit `dates`, `src/dates.py` unverändert.
- Prompt „Ändere in README.md ‚Helo' zu ‚Hello'." — erwartet: keine neue Zeile unter
  *Aktiv*. Der Hook meldet hier README.md als außerhalb des Bereichs; die Regel nennt
  „vom Nutzer verlangt" als zulässige Antwort.

Weil `-p` Projekt-Hooks ausführt, läuft `goal_scope.py` mit. Eine Fixture-Variante
`sr-goals-seeded-nohook` ohne Hook-Eintrag trennt Regel und Hook; der Runner kennt keine
Option, Hooks abzuschalten.

## Alternatives considered

**Ziele nur über `/goal`.** Verworfen: `/goal` endet mit einer neuen Session und mit
`/clear`, und der Evaluator liest keine Dateien.

**Ziele in `handoff.md`.** Verworfen: `handoff` schreibt die Datei jedes Mal komplett neu
und besitzt sie allein.

**Zielmanagement als eigene Skill.** Als Projekt-Skill liefe sie sogar in der Cloud.
Verworfen, weil eine Skill erst über ihre Description ausgelöst werden muss — beim
beiläufig entdeckten Nebenbefund passiert das nicht —, während eine Regel ohne `paths`
immer geladen ist. Gewinnt, wenn die Regel über 25 Zeilen wächst.

**Ein prompt-basierter Stop-Hook, der jeden Turn auf neue Ziele beurteilt.** Erkennt mehr
als Dateipfade, kostet aber je Turn einen Modellaufruf und ist stochastisch. Gewinnt, wenn
die Bereichsprüfung in der Vorlagen-Messung zu grob ist.

**Ein neues Runner-Ziel `verify` anlegen.** Ein Eingriff in `Makefile` oder
`package.json`, den der Nutzer nicht bestellt hat. Verworfen.

**Assertions auf Beobachtbares außerhalb von `.claude/` umlegen statt den Harness zu
ändern.** Dann prüfte jeder Eval einen Bericht statt das Ergebnis. Verworfen; im Review
simuliert: Mit `(".git/", ".claude/skills/")` wird kein bestehender Test rot.

**`verify_stop.py` mit frühem Ende bei `stop_hook_active`, wie hooks-guide empfiehlt.**
Dann blockiert er nur einmal und lässt das Turn-Ende danach auch bei Rot zu. Verworfen
zugunsten eines eigenen Zählers mit drei Versuchen; gewinnt, wenn drei Folgeturns zu
teuer sind.

**`/init` statt eigener CLAUDE.md-Erzeugung.** `/init` erzeugt die CLAUDE.md; mit
`CLAUDE_CODE_NEW_INIT=1` führt es laut commands-Doku auch durch Skills, Hooks und
persönliche Memory-Dateien (im Review zitiert). Es kennt weder Budget noch Ledger noch
Bereichs-Hook. Verworfen als alleiniger Weg; die Skill liest eine vorhandene CLAUDE.md
wie jede andere.

## Out of scope

GitHub-Integration (`/install-github-app`, Code Review), `.mcp.json`, LSP-Plugins, das
Schreiben von Tests (`testing-strategy`), Fehlersuche im Code (`/code-review`, Spec 04),
verschachtelte CLAUDE.md-Dateien in Monorepos, die agentische Pipeline auf der Devbox,
ein SHA im Kontextpaket von `review-context` und `docs/goals.md` als Soll-Quelle dort
(beides als Verbesserung für review-context vormerken), das Anlegen neuer
Werkzeug-Konfigurationen.

## Open questions

*Annahme:* Budget 150 immer geladene Zeilen, Zielregel ≤ 25 Zeilen, „trivial" höchstens
fünf Zeilen, *Erledigt* behält zehn, Verifikations-Hook drei Versuche — widersprich,
falls nein.

*Annahme:* Claude kann `/goal` nicht selbst setzen, weil es ein eingebauter Befehl und
keine Skill ist; die Regel lässt Claude die Zeile vorschlagen. Beim Bau messen.

*Annahme:* Das Ledger-Schema bleibt stabil genug für die Devbox-Pipeline; jede
Strukturänderung zählt `schema` hoch. Die Pipeline läuft mit `-p` und bekommt dort die
`permissions.allow`-Regeln des Repos nicht; sie braucht `--allowedTools`, User-Settings
oder den dokumentierten Trust-Eintrag `projects["<path>"].hasTrustDialogAccepted`.
Läuft sie mit `--bare` — laut headless-Doku künftig Standard für `-p` —, lädt sie weder
CLAUDE.md noch Rules noch Hooks; dann wirkt setup-repo dort nicht.

**Welcher Interpreter steht im committeten Hook-Kommando?** Eine Repo-`settings.json`
gilt zugleich für Windows, die Linux-Devbox und die Cloud. Kandidaten: `"shell": "bash"`
mit `python3 … || python …`, oder die Exec-Form mit `"args": []` (hooks-guide), die ein
Skript ohne Shell startet. Auf dem Windows-PC des Nutzers messen, bevor die Fragmente
festgeschrieben werden.

Die Harness-Änderung betrifft alle Skills: Der Judge-Prompt sieht künftig auch geänderte
Dateien unter `.claude/` außer `.claude/skills/`. Vor dem Merge die Contract-Evals aller
Skills einmal fahren.

Was gehört in `references/review/delphi.md`? Der Nutzer kennt Delphi; die Prüfpunkte
sollen von ihm kommen.

Ungemessen bleibt, ob die Bereichsprüfung neue Ziele zuverlässig genug erkennt, und ob
die Stack-Prüfpunkte im Reviewer greifen — kein Eval und kein Test misst das; die
Vorlagen-Messung deckt nur die Zielregel.

## Next steps

Spec 20 und 21 zuerst (Plugin-Quellordner, Lint-Liste `CLAUDE_CODE_ONLY`). Den
Interpreter für Hooks auf dem Windows-PC messen, Prüfpunkte für Delphi beim Nutzer
erfragen. Dann Plan mit `impl-plan` (16) und Bau nach `skill-forge` (17) Schritt 3 bis 7;
danach die Vorlagen-Messung der Zielregel.
