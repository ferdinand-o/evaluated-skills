# Der Zyklus — Zustandsmodell, Verhalten, ein Test je Lauf

## Zustandsmodell

Je Test-ID gilt einer von drei Zuständen: unbekannt, `rot`, `grün`. Jeder Aufruf von
`tdd_log.py` schreibt höchstens eine Zeile `| <id> | <phase> | <befehl> | <exit> | <zeit> | <ausgabe> |`
in den letzten Abschnitt von `.skills/cache/test-first/log.md`.

| Aufruf | Zustand vorher | Befehl | Phase der Zeile | Zustand danach | Exit von tdd_log.py |
| --- | --- | --- | --- | --- | --- |
| `red` | beliebig | Exit ≠ 0 | `red` | rot | 0 |
| `red` | beliebig | Exit 0 | `sofort-grün` | unverändert | 1 |
| `green` | rot | Exit 0 | `green` | grün | 0 |
| `green` | rot | Exit ≠ 0 | `noch-rot` | rot | 1 |
| `green` | nicht rot | läuft nicht | keine Zeile | unverändert | 1 |
| `refactor` | grün | Exit 0 | `refactor` | grün | 0 |
| `refactor` | grün | Exit ≠ 0 | `refactor-rot` | rot | 1 |
| `refactor` | nicht grün | läuft nicht | keine Zeile | unverändert | 1 |
| beliebig | beliebig | Programm fehlt, Exit 127 oder Zeitgrenze | `ungeprüft` | unverändert | 1 |

Unter der Tabelle steht `Vollständige Zyklen: <n>`: Tests, deren letzter Zyklus (ab dem
letzten `red`) ein `green` hat und die jetzt grün sind. Ein `red` nach Grün beginnt einen
neuen Zyklus. `start` beginnt einen neuen Abschnitt; Zustände und Zählung gelten je
Abschnitt.

Der Zustand steht nirgends sonst — `tdd_log.py` liest ihn bei jedem Aufruf aus dem Log.
Wer das Log von Hand ändert, ändert den Zustand.

## Was ein Verhalten ist

Eine beobachtbare Eigenschaft, die ein Test in einem Satz prüft: „`parse_date('31.12.')`
ergänzt das laufende Jahr", „`POST /orders` ohne Menge antwortet 422". Mehrere Asserts in
einem Test sind ein Verhalten, solange sie dieselbe Eigenschaft prüfen. Zwei
Eigenschaften — zwei Tests, zwei Zyklen.

Die Test-ID ist meist der Testname: ohne Leerzeichen, ohne `|`. Dieselbe ID in `red` und
`green`, sonst zählt der Zyklus nicht.

## Sofort grün

Läuft ein neuer Test beim ersten Mal grün, steht er als `sofort-grün` im Log. Zwei
Ursachen:

- **Der Test prüft nichts Neues** — er trifft ein Verhalten, das er nicht treffen soll,
  oder seine Assertion ist zu schwach. Schärfen, dann wieder `red`.
- **Das Verhalten gibt es schon.** Dann nichts implementieren, den Test behalten und in
  der Übergabe sagen: „sofort grün — das Verhalten bestand schon". Produktionscode
  bleibt unverändert.

Nie: den Test so lange umbauen, bis er rot ist, ohne zu klären, welche Ursache gilt.

## Ein Test je Lauf

Der Befehl nach `--` führt genau den Test des Verhaltens aus, nicht die ganze Suite —
sonst färbt ein fremder roter Test das Rot.

| Runner | Form |
| --- | --- |
| pytest | `python -m pytest tests/test_dates.py::test_year_is_filled -q` oder `-k year_is_filled` |
| vitest, jest | `npx vitest run src/dates.test.ts -t "year is filled"` |
| go | `go test ./dates -run TestYearIsFilled` |
| cargo | `cargo test year_is_filled` |

Den ganzen Verifikationsbefehl des Repos (CLAUDE.md, Zeile `Verifikation:`) einmal am
Ende, außerhalb des Logs.

## Grenzen des Rot

Rot heißt Exit ≠ 0 eines Befehls, dessen Programme existieren. Ein Import- oder
Sammelfehler zählt als Rot — der Test scheitert, solange der Code fehlt. Ein fehlendes
Runner-Modul (`python -m pytest` ohne pytest) sieht genauso aus und zählt ebenfalls als
Rot. Deshalb vor dem ersten `red` die Ausgabe lesen: Steht dort der erwartete
Fehlschlag oder `No module named pytest`?
