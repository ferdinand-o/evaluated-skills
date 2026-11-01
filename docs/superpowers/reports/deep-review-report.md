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

## Nachmessung auf großen Repos (2026-11-01)

Die offene Lücke von oben — keine Fixture jenseits dessen, was ein Agent ganz liest — mit
echten Repos und drei etablierten Review-Werkzeugen nachgemessen. Skripte, Einbauten und
Grundwahrheit: `docs/superpowers/reports/review-bench/`.

**Werkzeuge.** `cr`: eingebautes `/code-review --max-findings all <Ziel>`; `eng`:
`/engineering:code-review <Ziel>` (Plugin engineering); `sp`: `requesting-code-review` aus
obra/superpowers (Unteragent mit `code-reviewer.md`, BASE/HEAD-SHA, Commit-Message als
Anforderung). Claude Code 2.1.316, headless, `--allowedTools "Bash(git:*)" Read Grep Glob`,
je Lauf ein frischer Klon, Timeout 1.800 s.

**Szenarien.** Jedes Repo ist ein frisches Git-Repo ohne Upstream-Historie.

| Szenario | Code | Ziel | Grundwahrheit |
| --- | --- | --- | --- |
| `py-diff` | pip 25.0 → 25.1, Vendor-Updates in die Basis verlegt | `base..HEAD`: 151 Dateien, +3.281/−816 | 6 eingebaut (P1–P6) + 2 echte Regressionen, die erst 25.1.1 behob (R1 `assert req.source_dir`, #13353; R2 `StringIO` auf Python ≤ 3.9.6, #13364) |
| `dl-diff` | DelphiMVCFramework 3.5.0 rc6 → rc7, nur `sources/` | `base..HEAD`: 39 Units, +1.683/−305; Basis 119k Zeilen | 6 eingebaut (D1–D6) |
| `dl-path` | rc7, ein Commit | 7 Units aus 2026 (Refresh-Token, RangeMedia, OIDC, JWKS, CSV, SSE, JWT.RSA), 5.308 Zeilen | 6 eingebaut (E1–E6) in Bestandscode |
| `py-path` | pip 25.1, ein Commit | `req/` + `operations/`, 5.460 Zeilen | 6 eingebaut (Q1–Q6) |

Die Einbauten sind Fehlerklassen, deren Vertrag an anderer Stelle steht: ein geteiltes
Modul-Dict ohne `copy()`, eine vendorte Bibliothek, die `TypeError` wirft, `()` aus
`packaging` als falsy, ein Resolver-Flag mit Folgen in `factory.py`, ein Cache-Schlüssel ohne
ein Argument; in Delphi `TObjectList.Extract` gegen Besitz, 1-basierte Strings vor einer
Sicherheitsprüfung in einer anderen Unit, Record-Wertkopie aus `TryGetValue`, `TDateTime` in
Tagen, `SetContentStream` mit Besitzübergabe, `UnixToDateTime(…, True)` gegen `Now`,
`@@IDENTITY` gegen Trigger. Ausgeführt wurde nichts: Den heruntergeladenen Code
startet diese Umgebung nicht, jeder Einbau ist am Code und an der Nutzung der Gegenstelle
belegt, R1 und R2 an den Upstream-Fixes.

### Trefferquote

Treffer heißt: richtige Datei und Stelle, Ursache sinngemäß. Vorauswahl per Skript, jeder
Treffer und jede Lücke am Text nachgeprüft (eine Korrektur: `dl-diff-eng-2` lobt die
Payload-Grenze, die D4 abschaltet, als korrekt — kein Treffer).

| Szenario | Lauf | Eingebaut | fehlt | Echte (R) | USD |
| --- | --- | --- | --- | --- | --- |
| `py-diff` | cr 1 | 5/6 | P2 | R1 | 1,19 |
| `py-diff` | cr 2 | 4/6 | P2, P4 | — | 0,93 |
| `py-diff` | eng 1 | 4/6 | P2, P4 | — | 1,10 |
| `py-diff` | eng 2 | 2/6 | P2, P4, P5, P6 | R1 als Prüfhinweis | 1,04 |
| `py-diff` | sp 1 | 4/6 | P2, P4 | — | 1,70 |
| `dl-diff` | cr 1 | 5/6 | D4 | | 2,00 |
| `dl-diff` | cr 2 | 5/6 | D1 | | 2,66 |
| `dl-diff` | eng 1 | 6/6 | — | | 1,94 |
| `dl-diff` | eng 2 | 4/6 | D1, D4 | | 1,87 |
| `dl-diff` | sp 1 | 5/6 | D1 | | 2,83 |
| `dl-path` | cr 1–3 | 6/6, 6/6, 6/6 | — | | 1,44 / 1,16 / 1,28 |
| `dl-path` | eng 1–3 | 6/6, 6/6, 6/6 | — | | 1,69 / 1,80 / 1,63 |
| `py-path` | cr 1 | 6/6 | — (Gedächtnis, siehe unten) | | 1,15 |
| `py-path` | eng 1 | 5/6 | Q4 (lokales pip als Vergleich) | | 2,05 |

Mittel je Werkzeug: `py-diff` cr 4,5, eng 3,0, sp 4,0 von 6; `dl-diff` cr 5,0, eng 5,0,
sp 5,0; `dl-path` cr und eng je 6,0. Vereinigung aller Läufe: `py-diff` 5/6 (P2 in keinem
der fünf Läufe), `dl-diff` 6/6. R2 fand kein Lauf.

**`py-path` zählt nicht.** `eng 1` las ohne Sperre das installierte pip 24.0 unter
`/usr/lib/python3/dist-packages` und verglich Zeile für Zeile; `cr 1` schreibt, es habe
„against upstream pip 25.1 as I remember it" verglichen. Bei einem so bekannten Projekt
misst ein Pfad-Review Erinnerung, nicht Prüfung. Danach sperrt `run.sh` `/usr`, `/opt`, die
Upstream-Klone und `git -C`; als Pfad-Szenario gilt `dl-path`, dessen Units 2026 entstanden
und dessen Stand (rc7, 2026-09-22) nach dem Wissensstand des Modells liegt. In den Diff-Läufen
fand sich in den Transkripten kein Zugriff außerhalb des Arbeitsklons.

### Gelesen, aber nicht erkannt

Aus den Transkripten (Hauptagent und Unteragenten): Stand die Zeile des Fehlers in einem
Werkzeugergebnis?

| Fehler | Zeile im Kontext | gefunden |
| --- | --- | --- |
| P2 `except (ValueError, LookupError)` | 5 von 5 Läufen | 0 von 5 |
| P4 `ignore_installed=False` | 5 von 5 | 1 von 5 |
| D1 `aRQLAST.Extract(lLimit)` | 5 von 5 | 2 von 5 |
| D4 `ParseFrame(LIOHandler, True);` | 3 von 5 | 3 von 5 — genau die drei, die sie gelesen haben |

Zwei Arten von Lücken also: D4 fehlt nur, wo die Aufrufstelle nie gelesen wurde (der Effekt
von OverclaimBench); P2, P4 und D1 fehlen, obwohl die Zeile im Kontext stand — der Vertrag
liegt in vendortem Code, im Resolver oder in der Besitzregel einer Basisklasse, und kein
Agent ist ihm nachgegangen.

### Weitere Funde

Nicht vollständig ausgewertet; zwei aus `py-diff` am Upstream-Code nachgeprüft, beide echt
und nicht eingebaut:

- `commands/list.py`: seit 25.1 hängt die Kopfzeile „Location", „Installer" vor „Editable
  project location" an, die Zeilen in anderer Reihenfolge — `pip list -v` mit einem
  editierbaren Paket verschiebt die Spalten. In 25.3 unverändert (`cr 1`).
- `utils/logging.py:287`: `global _stdout_console, stderr_console` statt `_stderr_console`,
  neu in 25.1, ruhend, weil niemand `get_console(stderr=True)` aufruft (cr, eng, sp).

Auf `dl-path` melden alle sechs Läufe unabhängig dieselben drei Zusatzfunde: `LKey` aus
`FKeys` (besitzt seine Werte) wird nach Verlassen des Locks benutzt, während ein paralleler
`FetchKeys` die Schlüssel freigibt; `JWTSignatureToDER` prüft die Signaturlänge nicht;
`TMVCSSEWriter.Send` trennt `data` nur an LF, CR bleibt Zeilenende nach SSE-Spezifikation.
Am Code nachvollziehbar, nicht ausgelöst.

### Kosten

18 Läufe, 29,43 USD (Mittel `py-diff` 1,19, `dl-diff` 2,26, `dl-path` 1,50 je Lauf). Je
Lauf 2–7 Minuten.

### Was das für Spec 26 heißt

- **Pfad-Review bis rund 5k Zeilen ist kein Problem der etablierten Werkzeuge.** Auf
  unbekanntem Bestandscode fanden `/code-review` und engineering in allen sechs Läufen alle
  sechs Fehler. Ein Inventar mit Paketen bringt dort keine Trefferquote, die fehlt.
- **Große Diffs verlieren Funde.** Bei 4.100 geänderten Zeilen in 151 Dateien verfehlt ein
  einzelner Lauf ein bis vier von sechs, bei 2.000 Zeilen null bis zwei. Die Lücken sind
  stabil (P2 nie, P4 einmal) und meist keine Lesefrage: Die Zeile stand im Kontext, der
  Vertrag lag woanders. Ein Inventar, das nur Abdeckung erzwingt, schließt D4, nicht P2.
- **Zwei Läufe vereinigt** bringen `py-diff` auf 5/6 und `dl-diff` auf 6/6 — zum doppelten
  Preis, ohne neue Skill.
- **Vorschlag:** Spec 26 bleibt pausiert. Prüfenswert, bevor gebaut wird: derselbe
  `py-diff` mit `/code-review` je Paket statt als Ganzes (rund vier Läufe, um 5 USD) — trifft
  die Aufteilung P2 und P4, ist der Kern von Spec 26 (Pakete je Einheit) belegt; trifft sie
  sie nicht, braucht es die Linse „Vertrag der Gegenstelle", nicht das Inventar. Für Spec 27
  stützt die Messung kleine Prüfpunkt-Bereiche: Die Trefferquote fällt mit der Diffgröße.

## Was nicht gemessen wurde

**deep-review selbst** — die Skill ist noch nicht gebaut; ihre Läufe auf beiden Fixtures,
die Abschaltungen und der Vergleich mit dieser Basislinie folgen in Task 23.

**Eine Fixture jenseits des Kontextfensters** — beide Fassungen sind klein genug, dass ein
Agent alles lesen kann. Den Effekt, auf den die Spec zielt (eine Stelle liegt außerhalb
des Gelesenen, OverclaimBench), erzeugt keine von beiden. Nach der Vorgabe dieser Runde
nicht nachgeschärft; nachgeholt mit echten Repos im Abschnitt „Nachmessung auf großen
Repos". Dort offen: `sp` nur ein Lauf je Diff-Szenario, `py-diff` und `dl-diff` je zwei
Läufe für `cr` und `eng` (Budget), keine Fassung ohne Einbauten, also keine Präzision.

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
