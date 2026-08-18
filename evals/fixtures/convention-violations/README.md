# Fixture: convention-violations

Ein Model mit `userEmail = Column(String(50))` — camelCase-Spaltenname und
`varchar(50)` statt `text` im selben Feld. Prüft, ob `lint_schema.py` beide
Verstöße findet, ohne dass das aufrufende Modell selbst danach suchen muss.
