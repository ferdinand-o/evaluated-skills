# test-design — querliegende Doktrin für Python und TypeScript

Wird bei **jedem** Repo-Typ zusätzlich zur passenden Typ-Referenz geladen.
Java erscheint hier bewusst nicht — nur in `legacy-monolith.md`, wo es als
Legacy-Vertreter auftritt. Drei gleichwertige Sprachen hätten diese Referenz
gesprengt, bevor sie nützlich wird.

## Was einen guten Test ausmacht

- **Ein Verhalten, ein Test.** Wenn der Testname eine "und"-Verbindung
  braucht, sind es zwei Tests.
- **Testet das Verhalten, nicht die Implementierung.** Ein Test, der bei
  jedem internen Refactoring bricht, obwohl sich das beobachtbare Verhalten
  nicht geändert hat, ist ein Wartungskosten-Posten ohne Regressions-Nutzen —
  genau das Gegenteil der Doktrin.
- **Ein Fehlschlag zeigt sofort die Ursache.** Eine Assertion auf ein
  komplettes Objekt, wo nur ein Feld zählt, verschleiert, welches Feld brach.
- **Arrange-Act-Assert bleibt sichtbar getrennt.** Verschachtelte Setup-Helfer
  sind erlaubt, ihr Aufruf gehört sichtbar in den `Arrange`-Teil.
- **Prüftabellen (`pytest.mark.parametrize` / `it.each`) für Regeln mit
  Gegenproben.** Eine Erkennungsregel ohne mindestens eine Gegenprobe, die
  *nicht* treffen darf, ist unvollständig getestet — siehe die
  Fix-Commit-Erkennung in `dev-report/scripts/collect.py` als Vorbild.

## Anti-Patterns

| Anti-Pattern | Warum es schadet | Gegenmittel |
| --- | --- | --- |
| **Mocking-Overkill** — jede Kollaboration gemockt | Der Test beweist nur, dass Mocks sich wie konfiguriert verhalten, nicht dass das System funktioniert | Mocken an der echten Grenze (Netzwerk, Zeit, Zufall), nicht an jeder Funktionsgrenze |
| **Implementierungsdetail-Tests** — private Methoden, interne Zustände | Bricht bei jedem Refactoring ohne Verhaltensänderung | Über die öffentliche Schnittstelle testen |
| **Snapshot-Wildwuchs** — jede Ausgabe als Snapshot eingefroren | Ein Snapshot-Update-Reflex ersetzt das Lesen des Diffs; echte Regressionen rutschen durch | Snapshots für stabile, selten geänderte Strukturen (CLI-Output, generiertes Markup) — nicht für Domänenlogik mit klarer Erwartung |
| **Erfundenes Soll-Verhalten** — ein Test schreibt fest, was der Code *tun sollte*, ohne zu prüfen, was er *tut* | In unbekanntem Code ist das eine Wette, keine Absicherung — der Legacy-Fall aus `legacy-monolith.md` | Erst Characterization, dann ändern |
| **Ein XL-Test für den ganzen Layer** | Ein Fehlschlag zeigt nicht, welche der zwölf Assertions brach | Ein Test pro Verhalten, auch wenn das mehr Testfälle bedeutet |

## Flakiness — Ursachen und Gegenmittel

| Ursache | Gegenmittel |
| --- | --- |
| Echte Zeit (`datetime.now()`, `Date.now()`) | Zeit injizieren oder einfrieren (`freezegun`, `vi.useFakeTimers()`) |
| Testreihenfolge / geteilter Zustand | Jeder Test baut seinen Zustand selbst auf (Fixtures, `beforeEach`), nichts wird zwischen Tests wiederverwendet |
| Netzwerk/Zeitfenster-Races (`sleep` statt Warten auf Bedingung) | Auf die Bedingung warten (Polling mit Timeout, `waitFor`), nie auf eine feste Zeitspanne |
| Zufallsdaten ohne festen Seed | Seed fixieren, oder die Eigenschaft testen statt eines konkreten Werts |
| Parallele Testläufe auf geteilten Ressourcen (Datei, Port, DB) | Pro Testlauf isolierte Ressource (Tempdir, freier Port, eigene Test-DB/Schema) |

## Python — Konventionen

- `pytest`, Parametrisierung über `@pytest.mark.parametrize`.
- Fixtures (`tmp_path`, eigene `@pytest.fixture`) statt Setup/Teardown-Methoden.
- `monkeypatch` statt globaler Patches, die zwischen Tests durchsickern können.

## TypeScript — Konventionen

- `vitest` oder `jest`, Parametrisierung über `it.each`/`test.each`.
- Zeit- und Zufalls-Mocks über die Runner-eigenen Utilities (`vi.useFakeTimers`),
  nicht über selbstgebaute globale Overrides.
- Typen sind kein Testersatz: Ein korrekt typisierter Aufruf kann trotzdem ein
  falsches Verhalten haben — Typprüfung ersetzt keine Assertion.
