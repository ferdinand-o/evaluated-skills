# Spec 25: skill-dir — Skriptpfade, die in jedem Repo laufen

Skill-Spezifikation · Zyklus 25 · Entscheidung: jeder Skript-Aufruf steht in der SKILL.md als `${CLAUDE_SKILL_DIR}/scripts/…`, weil Claude Code nur dort ersetzt (gemessen); References verweisen auf die SKILL.md statt auf einen Pfad; Hook-Vorlagen tragen einen Platzhalter und halten nichts an, wenn das Skript fehlt; eine Lint-Regel in skill-forge hält das · Abgeglichen mit Spec 00 und Spec 20 · Folgespec aus Spec 20, Out of scope

## Problem

16 Skills rufen ihre Skripte in der SKILL.md repo-relativ auf, etwa
`python skills/architecture-map/scripts/extract_py.py`. Der Pfad stimmt nur im Checkout
dieser Sammlung. Spec 20 hat gezählt: In fremden Repos laufen die Skripte von 9 der 10
Skills in `cc-dev` und 4 der 6 in `cc-knowledge` nicht; die Plugins liefern dort Doktrin
ohne lauffähige Skripte. Dasselbe gilt im Eval-Workspace: Dort liegt die Skill unter
`.claude/skills/<name>/`, nicht unter `skills/<name>/` — ein Agent, der die SKILL.md
wörtlich nimmt, findet das Skript nicht und improvisiert.

Die Hook-Vorlage von debug-ledger ruft `python3 skills/debug-ledger/scripts/check_ledger.py`
auf; in einem fremden Repo fehlt die Datei, der Unterprozess endet mit 2, und der Hook hält
jeden `git commit` an (gemessen am 2026-10-07). Die Vorlage von sql-schema-architect hat
dasselbe Pfadproblem.

Vier Skills nutzen schon `${CLAUDE_SKILL_DIR}`: setup-repo, setup-user, work-plan,
test-first. Ihre echten Läufe in Eval-Workspaces zeigen, dass der Weg trägt.

## Constraints

**Gemessen am 2026-10-14 (CLI 2.1.296)** mit einer Probe-Skill, die die Variable auf drei
Wegen ausgibt:

| Ort | Ergebnis |
| --- | --- |
| Text der SKILL.md, `${CLAUDE_SKILL_DIR}` | ersetzt durch den absoluten Pfad des Skill-Ordners |
| Bash-Umgebung, `$CLAUDE_SKILL_DIR` | leer — die Variable ist nicht gesetzt |
| Reference, mit Read gelesen, `${CLAUDE_SKILL_DIR}` | bleibt wörtlich, die Shell macht daraus einen leeren String |

Daraus folgt: Ein Skript-Aufruf gehört in die SKILL.md. Eine Reference, die einen Aufruf
zeigt, muss auf die SKILL.md verweisen; mit `${CLAUDE_SKILL_DIR}` darin liefe der Befehl
gegen `/scripts/…`.

