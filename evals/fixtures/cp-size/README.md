# Fixture: cp-size

Erster Commit (Tag `reviewed`): Plan `docs/plans/fanout.md`, Code der Tasks 1 und
2, unter `.skills/cache/tasks/` die Task-Dateien 1 bis 3, `gate.json` (Prüfpunkte
vor Task 3 und final, keiner nach Task 3) und `review-state.json` mit
`last_reviewed: reviewed`. Zweiter Commit: Task 3 mit genau 430 neuen Zeilen in
`src/`. Nur `checkpoint status --after-task 3` zählt sie und meldet den Prüfpunkt
fällig (C5, ab 400 Zeilen) — Spec 27, Eval 5.
