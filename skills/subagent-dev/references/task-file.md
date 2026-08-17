# Task-Datei — Schema und Beispiel

Jede Task-Datei ist das, was ein delegierter Agent bekommt — **statt**
Konversationshistorie oder des ganzen Plans. `plan_to_tasks.py generate`
schreibt sie nach `.skills/cache/tasks/task-<id>-<slug>.md` (Ephemera, Spec 00
§1: jederzeit aus dem Plan neu erzeugbar, deshalb gitignored).

## Sechs Sektionen, immer in dieser Reihenfolge

1. **Ziel** — der Task-Titel aus dem Plan.
2. **Datei-Allowlist** — aus dem `Files:`-Block des Tasks (`Create`/`Modify`/
   `Test`/`Delete`, Zeilenbereiche abgeschnitten). Außerhalb dieser Dateien
   schreibt der Agent nicht; `verify` prüft das mechanisch.
3. **Interfaces** — `Consumes:`/`Produces:` wörtlich aus dem Plan. So kennt
   der Agent seine Nachbarn (Namen, Signaturen), ohne ihre Tasks zu sehen.
4. **Akzeptanzkriterien** — die `- [ ] **Step N: ...**`-Zeilen des Plans, als
   Liste.
5. **Global Constraints** — der komplette `## Global Constraints`-Abschnitt
   des Plans, wörtlich kopiert (ohne die eigene Überschrift, die die Task-Datei
   schon hat). Jeder Task-Vertrag schließt sie implizit ein.
6. **Nicht-Ziele** — alles außerhalb der Allowlist, plus die Titel der übrigen
   Tasks dieses Plans (damit ein Agent weiß, wessen Arbeit er nicht mit
   erledigen soll).

Danach folgt ein eingebetteter ` ```json `-Block — die maschinenlesbare
Fassung, die `verify` zurückliest (`task_id`, `plan`, `allowlist`, `produces`
mit `name`/`arity`). Menschen lesen die Prosa oben, `verify` liest nur den
JSON-Block; beide stammen aus demselben Render-Schritt und können nicht
auseinanderlaufen.

## Kopfzeile

Erste Zeile nach `docs/artifact-header.md`:

```
<!-- skill: subagent-dev | schema: 1 | generated: python skills/subagent-dev/scripts/plan_to_tasks.py generate <plan> -->
```

## Beispiel

Aus einem Mini-Plan mit `### Task 1: Parser`, `Files: Create src/parser.py,
Test tests/test_parser.py`, `Produces: parse(line: str) -> dict`:

```markdown
<!-- skill: subagent-dev | schema: 1 | generated: python skills/subagent-dev/scripts/plan_to_tasks.py generate docs/superpowers/plans/x.md -->

# Task 1: Parser

## Ziel

Parser

## Datei-Allowlist

Außerhalb dieser Dateien wird nicht geschrieben:

- `src/parser.py`
- `tests/test_parser.py`

## Interfaces

- Consumes: nichts Neues
- Produces:
  - `parse(line: str) -> dict`

## Akzeptanzkriterien

- Step 1: Write the failing test
- Step 2: Implement

## Global Constraints

- Alles auf Deutsch.

## Nicht-Ziele

Alles außerhalb der Datei-Allowlist oben. Andere Tasks dieses Plans gehören
nicht hierher:

- Task 2 – CLI

```json
{
  "task_id": 1,
  "plan": "docs/superpowers/plans/x.md",
  "allowlist": ["src/parser.py", "tests/test_parser.py"],
  "produces": [{"name": "parse", "arity": 1}]
}
```
```

## Grenzen

- Die Überlappungs- und Interface-Erkennung ist textbasiert (Backtick-Symbole
  in `Produces:`/`Consumes:`), keine semantische Analyse. Ein Symbol, das
  ohne Backticks oder in freier Prosa erwähnt wird, wird nicht erkannt — dann
  greift die konservative Regel nicht automatisch, und ein Mensch sollte die
  Files:/Interfaces:-Blöcke des Plans selbst noch einmal prüfen, bevor er dem
  Gate-Verdikt „parallel" folgt.
- Arity-Vergleich ist kein Typ-Check. `verify` prüft Namen und Parameteranzahl
  per `ast`, nie Typen — dafür müsste importiert werden, was diese Skill
  bewusst nie tut (Vorab-Entscheidung A3).
