<!-- skill: debug-ledger | schema: 1 | generated: python skills/debug-ledger/scripts/new_ledger.py --symptom "Login haengt beim Start fuer manche Nutzer" --repro "pytest tests/test_login.py::test_hang" --expected "Login kehrt in < 1s zurueck" --observed "Login haengt endlos, kein Fehler im Log" -->

## Symptom
Login hängt beim Start für manche Nutzer, kein Timeout, kein Fehler im Log.

## Repro-Kommando
```
pytest tests/test_login.py::test_hang
```

## Erwartung vs. Beobachtung
- Erwartet: Login kehrt in < 1s zurück
- Beobachtet: Login hängt endlos, kein Fehler im Log

## Evidenz-Log
Log-Ausgabe von `cache_key()` pro Request zeigt: zwei verschiedene Nutzer
erzeugen denselben Cache-Key, weil `cache_key()` den Nutzernamen auf 8 Zeichen
kürzt.

## Hypothesen
| Hypothese | Test | Ergebnis | Verdict |
| --- | --- | --- | --- |
| Cache-Key kollidiert zwischen Nutzern mit gleichem Präfix | Log-Ausgabe von cache_key() pro Request geprüft | Zwei Nutzer erzeugten denselben Key | Bestätigt |
| Race Condition im Session-Store | Lastfreier Einzelaufruf reproduziert den Hang ebenfalls | Hang tritt auch ohne Last auf, also keine Race Condition | Verworfen |

## Root Cause
`cache_key(username)` kürzt auf die ersten 8 Zeichen. Zwei Nutzernamen mit
gleichem Präfix (z. B. `alexander.mueller` und `alexander.schmidt`) erzeugen
denselben Key; der zweite wartet auf eine Sperre, die der erste nie freigibt.

## Fix
`cache_key()` nutzt die volle, eindeutige User-ID statt des gekürzten Namens.

## Verifikation
Vor dem Fix: `pytest tests/test_login.py::test_hang` hängt (Timeout nach 30s).
Nach dem Fix: `pytest tests/test_login.py::test_hang` grün in 0.3s.

## Prävention
Regressionstest ergänzt, der zwei Nutzer mit gleichem 8-Zeichen-Präfix prüft.
Docstring an `cache_key()` warnt vor Kürzung.
