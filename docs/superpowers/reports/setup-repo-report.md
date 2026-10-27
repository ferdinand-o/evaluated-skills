<!-- skill: skill-forge | schema: 1 | generated: von Hand nach skills/skill-forge/assets/skill-template/report.md -->
# setup-repo — Abschlussbericht (Abschnitt B und C)

Gebaut nach `specs/Spec 22 – setup-repo.md`, Tier 1, am 2026-10-12 sequenziell im
Hauptkontext: Abschnitt B nach `docs/superpowers/plans/2026-10-12-setup-repo-b.md`
(13 Tasks), Abschnitt C nach `docs/superpowers/plans/2026-10-12-setup-repo-c.md`
(11 Tasks); das Gate koppelte jeweils alle Tasks. Abschnitt A (Harness) war vorher ein
eigener PR. Abschnitt D (Ziel-Reviewer) fehlt. Die Abschnitte bis „Was nicht gemessen
wurde" beschreiben B; Abschnitt C folgt danach.

## Was entstanden ist

- `skills/setup-repo/SKILL.md` (117 Zeilen) mit den Modi plan, apply und check, nur als
  Slash-Befehl (`disable-model-invocation: true`, im Lint über `CLAUDE_CODE_ONLY`).
- Vier Werkzeuge, keines importiert ein anderes:
  - `detect_repo.py` erkennt Sprachen, Frontend, Runner, Tests, Linter, CI,
    CLAUDE-Dateien, `AGENTS.md`, Projekt-Skills und Plugin-IDs.
  - `harvest_rules.py` sammelt Kandidaten mit Quelle und `checked_by`.
  - `plan_repo.py` wählt den Verifikationsbefehl aus Runner-Einträgen, zählt das Budget,
    setzt Plugins je Repo und schreibt `plan.md` mit gehashtem Block. Die Klassen kommen
    über `--classes`; ohne Angabe gelten die des letzten Plans.
  - `apply_repo.py` prüft Hash, Bestand und uncommittete Ziele, legt Backups an, mischt,
    probt den Hook und committet nie. Mit `--check` ist es ein trockener apply, der nur
    `check.md` schreibt.
- Ein opt-in-Stop-Hook `verify_stop.py`: höchstens drei Blocks in Folge, „ungeprüft — …
  fehlt" einmal je Session. Das Fragment ruft ihn über den Starter mit `python3`- und
  `python`-Fallback auf.
- Zwei References, das CLAUDE.md-Gerüst, fünf Evals mit fünf Fixtures und ein
  Fixture-Test, der jeden Eval mit den installierten Skripten nachspielt.
- Nachbarn:
  - Rückverweise in testing-strategy, review-context und feature-spec.
  - `evaluated-dev` listet die Skill.
  - Routing-Zeilen in Spec 00 und README.
  - Kopfzeilen-Ausnahme für Rules mit `paths` in `docs/artifact-header.md`.

## Die Entscheidungen, die den Bau geprägt haben

- **check liegt in `apply_repo.py --check`.** Die Spec nennt kein Skript für `check.md`,
  Eval 1 bindet aber daran. Bei setup-user schloss erst eine Fix-Runde dieselbe Lücke,
  hier stand die Entscheidung im Plan.
- **Klassen über `--classes`.** Claude bearbeitet kein JSON von Hand. Ein erneuter Plan,
  etwa um den Hook zuzuschalten, behält die Klassen des letzten Plans, solange der
  Kandidatentext gleich ist.
- **Der Hook liest den Befehl aus der CLAUDE.md.** Eine Quelle statt zwei. Ein
  abgeleiteter Befehl (Delphi) steht mit Zusatz in der Zeile, der Hook findet ihn nicht,
  und angeboten wird er dann auch nicht.
- **Die CLAUDE.md nennt den Repo-Namen nicht.** Sonst hinge der Hash am Ordnernamen.
- **Lesson:** Die Lint-Regel `script-tier` verlangt „Tier N" im Docstring jedes Skripts.
  Kein Code-Task nannte das, deshalb gab es eine Fix-Runde nach Task 9.
- **Fix-Runde aus dem Ende-zu-Ende-Lauf:** Auf einer Kopie dieses Repos zeigte die
  Ansicht `.skills/cache/` als neue `.gitignore`-Zeile, obwohl sie schon stand. Jetzt
  trägt die Operation nur fehlende Zeilen, und `/x` gilt als gleich `x`.

## Was gemessen wurde

Endstand der Suite: 1 458 grün, 3 übersprungen, 2 rot. Rot sind nur die beiden vorbestehenden
Tests, `test_rest_api_architect_gate` (Spectral) und der Lint-Registertest für
mobile-audit. `lint_skill.py skills/setup-repo` meldet keinen Befund.

