<!-- skill: deep-review | schema: 1 | generated: von Hand nach docs/superpowers/plans/2026-10-30-deep-review.md, Task 1 -->
# deep-review — Abschlussbericht

Gebaut nach `specs/Spec 26 – deep-review.md` und
`docs/superpowers/plans/2026-10-30-deep-review.md`. Begonnen mit Task 1 (Messfixture und
Basislinie, 2026-10-30); gebaut ist die Skill bis Task 15 (SKILL.md, Plugin-Eintrag,
Projekt-Kopie; Abschnitt „Bau“). Dieser Bericht hält fest, woran sie sich in der Abnahme
(Task 16) messen lassen muss.

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

Review des Fixes: 11 Funde. In Runde 2 kommen drei mit falschem Ergebnis: Eine Kette aus mehreren Läufen verlor
die Funde der älteren Glieder. Ein Symlink über ein Verzeichnis-Symlink löste nicht auf. Ohne
Dateimodus galten Symlink und Datei mit gleichem Inhalt als gleich. Ebenfalls offen für known-limits:

- Ein früherer Plan wird vor dem Fokus- und Profilfilter streng geprüft. Ein kaputter oder alter
  Plan in `--since` bricht deshalb den ganzen Folgelauf ab, auch wenn er ohnehin übergangen würde.
  Das ist ein lauter Fehler, kein stilles Ergebnis.
- `apply_since` nimmt `PACKET_SIZE`, wenn dem Plan `packet_size` fehlt. Das trifft nur
  handbearbeitete Pläne, denn `build_plan` schreibt das Feld immer.
- `_check_fresh` erkennt einen schon angewandten `--since` am Text in `_meta.generated`. Sauberer
  wäre ein eigenes Feld.
- Doppelte Arbeit: `ls-tree` am ZIEL läuft für Schlüssel und Blobs zweimal. Die Prüfung
  „kann nicht auf sich selbst folgen“ steht zweimal, die Blob-Prüfung in `apply_since` doppelt.
  `split_range` reicht einen fertigen `Span` durch.
- Gibt es mehrere Abdeckungsketten, nimmt `apply_since` die kürzeste, bei gleicher Länge die
  über jüngere Läufe; Funde aus Läufen außerhalb dieser Kette werden nicht übernommen.

Fix-Runde 2 behob die drei (`reused_chain` mit den Funden aller Kettenglieder, Auflösung Teil
für Teil mit `LINK_MAX_HOPS = 40`, Marken als `<mode>:<sha>`); 1.731 Tests grün.

**Lesson für subagent-dev:** Die Testdatei von Hand in die Markdown-Allowlist von `fix-task.md`
einzutragen reicht nicht. `verify` liest den JSON-Block am Ende, also muss sie auch dort
stehen. Sonst meldet `verify` FAIL wegen der Testdatei, obwohl der Fix sich an die Allowlist
hielt. Das spricht dafür, dass `fix-task` die Testdatei selbst aufnimmt (Lesson 2 aus Prüfpunkt 4).

### Prüfpunkt 6 (nach Task 7, C1 und C5: record, merge, audit, CLI)

Task 7 mit Opus: `verify` PASS. Die Vertragsprüfung meldet 1 von 5 Steps fehlend: Die volle
Suite stand nicht im test-first-Log. Nach dem Merge liefen 1.738 Tests grün, das belegt den Step.
`/code-review` über 1.113 Zeilen ergab 20 Funde. Der schwerste: Ein Fund in einer Datei mit
Leerzeichen im Pfad oder mit einer Zeilenangabe wie `12 - 14` konnte nie als „im Bericht“
zählen, `audit` wäre nie vollständig geworden. Fix-Runde 1 nimmt 19 Funde auf (Zeilen beim
`record` normalisieren, UTF-8 für stdin/stdout, BOM, Funde zu Gegenstellen-Dateien bei
`--since`, eine strenge Definition für angenommene Ergebnisse, `merge` nicht mehr transitiv,
Kopfzeile mit allen fünf Feldern, Berichtslänge `REPORT_BASE_LINES` plus eine Zeile je Fund).

Offen für known-limits:

- `audit` liest den Bericht mit regulären Ausdrücken aus freiem Markdown. Ein anderer Gedankenstrich,
  Fettdruck oder eine Tabellenzeile statt der Fundzeile ergibt einen falschen `report_mismatch`.
  Sauberer wäre, wenn das Skript die datentragenden Zeilen selbst schreibt. Die Zahlen in der
  Pakettabelle prüft `audit` nicht. Das gehört zur Vorlage aus Task 11.

