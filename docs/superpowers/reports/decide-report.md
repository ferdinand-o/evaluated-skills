<!-- skill: skill-forge | schema: 1 | generated: von Hand nach skills/skill-forge/assets/skill-template/report.md -->
# decide — Abschlussbericht

Gebaut nach `specs/Spec 28 – decide.md`, Tier 1, am 2026-11-02 und 2026-11-03 nach
`docs/superpowers/plans/2026-11-02-decide.md` (10 Tasks) mit `subagent-dev`: Code-Tasks 1 bis 4
und 7 an Opus-Subagenten, Tasks 5 und 6 an Sonnet, Prüfpunkte nach `references/checkpoints.md`.
Dieser Report ist Task 10.

## Was entstanden ist

Zahlen aus `wc -l` im Worktree von Task 10; `git diff --stat 03e05a1..HEAD`: 75 Dateien,
9 791 Zeilen hinzu, 185 weg.

- `skills/decide/SKILL.md` (143 Zeilen, Grenze 150): Einordnung klein oder groß, Schritt 0
  `rules`, Vorrang Auftrag vor Regel vor eigener Einordnung, der feste Satz für Subagenten,
  `check` als letzter Aufruf vor der Antwort.
- `skills/decide/scripts/decide_log.py` (2 247 Zeilen, Stdlib, Tier 1) mit den Unterbefehlen
  `rules`, `add`, `summary`, `resolve`, `open`, `check`, `brief`. `add` kennt Belegzeile,
  Optionenzahl und `--class klein|gross`; `check` übersetzt Globs selbst und liest
  `docs/big-decisions.md` nach der Konsumenten-Regel, auch für `<a>...<b>`.
- `references/`: `reversibility.md` (93), `brief.md` (108), `option-memo.md` (132).
  `assets/big-decisions.md` als Vorlage der Ablage.
- Fünf Evals mit den Fixtures `dc-*` und je ein Strukturtest für Schema und Fixtures.
- 19 Akzeptanz-Tests aus den Stubs von `docs/specs/wip/decide.md` (keiner bleibt übersprungen),
  dazu `tests/test_decide_log.py` (2 528 Zeilen), `test_decide_evals_schema.py` (372) und
  `test_decide_fixtures.py` (249).
- Nachbarn (Task 8, 1066ad6): Routing-Zeile in Spec 00 und README, Rückverweise in feature-spec
  und work-plan, `plan_to_tasks.py generate` schreibt den festen Satz unter Nicht-Ziele jeder
  Task-Datei, decide in `evaluated-dev` und `PROJECT_SKILLS`. Task 9 (be57de7): Abschnitt
  `## decide` in `docs/known-limits.md`.

## Was gemessen wurde

**Tests, selbst ausgeführt im Worktree:**

- `python -m pytest -q tests/test_decide_*.py`: 160 grün.
- `python -m pytest -q` (vor diesem Report): 1 772 grün, 3 übersprungen, 2 rot. Rot sind der
  bekannte Altfehler `test_rest_api_architect_gate.py::test_main_exit_zero_when_degraded_but_checklist_clean`
  und `test_skills_lint.py::test_no_finding_outside_the_register[decide]`, der nur an der
  fehlenden Datei dieses Reports hing (`report-section`). Mit dem Report grün.

**Lint:** `lint_skill.py skills/decide --out .skills/cache/skill-forge/lint.json` vor dem
Report: alle Regeln `pass` außer `report-section` (der Report fehlte) und `neighbors`
UNCHECKED, weil `brainstorming` keinen Ordner unter `skills/` hat (erwidert von feature-spec
und work-plan). Der Stand nach dem Report steht im Commit.

**Eval-Läufe** (`claude -p` 2.1.316 ohne Permission-Host, `--permissions auto`, je Eval eine
Stichprobe; Rohdaten `scratchpad/evals/summary.md` und die Logs daneben):

| Eval | Lauf 1 mit Skill (605fdfe) | Lauf 1 ohne Skill (Spec 18) | Nachlauf | Abschluss mit Skill (e171b54) |
| --- | --- | --- | --- | --- |
| 1 `anti-ceremony-order-in-file-needs-no-decision` | PASS | rot („Keine Entscheidung nötig“ fehlt) | — | PASS |
| 2 `small-decision-cites-repo-source` | FAIL (kein `log.md`) | rot | FAIL (a3e2cf5) | FAIL |
| 3 `side-decision-expensive-stays-open` | PASS | rot | — | PASS |
| 4 `user-order-is-approval` | FAIL (kein „ungeprüft: data-delete“) | rot | FAIL (a3e2cf5); nach e171b54 PASS | PASS |
| 5 `always-ask-rule-upgrades-small` | PASS | rot | — | PASS |
| Summe | 3 von 5 | 0 von 5 grün (alle fünf rot, jeder misst etwas, das nur die Skill beiträgt) | 0 von 2 | 4 von 5 |