Ende-zu-Ende auf einer Kopie dieses Repos, mit leerem Config-Verzeichnis:
- **Erkennen und Ernten:** ein Kandidat, `testpaths` (Klasse `werkzeug`).
- **Plan:** Verifikation `python -m pytest` aus `[tool.pytest.ini_options]`, Budget 20
  von 150.
- **apply:** „angewendet und geprüft". Geschrieben wurden `CLAUDE.md`, eine fehlende
  `.gitignore`-Zeile und `permissions.allow`. Der committete Schalter
  `enabledPlugins: {"evaluated-dev@evaluated-skills": false}` blieb erhalten.
- **check:** „keine Abweichung", HEAD unverändert.

Eval-Läufe außerhalb des Harness: Workspace über `evalkit.workspace.prepare()`, je ein
Opus-Agent mit nichts als dem Prompt, Bewertung mit `evalkit.runner.grade()` gegen die
Baseline. Mit Skill bekam der Agent den Hinweis auf `.claude/skills/setup-repo/`, ohne
Skill lag dort nichts.

| Eval | mit Skill | ohne Skill | Beobachtung ohne Skill |
| --- | --- | --- | --- |
| 1 Anti-Zeremonie, check | bestanden | nicht bestanden | prüfte von Hand und änderte nichts, schrieb aber kein `check.md` |
| 2 plan als Default | bestanden | nicht bestanden | deutete `/setup-repo` als session-start-hook, legte `.claude/settings.json` und einen Hook an |
| 3 plan ohne Tests | bestanden | nicht bestanden | ebenso session-start-hook, kein Plan |
| 4 apply treu | bestanden | nicht bestanden | setzte den Plan von Hand treu um; nur `apply.md` fehlt |
| 5 manipulierter Plan | bestanden | nicht bestanden | rechnete den Hash von Hand nach, erkannte die Manipulation und wandte nichts an; kein `apply.md` |

Fünf von fünf mit Skill, null von fünf ohne, ein Lauf je Eval — eine Stichprobe. Die
Läufe ohne Skill zeigen, dass die Diskriminatoren am Artefakt hängen, nicht am
Verhalten: In Eval 1, 4 und 5 handelte das Basismodell in der Sache richtig. Die Evals
messen damit, dass die Skripte laufen, nicht, dass die Skill bessere Entscheidungen
erzwingt.

## Was nicht gemessen wurde

- **Der Harness selbst.** `run_evals.py` bricht unter root ab; keiner der fünf Evals lief
  im Harness.
- **Windows.** Der Starter (`command -v python3` gegen den Store-Platzhalter), der
  Verifikationsbefehl unter `cmd.exe` und `os.replace` bei offenem Leser zeigt erst der
  erste Lauf auf dem Windows-PC.
- **Echte Plugin-Installationen.** Plugin-IDs sind nur gegen Fake-Config-Verzeichnisse
  gemessen; wie `installPath` bei einem Marketplace mit `source: "./"` aussieht, ist
  geraten.
- **Die Klassifikation.** Nur Eval 2 misst sie, mit einem Kandidaten.
- **Die Wirkung im Alltag.** Ob Claude mit der erzeugten CLAUDE.md wirklich vor jeder
  Erfolgsmeldung verifiziert und ob der Verifikations-Hook in einer echten Session
  hilft, misst nichts.
- **Abschnitt D.** Kein Ziel-Reviewer.

## Abschnitt C — Ziele

### Was entstanden ist

- `references/goals.md`: Ledger-Schema (*Aktiv*, *Kandidaten*, *Erledigt*), IDs `G<n>`,
  „Fertig wenn" nach der `/goal`-Doku, Glob-Dialekt der Bereiche, die vier Klassen,
  Ausnahmen des Hooks.
- `assets/goals.md` (leerer Ledger), `assets/rules/goals.md` (immer geladene Zielregel,
  24 Zeilen), `assets/hooks/goal-scope.json` (beide Ereignisse, derselbe Starter).
- `assets/runtime/goal_scope.py`: `UserPromptSubmit` hält die Basis des Turns fest und
  gibt eine offene Meldung als `additionalContext` aus; `Stop` meldet Dateien außerhalb
  der Bereiche per `systemMessage`. Er hält nie etwas an.
- `plan_repo.py` legt Ledger und Regel an, wenn sie fehlen, wählt den Bereichs-Hook vor
  (`--without-goal-hook` wählt ihn ab) und kopiert Hook-Skripte nur, wenn sie fehlen oder
  abweichen. `apply_repo.py` erkennt beide eigenen Hooks, probt `goal_scope.py` mit
  Beispiel-Payload in einem Temp-Zustand und prüft in `check` die Ledger-Kopfzeile.
