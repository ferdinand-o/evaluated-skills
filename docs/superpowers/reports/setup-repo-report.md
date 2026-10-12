<!-- skill: skill-forge | schema: 1 | generated: von Hand nach skills/skill-forge/assets/skill-template/report.md -->
# setup-repo — Abschlussbericht (Abschnitt B)

Gebaut nach `specs/Spec 22 – setup-repo.md` und
`docs/superpowers/plans/2026-10-12-setup-repo-b.md`, Tier 1, am 2026-10-12 sequenziell im
Hauptkontext (Gate: alle 13 Tasks gekoppelt). Abschnitt A (Harness) war vorher ein
eigener PR. Abschnitt C (Ziele) und D (Ziel-Reviewer) fehlen.

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
  - `cc-dev` listet die Skill.
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
  `enabledPlugins: {"cc-dev@cc-skills": false}` blieb erhalten.
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
- **Abschnitt C und D.** Kein Ledger, keine Zielregel, kein Bereichs-Hook, keine
  Vorlagen-Messung, kein Ziel-Reviewer.

## Offen für die nächste Runde

- Abschnitt C nach eigenem Plan: Ledger, Zielregel, Bereichs-Hook, Vorlagen-Messung; dann
  Eval 1 und 4 um die Assertions auf Zielregel, Hook und Ledger ergänzen.
- Abschnitt D, sobald die Delphi-Prüfpunkte vorliegen.
- Erster echter Lauf auf dem Windows-PC und auf einem Repo des Nutzers.
- `detect_repo.py` zählt Sprachen auch aus Fixture-Ordnern; auf diesem Repo meldet es
  TypeScript, weil Fixtures `.ts`-Dateien tragen. Für die Verifikation ohne Folgen, für
  das Frontend womöglich nicht.
