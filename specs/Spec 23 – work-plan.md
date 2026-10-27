# Spec 23: work-plan — ein Plan für fremde Repos, den subagent-dev lesen kann

Skill-Spezifikation · Zyklus 23 · Entscheidung: eine eigene Plan-Skill für Repos außerhalb dieser Sammlung, im Planformat von impl-plan, mit einem lint-fähigen Verifikations-Task statt der vier Pflicht-Tasks der Sammlung; subagent-dev liest beide Kopfzeilen; danach zeigt kein Verweis mehr auf `superpowers:writing-plans` oder `superpowers:subagent-driven-development` · Abgeglichen mit Spec 00 und Spec 20 · Überarbeitet nach unabhängigem Review (2026-10-13: Verifikations-Task mit Files und Interfaces, Verweis-Tabelle um die Description von impl-plan und die dritte Fundstelle in subagent-dev ergänzt, Schwelle vereinheitlicht)

## Problem

Spec 20 macht das Abschalten von superpowers an drei Bedingungen fest; eine davon ist,
dass keine Description eines immer aktiven Plugins `superpowers:` enthält.
`sync_skills.py --report` zählt am 2026-10-13 sechs Fundstellen, alle in `evaluated-dev`:
architecture-map, feature-spec, rest-api-architect und dreimal subagent-dev — vier zeigen
auf `superpowers:writing-plans`, zwei auf `superpowers:subagent-driven-development`. Die
Description von impl-plan nennt `superpowers:writing-plans` ebenfalls; der Bericht zählt
sie nicht, weil impl-plan in keinem Plugin liegt. Dazu kommen Abgrenzungen im Rumpf von
feature-spec, rest-api-architect, architecture-map, subagent-dev und impl-plan sowie fünf
Stellen in README und Spec 00.

Die Lückentabelle in Spec 20 führt `writing-plans` als **Lücke**: `impl-plan` schreibt
Pläne nur zu Specs dieser Sammlung. Es verlangt eine Spec mit Eval-Tabelle, vier
Pflicht-Tasks (Evals, Nachbarn, known-limits, Report) und steht deshalb in
`.claude-plugin/excluded.json`. In einem fremden Repo gibt es nach `feature-spec`, nach
einem Befund von `architecture-map` oder nach einem Brownfield-Bericht von
`rest-api-architect` heute keinen Haus-Weg zum Plan.

Und `subagent-dev` kann einen Plan aus einem fremden Repo nicht prüfen:
`plan_to_tasks.py lint` verlangt die Kopfzeile `skill: impl-plan` und meldet jede andere
als Befund, obwohl die Description „or a superpowers:writing-plans plan" anbietet.

## Constraints

Portables Frontmatter (`name`, `description`). Tier 1 ohne eigenes Skript: Der Lint gehört
`subagent-dev` (Contract von impl-plan), work-plan ruft ihn auf über
`${CLAUDE_SKILL_DIR}/../subagent-dev/scripts/plan_to_tasks.py`. Beide Skills liegen in
`evaluated-dev`, der Verweis überschreitet keine Plugin-Grenze (Spec 20). Im Review nachgemessen:
Nach `claude plugin marketplace add` mit lokalem Pfad und `install evaluated-dev@evaluated-skills`
(CLI 2.1.296) liegt im Plugin-Cache die ganze Repo-Kopie, das Nachbarverzeichnis
`skills/subagent-dev/scripts/` also daneben. Fehlt das Skript (nur work-plan installiert,
claude.ai), heißt die Übergabe „ungeprüft — Lint nicht verfügbar", nie „fertig".
Gate-Grade: Zeigen des Plans G1, Lint G2.

`subagent-dev` selbst ruft seine Skripte heute repo-relativ auf
(`python skills/subagent-dev/scripts/plan_to_tasks.py …`); in einem fremden Repo laufen
`generate` und `verify` deshalb nicht, bis die Folgespec für `${CLAUDE_SKILL_DIR}` umstellt
(Spec 20, Out of scope). work-plan löst den Weg bis zum Lint, nicht bis zum Dispatch;
known-limits sagt das.

Ablage im Zielrepo: `docs/plans/<JJJJ-MM-TT>-<slug>.md` mit Kopfzeile
`<!-- skill: work-plan | schema: 1 | generated: … -->` in Zeile 1. Spec 00 §1 verlangt,
dass der erste Lauf die Anlage ankündigt; *Annahme:* Die Bitte um einen Plan ist die
Einwilligung, und die Antwort nennt den Pfad. Das Planformat (`### Task N:`,
`**Files:**`, `**Interfaces:**`, Checkbox-Steps, Präfixe `fn:`, `token:`, `file:`) ist
dasselbe wie bei impl-plan; Eigentümer bleibt `subagent-dev`. Plugin: `evaluated-dev`.

