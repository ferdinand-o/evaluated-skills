# Aufgabenschema: die vier Typen

Jede Aufgabe ist ein Objekt im Aufgaben-JSON (`~/.skills/verified-research/research/<thema>.exercises.json`,
Schema-Version 1). Gemeinsame Pflichtfelder für **jede** Aufgabe, unabhängig
vom Typ:

| Feld | Bedeutung |
| --- | --- |
| `id` | stabil, z. B. `mc-01`, `open-03`, `code-01`, `card-12` |
| `type` | `multiple_choice` \| `open_question` \| `coding` \| `flashcard` |
| `learning_objective` | ein Satz: was der Lernende danach kann |
| `bloom_level` | `erinnern` \| `verstehen` \| `anwenden` \| `analysieren` — bestimmt den Typ (siehe unten) |
| `difficulty` | Vektor nach `difficulty.md`: `{"steps", "prerequisites", "transfer", "label"}` |
| `stem` | der Aufgabenstamm — das, was der Lernende zuerst sieht |
| `verification` | wird vom Blind-Gate gefüllt, nie von Hand auf `verified` gesetzt |

**Bloom-Ebene bestimmt den Typ, nicht Geschmack:** Erinnern → Flashcard,
Verstehen → Multiple Choice, Anwenden/Analysieren → offene Frage oder Coding
(Coding, wenn Code das natürliche Medium der Antwort ist).

## Multiple Choice

```json
"options": [
  {"text": "…", "correct": true},
  {"text": "…", "correct": false},
  {"text": "…", "correct": false},
  {"text": "…", "correct": false}
]
```

- Genau eine Option trägt `"correct": true`.
- 3–5 Optionen. Jeder Distraktor folgt `distractors.md` — kein „alle Antworten
  richtig", kein triviales Ausscheiden per Textlänge oder Grammatik.
- Der Blind-Löser sieht `stem` und `options` (Text, nicht `correct`) und muss
  begründet wählen. Eine falsche Begründung ist ein Distraktor-Erfolg; eine
  *valide* Begründung für eine falsche Option ist ein kaputter Distraktor.

## Offene Frage

```json
"model_solution": "Musterantwort inkl. Lösungsweg",
"criteria": ["Kriterium 1, beobachtbar formuliert", "Kriterium 2", "…"]
```

- `criteria` sind beobachtbare Muss-Aussagen über eine gute Antwort, keine
  Stimmungsurteile — dieselbe Härte wie bei Eval-Assertions. „Nennt den
  Trade-off zwischen X und Y" statt „zeigt Verständnis".
- Der Blind-Löser sieht nur `stem`, antwortet frei, eine zweite Bewertung prüft
  die Antwort gegen `criteria`. Erfüllt eine plausible, fachlich vertretbare
  Antwort ein Kriterium nicht, ist das Kriterium zu eng — nicht die Antwort
  falsch.

## Coding

```json
"model_solution": "def foo(x):\n    return x * 2\n",
"test_suite": "from solution import foo\n\n\ndef test_foo():\n    assert foo(2) == 4\n"
```

- Konvention: `model_solution` ist der Inhalt von `solution.py`. `test_suite`
  importiert ausschließlich `from solution import …` — nichts sonst, damit
  `run_coding.py` beide Lösungen (Muster und Blind) unter demselben Testlauf
  austauschen kann, ohne den Testcode zu ändern.
- `test_suite` darf dem Blind-Löser gezeigt werden (wie einem Lernenden, der
  gegen gegebene Tests entwickelt) — nur `model_solution` bleibt verdeckt.
- Musterlösung muss die eigene Testsuite bestehen; tut sie das nicht, ist die
  Aufgabe fehlerhaft, nicht der Blind-Löser.

## Flashcard

```json
"front": "Frage/Reizwort",
"back": "Antwort — eine Information"
```

- **Eine Information pro Karte.** Zwei Fakten gehören auf zwei Karten, auch
  wenn sie zusammengehören. Ein „und" oder eine Aufzählung auf der Rückseite
  ist ein Hinweis, dass die Karte zu teilen ist.
- `back` beantwortet `front` exakt — keine Zusatzinformation, die `front`
  nicht verlangt hat.
- Blind-Check: Der Blind-Löser sieht nur `front` und antwortet frei; driftet
  die Antwort inhaltlich von `back` ab, ist `front` mehrdeutig formuliert.

## `verification`-Objekt

```json
"verification": {
  "method": "blind_solve_mc" | "blind_solve_open" | "blind_solve_coding" | "blind_check_flashcard" | "not_run",
  "detail": "ein bis zwei Sätze, mit Zitat der Blind-Begründung bei einem Konflikt",
  "checked_at": "ISO-Datum oder null",
  "protocol": { /* typspezifisch, siehe unten, oder null */ }
}
```

