# Spec 25: skill-dir — Skriptpfade, die in jedem Repo laufen

Skill-Spezifikation · Zyklus 25 · Entscheidung: jeder Skript-Aufruf steht in der SKILL.md als `python "${CLAUDE_SKILL_DIR}/scripts/…"`, weil Claude Code nur dort ersetzt (gemessen); References verweisen auf die SKILL.md statt auf einen Pfad; Hook-Vorlagen kopieren ihr Skript nach `.claude/hooks/` und rufen es über `$CLAUDE_PROJECT_DIR` auf wie setup-repo; eine Lint-Regel in skill-forge hält das · Abgeglichen mit Spec 00 und Spec 20 · Folgespec aus Spec 20, Out of scope · Überarbeitet nach unabhängigem Review (2026-10-14: Regel deckt fremde und python-lose Aufrufe, Reference-Regel ohne Fehlalarm in skill-forge, architecture-map ohne Absolutpfad im Artefakt, beide Hook-Vorlagen mit Existenzprüfung und Positivtest, Inventar um Template, work-plan, mobile-audit und known-limits ergänzt, evals_due nachgemessen)

## Problem

Skills rufen ihre Skripte in der SKILL.md repo-relativ auf, etwa
`python skills/architecture-map/scripts/extract_py.py`. Der Pfad stimmt nur im Checkout
dieser Sammlung. Gemessen am 2026-10-14 an den SKILL.md-Dateien: In `cc-dev` rufen 9 von 14
Skills ihre Skripte so auf, in `cc-ui` 2 von 4, in `cc-knowledge` 4 von 6 — in einem
fremden Repo liefert das Plugin dort Doktrin ohne lauffähige Skripte. Dasselbe gilt im
Eval-Workspace: Dort liegt die Skill unter `.claude/skills/<name>/` (`evalkit/workspace.py`),
nicht unter `skills/<name>/`.

Die Hook-Vorlage von debug-ledger ruft `skills/debug-ledger/scripts/check_ledger.py` auf;
in einem fremden Repo fehlt die Datei, der Unterprozess endet mit 2, und der Hook hält
jeden `git commit` an (gemessen am 2026-10-07). Die Vorlage von sql-schema-architect ruft
ihr Skript bei jedem Bash-Aufruf auf; fehlt es, endet `python3` mit 2 und der Hook hält
jeden Bash-Aufruf an.

Vier Skills nutzen schon `${CLAUDE_SKILL_DIR}`: setup-repo, setup-user, work-plan,
test-first. Beleg, dass der Weg trägt: In den test-first-Evals vom 2026-10-13 stand im
geladenen Skill-Text der ersetzte absolute Pfad (`T="…/ws/.claude/skills/test-first/scripts/tdd_log.py"`),
und `tdd_log.py` schrieb das Log in jedem Lauf mit Skill.

## Constraints

**Gemessen am 2026-10-14 (CLI 2.1.296)** mit einer Probe-Skill, die die Variable auf drei
Wegen ausgibt:

| Ort | Ergebnis |
| --- | --- |
| Text der SKILL.md, `${CLAUDE_SKILL_DIR}` | ersetzt durch den absoluten Pfad des Skill-Ordners |
| Bash-Umgebung, `$CLAUDE_SKILL_DIR` | leer — die Variable ist nicht gesetzt |
| Reference, mit Read gelesen, `${CLAUDE_SKILL_DIR}` | bleibt wörtlich, die Shell macht daraus einen leeren String |

Daraus folgt: Ein Skript-Aufruf gehört in die SKILL.md. Eine Reference, die einen Aufruf
zeigt, verweist auf die SKILL.md. Die Skripte sind nicht ausführbar (Mode 100644); der
Aufruf beginnt deshalb immer mit `python`.