## Approach

**Eiserne Regel:** *Kein Plan ohne Verifikations-Task und ohne Lint-Lauf — oder ohne den
ausdrücklichen Vermerk „ungeprüft"; und kein Plan für eine Änderung, die keinen braucht.*

### Skill-Struktur

```
skills/work-plan/
├── SKILL.md                         Ablauf, Schwelle, Quellen (feature-spec, architecture-map, rest-api-architect, Auftrag), Verifikations-Task, Lint, Übergabe
├── references/task-patterns.md      Code-Task (fünf Steps), Doku-Task, Verifikations-Task mit Files und Interfaces, Zuschnittsregel, Interface-Vokabular — aus impl-plan übernommen, ohne die Pflicht-Tasks der Sammlung
└── assets/plan-template.md          Kopfzeile skill: work-plan, Goal, Architecture, Spec oder Auftrag, `- Annahme:`-Zeilen, Verifikations-Task als letzter Task

skills/subagent-dev/scripts/plan_to_tasks.py   Kopfzeile impl-plan oder work-plan; für work-plan: Quelle `**Spec:**` oder `**Auftrag:**`, letzter Task „Verifikation", Coverage gegen die Akzeptanzkriterien einer feature-spec-Spec; Docstrings und Hilfetext nennen beide Formate
skills/subagent-dev/SKILL.md         Description und Abgrenzung ohne superpowers; „Plan vorhanden?" nennt impl-plan und work-plan
skills/feature-spec/SKILL.md, skills/architecture-map/SKILL.md, skills/rest-api-architect/SKILL.md, skills/impl-plan/SKILL.md   Verweise auf work-plan statt superpowers:writing-plans; Projekt-Kopien über sync_skills.py
skills/setup-repo/assets/runtime/goal_scope.py, skills/setup-repo/references/goals.md   docs/plans/ als Hausartefakt ausgenommen
.claude-plugin/marketplace.json      work-plan in der skills-Liste von evaluated-dev
specs/Spec 00 – skill-foundation.md, README.md   Routing: writing-plans → work-plan an fünf Stellen, neue Zeile work-plan; README-Liste von evaluated-dev
docs/known-limits.md                 Abschnitt work-plan
docs/superpowers/reports/work-plan-report.md   Report mit „Was nicht gemessen wurde"
evals/work-plan/evals.json           vier Evals, siehe unten
evals/fixtures/wp-small/, wp-spec/, wp-verify/, wp-finding/   je fixture.json mit "git": true
tests/test_subagent_dev_plan_to_tasks.py, tests/test_plans_lint.py, tests/test_marketplace.py, tests/test_setup_repo_goal_scope.py   siehe Tests (Repo)
```

### Ablauf

1. **Anlass prüfen.** Ein Plan lohnt sich, wenn mindestens eines gilt: die Arbeit
   berührt mehr als zwei Dateien, sie schafft eine neue öffentliche Schnittstelle, oder
   ihre Schritte hängen in einer Reihenfolge voneinander ab. Gilt nichts davon, antwortet
   die Skill mit „Kein Plan nötig" und dem direkten Weg und schreibt keine Datei.
2. **Quelle festhalten.** Liegt ein feature-spec-Entwurf vor (`docs/specs/wip/…`, Kopfzeile
   `skill: feature-spec`), zeigt `**Spec:**` darauf. Sonst steht unter `**Auftrag:**` der
   Wortlaut des Nutzers, ein Issue-Link oder der Pfad eines Befunds — etwa
   `ARCHITECTURE.md` von architecture-map oder ein Brownfield-Bericht von
   rest-api-architect. Was die Skill dafür annimmt, steht in `- Annahme:`-Zeilen, bei
   keiner Annahme `- Annahme: keine`. Sie erfindet keine Anforderungen.
3. **Repo lesen.** Der Verifikationsbefehl kommt aus der CLAUDE.md-Zeile `Verifikation:`
   (setup-repo), sonst aus vorhandenen Runner-Einträgen; fehlt er, heißt es
   „Verifikation: keine — ungeprüft". Pfade, Module und Tests stammen aus dem Repo.