Fix-Runde 1 ergab 1.753 Tests grün. Das Review des Fixes meldete 12 Funde. Davon gehen sechs
mit falschem Ergebnis oder Absturz in Runde 2:

- Eine Zeile wie `Fazit — vollständig` galt als Fundzeile, die Behauptung wurde nie geprüft.
- Gebeugte Formen („vollständige Abdeckung“) rutschten durch.
- Ehrliche Verneinungen („**nicht** vollständig“) galten als Behauptung.
- Funde zu Dateien außerhalb des Pakets wanderten über mehrere `--since`-Läufe weiter, ohne
  Prüfung der Datei selbst.
- stdin mit BOM oder ohne stdin.
- Überlappende Spannen beim `merge`.

Ebenfalls offen für known-limits:

- Pläne, die vor diesem Fix geschrieben wurden und übernommene Funde mit frei formulierter
  Zeilenangabe enthalten („12, 14“), sind jetzt ein `KitError` für `merge`, `audit` und
  `--since`. Das ist ein lauter Fehler, und solche Pläne gibt es nur aus dem Bau.
- `_meta.generated` hält `--report`/`--soll-file` repo-relativ fest, aufgelöst wird aber
  gegen das Arbeitsverzeichnis. Das notierte Kommando wiederholt sich nur aus der Repo-Wurzel
  gleich.
- `_line_span` parst die normalisierte Zeile ein zweites Mal. `_checked_plan` gibt
  `file_keys` doppelt zurück.

Diese drei Punkte decken die übrigen sechs Funde ab: Die beiden Aufräum-Funde stehen zusammen
im dritten. Der Vorschlag, Außer-Paket-Funde je eigener Datei zu führen, ging in die Lösung
von Runde 2 ein.

Ergebnis von Fix-Runde 2: Die sechs oben genannten Funde sind behoben. Übernommene Einträge
tragen jetzt `outside` mit `{finding, packet_files, file_blob}` und werden bei jedem Hop neu
geprüft. 1.759 Tests grün. Daraus ergibt sich eine neue Grenze: Außer-Paket-Funde aus Plänen
von vor Runde 2 werden nicht weitergegeben, weil ihr Datei-Stand fehlt. Das betrifft nur Läufe
aus dem Bau.

**Lesson für test-first/subagent-dev:** `tdd_log.py green` nimmt nur einen Test an, der vorher
rot war. Den Lauf der vollen Suite nach allen Zyklen kann man daher nicht als `green`
protokollieren. Der Agent wich auf `refactor` aus. Deshalb meldete die Vertragsprüfung von
Task 7 „volle Suite fehlt“. Der Step „Grün sehen: volle Suite“ und das Log passen nicht zusammen.

### Task 8, Task 9 und Prüfpunkt 7 (vor Task 10, C1 und C5)

Task 8 (Sonnet) hat `fix-task` beigebracht, die `findings.json` von deep-review zu lesen; Task 9
(Opus) hat `references/packets.md` und `references/counterparts.md` geschrieben. Beide haben
`verify` bestanden. Bei Task 8 meldet die Vertragsprüfung wieder „volle Suite nicht im Log“
(Lesson oben); nach dem Merge waren 1.761 Tests grün. Der Haiku-Agent der Vertragsprüfung rief
einmal `interrupt_session` auf, obwohl der Auftrag das ausschloss. Der Aufruf wurde abgelehnt.

Task 9 nennt 13 Stellen, an denen das Skript vom Spec abweicht. Die References beschreiben das
Skript. Der Spec muss nachgezogen werden, das geschieht vor der Abnahme in Task 16. Die
wichtigsten Abweichungen:

- `plan` hat kein `--run`. Ein Lauf wird über `counterparts`, `record`, `merge` und `audit`
  fortgesetzt.
- Die Paket-Bereiche baut `counterparts`.
- `s1` bekommt beim Wurzel-Commit und nach `--since` mit Übernahme doch Hilfscommits.
- `--since` hat Abdeckungskette, Fokus- und Profilgleichheit und `outside`.
- `merge` ist nicht transitiv.
- `audit.json` hat zusätzlich `coverage`.
- Der Anti-Zeremonie-Fall zählt die Kopfzeile nicht mit.
- Der Delphi-Sammler kann mehr als im Spec beschrieben.

