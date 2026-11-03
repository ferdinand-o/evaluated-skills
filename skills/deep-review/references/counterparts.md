# Gegenstellen: Sammelregel, Paketblock, Lesehilfe

Referenz für den Hauptagenten. Was `review_kit.py counterparts --run <lauf>` je Paket sammelt,
wie `packets/<id>.md` aussieht und wie der Reviewer den Block liest. Den Block gibst du jedem
Unteragenten von `/code-review` unverändert mit (`review-brief.md`). Grenzwerte stehen in
`packets.md`.

## Woher die Daten kommen

- Geänderte Zeilen aus `git diff -U0` über den Bereich des Plans (Merge-Basis..ZIEL), nur für
  die Dateien des Pakets. Eine reine Löschung ändert keine Zeile am ZIEL.
- Der Code kommt aus Git am ZIEL, nie aus dem Arbeitsbaum. Python wird nur per `ast`
  gelesen, Delphi per Text-Scanner. Zielcode wird nie importiert oder gestartet.
- Gesucht wird im ganzen Repo am ZIEL, auch in vendortem Code und in Dateien, die nicht im
  Diff stehen. `.skills/` zählt nicht.
- Mechanisch: Jede Stelle, die die Sammelregel trifft, steht im Block. Es gibt keine Auswahl
  nach Verdacht. Was nicht eindeutig auflösbar ist, fehlt und wird als „nicht aufgelöst“
  gezählt.

## Sammelregel je Sprache

| Sprache | Dateien | Stelle | steht im Block, wenn |
| --- | --- | --- | --- |
| Python | `.py` | Aufruf auf einer geänderten Zeile | eine erreichte Definition etwas wirft oder der Aufruf ein geändertes Schlüsselwort-Argument hat |
| Python | | geänderte `except`-Klausel | ein Aufruf im `try`-Block eine Definition erreicht, die etwas wirft |
| Delphi | `.pas`, `.dpr`, `.dpk` | Aufruf auf einer geänderten Zeile | die Implementierung etwas wirft oder ihr Kopf einen Default-Wert hat |
| Delphi | | `Extract`, `ExtractPair`, `ExtractItem`, `Remove`, `Delete`, `Clear`, `Dequeue`, `Pop`, `Free`, `FreeAndNil`, `SetContentStream` auf einer geänderten Zeile (`Delete`, `Clear`, `Dequeue` und `Pop` geben bei OwnsObjects frei, `ExtractItem` gibt ab; an TDictionary/TObjectDictionary gibt es nur `ExtractPair`; eigene Methoden `ExtractKey`/`ExtractValue` bekommen keinen Besitz-Hinweis) | der Typ des Empfängers auflösbar ist (Klasse im Repo oder Besitz-Default der RTL) |
| Delphi | | geändertes `inherited Create(…)` im Konstruktor einer Klasse mit Besitz-Default der RTL | immer |
| andere | alle übrigen Endungen | keine | nie: „Gegenstellen nicht gesammelt (Sprache)“ |

Endungen ohne Rücksicht auf Groß/Klein. Fokus `quality` sammelt keine Gegenstellen. Der Block
sagt dann „Gegenstellen nicht gesammelt (Fokus quality).“

### Python

- **Auflösung:** Ein voll qualifizierter Modulpfad (`pkg.mod.func(...)`) entscheidet zuerst.
  Danach gilt die eigene Datei, dann die importierten Dateien und Pakete. Ohne Importbezug und
  mit mehr als `AMBIGUOUS_MAX` (3) gleichnamigen Definitionen gibt es nichts, die Stelle wird
  gezählt. Je Aufruf höchstens zwei Definitionen. Ein Klassenaufruf erreicht `__init__`.
- **Je Definition:** Signatur, erste Docstring-Zeile (`Doc:`, höchstens 240 Zeichen),
  `wirft:` und darunter bis zu acht `raise`-Zeilen. Die `raise`-Stellen werden transitiv über
  Aufrufe im selben Modul gesucht, `RAISE_DEPTH` (2) Ebenen tief.
- **`except`:** Die Überschrift nennt die gefangenen Typen. Darunter steht jede Definition,
  die ein Aufruf im `try`-Block erreicht und die etwas wirft.
- **Geändertes Schlüsselwort-Argument:** Dazu kommt der Weg durch die Gegenstellen bis zu
  den Bedingungen, die den Parameter prüfen. Er führt über `FLAG_DEPTH` (4) Funktionen und
  zeigt höchstens zwölf Zeilen. Endet er an einer mehrdeutigen Gegenstelle, wird die
  Weitergabe gezählt.

### Delphi

- **Aufrufe:** `Name(`, `Obj.Name(`, `Name<T>(` und im Rumpf einer Routine auch ohne Klammer
  (`Flush;`, `Queue.Drain;`). Gesucht werden zuerst die geschachtelten Routinen, dann die
  eigene Klasse, dann die eigene Unit, dann die Units der `uses`-Listen (die zuletzt genannte
  verdeckt frühere). Bei einem Empfänger mit bekanntem Typ gilt nur dessen Klassenkette.
