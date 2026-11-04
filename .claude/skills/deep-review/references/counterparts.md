# Gegenstellen: Sammelregel, Paketblock, Lesehilfe

Referenz für den Hauptagenten. Was `review_kit.py counterparts --run <lauf>` je Paket sammelt,
wie `packets/<id>.md` aussieht und wie der Reviewer den Block liest. Den Block gibst du jedem
Unteragenten von `/code-review` unverändert mit, als Teil von `packets/<id>.prompt.md`
(`review-brief.md`). Grenzwerte stehen in `packets.md`. `plan` sammelt die Gegenstellen einmal
und legt sie je Datei im Laufordner ab (`counterparts.json`); `counterparts` schreibt aus
dieser Ablage die Blöcke. Im [Pfad-Modus](packets.md#pfad-modus) filtert es zusätzlich
je Paket.

## Woher die Daten kommen

- Geänderte Zeilen aus `git diff -U0` über den Bereich des Plans (Merge-Basis..ZIEL), nur für
  die Dateien des Pakets. Eine reine Löschung ändert keine Zeile am ZIEL.
- Der Code kommt aus Git am ZIEL, nie aus dem Arbeitsbaum. Python wird nur per `ast`
  gelesen, Delphi und TypeScript/JavaScript per Text-Scanner (Strings, Template-Literale und
  Kommentare ausgeblendet), alle übrigen Sprachen per Namenssuche. Zielcode wird nie
  importiert oder gestartet.
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
| TypeScript, JavaScript | `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs` | Aufruf auf einer geänderten Zeile | die Gegenstelle etwas wirft (`throw`) oder `async` ist und der Aufruf kein `await` hat |
| TypeScript, JavaScript | | geänderte `catch`-Klausel | ein Aufruf im `try`-Block eine Gegenstelle erreicht, die etwas wirft |
| Java, C#, Go, Rust, C, C++, Kotlin, Swift | `.java`, `.cs`, `.go`, `.rs`, `.c`, `.h`, `.cc`, `.cpp`, `.cxx`, `.hpp`, `.hh`, `.hxx`, `.kt`, `.kts`, `.swift` | Aufruf auf einer geänderten Zeile | der Name im Repo genau einmal definiert ist und dessen Rumpf `throw` oder `panic` enthält ([Namens-Rückfall](#namens-rückfall)) |
| andere | alle übrigen Endungen | keine | nie: „Gegenstellen nicht gesammelt (Sprache)“ |

Endungen ohne Rücksicht auf Groß/Klein. Fokus `quality` sammelt keine Gegenstellen. Der Block
sagt dann „Gegenstellen nicht gesammelt (Fokus quality).“

### Python

- **Auflösung:** Ein voll qualifizierter Modulpfad (`pkg.mod.func(...)`) entscheidet zuerst.
  Danach gilt die eigene Datei, dann die importierten Dateien und Pakete. Ohne Importbezug und
  mit mehr als `AMBIGUOUS_MAX` (3) gleichnamigen Definitionen gibt es nichts, die Stelle wird
  gezählt. Je Aufruf höchstens zwei Definitionen. Ein Klassenaufruf erreicht `__init__`.
- **Attribut-Aufruf:** `modul.f()` und `Klasse.m()` gehen über den Import, auch wenn ein Modul
  den Namen eine Ebene weiterreicht (`from .impl import load` in `pkg/__init__.py`). Ist der Typ
  des Empfängers unbekannt (`finder.find()`, `self.x.m()`), gilt die einzige Klasse oder Methode
  dieses Namens im Repo, markiert als „(Empfänger unbekannt, Name eindeutig)“ — nur wenn es genau
  eine gibt und der Name keine Methode eingebauter oder Stdlib-Typen ist (`BUILTIN_METHOD_NAMES`:
  `start`, `get`, `copy`, `append`, `items`, `join`, `read` …); sonst gibt es nichts, und die
  Stelle wird gezählt. `m.start()` auf einem Regex-Treffer bleibt also ungelöst.
- **Je Definition:** Signatur, erste Docstring-Zeile (`Doc:`, höchstens 240 Zeichen),
  `wirft:` und darunter bis zu acht `raise`-Zeilen. Die `raise`-Stellen werden transitiv über
  Aufrufe im selben Modul gesucht, `RAISE_DEPTH` (2) Ebenen tief.
- **`except`:** Die Überschrift nennt die gefangenen Typen. Darunter steht jede Definition,
  die ein Aufruf im `try`-Block erreicht und die etwas wirft.
- **Geändertes Schlüsselwort-Argument:** Dazu kommt der Weg durch die Gegenstellen bis zu
  den Bedingungen, die den Parameter prüfen. Er führt über `FLAG_DEPTH` (4) Funktionen und
  zeigt höchstens zwölf Zeilen. Endet er an einer mehrdeutigen Gegenstelle, wird die
  Weitergabe gezählt.

### TypeScript und JavaScript

- **Auflösung:** Ein Name zählt, wenn ihn `import f from './x'`, `import { f } from '../y'`,
  `import * as m from './z'` oder `const { f } = require('./z')` / `const m = require('./z')`
  (dann `m.f(…)`) an eine **relative** Datei bindet. Die Endung ergibt sich in der Folge `.ts`,
  `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs`, danach `x/index.*`. Nicht aufgelöst werden Pakete
  (`node_modules`), Pfad-Aliase aus `tsconfig.json` (`@/x`) und relative Importe ohne Datei am
  Ziel; sie stehen nicht im Block, zählen aber als „nicht aufgelöst“. Eine geänderte Datei unter
  `node_modules` steht mit dem Grund „unter node_modules, Gegenstellen nicht gesammelt“ in der
  Dateiliste.
- **Definition:** `function f`, `export function f`, `const f = (…) =>`, `export const f = async …`,
  `exports.f = …`, mit der Signaturzeile. Klassenmethoden und Re-Exports (`export … from`)
  werden nicht aufgelöst.
- **Wann ein Eintrag entsteht:** wenn die Gegenstelle `throw` enthält oder wenn sie `async` ist
  und der Aufruf ohne `await` steht (nicht als `return f(…)`, nicht vor `.then(`, `.catch(`,
  `.finally(`). `wirft:` und die `throw`-Zeilen kommen aus dem Rumpf, transitiv in derselben
  Datei bis `RAISE_DEPTH` (2). Der async-Fall trägt die Zeile `async: Aufruf ohne await, …`.
- **`catch`:** Je geänderter `catch`-Klausel (vom Wort `catch` bis zur schließenden Klammer; die
  Verengung steht in TypeScript im Rumpf, etwa `if (e instanceof …)`) ein Eintrag mit den
  werfenden Gegenstellen der Aufrufe im `try`-Block, wie bei Python. Die Überschrift ist
  `### <datei>:<zeile> catch (e)`.
- **Nicht gesammelt:** Typinferenz und ein geändertes Argument mit seinem Weg (`Weg:` gibt es
  nur bei Python).

### Namens-Rückfall

Für Java, C#, Go, Rust, C, C++, Kotlin und Swift gibt es keinen eigenen Sammler, nur diese
Namenssuche:

- **Auflösung:** Der Name eines Aufrufs auf einer geänderten Zeile wird im ganzen Repo am Ziel
  gesucht, auch über Dateien und Sprachen hinweg (`func Name(` für Go, `fn name(` für Rust,
  `fun`/`func` für Kotlin und Swift, Rückgabetyp plus `Name(…) {` für Java, C#, C und C++). Gibt
  es genau eine Definition, steht sie im Block mit Signaturzeile und der Kennzeichnung
  **„(Name eindeutig, ohne Sammler)“**. Zwei oder mehr gleichnamige Definitionen: nicht aufgelöst,
  gezählt. Mehrfache Namen werden nicht geraten, auch nicht mit Importen: Importe, Überladungen
  und Besitz kennt dieser Rückfall nicht.
- **Eintrag:** nur, wenn der Rumpf der Definition eine direkte `throw`- oder `panic`-Zeile hat;
  sie steht unter `wirft:` und als `throw … at <datei>:<zeile>` bzw. `panic … at …`. Würfe in
  Funktionen, die der Rumpf aufruft, folgt der Rückfall nicht. Eine Deklaration ohne Rumpf
  (Protokoll, Interface, `abstract`) hat keine Zeile.
- **C und C++:** auch `int Parser::parse(…) {`, Zeiger- und Referenz-Rückgaben und
  `const`/`noexcept`/`override`/`-> T` vor `{`. Der Name ist der letzte Teil nach `::`: Der
  Aufruf `parse(x)` trifft `Parser::parse`. Der Typ einer `throw`-Zeile endet vor einem `::`
  (`throw std::out_of_range(…)` erscheint als `throw std`), die Zeile selbst ist lesbar.

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
| Sprachen ohne Sammler und ohne Namens-Rückfall (SQL, Shell, …) | Dateizeile `` - `<datei>` — Gegenstellen nicht gesammelt (Sprache) `` |
| Aufrufe ohne Importbezug mit mehr als 3 gleichnamigen Definitionen (Python, Delphi); mehrfach definierte Namen im Namens-Rückfall | fehlen, gezählt als „nicht aufgelöst“ |
| TypeScript/JavaScript: Pakete, `node_modules`, Pfad-Aliase, Klassenmethoden, Re-Exports, Typinferenz | fehlen; nicht aufgelöste Importe sind gezählt |
| Aufrufe, deren Definition nichts wirft (Delphi: auch ohne Default) und ohne geändertes Argument | fehlen, nicht gezählt |
| `raise` in anderen Modulen bzw. Units als der Definition | fehlen in `wirft:` |
| Typinferenz: Ausdrücke, Funktionsergebnisse, Delphi-`with` und Indexer | Python löst `obj.name(...)` mit unbekanntem Empfänger nur bei eindeutigem, nicht eingebautem Methodennamen auf (markiert), sonst zählt die Stelle; Delphi zeigt keine Gegenstelle |
| Delphi: andere Zweige von `{$IFDEF}`, `{$I}`-Dateien | geänderte Zeilen dort stehen mit Zahl in der Dateiliste |
| Dateien am ZIEL, die der Sammler nicht lesen kann | Dateiliste: „Datei am ZIEL nicht lesbar: <grund>“ |

Gründe für nicht lesbare Dateien: `Syntaxfehler`, `Symlink`, `Pfad nicht UTF-8`,
`Submodul (gitlink), keine Datei`, `Blöcke gehen nicht auf (Delphi-Scanner)`,
`unter node_modules, Gegenstellen nicht gesammelt`, `nicht als Datei im Baum des ZIELS`. Nicht lesbare Dateien derselben Sprache außerhalb des
Pakets stehen als eine Zahl am Ende des Blocks, denn dort wurde nicht gesucht.

## Zeilenformat des Paketblocks

```
<!-- skill: deep-review | schema: 1 | generated: … counterparts --run <lauf> | packet: <id> | counterparts: <n> -->
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
| `### <datei>:<zeile> ruft <name>(...)` | Aufruf (Python, Delphi, TypeScript/JavaScript, Namens-Rückfall) |
| `### <datei>:<zeile> except <Typen>` | geänderte `except`-Klausel (Python; ohne Typ `alles`) |
| `### <datei>:<zeile> catch (e)` | geänderte `catch`-Klausel (TypeScript/JavaScript) |
| `### <datei>:<zeile> <Op> auf <Empfänger>: <Typ>` | Freigabe oder Entnahme (Delphi) |
| `### <datei>:<zeile> inherited Create auf Self: <Klasse>` | Konstruktor einer besitzenden Klasse (Delphi) |

- `| counterparts: <n>` in der Kopfzeile ist die Zahl der Gegenstellen des Pakets, maschinenlesbar
  (Bericht und `packets.md`); bei Fokus `quality` fehlt das Feld.
- Hat eine Zeile mehrere Einträge für denselben Namen, trägt die Überschrift die Spalte:
  `### <datei>:<zeile>:<spalte> …`.
- Zeilen unter einer Gegenstelle bei TypeScript/JavaScript und Namens-Rückfall: `wirft: <Typ>`
  mit `throw <Typ> at <datei>:<zeile>` bzw. `panic … at …`, bei einem Aufruf ohne `await` die
  Zeile `async: Aufruf ohne await, das Ergebnis und ein Fehler werden nicht abgewartet`.
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

### `catch` und `async` in TypeScript

Der Diff in `web/checkout.ts` fängt in einem `try` um `reserve(user, units)` nur noch
`TypeError` ab und ruft `recordUsage(user, got)` ohne `await`:

```
### web/checkout.ts:6 ruft recordUsage(...)
- Gegenstelle recordUsage [shared/quota.ts:10]: async function recordUsage(user: string, units: number)
  async: Aufruf ohne await, das Ergebnis und ein Fehler werden nicht abgewartet

### web/checkout.ts:8 catch (e)
- Gegenstelle reserve [shared/quota.ts:3]: function reserve(user: string, units: number)
  wirft: QuotaExceeded
    throw QuotaExceeded at shared/quota.ts:5
```

- Wie bei `except`: `wirft:` gegen das, was die `catch`-Klausel behält. `QuotaExceeded` erfüllt
  `e instanceof TypeError` nicht und läuft per `throw e` nach oben. Öffne `shared/quota.ts:5`,
  und prüfe, ob der Aufrufer weiter oben den Fehler fängt.
- Ein `async:`-Eintrag sagt nur, dass der Aufruf nicht abgewartet wird. Ob das Ergebnis oder
  ein Fehler dort gebraucht wird, zeigt erst der Rumpf; ein Fehler von `recordUsage` wird zu
  einem unbehandelten Promise-Fehler und erreicht das `catch` nicht.
- `node_modules`, Pfad-Aliase und Klassenmethoden fehlen im Block. Ein Aufruf dorthin steht
  unter „nicht aufgelöst“ und gehört in das normale Review.

### Namens-Rückfall: eindeutiger Name

Der Diff in `native/ring.cpp` ruft `Ring::pop(n - 1)` aus `drain`:

```
### native/ring.cpp:8 ruft pop(...)
- Gegenstelle pop [native/ring.cpp:2]: int Ring::pop(int n) (Name eindeutig, ohne Sammler)
  wirft: std
    throw std at native/ring.cpp:4
```

- Die Kennzeichnung sagt: Der Name `pop` gibt es im Repo einmal, mehr weiß der Block nicht. Ob
  der Aufruf wirklich diese Definition trifft (Klasse, Überladung, Import), prüfst du am
  Aufruf selbst. Gäbe es `pop` zweimal, fehlte der Eintrag und die Stelle zählte als „nicht
  aufgelöst“.
- `wirft:` zeigt nur die direkten `throw`-/`panic`-Zeilen des Rumpfs; öffne die Zeile
  `throw … at …` für den vollen Ausdruck. Was `pop` über Aufrufe tiefer wirft, steht nicht da.

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
