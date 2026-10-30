# Fixture: plan-fanout

Ein work-plan-Plan unter `docs/plans/fanout.md` mit fünf Tasks: Task 1 liefert
`parse_order`, Task 3 (Import) und Task 4 (Export) verwenden es, Task 2 ist
unabhängig, Task 5 heißt `Verifikation`. Prüft, dass `plan_to_tasks.py generate`
Task 1 als Vorleistung mit zwei Abnehmern opus gibt (M1) und einen Prüfpunkt vor
dem ersten Abnehmer setzt (C1) — Spec 27, Eval 2. `.gitignore` und Plan stehen als
`touch`-Einträge in `fixture.json`.