`/code-review` über 571 Zeilen ergab 11 Funde. Die wichtigsten: `fix-task` nahm bei
zusammengelegten Funden nur die erste Zeile und mischte die Szenarien. Jedes Objekt mit
`findings`, auch ein einzelnes `results/p1.json`, galt als ganzer Lauf. `file: null` wurde zum
Allowlist-Eintrag. Den Report-Fund (Zählung in Prüfpunkt 6) habe ich selbst berichtigt. Die
übrigen sieben gehen in Fix-Runde 1.

Fix-Runde 1 ergab 1.766 Tests grün. Das Review des Fixes meldete 12 Funde. In Runde 2 kommen
die mit Absturz oder falschem Ergebnis:

- Eine verdicts-Zeile mit `reason: null` oder ohne `id` führte zu Traceback bzw. unklarer
  Meldung.
- `./src/a.py`, `src` oder `src/*` erweiterten die Allowlist.
- Ein bloßes `{"findings": …}` und `summary: null` wurden neu abgewiesen.
- Zeilenangaben wie `abc` oder `-5` landeten ungeprüft in der Task-Datei.

Offen für known-limits:

- Hat ein eingerücktes `findings.json` einen Syntaxfehler, nennt die Meldung die Position aus
  dem jsonl-Versuch (Zeile 1), nicht die echte.
- `fix-task` kopiert Zeilen- und Pfadregeln aus `review_kit.py` (`FIX_LINE_RE`, `_line_span`,
  `_repo_path`). Zwei Tier-1-Skripte aus verschiedenen Skills teilen keinen Code. Die Kopien
  können auseinanderlaufen.
- Ein Fund aus `findings.json` mit nur einer Quelle wird auch in der Quellenform dargestellt,
  die Zeile steht dann doppelt.

### Task 10, Task 11 und Prüfpunkt 8 (C5)

Task 10 (review-brief.md, delphi.md) und Task 11 (Berichtsvorlage mit `test_report_template`)
liefen mit Sonnet, `verify` PASS. Der Commit von Task 10 trug „Claude Sonnet 5.5“ statt der
Attributionsvorgabe der Sitzung. Ich habe ihn vor dem Merge im lokalen Commit berichtigt, seither
nennt jeder Dispatch die Zeilen wörtlich. Beim Suite-Lauf nach dem Merge von Task 11 startete
der Container neu. Merge und Aufräumen waren schon durch; der wiederholte Lauf ergab 1.771 grün.

`/code-review` über 504 Zeilen ergab 18 Funde. Die wichtigsten:

- Eine korrekt ausgefüllte Vorlage konnte an der Längengrenze von `audit` scheitern: 18 feste
  Zeilen plus eine je Grund unter „Nicht geprüft“.
- Platz für `notes`, „Gegenstellen nicht gesammelt“ und die übernommenen Dateien fehlte.
- `/security-review` prüft den aktuellen Branch, nicht den Planbereich.
- In delphi.md stimmte der Zeitpunkt der Freigabe bei `as`-Interface-Temporären nicht, und es
  standen zwei falsche RTL-Namen (`TStringList.Items`, `UTCNow`) darin.
- Das Extract-Beispiel glich dem geplanten Eval-Szenario.

Ein Fund (Runlog-Zeile für Task 11) war beim Review schon behoben. Die übrigen gehen
zusammengefasst als F1–F12 in Fix-Runde 1.

Fix-Runde 1 ergab 1.776 Tests grün. Die Vorlage hat jetzt eine Zeile für „Nicht geprüft“, eine
für Hinweise und eine für übernommene Dateien; ohne Funde und bei `split: false` sind es 20
Zeilen. Das Review des Fixes meldete 18 Funde. In Runde 2 kommen die mit falschem Ergebnis:

- Der Scope-Abgleich für `/security-review` lag in beiden Richtungen falsch.
- Der Sammler kennt `ExtractPair` nicht, und `doOwnsKeys` fehlte.
- `audit` prüfte die Zeilen „Hinweise“ und „Übernommen“ nicht.
- „Nicht geprüft“ verbarg übersprungene Quelldateien.
- Eine Payload-Datei mit BOM wurde abgewiesen.

Offen für known-limits:

- Die Doku-Funde zu review-brief.md und delphi.md haben keine Tests, die alten Fehler könnten
  unbemerkt zurückkommen.
- Die Vorlage nennt die Grenzwerte (`SPLIT_AT`, `PACKET_SIZE`) nicht, obwohl packets.md das
  verspricht.
- Die Vorlage nennt `REPORT_BASE_LINES (20)` als Zahl, ohne dass ein Test sie gegen die
  Konstante prüft.
