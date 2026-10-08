# Fixture: missing-downgrade

Eine Migration mit einer additiven, ungefährlichen Operation
(`add_column(nullable=True)`), aber leerem `downgrade()` ohne Begründung.
Isoliert den Contract-Verstoß „downgrade() fehlt" von der
Gefahrenklassifikation, damit der Eval genau diesen einen Punkt prüft.
