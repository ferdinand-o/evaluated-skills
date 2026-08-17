# Implementierungsbericht: exercise-forge (Spec 13)

Branch `feat/exercise-forge`, Basis `specs/skill-foundation` (`0831fb7`).

## Was entstanden ist

`skills/exercise-forge/`:

- `SKILL.md` (83 Zeilen) — Workflow, Contract, Anti-Rationalisierungs-Tabelle,
  Abgrenzung zu `learning-coach` (Spec 14) und `visual-summary`.
- `references/task-schemas.md`, `distractors.md`, `difficulty.md` — reine
  Autoren-Doktrin (Tier 0, keine Skripte).
- `scripts/verify_blind.py` (Tier 1) — Blind-Gate für alle vier Aufgabentypen.
  MC und Coding sind einstufig (ein Blind-Löser-Aufruf, mechanischer Abgleich);
  offene Fragen und Flashcards sind zweistufig (Blind-Antwort, dann ein
  zweiter, unabhängiger Bewertungs-Aufruf gegen Kriterien bzw. Rückseite —
  demselben JSON-Verdict-Muster wie `evalkit.judge`, hier eigenständig
  dupliziert statt importiert).
- `scripts/run_coding.py` (Tier 2, pytest) — führt Musterlösung und
  Blind-Lösung nie per `import` aus, sondern als eigener
  `python -m pytest`-Subprozess in einem Wegwerf-Verzeichnis.
- `scripts/export.py` (Tier 1) — validiert das Schema, rendert
  `docs/exercises/<thema>.md` (Aufgaben/Lösungen getrennt, Verifikationsstatus
  sichtbar) und `docs/exercises/<thema>-anki.csv`.

`evals/exercise-forge/evals.json` — fünf Evals aus Spec 13 §Approach, mit
eigenen Fixtures unter `evals/fixtures/exercise-forge-*`. **Geschrieben, nicht
ausgeführt** — ein echter Lauf würde verschachtelte `claude -p`-Aufrufe
auslösen. `tests/test_exercise_forge_evals_schema.py` prüft nur, dass
`evalkit.schema.load_evals()` die Datei strukturell akzeptiert.

31 neue Unit-Tests über vier Testdateien (`test_exercise_forge_verify_blind.py`,
`test_exercise_forge_run_coding.py`, `test_exercise_forge_export.py`,
`test_exercise_forge_evals_schema.py`) plus eine Korrektur an
`tests/conftest.py` (siehe unten). Gesamte Suite: **208 von 208 Tests grün**
(`.venv/bin/pytest -q`).

## Eigene Design-Entscheidungen (nicht aus Spec 13 oder den Rulings ableitbar)

1. **Projekt-Override-Mechanismus für den Interface-Pfad.** `resolve_exercises_path()`
   schreibt nach `.skills/verified-research/research/<thema>.exercises.json`,
   *falls dieses Verzeichnis im Projekt bereits existiert* — sonst nach
   `~/.skills/verified-research/research/`. Das ist zugleich der Mechanismus,
   der die Evals aus dem echten `$HOME` heraushält: `evalkit` biegt `$HOME`
   nicht um (siehe `docs/known-limits.md`, Abschnitt Isolation), ein Eval ohne
   dieses Override hätte beim echten Ausführen die Home-Verzeichnisse des
   Aufrufers beschrieben. Jede Fixture bringt das Verzeichnis deshalb leer mit
   (`.skills/verified-research/research/.gitkeep`).
2. **Export-Zielpfad `docs/exercises/<thema>.md` bzw. `-anki.csv`.** Spec 13
   nennt nur das Format, nicht den Ablageort der gerenderten Artefakte. Nach
   Spec 00 §1 ist ein gerendertes Übungsblatt ein „Wissen"-Artefakt
   (menschenlesbar, überlebt die Skill) — analog zu `docs/reports/` bei
   `dev-report`.
3. **CSV-Kopfzeilen-Ausnahme.** Die Anki-CSV trägt bewusst keine
  Artefakt-Kopfzeile, weil Anki `#`-Zeilen als Import-Direktiven interpretiert.
  Nach dem Muster der bestehenden `handoff.md`-Ausnahme in
  `docs/artifact-header.md` dokumentiert und dort ergänzt.
