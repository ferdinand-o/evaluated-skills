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

77 Unit-Tests über vier Testdateien (`test_exercise_forge_verify_blind.py`,
`test_exercise_forge_run_coding.py`, `test_exercise_forge_export.py`,
`test_exercise_forge_evals_schema.py`, Stand nach Fix-Runde 3) plus eine
Korrektur an `tests/conftest.py` (siehe unten). Gesamte Suite: **223 von 223
Tests grün** (`.venv/bin/pytest -q`).

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

## Fix-Runde 1 (unabhängiger Review)

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
`one-step-harder-changes-the-vector-not-just-wording` — D1 und D2 galten damit
als mittelbar bestätigt. **Das war voreilig, siehe Fix-Runde 3** —
`overspecified-coding-tests-are-flagged` erwies sich in Wahrheit als falsch
grün. Zwei Evals (`mc-distractor-trap-is-caught`,
`narrow-criteria-on-open-question-are-flagged`) fielen bei identischem Commit
und identischer Fixture über zwei Läufe abwechselnd rot/grün — keine kaputte
Eval, sondern eine Eigenschaft ihrer Bauform: Beide Judge-Claims verlangten
drei Bedingungen in einem Satz (Gate ausgeführt, Konflikt benannt, nicht
`verified`); eine Kette aus drei Gliedern kippt schon, wenn eines wackelt,
und welches Glied wackelt, variiert zwischen Läufen. Fix: „Gate ausgeführt"
und „nicht `verified`" sind im Aufgaben-JSON direkt sichtbar und wurden zu
mechanischen Assertionen (`file_matches` auf das `method`-Feld bzw.
`must_not` auf `"status": "verified"`); nur „Konflikt sichtbar benannt"
bleibt Judge-Claim, jetzt als einzige, einzeln entscheidbare Bedingung. Die
generelle Beobachtung — zusammengesetzte Judge-Claims sind unzuverlässig,
unabhängig von der Skill — stand zu diesem Zeitpunkt in
`docs/known-limits.md` unter „Judge"; Fix-Runde 3 verschärft sie. Die beiden
geänderten Evals wurden nach der Zerlegung nicht erneut gegen einen echten
Agenten gefahren (nur schema-validiert); die vier bestätigten Evals wurden
nicht verändert.

## Fix-Runde 3 (Zerlegung deckt einen echten Defekt auf)

Der Koordinator fuhr den Bestätigungslauf. Ergebnis: drei Evals bestanden
zuverlässig (`single-flashcard-stays-single`, `twenty-cards-stay-atomic`,
`one-step-harder-changes-the-vector-not-just-wording`). Die beiden in
Fix-Runde 2 zerlegten Evals fielen jetzt **mechanisch**, nicht mehr am
Judge: `must_not` fand `"status": "verified"` in beiden Fixtures, obwohl
beide absichtlich einen Konflikt enthalten (der ambige Distraktor, das zu
enge Kriterium). `overspecified-coding-tests-are-flagged` — zu diesem
Zeitpunkt noch mit dem alten, zusammengesetzten Claim — fiel am Judge. Die
in Fix-Runde 2 als „bestanden" gemeldeten vier Evals waren also nur zu drei
Vierteln ehrlich grün: Der zusammengesetzte Claim bei
`overspecified-coding-tests-are-flagged` hatte denselben Defekt vorher
überstimmt — er bejahte die Kette, weil „Konflikt benannt" erfüllt war, und
verlor dabei, dass „nicht verified" es nicht war.

