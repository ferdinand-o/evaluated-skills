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

### Entscheidungsexperiment (2026-11-02)

Frage: Fehlen P2 und P4 wegen der Diffgröße oder weil niemand die Gegenstelle prüft? Zwei
Varianten, nur `/code-review --max-findings all`, 6 Läufe, 5,01 USD.

- **a) Aufteilen:** derselbe Endstand, Prüfbereich `mid..HEAD` je Paket — `cli+commands+req`
  (591 Zeilen), `models+index+resolution+wheel_builder` (602), `network+metadata+utils+operations+Rest`
  (651); Tests und Doku nicht geprüft (keine Einbauten).
- **b) Gegenstelle:** ganzer Diff, `--append-system-prompt` mit dem Auftrag, je geänderter
  Zeile die Gegenstelle nachzuschlagen — auch vendorten Code, Basisklassen, Framework — und
  deren Vertrag zu prüfen (Ausnahmen, Randwerte, Besitz, Wirkung eines Flags).

| Variante | Lauf | Eingebaut | Echte | USD |
| --- | --- | --- | --- | --- |
| a) `py-diff` in 3 Paketen | je 1 | P5 · P3 P6 · P1 = 4/6 | R1, **R2** | 0,56 + 0,36 + 0,50 = 1,43 |
| b) `py-diff` ganz | 1 | 4/6 (P2, P4 fehlen) | — | 1,16 |
| b) `py-diff` ganz | 2 | 4/6 (P2, P4 fehlen) | — | 0,93 |
| b) `dl-diff` ganz | 1 | **6/6** | | 1,48 |

- **Aufteilen** findet so viel wie ein ganzer Lauf, ist billiger und fand als einziger Lauf
  der ganzen Messung R2 (`StringIO` ohne `.encoding`, das `compileall` auf dem Fehlerpfad
  braucht — die Regression, die 25.1.1 behob). P2 und P4 fehlen auch im Paket mit 591 Zeilen.
- **Die Anweisung allein** ändert auf `py-diff` nichts. Auf `dl-diff` fand der Lauf D1
  (Besitz bei `TObjectList.Extract`, in der Anweisung genannt), das 3 von 5 Läufen ohne sie
  verfehlten — ein Lauf, kein Beleg.
- **Die Ursache für P2 und P4 steht in den Transkripten:** Kein einziger der acht Läufe auf
  `py-diff` und seinen Paketen hat `src/pip/_vendor/dependency_groups` geöffnet, auch nicht
  mit der Anweisung. Den Resolver (`resolvelib/factory.py`, `candidates.py`) las nur `cr 1`
  ausführlich — der einzige Lauf, der P4 fand. Die Lücke ist eine nicht geöffnete
  Gegenstelle, und eine Bitte im Prompt öffnet sie nicht.

### Prototyp: Gegenstellen mechanisch sammeln (2026-11-02)

`review-bench/counterparts.py` (Stdlib, `ast`, ohne Import des Zielcodes) geht über jede
geänderte Zeile des Bereichs und schreibt je Stelle: die erreichte Definition (auch in
`_vendor`, aufgelöst über die Importe der Datei und voll qualifizierte Modulpfade), die
`raise`-Stellen der Definition transitiv im selben Modul (Tiefe 2); für eine geänderte
`except`-Klausel die Ausnahmen aller Aufrufe im `try`-Block; für ein geändertes
Schlüsselwort-Argument seinen Weg durch die Gegenstellen bis zu den Bedingungen, die es
prüfen (Tiefe 4). Keine Auswahl nach Verdacht: Paket 1 ergibt 38 Stellen, 28,7 KB; der
ganze `py-diff` 87 Stellen, 49 KB. Für P2 steht dort `except (ValueError, LookupError)`
neben „`DependencyGroupResolver.resolve` wirft … TypeError" mit Zeilen im vendorten Code,
für P4 der Weg `make_resolver → Resolver → Factory → factory.py:127: if not ignore_installed`.
Übergabe als `--append-system-prompt` mit dem Auftrag, den Block an jeden Unteragenten
weiterzugeben. 4 Läufe, 3,27 USD.

| Bereich | ohne Kontext | mit Kontext, Lauf 1 | mit Kontext, Lauf 2 |
| --- | --- | --- | --- |
| Paket 1 (`cli+commands+req`, 591 Zeilen; enthält P2, P4, P5) | P5 | **P2**, P5 | **P4**, P5 |
| ganzer `py-diff` (4.097 Zeilen) | 2–5 von 6 in 7 Läufen, P2 nie, P4 einmal | 4/6 (P2, P4 fehlen) | 4/6 (P2, P4 fehlen) |

- **Paket plus Gegenstellen** findet erstmals P2 (zuvor 0 von 8 Läufen auf diesem Code) und P4; die beiden
  Läufe zusammen finden alle drei Fehler des Pakets. Je Lauf einer von beiden — die
  Streuung bleibt, zwei Läufe sind kein Mittelwert.