4. **Blind-Gate-Verdikt-Vokabular.** Spec 13 nennt nur „geprüft/nicht
   verifiziert" implizit; ich habe einen dritten Zustand `suspicious`
   eingeführt (zwischen `verified` und `unverified`), weil ein
   Blind-Löser-Abweichung laut Spec „die Aufgabe ist verdächtig" heißt — nicht
   automatisch falsch, aber auch nicht „nicht gelaufen". `export.py` behandelt
   `suspicious` und `unverified` in der Markdown-Ausgabe gleich sichtbar
   (`[UNGEPRÜFT: <Grund>]`), in der Anki-CSV bleibt der Tag differenziert
   (`verified`/`suspicious`/`unverified`), damit der Nutzer verdächtige von
   ungeprüften Karten unterscheiden kann.
5. **Kein eigenes Distraktor-„valide Begründung"-Urteil in `verify_blind.py`.**
   Spec 13 verlangt, dass ein mit valider Begründung gewählter Distraktor als
   kaputt gilt. Ein zweites, unabhängiges Urteil darüber, ob die Begründung
   „valide" war, hätte einen dritten `claude -p`-Aufruf pro MC-Prüfung
   gekostet. Stattdessen markiert das Skript jede Distraktor-Wahl als
   `suspicious` und zitiert die Begründung im Klartext — der Mensch (oder die
   Claude-Session, die die Skill ausführt) entscheidet, ob die Begründung
   trägt. Das ist mechanisch günstiger und verletzt A4 nicht (kein Fall wird
   stillschweigend als „ok" behandelt).
6. **Anki-CSV exportiert alle vier Typen, nicht nur Flashcards und MC.** Spec
   13 nennt „Flashcards direkt; MC als Karte mit verdeckten Optionen" explizit,
   schließt offene Fragen/Coding aber nicht aus. Beide werden als
   Frage/Musterantwort-Karte exportiert — konsistent mit dem Anki-Anwendungsfall
   (Wiederholung), auch wenn sie kein Multiple-Choice-Format haben.
7. **Nebenbefund in `tests/conftest.py`.** `load_script()` registrierte das
   geladene Modul nicht in `sys.modules`, bevor `exec_module()` lief — unter
   Python 3.13 lässt das jedes `@dataclass` in einem so geladenen Skript mit
   `AttributeError: 'NoneType' object has no attribute '__dict__'` scheitern
   (`dataclasses._is_type` sucht `sys.modules[cls.__module__]`). Betraf nur
   `verify_blind.py` (bislang einziges Skript mit `@dataclass`), behoben mit
   einer Zeile (`sys.modules[spec.name] = module`), Fix committet zusammen mit
   der ersten `verify_blind.py`-Änderung.

## Bekannte Grenzen (analog zu `docs/known-limits.md`)

- **Kein drittes Urteil über „valide Begründung" bei MC-Distraktoren** (siehe
  Entscheidung 5 oben) — `suspicious` ist eine Warnung, kein Beweis, dass der
  Distraktor kaputt ist.
- **Die Evals sind ungelaufen.** Die fünf Fixtures wurden von Hand geprüft, wo
  mechanisch möglich (der Überspezifizierte-Tests-Fall in
  `exercise-forge-coding-overspecified` wurde direkt gegen `run_coding.py`
  verifiziert — siehe Commit-Historie), aber kein Eval wurde je über
  `run_evals.py` gegen einen echten Agenten gefahren. Ob die Judge-Claims in
  der Praxis trennscharf genug formuliert sind, ist unbewiesen.
- **`verify_blind.py` läuft den Blind-Löser in einem leeren Temp-Verzeichnis**,
  nicht in einer vollständig isolierten Prozessumgebung — dieselbe Grenze wie
  bei `evalkit.dispatch.run_agent` (siehe `docs/known-limits.md`, Abschnitt
  Isolation): `$HOME`/`os.environ` gehen unverändert an den Subprozess.
