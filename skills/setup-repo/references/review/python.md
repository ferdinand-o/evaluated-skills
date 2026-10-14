# Prüfpunkte — Python

Konformität, nicht Fehlersuche: Der Ziel-Reviewer prüft je Punkt nur den Diff des Ziels.
`plan_repo.py` setzt die Zeilen unter „Prüfpunkte" wörtlich in `.claude/agents/reviewer.md`
ein, wenn das Repo Python enthält. Format je Zeile: `- **<id>** — <Prüfpunkt> Quelle: <Quelle>`.

## Prüfpunkte

- **py-test-for-public** — Eine neue öffentliche Funktion, Methode oder Klasse (Name ohne führenden Unterstrich) wird von mindestens einem Test im Diff oder im Repo aufgerufen. Quelle: Spec 22, Abschnitt „Review" (Beispiel „neue öffentliche Funktion hat einen Test").
- **py-dependency-in-manifest** — Ein neuer Import eines Drittpakets steht als Abhängigkeit im Manifest des Repos (`pyproject.toml` unter `[project] dependencies` oder einer optionalen Gruppe, sonst `requirements*.txt`). Quelle: PEP 621, Abschnitt „dependencies/optional-dependencies", https://peps.python.org/pep-0621/
- **py-naming** — Neue Namen folgen PEP 8: Funktionen und Variablen `snake_case`, Klassen `CapWords`, Konstanten `UPPER_CASE`. Quelle: PEP 8, Abschnitt „Naming Conventions", https://peps.python.org/pep-0008/
- **py-no-bare-except** — Kein neues `except:` ohne Ausnahmetyp. Quelle: PEP 8, Abschnitt „Programming Recommendations", https://peps.python.org/pep-0008/