- Ein Test-Block wiederholt einen anderen, und in delphi.md sind zwei Zeilen falsch umbrochen.
- Der Werkzeugname „Review ohne /security-review“ steht noch nicht im Spec; er wird beim
  Nachziehen des Specs aufgenommen.

Fix-Runde 2 behob die fünf. `audit` prüft jetzt die Zeilen Hinweise und Übernommen. Reine
Kommentarzeilen zählen nicht zur Längengrenze. `DELPHI_RELEASES` kennt `ExtractPair`,
`ExtractKey` und `ExtractValue`. 1.780 Tests grün. (`ExtractKey`/`ExtractValue` sind in
Prüfpunkt 9 wieder entfernt worden, weil sie keine belegten RTL-Methoden sind.)

### Task 12, Task 13 und Prüfpunkt 9 (C5)

Task 12 hat sechs Evals und die Fixtures `dr-split` (469 Zeilen in drei Verzeichnissen),
`dr-contract` und `dr-delphi` gebaut. `test_evals_and_fixtures` spielt jeden Eval mechanisch
durch (plan, counterparts, record mit `[]`, merge, Bericht, audit, cleanup) und prüft die
Assertions gegen die echte Ausgabe. Alle Muster der Spec treffen unverändert.

Das Delphi-Formatbeispiel in `counterparts.md` zeigte genau das Muster von Eval 4. Ich habe es
selbst auf `TObjectDictionary`/`ExtractPair` umgestellt (`dbd13b7`).

Task 13 hat die Nachbarn eingepflegt: Spec 00, Spec 27, README, checkpoints.md und die
Rückverweise in review-context, debug-ledger und test-first.

Dabei kam ein Bruch der Schnittstelle zutage: `--since` übernahm nur aus Läufen mit gleichem
Profil. Die Zwischen-Prüfpunkte laufen aber mit `checkpoint`, der finale meist mit `standard`.
Der finale Prüfpunkt hätte also alles neu reviewt. **Entscheidung:** Nach Spec 26 ist
`checkpoint` „wie standard, plus Soll“. Ein `standard`-Plan übernimmt daher aus `standard`
und `checkpoint`, ein `checkpoint`-Plan nur aus `checkpoint`.

`/code-review` über 521 Zeilen ergab 12 Funde. In Fix-Runde 1 kommen:

- die Profil-Regel;
- `ExtractKey`/`ExtractValue` werden wieder entfernt, sie sind keine belegten RTL-Methoden;
- die Nachprüfung eines Fixes läuft ohne `--since` über die Fix-Commits, sonst kämen die Funde
  unberührter Dateien zurück;
- das Profil des finalen Prüfpunkts steht so, wie `checkpoint.json` es meldet;
- der Ersatzweg `/code-review` in subagent-dev bekommt die richtige Eingabe für `fix-task`;
- in Spec 27 standen unter „Next steps“ noch Sätze, die Spec 26 „pausiert“ nannten.

Zwei Funde („deep-review ist installiert“ in README und Spec 27) erledigt Task 15. Ein Fund
war schon behoben.

Offen für known-limits:

- `--since` kann Funde zurückbringen, deren Fix in einer anderen Datei landete. Der
  Hauptagent gleicht übernommene Funde gegen die Fix-Runden ab.
- `plan_to_tasks.py` liest `verdicts.jsonl` weiter, der Spec wollte es aus Docstring und
  `--help` streichen (Spec-Nachzug).
- `EVAL_RUNS` im Test doppelt den Fixture-Namen aus `evals.json`, und Fixtures werden mehrfach
  gebaut.
- Die Runlog-Zeile zu Prüfpunkt 8 zählt „5 von 18“ für Runde 2. Gemeint sind fünf Funde aus
  dem Review des Fixes, das wieder 18 meldete.

Fix-Runde 1 ergab 1.781 Tests grün; `sync --check` und lint-spec waren sauber. Die Regel für
das Profil: `SINCE_PROFILES`. Bei der Doku zeigte sich: Der finale Prüfpunkt meldet immer
`standard`, auch wenn C5 oder rote Tests auf ihn fallen, denn `PROFILES` ist geordnet und
`standard` steht oben. Er übernimmt trotzdem aus den `checkpoint`-Läufen. Der Fix-Pfad ruft
`mark` je Lauf auf, erst für den Prüfpunkt, dann für die Nachprüfung, damit sich die Kette am
finalen Prüfpunkt schließt.

