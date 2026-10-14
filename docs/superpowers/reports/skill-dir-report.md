<!-- skill: skill-forge | schema: 1 | generated: von Hand nach skills/skill-forge/assets/skill-template/report.md -->
# skill-dir — Abschlussbericht

Gebaut nach `specs/Spec 25 – skill-dir.md` am 2026-10-14, sequenziell im Hauptkontext nach
`docs/superpowers/plans/2026-10-14-skill-dir.md` (10 Tasks, das Gate koppelte alle). Jeder
Task wurde mit `plan_to_tasks.py verify` in einem sauberen Worktree abgenommen. Die Spec
lief vorher durch einen unabhängigen Review, der elf Befunde fand, vier davon blockierend.

## Was entstanden ist

- **17 Skills umgestellt.** 21 Skills rufen ihre Skripte jetzt über `${CLAUDE_SKILL_DIR}`
  auf, an 54 Stellen; vier taten es schon vorher (setup-repo, setup-user, work-plan,
  test-first). verified-research bekam dabei ein `python` vor die Aufrufe (die Skripte sind
  nicht ausführbar), mobile-audit verlor die `<skill-dir>`-Form, human-prose, skill-forge
  und das Skill-Template die Zeilen „# installiert:".
- **Nachbarn:** impl-plan und skill-forge rufen den Lint von subagent-dev über
  `${CLAUDE_SKILL_DIR}/../subagent-dev/`; ein Test hält fest, dass solche Nachbarn im
  selben Plugin oder beide unter `.claude/skills/` liegen.
- **architecture-map** schreibt `python scripts/<datei>` statt `sys.argv[0]` in das
  Artefakt; `drift_check.py` löst jede Form gegen den eigenen Skill-Ordner auf, auch alte
  Footer mit `skills/…` oder einem Pfad einer anderen Maschine.
- **Hook-Vorlagen** von debug-ledger und sql-schema-architect rufen eine Kopie unter
  `.claude/hooks/` über `$CLAUDE_PROJECT_DIR` auf. Fehlt sie, gibt der Hook eine
  `systemMessage` „ungeprüft" aus und endet mit 0; bei einem Verstoß endet er weiter mit 2.
  `migration_gate.py` erkennt den Hook auch am neuen Pfad.
- **Lint-Regel `script-paths`** (fünfzehnte Regel): repo-relative Aufrufe in der SKILL.md,
  `${CLAUDE_SKILL_DIR}` mit `python` in References, Skillpfade in Hook-Vorlagen. Das
  Register in `tests/test_skills_lint.py` blieb leer.
- **Eval 7** `repo-relative-script-path-is-reported` mit Fixture `sf-relpath`; Eval 1 bindet
  zusätzlich an `script-paths: pass`.

## Die Entscheidungen, die den Bau geprägt haben

- **Erst gemessen.** Eine Probe-Skill gab die Variable auf drei Wegen aus: im Text der
  SKILL.md ersetzt, in der Bash-Umgebung leer, in einer Reference wörtlich. Daraus folgt,
  dass jeder Aufruf in die SKILL.md gehört.
- **Hooks kopieren statt Platzhalter.** Der erste Entwurf trug `<skill-dir>` und einen
  absoluten Pfad in `settings.json`. Der Review zeigte: Der Pfad veraltet mit jedem
  Plugin-Update, und ein nicht ersetzter Platzhalter schaltet den Hook still ab. Die Kopie
  nach `.claude/hooks/` folgt setup-repo und ist committbar.
- **Die Regel nach der Umstellung.** Eingebaut nach den Tasks 1 bis 5, damit das Register nie
  wuchs und die Suite nie rot war.

## Was gemessen wurde

Suite im frischen Worktree: 1 546 grün, 3 übersprungen, 1 rot
(`test_rest_api_architect_gate`, Spectral fehlt in der Umgebung).

`evals_due` nach der Umstellung: nur learning-coach (ein Assertion-Muster trifft das Wort
„python" in der Aufrufzeile), motion-landing (Aufrufzeile im Contract-Abschnitt) und
skill-forge (Regelzahl im Contract). Gefahren im Harness als root (Branch
`claude/harness-allowed-tools`), dazu architecture-map, weil sich dort das Verhalten der
Skripte geändert hat. Jeder Fehlschlag wurde gegen `main` nachgefahren:

| Skill | mit Spec 25 | auf main | ohne Skill |
| --- | --- | --- | --- |
| architecture-map | 5/5 | — | — |
| skill-forge | 5/7 | 5/6 | 0/7 grün |
| motion-landing | 2/4 | 2/4 | — |
| learning-coach (contract) | 4/6 | 4/6 | — |

Dieselben Evals scheitern auf `main` mit denselben Meldungen: skill-forge
`routing-new-skill-gets-house-evals` (Manifest-Eintrag fehlt), motion-landing
`artifact-context-degrades-visibly` und `reduced-motion-scene-shows-static-content-not-frozen-hidden`
(kein `verify-report.json`), learning-coach `abrupt-end-still-updates` und
`solution-without-explain-back-keeps-grade`. Sie sind älter als diese Spec und hier nicht
behoben. Der learning-coach-Eval, den `evals_due` meldete
(`short-session-still-updates`), besteht.

**Eval 7** bestand in drei von vier Läufen. Im Harness-Lauf fehlte `lint.json`; in drei
Einzelläufen mit `claude -p` lief der Lint ohne `--base`, schrieb `lint.json` und meldete
genau `script-paths`. Ohne Skill war er rot.

## Was nicht gemessen wurde

- **Ein Lauf in einem fremden Repo über ein installiertes Plugin.** Gemessen ist der
  Eval-Workspace, der dieselbe Lage hat (Skill unter `.claude/skills/`).
- **Eine SKILL.md, die mit Read geladen wird** (Subagent, Cowork, claude.ai) — dort bleibt
  die Variable wörtlich.
- **Ob Claude Code die `systemMessage` eines `PreToolUse`-Hooks anzeigt.**
- **Warum Eval 7 im Harness einmal ohne `lint.json` endete**; der Harness speichert kein
  Transcript (known-limits, Betrieb).
- **Die älteren roten Evals** von skill-forge, motion-landing und learning-coach.

## Offen für die nächste Runde

- Die fünf älteren roten Evals einzeln untersuchen.
- Ein Transcript je Harness-Lauf speichern; ohne es bleibt ein einzelner Fehlschlag wie bei
  Eval 7 unerklärt.
