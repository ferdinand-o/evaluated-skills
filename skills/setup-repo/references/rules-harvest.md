# Regel-Ernte — Kandidat, Quelle, Klasse

`harvest_rules.py` sammelt Kandidaten mit Quelle; die Klasse trägt Claude ein. Was ein
konfiguriertes Werkzeug schon prüft, wird nie eine Regelzeile. Was fehlt, steht als
„ungeprüft" da, nie erfunden.

## Quellen

| Quelle | Kandidaten | `checked_by` |
| --- | --- | --- |
| `pyproject.toml` `[tool.ruff]`, `ruff.toml`, `.ruff.toml` | `line-length`, `target-version`, ausgewählte Regelsätze (`select`) | `ruff` |
| `pyproject.toml` `[tool.black]` | `line-length` | `black` |
| `pyproject.toml` `[tool.mypy]`, `mypy.ini` | `strict` | `mypy` |
| `pyproject.toml` `[tool.pytest.ini_options]` | `testpaths` | `pytest` |
| `setup.cfg` / `.flake8` `[flake8]` | `max-line-length` | `flake8` |
| `.editorconfig` | `indent_style`, `indent_size`, `max_line_length` | `editorconfig` |
| `.prettierrc*` | `printWidth`, `semi`, `singleQuote` | `prettier` |
| `tsconfig.json` | `strict` | `tsc` |
| ESLint-Konfiguration | dass sie gilt, mit Dateiname | `eslint` |
| `CONTRIBUTING*` | Aufzählungspunkte, höchstens 20 | — |
| Commit-Betreffs der letzten 50 Commits | ein gemeinsames Präfixformat, wenn mindestens 60 % ihm folgen | — |

IDs heißen `c1`, `c2`, … in der Reihenfolge der Tabelle. `checked_by` ist ein Beleg, keine
Klasse: Ob das Werkzeug im Projekt läuft, entscheidet Claude.

## Klassen

| Klasse | Wann | Folge im Plan |
| --- | --- | --- |
| `ableitbar` | Claude sieht es beim Lesen des Codes (Sprache, Ordnerstruktur, Testframework) | fällt weg, nur im Bericht |
| `werkzeug` | ein konfigurierter Linter, Formatter oder Typprüfer prüft es schon | keine Regelzeile; im Bericht mit „Werkzeug" |
| `regel` | sonst | eine Zeile in der CLAUDE.md, oder mit `paths` eine eigene Datei unter `.claude/rules/` |
| `offen` | noch nicht klassifiziert | keine Regelzeile; die Ansicht nennt den Kandidaten als offen |

Eingetragen wird über

```bash
python plan_repo.py --classes '{"c1": "werkzeug", "c4": {"class": "regel", "paths": ["src/**/*.py"]}}'
```

Eine Regel bekommt `paths`, wenn sie nur einen Teil des Repos betrifft; dann lädt Claude
Code sie nur bei passenden Dateien, und sie zählt nicht ins Budget. Die erzeugte Datei
trägt Frontmatter mit `paths`, die Kopfzeile steht in der ersten Zeile danach, und die
Quelle steht in der Regel selbst.

## Budget

Immer geladene Zeilen: die CLAUDE.md samt Importen (`@AGENTS.md` zählt mit) plus alle
Rules ohne `paths`. Grenze 150. `plan_repo.py` zählt das Ergebnis nach apply und meldet
eine Überschreitung als Befund in der Ansicht; gekürzt wird durch Klassifikation
(`werkzeug`, `ableitbar`, `paths`), nicht durch Streichen von Belegen.
