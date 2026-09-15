<!-- skill: skill-forge | schema: 1 | generated: von Hand nach skills/skill-forge/assets/skill-template/report.md — beim Kopieren skill auf die neue Skill setzen -->
# … — Abschlussbericht

Gebaut nach `specs/Spec NN – ….md` und `docs/superpowers/plans/<datum>-….md`. Tier …,
gebaut am … (sequenziell im Hauptkontext | mit `subagent-dev` in … Paketen).

## Was entstanden ist

```
skills/…/SKILL.md                … Zeilen (Grenze 150)
skills/…/references/…            …
skills/…/scripts/….py            Tier …
evals/…/evals.json               … Evals, davon … contract
tests/test_….py                  … Tests
```

Nachgezogen: Routing-Matrix in Spec 00 §5 und `README.md`, Abgrenzungssätze der
Nachbarn …, Abschnitt in `docs/known-limits.md`.

## Die Entscheidungen, die den Bau geprägt haben

**…** — je Entscheidung: was die Spec offenließ, was entschieden wurde, warum, und was
es kostet. Drei sind üblich; eine reicht, wenn es nur eine gab.

## Was gemessen wurde

- **… Tests grün**, davon … neu; der Fehlschlag …, falls einer, mit Ursache und ob er
  vorbestehend ist (per `git stash` gegengeprüft).
- **Lint:** `lint_skill.py skills/…` — … Regeln `pass`, … `unchecked` mit Grund, …
  `hint`; `evals_due` gegen `--base …`.
- **Evals:** … gefahren | geschrieben und schema-validiert, nicht gefahren.
- **Baseline:** … Evals mit `--without-skill` gefahren, … davon grün ohne Skill (je
  Eval: umgebaut an …, oder gestrichen) | nicht gefahren, siehe unten.
- Jede Zahl hier ist nachgemessen, nicht aus dem Plan abgeschrieben.

## Was nicht gemessen wurde

**Die Evals** — gefahren oder nicht, und wenn nicht, warum (`docs/known-limits.md`,
„Betrieb"). Was vorliegt, ist dann eine schema-valide Sammlung, kein Nachweis.

**Der Trigger** — ob „…" bei dieser Skill landet, entscheidet der Harness pro Lauf.
Der Routing-Eval misst es, wenn er fährt; bis dahin ist die Description eine Annahme.

**Die Baseline** — ohne `--without-skill`-Lauf bleibt je Eval beantwortet, nicht
gemessen, ob das Basismodell dasselbe könnte; ein Eval, der ohne Skill genauso grün
wäre, fiele nicht auf.

**…** — jede weitere Lücke mit dem konkreten Fall, in dem sie beißt. Diese Sektion
hat nie null Einträge: Eine Skill, bei der nichts ungemessen blieb, hat nicht
hingesehen.

## Offen für die nächste Runde

- …
