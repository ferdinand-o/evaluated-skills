# Spec 20: plugin-split — vier Plugins statt eines, superpowers wird abgelöst statt überstimmt

Skill-Spezifikation · Zyklus 20 · Entscheidung: Zuschnitt nach dem einzigen Hebel, den Claude Code für Plugin-Skills bietet (`enabledPlugins` je Scope, `defaultEnabled` je Eintrag); je Plugin ein eigener Quellordner mit generierten Kopien aus `skills/`, weil der Sync-Weg von claude.ai `skills`-Listen nicht als Filter liest; superpowers wird erst abgeschaltet, wenn die Abschaltbedingung erfüllt ist · Abgeglichen mit Spec 00 · Überarbeitet nach unabhängigem Review

## Problem

Die Sammlung ist ein einziges Plugin (`.claude-plugin/marketplace.json`, ein Eintrag
`cc-skills` mit 21 Skills). Abschalten lässt sich nur alles oder nichts: Laut
Claude-Code-Doku (skills, „Override skill visibility from settings") gilt „Plugin
skills are not affected by `skillOverrides`. Manage those through `/plugin`
instead."; `enabledPlugins` wirkt je Plugin.

Parallel ist superpowers 6.4.2 installiert. Es bringt 15 Skills mit 2 302 Zeichen
Description (gemessen am 2026-10-07 per Regex über das Frontmatter) und einen
`SessionStart`-Hook mit Matcher `startup|clear|compact` (`hooks/hooks.json` im Plugin),
der seine Doktrin nach jedem Start, jedem `/clear` und jeder Compaction neu
einspielt. Gegen diese Injektion steht die Routing-Matrix aus Spec 00 §5 nur als Text.
Die Hausskills verweisen ihrerseits auf superpowers: 28 Zeilen mit `superpowers:` in
12 Dateien von 7 Skills (`grep -c`, 2026-10-07). In den Descriptions stehen 8
Fundstellen in 6 Skills: `writing-plans` 5-mal (architecture-map, feature-spec,
impl-plan, rest-api-architect, subagent-dev), `subagent-driven-development` 2-mal
(subagent-dev), `writing-skills` 1-mal (skill-forge). Dazu nennen drei Descriptions
superpowers-Skills ohne Namensraum (`feature-spec` und `debug-ledger`:
`systematic-debugging`; `testing-strategy`: `test-driven-development`).

Der größte Gewinn liegt bei superpowers, nicht bei den eigenen Descriptions: Im
User-Scope bleiben nach der Aufteilung 10 603 von 13 467 Zeichen eigener Descriptions
(78,7 %, Summen nach Tabelle unten); was wegfällt, sind die superpowers-Descriptions
und die SessionStart-Injektion.

**Eine gemeinsame Quelle für alle Plugins funktioniert auf dem Sync-Weg nicht.** Die
synchronisierte Kopie von cc-skills in einer Claude-Code-Session trägt eine von claude.ai
erzeugte `plugin.json` mit `skills`-Liste ohne `cad-parts`, und die Session lädt
`cc-skills:cad-parts` trotzdem (im Review gemessen, 2026-10-07). Die Doku erklärt das:
Eine `skills`-Liste in der `plugin.json` „Adds to the default `skills/` scan"; nur ein
Marketplace-Eintrag mit Root-Quelle filtert, „only those subdirectories load"
(plugins/manifest-reference). Vier Plugins mit `source: "./"` würden auf dem Sync-Weg
also je alle 22 Ordner laden. Auf dem CLI-Weg filtern sie korrekt (Simulation im Review:
10, 3, 6, 2 Skills).

Der Nutzer hat am 2026-10-07 entschieden: superpowers wird durch die eigene Sammlung
ersetzt, und die Aufteilung ist eine eigene Vorstufe vor den Setup-Skills (Spec 21,
22), weil deren Routing an genau diesem Schalter hängt.

## Constraints

Keine neue Skill. `skills/<name>/` bleibt der einzige Ort, an dem Skills gepflegt
werden; Tests, Evals, Pläne und Skriptpfade ziehen nicht um. Je Plugin entsteht ein
Quellordner `plugins/<plugin>/skills/<name>/` als generierte Kopie, geschrieben von
`scripts/sync_plugins.py` (Tier 1, Repo-Werkzeug) und geprüft von einem Test, der
Kopie und Original byteweise vergleicht. Symlinks sind kein sicherer Ausweg: Die CLI löst sie innerhalb eines Marketplace auf,
aber ob der Sync-Weg von claude.ai sie liest, ist ungemessen, und git-Symlinks sind
unter Windows unzuverlässig.

Die neue Lint-Regel `plugin-membership` ist Tier 1 und G2, ebenso der Test; einen
Hook gibt es nicht. Plugin-Namen kollidieren nicht mit dem geplanten Repo
`ferdinand-o/cc-frontend`, deshalb heißt das UI-Plugin hier `cc-ui`. Descriptions
bleiben frei von `<…>`.

**Abweichung von Spec 00:** Spec 00 führt „Plugin-/Marketplace-Packaging und
Verteilung" unter Out of scope. Diese Spec holt das Packaging herein, weil das Routing
inzwischen davon abhängt; der Bau zieht die Zeile in Spec 00 nach.

Das Abschalten von superpowers ist nicht Teil dieses Baus. Es ist eine
Profilentscheidung, die `setup-user` (Spec 21) umsetzt, sobald die Abschaltbedingung
erfüllt ist.

## Approach

**Eiserne Regel:** *Jede Skill liegt in genau einem Plugin oder steht mit Grund in
`.claude-plugin/excluded.json`, und jede Plugin-Kopie gleicht ihrem Original — und
superpowers wird erst abgeschaltet, wenn die Abschaltbedingung erfüllt ist.*

### Zuschnitt

Kriterium ist, welche Skills gemeinsam an- und abgeschaltet werden, nicht, wovon sie
handeln. Zeichen = Summe der Description-Längen (Rohstring ohne äußere
Anführungszeichen, gemessen wie im Problem).

| Plugin | Skills | Zeichen | `defaultEnabled` |
| --- | --- | --- | --- |
| `cc-dev` | architecture-map, debug-ledger, dev-report, feature-spec, handoff, rest-api-architect, review-context, sql-schema-architect, subagent-dev, testing-strategy | 6 318 | true |
| `cc-ui` | enterprise-ui, motion-landing, ui-architect | 1 685 | false — an je Frontend-Repo |
| `cc-knowledge` | explain, exercise-forge, human-prose, learning-coach, verified-research, visual-summary | 4 285 | true |
| `cc-meta` | impl-plan, skill-forge | 1 179 | false — an nur im Repo `cc-skills`; `dependencies: ["cc-dev"]`, weil skill-forge in Schritt 3 die Skill subagent-dev aufruft |

Jeder Eintrag hat `source: "./plugins/<plugin>"`, keine `skills`-Liste und keine
`plugin.json`. Laut Doku überschreibt eine Projekt-Einstellung die User-Einstellung
(„the project setting overrides the user setting", plugins/install); `cc-ui` und
`cc-meta` werden deshalb je Repo eingeschaltet. Eine Installation per `claude plugin
install` schreibt für ein Plugin mit `defaultEnabled: false` ausdrücklich `false` in
die User-Settings (im Review gemessen); das Projekt-`true` gewinnt trotzdem.

Das Manifest bekommt `renames: {"cc-skills": null}`. `cad-parts` steht mit Grund in
`.claude-plugin/excluded.json`; die Datei ersetzt das Dict `EXCLUDED` in
`tests/test_marketplace.py`, damit Test und Lint dieselbe Quelle lesen.

### Lückentabelle superpowers → Haus

| superpowers | Ersatz | Status | Verweise umgeschrieben in |
| --- | --- | --- | --- |
| systematic-debugging | debug-ledger | vorhanden | dieser Spec: Description und Abgrenzung von `feature-spec` und `debug-ledger` |
| subagent-driven-development | subagent-dev (mit Plan); ohne Plan das eingebaute Agent-Werkzeug | vorhanden | Spec 23 (2 Fundstellen in der Description von subagent-dev, zusammen mit writing-plans) |
| requesting-code-review | review-context plus `/code-review` | vorhanden (Zuschnitt Spec 04 offen) | — |
| receiving-code-review | User-Regel `verification.md`: Befunde vor dem Umsetzen nachmessen (Spec 21) | Regel, kommt mit 21 | — |
| verification-before-completion | User-Regel `verification.md` (Spec 21) und Verifikationsbefehl (Spec 22) | Regel, kommt mit 21/22 | — |
| using-git-worktrees | eingebaute Worktrees (`claude --worktree`) | nativ | — |
| brainstorming | die Profil-Skill `brainstorming`, nicht Teil von superpowers | nicht betroffen | — |
| writing-plans | Plan für fremde Repos; `impl-plan` gilt nur für Specs dieser Sammlung | **Lücke** | Spec 23 (5 Fundstellen) |
| test-driven-development | Ziel des Verweises in `testing-strategy` | **Lücke** | Spec 24 |
| writing-skills | Verweis aus `skill-forge` (cc-meta) bleibt als Abgrenzung; wer eine Disziplin-Skill baut, schaltet superpowers dafür von Hand ein | bleibt bewusst | — |
| executing-plans, dispatching-parallel-agents | subagent-dev (sequenziell als Default) bzw. Agent-Werkzeug | entfällt | — |
| finishing-a-development-branch | dev-report und handoff | entfällt | — |
| using-superpowers, diagnosing-superpowers | — | entfällt | — |

### Skill-Struktur

```
skills/skill-forge/
├── SKILL.md                         Schritt 7: Plugin-Zuordnung und sync_plugins.py, auch nach jeder Änderung an einer bestehenden Skill; „Dreizehn Regeln" → „Vierzehn"; „Sieben Regeln unchecked" → „Acht"; Satz zu unchecked im Eval-Workspace nennt plugin-membership
├── references/checklist.md          Phase Report und Nachbarn: Punkt Plugin-Zuordnung; Titel „die 19 Punkte" → „die 20 Punkte"
├── references/reviewer-prompt.md    „dreizehn Regeln" → „vierzehn"
└── scripts/lint_skill.py            Tier 1 — Regel plugin-membership; Kopfzeile und Docstring „dreizehn" → „vierzehn"

scripts/sync_plugins.py              Tier 1, Repo-Werkzeug — kopiert skills/<name>/ nach plugins/<plugin>/skills/<name>/ laut Zuordnung; --check meldet Abweichung
plugins/cc-dev/skills/…, plugins/cc-ui/skills/…, plugins/cc-knowledge/skills/…, plugins/cc-meta/skills/…   generierte Kopien
.claude-plugin/marketplace.json      vier Einträge mit source ./plugins/<plugin>; renames; defaultEnabled; dependencies
.claude-plugin/excluded.json         {"cad-parts": "<Grund>"}
tests/test_marketplace.py            bestehende Tests umgestellt, neue siehe Tests (Repo)
tests/test_skill_forge_lint.py       make_repo mit Manifest; Regelzahl 14; unchecked-Zahl +1; plugin-membership-Fälle
tests/test_skill_forge_evals_schema.py  len(evals) == 7; Grip-Tests für die Lint-Muster der Evals 1, 6 und 7
skills/impl-plan/SKILL.md            Pflicht-Task „Nachbarn" nennt die Plugin-Zuordnung
evals/skill-forge/evals.json         Eval 1 geändert, Evals 6 und 7 neu
evals/fixtures/sf-existing/          bekommt Manifest, plugins/-Kopien von note-tag und handoff, excluded.json — bleibt lint-sauber
evals/fixtures/sf-spec-plugins/      Kopie von sf-spec plus Manifest mit zwei Plugins, scripts/sync_plugins.py, fixture.json mit "git": true
evals/fixtures/sf-plugin-orphan/     specs/ als Repo-Marker, Manifest mit einer Skill, orphan-x ohne Kopie, fixture.json mit "git": true
skills/feature-spec/SKILL.md         Description „use systematic-debugging" → „use debug-ledger"; Abgrenzung **systematic-debugging** → **debug-ledger**
skills/debug-ledger/SKILL.md         Description ohne `systematic-debugging`; Abgrenzung behält superpowers:systematic-debugging als Herkunft
specs/Spec 00 – skill-foundation.md  §5: Spalte „Plugin" als letzte Spalte; Zeile „Bug, Testfehler" → debug-ledger (01); Out of scope ohne Packaging
README.md                            Aufbau: plugins/; Installation je Plugin als Liste (keine Tabelle); Umstieg von cc-skills
docs/known-limits.md                 Marketplace: Quellordner, Sync-Weg, Namensraum; skill-forge: vierzehn Regeln, sieben Evals
docs/superpowers/reports/skill-forge-report.md   Abschnitt zu dieser Runde
```

### Ablauf

In `skill-forge`, Schritt 7, nach „Routing-Matrix in Spec 00 §5 und `README.md`": Die
neue Skill bekommt genau ein Plugin — Frage: „mit welchen Skills wird sie an- und
abgeschaltet?", nicht „wovon handelt sie?". Die Zuordnung steht in
`scripts/sync_plugins.py` (eine Tabelle Plugin → Skills); danach erzeugt
`python scripts/sync_plugins.py` die Kopie. Passt kein Plugin, kommt die Skill mit Grund
in `.claude-plugin/excluded.json`.

`plugin-membership` liest das Manifest, löst je Eintrag den Quellordner auf und zählt,
in wie vielen `<quelle>/skills/<name>/SKILL.md` die Skill liegt. `pass` bei genau einem
Plugin oder Ausschluss, `finding` bei null oder mehr als einem, ebenso wenn sie
ausgeschlossen und trotzdem kopiert ist, und `unchecked` ohne Manifest — nie `pass`
ohne Manifest. Ob die Kopie dem Original gleicht, prüft der Test, nicht die Regel.

Das README beschreibt die Installation als Liste, nicht als Tabelle: `_routing_names` in
`lint_skill.py` liest die zweite Spalte jeder README-Tabelle als „zuständig".

Im Bau selbst: Manifest umbauen, Kopien erzeugen, Tests umschreiben, Matrix und README
nachziehen, dann `claude plugin validate .` und eine lokale Installation aller vier
Plugins. Danach der Sync-Weg: Branch in claude.ai als Plugin-Quelle einbinden und in
einer synchronisierten Session zählen, ob jede Skill genau einmal erscheint. Die
geänderten Descriptions machen `evals_due` für feature-spec und debug-ledger; deren
Evals laufen mit.

### Contract

- **Genau ein Plugin je Skill, Kopie gleich Original.** Mechanismus:
  `tests/test_marketplace.py` und `plugin-membership` (beide G2, beide lesen
  `excluded.json`), dazu `sync_plugins.py --check` im Test.
- **Abschaltbedingung für superpowers:** (a) die Lückentabelle hat keine Zeile „Lücke",
  und (b) keine Description eines Plugins, das im User-Scope aktiv ist (`cc-dev`,
  `cc-knowledge`), enthält `superpowers:`. Plugins mit `defaultEnabled: false` zählen
  nicht; der Verweis aus `skill-forge` auf `superpowers:writing-skills` bleibt deshalb
  stehen. (a) liegt als Daten in `skills/setup-user/references/superpowers-gaps.json`
  (Spec 21) und wird von Spec 23 und 24 nachgezogen; ein Test in Spec 21 hält Datei und
  Tabelle gleich. (b) prüft `route_check.py` mechanisch, aber nur Descriptions — die rund
  28 Verweise in SKILL.md-Rümpfen und Skripten schreibt Spec 23 mit um. Nackte Namen wie `systematic-debugging` zählen nicht als Verweis; die drei
  bekannten Fälle schreiben diese Spec und Spec 24 um.
- **Kein Verweis zeigt ins Leere, solange superpowers an ist.** Die 7 Fundstellen zu
  `writing-plans` und `subagent-driven-development` bleiben, bis Spec 23 sie umschreibt.
- **Anti-Zeremonie-Fall:** Ein geänderter Satz in einer bestehenden Skill löst keine
  Manifeständerung aus; `plugin-membership` bleibt `pass`. Die Kopie zieht
  `sync_plugins.py` nach, der Test meldet sonst Abweichung.

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
| `test_every_skill_in_exactly_one_plugin` | `tests/test_marketplace.py` | je Skill unter `skills/` genau eine Kopie unter `plugins/*/skills/` oder Eintrag in `excluded.json`, nie beides |
| `test_plugin_copies_match_originals` | dito | `sync_plugins.py --check` ohne Abweichung |
| `test_plugin_entries_are_fixed` | dito | genau die vier Namen; `source` `./plugins/<name>`; keine `skills`-Liste; `defaultEnabled` und `dependencies` wie in der Tabelle; `renames` erlaubt |
| `test_no_plugin_json_in_plugin_sources` | dito | ersetzt `test_no_plugin_json_that_would_conflict_with_strict_false` |
| `test_excluded_json_names_existing_skills_with_reason` | dito | jede Zeile nennt einen Ordner unter `skills/` und einen nicht leeren Grund |
| `test_descriptions_carry_no_angle_bracket_tags` | dito | unverändert behalten |
| `test_plugin_membership_rule` | `tests/test_skill_forge_lint.py` | pass bei genau einem Plugin und bei Ausschluss; finding bei null, zwei, und bei ausgeschlossen plus kopiert; unchecked ohne Manifest |

### Evals

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-one-sentence-change-lints-only` | contract | `sf-existing` mit Manifest | unverändert; zusätzlich `file_unchanged` `.claude-plugin/marketplace.json` und `file_matches` auf `.skills/cache/skill-forge/lint.json`: `"id": "plugin-membership", "status": "pass"` | bleibt Pflicht-Eval; das `pass` schreibt nur der Lint der Skill |
| 6 | `new-skill-lands-in-exactly-one-plugin` | contract | `sf-spec-plugins` | `file_exists` `plugins/*/skills/reminder/SKILL.md`; `file_matches` auf `lint.json`: `"id": "plugin-membership", "status": "pass"` | ohne skill-forge entsteht weder `lint.json` noch der Grund, `sync_plugins.py` zu fahren |
| 7 | `skill-outside-any-plugin-is-reported` | contract | `sf-plugin-orphan` | `file_matches` auf `lint.json`: `"id": "plugin-membership", "status": "finding"`; `file_unchanged` `.claude-plugin/marketplace.json`; `file_absent` `plugins/*/skills/orphan-x/SKILL.md` | nur `lint_skill.py` kennt die Regel; „Prüfe" heißt melden, nicht beheben — Manifest unverändert und keine Kopie halten den Agenten davon ab, die Zuordnung selbst nachzuziehen und dann `pass` zu lesen |

Prompts: Eval 6 „Bau mir eine Skill nach specs/Spec 30 – reminder.md.", Eval 7 „Prüfe
die Skill orphan-x mit skill-forge.". Die Evals 2 bis 5 laufen unverändert mit.

## Alternatives considered

**Ein Plugin, gesteuert über `skillOverrides`.** Geht nicht: Die Doku schließt
Plugin-Skills aus (Zitat im Problem).

**Vier Plugins mit `source: "./"` und `skills`-Listen.** Der kleinste Umbau und auf dem
CLI-Weg korrekt. Verworfen, weil der Sync-Weg die Liste nur als Zusatz liest (Problem).
Hätte gewonnen, wenn der Nutzer Plugins nur über die CLI installierte.

**Die Skills physisch nach `plugins/<plugin>/skills/` verschieben.** Keine Kopien,
keine Drift. Verworfen, weil jeder `skills/<name>`-Pfad in Tests, Evals, Plänen und
SKILL.md-Dateien umzöge. Gewinnt, wenn die Kopien sich im Alltag als lästig erweisen.

**Die Sammlung als persönliche Skills unter `~/.claude/skills/`.** Dann wirkt
`skillOverrides`. Verworfen, weil Update-Weg und Namensraum verloren gehen und 17 Skills
gleichnamig im Nutzerprofil liegen (known-limits, Marketplace).

**Ein Plugin je Skill.** 21 Schalter und ein Manifest, das niemand mehr liest.

**`forceRemoveDeletedPlugins: true`.** Würde die alte Installation zuverlässig
deinstallieren, ist aber eine dauerhafte Richtlinie für alle künftigen Entfernungen.
Verworfen zugunsten von `renames` und dem Umstieg im README; im Review gemessen: nach
`marketplace update` ist `cc-skills@cc-skills` ausgeschaltet.

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
von `enabledPlugins` (Spec 21 und 22). Die Skriptpfade der 16 Skills mit
`skills/<name>/scripts/…` auf `${CLAUDE_SKILL_DIR}` umstellen — mit eigenen
Plugin-Quellordnern wird das dringlicher, weil der Plugin-Root nicht mehr die
Repo-Wurzel ist (known-limits, Marketplace). Der Hook-Pfad in
`debug-ledger/assets/hooks/check-ledger.json`, der in fremden Repos jeden `git commit`
anhält (gemessen am 2026-10-07: Exit 2). Ein Umbenennen von `docs/superpowers/`. Der
Gesamt-Frontend-Skill, der `cc-ui` später ersetzt. Versionsnummern je Plugin
(Spec 00, Out of scope).

## Open questions

*Annahme:* Zuschnitt, Namen und `defaultEnabled` wie in der Tabelle — widersprich, falls
nein.

*Annahme:* Generierte Kopien unter `plugins/` sind tragbar: rund 21 Ordner doppelt im
Repo, geprüft vom Test — widersprich, falls du lieber verschiebst.

*Annahme:* `cc-ui` ist eine Übergangslösung bis zum Gesamt-Frontend-Skill und wird
danach entfernt.

**Übernimmt claude.ai beim Sync `defaultEnabled` und `dependencies`?** Die erzeugte
`plugin.json` der heutigen Synchronisation enthält nur description, keywords,
lspServers, monitors, name, repository, settings, skills, version (im Review gesehen).
Fehlt `defaultEnabled`, sind `cc-ui` und `cc-meta` in synchronisierten Sessions an. Beim
Sync-Test im Bau messen; Abhilfe wäre `"<name>@synced": false` im User-Scope, das
`claude plugin disable` laut Doku schreibt (plugins/loading).

Das alte claude.ai-Plugin `cc-skills` bleibt im Konto, bis der Nutzer es dort entfernt;
`renames` wirkt nur auf CLI-Installationen. Der Umstieg im README nennt beide Wege.

Ungemessen bleibt, ob die Aufteilung die Trefferquote des Routings verbessert: Die
Routing-Evals installieren Skills unter `.claude/skills/`, nie als Plugin.

## Next steps

Plan mit `impl-plan` (16) und Bau nach `skill-forge` (17) Schritt 3 bis 7; im Bau der
Sync-Test auf einem Branch vor dem Merge. Danach Spec 21 und 22; Spec 23 (Plan für
fremde Repos) und Spec 24 (TDD) schließen die Lücken, erst dann schaltet `setup-user`
superpowers ab.