**Untersuchung:** `verify_mc`, `verify_open` und `run_coding.verify_coding`
wurden erneut gegen die konkreten Fixture-Inhalte durchgespielt (nicht nur
gelesen) — keine der drei Funktionen gibt für einen erkannten Konflikt
`_verified(...)` zurück; das ist in den bestehenden Unit-Tests bereits
scharf abgesichert (`test_verify_mc_distractor_choice_is_suspicious` u. Ä.).
`main()` in `verify_blind.py` schreibt zudem exakt das `verdict`-Objekt in
die Datei, das es auch druckt — kein Divergenzpunkt zwischen „melden" und
"markieren" im Skript selbst. Ohne persistiertes Transcript (`evalkit`
speichert keins, siehe `docs/known-limits.md`) lässt sich der genaue Ablauf
im Agenten nicht rekonstruieren; die plausibelste Erklärung, die mit allen
Fakten (Code korrekt, `status` trotzdem `verified`, frühere Läufe bestätigten
„Konflikt benannt") vereinbar ist: Die Session hat `verification` nach dem
Melden direkt mit einem Editor-Werkzeug auf `status: verified` gesetzt, statt
den Status aus einem erneuten `verify_blind.py`-Lauf zu übernehmen — und
dabei vermutlich `method`/`checked_at` des vorherigen (echten) `suspicious`-
Laufs unverändert gelassen, wodurch selbst `export.has_verified_provenance()`
das nicht erkannt hätte (sie prüft nur, *dass* `method`/`checked_at`
vorhanden sind, nicht, dass sie zum aktuellen `status` passen — eine bislang
unbenannte Lücke in der D1-Herkunftsprüfung, jetzt in `docs/known-limits.md`
dokumentiert).

**Fix:**
1. `overspecified-coding-tests-are-flagged` nach demselben Muster zerlegt wie
   die anderen beiden (mechanisches „Gate lief", mechanisches „nicht
   verified", ein einzelner Judge-Claim „überspezifizierter Test benannt").
2. `SKILL.md` verschärft an der Stelle, wo die Rationalisierung entsteht:
   Contract bekommt einen neuen Satz „Melden ersetzt nicht Markieren" (die
   Änderung an `verification` kommt ausschließlich aus einem Skriptlauf,
   nie von Hand — auch nicht nach einer Erklärung); Workflow-Schritt 5 sagt
   jetzt explizit „`verify_blind.py` erneut aufrufen", nicht "nochmal
   überlegen"; Anti-Rationalisierungs-Tabelle bekommt die Zeile „Ich hab den
   Fund doch erklärt, das reicht" → „Melden ersetzt nicht Markieren."
3. Drei neue Schema-Tests (`test_problem_found_evals_check_gate_ran_
   mechanically`, `test_problem_found_evals_check_not_verified_mechanically`,
   `test_problem_found_evals_carry_exactly_one_judge_claim`) halten die
   Drei-Assertionen-Zerlegung für alle drei „Gate findet ein Problem"-Evals
   dauerhaft fest, damit sie nicht unbemerkt wieder zu einer Kette
   zusammenwachsen.

**Was bewusst nicht gebaut wurde:** Ein mechanischer (G2) oder erzwungener
(G3) Schutz gegen genau dieses Hand-Editieren der Quelle. Der SKILL.md-Fix
ist G1 (Selbstauskunft, Spec 00 §4) — er verlangt es, erzwingt es aber nicht.
Ein Hook, der einen Edit auf `verification` ohne begleitenden Skriptlauf
blockiert, wäre nach Spec 00 §4 nur dort gerechtfertigt, wo der Schaden
irreversibel ist und der Nutzer ihn bewusst installiert — für eine
Lernaufgaben-Skill mit menschlichem Review vor dem Lernen erschien mir das
unverhältnismäßig gegenüber dem Aufwand, entscheide aber gern anders, wenn
gewünscht. Das ist eine eigene Design-Entscheidung dieser Runde, keine aus
Spec 13 oder den Rulings ableitbare.

## Bekannte Grenzen (analog zu `docs/known-limits.md`)

- **Kein drittes Urteil über „valide Begründung" bei MC-Distraktoren** (siehe
  Entscheidung 5 oben, L1) — `suspicious` ist eine Warnung zur menschlichen
  Durchsicht, kein Beweis, dass der Distraktor kaputt ist. Der Contract
  verspricht das seit der Fix-Runde auch nicht mehr.
- **Die Herkunftsprüfung aus D1 ist strukturell, nicht kryptographisch — und
  prüft `method`/`checked_at` nicht gegen den aktuellen `status`.**
  `has_verified_provenance()` verlangt `method` aus dem echten Methodenset und
  ein gesetztes `checked_at`, aber beide könnten von einem früheren, echten
  Lauf mit einem *anderen* Status stammen: Eine Session könnte einen echten
  `suspicious`-Datensatz nehmen und nur das Wort `status` auf `verified`
  ändern, `method`/`checked_at` unangetastet — die Prüfung sähe „echte
  Herkunft" und würde es nicht bemerken. Genau dieses Muster ist die
  plausibelste Erklärung für den in Fix-Runde 3 gefundenen Defekt (siehe
  dort). Eine Signatur oder ein Audit-Log, das `status` an den konkreten Lauf
  bindet, wäre der nächste Schritt, wurde hier nicht gebaut.
