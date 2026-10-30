<!-- skill: deep-review | schema: 1 | generated: von Hand nach docs/superpowers/plans/2026-10-30-deep-review.md, Task 1 -->
# deep-review — Abschlussbericht

Gebaut nach `specs/Spec 26 – deep-review.md` und
`docs/superpowers/plans/2026-10-30-deep-review.md`. Stand: Task 1 (Messfixture und
Basislinie, 2026-10-30). Die Skill selbst gibt es noch nicht; dieser Bericht hält fest,
woran sie sich in Task 23 messen lassen muss.

## Was entstanden ist

```
evals/fixtures/dr-seeded/fixture.json        lagerwerk + Sammelversand, fünf eingebaute Fehler
evals/fixtures/dr-seeded/README.md           Projekt-README (Baseline-Commit)
evals/fixtures/dr-seeded-clean/fixture.json  dieselbe Fixture ohne die fünf Fehler
evals/fixtures/dr-seeded-clean/README.md     wie oben
tests/test_deep_review_kit.py                test_seeded_fixtures
```

`prepare()` baut drei Commits: `fixture baseline` (README.md), bei Tag `base` das Paket
`lagerwerk` (12 Module, 1.138 Zeilen, dazu 246 Zeilen Tests und Hilfsdateien: Bestand, Inventur,
Wareneingang, Retouren, Reservierung, Paketdienst, Versand mit Wiederholung und Storno,
Exporte), darauf als HEAD das Feature „Sammelversand" (4 neue Module, 2 geänderte, 2 neue
Testdateien, 401 Zeilen hinzu, 1 entfernt). Die README liegt im Fixture-Ordner, weil `prepare()` den
Baseline-Commit ohne `--allow-empty` macht.

Jeder Fehler sieht im Diff allein korrekt aus. Erkennbar ist er erst mit einer Stelle aus
`base`, die der Diff nicht berührt:

| Nr. | Klasse | Stelle im Diff | Vertrag in `base` |
| --- | --- | --- | --- |
| 1 | `None` über zwei Dateien | `lagerwerk/batch.py:106`, `primary_bin()` ungeprüft in den `PickStop` | `lagerwerk/warehouse.py:95`: `None`, wenn aller Bestand unter Inventursperre liegt, obwohl die Reservierung gelingt |
| 2 | Grenzwert um eins daneben | `lagerwerk/packing.py:15`, `<=` gegen `MAX_PARCEL_WEIGHT_G` | `lagerwerk/config.py:7`: Grenze exklusiv |
| 3 | Ressourcenleck nur im Fehlerpfad | `lagerwerk/batch.py:149–153`, `ExportSink(...).open()` … `commit()` | `lagerwerk/storage.py:16`: nur `discard()`/`__exit__` schließen den Handle und löschen `.part` |
| 4 | verschluckte Exception | `lagerwerk/booking.py:30–32`, `except CarrierError` → `return parcel.label` | `lagerwerk/dispatch.py:47`: Wiederholung und Storno in `Dispatcher.ship` laufen nie |
| 5 | Kommentar widerspricht Code | `lagerwerk/zones.py:43`, Listenpreis netto | `lagerwerk/interfaces.py:26`: `RateProvider.quote` verspricht brutto |

`test_seeded_fixtures` prüft: beide Manifeste mit `"git": true`, zwei Commits, Tag `base`
am ersten; Gerüst und Messages gleich; genau fünf abweichende Blöcke, jeder von einer
Diff-Stelle der `description` getroffen; je Fehler eine zweite Stelle in einer Datei, die
`base..HEAD` nicht berührt; keine verräterischen Wörter im neuen Code; die mitgelieferten
35 Tests laufen auf beiden Fassungen grün, treffen also keinen der fünf Fehler. Ein
Probelauf außerhalb der Suite zeigt alle fünf: Absturz bei gesperrtem Fach, 31.500 g
passt, Auftrag „versandt" mit Label `None` nach einem einzigen Ausfall, liegengebliebene
`.part`-Datei, 410 statt 488 Cent.

## Basislinie

**Aufbau.** Je Fixture und Werkzeug drei Läufe, jeder in einem frischen Workspace aus
`evalkit.workspace.prepare(dest, None, fixture_dir)`, Timeout 600 s, `--max-turns 30`,
Claude Code 2.1.314, Standard-Berechtigungsmodus:

- `/code-review`: `claude -p "/code-review base..HEAD" --output-format json`
  (laut `modelUsage` `claude-opus-5-5`; keine Stufe angegeben).
