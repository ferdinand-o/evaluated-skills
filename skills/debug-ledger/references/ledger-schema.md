# Ledger-Schema

Ein Ledger ist immer im Mini-Schema. Drei der Signale aus der SKILL.md schalten es
auf das volle Schema um (`new_ledger.py --escalate`); die zusätzlichen Sektionen
kommen dann mit dem Platzhalter `_(noch offen)_` an und werden während der
Untersuchung gefüllt.

## Mini-Schema (immer, ab Anlage gefüllt)

| Feld | Inhalt |
| --- | --- |
| `## Symptom` | Beobachtetes Fehlverhalten, wörtlich — keine Interpretation. |
| `## Repro-Kommando` | Exaktes, kopierbares Kommando, das den Bug auslöst. |
| `## Erwartung vs. Beobachtung` | Zwei Zeilen: was hätte passieren sollen, was ist passiert. |

Diese drei Felder werden von `new_ledger.py` beim Anlegen aus den Flags
`--symptom/--repro/--expected/--observed` gefüllt — sie sind bei Anlage nie leer.
`check_ledger.py` prüft sie trotzdem bei jedem Aufruf, falls jemand ein Feld von
Hand geleert hat.

## Volles Schema (durch `--escalate` angehängt)

| Feld | Inhalt |
| --- | --- |
| `## Evidenz-Log` | Instrumentierungs-Outputs und Bisect-Ergebnisse, mit Kommando und Zeitstempel. |
| `## Hypothesen` | Tabelle `Hypothese \| Test \| Ergebnis \| Verdict` — eine Zeile pro getesteter Hypothese. Verdict ist `Bestätigt` oder `Verworfen`, nie Freitext. |
| `## Root Cause` | Die tatsächliche Ursache, nicht das Symptom. |
| `## Fix` | Die vorgeschlagene Änderung. |
| `## Verifikation` | Failing Test vor dem Fix (Kommando + Fehlschlag), grüner Lauf danach (Kommando + Erfolg). |
| `## Prävention` | Was eine Wiederholung verhindert: Test, Assertion, Doku, Guard. |

**Contract:** `check_ledger.py` meldet einen Verstoß, wenn `## Fix` gefüllt ist,
aber keine Zeile der Hypothesen-Tabelle als *getestet* zählt. Eine Zeile zählt
nur als getestet, wenn alle drei Bedingungen gelten:

1. **Test und Ergebnis tragen echten Inhalt** — mindestens 8 Zeichen, keine
   Füllwörter (`-`, `n/a`, `TBD`, `unklar`, `unbekannt`, `offen`, `unsicher`,
   `vielleicht`, …) und mindestens ein Buchstabe (kein reiner Satzzeichen-Text
   wie `-` oder `?`).
2. **Verdict stammt aus der geschlossenen Menge `Bestätigt` / `Verworfen`**
   (Groß-/Kleinschreibung egal). Freitext wie „Unklar", „vielleicht", „passt
   schon" zählt nicht — ein Verdict ist ein Ergebnis, keine Einschätzung.
3. Hypothese selbst darf frei formuliert sein (das ist die Vermutung, die
   getestet wird) — nur Test/Ergebnis/Verdict müssen die Kriterien oben erfüllen.

Eine Zeile wie `Vermutlich ein Cache-Problem | - | - | Unklar` zählt **nicht**
als getestet — weder Test noch Ergebnis tragen Inhalt, und „Unklar" ist kein
gültiges Verdict. Ein Fix ohne getestete Hypothese ist geraten, kein Ergebnis
einer Untersuchung.

## Ausgefülltes Beispiel

```markdown
<!-- skill: debug-ledger | schema: 1 | generated: python skills/debug-ledger/scripts/new_ledger.py --symptom "Login haengt beim Start" --repro "pytest tests/test_login.py::test_hang" --expected "Login kehrt in < 1s zurueck" --observed "Login haengt endlos" -->

## Symptom
Login hängt beim Start, kein Timeout, kein Fehler im Log.

## Repro-Kommando
```
pytest tests/test_login.py::test_hang
```

## Erwartung vs. Beobachtung
- Erwartet: Login kehrt in < 1s zurück
- Beobachtet: Login hängt endlos

## Evidenz-Log
`bisect_run.py --good v1.2 --bad HEAD --command "pytest tests/test_login.py::test_hang"`
→ erster schlechter Commit: `a1b2c3d` ("feat: Session-Cache eingeführt").
Instrumentierung an der Cache-Grenze zeigt: `cache_key` ist für zwei
verschiedene Nutzer identisch.

## Hypothesen
| Hypothese | Test | Ergebnis | Verdict |
| --- | --- | --- | --- |
| Cache-Key kollidiert zwischen Nutzern | Log-Ausgabe von `cache_key` pro Request geprüft | Zwei Nutzer erzeugten denselben Key | Bestätigt |
| Race Condition im Session-Store | Lastfreier Einzelaufruf reproduziert den Hang ebenfalls | Hang tritt auch ohne Last auf | Verworfen |

## Root Cause
`cache_key = hash(username[:8])` kürzt auf 8 Zeichen — zwei Nutzernamen mit
gleichem Präfix kollidieren, der zweite wartet auf eine Sperre, die nie freigegeben wird.

## Fix
`cache_key` nutzt die volle User-ID statt des gekürzten Namens.

## Verifikation
Vor dem Fix: `pytest tests/test_login.py::test_hang` hängt (Timeout nach 30s).
Nach dem Fix: `pytest tests/test_login.py::test_hang` grün in 0.4s.

## Prävention
Regressionstest `test_cache_key_is_unique_per_user` ergänzt; Docstring an
`cache_key()` warnt vor Kürzung.
```
