# Fixture: plan-hidden-overlap

Ein Plan mit zwei Tasks, die beide `config/shared.yaml` anfassen — die
Überlappung, die nur beim Lesen der `Files:`-Blöcke auffällt, nicht am
Task-Titel. Prüft, dass `plan_to_tasks.py` die Parallelisierung verweigert
(Spec 09, Eval 1).