- **Flashcard-Atomarität („eine Information pro Karte") ist nicht mechanisch
  geprüft.** Das Blind-Gate prüft nur Eindeutigkeit der Frage (Antwort trifft
  Rückseite), nicht ob die Rückseite mehrere Fakten bündelt. Eine verlässliche
  Heuristik dafür schien mir zu fragil, um sie als Prüfung auszugeben (A4) —
  die Regel bleibt Autorendoktrin in `task-schemas.md`, nicht Code.
- **`export.py` validiert Struktur, nicht Inhalt.** Eine Aufgabe mit
  vollständigem, aber inhaltlich falschem Schema (z. B. `criteria: [""]`)
  besteht `validate_exercise()`.

## Abweichung vom Auftrag: `brief-common.md` fehlte

Der Auftrag verwies auf
`.../scratchpad/brief-common.md` als erste Pflichtlektüre („Fundament-Contract,
Arbeitsweise, Fehlerklassen, die hier real zugeschlagen haben"). Diese Datei
existierte im Scratchpad-Verzeichnis nicht — nur `rulings-final-four.md` war
vorhanden (geprüft per Dateisystemsuche, auch in Nachbar-Session-Verzeichnissen).
Ich habe das nicht als BLOCKED behandelt (der Auftrag nennt BLOCKED explizit
nur für den Fall, dass der Git-Checkout auf die Basis scheitert), sondern bin
mit den verfügbaren Quellen weitergearbeitet: `specs/Spec 00 – skill-foundation.md`
als Fundament-Contract, `docs/known-limits.md` und die Commit-Historie
(`0097449`, `a1417b3`, `e186556`, `a231b19`, `877cb25`) als die „real
zugeschlagenen Fehlerklassen", sowie die bereits gebaute `dev-report`-Skill als
Konventions-Referenz für Code-Stil, Test-Aufbau und SKILL.md-Form. Die fünf
genannten Commits betreffen den Eval-Harness (Judge wertet Assistant-Antwort
statt Rohtranscript aus, Glob-Pfade, Binärdateien im Judge-Aufruf,
schwankende Eval-Ergebnisse) — für `exercise-forge` direkt relevant war davon
nur die Judge-Lektion (Assertions gegen Artefakte, nicht gegen Prosa) und die
Erkenntnis, dass ein einzelnes Eval-Ergebnis eine Stichprobe ist — beides ist
in die Eval-Formulierungen oben eingeflossen (mechanische `file_exists`-Musts
neben jedem Judge-Claim, keine Übertreibung der Trennschärfe einzelner Läufe).

Eine Einschränkung bleibt: Der Glob-Pfad-Fix (`a1417b3`) existiert nur auf dem
Branch `feat/dev-report`, nicht auf `specs/skill-foundation` (meiner Basis) —
`git branch --contains a1417b3` zeigt ausschließlich `feat/dev-report`. Meine
Evals verzichten deshalb bewusst auf Glob-Pfade und pinnen jedes Thema im
Prompt explizit (`'python-basics'`, `'algorithms'`, `'sorting'`), damit der
Zieldateiname ohne Glob-Unterstützung deterministisch bleibt.

## Testergebnis

```
.venv/bin/pytest -q
208 passed
```

## Offene Sorgen

- `brief-common.md` fehlte (siehe oben) — falls die Datei eigentlich existieren
  sollte, sind mir möglicherweise Fehlerklassen oder Arbeitsweise-Vorgaben
  entgangen, die dort und nirgends sonst standen.
- Die fünf Evals sind nie gegen einen echten Agenten gelaufen; die
  Judge-Claims könnten in der Praxis zu großzügig oder zu streng ausfallen —
  das lässt sich erst mit einem echten `run_evals.py`-Lauf zeigen.
- Der Glob-Pfad-Fix aus dem Eval-Harness ist auf dieser Basis nicht vorhanden;
  sollte `feat/dev-report` vor `exercise-forge` gemergt werden, könnten die
  hartkodierten Themennamen in den Eval-Prompts unnötig restriktiv wirken
  (kein Schaden, nur ungenutztes Potenzial).
- `verify_blind.py`s Zwei-Aufruf-Protokoll (offene Fragen, Flashcards) kostet
  im Realbetrieb zwei `claude -p`-Aufrufe pro Aufgabe zusätzlich zum
  Haupt-Workflow — bei „20 Karten auf einmal" ggf. spürbare Latenz. Keine
  Parallelisierung eingebaut.