**Es gibt kein `status`-Feld.** Das war ein bewusster Schritt (Fix-Runde 5),
kein Versehen: Ein gespeicherter Status wäre redundant zu dem, was sich aus
`protocol` ohnehin ableiten lässt — und ein redundantes, frei editierbares
Feld war genau die Fehlerquelle. Zwei vorherige Fix-Runden versuchten
schwächere Lösungen und scheiterten daran, gemessen an echten Agentenläufen:

1. **G1 — Doktrin** ("schreib `status` nie selbst"): reichte nicht. Eine
   Session setzte `status: "verified"` in der Aufgaben-JSON, nachdem sie einen
   vom Gate gefundenen Konflikt bereits gemeldet hatte.
2. **G2 — nur beim Rendern ableiten** (`export.py` liest `status` nicht mehr,
   berechnet ihn aber aus `protocol`): schloss die Lücke fürs *gerenderte*
   Übungsblatt, ließ aber den Widerspruch in der **Aufgaben-JSON selbst**
   stehen — einem Artefakt, das auch andere Werkzeuge lesen (`learning-coach`,
   Zyklus 14).

**Konsequenz:** Wer einen Status braucht — egal ob `export.py`, `verify_blind.py`
selbst (für seinen `--all`-Filter) oder ein fremder Konsument wie
`learning-coach` — leitet ihn nach der folgenden Regel ab, statt ihn zu lesen.
Das ist die Regel, unabhängig vom Code dieser Skill:

**Ableitungsregel:**

1. Ist `method` gleich `"not_run"` (oder fehlt): Status ist `unverified`. Das
   ist der Normalfall einer frisch erzeugten, noch nicht geprüften Aufgabe.
2. Ist `method` keiner der vier echten Werte oben (weder `not_run` noch eine
   der vier Blind-Gate-Methoden): Status ist `unverified` — kein bekannter
   Prüfnachweis.
3. Fehlt `checked_at`, oder ist `protocol` kein Objekt: Status ist
   `unverified` — `method` sieht nach einem echten Lauf aus, aber der
   Nachweis ist unvollständig.
4. Sonst, je nach Typ, aus `protocol` (siehe Tabelle) — bei
   `multiple_choice`/`open_question` **nachgerechnet gegen die aktuellen
   Aufgabendaten** (Optionen/Kriterien), nicht nur gegen das im Protokoll
   behauptete Ergebnis:

| Typ | `protocol`-Feld | Ableitung |
| --- | --- | --- |
| `multiple_choice` | `{"chosen_index": int}` | `verified`, wenn `options[chosen_index].correct == true` ist; sonst `suspicious` |
| `open_question` | `{"criteria_met": [bool, …], "answer_is_plausible": bool}` | `unverified`, wenn `answer_is_plausible` falsch ist oder `criteria_met` nicht zur Länge von `criteria` passt; sonst `verified`, wenn alle `criteria_met` wahr sind, sonst `suspicious` |
| `flashcard` | `{"matches": bool}` | `verified`, wenn `matches` wahr ist; sonst `suspicious` |
| `coding` | `{"model_passed": bool, "blind_passed": bool}` | `unverified`, wenn `model_passed` fehlt oder falsch ist; sonst `verified`, wenn `blind_passed` wahr ist, sonst `suspicious` — **`blind_passed` fehlend ist `unverified`, nicht `suspicious`** (keine Blind-Lösung übergeben ≠ Blind-Lösung durchgefallen) |

Referenzimplementierung: `export.derive_status_from_protocol(exercise)` bzw.
identisch dupliziert `verify_blind.derive_status_from_protocol(exercise)`
(Rulings A3 — Skripte bleiben eigenständig, deshalb zweimal derselbe
Funktion statt eines Imports). Eine neu erzeugte Aufgabe trägt
`{"method": "not_run", "detail": "Blind-Gate noch nicht gelaufen", "checked_at": null, "protocol": null}`.

**Für `learning-coach` (Zyklus 14):** Diese Skill liest dieselben
Aufgaben-JSONs (`~/.skills/verified-research/research/<thema>.exercises.json`)
und meldet unter anderem „keine verifizierten Aufgaben gefunden". Sie muss
den Status ebenfalls nach obiger Regel ableiten, nicht aus einem `status`-Feld
lesen — das Feld existiert nicht (mehr). Eine Prüfung auf `exercise["verification"]["status"] == "verified"`
liefert einen `KeyError`, keine falsche Antwort — das ist absichtlich laut,
nicht still (siehe Rulings A4).