- Sonnet: `claude -p --model sonnet "Prüf den Diff base..HEAD auf Fehler. Nenne je Fund
  Datei:Zeile und Grund." --output-format json` (`claude-sonnet-5-5`), ohne Inventar.

Treffer heißt: richtige Datei und Stelle im Diff, Klasse sinngemäß. Ausgewertet per
Skript (Datei plus Stichwort je Fehler), jeder Treffer und jede Lücke danach am Text
nachgeprüft; die Rohantworten liegen nicht im Repo. Kein Lauf stieß an `--max-turns`.

### Trefferquote auf `dr-seeded`

| Lauf | F1 | F2 | F3 | F4 | F5 | Treffer | `total_cost_usd` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/code-review` 1 | ja | ja | ja | ja | ja | 5/5 | 0,3738 |
| `/code-review` 2 | ja | ja | ja | ja | ja | 5/5 | 0,4480 |
| `/code-review` 3 | ja | ja | ja | ja | ja | 5/5 | 0,2896 |
| Sonnet 1 | nein | ja | ja | ja | ja | 4/5 | 0,2034 |
| Sonnet 2 | nein | ja | ja | ja | ja | 4/5 | 0,2130 |
| Sonnet 3 | ja | ja | ja | ja | ja | 5/5 | 0,2177 |

Mittel: `/code-review` 5,0 von 5, Sonnet 4,33 von 5; die Vereinigung beider findet in
jedem Lauf alle fünf. Die Treffer begründen mit dem Vertrag aus `base` (exklusive Grenze
in `config.py`, Brutto-Zusage von `RateProvider`, `ExportSink`-Docstring, Wiederholung
und Storno im `Dispatcher`, Inventursperre): Die Werkzeuge lesen die unveränderten Dateien
von sich aus. Sonnet verfehlt zweimal Fehler 1,
den einzigen, dessen Vertrag zwei Schritte entfernt liegt (Reservierung gelingt, Fach
trotzdem gesperrt).

### Weitere Funde auf `dr-seeded-clean`

| Lauf | als Fehler gemeldet | davon Code | davon Stil/Doppelung/Tests | Hinweise ohne Fehler-Einstufung | `total_cost_usd` |
| --- | --- | --- | --- | --- | --- |
| `/code-review` 1 | 10 | 7 | 3 | — | 0,3807 |
| `/code-review` 2 | 10 | 7 | 3 | — | 0,5322 |
| `/code-review` 3 | 10 | 8 | 2 | — | 0,4309 |
| Sonnet 1 | 5 | 4 | 1 | — | 0,3005 |
| Sonnet 2 | 1 | 1 | 0 | 5 | 0,2725 |
| Sonnet 3 | 0 | 0 | 0 | 7 | 0,2654 |

Keiner dieser Funde hält eine der fünf korrigierten Stellen für falsch; Sonnet 2 und 3
bestätigen sie ausdrücklich. Die Funde betreffen Schwächen, die beide Fassungen gleich
haben — und sie sind **keine Fehlalarme**. Nachgeprüft am 2026-10-30 mit einem
Repro-Skript gegen den Code von `dr-seeded-clean` (Hilfen aus `tests/helpers.py`); jeder
dieser fünf Funde lässt sich auslösen:

| Fund (in wie vielen `/code-review`-Läufen) | Auslösung | Ergebnis |
| --- | --- | --- |
| zurückgestellter Auftrag kollidiert im nächsten Lauf mit seiner Reservierung (3 von 3) | Lauf 1 stellt `O1` zurück, Lauf 2 mit demselben `ReservationBook` ruft `add(O1)` | `ValueError: O1 ist schon reserviert`, `add()` fängt nur `InsufficientStock` |
| `UnknownZone` aus `pack()` ungefangen (3 von 3) | Auftrag mit `zone="CH"` vor einem gültigen | `UnknownZone: 'CH'`, der ganze Packlauf bricht ab |
| Gefahrgut außerhalb DE scheitert immer (3 von 3) | `A-100` + `L-400`, Zone `EU1` | erst gebucht, dann storniert, Auftrag `failed` |
| `ship()` nicht wiederholbar (2 von 3) | `ship()` zweimal | zweite Sendung gebucht (1 → 2), dann `KeyError: 'O1'` ohne Storno |
| Kommissionierung ohne Blick auf den Fachbestand (2 von 3) | 25 × `A-100`, Hauptfach hat 20 | ein Stopp „25 aus `G01-F04-E0`" |

Nur gelesen, nicht ausgelöst, aber am Code nachvollziehbar: Export am selben Tag
überschreibt den vorigen, abgelaufene Reservierung führt in `Dispatcher.ship` zu einem
`KeyError` nach dem Buchen. Die Stil- und Doppelungsfunde (zweite Stufentabelle in
`zones.py`, Liste statt Menge für `deferred`, toter `parcel_count`) stimmen sachlich und
sind Hinweise, keine Fehler. Die Fixture enthält damit neben den fünf eingebauten Fehlern
mindestens fünf weitere echte, unabsichtliche; `dr-seeded-clean` ist keine fehlerfreie
Fassung, nur eine ohne die fünf.

Für die Abnahme heißt das: Die Präzision lässt sich an der Gesamtzahl der Funde auf
`dr-seeded-clean` nicht messen. Gezählt werden darf nur, ob ein Fund einer der fünf
korrigierten Stellen widerspricht — das tat in keinem Lauf ein Werkzeug.

### Kosten

Diese Runde: 3,9278 USD (`/code-review` 2,4554, im Mittel 0,409 je Lauf; Sonnet 1,4724,
im Mittel 0,245 je Lauf). Die erste Fassung der Fixture (ein Rechnungslauf mit 166 Zeilen,
alle Fehler lokal im Diff sichtbar) hatte beide Werkzeuge in allen zwölf Läufen bei 5 von 5
und kostete in zwei Messrunden 2,9645 USD; sie ist durch diese Fassung ersetzt. Zusammen:
6,8923 USD.

### Was das für die Abnahme heißt

Die Schwelle der Spec — deep-review findet im Mittel mindestens so viele der fünf wie
`/code-review` und Sonnet zusammen — liegt bei 5 von 5, weil schon die Vereinigung alle
fünf findet. deep-review kann auf `dr-seeded` also gleichziehen, nicht überholen. Auch in
dieser Fassung trennt die Trefferquote nur Sonnet (4,33) von `/code-review` (5,0); der
Diff mit rund 400 Zeilen und die Basis mit 1.384 Zeilen passen beide ganz in den Kontext, und
beide Werkzeuge lesen die Verträge in `base` ungefragt. Ein Vorsprung in der Präzision zeichnet sich
ebenfalls nicht ab: Was zunächst als zehn Fehlalarme je `/code-review`-Lauf gezählt wurde,
sind echte Fehler der Fixture (siehe oben). `/code-review` ist auf dieser Fixture in
Trefferquote und Präzision stärker als ein einzelner Sonnet-Lauf, der von denselben echten
Fehlern höchstens einen als Fehler einstuft.

## Was nicht gemessen wurde

**deep-review selbst** — die Skill ist noch nicht gebaut; ihre Läufe auf beiden Fixtures,
die Abschaltungen und der Vergleich mit dieser Basislinie folgen in Task 23.

**Eine Fixture jenseits des Kontextfensters** — beide Fassungen sind klein genug, dass ein
Agent alles lesen kann. Den Effekt, auf den die Spec zielt (eine Stelle liegt außerhalb
des Gelesenen, OverclaimBench), erzeugt keine von beiden. Nach der Vorgabe dieser Runde
nicht nachgeschärft.

**Tests im Lauf** — alle Läufe im Standard-Berechtigungsmodus; `permission_denials` ist
in 11 von 12 Läufen nicht leer: `python -m pytest`, `~/.claude/CLAUDE.md` und verkettete
Bash-Aufrufe bekamen keine Freigabe. Die Funde stammen aus dem Lesen, nicht aus
Ausführung.

**Die Stufe von `/code-review`** — ohne Angabe übernimmt das Kommando die zuletzt
getippte Stufe; welche das headless war, steht nicht in der Antwort. Andere Stufen sind
nicht gemessen.

**Kosten der Unteragenten** — `total_cost_usd` ist die Zahl der CLI. Ob sie Unteragenten
von `/code-review` vollständig enthält, ist nicht nachgeprüft; `modelUsage` nennt nur
`claude-opus-5-5`, `num_turns` steht bei 0.

**Streuung und Auswertung** — drei Läufe je Zelle. Die Zuordnung der Treffer lief per
Skript mit Nachprüfung am Text, die Einteilung der weiteren Funde in Code und Stil von Hand
durch den bauenden Agenten, ohne zweite Auswertung.
