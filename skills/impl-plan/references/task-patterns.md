# Task-Muster — zwei Formen, eine Zuschnittsregel, ein Vokabular

Ein Plan dieser Sammlung schreibt meistens keine Funktionen, sondern `SKILL.md`,
References, `evals.json`, Fixtures. Der TDD-Fünfschritt aus `writing-plans` passt auf
Code; für Doktrin-Dateien gab es bisher kein Muster, und jeder Plan improvisierte
eines. Hier stehen beide.

## Code-Task

Für alles, was ein Test prüfen kann: Skripte, Parser, Assertions.

````markdown
### Task 3: Eval-IDs aus der Spec-Tabelle lesen

**Files:**
- Modify: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: `fn:parse_plan(text)`
- Produces: `fn:spec_eval_ids(spec_text)`

- [ ] **Step 1: Test schreiben** — eine Spec mit `id`-Spalte liefert die IDs; eine Spec
      ohne Tabelle liefert `None`.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_subagent_dev_plan_to_tasks.py -k spec_eval_ids`.
- [ ] **Step 3: Implementieren** — Header-Zeile mit Spalte `id` finden, Backtick-Werte
      der Spalte sammeln, Trennzeile überspringen.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**
````

Fünf Steps, weil der Zyklus fünf Zustände hat — nicht, weil jeder Step fünf Minuten
dauern soll. Ein Step ist eine Handlung mit einem beobachtbaren Ergebnis.

## Doktrin-Task

Für `SKILL.md`, References, Templates, Fixtures, `evals.json`. Es gibt keinen roten
Test, den man erst sehen könnte — es gibt eine Datei, eine mechanische Prüfung darauf,
und einen Commit.

````markdown
### Task 5: SKILL.md

**Files:**
- Create: `skills/explain/SKILL.md`

**Interfaces:**
- Consumes: `token:Unverified:`, `token:Source:`
- Produces: `token:Next:`

- [ ] **Step 1: Frontmatter** — `name`, Description mit Triggern und Abgrenzung gegen die
      zwei stärksten Konkurrenten.
- [ ] **Step 2: Contract und Anti-Rationalisierung** — die Regeln aus der Spec, keine
      Zeile, die eine andere nur umformuliert.
- [ ] **Step 3: Prüfen** — `wc -l` unter 150, Sprachprüfung nach Spec 00 §4 (G1 sagt
      „verlangt", nie „blockiert"), Schema-Test der Evals grün.
- [ ] **Step 4: Commit.**
````

Die mechanische Prüfung in Step 3 ist Pflicht, auch wenn sie klein ist: Zeilenzahl,
`load_evals`, `lint`. Ein Doktrin-Task ohne mechanischen Step ist reine
Selbstauskunft — und die Pitfalls-Datei hält fest, was das gekostet hat.

## Evals zuerst bei Tier 0

Hat eine Skill kein Skript, gibt es keinen Code, den Unit-Tests prüfen könnten. Dann
sind die Evals das **einzige** Messinstrument — die ausführbare Definition von
„fertig", nicht ihre Nachkontrolle. Der Eval-Task steht deshalb vor der `SKILL.md`,
nicht danach. Spec 15 (`explain`) hat das so gebaut; die Reihenfolge ist seither Regel,
nicht Geschmack. Ein Plan für eine Tier-0-Skill, dessen `### Task N: Evals` hinter dem
`SKILL.md`-Task steht, ist ein Befund im Reviewer-Prompt.

## Zuschnittsregel

Aus `writing-plans`, übersetzt und beibehalten, weil sie richtig ist:

> Eine Task ist die kleinste Einheit, die ihren eigenen Prüfzyklus trägt und einem
> frischen Reviewer ein eigenes Gate wert ist. Setup, Konfiguration, Gerüst und
> Dokumentation gehören in die Task, deren Ergebnis sie braucht. **Teile nur dort, wo
> ein Reviewer die eine Task ablehnen und die Nachbar-Task annehmen könnte.** Jede
> Task endet mit etwas, das sich unabhängig prüfen lässt.

Für Doktrin-Tasks heißt das meist: eine Datei, eine Task. Zwei References in einer
Task sind nur dann richtig, wenn keine ohne die andere prüfbar ist.

## Die vier Pflicht-Tasks

Jeder Plan dieser Sammlung trägt sie, mit **kanonischen Titeln** — wörtlich, weil
Evals und Reviewer die Pflichtinhalte daran erkennen:

| Titel | Inhalt |
| --- | --- |
| `### Task N: Evals` | `evals/<skill>/evals.json`, Fixtures, Schema-Test |
| `### Task N: Nachbarn` | Routing-Matrix an beiden Orten, Abgrenzungssätze der Nachbar-Skills |
| `### Task N: known-limits` | Abschnitt in `docs/known-limits.md`: was ungemessen bleibt |
| `### Task N: Report` | `docs/superpowers/reports/<skill>-report.md` mit der Sektion „Was nicht gemessen wurde" |

Im Anti-Zeremonie-Fall — eine Änderung an ein, zwei Dateien einer bestehenden Skill —
werden die vier zu **einem** Sammel-Task `### Task N: Pflicht` mit je einer Zeile pro
Punkt. Nicht null: Auch eine Satzänderung kann einen Nachbarn betreffen, und wenn nicht,
kostet die Zeile „Nachbarn: keine" nichts.

## Platzhalter

Aus `writing-plans`, ergänzt um das, was `plan_to_tasks.py lint` mechanisch erkennt.
Diese Wendungen sind **Planfehler**, keine Notizen:

- `TBD`, `TODO`, `FIXME`, `XXX`, `???`, `<platzhalter>`, `<placeholder>` — der Lint
  meldet sie mit Zeilennummer.
- „später ausfüllen", „Details folgen", „ähnlich wie Task N" — der Leser einer Task
  sieht nur seine eigene; Wiederholung ist billiger als ein Verweis ins Leere.
- „Fehlerbehandlung ergänzen", „Randfälle abdecken", „Tests dazu schreiben" ohne zu
  sagen, welche — ein Step beschreibt eine Handlung, nicht einen Wunsch.
- Ein Symbol in `Consumes:`, das keine Task in `Produces:` führt.

Wo ein Template eine Auslassung braucht, steht `…` — kein Platzhalterwort.

## Interface-Vokabular

Nackte Bezeichner bleiben gültig. Drei Präfixe kommen dazu; jedes andere Präfix und
jeder Backtick-Ausdruck, der kein Bezeichner ist, macht die Task für das Gate
**unbekannt** — fail-closed, also serialisiert.

| Form | Bedeutet | Gate (`subagent-dev`) | `verify` |
| --- | --- | --- | --- |
| `` `fn:parse(line)` `` | Aufrufbares, Name + Arity | Symbol-Überlappung über den Namen | per `ast`: Name und Parameterzahl |
| `` `token:Next:` `` | wörtlicher Ausgabe-Token einer Doktrin | Symbol-Überlappung über den Namen | Textsuche in den Allowlist-Dateien |
| `` `file:docs/x.md` `` | Lese-Abhängigkeit auf eine Datei, die ein anderer Task schreibt | Pfad-Überlappung gegen dessen `Files:` | nicht geprüft — gehört nie in `Produces:` |

Zwei Regeln dazu: Ein `token:` in `Produces:` heißt, die Datei dieser Task enthält den
Token wörtlich — sonst meldet `verify` `missing`. Und `file:` steht nur in
`Consumes:`; eine erzeugte Datei gehört in `Files:`, der Lint meldet sie sonst.