- **Ganzer Diff plus Gegenstellen** bringt nichts: Bei 87 Stellen und 4.100 Zeilen geht der
  Hinweis unter. Der Kontext wirkt nur, wenn der Bereich klein genug ist.
- Nur Python; für Delphi gibt es den Sammler nicht.

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
- **Nach dem Entscheidungsexperiment:** Spec 26 in der Form des Entwurfs (eigene
  Such-Pipeline, Inventar, Nonce) wird nicht gebaut. Was fehlt, ist schmaler und mechanisch:
  große Bereiche in Pakete schneiden und `/code-review` je Paket laufen lassen (billiger,
  fand R2), und die Gegenstellen der geänderten Aufrufe — Definitionen der aufgerufenen
  Funktionen samt vendortem Code, ihre `raise`-Stellen, Besitz- und Flag-Verträge — per
  Skript sammeln und dem Review mitgeben, statt darum zu bitten. Der Prototyp zeigt: Erst
  beides zusammen — Paket und Gegenstellen — findet P2 und P4 (je einmal in zwei Läufen).
  Für Spec 27 stützt die Messung kleine Prüfpunkt-Bereiche.

## Bau (ab 2026-11-02)

### Prüfpunkt 1 (vor Task 3, nach Task 2)

`/code-review --max-findings all` über Task 2 (525 Zeilen): 17 Funde, Fix-Runde 1 behob alle;
Review des Fixes: 10 Funde, Fix-Runde 2 behob alle; Review des zweiten Fixes: 12 Funde.
Nach der Regel von subagent-dev (zwei Fix-Runden) entschied der Nutzer: eine dritte, schmale
Runde für die drei echten (Delphi-Testregel als Segmentregel, Wurzel-Commit mit `root` und
Hilfscommits, Quelldatei mit Nicht-UTF-8-Pfad mit eigenem Grund), die übrigen neun bleiben
offen und gehen nach known-limits:

- Einzelner Bereich `X` wird beim Wiedereinlesen über die Merge-Basis zu `Span(fork, X, fork)`;
  bei Criss-Cross-Historie liefert `git log` dann andere Commit-Messages als `BASIS..X`.
- `_toplevel` meldet jeden Git-Fehler als „kein Git-Repository" (auch „dubious ownership").
- `git rev-parse --show-toplevel` und die Bereichsprüfung laufen je Plan zweimal.
- Temp-Datei in `write_json` wird außerhalb des `try` angelegt; ein Abbruch genau dazwischen
  hinterlässt eine `.tmp`-Datei.
- Die escapte Form eines Nicht-UTF-8-Pfads ist nicht eindeutig gegen einen echten Pfad mit
  Backslash-Folge.
- Der Kommentar zu `DIFF_PATHSPEC` verschweigt, dass subagent-dev aus seinem Arbeitsordner
  zählt, deep-review aus der Repo-Wurzel.
- `test_f15` prüft nur UTC-Eingaben, nicht mehr die Sommerzeit-Reihenfolge.
- `new_run_id` lehnt eine korrekte Ortszeit mit Offset ab, statt sie nach UTC umzurechnen.

### Prüfpunkt 2 (nach Task 3, C5)

`/code-review` über Task 3 und Spec-Nachträge (437 Zeilen): 12 Funde, Fix-Runde 1 behob alle
(Datei/Ordner-Kollision über Paketgrenzen, Sperre für `plan.json`, Bereich nach `cleanup`,
Arbeitsbaum-Vergleich über git statt Eigenbau). Review des Fixes: 12 Funde; nach der Linie
aus Prüfpunkt 1 kamen nur die sechs, die hängen oder falsch melden, in Runde 2 (verwaiste
Sperre, HEAD-Cache, Index-Kopie mit frischem mtime, fehlender Index, unhashbare Notiz); offen
für known-limits:

- Die Sperre umfasst die ganze Git-Arbeit eines Pakets; parallele Vorbereitung vieler Pakete
  eines Laufs läuft nacheinander und kann `LOCK_WAIT` (600 s) erreichen. deep-review bereitet
  Pakete nacheinander im Hauptkontext vor.
- Dateien mit `assume-unchanged` oder `skip-worktree` (Sparse-Checkout) meldet der
  Arbeitsbaum-Vergleich nicht als abweichend.
- `_tree_entries` prüft Mitgliedschaft in einer Liste (O(n·m)).
- `_refs_hold` und `cleanup` lesen Refs mit doppeltem Code.
- `ARG_CHUNK_CHARS` rechnet feste Argumente, Quoting und UTF-16-Länge unter Windows nicht ein.

### Prüfpunkt 3 (vor Task 5, C1 und C5)

