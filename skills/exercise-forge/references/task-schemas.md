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
  "status": "verified" | "suspicious" | "unverified",
  "method": "blind_solve_mc" | "blind_solve_open" | "blind_solve_coding" | "blind_check_flashcard" | "not_run",
  "detail": "ein bis zwei Sätze, mit Zitat der Blind-Begründung bei suspicious",
  "checked_at": "ISO-Datum oder null"
}
```

`status: verified` entsteht **ausschließlich** durch `verify_blind.py` (bzw.
`run_coding.py` für Coding). Eine neu erzeugte Aufgabe trägt
`{"status": "unverified", "method": "not_run", "detail": "Blind-Gate noch nicht gelaufen", "checked_at": null}`.
