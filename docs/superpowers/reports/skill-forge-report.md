# skill-forge — Abschlussbericht

Gebaut nach `specs/Spec 17 – skill-forge.md` und `docs/superpowers/plans/2026-09-10-skill-forge.md`.
Zyklus 17, Tier 1, gebaut am 2026-09-10 sequenziell im Hauptkontext (dreizehn Tasks,
ein Commit je Task; das Gate sagte `sequential`, weil jede Task das Skript oder die
Skill-Dateien berührt).

## Was entstanden ist

```
skills/skill-forge/SKILL.md                     93 Zeilen (Grenze 150)
skills/skill-forge/references/checklist.md      19 Punkte je Bauphase, 13 mit Regel-ID
skills/skill-forge/references/form-selection.md „Match the Form to the Failure", übersetzt, sechs Hausfälle
skills/skill-forge/references/evals.md          Diskriminator, Judge, Fixtures, Trigger-Eval-Set, Baseline-Forderung
skills/skill-forge/references/reviewer-prompt.md Bau-Review mit Nachmessen
skills/skill-forge/assets/skill-template/       SKILL.md, evals.json, report.md — bestehen den eigenen Lint
skills/skill-forge/scripts/lint_skill.py        830 Zeilen, Tier 1, dreizehn Regeln, Diff-Modus
evals/skill-forge/evals.json                    5 contract-Evals
evals/fixtures/sf-existing, sf-gate, sf-noanti, sf-spec
tests/test_skill_forge_lint.py                  40 Tests
tests/test_skills_lint.py                       Repo-Test, 5 Tests (2 parametrisiert über 21 Skills)
tests/test_skill_forge_evals_schema.py          8 Tests
```

Nachgezogen: Spec 00 §2 (ID-Präfix `anti-ceremony-`), §5 (Description ohne
Prozessbeschreibung, Routing-Zeile), `README.md`, `impl-plan` und Spec 16 (skill-forge
nicht mehr „geplant"), Abschnitt in `docs/known-limits.md`.

## Die Entscheidungen, die den Bau geprägt haben

**Nur neue Befunde zählen.** Der erste Spec-Entwurf ließ jeden Lauf alle Befunde
zählen; mit 20 von 21 Skills im Register hätte ein geänderter Satz den Lint rot gemacht
und die Eiserne Regel entweder Aufräumen oder Ignorieren verlangt. Jetzt lintet
`--base` den Ordner zweimal — Arbeitsstand und `git show <rev>:` — und der Exit-Code
folgt `new_findings`. Der Basisstand sieht dabei die Nachbarn des echten Repos, sonst
wäre jeder Nachbarn-Befund an der Basis unsichtbar und danach „neu".

**`unchecked` und `hint` sind eigene Zustände.** Sieben Regeln brauchen `docs/`,
`README.md`, `evals/` oder fremde Skills. Im Eval-Workspace fehlt das meiste davon;
dort sagt der Lint `unchecked` mit Grund statt `pass`. `judge-claims` meldet `hint`:
24 von 47 Claims im Repo tragen eine Konjunktion, die meisten legitim — eine Regel, die
das rot machte, wäre ein Register-Eintrag für elf Skills ohne Erkenntnis.

**Die Fixtures sind an der Basis sauber.** Eval 1 misst, ob ein geänderter Satz zur
Zeremonie eskaliert — nicht, ob Altlasten aufgeräumt werden. Dafür trägt `sf-existing`
Report, known-limits-Abschnitt, Routing-Matrix und eine `evals.json` mit Präfix; der
Schema-Test prüft, dass sie ohne Befund und ohne `unchecked` ist.

## Was gemessen wurde

- **Volle Suite: 1123 bestanden beim Bau, 1134 nach der Fix-Runde**, einer fremd rot
  (`test_rest_api_architect_gate.py::test_main_exit_zero_when_degraded_but_checklist_clean`,
  vorbestehend, erwartet ein fehlendes Spectral, das hier über `npx` erreichbar ist).
  42 neue Tests in drei Dateien beim Bau, 53 nach der Fix-Runde, dazu 21 Skills zweimal
  parametrisiert im Repo-Test.
- **Erster Lint-Lauf über alle Skills (2026-09-10):** 20 Skills mit Befund, 79
  (Skill, Regel)-Paare im Register. Je Regel: `report-section` 19, `description` 18,
  `routing` 14, `anti-ceremony-eval` 11, `neighbors` 11, `evals-exist` 3,
  `asset-headers` 2, `gate-language` 1; `script-tier`, `frontmatter`, `skill-md-lines`,
  `fixture-git` 0. Gegen die Spec-Erwartung: `anti-ceremony-eval` 11 statt 14, weil die
  drei Skills ohne `evals.json` nur unter `evals-exist` zählen; `routing` 14 statt „7
  und 6", weil beide Matrizen gefordert sind; `neighbors` 11 statt 13. (Die erste
  Fassung dieses Reports nannte 20 und 15 — sie hatte `skill-forge` selbst mitgezählt.)
