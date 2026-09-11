# Spec-Brief — was ein Brainstorming für eine Skill dieser Sammlung vorher wissen muss

Eingabe für `brainstorming` (die eigene Profil-Skill), zusammen mit
`assets/spec-template.md`. Die Skizzen in §7 der Prüfung
`docs/assessment-writing-skills-writing-plans.md` waren die Eingabe für Spec 16 und 17
— die beiden Specs, die ohne Format-Nacharbeit durch `impl-plan` gingen. Dieses Brief
ist die Verallgemeinerung: erst lesen, dann fragen, dann schreiben.

## 1 · Vorher lesen — Orientieren heißt hier messen

Die Review-Funde der Faktenklasse (§4.1 der Prüfung `docs/assessment-brainstorming.md`)
waren Aussagen über Dateien, die niemand geöffnet hatte. Vor der ersten Frage:

| Was | Wo | Wofür |
| --- | --- | --- |
| Descriptions der zwei stärksten Konkurrenten | `skills/<name>/SKILL.md`, Frontmatter; fremde Skills im Nutzerprofil | Abgrenzung mit echten Trigger-Wörtern, nicht mit vermuteten |
| Routing-Matrix | `specs/Spec 00 – skill-foundation.md` §5, `README.md` | die Zeile, die diese Skill bekommt — und welche „nicht"-Einträge sie verschiebt |
| known-limits der Nachbarn | `docs/known-limits.md`, Abschnitt je Skill | was dort schon als Lücke steht, wird nicht als neu erfunden |
| Assertion-Typen | `evalkit/schema.py` (`ASSERTION_TYPES`) | jede Eval-Zeile bindet an einen davon; „vergleicht zwei Läufe" gibt es nicht |
| Eval-Workspace | `evalkit/workspace.py`, `prepare()` | dort liegen nur Skill-Ordner und Fixture — ein Eval, der ein Skript eines Nachbarn braucht, ist rot |
| Artefakt-Vertrag | `docs/artifact-header.md` | Kopfzeile, Bootstrap, Ausnahmen — was ein neues Artefakt tragen muss |
| Pitfalls | `docs/skill-building-pitfalls.md`, „Die eine Frage" | wo meldet etwas Erfolg, ohne geprüft zu haben |

Was daraus in die Spec kommt, kommt mit Quelle („gemessen: 3 von 17", „laut
`known-limits.md`, Abschnitt X"). Eine Zahl ohne Quelle ist beim Review ein Befund.

## 2 · Die Fragen, die das Brainstorming beantworten muss

Höchstens drei davon dem Nutzer stellen — die, bei denen eine andere Antwort einen
anderen Zuschnitt ergibt. Der Rest wird als `Annahme:` in die Spec geschrieben,
einzeln widersprechbar.

1. **Tier.** 0 (nur Doktrin), 1 (Stdlib), 2, 3 — und wer Tier 3 will, begründet es in
   den Constraints (Spec 00 §3). Eine Eiserne Regel, die an einem Skriptaufruf hängt,
   ist nie Tier 0.
2. **Gate-Grad je Gate.** Was „verlangt" die SKILL.md (G1), was „meldet" ein Skript
   (G2), und gibt es einen Grund für einen Hook (G3, nur bei irreversiblem Schaden)?
3. **Der Anti-Zeremonie-Fall.** Der triviale Anlass, bei dem die Skill klein bleiben
   muss — was löst er aus, was nicht. Er wird der erste Eval (`anti-ceremony-…`).
4. **Die zwei stärksten Konkurrenten.** Mit Namen, mit dem Anlass, bei dem sie
   gewinnen sollen. Beide bekommen beim Bau einen Rückverweis.
5. **Das Artefakt.** Welche Datei entsteht nur durch diese Skill, an welchem Ort, mit
   welcher Kopfzeile — daran binden die Evals; ohne eigenes Artefakt bleibt nur ein
   Token in der Ausgabe (Spec 15: `Next:`).
6. **Was ungemessen bleibt.** Harness (läuft nicht als root), Trigger (Stichprobe),
   Fremdumgebung (claude.ai ohne Shell) — ausdrücklich in Open questions.

## 3 · Danach

Die Spec nach `assets/spec-template.md` unter `specs/Spec NN – <name>.md`; dann
`python skills/subagent-dev/scripts/plan_to_tasks.py lint-spec "specs/Spec NN – <name>.md"`;
dann der Review nach `references/spec-reviewer-prompt.md` und der Vermerk in der
Kopfzeile. Erst danach `impl-plan`.