- **Nicht geraten:** Ein Aufruf auf einer Unit außerhalb des Repos (`System.SysUtils.Format(`)
  oder auf einer Unit, deren Blöcke nicht aufgehen, ergibt nichts und wird gezählt. Ebenso
  ein unbekannter Empfänger mit mehr als 3 gleichnamigen Methoden, ohne Klammer schon mit
  einer.
- **Je Implementierung:** Kopf aus der Deklaration (`interface`-Teil oder Klassenrumpf) mit
  Default-Werten, `deklariert:` mit deren Zeile, `wirft:` mit `raise`-Zeilen aus derselben
  Unit (Tiefe 2). Überladungen werden nach Namen und Typen der Parameter getrennt.
- **Besitz:** Der Typ des Empfängers kommt aus der Parameterliste, dem `var`-Abschnitt, einem
  Inline-`var`, einem Feld oder einer Property der Klasse, einer Unit-Variable oder `Self`.
  Gezeigt werden die Klassendeklaration mit Basisklasse und die `inherited Create(…)` ihrer
  Konstruktoren, über bis zu vier Klassen der Kette. Erbt sie von `TObjectList<…>`,
  `TObjectDictionary<…>`, `TObjectQueue<…>`, `TObjectStack<…>` oder `TObjectList` (Contnrs),
  steht der Besitz-Default der RTL dabei.

## Was nicht gesammelt wird

| nicht gesammelt | Folge im Block |
| --- | --- |
| Sprachen ohne Sammler (TypeScript, Java, SQL, …) | Dateizeile `` - `<datei>` — Gegenstellen nicht gesammelt (Sprache) `` |
| Aufrufe ohne Importbezug mit mehr als 3 gleichnamigen Definitionen | fehlen, gezählt als „nicht aufgelöst“ |
| Aufrufe, deren Definition nichts wirft (Delphi: auch ohne Default) und ohne geändertes Argument | fehlen, nicht gezählt |
| `raise` in anderen Modulen bzw. Units als der Definition | fehlen in `wirft:` |
| Typinferenz: Ausdrücke, Funktionsergebnisse, Delphi-`with` und Indexer | Python löst `obj.name(...)` nur über ein Modul im Repo, `self`/`cls`/`super()`, eine bekannte Klasse oder `Klasse(...)` auf, sonst zählt die Stelle als nicht aufgelöst; Delphi zeigt keine Gegenstelle |
| Delphi: andere Zweige von `{$IFDEF}`, `{$I}`-Dateien | geänderte Zeilen dort stehen mit Zahl in der Dateiliste |
| Dateien am ZIEL, die der Sammler nicht lesen kann | Dateiliste: „Datei am ZIEL nicht lesbar: <grund>“ |

Gründe für nicht lesbare Dateien: `Syntaxfehler`, `Symlink`, `Pfad nicht UTF-8`,
`Submodul (gitlink), keine Datei`, `Blöcke gehen nicht auf (Delphi-Scanner)`,
`nicht als Datei im Baum des ZIELS`. Nicht lesbare Dateien derselben Sprache außerhalb des
Pakets stehen als eine Zahl am Ende des Blocks, denn dort wurde nicht gesucht.

## Zeilenformat des Paketblocks

```
<!-- skill: deep-review | schema: 1 | generated: … counterparts --run <lauf> | packet: <id> -->
# Paket <id>

Bereich: `<von>..<bis>`

Dateien (<n>):
- `<datei>`
- `<datei>` — Gegenstellen nicht gesammelt (Sprache)

## Gegenstellen

<k> Stelle(n) nach der Sammelregel, mechanisch gesammelt (ohne Auswahl nach Verdacht); <u> nicht aufgelöst (ohne Importbezug und mehrdeutig: nichts statt Raten).

### <datei>:<zeile> ruft <name>(...)
- Gegenstelle <Name> [<datei>:<zeile>]: <Signatur>
  Doc: <erste Docstring-Zeile>
  wirft: <Typ>, <Typ>
    raise <Typ> at <datei>:<zeile>
  geändert: <arg>=<wert>; Weg:
    <datei>:<zeile>: <param> -> <Ziel>(<arg>=...) [<datei>:<zeile>]
    <datei>:<zeile>: if <bedingung>: <erste Anweisung>
```

| Überschrift | Art |
| --- | --- |
| `### <datei>:<zeile> ruft <name>(...)` | Aufruf (Python, Delphi) |
| `### <datei>:<zeile> except <Typen>` | geänderte `except`-Klausel (Python; ohne Typ `alles`) |
| `### <datei>:<zeile> <Op> auf <Empfänger>: <Typ>` | Freigabe oder Entnahme (Delphi) |
| `### <datei>:<zeile> inherited Create auf Self: <Klasse>` | Konstruktor einer besitzenden Klasse (Delphi) |

- Hat eine Zeile mehrere Einträge für denselben Namen, trägt die Überschrift die Spalte:
  `### <datei>:<zeile>:<spalte> …`.
- Delphi-Zeilen unter einer Gegenstelle: `deklariert: <datei>:<zeile>`,
  `inherited Create(…) at <datei>:<zeile>`, `Besitz (RTL): …`.
