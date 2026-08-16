# Fixture: review-context-caller

`src/user.py` ruft `add()` aus `src/calc.py` auf. Der deklarierte Commit
ändert nur den Body von `add()`, nicht die Signatur — die Python-`ast`-
Erkennung muss die Funktion trotzdem als berührt erkennen (Zeilenbereich-
Überlappung, nicht nur Signaturzeile), und `find_callers()` muss die
Signatur von `use_add()` als `caller_signature` auflösen.