Das Review des Fixes meldete 11 Funde. Fünf davon gehen in Runde 2:

- Die Nachprüfung ohne `--since` übersah den Aufrufer, der den Fund trug. Ein Fix nur an Tests
  ließ `plan` scheitern, ohne Lauf-ID für `mark`. Der Bereich geht deshalb zurück auf
  `<Basis>..HEAD` mit `--since`. Funde, die laut `fix-task.md` behoben sind, verwirft der
  Hauptagent.
- `findings.json` nannte bei übernommenen Funden nur den jüngsten Lauf, nicht den, der sie
  meldete.
- Das Profil `checkpoint` lief auch ohne `--soll-file`, und packets.md nannte es fälschlich
  eine „Obermenge“.
- Für das Soll der Nachprüfung galten zwei Regeln, und `fix-task.md` wird jede Runde
  überschrieben.
- `DELPHI_RELEASES` fehlten `Delete`, `Clear`, `ExtractItem`, `Dequeue` und `Pop`.

Offen für known-limits:

- Der Test der gemischten Kette prüft nur `reused_chain`, nicht die vereinigten Funde.
- Der F2-Test prüft nicht, dass `ExtractKey` weiter als gewöhnlicher Aufruf gesammelt wird.
- `ExtractAt` ist nicht aufgenommen, weil unbelegt ist, ab welcher RTL-Version es die Methode
  gibt.

Fix-Runde 2 hat die fünf Funde behoben, danach liefen 1.786 Tests grün. Übernommene Funde tragen
jetzt `run`, den Lauf, der sie gemeldet hat, und `findings.json` nennt diesen Lauf in
`sources[].reused_from`. `plan --profile checkpoint` verlangt `--soll-file`. Ein Fix, der nur
Tests ändert, scheitert mit dem wiederhergestellten Bereich nicht. Alle Dateien werden
übernommen, und es entsteht ein normaler Lauf. `--run none` bleibt für den echten Fall „nichts zu
reviewen“.

### Task 14, Task 15, Spec-Nachzug und Prüfpunkt 10 (C5)

Task 14 (Sonnet) hat known-limits um den Abschnitt `## deep-review` mit 56 Grenzen in acht
Themen erweitert. Was im Code inzwischen behoben ist, hat er weggelassen. Parallel dazu hat ein
Opus-Agent Spec 26 an den Bau nachgezogen (lint-spec sauber).

Task 15 (Sonnet) hat die SKILL.md (135 Zeilen, Lint ohne Befund), den Eintrag in
`evaluated-dev` und die Projekt-Kopie angelegt. Seither nennt Claude Code deep-review als Skill.

Der Bereich des Prüfpunkts hatte 6.981 Zeilen, davon 671 ohne die Projekt-Kopie. Die Kopie ist
laut `sync --check` byte-gleich mit dem reviewten Original. `/code-review` bekam deshalb den
Hinweis, sie zu überspringen. Ergebnis: 19 Funde, kein Absturz. In Fix-Runde 1 kamen alle,
gebündelt als F1–F8:

- Git Bash unter Windows schreibt `--tool /code-review` in einen Pfad um. `record` kanonisiert
  das Werkzeug jetzt, und die SKILL.md übergibt es ohne Schrägstrich.
- `_meta.generated` nennt den Pfad `review_kit.py` ohne Repo-Pfad.
- Der Cache-Ordner bekommt eine eigene `.gitignore`.
- SKILL.md nennt die Eiserne Regel wörtlich wie Spec 26 und sagt dazu: `cleanup --stale`
  betrifft alle Läufe, `--split-at` steht im Aufruf, und die Übergabe nennt fix-task, debug-ledger
  und test-first.
- `/security-review` läuft nicht bei einem Folgelauf mit Übernahme.
- Schon behobene übernommene Funde bleiben im Bericht. Sie fehlen nur in der Eingabe für den
  nächsten `fix-task`.
- Veraltete Stände (Task 23, „Task 15 offen“) sind berichtigt.

Ergebnis: 1.792 Tests grün, SKILL.md mit 148 Zeilen.

## Was nicht gemessen wurde

**deep-review selbst** — die Skill ist bis Task 15 gebaut (Skript, References, Vorlage, Evals,
SKILL.md, Plugin-Eintrag, Projekt-Kopie), aber noch nicht gemessen; ihre Läufe auf beiden
Fixtures, die Abschaltungen und der Vergleich mit dieser Basislinie folgen in der Abnahme,
Task 16.

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
