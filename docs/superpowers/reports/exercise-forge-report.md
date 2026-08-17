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

`evals/exercise-forge/evals.json` — **sechs** Evals: die fünf aus Spec 13
§Approach plus der verpflichtende Anti-Zeremonie-Eval aus Spec 00 §2, mit
eigenen Fixtures unter `evals/fixtures/exercise-forge-*`. **Geschrieben, nicht
ausgeführt** — ein echter Lauf würde verschachtelte `claude -p`-Aufrufe
auslösen. `tests/test_exercise_forge_evals_schema.py` prüft nur, dass
`evalkit.schema.load_evals()` die Datei strukturell akzeptiert (siehe
Fix-Runde unten — die ursprüngliche Fassung behauptete „fünf Evals aus Spec
13", deckte aber nur vier der fünf Spec-13-Szenarien ab).

44 Unit-Tests über vier Testdateien (`test_exercise_forge_verify_blind.py`,
`test_exercise_forge_run_coding.py`, `test_exercise_forge_export.py`,
`test_exercise_forge_evals_schema.py`) plus eine Korrektur an
`tests/conftest.py` (siehe unten). Gesamte Suite: **220 von 220 Tests grün**
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
   gekostet. Das Skript markiert jede Distraktor-Wahl identisch als
   `suspicious` und zitiert die Begründung im Klartext — der Mensch (oder die
   Claude-Session, die die Skill ausführt) entscheidet, ob die Begründung
   trägt. Das ist mechanisch günstiger und verletzt A4 nicht (kein Fall wird
   stillschweigend als „ok" behandelt). **Nachtrag Fix-Runde (L1):** In der
   ursprünglichen Fassung sprach `SKILL.md`s Contract dennoch von einem
   Distraktor, der „mit valider Begründung" als kaputt *gilt* — eine
   Formulierung, die dem Mechanismus ein Urteilsvermögen zuschrieb, das er
   nicht hat. Der Contract-Satz wurde zurückgezogen auf das, was das Gate
   tatsächlich leistet: eine Markierung zur menschlichen Durchsicht. Der
   Verzicht selbst bleibt unverändert — nur die Beschreibung wurde ehrlicher.
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

## Fix-Runde (unabhängiger Review)

Ein unabhängiger Reviewer prüfte den Stand gegen `SKILL.md`, Spec 00 §1–4,
`docs/artifact-header.md`/`docs/known-limits.md` und fand zwei Defekte, drei
Lücken und eine Anmerkung (vollständiger Befund:
`scratchpad/review-exercise-forge.md`). Bearbeitet:

- **D1 (Defekt) — `export.py` glaubte eine von Hand geschriebene Verifikation.**
  `_check_verification` prüfte nur, dass `status` bekannt und `method`
  nicht-leer war — nicht, dass `method` eine der vier echten
  Blind-Gate-Methoden ist und `checked_at` gesetzt ist. Eine Session hätte
  `"status": "verified"` frei erfinden können, `export.py` hätte es klaglos
  als `[geprüft]` gerendert. Fix: `has_verified_provenance()` und
  `_effective_status()` prüfen die Herkunft; ohne echte Spur wird die Aufgabe
  beim Rendern auf `unverified` zurückgestuft — **exportiert, aber sichtbar
  als ungeprüft**, nicht ausgeschlossen (das war die explizite Vorgabe: „ist
  ungeprüft und wird als ungeprüft exportiert"). Sieben neue Tests.
- **D2 (Defekt) — `verify_open` verifizierte Aufgaben ohne Kriterien.**
  `all(met)` ist `True` für eine leere Liste; eine `open_question` mit
  `"criteria": []` bestand den (leeren) Abgleich und wurde `verified`. Fix:
  Vorabprüfung in `verify_open` gibt `unverified` zurück, bevor überhaupt ein
  Blind-Löser-Aufruf startet. Geprüft, ob dieselbe Konstruktion anderswo im
  Skript steckt (`grep -n "all(\|any("`) — es gab nur diese eine Stelle. Zwei
  neue Tests.
- **L1 (Lücke) — Contract versprach mehr, als das MC-Gate hält.** `SKILL.md`
  sagte, ein Distraktor gelte nur bei „valider Begründung" als kaputt; der
  Code markiert jede Fehlwahl identisch als `suspicious`, ohne
  Begründungsqualität zu bewerten. Der Verzicht auf ein drittes LLM-Urteil
  bleibt (siehe Design-Entscheidung 5) — der Contract-Satz wurde auf das
  zurückgezogen, was der Mechanismus tatsächlich leistet: eine Markierung zur
  menschlichen Durchsicht, kein Verdikt. Workflow-Schritt 5 verlangt jetzt
  explizit, die zitierte Begründung zu lesen, bevor etwas geändert wird.
- **L2 (Lücke) — `main() --all` verlor bereits geprüfte Urteile bei einer
  malformten Aufgabe.** Eine MC-Option ohne `"text"` löste ein unbehandeltes
  `KeyError` aus; `save_exercises()` lief erst nach der ganzen Schleife, ein
  Absturz mittendrin verwarf alle bereits berechneten Urteile. Fix: `verify_one`
  läuft pro Aufgabe in einem `try/except`, ein Fehlschlag wird als benannter
  `unverified`-Befund erfasst statt den Batch zu beenden; `save_exercises()`
  läuft jetzt nach jeder Aufgabe, nicht nur am Ende. Zwei neue Tests.
- **L3 (Lücke) — Eval-Abdeckung log über sich selbst.** Plan und dieser
  Bericht behaupteten „fünf Evals aus Spec 13 §Approach", tatsächlich fehlte
  Spec 13s Eval 4 (Karten-Atomarität bei „20 Karten zu X") ersatzlos — vier
  von fünf Spec-13-Szenarien waren abgedeckt, plus ein unabhängiger,
  zusätzlicher Spec-00-Pflichteval, macht fünf total, aber fälschlich als „die
  fünf aus Spec 13" beschrieben. Fix: sechster Eval
  `twenty-cards-stay-atomic` ergänzt (behavior/Judge — Kartenzahl und
  Inhaltsbündelung sind mit den vorhandenen Assertion-Primitiven nicht
  mechanisch zählbar, siehe `docs/known-limits.md`); dieser Bericht und die
  Eval-Beschreibung oben korrigiert. Ein Regressionstest
  (`test_all_five_spec13_scenarios_are_covered`) verhindert, dass künftig
  wieder eines der fünf Spec-13-Stichworte stillschweigend aus der Suite
  verschwindet.
- **A1 (Anmerkung) — tote Test-Assertion.** `test_render_markdown_never_
  marks_suspicious_as_verified` prüfte einen Substring
  (`"card-01 [geprüft]"`), der wegen des echten Headerformats nie auftreten
  konnte — die Assertion wäre auch bei einem kaputten `_status_marker` nie
  fehlgeschlagen. Korrigiert auf eine Prüfung, die tatsächlich etwas bewacht
  (`"[geprüft]" not in md`).

Alle fünf Punkte wurden bearbeitet — der Reviewer stufte keinen als „lassen,
wenn er es nicht verdient" ein, also gibt es hier keinen zurückgewiesenen
Befund zu begründen.

## Fix-Runde 2 (echter Eval-Lauf, zusammengesetzte Judge-Claims)

Der Koordinator fuhr die sechs Evals danach real gegen `run_evals.py`. Vier
bestanden zuverlässig: `single-flashcard-stays-single`,
`twenty-cards-stay-atomic`, `overspecified-coding-tests-are-flagged`,
`one-step-harder-changes-the-vector-not-just-wording` — D1 und D2 sind damit
mittelbar bestätigt (die Coding-Fixture braucht ein funktionierendes,
un-rationalisiertes Blind-Gate, um überhaupt grün zu werden). Zwei Evals
(`mc-distractor-trap-is-caught`, `narrow-criteria-on-open-question-are-flagged`)
fielen bei identischem Commit und identischer Fixture über zwei Läufe
abwechselnd rot/grün — keine kaputte Eval, sondern eine Eigenschaft ihrer
Bauform: Beide Judge-Claims verlangten drei Bedingungen in einem Satz
(Gate ausgeführt, Konflikt benannt, nicht `verified`); eine Kette aus drei
Gliedern kippt schon, wenn eines wackelt, und welches Glied wackelt,
variiert zwischen Läufen. Fix: „Gate ausgeführt" und „nicht `verified`" sind
im Aufgaben-JSON direkt sichtbar und wurden zu mechanischen Assertionen
(`file_matches` auf das `method`-Feld bzw. `must_not` auf `"status":
"verified"`); nur „Konflikt sichtbar benannt" bleibt Judge-Claim, jetzt als
einzige, einzeln entscheidbare Bedingung. Die generelle Beobachtung —
zusammengesetzte Judge-Claims sind unzuverlässig, unabhängig von der Skill —
steht jetzt in `docs/known-limits.md` unter „Judge". Die beiden geänderten
Evals wurden nach der Zerlegung nicht erneut gegen einen echten Agenten
gefahren (nur schema-validiert); die vier bestätigten Evals wurden nicht
verändert.

## Bekannte Grenzen (analog zu `docs/known-limits.md`)

- **Kein drittes Urteil über „valide Begründung" bei MC-Distraktoren** (siehe
  Entscheidung 5 oben, L1) — `suspicious` ist eine Warnung zur menschlichen
  Durchsicht, kein Beweis, dass der Distraktor kaputt ist. Der Contract
  verspricht das seit der Fix-Runde auch nicht mehr.
- **Die Herkunftsprüfung aus D1 ist strukturell, nicht kryptographisch.**
  `has_verified_provenance()` verlangt `method` aus dem echten Methodenset und
  ein gesetztes `checked_at` — beides ließe sich mit hinreichend Sorgfalt
  auch von Hand nachbilden (`"method": "blind_solve_mc", "checked_at":
  "2026-01-01T00:00:00Z"` ohne je `verify_blind.py` laufen zu lassen). Die
  Prüfung erhöht die Hürde für eine unbeabsichtigte Rationalisierung
  erheblich, verhindert aber keine vorsätzliche Fälschung — dafür bräuchte es
  eine Signatur oder ein Audit-Log, das hier nicht gebaut wurde.
- **Blind-Gate ist ein Einzel-Stichprobenlauf ohne Retry oder Mehrheitsvotum.**
  Jeder Aufruf ist ein einzelner `claude -p`-Lauf; ein funktionierender,
  absichtlich schwieriger Distraktor kann mit einer gewissen
  Grundwahrscheinlichkeit trotzdem `suspicious` auslösen (der Blind-Löser rät
  falsch, ohne dass am Distraktor etwas kaputt ist) — von einem echten Befund
  nicht unterscheidbar, ohne die Begründung selbst zu lesen (siehe L1).
- **Vier der sechs Evals sind gegen einen echten Agenten bestätigt** (siehe
  Fix-Runde 2), **die beiden zerlegten Evals seit ihrer Änderung nicht erneut.**
  `mc-distractor-trap-is-caught` und `narrow-criteria-on-open-question-are-flagged`
  wurden nach dem Zusammengesetzte-Claims-Fund umgebaut, aber nur
  schema-validiert (`evalkit.schema.load_evals()`), nicht erneut über
  `run_evals.py` gefahren. Ob die jetzt atomaren Judge-Claims tatsächlich
  stabiler sind, ist plausibel (die Kettenursache ist behoben), aber noch
  nicht empirisch bestätigt.
- **`verify_blind.py` läuft den Blind-Löser in einem leeren Temp-Verzeichnis**,
  nicht in einer vollständig isolierten Prozessumgebung — dieselbe Grenze wie
  bei `evalkit.dispatch.run_agent` (siehe `docs/known-limits.md`, Abschnitt
  Isolation): `$HOME`/`os.environ` gehen unverändert an den Subprozess.
- **Flashcard-Atomarität („eine Information pro Karte") ist nicht mechanisch
  geprüft.** Das Blind-Gate prüft nur Eindeutigkeit der Frage (Antwort trifft
  Rückseite), nicht ob die Rückseite mehrere Fakten bündelt. Eine verlässliche
  Heuristik dafür schien mir zu fragil, um sie als Prüfung auszugeben (A4) —
  die Regel bleibt Autorendoktrin in `task-schemas.md`, nicht Code; der neue
  Eval `twenty-cards-stay-atomic` prüft sie als Judge-Claim, ungelaufen.
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
220 passed
```

## Offene Sorgen

- `brief-common.md` fehlte (siehe oben) — falls die Datei eigentlich existieren
  sollte, sind mir möglicherweise Fehlerklassen oder Arbeitsweise-Vorgaben
  entgangen, die dort und nirgends sonst standen.
- Vier von sechs Evals sind gegen einen echten Agenten bestätigt; die beiden
  zerlegten (`mc-distractor-trap-is-caught`,
  `narrow-criteria-on-open-question-are-flagged`) wurden seit dem Umbau nicht
  erneut gefahren — bin nicht sicher, ob die verbliebenen Judge-Claims in der
  Praxis wirklich stabiler sind oder nur die eine bekannte Fehlerquelle
  (zusammengesetzte Bedingungen) beseitigt wurde, während eine andere
  unentdeckt bleibt.
- Die Herkunftsprüfung aus D1 ist strukturell, nicht kryptographisch (siehe
  Bekannte Grenzen) — eine vorsätzliche Fälschung von `method`/`checked_at`
  bliebe unentdeckt. Das war mit den Mitteln dieser Skill (Tier 1, kein
  Signatur-/Audit-Mechanismus) nicht wirtschaftlich zu schließen.
- Der Glob-Pfad-Fix aus dem Eval-Harness ist auf dieser Basis nicht vorhanden;
  sollte `feat/dev-report` vor `exercise-forge` gemergt werden, könnten die
  hartkodierten Themennamen in den Eval-Prompts unnötig restriktiv wirken
  (kein Schaden, nur ungenutztes Potenzial).
- `verify_blind.py`s Zwei-Aufruf-Protokoll (offene Fragen, Flashcards) kostet
  im Realbetrieb zwei `claude -p`-Aufrufe pro Aufgabe zusätzlich zum
  Haupt-Workflow — bei „20 Karten auf einmal" ggf. spürbare Latenz. Keine
  Parallelisierung eingebaut.
