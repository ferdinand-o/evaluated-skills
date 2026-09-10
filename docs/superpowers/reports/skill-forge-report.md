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
skills/skill-forge/scripts/lint_skill.py        743 Zeilen, Tier 1, dreizehn Regeln, Diff-Modus
evals/skill-forge/evals.json                    5 contract-Evals
evals/fixtures/sf-existing, sf-gate, sf-noanti, sf-spec
tests/test_skill_forge_lint.py                  29 Tests
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

- **Volle Suite: 1123 bestanden**, einer fremd rot
  (`test_rest_api_architect_gate.py::test_main_exit_zero_when_degraded_but_checklist_clean`,
  vorbestehend, erwartet ein fehlendes Spectral, das hier über `npx` erreichbar ist).
  42 neue Tests in drei Dateien, dazu 21 Skills zweimal parametrisiert im Repo-Test.
- **Erster Lint-Lauf über alle Skills (2026-09-10):** 20 Skills mit Befund, 79
  (Skill, Regel)-Paare im Register. Je Regel: `report-section` 20, `description` 18,
  `routing` 15, `anti-ceremony-eval` 11, `neighbors` 11, `evals-exist` 3,
  `asset-headers` 2, `gate-language` 1; `script-tier`, `frontmatter`, `skill-md-lines`,
  `fixture-git` 0. Gegen die Spec-Erwartung: `anti-ceremony-eval` 11 statt 14, weil die
  drei Skills ohne `evals.json` nur unter `evals-exist` zählen; `routing` 15 statt „7
  und 6", weil beide Matrizen gefordert sind; `neighbors` 11 statt 13.
- **Selbstbezug:** `lint_skill.py skills/skill-forge` — dreizehn Regeln `pass`, kein
  Register-Eintrag. Während des Baus war die Skill in `_UNDER_CONSTRUCTION` des
  Repo-Tests statt im Register; mit diesem Report ist das entfernt.
- **Jedes `lint.json`-Muster der Evals** greift an einer echten Skript-Ausgabe: Eval 3
  an `sf-gate`, Eval 4 an `sf-noanti`, keines an der sauberen `sf-existing`; Eval 1 und
  2 nachgespielt mit der Änderung aus dem Prompt und `--base HEAD`.
- **Das Template** besteht als Skill in einem Temp-Ordner die Regeln 1–5 und
  `anti-ceremony-eval`; seine `evals.json` lädt über `evalkit`.

## Was nicht gemessen wurde

**Kein einziger der fünf Evals ist gefahren** — derselbe Grund wie bei `explain` und
`impl-plan` (`docs/known-limits.md`, „Betrieb"). Die Muster greifen an echten
Skript-Ausgaben, aber ob ein Agent den Lint im Diff-Modus *aufruft* statt „schnell
alles aufzuräumen", ist genau die Frage von Eval 1, und sie ist unbeantwortet.

**Der Trigger ist ungemessen — und er war die Diagnose.** Ob „bau mir eine Skill" bei
`skill-forge` oder bei `skill-creator` landet, entscheidet der Harness pro Lauf. Die
Description-Doktrin ist eine Entscheidung mit je einem Beleg pro Seite; das
Trigger-Eval-Set in `references/evals.md` wartet auf einen Harness außerhalb eines
Root-Containers.

**Das Register wurde einmal gemessen, nicht zweimal.** Die 79 Paare stammen aus einem
Lauf des Skripts, das in derselben Sitzung entstand. Eine Regel mit systematischem
Falsch-Rot würde das Register still füllen; die Unterschiede zur Spec-Erwartung sind
erklärt, nicht unabhängig geprüft.

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