4. **Tasks schneiden** nach `references/task-patterns.md`: Code-Task mit fünf Steps
   (Test schreiben, Rot sehen, Implementieren, Grün sehen, Commit), Doku- oder
   Konfig-Task mit drei Steps, Zuschnittsregel wie impl-plan („teile nur, wo ein
   Reviewer die eine Task ablehnen und die Nachbar-Task annehmen könnte").
5. **Verifikations-Task als letzter Task**, Titel wörtlich `Verifikation`:
   - `**Files:**` mit `- Test: \`<datei>\``, der Datei, die den Befehl definiert
     (`CLAUDE.md`, `Makefile`, `package.json`, `pyproject.toml`); ohne Befehl die
     CLAUDE.md, sonst der Plan selbst.
   - `**Interfaces:**` mit `Consumes:` gleich allen `Produces:`-Symbolen der Code-Tasks
     und `Produces: (nichts Neues)` — so steht er für das Gate hinter allen.
   - Ein Step führt den Befehl aus und nennt Erwartung und Ergebnis.
   Bei einer feature-spec-Quelle zitiert jeder Akzeptanzkriterium-Titel (`### …` unter
   `## Akzeptanzkriterien`) wörtlich in mindestens einem Task.
6. **Lint:** `plan_to_tasks.py lint <plan>`. Befunde beheben, nicht umformulieren.
7. **Zeigen und übergeben:** den Plan zeigen (Pfad, Tasks, Verifikation) und sagen „Plan
   liegt unter …, Lint sauber, weiter mit subagent-dev" — oder „ungeprüft — Lint nicht
   verfügbar".

**subagent-dev** lernt die zweite Kopfzeile. `plan_to_tasks.py lint` akzeptiert
`skill: impl-plan` und `skill: work-plan`; die Regeln für impl-plan bleiben. Für
work-plan gilt: genau eine Quelle (`**Spec:**` oder `**Auftrag:**`), der letzte Task heißt
`Verifikation`, und zeigt `**Spec:**` auf eine Datei mit Kopfzeile `skill: feature-spec`,
läuft die Coverage über deren Kriterien-Titel statt über eine Eval-Tabelle; ohne diese
Kopfzeile bleibt sie `unchecked`. `generate` und `verify` ändern sich nicht.

**Verweise.** Danach zeigt keine Description und keine Abgrenzung mehr auf
`superpowers:writing-plans` oder `superpowers:subagent-driven-development`:

| Stelle | heute | danach |
| --- | --- | --- |
| subagent-dev, Description (3) | „or a superpowers:writing-plans plan"; „use superpowers:subagent-driven-development directly"; „… that superpowers:subagent-driven-development does not have" | „or a work-plan plan for repos outside this collection"; „use the built-in Agent tool directly, or work-plan first"; „… that a plain Agent dispatch does not have" |
| subagent-dev, Abgrenzung | writing-plans für Repos ohne impl-plan; subagent-driven-development als Referenz für den Ablauf | work-plan für fremde Repos; das eingebaute Agent-Werkzeug ohne Plan |
| impl-plan, Description und Abgrenzung | „For repositories without subagent-dev, use superpowers:writing-plans instead"; writing-plans für Repos ohne subagent-dev | „For repositories outside this collection, use work-plan instead"; work-plan |
| feature-spec, Description und Abgrenzung | writing-plans zerlegt die Spec | work-plan zerlegt die Spec |
| architecture-map, Description und Abgrenzung | Refactoring-Plan über writing-plans | über work-plan |
| rest-api-architect, Description und Rumpf (2) | Brownfield-Befund über writing-plans | über work-plan |
| `plan_to_tasks.py`, Docstrings und Hilfetext | „superpowers:writing-plans-Plan" | „impl-plan- oder work-plan-Plan" |
| README und Spec 00 | writing-plans in den Routing-Zeilen zu feature-spec und impl-plan (je zweimal) und in der Annahme zu `to-tickets` (Spec 00 §5) | work-plan; eigene Routing-Zeile für work-plan; README-Liste von evaluated-dev |

Bewusst bleiben: die Herkunftszeile in `impl-plan/references/reviewer-prompt.md` („Aus
`superpowers:writing-plans` übersetzt"), die Abgrenzungen gegen `superpowers:brainstorming`
und `superpowers:writing-skills` in skill-forge und impl-plan, die gegen
`superpowers:systematic-debugging` in debug-ledger. Sie sind Herkunft oder Abgrenzung
gegen eine Skill, die bei Bedarf von Hand eingeschaltet wird, und keine Routing-Ziele.

**setup-repo.** Pläne sind Arbeitsartefakte, keine Zielarbeit: `docs/plans/` kommt zu den
Ausnahmen des Bereichs-Hooks.

### Contract

- **Kein Plan ohne Anlass.** Unter der Schwelle aus Schritt 1 „Kein Plan nötig", keine
  Datei.
- **Quelle oder Annahme.** Jede Anforderung im Plan steht in der Spec, im Auftrag oder in
  einer `- Annahme:`-Zeile.
- **Verifikation zuletzt.** Der letzte Task heißt `Verifikation`, nennt den Befehl oder
  „keine — ungeprüft" und ist lint-fähig.
- **Lesbar für subagent-dev.** Kopfzeile, Task-Blöcke, Interfaces im Vokabular; `lint`
  sauber oder die Übergabe sagt „ungeprüft".
- **Anti-Zeremonie-Fall:** Ein Tippfehler bekommt keinen Plan.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| Implementierungsplan zu einer Spec dieser Sammlung | **impl-plan** | work-plan — die Sammlung hat eigene Pflicht-Tasks |
| was gebaut werden soll, mit Akzeptanzkriterien | **feature-spec** | work-plan beginnt bei der fertigen Spec |
| Plan zerlegen, Gate, Dispatch, Abnahme | **subagent-dev** | work-plan schreibt den Plan und dispatcht nicht |
| Befund zur Architektur oder zur API, der Arbeit nach sich zieht | **architecture-map**, **rest-api-architect** | work-plan plant die Arbeit, der Befund bleibt dort |
| der Rot-Grün-Zyklus innerhalb eines Code-Tasks | test-first (24) | work-plan nennt den Zyklus nur als Steps |
| Plan im Gespräch ohne Datei | eingebauter Plan-Modus | work-plan — die Datei ist für subagent-dev |

Rückverweise beim Bau, je mit dem Wort work-plan: subagent-dev, impl-plan, feature-spec,
architecture-map und rest-api-architect (siehe Tabelle Verweise). work-plan nennt alle
fünf zurück (Regel `neighbors`).

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_lint_accepts_work_plan_header` | `tests/test_subagent_dev_plan_to_tasks.py` | Kopfzeile `skill: work-plan` ohne Befund; fremde Kopfzeile weiter Befund; impl-plan-Regeln unverändert |
| `test_work_plan_needs_one_source_and_final_verification` | dito | weder `**Spec:**` noch `**Auftrag:**` → Befund; beide → Befund; kein Task `Verifikation` oder nicht als letzter → Befund; ein Verifikations-Task nach `references/task-patterns.md` ohne Befund |
| `test_work_plan_coverage_against_feature_spec_criteria` | dito | jedes `### `-Kriterium unter `## Akzeptanzkriterien` wörtlich in einem Task → `checked`; ein fehlendes → Befund mit Titel; Spec ohne feature-spec-Kopfzeile → `unchecked` |
| `test_work_plan_template_is_lint_clean` | `tests/test_plans_lint.py` | `skills/work-plan/assets/plan-template.md`, mit Beispielwerten gefüllt, ohne Befund |
| `test_no_superpowers_routing_targets` | `tests/test_marketplace.py` | `sync_skills.py --report` zählt 0; kein `superpowers:writing-plans` und kein `superpowers:subagent-driven-development` unter `skills/` außer der Herkunftszeile in `skills/impl-plan/references/reviewer-prompt.md` |
| `test_goal_scope_ignores_house_artifacts` | `tests/test_setup_repo_goal_scope.py` | erweitert um `docs/plans/` |

### Evals

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-one-file-change-gets-no-plan` | contract | `wp-small` | `file_absent` `docs/plans/*.md`; `output_matches` `Kein Plan nötig`; `git_head_unchanged` | den Wortlaut der Schwelle schreibt nur die Skill; ohne sie entsteht ein Plan im Gespräch oder als Datei |
| 2 | `plan-from-feature-spec-covers-criteria` | contract | `wp-spec` | `artifact_header` und `file_matches` `skill: work-plan` auf `docs/plans/*.md`; `file_matches` dort `\*\*Spec:\*\* .docs/specs/wip/export\.md.`, `\*\*Interfaces:\*\*`, `(?s)### Task \d+: Verifikation\n(?!.*### Task)` und alle drei Kriterien-Titel wörtlich | Kopfzeile, Interfaces und der Verifikations-Task als letzter Task entstehen nur mit der Skill |
| 3 | `verification-task-uses-repo-command` | contract | `wp-verify` | `file_matches` `docs/plans/*.md` auf `(?s)### Task \d+: Verifikation.*make ci\b`; `file_unchanged` `CLAUDE.md`; `output_matches` `ungeprüft` | die Fixture nennt `make ci` nur in der CLAUDE.md-Zeile `Verifikation:` (nicht `make check`, das als Beispiel in `task-patterns.md` steht — geschärft beim Bau); der Lint fehlt im Workspace, und nur die Skill sagt dann „ungeprüft" |
| 4 | `plan-from-finding-records-assignment` | contract | `wp-finding` | `file_matches` `skill: work-plan` und `\*\*Auftrag:\*\*.*ARCHITECTURE\.md` und `(?m)^- Annahme:` auf `docs/plans/*.md` | ohne Spec hält nur die Skill die Quelle als Auftrag und die Annahmen in Hausform fest |

Prompts: 1 „Schreib einen Plan: in src/greet.py den Tippfehler ‚Helo' korrigieren.",
2 „Schreib den Plan zur Spec docs/specs/wip/export.md.", 3 „Schreib einen Plan für einen
CSV-Export der Berichte mit CLI-Option `--csv` und einem Abschnitt in der README.",
4 „Schreib einen Plan für den Zyklus, den ARCHITECTURE.md meldet: Danach soll die Domäne gar nicht mehr von der Persistenz abhängen — User bekommt seine Session von außen, statt get_session() selbst aufzurufen." (geschärft nach dem ersten Lauf: der Zyklus allein liegt unter der Schwelle) Die Fixture `wp-spec`
trägt einen feature-spec-Entwurf mit drei Akzeptanzkriterien; `wp-finding` ein
`ARCHITECTURE.md` mit einem Zyklusbefund von architecture-map. Im Eval-Workspace liegt nur
work-plan, nicht subagent-dev; der Lint ist dort nicht verfügbar. Vor der Abnahme läuft
jeder Eval einmal ohne Skill (Spec 18).

## Alternatives considered

**impl-plan um einen Modus für fremde Repos erweitern.** Eine Skill, zwei Pflicht-Sätze,
eine Description für zwei Anlässe. Verworfen: impl-plan steht mit Grund in
`excluded.json`, weil Eval-Tabelle und die vier Pflicht-Tasks nur in dieser Sammlung
gelten; ein Modus brächte sie in jedes Repo oder schwächte sie hier.

**superpowers:writing-plans behalten.** Verworfen: Es hält superpowers an, das Spec 20
abschalten will, und sein Kopf verlangt `subagent-driven-development`.

**Nur der eingebaute Plan-Modus.** Er plant im Gespräch, ohne Datei, ohne Lint und ohne
Übergabe an subagent-dev. Verworfen als alleiniger Weg; die Skill grenzt sich ab.

**Ablage unter `docs/superpowers/plans/` wie in diesem Repo.** Verworfen: Der Name trüge
superpowers in fremde Repos, die es nie installiert haben.

## Out of scope

Der TDD-Zyklus selbst (Spec 24). Das Ausführen von Plänen (subagent-dev) und dessen
Skriptpfade in fremden Repos. Ein Umbenennen von `docs/superpowers/` in diesem Repo. Die
Datei `superpowers-gaps.json` (Spec 21, Abschnitt B). Die Folgespec, die Skriptpfade aller
Skills auf `${CLAUDE_SKILL_DIR}` umstellt.

## Open questions

*Annahme:* Name `work-plan`, Ablage `docs/plans/`, Schwelle „mehr als zwei Dateien, neue
öffentliche Schnittstelle oder Reihenfolge" — widersprich, falls nein.

*Annahme:* Bis Spec 24 gebaut ist, nennt der Code-Task den Zyklus als Steps ohne Verweis
auf eine Skill; der Verweis auf test-first kommt mit Spec 24.

*Annahme:* work-plan kommt nicht in `PROJECT_SKILLS`. In diesem Repo plant impl-plan; die
Projekt-Kopien von feature-spec, architecture-map, subagent-dev und impl-plan nennen
work-plan, das hier und in Cloud-Sessions nicht geladen ist — das ist eine Abgrenzung,
kein Routing-Ziel in diesem Repo.

Ungemessen bleibt, ob `${CLAUDE_SKILL_DIR}` im Plugin-Cache auf den Ordner der Skill
auflöst und ob ein Marketplace von GitHub dieselbe Repo-Kopie anlegt wie der lokale Pfad.
Ungemessen ist auch das Listing: Spec 20 hat in `evaluated-dev` neun Skills ohne Description
gezählt, und work-plan kommt dazu; Trigger-Evals installieren die Skill allein und sehen
das nicht.

Nach Spec 23 und 24 ändert sich der Status von `writing-plans`,
`subagent-driven-development` und `test-driven-development` in der Lückentabelle. Spec 21
Abschnitt B legt `superpowers-gaps.json` mit diesem Stand an.

## Next steps

Plan mit `impl-plan` (16) und Bau nach `skill-forge` (17) Schritt 3 bis 7. Danach Spec 24,
dann Spec 21 Abschnitt B mit der Abschaltbedingung.