- **Eval 2** fiel in allen drei Läufen mit Skill aus demselben Grund: decide wurde nicht
  ausgelöst, es entstand kein `log.md`, obwohl die Änderung (`getLogger(__name__)`) stimmte und
  `CONTRIBUTING.md` die Antwort enthielt. Der Prompt nennt die Skill nicht. Der Nutzer
  entschied, das zu dokumentieren und die Description unverändert zu lassen (known-limits).
- **Eval 4, Diagnose.** Der Runner speichert kein Transcript; ich ließ den Eval von Hand über
  `evalkit.prepare` und `run_agent` laufen (`scratchpad/evals/diag4/`). Das Transcript zeigte:
  Skill geladen, Block in `docs/big-decisions.md` (D-1) korrekt freigegeben, Modell und
  Migration geändert, `check` nie aufgerufen. Die Antwort behauptete trotzdem „Die Prüfung
  meldet keine Änderung ohne Freigabe“. Das ist kein Fehler des Skripts, sondern ein Satz über
  ein Ergebnis, das nie erhoben wurde.
- **Änderung e171b54:** Die SKILL.md macht `check` zum letzten Aufruf vor der Antwort und
  verbietet einen Satz über ein Ergebnis ohne Aufruf. Danach: Eval 4 allein PASS, im
  Abschlusslauf der ganzen Reihe 4 von 5.
- `~/.skills/decide/rules.md` existierte bei keinem Lauf (geprüft: `/root/.skills/decide` fehlt);
  die Evals lesen das echte `HOME`, die Ergebnisse gelten für diesen Fall.
- Nach e171b54 lief **kein** Lauf ohne Skill mehr. Die 0 von 5 ohne Skill gilt für den Stand
  605fdfe; dass die Skill in Eval 4 den Unterschied macht, ist für den Stand davor gemessen.

**Nachbarn:** Der Commit von Task 8 (1066ad6) nennt `evals_due` für feature-spec, work-plan und
subagent-dev: alle False (Lint `--base HEAD`: 0 neue Befunde bei allen dreien; die Descriptions
blieben unverändert, Rückverweise stehen in den Abgrenzungen). Deshalb keine erneuten Evals der
Nachbarn.

## Der Bau

Alle Zahlen aus `.skills/subagent-dev/runlog.jsonl` (39 Zeilen) und `git log 03e05a1..HEAD`.

**Vier Code-Tasks (1 bis 4) und ein Prüfpunkt nach Task 7, je zwei Fix-Runden und eine
Mini-Runde.** Jeder Prüfpunkt reviewte der Reihe nach den Task, dann die erste Fix-Runde, dann
die zweite; nach der zweiten Runde war die Grenze von zwei Runden erreicht und der Hauptagent
legte die Restfunde dem Nutzer vor. Der Nutzer gab je Prüfpunkt eine Mini-Runde frei, ohne
Review danach; die Restfunde gingen nach known-limits.

| Prüfpunkt | Funde je Review (Task, Runde 1, Runde 2) | Besonderheit |
| --- | --- | --- |
| vor Task 2 (nach Task 1) | 15, 10, 15 | zusätzlich Runde 3 (10 Funde) und Mini-Runde 4, vom Nutzer freigegeben |
| vor Task 3 (nach Task 2) | 14, 10, 11 | Mini-Runde |
| nach Task 3 | 12, 10, 10 | Mini-Runde |
| nach Task 4 | 12, 12, 9 | Mini-Runde |
| nach Task 7 (Tasks 5 bis 7) | 12, 12, 12 | Mini-Runde a3e2cf5 |

Tasks 5 und 6 (Sonnet, 82 673 und 96 278 Tokens) und Task 7 (Opus, 174 062) liefen ohne
eigene Fehlerrunde; ihr Review kam gebündelt am Prüfpunkt nach Task 7. Die im runlog
verzeichneten Subagentenläufe summieren sich auf 2 823 458 Tokens in 19 Einträgen; die
Review-Läufe und drei Mini-Runden tragen im runlog keine Token-Zahl und sind darin nicht
enthalten.

**Entscheidungen des Nutzers unterwegs:**

- Prüfpunkt 1, Runde 3: Betriebssystem-Sperre (`fcntl`/`msvcrt`) statt einer eigenen Sperre
  (e6dc62e). Die Randfälle gingen nach known-limits.