- Einträge stehen nach Datei, Zeile und Art sortiert.
- **Kappung:** Höchstens `BLOCK_MAX_CHARS` (30000) Zeichen je Datei, Kopfzeile eingeschlossen.
  Die Dateiliste bekommt höchstens die Hälfte, außer die Stellen brauchen weniger. Was fehlt,
  ist benannt mit
  `- … und <n> weitere Datei(en) (gekappt)` und
  `(gekappt: <x> von <y> Stellen nicht im Block — Grenze <z> Zeichen je Paket)`. `<z>` ist
  die Grenze ohne die Kopfzeile. Nie still.
- Die Ausgabe von `counterparts` je Paket lautet
  `<id>: <bereich> · <pfad> · <k> Gegenstellen, <gezeigt> gezeigt, <u> nicht aufgelöst`.

## Lesehilfe für den Reviewer

### `wirft:` neben einer geänderten `except`-Klausel

Der Diff verengt in `sensors/ingest.py` ein `except (ValueError, OverflowError)` auf
`except ValueError`:

```
### sensors/ingest.py:41 except ValueError
- Gegenstelle to_celsius [vendor/unitconv/convert.py:18]: def to_celsius(raw, strict=False)
  Doc: Rohwert des Fühlers in Grad Celsius.
  wirft: OverflowError, ValueError
    raise ValueError at vendor/unitconv/convert.py:24
    raise OverflowError at vendor/unitconv/convert.py:31
```

- Vergleiche `wirft:` mit den Typen der Überschrift. Ein Typ in `wirft:`, den die Klausel
  nicht mehr fängt, läuft jetzt nach oben durch. Hier ist das `OverflowError` aus Zeile 31.
- Die Frage lautet also: Fängt ein Aufrufer weiter oben `OverflowError`? Sonst bricht der
  Import beim ersten Ausreißer ab, statt den Wert zu verwerfen.
- `wirft:` zeigt alles, was die Definition werfen *kann*. Ob ein `raise` innerhalb der
  Gegenstelle selbst gefangen wird, prüft das Skript nicht. Öffne die `raise … at`-Zeile,
  bevor du daraus einen Fund machst.
- Ein Name in Kleinbuchstaben in `wirft:` (`raise err`) ist eine Variable. Ihren Typ zeigt
  erst die Zeile selbst.

### `Weg:` bis zur Bedingung

Der Diff ändert in `report/build.py` den Aufruf auf `summarize(points, skip_gaps=False)`:

```
### report/build.py:57 ruft summarize(...)
- Gegenstelle summarize [report/stats.py:9]: def summarize(points, skip_gaps=True)
  geändert: skip_gaps=False; Weg:
    report/stats.py:14: skip_gaps -> fill_series(skip_gaps=...) [report/series.py:22]
    report/series.py:25: if skip_gaps: return [p for p in points if p.value is not None]
```

- Jede Zeile mit `->` ist eine Weitergabe des Parameters. Jede Zeile mit `if` ist eine
  Bedingung, die ihn prüft (auch `while` und `x if c else y` stehen als `if`).
- Spiel den neuen Wert durch: Mit `False` springt `series.py:25` nicht mehr an, Punkte mit
  `value is None` bleiben in der Reihe. Die Frage lautet: Verträgt der Code hinter
  `fill_series` solche Punkte?
- Unterscheiden sich der Default der Gegenstelle (`skip_gaps=True`) und der neue Wert, ist das
  Verhalten des Aufrufers geändert, auch wenn die Gegenstelle selbst nicht im Diff steht.

### Besitz bei Delphi

```
### Outbox.pas:88 ExtractPair auf ABox: TMailBox
- Gegenstelle TMailBox [Mailer.pas:12]: TMailBox = class(TObjectDictionary<string, TMail>)
  inherited Create([doOwnsValues]) at Mailer.pas:40
  Besitz (RTL): TObjectDictionary<…>: Besitz nur nach Ownerships im Konstruktor (doOwnsKeys, doOwnsValues; das geerbte Create ohne sie besitzt nichts) — Remove und Clear geben Besitztes frei, ExtractPair nicht
```

- `inherited Create(…)` und `Besitz (RTL)` sagen, wer freigibt. Wechselt der Diff von
  `Remove` auf `ExtractPair`, gibt das Dictionary den Wert nicht mehr frei. Ab dann muss ihn
  jemand anderes freigeben. Bei Listen, Queues und Stacks gilt dasselbe für `Extract`.
- Bei einem Aufruf zeigt der Kopf die Default-Werte, `deklariert:` sagt, wo sie stehen.
  Weitere Delphi-Fragen stehen in `delphi.md`.

### Die Zahlen im Kopf

- `<u> nicht aufgelöst`: An so vielen Stellen hätte es eine Gegenstelle geben können. Das
  Skript nennt sie nicht, weil es raten müsste. Sie gehören in das normale Review.
- Eine Datei mit „Gegenstellen nicht gesammelt (Sprache)“ wird ohne Block reviewt. Ein leerer
  Abschnitt heißt dort nicht, dass es keine Verträge gibt.
