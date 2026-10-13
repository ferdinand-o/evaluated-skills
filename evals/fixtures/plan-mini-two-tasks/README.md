# Fixture: plan-mini-two-tasks

Ein Plan mit genau zwei völlig unabhängigen Tasks (kein gemeinsamer Datei-
oder Interface-Berührpunkt). Der Anti-Zeremonie-Fall (Spec 00 §2): zu wenige
Pakete, um den Dispatch-Overhead zu rechtfertigen, obwohl beide Tasks für
sich genommen parallel-sicher wären. Prüft, dass `plan_to_tasks.py`
`"no-delegate"` mit Begründung liefert statt `"parallel"` (Spec 09, Eval 2).