- **Selbstbezug:** `lint_skill.py skills/skill-forge` — zwölf Regeln `pass`, `neighbors`
  `unchecked`, weil die Abgrenzung `skill-creator` nennt und der Lint eine fremde Skill
  nicht von einer fehlenden unterscheiden kann; kein Register-Eintrag. Während des Baus
  war die Skill in `_UNDER_CONSTRUCTION` des Repo-Tests statt im Register; mit diesem
  Report ist das entfernt.
- **Jedes `lint.json`-Muster der Evals** greift an einer echten Skript-Ausgabe: Eval 3
  an `sf-gate`, Eval 4 an `sf-noanti`, keines an der sauberen `sf-existing`; Eval 1 und
  2 nachgespielt mit der Änderung aus dem Prompt und `--base HEAD`.
- **Das Template** besteht als Skill in einem Temp-Ordner die Regeln 1–5 und
  `anti-ceremony-eval`; seine `evals.json` lädt über `evalkit`.

## Fix-Runde nach dem Review (2026-09-10)

Zwei unabhängige Reviews — ein Subagent mit frischem Kontext nach dem eigenen
`reviewer-prompt.md`, dazu `/code-review` über den Diff — fanden keinen Spec-Bruch,
aber zwei schwere Löcher im Skript und eine Reihe Präzisionsfehler. Alles behoben,
jeder Punkt mit Test:

- **`neighbors` war fail-open:** Ein genannter Nachbar ohne Ordner im Workspace ergab
  `pass` über eine leere Menge — das `all([])`-Muster aus den Pitfalls, in allen vier
  Fixtures sichtbar. Jetzt zählen genannte Namen (`**name**`, die Hausform), ein
  fehlender Name ist `unchecked`, der Rückverweis wird wortgebunden geprüft
  („unexplained" erwidert `explain` nicht).
- **Traceback statt Befund** bei `fixture.json` als Liste, Verzeichnissen oder toten
  Symlinks unter `scripts/` und `assets/`, Latin-1 in `artifact-header.md`, Binärdateien
  im Diff-Modus. Jede Regel läuft jetzt in einem Fangnetz („Regel abgebrochen" ist ein
  Befund), Dateilisten filtern auf `is_file()`, Git-Ausgabe wird als UTF-8 mit Ersatz
  gelesen.
- **Eval 2 maß nicht, was seine Notiz sagte:** Das Pattern traf die Zeile wegen eines
  Backticks nicht, `evals_due: true` kam allein aus dem Contract. Der Token steht jetzt
  im Ablauf, das Pattern hat keinen Anker, und der Schema-Test bindet den Grund.
- **Eval 3 und 4** bekamen `"git": true`, damit der vorgeschriebene Aufruf mit
  `--base HEAD` eine `lint.json` schreibt statt mit Exit 2 zu enden.
- **`gate-language`:** umbrochene Listenpunkte bleiben eine Einheit, Groß-/Kleinschreibung
  ignoriert, „ohne" ist keine Negation mehr.
- **Diff-Modus:** Pfade relativ zur Git-Wurzel (`rev-parse --show-toplevel`), damit eine
  Sammlung als Unterordner eines größeren Repos funktioniert; `---`/`+++` nur direkt nach
  `diff --git` als Kopfzeile; `--no-renames` (Umbenennung = gelöscht plus neu, wie Spec 17
  sagt); untrackte Dateien zählen; ungültige Regexe stehen im Grund; ein `git diff` statt
  zwei.
- Kleineres: `description: >` als YAML-Block, `Use whenever`; `evals-exist` lehnt leere
  Listen ab wie `evalkit`; `asset-headers`-Ausnahme nur per Pfad; Git-Helfer der Tests
  in `conftest.py`; Register-Zahlen 19 und 14 korrigiert.

## Erster Eval-Lauf (2026-09-11) — außerhalb des Harness

Der Harness fährt hier nicht (root-Container). Ersatz: je Eval ein Workspace über
`evalkit.workspace.prepare()` (Skill installiert unter `.claude/skills/skill-forge/`,
Fixture an der Wurzel, Baseline-Commit), ein Opus-Subagent mit nichts als dem
Eval-Prompt und dem Hinweis „Skills liegen unter `.claude/skills/`", danach Bewertung
mit `evalkit.runner.grade()` gegen die Baseline — dieselben Assertionen wie im Harness.

| Eval | Ergebnis | Beobachtung |
| --- | --- | --- |
| 1 Anti-Zeremonie | bestanden | eine Zeile, Lint mit `--base HEAD`, `evals_due: false`, Commit; ausdrücklich kein Eval, kein Report, kein Review |
| 2 Token-Wechsel | bestanden | `evals_due: true` über den Pattern-Zweig; Agent zog die Assertion in `evals.json` nach, sonst nichts |
| 3 Gate-Wort | bestanden | Befund gemeldet, nicht repariert; fuhr den Lint mit und ohne `--base`, weil der Befund im Diff-Modus ein Altbefund ist |
| 4 fehlender Anti-Zeremonie-Eval | bestanden | Befund als Altbefund gemeldet, `unchecked` als „nicht bestanden" wiedergegeben |
| 5 Routing ohne Skill-Namen | bestanden | wählte `skill-forge` über die Routing-Matrix statt `skill-creator`; Evals vor der SKILL.md; Report mit Pflichtsektion |

Fünf von fünf, **ein Lauf je Eval** — eine Stichprobe, kein Beweis (known-limits,
„Stichprobe"). Der Aufbau ist stärker als der Harness: Der Hinweis auf
`.claude/skills/` ersetzt das automatische Laden, und ein Subagent sieht daneben die
Skills des Nutzerprofils, darunter `skill-creator`. Eval 5 hat trotzdem `skill-forge`
gewählt, mit der Routing-Matrix der Fixture als Begründung.

Drei Funde aus den Läufen, in der Folgerunde behoben:

- **„Prüfe die Skill X" mit `--base HEAD` ist grün, weil jeder Befund ein Altbefund
  ist.** Der Agent in Eval 3 erkannte das und fuhr beide Aufrufe. Die SKILL.md sagt jetzt:
  Prüfen ohne Änderung läuft ohne `--base`.
- **Wo eine neue Skill liegt, stand nirgends.** Eval 5 legte `reminder` unter
  `.claude/skills/` an, weil der Workspace keinen `skills/`-Ordner hatte. Die SKILL.md
  nennt jetzt `skills/<name>/`.
- **Der Lint las Frontmatter per Regex und meldete YAML-ungültige Descriptions grün.**
  Der Agent in Eval 5 fand es an seiner eigenen Skill; nachgemessen mit PyYAML über alle
  21 Skills: `impl-plan` und `debug-ledger` luden nicht (unquotiertes „: " in der
  description). Beide Descriptions stehen jetzt in Anführungszeichen, Wortlaut
  unverändert; `frontmatter` prüft die vier Fälle, in denen ein unquotierter Skalar
  nicht lädt, und `split_frontmatter` liefert Werte ohne Anführungszeichen. Ob der
  Skill-Loader von Claude Code strikt parst, ist weiterhin nicht gemessen — falls ja,
  war `impl-plan` seit seinem Merge nicht ladbar.

### Zweiter Lauf nach der Folgerunde (2026-09-11)

Derselbe Aufbau, frische Workspaces, die Skill aus der Folgerunde: wieder fünf von
fünf. Die drei Änderungen sind im Verhalten sichtbar — die Prüf-Agenten (Eval 3 und 4)
fuhren den Lint ohne `--base` und nannten dafür den Satz aus der SKILL.md; der
Routing-Agent legte `reminder` unter `skills/` an, mit YAML-gültiger Description
(PyYAML gegengeprüft) und vier `evalkit`-ladbaren Evals. Eval 1 und 2 verliefen wie im
ersten Lauf: eine Zeile plus Commit, beziehungsweise `evals_due: true` plus nachgezogene
Assertion, sonst nichts.

## Was nicht gemessen wurde

**Die fünf Evals sind zweimal gefahren, außerhalb des Harness.** Zwei Läufe je Eval,
mit einem Aufbau, der das Laden der Skill stärker nahelegt als der Harness. Ob ein
Agent den Lint im Diff-Modus *aufruft* statt „schnell alles aufzuräumen", ist an zwei
Stichproben positiv beantwortet — zehn von zehn, und trotzdem kein Beweis.

**Der Trigger ist an einer Stichprobe gemessen — und er war die Diagnose.** Ein Lauf
von „bau mir eine Skill" landete bei `skill-forge`, mit dem Hinweis auf
`.claude/skills/` im Prompt. Ob er ohne diesen Hinweis und in fünf Wiederholungen dort
landet, entscheidet der Harness; das Trigger-Eval-Set in `references/evals.md` wartet
auf einen Harness außerhalb eines Root-Containers.

**Das Register wurde zweimal gemessen, von zwei Seiten.** Die 79 Paare stammen aus dem
Bau; beide Reviewer haben sie unabhängig nachgezählt und dabei die falschen Summen je
Regel gefunden (20/15 statt 19/14). Das Register selbst hielt, die Prosa darüber nicht.

**Die Heuristiken haben bekannte Löcher.** Zwölf Prozessverben, drei Trigger-Formen,
Negation im Absatz — `references/checklist.md` und `known-limits` nennen die Fälle,
die durchgehen. Der Reviewer fängt sie, wenn er sie sucht.

**Die Baseline ohne Skill fehlt.** Die Diskriminator-Frage wird je Eval beantwortet,
nicht gemessen. `--without-skill` bleibt eine eigene Spec.

## Offen für die nächste Runde

- Die fünf Evals außerhalb eines Root-Containers fahren, zuerst
  `anti-ceremony-one-sentence-change-lints-only` und `routing-new-skill-gets-house-evals`.
- Das Register schrumpfen lassen, eine Skill pro Anlass: Beim nächsten Fix an einer
  registrierten Skill die `report-section` nachziehen und den Eintrag streichen.
- `--without-skill` als eigene Spec.
- Die Prüfung `docs/assessment-writing-skills-writing-plans.md` von ihrem Branch nach
  main holen; `checklist.md` zitiert sie.