- **Blind-Gate ist ein Einzel-Stichprobenlauf ohne Retry oder Mehrheitsvotum.**
  Jeder Aufruf ist ein einzelner `claude -p`-Lauf; ein funktionierender,
  absichtlich schwieriger Distraktor kann mit einer gewissen
  Grundwahrscheinlichkeit trotzdem `suspicious` auslösen (der Blind-Löser rät
  falsch, ohne dass am Distraktor etwas kaputt ist) — von einem echten Befund
  nicht unterscheidbar, ohne die Begründung selbst zu lesen (siehe L1).
- **Kein mechanischer Schutz gegen Hand-Editieren von `verification`.**
  `SKILL.md` verbietet es jetzt explizit und an der Versuchungsstelle
  (Fix-Runde 3, „Melden ersetzt nicht Markieren"), aber das ist ein G1-Fix
  (Selbstauskunft) — nichts im Code verhindert oder erkennt einen direkten
  Edit auf `verification.status`, der nicht aus einem `verify_blind.py`-
  Lauf stammt. Ein G2-Skript oder ein G3-Hook wäre nach Spec 00 §4 der
  nächste Schritt, wurde bewusst nicht gebaut (siehe Fix-Runde 3).
- **Drei der sechs Evals sind gegen einen echten Agenten bestätigt**
  (`single-flashcard-stays-single`, `twenty-cards-stay-atomic`,
  `one-step-harder-changes-the-vector-not-just-wording`, siehe Fix-Runde 3).
  Die drei „Gate findet ein Problem"-Evals (`mc-distractor-trap-is-caught`,
  `narrow-criteria-on-open-question-are-flagged`,
  `overspecified-coding-tests-are-flagged`) sind seit ihrer Zerlegung nur
  schema-validiert, nicht erneut über `run_evals.py` gefahren — sie sind
  gerade die Evals, die den Fix-Runde-3-Defekt aufdecken sollen, also die mit
  dem größten Interesse an einer echten Bestätigung.
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
223 passed
```

## Offene Sorgen

- `brief-common.md` fehlte (siehe oben) — falls die Datei eigentlich existieren
  sollte, sind mir möglicherweise Fehlerklassen oder Arbeitsweise-Vorgaben
  entgangen, die dort und nirgends sonst standen.
- Drei von sechs Evals sind gegen einen echten Agenten bestätigt; die drei
  „Gate findet ein Problem"-Evals wurden seit ihrer Zerlegung nicht erneut
  gefahren. Der SKILL.md-Fix aus Fix-Runde 3 ist plausibel, aber ungeprüft —
  ob er das Hand-Editieren von `verification` in der Praxis wirklich
  verhindert, oder ob eine Session die neue Doktrin genauso übergeht wie die
  alte implizite, weiß ich nicht. Das ist die größte offene Frage dieser
  gesamten Skill: ein G1-Fix für ein Problem, das eigentlich einen G2/G3-Fix
  verdient hätte, den ich bewusst nicht gebaut habe (Abwägung in Fix-Runde 3).
- Die Herkunftsprüfung aus D1 ist strukturell, nicht kryptographisch, und
  prüft `method`/`checked_at` nicht gegen den aktuellen `status` (siehe
  Bekannte Grenzen und Fix-Runde 3) — eine Session, die nur das `status`-Wort
  in einem echten, älteren Datensatz ändert, bliebe unentdeckt. Das war mit
  den Mitteln dieser Skill (Tier 1, kein Signatur-/Audit-Mechanismus) nicht
  wirtschaftlich zu schließen.
- Der Glob-Pfad-Fix aus dem Eval-Harness ist auf dieser Basis nicht vorhanden;
  sollte `feat/dev-report` vor `exercise-forge` gemergt werden, könnten die
  hartkodierten Themennamen in den Eval-Prompts unnötig restriktiv wirken
  (kein Schaden, nur ungenutztes Potenzial).
- `verify_blind.py`s Zwei-Aufruf-Protokoll (offene Fragen, Flashcards) kostet
  im Realbetrieb zwei `claude -p`-Aufrufe pro Aufgabe zusätzlich zum
  Haupt-Workflow — bei „20 Karten auf einmal" ggf. spürbare Latenz. Keine
  Parallelisierung eingebaut.
