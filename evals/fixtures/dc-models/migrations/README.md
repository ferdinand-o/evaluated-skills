# Migrationen

Fortlaufend nummeriert, eine Datei je Schritt: `NNNN_<name>.py`, zum Beispiel `0001_initial.py`.
Jede Datei hat `up(db)` und `down(db)`; `db` bietet `execute(sql)`. Kein Framework.