- Fixtures neu erzeugt; Eval 1 prüft zusätzlich Zielregel, Bereichs-Hook und Ledger auf
  `file_unchanged`, Eval 4 `goal_scope` in den Settings.
- Vorlagen-Messung in `evals-templates/` mit Fixture `sr-goals-seeded` und zwei Fällen.
- handoff nennt `docs/goals.md` unter „Einstiegspunkte"; README nennt `evals-templates/`.

### Entscheidungen

- **Proben schreiben keinen echten Zustand.** `goal_scope.py` liest den Zustandspfad aus
  `SETUP_REPO_GOAL_STATE`; `apply` und `check` proben mit einer Temp-Datei.
- **`src/` gilt als `src/**`.** Die Spec nannte den Fall nicht.
- **Ledger und Regel kommen immer**, nur der Hook ist abwählbar; die Regel schweigt ohne
  aktives Ziel.

### Was gemessen wurde

Suite: 1 488 grün, 3 übersprungen, 1 rot (`test_rest_api_architect_gate`, Spectral fehlt
in der Umgebung). `lint_skill.py skills/setup-repo` ohne Befund.

**Echte kopflose Sessions.** Neu in dieser Runde: `claude -p` läuft hier als root, wenn
man `--dangerously-skip-permissions` weglässt und die Werkzeuge mit `--allowedTools`
freigibt (`--permission-mode acceptEdits`). Damit lädt Claude Code im Workspace
CLAUDE.md, Rules, Projekt-Skills und Hooks wie in echt — anders als die Agenten-Läufe
aus Abschnitt B. Workspaces über `evalkit.workspace.prepare()`, Bewertung mit
`evalkit.runner.grade()`, ein Lauf je Eval:

| Eval | mit Skill | ohne Skill |
| --- | --- | --- |
| 1 Anti-Zeremonie, check | bestanden | nicht bestanden |
| 2 plan als Default | bestanden | nicht bestanden |
| 3 plan ohne Tests | bestanden | nicht bestanden |
| 4 apply treu | bestanden | nicht bestanden |
| 5 manipulierter Plan | bestanden | nicht bestanden |

**Vorlagen-Messung der Zielregel**, je drei Läufe:

| Fall | Runde 1 | Runde 2 |
| --- | --- | --- |
| README-Prompt erzeugt keine Ledger-Zeile | 3/3 | 3/3 |
| Fehler in `dates.py` wird Kandidat, `dates.py` bleibt | 1/3 | 1/3 |

Runde 1 deckte zwei Schwächen auf: Die installierte Skill unter `.claude/skills/` machte
`ruff check .` und damit `make check` rot, und zwei Läufe hielten sich damit auf. Beide
ordneten die Lint-Befunde richtig als neues Ziel ein, fragten aber, statt einzutragen;
einer hielt den Bereich von G1 für ein Schreibverbot auf `docs/goals.md`. Fix-Runde: Die
Regel sagt „Eintragen ist kein Umsetzen: ohne Rückfrage, und `docs/goals.md` liegt nie
außerhalb eines Bereichs"; die Fixture nimmt `.claude` von ruff aus.

In Runde 2 lasen die zwei gescheiterten Läufe `dates.py` nicht und meldeten „nichts
Weiteres entdeckt". Bezogen auf die Läufe, die den Fehler entdeckten, trug die Regel ihn
in beiden Runden jedes Mal als Kandidat ein und ließ `dates.py` unverändert (2 von 2).
Der Fall misst also Entdecken und Eintragen zusammen; die Fixture wurde nicht verbogen,
bis die Quote stimmt.

### Was nicht gemessen wurde

- **Ob der Bereichs-Hook neue Ziele zuverlässig genug erkennt.** Mit `-p` sieht Claude
  seine Meldung nie; in den kopflosen Läufen lief er, wirkte aber nur im Log.
- **Interaktive Sessions** mit Meldung beim nächsten Prompt — gemessen nur im Test.
- **Windows** für den Starter beider Hooks.
- **Ob die Fix-Runde der Regel das Nachfragen dauerhaft verhindert** — in Runde 2 kam
  kein Lauf in die Lage.

## Offen für die nächste Runde

