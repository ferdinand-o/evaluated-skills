# Spec 20: plugin-split — drei Plugins und eine Projekt-Installation statt eines Plugins, superpowers wird abgelöst statt überstimmt

Skill-Spezifikation · Zyklus 20 · Entscheidung: Zuschnitt nach dem einzigen Hebel, den Claude Code für Plugin-Skills bietet (`enabledPlugins` je Scope, `defaultEnabled` je Eintrag); drei Marketplace-Einträge mit Root-Quelle und `skills`-Liste, weil der Nutzer Plugins nur über die CLI anbindet; die Projekt-Installation unter `.claude/skills/` kommt aus einer Tabelle; superpowers wird erst abgeschaltet, wenn die Abschaltbedingung erfüllt ist · Abgeglichen mit Spec 00 · Überarbeitet nach unabhängigem Review (zweite Runde 2026-10-08; dritte Fassung nach der Sync-Messung vom 2026-10-08: CLI-Weg statt Plugin-Kopien)

## Problem

Die Sammlung ist ein einziges Plugin (`.claude-plugin/marketplace.json`, ein Eintrag
`cc-skills` mit 21 Skills). Abschalten lässt sich nur alles oder nichts: Laut
Claude-Code-Doku (skills, „Override skill visibility from settings") gilt „Plugin
skills are not affected by `skillOverrides`. Manage those through `/plugin`
instead."; `enabledPlugins` wirkt je Plugin.

**Das Listing läuft schon heute über.** `/context` in einer lokalen Session mit dem per
CLI angebundenen Plugin zeigte am 2026-10-08 zwölf Skills mit 120 bis 300 Tokens, zusammen
rund 2 620, und neun Skills mit weniger als 20 Tokens: sql-schema-architect,
rest-api-architect, verified-research, review-context, testing-strategy,
visual-summary, skill-forge, subagent-dev, ui-architect
(`docs/superpowers/validation/2026-10-08-plugin-split-sync.md`). Das passt zum
Listing-Budget der skills-Doku, bei dessen Überlauf Descriptions wegfallen; diese neun
stehen dann nur mit ihrem Namen im Kontext und lösen über ihre Trigger nicht aus. Dass
das die Ursache ist, ist nicht bewiesen; der Bau misst nach der Aufteilung erneut.

Parallel ist superpowers 6.4.2 installiert. Es bringt 15 Skills mit 2 302 Zeichen
Description (gemessen am 2026-10-07 per Regex über das Frontmatter) und einen
`SessionStart`-Hook mit Matcher `startup|clear|compact` (`hooks/hooks.json` im Plugin),
der seine Doktrin nach jedem Start, jedem `/clear` und jeder Compaction neu
einspielt. Gegen diese Injektion steht die Routing-Matrix aus Spec 00 §5 nur als Text.
Die Hausskills verweisen ihrerseits auf superpowers: 28 Zeilen mit `superpowers:` in
12 Dateien von 7 Skills (`grep -c`, 2026-10-07, im zweiten Review nachgemessen). In den
Descriptions stehen 8 Fundstellen in 6 Skills: `writing-plans` 5-mal (architecture-map,
feature-spec, impl-plan, rest-api-architect, subagent-dev), `subagent-driven-development`
2-mal (subagent-dev), `writing-skills` 1-mal (skill-forge). Dazu nennen drei
Descriptions superpowers-Skills ohne Namensraum (`feature-spec` und `debug-ledger`:
`systematic-debugging`; `testing-strategy`: `test-driven-development`).

Die Aufteilung spart im User-Scope 2 864 von 13 467 Zeichen eigener Descriptions (es
bleiben 10 603, 78,7 %; Rohstring samt `\"`-Escapes, geparst 13 447 und 10 591). Mit
`cc-ui` je Repo und impl-plan und skill-forge nur im Repo selbst fallen drei bis fünf
Skills aus dem Listing; ob das reicht, damit die neun übrigen wieder ihre Description
zeigen, misst der Bau in `/context`. Die superpowers-Injektion fällt erst mit der
Abschaltung weg.

**Angebunden wird nur über die CLI.** Der Nutzer bindet die Sammlung lokal per
`/plugin marketplace add` an. Laut seinen Angaben vom 2026-10-08 enthält
`plugins/synced/` nur Skills, keine Plugins mit Skills; Plugins werden in
Cloud-Sessions nicht eingebunden (als Bug gemeldet, noch offen); und beim Einbinden per
Repository auf claude.ai lässt sich kein Branch wählen. Auf dem CLI-Weg filtert ein
Marketplace-Eintrag mit Root-Quelle und `skills`-Liste: „only those subdirectories load"
(plugins/manifest-reference); im ersten Review simuliert: 10, 3, 6 und 2 Skills je
Eintrag.

**Seit PR #16 gibt es eine Projekt-Installation.** `.claude/skills/` enthält zehn Skills
für die Arbeit an diesem Repo, weil Cloud-Sessions Projekt-Skills laden, Plugins aber
nicht (Spec 22, Problem). Die Liste steht als `REPO_DEV_SKILLS` in
`tests/test_project_skills_copy.py`: impl-plan, skill-forge und acht Skills von `cc-dev`
ohne rest-api-architect und sql-schema-architect. Ein eigenes Plugin für impl-plan und
skill-forge zeigte diese beiden im Repo doppelt an und hätte keinen Einsatzort, weil
beide laut ihrer Description nur für diese Sammlung gelten. Ebenso erschienen die acht
`cc-dev`-Skills doppelt, solange `cc-dev` im User-Scope an ist.

Der Nutzer hat am 2026-10-07 entschieden: superpowers wird durch die eigene Sammlung
ersetzt, und die Aufteilung ist eine eigene Vorstufe vor den Setup-Skills (Spec 21,
22), weil deren Routing an genau diesem Schalter hängt.

## Constraints

Keine neue Skill. `skills/<name>/` bleibt der einzige Ort, an dem Skills gepflegt
werden; Tests, Evals, Pläne und Skriptpfade ziehen nicht um. Alle drei Plugins haben
die Repo-Wurzel als Quelle und wählen ihre Skills per `skills`-Liste; es gibt keine
Plugin-Kopien. Die Projekt-Installation `.claude/skills/<name>/` ist eine generierte
Kopie; sie schreibt `scripts/sync_skills.py` (Tier 1, Repo-Werkzeug) aus einer Tabelle,
die `REPO_DEV_SKILLS` ersetzt.

Die neue Lint-Regel `plugin-membership` ist Tier 1 und G2, ebenso die Tests; einen
Hook gibt es nicht. Plugin-Namen kollidieren nicht mit dem geplanten Repo
`ferdinand-o/cc-frontend`, deshalb heißt das UI-Plugin hier `cc-ui`. Descriptions
bleiben frei von `<…>`. Kein Plugin-Eintrag trägt ein `version`-Feld: Laut Doku
(plugins/loading) bleiben Nutzer bei gesetzter Version auf der Cache-Kopie, bis sich der
String ändert; ohne Feld gilt der Commit.

**Abweichung von Spec 00:** Spec 00 führt „Plugin-/Marketplace-Packaging und
Verteilung" unter Out of scope. Diese Spec holt das Packaging herein, weil das Routing
inzwischen davon abhängt; der Bau zieht die Zeile in Spec 00 nach.
`.claude-plugin/excluded.json` ist Repo-Konfiguration, kein Artefakt einer Skill, und
trägt deshalb kein `_meta`; Schlüssel mit `_` am Anfang ignorieren Test und Regel.

Das Abschalten von superpowers ist nicht Teil dieses Baus. Es ist eine
Profilentscheidung, die `setup-user` (Spec 21) umsetzt, sobald die Abschaltbedingung
erfüllt ist. Mit Spec 20 allein bleibt superpowers an.

## Approach

**Eiserne Regel:** *Jede Skill steht in der `skills`-Liste genau eines Plugins oder mit
Grund in `.claude-plugin/excluded.json`, jede Projekt-Kopie gleicht ihrem Original,
bevor committet wird — und superpowers wird erst abgeschaltet, wenn die
Abschaltbedingung erfüllt ist.*

### Zuschnitt

Kriterium ist, welche Skills gemeinsam an- und abgeschaltet werden, nicht, wovon sie
handeln. Zeichen = Summe der Description-Längen (Rohstring ohne äußere
Anführungszeichen, gemessen wie im Problem).

| Plugin | Skills | Zeichen | `defaultEnabled` |
| --- | --- | --- | --- |
| `cc-dev` | architecture-map, debug-ledger, dev-report, feature-spec, handoff, rest-api-architect, review-context, sql-schema-architect, subagent-dev, testing-strategy | 6 318 | true |
| `cc-ui` | enterprise-ui, mobile-audit, motion-landing, ui-architect | 2 461 | false — an je Frontend-Repo |
| `cc-knowledge` | explain, exercise-forge, human-prose, learning-coach, verified-research, visual-summary | 4 285 | true |
| kein Plugin | impl-plan, skill-forge (1 179 Zeichen) — nur für Specs dieser Sammlung, Projekt-Kopie; cad-parts — braucht einen stl-cad-server | — | — |

mobile-audit kam mit PR #17 nach dieser Spec auf main und beim Merge am 2026-10-09 nach
`cc-ui`: Sie prüft Webseiten mobil, teilt `references/mobile.md` mit den drei UI-Skills
und wird mit ihnen je Frontend-Repo an- und abgeschaltet. Die Zeichen im Problem sind der
Stand vor dem Merge; danach hat `cc-dev` 6 305 Zeichen, weil zwei Descriptions kürzer
wurden.

Jeder Eintrag hat `source: "./"`, `strict: false`, eine sortierte `skills`-Liste mit
`./skills/<name>`, kein `version` und keine `dependencies`. Laut Doku überschreibt eine
Projekt-Einstellung die User-Einstellung („the project setting overrides the user
setting", plugins/install); `cc-ui` wird deshalb je Repo eingeschaltet. Eine Installation
per `claude plugin install` schreibt für ein Plugin mit `defaultEnabled: false`
ausdrücklich `false` in die User-Settings (am 2026-10-08 mit CLI 2.1.294 nachgemessen);
das Projekt-`true` gewinnt trotzdem.

`impl-plan`, `skill-forge` und `cad-parts` stehen mit Grund in
`.claude-plugin/excluded.json`; die Datei ersetzt das Dict `EXCLUDED` in
`tests/test_marketplace.py`, damit Test und Lint dieselbe Quelle lesen. Die Tabelle in
`sync_skills.py` führt die zehn Skills der heutigen `REPO_DEV_SKILLS`. Im Repo
`cc-skills` schaltet eine neue, committete `.claude/settings.json` `cc-dev@cc-skills` aus
(heute gibt es dort keine), damit die acht Projekt-Kopien nicht doppelt erscheinen.
rest-api-architect und sql-schema-architect fehlen damit in diesem Repo; das entspricht
der Auswahl aus PR #16.

Das Manifest bekommt `renames: {"cc-skills": null}`.

### Lückentabelle superpowers → Haus

| superpowers | Ersatz | Status | Verweise umgeschrieben in |
| --- | --- | --- | --- |
| systematic-debugging | debug-ledger | vorhanden | dieser Spec: Description und Abgrenzung von `feature-spec` und `debug-ledger` |
| subagent-driven-development | subagent-dev (mit Plan); ohne Plan das eingebaute Agent-Werkzeug | vorhanden | Spec 23 (2 Fundstellen in der Description von subagent-dev, zusammen mit writing-plans) |
| requesting-code-review | review-context plus `/code-review` | vorhanden (Zuschnitt Spec 04 offen) | — |
| receiving-code-review | User-Regel `verification.md`: Befunde vor dem Umsetzen nachmessen (Spec 21) | Regel, kommt mit 21 | — |
| verification-before-completion | User-Regel `verification.md` (Spec 21) und Verifikationsbefehl (Spec 22) | Regel, kommt mit 21/22 | — |
| using-git-worktrees | eingebaute Worktrees (`claude --worktree`) | nativ | — |
| brainstorming | die Profil-Skill `anthropic-skills:brainstorming`; skill-forge und impl-plan grenzen sich von `superpowers:brainstorming` ab | vorhanden | — |
| writing-plans | Plan für fremde Repos; `impl-plan` gilt nur für Specs dieser Sammlung | **Lücke** | Spec 23 (5 Fundstellen) |
| test-driven-development | Ziel des Verweises in `testing-strategy` | **Lücke** | Spec 24 |
| writing-skills | Verweis aus `skill-forge` (Projekt-Kopie) bleibt als Abgrenzung; wer eine Disziplin-Skill baut, schaltet superpowers dafür von Hand ein | bleibt bewusst | — |
| executing-plans, dispatching-parallel-agents | subagent-dev (sequenziell als Default) bzw. Agent-Werkzeug | entfällt | — |
| finishing-a-development-branch | dev-report und handoff | entfällt | — |
| using-superpowers, diagnosing-superpowers | — | entfällt | — |

Diese Tabelle ist der Stand beim Schreiben. Nach dem Bau von Spec 21 ist
`skills/setup-user/references/superpowers-gaps.json` die Quelle; Spec 23 und 24 ändern
den Status dort, nicht hier.

### Skill-Struktur

```
skills/skill-forge/
├── SKILL.md                         Schritt 4: Lint und sync_skills.py --check; Anti-Zeremonie-Satz „Lint, Sync-Check, Commit"; Schritt 7: Plugin-Zuordnung in der skills-Liste oder excluded.json, Projekt-Tabelle; Satz „Prüfen ändert nichts: Befunde werden gemeldet, nicht behoben"; „Dreizehn Regeln" → „Vierzehn"; „Sieben Regeln unchecked" → „Acht"; Satz zu unchecked im Eval-Workspace nennt plugin-membership
├── references/checklist.md          Phase Report und Nachbarn: Punkt Plugin-Zuordnung; Titel „die 19 Punkte" → „die 20 Punkte"
├── references/reviewer-prompt.md    „dreizehn Regeln" → „vierzehn"
└── scripts/lint_skill.py            Tier 1 — Regel plugin-membership; Kopfzeile und Docstring „dreizehn" → „vierzehn"; Lint-Ausgabe nennt sync_skills.py --check

scripts/sync_skills.py               Tier 1, Repo-Werkzeug — Tabelle PROJECT_SKILLS; spiegelt skills/<name>/ nach .claude/skills/<name>/; --check meldet fehlende, überzählige und abweichende Dateien; --report zählt superpowers:-Verweise in Descriptions von Plugins mit defaultEnabled true
.claude/skills/…                     generierte Kopien, Inhalt wie nach PR #16
.claude/settings.json                enabledPlugins: cc-dev@cc-skills auf false
.claude-plugin/marketplace.json      drei Einträge mit source ./ und skills-Liste; renames; defaultEnabled; kein version
.claude-plugin/excluded.json         cad-parts, impl-plan, skill-forge je mit Grund
tests/test_marketplace.py            bestehende Tests umgestellt, neue siehe Tests (Repo)
tests/test_project_skills_copy.py    entfällt; seine Prüfung übernimmt test_project_copies_match_originals
tests/test_skill_forge_lint.py       make_repo mit Manifest; Regelzahl 14; unchecked-Zahl +1; plugin-membership-Fälle
tests/test_skill_forge_evals_schema.py  len(evals) == 6; Grip-Tests für die Lint-Muster der Evals 1, 5 und 6
skills/impl-plan/SKILL.md            Pflicht-Task „Nachbarn" nennt die Plugin-Zuordnung
skills/visual-summary/references/charts.md   A11y-Prinzipien ausformuliert statt Verweis auf skills/enterprise-ui/ (anderes Plugin)
evals/skill-forge/evals.json         Evals 1 und 5 geändert, Eval 6 neu
evals/fixtures/sf-existing/          bekommt Manifest mit note-tag und handoff in einer skills-Liste und excluded.json — bleibt lint-sauber
evals/fixtures/sf-spec/              bekommt Manifest mit zwei Plugins
evals/fixtures/sf-plugin-orphan/     specs/ als Repo-Marker, Manifest mit einer Skill, orphan-x in keiner Liste, fixture.json mit "git": true
skills/feature-spec/SKILL.md         Description „use systematic-debugging" → „use debug-ledger"; Abgrenzung **systematic-debugging** → **debug-ledger**
skills/debug-ledger/SKILL.md         Description ohne `systematic-debugging`; Abgrenzung behält superpowers:systematic-debugging als Herkunft
specs/Spec 00 – skill-foundation.md  §5: Zeile „Bug, Testfehler" → debug-ledger (01); Out of scope ohne Packaging; keine Plugin-Spalte
README.md                            Aufbau: .claude/skills/ und scripts/; Installation je Plugin als Liste (keine Tabelle) samt Zuordnung; Umstieg von cc-skills
docs/known-limits.md                 Marketplace: Root-Quelle mit skills-Liste, nur CLI-Weg, Namensraum, Skriptpfade; skill-forge: vierzehn Regeln, sechs Evals
docs/superpowers/reports/skill-forge-report.md   Abschnitt zu dieser Runde
```

### Ablauf

In `skill-forge`, Schritt 7, nach „Routing-Matrix in Spec 00 §5 und `README.md`": Die
neue Skill kommt in die `skills`-Liste genau eines Plugins im Manifest — Frage: „mit
welchen Skills wird sie an- und abgeschaltet?", nicht „wovon handelt sie?". Passt kein
Plugin, kommt sie mit Grund in `.claude-plugin/excluded.json`. Gehört sie zur Arbeit an
diesem Repo, kommt sie zusätzlich in die Tabelle von `sync_skills.py`, und
`python scripts/sync_skills.py` erzeugt die Kopie.

In `skill-forge`, Schritt 4: Nach dem Lint läuft `python scripts/sync_skills.py
--check`; meldet es Abweichung, läuft `sync_skills.py` und dann der Check erneut. Der
Anti-Zeremonie-Satz lautet danach „Lint, Sync-Check, Commit — sonst nichts". So fällt
eine veraltete Projekt-Kopie vor dem Commit auf, nicht erst beim nächsten pytest-Lauf.

`sync_skills.py` spiegelt: Es kopiert neue und geänderte Dateien, löscht in der Kopie,
was im Original fehlt, und ignoriert `__pycache__/` und `*.pyc`. `--check` schreibt
nichts und meldet je Datei fehlend, überzählig oder abweichend; Exit 1 bei Befund. Ein
Manifest, das kein gültiges JSON ist, oder ein `excluded.json`, das kein JSON-Objekt
ist, endet bei `--report` mit Exit 2 und einer Meldung.

`plugin-membership` liest das Manifest und zählt, in wie vielen `skills`-Listen
`./skills/<name>` steht. `pass` bei genau einer Liste oder Ausschluss, `finding` bei null
oder mehr als einer, ebenso wenn die Skill ausgeschlossen ist und trotzdem in einer Liste
steht. `unchecked` ohne Manifest, bei einem Eintrag ohne `skills`-Liste oder mit
unlesbarem `excluded.json` — nie `pass` ohne Manifest. Ob die Projekt-Kopie dem Original
gleicht, prüft `--check`, nicht die Regel.

Das README beschreibt die Installation als Liste, nicht als Tabelle: `_routing_names` in
`lint_skill.py` liest die zweite Spalte jeder README-Tabelle als „zuständig". Die Liste
nennt je Plugin seine Skills; eine Plugin-Spalte in Spec 00 §5 gibt es nicht, weil die
Matrix 14 der 22 Skills nicht führt und sonst eine dritte, ungetestete Zuordnung
entstünde.

Im Bau: Manifest umbauen, Projekt-Kopien über das Skript erzeugen, Tests umschreiben,
Matrix und README nachziehen, dann `claude plugin validate .` und eine lokale
Installation aller drei Plugins in einem Wegwerf-Config-Verzeichnis, die 10, 3 und 6
Skills zeigt. Nach dem Merge misst der Nutzer `/context` erneut. Die geänderten
Descriptions machen `evals_due` für feature-spec und debug-ledger; deren Evals laufen
mit.

### Contract

- **Genau ein Plugin je Skill, Projekt-Kopie gleich Original.** Mechanismus:
  `tests/test_marketplace.py` und `plugin-membership` (beide G2, beide lesen
  `excluded.json`), dazu `sync_skills.py --check` in skill-forge Schritt 4 und im Test.
- **Abschaltbedingung für superpowers:** (a) die Lückentabelle hat keine Zeile „Lücke";
  (b) keine Description eines Plugins mit `defaultEnabled: true` (`cc-dev`,
  `cc-knowledge`) enthält `superpowers:`; (c) jede Zeile mit Status „Regel" ist als
  Regeldatei im Config-Verzeichnis installiert. Skills ohne Plugin zählen für (b) nicht;
  der Verweis aus `skill-forge` auf `superpowers:writing-skills` bleibt deshalb stehen.
  (a) liegt als Daten in `skills/setup-user/references/superpowers-gaps.json` (Spec 21);
  (b) zählt `sync_skills.py --report` an der Quelle, heute 6 Fundstellen in `cc-dev`
  (architecture-map, feature-spec, rest-api-architect, subagent-dev dreimal); (a) bis
  (c) zusammen prüft `route_check.py` (Spec 21) am installierten Bestand. Nackte Namen
  wie `systematic-debugging` zählen nicht als Verweis; die drei bekannten Fälle
  schreiben diese Spec und Spec 24 um.
- **Kein Verweis zeigt ins Leere, solange superpowers an ist.** Die 7 Fundstellen zu
  `writing-plans` und `subagent-driven-development` in Descriptions bleiben, bis Spec 23
  sie umschreibt. Von den 22 Zeilen außerhalb der Descriptions bleiben die Abgrenzungen
  in skill-forge und debug-ledger bewusst stehen; die 7 Zeilen in `plan_to_tasks.py`
  beschreiben das Planformat von writing-plans und sind kein Verweis. Den Rest schreibt
  Spec 23 um.
- **Kein Dateiverweis über eine Plugin-Grenze.** Eine Skill in einem Plugin verweist
  nicht auf `skills/<andere>/…`, wenn die andere in einem anderen Plugin liegt oder
  ausgeschlossen ist; heute trifft das nur visual-summary → enterprise-ui.
- **Anti-Zeremonie-Fall:** Ein geänderter Satz in einer bestehenden Skill löst keine
  Manifeständerung aus; `plugin-membership` bleibt `pass`, und eine Projekt-Kopie zieht
  der Sync-Check in Schritt 4 nach.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| neue Skill einem Plugin zuordnen | **skill-forge** Schritt 7 | impl-plan (16) — plant den Bau, ordnet nicht zu; superpowers:writing-skills — kennt das Manifest dieser Sammlung nicht |
| Plugins je Account oder Repo an- und abschalten | setup-user (21), setup-repo (22) | skill-forge — prüft nur die Zuordnung im Manifest |

Rückverweise beim Bau: `impl-plan` nennt `skill-forge` bereits; `skill-forge` nennt
`superpowers:writing-skills` bereits in Description und Abgrenzung. `impl-plan` nimmt
die Plugin-Zuordnung in seine Pflicht-Task „Nachbarn" auf, damit ein Plan sie nicht
vergisst.

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_every_skill_in_exactly_one_plugin` | `tests/test_marketplace.py` | je Skill unter `skills/` genau eine `skills`-Liste oder ein Eintrag in `excluded.json`, nie beides |
| `test_project_copies_match_originals` | dito | `sync_skills.py --check` ohne Befund; ersetzt `tests/test_project_skills_copy.py` |
| `test_sync_mirrors_and_ignores_pycache` | dito | in einem Temp-Repo: gelöschte Datei verschwindet aus der Kopie, `__pycache__/` wird nicht kopiert, `--check` meldet überzählige Datei |
| `test_plugin_entries_are_fixed` | dito | genau `cc-dev`, `cc-ui`, `cc-knowledge`; `source` `./`; sortierte `skills`-Liste mit existierenden Ordnern; kein `version`, keine `dependencies`; `defaultEnabled` wie in der Tabelle; `renames` erlaubt |
| `test_no_plugin_json_that_would_conflict_with_strict_false` | dito | unverändert behalten |
| `test_excluded_json_names_existing_skills_with_reason` | dito | jede Zeile ohne `_` am Anfang nennt einen Ordner unter `skills/` und einen nicht leeren Grund |
| `test_no_file_refs_across_plugins` | dito | kein `skills/<andere>/` in den Dateien einer Plugin-Skill, wenn die andere in einem anderen Plugin liegt oder ausgeschlossen ist |
| `test_superpowers_report_counts_descriptions` | dito | `--report` in einem Temp-Repo: Fundstelle in einem Plugin mit `defaultEnabled: true` zählt, in einem mit `false` und in einer ausgeschlossenen Skill nicht |
| `test_repo_disables_cc_dev_for_project_copies` | dito | `.claude/settings.json` setzt `cc-dev@cc-skills` auf `false` |
| `test_descriptions_carry_no_angle_bracket_tags` | dito | unverändert behalten |
| `test_plugin_membership_rule` | `tests/test_skill_forge_lint.py` | pass bei genau einer Liste und bei Ausschluss; finding bei null, zwei, und bei ausgeschlossen plus gelistet; unchecked ohne Manifest, bei Eintrag ohne Liste und bei kaputtem `excluded.json` |

### Evals

Der Harness schließt `.claude/` aus (Spec 22, Problem); kein Eval prüft deshalb die
Projekt-Kopien. Das tun Test und Sync-Check.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-one-sentence-change-lints-only` | contract | `sf-existing` mit Manifest | unverändert; zusätzlich `file_matches` auf `.skills/cache/skill-forge/lint.json`: `"id": "plugin-membership", "status": "pass"` und `file_unchanged` `.claude-plugin/marketplace.json` | das `pass` schreibt nur der Lint der Skill; ein Satz ändert das Manifest nicht |
| 2 | `token-change-makes-evals-due` | contract | `sf-existing` mit Manifest | unverändert | unverändert; die Fixture bekommt nur Manifest und `excluded.json` dazu |
| 3 | `gate-word-without-hook-is-reported` | contract | `sf-gate` | unverändert | unverändert; die Fixture hat kein Manifest, `plugin-membership` ist dort `unchecked` |
| 4 | `missing-anti-ceremony-eval-is-reported` | contract | `sf-noanti` | unverändert | unverändert; wie Eval 3 |
| 5 | `routing-new-skill-gets-house-evals` | contract | `sf-spec` mit Manifest | unverändert; zusätzlich `file_matches` `.claude-plugin/marketplace.json` auf `"\./skills/reminder"` und `file_matches` auf `lint.json`: `"id": "plugin-membership", "status": "pass"` | ohne skill-forge entsteht kein `lint.json` und kein Grund, die Skill in eine Liste einzutragen |
| 6 | `skill-outside-any-plugin-is-reported` | contract | `sf-plugin-orphan` | `file_matches` auf `lint.json`: `"id": "plugin-membership", "status": "finding"`; `file_unchanged` `.claude-plugin/marketplace.json` und `.claude-plugin/excluded.json` | nur `lint_skill.py` kennt die Regel; „Prüfen ändert nichts" steht in der SKILL.md, deshalb bleiben Manifest und Ausschlussliste unverändert |

Prompts: Evals 1 bis 5 unverändert, Eval 6 „Prüfe die Skill orphan-x mit
skill-forge.". Eval 5 baut mit einem zweiten Plugin im Manifest keinen zweiten
Skill-Bau auf; die Fixture `sf-spec` bekommt nur das Manifest dazu.

## Alternatives considered

**Ein Plugin, gesteuert über `skillOverrides`.** Geht nicht: Die Doku schließt
Plugin-Skills aus (Zitat im Problem).

**Je Plugin ein eigener Quellordner mit generierten Kopien.** So stand es in der zweiten
Fassung, begründet mit dem Sync-Weg von claude.ai, der eine `skills`-Liste nicht als
Filter liest. Verworfen am 2026-10-08, weil der Nutzer nur über die CLI anbindet und der
Sync-Weg für Plugins nicht genutzt wird (Problem). Gewinnt, wenn Plugins künftig über
claude.ai synchronisiert werden sollen.

**Ein viertes Plugin `cc-meta` für impl-plan und skill-forge.** So stand es in der ersten
Fassung. Verworfen, weil beide nur in diesem Repo gelten und dort seit PR #16 als
Projekt-Kopie liegen; das Plugin hätte sie doppelt angezeigt und `dependencies` auf
`cc-dev` gebraucht. Gewinnt, wenn die beiden in einem zweiten Repo gebraucht werden.

**Die Skills physisch nach `plugins/<plugin>/skills/` verschieben.** Keine Listen, keine
Kopien. Verworfen, weil jeder `skills/<name>`-Pfad in Tests, Evals, Plänen und
SKILL.md-Dateien umzöge.

**Ein Pre-Commit-Hook statt Sync-Check in Schritt 4.** Fängt auch Änderungen außerhalb
von skill-forge. Verworfen für diesen Bau, weil Hooks in diesem Repo opt-in bleiben
(Spec 00); gewinnt, wenn der Test trotz Schritt 4 Drift findet.

**Die Sammlung als persönliche Skills unter `~/.claude/skills/`.** Dann wirkt
`skillOverrides`. Verworfen, weil Update-Weg und Namensraum verloren gehen und 17 Skills
gleichnamig im Nutzerprofil liegen (known-limits, Marketplace).

**Ein Plugin je Skill.** 21 Schalter und ein Manifest, das niemand mehr liest.

**`forceRemoveDeletedPlugins: true`.** Würde die alte Installation zuverlässig
deinstallieren, ist aber eine dauerhafte Richtlinie für alle künftigen Entfernungen.
Verworfen zugunsten von `renames` und dem Umstieg im README; im ersten Review gemessen:
nach `marketplace update` ist `cc-skills@cc-skills` ausgeschaltet.

**superpowers behalten und die Hausmatrix in CLAUDE.md schreiben.** Anweisung gegen eine
Injektion bei jedem Start und jedem `/clear`. Der Nutzer hat sich für Ablösung
entschieden.

**superpowers sofort abschalten.** Die Verweise auf `superpowers:writing-plans` liefen
ins Leere. Deshalb die Abschaltbedingung.

**superpowers im Repo `cc-skills` anlassen, für writing-skills.** Dort liefe die
SessionStart-Injektion weiter, wo impl-plan und skill-forge arbeiten (known-limits,
impl-plan). Verworfen; writing-skills wird bei Bedarf von Hand eingeschaltet.

## Out of scope

Die Ersatz-Skills (Spec 23 für Pläne in fremden Repos samt Umschreiben der
`superpowers:`-Verweise, Spec 24 für TDD). Das Abschalten von superpowers und das Setzen
von `enabledPlugins` außerhalb dieses Repos (Spec 21 und 22). Die Skriptpfade der 16
Skills mit `skills/<name>/scripts/…` auf `${CLAUDE_SKILL_DIR}` umstellen. Die Pfade sind
relativ zum Arbeitsverzeichnis; in fremden Repos laufen deshalb schon heute die Skripte
von 9 der 10 Skills in `cc-dev` und 4 der 6 in `cc-knowledge` nicht. Die Plugins liefern
dort Doktrin ohne lauffähige Skripte; `known-limits` sagt das mit diesen Zahlen, und eine
eigene Folgespec stellt um. Der Hook-Pfad in
`debug-ledger/assets/hooks/check-ledger.json`, der in fremden Repos jeden `git commit`
anhält (gemessen am 2026-10-07: Exit 2). Ein Umbenennen von `docs/superpowers/`. Der
Gesamt-Frontend-Skill, der `cc-ui` später ersetzt. Der Sync-Weg über claude.ai.

## Open questions

*Annahme:* Zuschnitt, Namen und `defaultEnabled` wie in der Tabelle — widersprich, falls
nein.

*Annahme:* rest-api-architect und sql-schema-architect bleiben im immer aktiven `cc-dev`,
weil API- und Schemafragen in fast jedem Backend-Repo auftauchen und beide zusammen nur
1 280 Zeichen kosten — widersprich, falls sie wie `cc-ui` je Repo an sollen.

*Annahme:* `cc-ui` ist eine Übergangslösung bis zum Gesamt-Frontend-Skill und wird
danach entfernt.

Das alte Plugin `cc-skills` verschwindet bei CLI-Installationen über `renames` nach
`/plugin marketplace update`; der Umstieg im README nennt die drei neuen
`/plugin install`-Befehle.

Ungemessen bleibt, ob die Aufteilung das Listing so weit entlastet, dass die neun Skills
ohne Description wieder eine zeigen; der Nutzer misst `/context` nach dem Merge.
Ungemessen ist auch, ob die Aufteilung die Trefferquote des Routings verbessert: Die
Routing-Evals installieren Skills unter `.claude/skills/`, nie als Plugin. Ebenso offen
ist, ob `Skill(...)`-Deny-Regeln in den Permissions Plugin-Skills ausblenden; die Doku
schweigt dazu.

## Next steps

Plan mit `impl-plan` (16) überarbeiten und Bau nach `skill-forge` (17) Schritt 3 bis 7.
Nach dem Merge `/context` erneut messen. Danach Spec 21 und 22; Spec 23 (Plan für
fremde Repos) und Spec 24 (TDD) schließen die Lücken, erst dann schaltet `setup-user`
superpowers ab. Die Folgespec für `${CLAUDE_SKILL_DIR}` steht unabhängig davon an.