- Subagenten wörtlich unterrichten, nicht mechanisch prüfen (8ea0160, Spec 28).
- Restfunde nach den Prüfpunkten 2 bis 4 in den Task known-limits statt in weitere Runden.
- Eval 2 dokumentieren, die Description nicht ändern.

**Spec-Änderungen während des Baus:** Auftrag als Freigabe auch für Regel-Themen
(`rule:<thema>`, 6cffbe8); `dependency` und `permissions` nur teilweise geprüft (5544dec);
`check` nimmt `<a>...<b>` an (a1d7194).

## Fehler im Prozess

- **Worktree für Task 1 ging von `main` aus,** nicht vom Planstand; die Arbeit kam per
  Cherry-Pick in den Branch.
- **Zwei Commit-Messages (29be62f, dd70964) nannten Planänderungen, die nicht gelandet waren.**
  29be62f (Angleichung des Entwurfs) nachgeholt in 211c683, dd70964 (Planänderung zu Task 4)
  nachgeholt in ef8b08f; die Commits bleiben wie sie sind.
- **Der Merge von Task 7 kam vor dem `verify`-Verdikt.** Ursache war ein Planfehler in
  Files/Produces von Task 7; der Plan wurde danach angepasst (vgl. 076a258).
- **`reversibility.md` beschrieb Eval 3.** Der Hauptagent hatte das selbst so verlangt; ersetzt
  durch ein Beispiel ohne Eval-Szenario (8773c92), wie Spec 28 es für `option-memo.md` fordert.
- **Größe.** `decide_log.py` hat 2 247 Zeilen und ist damit deutlich größer, als Spec 28 ein
  Tier-1-Skript zuschneidet. Die Prüfpunkte verlängerten es von Runde zu Runde; zurückgeschnitten
  wurde es nicht. Offen.

## Abnahme

Spec 28 ist **abgenommen mit Vorbehalt.** Vier der fünf Evals sind mit Skill grün, alle fünf
waren ohne Skill rot (Stand 605fdfe). Eval 2 ist rot und bleibt es, weil die Description nicht
verändert wird; das Routing mitten in einer Aufgabe ist damit der gemessene Schwachpunkt. Die
19 Akzeptanzkriterien laufen als Tests (160 decide-Tests grün). Der finale Prüfpunkt über den
ganzen Bau steht aus.

## Finaler Prüfpunkt

Steht aus.

## Was nicht gemessen wurde

- **Der beaufsichtigte Weg mit `AskUserQuestion`.** Alle Evals laufen über `claude -p` ohne
  Permission-Host; ob die gebündelte Frage und `resolve` im Betrieb funktionieren, zeigt kein
  Lauf.
- **Ob Subagenten den festen Satz befolgen.** evalkit liest nur Text; ob ein Subagent startet,
  den Satz bekommt und `decide_log.py add` unterlässt, misst nichts, ebenso nicht, ob
  `CLAUDE_CODE_SESSION_ID` in Subagenten dieselbe ist.
- **Routing außerhalb der fünf Prompts.** Die Description muss mitten in einer Aufgabe
  auslösen; je Fall steht ein Prompt, und Eval 2 zeigt, dass das nicht immer gelingt.
- **Windows und NFS bei der Sperre.** Die Betriebssystem-Sperre ist unter Linux getestet;
  `msvcrt` und Netzwerk-Dateisysteme sind es nicht.
- **Ein Lauf ohne Skill nach e171b54.** Dass ohne Skill weiterhin alles rot wäre, ist für den
  Stand 605fdfe gemessen, nicht für den heutigen.
- **claude.ai ohne Shell.** Dort fehlt das Skript; die Übergabe sagt „ungeprüft“, ein Lauf
  dazu fand nicht statt.
- **Stichprobengröße.** Je Eval standen ein bis drei Läufe; Eval 4 hat nach der Änderung einen
  grünen Einzellauf und einen grünen Abschlusslauf, keine Wiederholung. Der Runner speichert
  kein Transcript, die Diagnose von Eval 4 ist ein Handlauf.

## Offen für die nächste Runde

- Länge von `decide_log.py` gegen Spec 28 prüfen und Teile (Glob-Übersetzer, Sperre) auslagern
  oder die Spec anpassen.
- Eval 2: entweder eine Description, die bei kleinen Fragen mitten in der Arbeit auslöst, oder
  ein Prompt, der die Lage ohne das Wort „entscheiden“ zuspitzt; Entscheidung des Nutzers.
- Ein Runner, der das Transcript speichert, damit die Diagnose wie bei Eval 4 nicht von Hand
  laufen muss.
