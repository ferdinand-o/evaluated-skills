# Fixture: array-vs-relation

Eine bestehende `articles`-Tabelle. Der Prompt verlangt wörtlich eine
Array-Spalte `tag_ids integer[]`, um Artikeln Tags zuzuordnen — das
Antipattern aus `references/modeling.md`. Prüft, ob die Skill zur
Junction-Tabelle rät statt der Anfrage einfach zu folgen.
