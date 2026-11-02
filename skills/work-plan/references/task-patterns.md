# Task-Muster — drei Formen, eine Zuschnittsregel, ein Vokabular

Ein Plan von work-plan liest `subagent-dev` mit `plan_to_tasks.py`: Jeder Task ist ein
Block `### Task N: <Titel>` mit `**Files:**`, `**Interfaces:**` und Checkbox-Steps. Das
Format gehört subagent-dev; hier stehen die drei Formen, die ein Plan in einem fremden
Repo braucht.

## Code-Task

Für alles, was ein Test prüfen kann. Fünf Steps, weil der Zyklus fünf Zustände hat;
Rot und Grün laufen über test-first, das sie mit Befehl und Exit-Code belegt.

````markdown
### Task 1: CSV hat Kopfzeile

**Files:**
- Create: `src/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `fn:write_csv(rows, path)`

- [ ] **Step 1: Test schreiben** — eine Liste mit zwei Zeilen ergibt eine Datei, deren
      erste Zeile die Spaltennamen trägt.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_export.py -k header`.
- [ ] **Step 3: Implementieren** — `write_csv` mit `csv.writer`, Kopfzeile aus den
      Schlüsseln der ersten Zeile.
- [ ] **Step 4: Grün sehen**, dann den Verifikationsbefehl des Repos.
- [ ] **Step 5: Commit.**
````

Kommt der Plan aus einer feature-spec-Spec, zitiert der Task-Titel oder ein Step den Titel
des Akzeptanzkriteriums wörtlich — der Lint gleicht die Titel ab.

## Doku- oder Konfig-Task

Für README, Doku, Konfiguration ohne Verhaltensänderung. Drei Steps: Datei, mechanische
Prüfung, Commit.

````markdown
### Task 2: README-Abschnitt zum Export

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `fn:write_csv(rows, path)`
- Produces: `token:--csv`

- [ ] **Step 1: Schreiben** — Abschnitt „Export" mit Aufruf `report --csv out.csv`.
- [ ] **Step 2: Prüfen** — der Aufruf aus dem Abschnitt läuft im Repo.
- [ ] **Step 3: Commit.**
````

## Verifikations-Task

Immer der letzte Task, Titel wörtlich `Verifikation`.

- `**Files:**` nennt mit `Test:` die Datei, die den Befehl definiert: `CLAUDE.md` mit der
  Zeile `Verifikation:` (setup-repo), sonst `Makefile`, `package.json` oder
  `pyproject.toml`; ohne Befehl die CLAUDE.md, sonst den Plan selbst.
- `Consumes:` nennt alle `Produces:`-Symbole der Code-Tasks. So steht der Task für das
  Gate von subagent-dev hinter allen anderen.
- `Produces: (nichts Neues)`.

````markdown
### Task 3: Verifikation

**Files:**
- Test: `CLAUDE.md`

**Interfaces:**
- Consumes: `fn:write_csv(rows, path)`, `token:--csv`
- Produces: (nichts Neues)

- [ ] **Step 1: Verifikation** — `make check` laufen lassen; erwartet: grün. Ergebnis mit
      Befehl und Ausgabe in die Übergabe.
````

Fehlt ein Befehl, sagt der Step „Verifikation: keine — ungeprüft" und nennt, was der
Nutzer stattdessen prüfen kann.

## Modell und Abnehmer

Welches Modell eine Task baut und wo reviewt wird, entscheidet subagent-dev aus dem
ganzen Plan: Opus für Vorleistungen mit mindestens zwei Abnehmern, Risikopfade
(`auth`, `migration`, `.sql` …) und breite Tasks ab fünf Dateien, sonst Sonnet. Der Plan
kann das für eine Task festlegen — eine optionale Zeile direkt unter dem Task-Titel, vor
`**Files:**`:

```markdown
### Task 4: Preisberechnung

**Modell:** opus

**Files:**
```

Nur `opus` oder `sonnet`; anderes meldet der Lint, und die Regeln greifen. Gedacht für
das, was das Skript nicht sieht: Nebenläufigkeit, Algorithmen mit Sonderfällen.

**Abnehmer-Task beginnt mit einem Test gegen die Vorleistung.** Konsumiert eine Task ein
`Produces`-Symbol einer früheren, ist ihr erster Step ein Test, der dieses Symbol so
aufruft, wie die Task es braucht. subagent-dev prüft vorher nur Name und Arity; ob die
Vorleistung das Richtige tut, zeigt erst dieser Test.

## Zuschnittsregel

Aus impl-plan übernommen, weil sie richtig ist:

> Eine Task ist die kleinste Einheit, die ihren eigenen Prüfzyklus trägt und einem
> frischen Reviewer ein eigenes Gate wert ist. Setup, Konfiguration, Gerüst und
> Dokumentation gehören in die Task, deren Ergebnis sie braucht. **Teile nur dort, wo
> ein Reviewer die eine Task ablehnen und die Nachbar-Task annehmen könnte.**

## Interface-Vokabular

Nackte Bezeichner bleiben gültig. Drei Präfixe; jedes andere Präfix und jeder
Backtick-Ausdruck, der kein Bezeichner ist, macht die Task für das Gate unbekannt und
serialisiert den Bau.

| Form | Bedeutet | `verify` von subagent-dev |
| --- | --- | --- |
| `` `fn:parse(line)` `` | Aufrufbares, Name und Parameterzahl | per `ast` |
| `` `token:Next:` `` | wörtlicher Text, den die Datei der Task enthält | Textsuche |
| `` `file:docs/x.md` `` | Lese-Abhängigkeit auf eine Datei einer anderen Task | nicht geprüft, nie in `Produces:` |

Kein `…` in einem Symbol: Beispielnamen statt Auslassung.

## Platzhalter

`TBD`, `TODO`, `FIXME`, `XXX`, `???` meldet der Lint mit Zeilennummer. „Ähnlich wie
Task N", „Fehlerbehandlung ergänzen" oder „Tests dazu schreiben" ohne zu sagen welche
findet er nicht — das sind trotzdem Planfehler: Der Leser einer Task sieht nur seine eigene.
