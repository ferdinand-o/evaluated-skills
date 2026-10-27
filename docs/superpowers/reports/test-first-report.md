<!-- skill: skill-forge | schema: 1 | generated: von Hand nach skills/skill-forge/assets/skill-template/report.md -->
# test-first — Abschlussbericht

Gebaut nach `specs/Spec 24 – test-first.md`, Tier 1, am 2026-10-13 sequenziell im
Hauptkontext nach `docs/superpowers/plans/2026-10-13-test-first.md` (7 Tasks, das Gate
koppelte alle). Jeder Task wurde mit `plan_to_tasks.py verify` in einem sauberen Worktree
abgenommen.

## Was entstanden ist

- `skills/test-first/SKILL.md` (92 Zeilen): Zyklus je Verhalten in sieben Schritten mit
  den Aufrufen von `tdd_log.py`, Ausnahmen („Kein Test-Zyklus nötig"), Verzicht
  („ungetestet auf Wunsch"), „Druck ist kein Verzicht", Übergabe aus `status`.
- `scripts/tdd_log.py` (Stdlib): `start`, `red`, `green`, `refactor`, `status` nach dem
  Zustandsmodell der Spec. Der Zustand je Test steht nur im Log und wird bei jedem Aufruf
  aus dem letzten Abschnitt gelesen. Ausführung wie `verify_stop.py`, dazu eine eigene
  Prozessgruppe, damit die Zeitgrenze die ganze Befehlskette beendet.
- `references/cycle.md`: Zustandsmodell, was ein Verhalten ist, sofort grün, ein Test je
  Lauf je Runner, Grenzen des Rot.
- Fünf Evals mit den Fixtures `tf-docs`, `tf-feature`, `tf-existing`;
  `tests/test_test_first_fixtures.py` spielt das erwartete Verhalten mit dem echten
  Skript in Eval-Workspaces nach und bewertet es mit `evalkit`.
- Nachbarn: testing-strategy (Description und Abgrenzung), debug-ledger (Abgrenzung) und
  der Code-Task in work-plan verweisen auf test-first; `evaluated-dev` listet die Skill;
  Routing-Zeile in README und Spec 00. `test_no_superpowers_routing_targets` sucht jetzt
  auch `test-driven-development`; `sync_skills.py --report` bleibt bei 0.

## Die Entscheidungen, die den Bau geprägt haben

- **Kein zweiter Zustandsspeicher.** Der Zustand je Test wird aus dem Log gelesen, nicht
  aus einer JSON-Datei daneben. So kann das Log nicht von einem Zustand abweichen, den
  niemand sieht.
- **Prozessgruppe statt `subprocess.run(timeout=…)`.** Mit `shell=True` beendet die
  Zeitgrenze sonst nur die Shell; ein Kindprozess, der die Pipe offen hält, blockiert den
  Aufruf weiter. Der Test mit 0,5 s Zeitgrenze läuft so in unter einer Sekunde.
- **Die Description von test-first nennt superpowers ohne Präfix.** Mit
  `superpowers:test-driven-development` darin zählte `--report` wieder 1, sobald
  test-first in `evaluated-dev` steht.

## Was gemessen wurde

Suite: 1 521 grün, 3 übersprungen, 1 rot (`test_rest_api_architect_gate`, Spectral fehlt
in der Umgebung). `lint_skill.py skills/test-first` ohne Befund.

**Echte kopflose Sessions** (`claude -p` mit `--allowedTools`, `--permission-mode
acceptEdits`, CLI 2.1.296), Workspaces über `evalkit.workspace.prepare()`, Bewertung mit
`evalkit.runner.grade()`:

| Eval | erste Fassung | nach dem Fix | ohne Skill |
| --- | --- | --- | --- |
| 1 Anti-Zeremonie, Doku-Tippfehler | 0/1 | 2/2 | 0/1 |
| 2 Rot vor Grün im Log | 1/1 | 1/1 | 0/1 |
| 3 sofort grün markiert | 1/1 | 1/1 | 0/1 |
| 4 Druck, trotzdem Rot zuerst | 1/1 | 1/1 | 0/1 |
| 5 ausdrücklicher Verzicht | 0/1 | 2/2 | 0/1 |

Ohne Skill entstand nie ein Log; bei Eval 1 und 5 fehlte der Wortlaut. In Eval 3 hielt
der Lauf mit Skill fest, dass der neue Test sofort grün war, und ließ `src/slug.py`
unverändert. In Eval 4 lief das Rot als Sammelfehler (`ImportError`, pytest Exit 4) — laut
Spec ein echtes Rot, weil der Test scheitert, solange der Code fehlt.

**Der wichtigste Befund: Ausnahme und Verzicht leben in der Description.** Im ersten Lauf
von Eval 1 und 5 rief Claude die Skill gar nicht auf: Eine Doku-Korrektur und ein
Auftrag „ohne Tests" sind gerade die Fälle, für die test-first nicht gilt. Das Verhalten
stimmte (kein Zyklus, kein Test), der Wortlaut nicht — er stand nur im Rumpf; Claude
schrieb „Einen Test-Zyklus braucht es dafür nicht" und „wie gewünscht". Der Fix nennt
beide Sätze wörtlich in der Description. In den vier Läufen danach wurde die Skill wieder
nicht geladen, und alle vier bestanden; in Eval 2 bis 4 lud Claude sie jedes Mal. Das
gilt für jede Skill mit einer Ausnahme: Was im Ausnahmefall gesagt werden soll, gehört in
die Description, weil der Rumpf dann nie gelesen wird.

**testing-strategy nach der Description-Änderung** (`evals_due`), je ein Lauf mit Skill:

| Eval | Ergebnis |
| --- | --- |
| `anti-ceremony-single-test-stays-short` | bestanden |
| `routing-trap-asks-instead-of-guessing` | bestanden |
| `extension-trap-sw-termination-named` | mechanisch bestanden; Judge-Claim von mir bejaht |
| `legacy-trap-characterization-not-invented-behavior` | mechanisch bestanden; Judge-Claim von mir bejaht |

Der Anti-Zeremonie-Fall, den eine frühere Klausel zu `test-driven-development` schon
einmal ausgeschlossen hatte (known-limits, testing-strategy), besteht mit der neuen.

## Was nicht gemessen wurde

- **Auslösen in Konkurrenz.** Die Evals installieren test-first allein; ob die Skill neben
  testing-strategy, debug-ledger und dem superpowers-Plugin auslöst, misst kein Lauf.
- **Andere Runner als pytest.** `cycle.md` nennt vitest, jest, go und cargo; gelaufen ist
  nur pytest.
- **Windows.** Shell `cmd.exe`, keine Prozessgruppe bei der Zeitgrenze.
- **Ob der Befehl wirklich den genannten Test ausführt.** Das Log belegt den Lauf, nicht
  dessen Zuschnitt.
- **Ein unabhängiger Judge** für die zwei behavior-Evals von testing-strategy; bewertet
  habe ich sie selbst.

## Offen für die nächste Runde

- Spec 21 Abschnitt B: `superpowers-gaps.json` mit dem Stand nach Spec 23 und 24,
  `route_check.py` und die Abschaltbedingung.
- Eine Längenprüfung der Description im Lint von skill-forge — die von test-first lag
  nach dem Fix kurz bei 1032 Zeichen, und der Lint schwieg.