Nachbar-Skripte über `${CLAUDE_SKILL_DIR}/../<andere>/scripts/` nur, wenn beide Skills im
selben Plugin liegen oder beide in `PROJECT_SKILLS` (`scripts/sync_skills.py`) stehen
(Spec 20, „Kein Dateiverweis über eine Plugin-Grenze"). Heute: work-plan → subagent-dev
(beide `cc-dev`), impl-plan und skill-forge → subagent-dev (alle drei Projekt-Kopien).

Tier unverändert je Skill. Gate-Grade: die Lint-Regel `script-paths` ist G2; die
Hook-Vorlagen bleiben G3 (Spec 00 §4). Die Kopfzeilen erzeugter Artefakte und die
`GENERATED`-Konstanten der Skripte bleiben: Sie benennen die Herkunft und werden nicht
ausgeführt. Ausnahme ist architecture-map, deren Kopfzeile `drift_check.py` wieder
ausführt (Ablauf, Schritt 4).

## Approach

**Eiserne Regel:** *Ein Skript-Aufruf, den Claude ausführen soll, steht in der SKILL.md
und beginnt mit `python "${CLAUDE_SKILL_DIR}/`; eine Hook-Vorlage hält nie etwas an, nur
weil ihr Skript fehlt — sie sagt dann „ungeprüft".*

### Skill-Struktur

```
skills/skill-forge/
├── SKILL.md                         eigene Aufrufe auf ${CLAUDE_SKILL_DIR}; lint-spec über ../subagent-dev mit Degradationszeile; Zeile „# installiert:" entfällt; „Vierzehn Regeln" → „Fünfzehn"
├── assets/skill-template/SKILL.md   Aufrufmuster mit ${CLAUDE_SKILL_DIR}; Zeile „# installiert:" entfällt
├── references/checklist.md          Punkt 19 (repo-relativ, „Ermessen") ersetzt durch Regel script-paths; Regel in der Tabelle
├── references/reviewer-prompt.md    „vierzehn Regeln" → „fünfzehn"
├── references/spec-brief.md         lint-spec-Aufruf verweist auf die SKILL.md
└── scripts/lint_skill.py            Tier 1 — Regel script-paths; Kopfzeile, Docstring und Ausgabe „fünfzehn"

skills/<name>/SKILL.md               python skills/<name>/scripts/… → python "${CLAUDE_SKILL_DIR}/scripts/…": architecture-map,
                                     debug-ledger, dev-report, exercise-forge, feature-spec, human-prose (Zeile „# installiert:"
                                     entfällt), learning-coach, motion-landing, rest-api-architect, review-context,
                                     sql-schema-architect, subagent-dev, testing-strategy, verified-research (dort ohne python,
                                     wird ergänzt); impl-plan über ../subagent-dev; mobile-audit (<skill-dir>-Form → ${CLAUDE_SKILL_DIR})
skills/work-plan/SKILL.md            Satz „subagent-dev ruft seine Skripte repo-relativ auf … nicht bis zum Dispatch" entfällt
skills/verified-research/references/rating-rubric.md, delta-mode.md   Aufrufe verweisen auf die SKILL.md
skills/setup-repo/references/rules-harvest.md   Aufruf `python plan_repo.py …` verweist auf die SKILL.md
skills/architecture-map/scripts/extract_py.py, extract_ts.py, analyze_graph.py   generated: python scripts/<datei> … statt sys.argv[0]
skills/architecture-map/scripts/drift_check.py   löst scripts/<datei> und jeden Pfad, der auf /scripts/<datei> endet, gegen den eigenen Skill-Ordner auf
skills/debug-ledger/assets/hooks/check-ledger.json        Aufruf $CLAUDE_PROJECT_DIR/.claude/hooks/check_ledger.py; fehlt die Datei: systemMessage „ungeprüft", Exit 0
skills/sql-schema-architect/assets/hooks/migration-gate.json   dasselbe für migration_gate.py
skills/debug-ledger/SKILL.md, skills/sql-schema-architect/SKILL.md   Abschnitt Hook: Skript aus ${CLAUDE_SKILL_DIR} nach .claude/hooks/ kopieren, dann Fragment übernehmen
evals/skill-forge/evals.json, evals/fixtures/sf-relpath/   Eval 7 neu, Eval 1 um script-paths ergänzt
.claude/skills/*                     Projekt-Kopien über sync_skills.py
tests/test_skill_forge_lint.py       Regelzahl 15; Fälle für script-paths
tests/test_skill_forge_evals_schema.py   len(evals) == 7; Grip-Test für Eval 7
tests/test_skill_dir_paths.py        neu, siehe Tests
tests/test_marketplace.py            test_no_file_refs_across_plugins erkennt auch /../<skill>/
docs/known-limits.md                 Stellen zu Skriptpfaden: Marketplace (2026-09-23 und Spec 20), skill-forge („Zweiform"), work-plan; neuer Abschnitt skill-dir
docs/superpowers/reports/skill-dir-report.md   Report mit „Was nicht gemessen wurde"
```

### Ablauf (Bau)

1. **Lint-Regel `script-paths`**, eingebaut nach der Umstellung (Schritt 2 bis 4), damit
   `test_no_finding_outside_the_register` nie rot ist; ein Prototyp misst vorher, welche
   Zeilen sie trifft. Sie meldet `finding`, zeilenweise, Kopfzeilen
   (Zeilen mit `generated:`) ausgenommen:
   - (a) in der SKILL.md jede Zeile mit `skills/<beliebiger-name>/scripts/` oder
     `<skill-dir>/scripts/` — mit oder ohne `python`, in Codeblock, Inline-Code oder
     Prosa. Ein Aufruf eines anderen Skills lautet `${CLAUDE_SKILL_DIR}/../<name>/scripts/`.
   - (b) in einer Reference eine Zeile mit `${CLAUDE_SKILL_DIR}` und `python`.
   - (c) in einem Hook-Asset unter `assets/hooks/` ein Pfad `skills/<name>/scripts/`.
   Eine Skill ohne Treffer: `pass`. Das Register `KNOWN_FINDINGS` in
   `tests/test_skills_lint.py` wächst nicht; alle Skills werden im selben Bau umgestellt.
2. **Umstellen je Skill.** Aufrufe in der SKILL.md, Verweise in References, Projekt-Kopie
   über `sync_skills.py`. Kontrolle ist `lint_skill.py skills/<name>` **ohne** `--base`:
   kein `script-paths`. (`--base` hilft hier nicht, weil der Befund an der Basis schon
   bestand und deshalb nicht als neu gilt.) Dann `lint_skill.py --base HEAD~1` für
   `evals_due`.
3. **Hook-Vorlagen.** Beide Fragmente rufen `"$CLAUDE_PROJECT_DIR/.claude/hooks/<skript>.py"`
   auf, wie `setup-repo/assets/hooks/verify-stop.json`. Fehlt die Datei, gibt der Hook
   `{"systemMessage": "[<skill>] Hook ungeprüft — .claude/hooks/<skript>.py fehlt"}` aus und
   endet mit 0. Die SKILL.md sagt beim Übernehmen: `cp "${CLAUDE_SKILL_DIR}/scripts/<skript>.py"
   .claude/hooks/`, dann Fragment mischen; beide Skripte sind Stdlib-Einzeldateien. Der Hook
   endet weiter mit Exit 2, wenn das Skript einen Verstoß findet.
4. **architecture-map.** Die drei Skripte schreiben `generated: python scripts/<datei> …`
   statt `sys.argv[0]`; `drift_check.py` führt einen Befehl, dessen Skriptpfad
   `scripts/<datei>` ist oder auf `/scripts/<datei>` endet, mit dem Skript aus seinem eigenen
   Skill-Ordner aus. Bestehende `ARCHITECTURE.md` mit altem Pfad bleiben prüfbar.
5. **Evals.** Für jede Skill, bei der `evals_due` nach der Umstellung `True` meldet, laufen
   die betroffenen Evals im Harness (`run_evals.py --skill <name>`). Ein Treffer, der nur an
   einem Wort wie „python" in der Aufrufzeile hängt, ist ein Fehlalarm; er steht mit Grund
   im Report statt eines Laufs. Dazu Eval 1 und 7 von skill-forge.

### Contract

- **Aufruf in der SKILL.md, mit `${CLAUDE_SKILL_DIR}`.** Mechanismus: `script-paths` (G2).
- **References ohne ausführbaren `${CLAUDE_SKILL_DIR}`-Aufruf.** Sie nennen das Skript beim
  Namen und verweisen auf den Aufruf in der SKILL.md.
- **Nachbarn nur im selben Plugin oder in der Projekt-Kopie.** Mechanismus:
  `test_neighbor_paths_stay_inside_a_plugin`.
- **Hook-Vorlagen halten nichts an, weil ein Skript fehlt, und melden das.** Mechanismus:
  Test mit fehlendem Skript (Exit 0, `systemMessage`) und mit Verstoß (Exit 2).
- **Anti-Zeremonie-Fall:** Eine Skill ohne Skripte bekommt `script-paths: pass` ohne
  Änderung.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| Skill bauen oder prüfen, Regel `script-paths` | **skill-forge** | diese Spec ändert die Regeln, nicht den Ablauf von skill-forge |
| Plugin-Zuordnung, Projekt-Kopien | Spec 20 (`sync_skills.py`, `plugin-membership`) | unverändert |
| Hook-Vorlage übernehmen | **debug-ledger**, **sql-schema-architect** (Abschnitt Hook) | diese Spec ändert Ort und Verhalten bei fehlendem Skript, nicht, was der Hook prüft |
| Hook aus einem Repo-Plan installieren | setup-repo | dessen Weg (`.claude/hooks/`, `$CLAUDE_PROJECT_DIR`) ist hier das Vorbild |

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_script_paths_rule` | `tests/test_skill_forge_lint.py` | (a) mit und ohne `python`, mit fremdem Skill-Namen und `<skill-dir>`; (b); (c); Kopfzeile `generated: python skills/…` und eine Skill ohne Skripte `pass`; die Tabellenzeile in `checklist.md` löst (b) nicht aus |
| `test_rule_count` | dito | `len(set(RULE_IDS)) == 15` |
| `test_no_finding_outside_the_register` | `tests/test_skills_lint.py` | unverändert; das Register wächst nicht |
| `test_skill_md_calls_resolve_from_skill_dir` | `tests/test_skill_dir_paths.py` | jeder `${CLAUDE_SKILL_DIR}/scripts/<datei>` und `${CLAUDE_SKILL_DIR}/../<skill>/scripts/<datei>` zeigt auf eine existierende Datei |
| `test_neighbor_paths_stay_inside_a_plugin` | dito | jedes `../<skill>` liegt im selben Plugin wie die aufrufende Skill oder beide stehen in `PROJECT_SKILLS` |
| `test_hook_templates_report_missing_script_and_still_block` | dito | je Vorlage: fehlendes Skript → Exit 0 mit `systemMessage`; vorhandenes Skript und Verstoß → Exit 2 |
| `test_drift_check_resolves_old_and_new_paths` | `tests/test_architecture_map_drift_check.py` | Footer mit `skills/architecture-map/scripts/…`, `.claude/skills/…/scripts/…` und `scripts/…` laufen alle |
| `test_no_file_refs_across_plugins` | `tests/test_marketplace.py` | erkennt zusätzlich `/../<skill>/` |
| `test_seven_contract_evals_load` | `tests/test_skill_forge_evals_schema.py` | sieben Evals; Grip-Test: das Muster von Eval 7 trifft die echte Lint-Ausgabe auf `sf-relpath`, nicht die auf `sf-existing` |

### Evals

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-one-sentence-change-lints-only` | contract | `sf-existing` mit Manifest | unverändert; zusätzlich `file_matches` auf `.skills/cache/skill-forge/lint.json`: `"id": "script-paths", "status": "pass"` | das `pass` der neuen Regel schreibt nur der Lint; die Fixture-Skill hat keine Skripte |
| 7 | `repo-relative-script-path-is-reported` | contract | `sf-relpath` | `file_matches` `.skills/cache/skill-forge/lint.json` auf `"id": "script-paths", "status": "finding"`; `file_unchanged` `skills/relpath-x/SKILL.md` | nur `lint_skill.py` kennt die Regel; „Prüfen ändert nichts" steht in der SKILL.md von skill-forge |

Prompts: Eval 1 unverändert, Eval 7 „Prüfe die Skill relpath-x mit skill-forge." Die
Fixture `sf-relpath` trägt eine Mini-Skill mit einem Skript und dem Aufruf
`python skills/relpath-x/scripts/run.py` in der SKILL.md, dazu `docs/artifact-header.md`
und Manifest wie `sf-plugin-orphan`.

## Alternatives considered

**Die Variable in die Bash-Umgebung bringen** (ein SessionStart-Hook, der
`CLAUDE_SKILL_DIR` exportiert). Verworfen: Es gibt keinen einen Skill-Ordner je Session.

**Skripte nach `~/.skills/bin` installieren.** Verworfen: eine zweite Kopie neben dem
Plugin-Cache, die veraltet, und ein Schreibzugriff außerhalb des Repos.

**References dürfen `${CLAUDE_SKILL_DIR}` tragen.** Verworfen nach der Messung: Die Shell
ersetzt es durch einen leeren String, der Befehl läuft gegen `/scripts/…`.

**Hook-Vorlagen mit Platzhalter `<skill-dir>` und Absolutpfad in `settings.json`.**
Verworfen nach dem Review: Der Pfad veraltet mit jedem Plugin-Update und unterscheidet
sich je Rechner; ein nicht ersetzter Platzhalter schaltet den Hook still ab. Die Kopie
nach `.claude/hooks/` ist committbar und gilt für alle im Team.

## Out of scope

Kopfzeilen und `GENERATED`-Konstanten außer architecture-map. Tests, Pläne und Reports,
die `skills/<name>/scripts/` im Repo aufrufen — sie laufen in diesem Checkout. Ein Lauf
der Skills in einem fremden Repo über ein installiertes Plugin; gemessen wird der
Eval-Workspace, der dieselbe Lage hat.

## Open questions

*Annahme:* Hook-Vorlagen werden von Hand übernommen (G3, Spec 00 §4); die SKILL.md nennt
Kopieren und Mischen — widersprich, falls sie ein Installationsskript bekommen sollen.

*Annahme:* Ob eine `systemMessage` eines `PreToolUse`-Hooks mit Exit 0 dem Nutzer
angezeigt wird, folgt der Hook-Doku; setup-repo nutzt denselben Weg für `Stop`. Gemessen
ist es für `PreToolUse` nicht.

Ungemessen: eine SKILL.md, die nicht über das Skill-Werkzeug, sondern mit Read geladen
wird (Subagent, Cowork, claude.ai) — dort bleibt `${CLAUDE_SKILL_DIR}` wörtlich, und der
Aufruf scheitert wie heute der repo-relative. known-limits sagt das.

## Next steps

Plan mit `impl-plan` (16) und Bau auf dem Branch `claude/skill-dir-paths`.