Nachbar-Skripte über `${CLAUDE_SKILL_DIR}/../<andere>/scripts/` nur innerhalb eines
Plugins oder innerhalb der Projekt-Kopien (Spec 20, „Kein Dateiverweis über eine
Plugin-Grenze"); impl-plan und skill-forge rufen den Lint von subagent-dev so auf, alle
drei liegen unter `.claude/skills/`.

Tier unverändert je Skill. Gate-Grade: Die neue Lint-Regel `script-paths` ist G2 wie die
übrigen Regeln von `lint_skill.py`. Kein Hook. Die Kopfzeilen erzeugter Artefakte
(`generated: python skills/<name>/scripts/…`) bleiben: Sie benennen die Herkunft, sie
werden nicht ausgeführt.

## Approach

**Eiserne Regel:** *Ein Skript-Aufruf, den Claude ausführen soll, steht in der SKILL.md
und beginnt mit `${CLAUDE_SKILL_DIR}`; eine Hook-Vorlage hält nie etwas an, nur weil ihr
Skript fehlt.*

### Skill-Struktur

```
skills/skill-forge/
├── SKILL.md                         Schritt 4 nennt script-paths; Regelzahl +1; eigene Aufrufe auf ${CLAUDE_SKILL_DIR}, Lint von subagent-dev über ../subagent-dev
├── references/checklist.md          Regel script-paths in der Tabelle
├── references/spec-brief.md         lint-spec-Aufruf verweist auf die SKILL.md statt auf einen Pfad
└── scripts/lint_skill.py            Tier 1 — Regel script-paths

skills/<name>/SKILL.md               15 weitere Skills: python skills/<name>/scripts/… → python "${CLAUDE_SKILL_DIR}/scripts/…" —
                                     architecture-map, debug-ledger, dev-report, exercise-forge, feature-spec, human-prose,
                                     learning-coach, motion-landing, rest-api-architect, review-context, sql-schema-architect,
                                     subagent-dev, testing-strategy, verified-research; impl-plan über ../subagent-dev
skills/verified-research/references/rating-rubric.md, delta-mode.md   Aufrufe verweisen auf die SKILL.md
skills/debug-ledger/assets/hooks/check-ledger.json        Platzhalter <skill-dir>; fehlt das Skript, Exit 0 mit Hinweis
skills/sql-schema-architect/assets/hooks/migration-gate.json   Platzhalter <skill-dir>
skills/debug-ledger/SKILL.md, skills/sql-schema-architect/SKILL.md   Abschnitt Hook: <skill-dir> durch den Pfad aus ${CLAUDE_SKILL_DIR} ersetzen
evals/skill-forge/evals.json, evals/fixtures/sf-relpath/   Eval 7 neu, Eval 1 um script-paths ergänzt
.claude/skills/*                     Projekt-Kopien über sync_skills.py
tests/test_skill_forge_lint.py, tests/test_skills_lint.py, tests/test_skill_forge_evals_schema.py, tests/test_skill_dir_paths.py   siehe Tests
docs/known-limits.md                 Abschnitt „Skriptpfade" ersetzt die Zählung aus Spec 20
docs/superpowers/reports/skill-dir-report.md   Report mit „Was nicht gemessen wurde"
```

### Ablauf (Bau)

1. **Lint-Regel zuerst.** `script-paths` meldet als `finding`:
   (a) in der SKILL.md ein Aufruf `skills/<eigener-name>/scripts/` (ausführbar, also nach
   `python`, `python3`, `py` oder in einem Codeblock), (b) in einer Reference
   `${CLAUDE_SKILL_DIR}`, (c) in einem Hook-Asset unter `assets/hooks/` ein Pfad
   `skills/<name>/scripts/` statt des Platzhalters `<skill-dir>`. Kopfzeilen
   (`generated: …`) zählen nie. Das Register `KNOWN_FINDINGS` in
   `tests/test_skills_lint.py` wächst nicht: alle 16 Skills werden im selben Bau
   umgestellt.
2. **Umstellen je Skill** — mechanisch, je Skill ein Task: Aufrufe in der SKILL.md,
   Verweise in den References, Projekt-Kopie über `sync_skills.py`, `lint_skill.py
   --base` ohne neuen Befund, `evals_due` notieren.
3. **Hook-Vorlagen.** `check-ledger.json` prüft vor dem Unterprozess, ob das Skript
   existiert; fehlt es, schreibt es einen Hinweis auf stderr und endet mit 0. Beide
   Vorlagen tragen `<skill-dir>`; die SKILL.md sagt, dass beim Übernehmen der Pfad aus
   `${CLAUDE_SKILL_DIR}` eingesetzt wird, absolut, mit Schrägstrichen.
4. **Evals der umgestellten Skills** im Harness (seit 2026-10-14 als root lauffähig),
   je Skill einmal mit Skill: `run_evals.py --skill <name> --class contract`.

### Contract

- **Aufruf in der SKILL.md, mit `${CLAUDE_SKILL_DIR}`.** Mechanismus: `script-paths` (G2).
- **References ohne `${CLAUDE_SKILL_DIR}`.** Sie nennen das Skript beim Namen und
  verweisen auf den Aufruf in der SKILL.md.
- **Hook-Vorlagen halten nichts an, weil ein Skript fehlt.** Ein Test führt die Vorlage
  von debug-ledger mit fehlendem Skript aus und erwartet Exit 0.
- **Anti-Zeremonie-Fall:** Eine Skill ohne Skripte bekommt `script-paths: pass` ohne
  Änderung.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| Skill bauen oder prüfen, Regel `script-paths` | **skill-forge** | diese Spec ändert die Regeln, nicht den Ablauf von skill-forge |
| Plugin-Zuordnung, Projekt-Kopien | Spec 20 (`sync_skills.py`, `plugin-membership`) | unverändert |
| Hook-Vorlage übernehmen | **debug-ledger**, **sql-schema-architect** (Abschnitt Hook) | diese Spec ändert nur den Pfad und das Verhalten bei fehlendem Skript, nicht, was der Hook prüft |

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_script_paths_rule` | `tests/test_skill_forge_lint.py` | (a) bis (c) als `finding`, Kopfzeile `generated: python skills/…` und eine Skill ohne Skripte als `pass` |
| `test_no_finding_outside_the_register` | `tests/test_skills_lint.py` | unverändert; das Register wächst nicht |
| `test_skill_md_calls_resolve_from_skill_dir` | `tests/test_skill_dir_paths.py` | jeder `${CLAUDE_SKILL_DIR}/scripts/<datei>` und `${CLAUDE_SKILL_DIR}/../<skill>/scripts/<datei>` in einer SKILL.md zeigt auf eine existierende Datei |
| `test_hook_templates_never_block_on_missing_script` | dito | `check-ledger.json` mit `<skill-dir>` auf einen leeren Ordner, Payload `git commit` → Exit 0, Hinweis auf stderr |

### Evals

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-one-sentence-change-lints-only` | contract | `sf-existing` mit Manifest | unverändert; zusätzlich `file_matches` auf `.skills/cache/skill-forge/lint.json`: `"id": "script-paths", "status": "pass"` | das `pass` der neuen Regel schreibt nur der Lint; die Fixture-Skill hat keine Skripte |
| 7 | `repo-relative-script-path-is-reported` | contract | `sf-relpath` | `file_matches` `.skills/cache/skill-forge/lint.json` auf `"id": "script-paths", "status": "finding"`; `file_unchanged` `skills/relpath-x/SKILL.md` | nur `lint_skill.py` kennt die Regel; „Prüfen ändert nichts" steht in der SKILL.md von skill-forge |

Prompts: Eval 1 unverändert, Eval 7 „Prüfe die Skill relpath-x mit skill-forge." Die Fixture `sf-relpath` trägt eine
Mini-Skill mit einem Skript und dem Aufruf `python skills/relpath-x/scripts/run.py` in der
SKILL.md, dazu `docs/artifact-header.md` und Manifest wie `sf-plugin-orphan`.

## Alternatives considered

**Die Variable in die Bash-Umgebung bringen** (ein SessionStart-Hook, der
`CLAUDE_SKILL_DIR` exportiert). Verworfen: Es gibt keinen einen Skill-Ordner je Session,
und ein Hook, der Umgebung setzt, ist mehr Mechanik als das Problem.

**Skripte nach `~/.skills/bin` installieren.** Verworfen: eine zweite Kopie neben dem
Plugin-Cache, die veraltet, und ein Schreibzugriff außerhalb des Repos.

**References dürfen `${CLAUDE_SKILL_DIR}` tragen, Claude ersetzt es selbst.** Verworfen
nach der Messung: Die Shell ersetzt es durch einen leeren String, der Befehl läuft gegen
`/scripts/…` und scheitert mit einer irreführenden Meldung.

## Out of scope

Die Kopfzeilen erzeugter Artefakte und die `GENERATED`-Konstanten der Skripte (Herkunft,
kein Aufruf). Tests, Pläne und Reports, die `skills/<name>/scripts/` im Repo aufrufen —
sie laufen in diesem Checkout. Ein Lauf der Skills in einem fremden Repo über ein
installiertes Plugin; gemessen wird der Eval-Workspace, der dieselbe Lage hat.

## Open questions

*Annahme:* Hook-Vorlagen werden von Hand übernommen (G3, Spec 00 §4); ein Platzhalter,
den Claude beim Übernehmen ersetzt, genügt — widersprich, falls die Vorlagen ein
Installationsskript bekommen sollen.

*Annahme:* `evals_due` der 16 Skills wird mit je einem Contract-Lauf im Harness bedient;
behavior-Evals mit Judge laufen nicht erneut, weil sich an ihrer Doktrin nichts ändert.

## Next steps

Review durch einen unabhängigen Subagenten, dann Plan mit `impl-plan` (16) und Bau.