- Die Delphi-Prüfpunkte des Nutzers nach `references/review/delphi.md`.
- Den Eval-Harness auf `--allowedTools` statt `--dangerously-skip-permissions` umstellen;
  dann läuft er auch als root (known-limits, „Der Harness läuft nicht als root").
- Vorlagen-Messung mit einer Fixture, in der der Nebenbefund beim Arbeiten zwangsläufig
  sichtbar wird, etwa über einen Test, der `dates.py` berührt.
- Erster echter Lauf auf dem Windows-PC und auf einem Repo des Nutzers.
- Behoben am 2026-10-12: `detect_repo.py` zählte Sprachen auch aus Fixture-Ordnern und
  meldete auf diesem Repo TypeScript; Ordner `fixtures`, `__fixtures__` und `testdata`
  werden jetzt übersprungen.

## Abschnitt D — Ziel-Reviewer (2026-10-14)

Gebaut nach `docs/superpowers/plans/2026-10-14-setup-repo-d.md` (8 Tasks, das Gate
koppelte alle), sequenziell im Hauptkontext, jeder Task mit `verify` im sauberen Worktree
abgenommen. Auf Wunsch des Nutzers ohne Delphi-Prüfpunkte gebaut.

### Was entstanden ist

- `references/review/python.md`, `typescript.md`, `generic.md` mit je einer Zeile pro
  Prüfpunkt (ID, Text, Quelle); `delphi.md` leer mit Hinweis, dass die Punkte vom Nutzer
  kommen.
- `assets/agents/reviewer.md`: Subagent mit drei Prüfungen („Fertig wenn" belegt, Bereich,
  Prüfpunkte des Stacks), Urteil je Punkt und Failure-Szenario je Befund; sucht keine Bugs.
- `plan_repo.py` plant `.claude/agents/reviewer.md` mit den Prüfpunkten der erkannten
  Sprachen und den allgemeinen; ein vorhandener bleibt unberührt, `--without-reviewer`
  wählt ab. Ein Stack ohne Prüfpunkte steht als „ungeprüft — keine Prüfpunkte für …" da.
- Die Zielregel nennt den Reviewer vor *Erledigt* (jetzt 25 von 25 Zeilen); SKILL.md,
  `references/goals.md`, `plan-format.md`, `docs/artifact-header.md` und review-context
  ziehen nach.

### Entscheidungen

- **Ohne Delphi bauen.** Der Nutzer entschied am 2026-10-14, D nicht länger an seinen
  Delphi-Punkten hängen zu lassen. Sie kommen später als reine Datenergänzung; Code und
  Tests ändern sich dafür nicht.
- **Prüfpunkte als Daten, nicht im Asset.** Das Asset hat einen Platzhalter;
  `plan_repo.py` setzt die Zeilen ein. So landen im Zielrepo nur die Punkte seines Stacks.
- **Quellen ohne Sprungmarken.** PEP 8, PEP 621 und die npm-Doku waren aus dem Container
  nicht erreichbar (Netzwerk-Policy, auch WebFetch). Die Prüfpunkte nennen Seite und
  Abschnittsnamen; Anker aus dem Gedächtnis wären unbelegt gewesen.

### Was gemessen wurde

Suite: 1 542 grün, 3 übersprungen, 1 rot (`test_rest_api_architect_gate`, Spectral fehlt
in der Umgebung). `lint_skill.py skills/setup-repo` ohne neuen Befund.

Echte kopflose Sessions (`claude -p` mit `--allowedTools`, CLI 2.1.296), je ein Lauf,
bewertet mit `evalkit.runner.grade()` — alle fünf Evals erneut, weil sich SKILL.md,
Zielregel und Fixtures geändert haben:

| Eval | mit Skill | ohne Skill |
| --- | --- | --- |
| `anti-ceremony-check-on-aligned-repo-changes-nothing` | bestanden | — |
| `plan-from-repo-writes-only-report` | bestanden | — |
| `plan-without-tests-says-unverified` | bestanden | — |
| `apply-executes-plan-faithfully` | bestanden | nicht bestanden |
| `apply-refuses-tampered-plan` | bestanden | — |

**Die neue Assertion diskriminiert nicht.** Eval 4 prüft jetzt auch, dass
`.claude/agents/reviewer.md` die ID `py-test-for-public` trägt. Ohne Skill las der Agent
den Block aus `plan.md`, setzte ihn mit einem eigenen Skript um und erzeugte
`reviewer.md` byte-gleich; gescheitert ist der Lauf nur an `apply.md`. Die Notiz des
Evals behauptete vorher das Gegenteil und ist korrigiert. Die Assertion bleibt, weil sie
prüft, dass die Prüfpunkte im Zielrepo ankommen.

### Was nicht gemessen wurde

- **Ein Lauf, in dem ein Ziel abgeschlossen wird** — ob Claude den Reviewer aufruft und
  ob dessen Urteile stimmen.
- **Ob ein Projekt-Agent mit diesem Frontmatter lädt**; geprüft ist nur der Inhalt.
- **Die Quellen der Prüfpunkte** (nicht erreichbar, siehe oben).
- **Delphi** — keine Prüfpunkte.