`/code-review` über Task 4 (785 Zeilen): 11 Funde, Fix-Runde 1 behob alle (zwei Aufrufe auf
einer Zeile, `.PY` still übergangen, unlesbare Paketdateien ohne Hinweis, Kappung über den
ganzen Block, Performance). Review des Fixes: 13 Funde; in Runde 2 die sieben mit falschem
Inhalt (Ausschnitt bei Latin-1 und BOM verschoben, `render_block` ohne Kennzeichnung für
andere Sprachen, falsche Symlink- und Grund-Hinweise, Zählung bei `Path`, gleiche Überschriften);
offen für known-limits:

- Der Index hält die Quell-Bytes aller Python-Dateien des Repos im Prozess-Cache (Speicher bei
  großen vendorten Bäumen).
- Mehrzeilige Rumpf-Anweisungen zeigen im Weg die erste Quellzeile samt Kommentar.
- `INDEX_CACHE_SIZE = 1`: Wechsel zwischen zwei Zielen baut den Index jedes Mal neu.
- `_is_python` und `_has_collector` prüfen dasselbe doppelt.
- `write_counterparts` löst den Bereich und den Index ein zweites Mal auf.
- `_render` hat einen Sonderzweig für den Qualitätsfokus.

### Prüfpunkt 4 (nach Task 5, C5: Delphi-Scanner)

`/code-review` über Task 5 (1.345 Zeilen): 20 Funde, Fix-Runde 1 behob alle (`&End` als
Schlüsselwort, `<T: record>` als Record, klammerlose Aufrufe, Sichtbarkeit geschachtelter
Routinen, Unit-qualifizierte RTL-Aufrufe, Überladungen, `{$IFDEF}`, `TObjectQueue/Stack`,
Sammler-Tabelle). Review des Fixes: 14 Funde; elf mit falschem oder stillem Ergebnis in Runde 2;
offen für known-limits:

- `enclosing()` sucht linear über alle Routinen und läuft je Kandidat — in großen Units etwa
  quadratisch.
- `inherited Create` ruft `_ownership` doppelt.
- `COUNTERPART_SUFFIXES` ist tot, `_is_python`/`_is_delphi` doppeln `COLLECTORS`, `local_type`
  hat einen ungenutzten Default.

Was der Scanner bewusst nicht kann (Bericht der Fix-Runde 1): kein Parser, keine Defines (immer
der erste Zweig, `{$I}` nicht gelesen); keine Typinferenz für Ausdrücke, Funktionsergebnisse,
`with`, Indexer; Überladungen nicht nach Argumenttypen; `raise` nur innerhalb der Unit; RTL nur
über die feste Tabelle `OWNERSHIP_RTL`.

**Lessons für subagent-dev:** (1) Agent-Worktrees starten auf `main`, nicht auf dem
Arbeitsbranch; jeder Agent musste die Basis selbst zurücksetzen — der Dispatch nennt sie seither
ausdrücklich. (2) `fix-task` nimmt nur die Dateien der Funde in die Allowlist, nicht die
Testdatei, obwohl die Akzeptanz „mit Test belegt" verlangt; von Hand ergänzt. (3) Das Review
des Fixes mit `--max-findings all` findet auf neuem Code jede Runde neue Randfälle; nach zwei
Runden liefen die Funde von „Absturz" zu „Kommentar ungenau" — die Grenze von zwei Runden
trägt.

### Prüfpunkt 5 (nach Task 6, C5: Datei-Schlüssel und `--since`)

Task 6 mit Sonnet: `verify` PASS, Vertrag geprüft (0 von 5 Steps fehlen), 1.721 Tests grün.
`/code-review` über 469 Zeilen ergab 12 Funde. Der wichtigste: Der Schlüssel aus Inhalt am ZIEL
plus Gegenstellen sagt nicht, ob der frühere Lauf alle Änderungen des neuen Bereichs gesehen
hat. Ein Lauf über `t1..t2` hätte eine Datei für `t0..t2` freigegeben, auch gelöschte Dateien
mit anderem Inhalt. Fix-Runde 1 bekommt dafür eine Abdeckungskette (`base_blob`/`target_blob`
je Datei): Übernommen wird nur, wenn sich die Kette über die angegebenen Läufe bis zur neuen
Basis schließt. Außerdem in Runde 1: Profil-Abgleich, `plan_since` nur auf frischem Lauf, Gleichstand
der Lauf-IDs, Symlinks, gemeinsames `_pack`, Validierung früherer Pläne, `test_f03` wieder streng.

Offen für known-limits:

- `plan` sammelt die Gegenstellen über den ganzen Bereich, um die Schlüssel zu bilden;
  `counterparts` sammelt je Paket erneut. Damit kostet das Sammeln etwa doppelt, und ein
  Sammelfehler bricht schon `plan` ab.

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
