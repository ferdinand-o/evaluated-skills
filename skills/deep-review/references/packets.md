# Pakete: Plan, Schnittregel, Bereiche, Folgeläufe

Referenz für den Hauptagenten. Was `review_kit.py plan` zählt und schneidet (Bereich oder
Pfad, ganze Dateien oder Spannen), welche Stufe jedes Paket bekommt, was der Reviewer je Paket
sieht, wie ein Folgelauf Funde übernimmt, wie `verify` und `verdict` Funde prüfen und wie ein
Lauf fortgesetzt und aufgeräumt wird. Was im Paketblock steht, beschreibt `counterparts.md`,
was der Reviewer als Auftrag bekommt und zurückgibt, `review-brief.md`.

## Grenzwerte

Am Kopf von `review_kit.py` (E7). Der Bericht nennt sie.

| Konstante | Wert | Bedeutung |
| --- | --- | --- |
| `SPLIT_AT` | 800 | bis hierher geänderte Zeilen: ein Paket über den Originalbereich (`--split-at N` ersetzt den Wert) |
| `PACKET_SIZE` | 600 | obere Paketgröße beim Teilen; `packet_size` = kleiner von 600 und `split_at` |
| `SPAN_MIN_SHARE` | 0,25 | Spannen: ein Schnitt vor einer Definition oder nach einer Leerzeile nur, wenn die Spanne dann mindestens diesen Anteil von `packet_size` geänderter Zeilen trägt |
| `PATH_SPLIT_AT` | 6000 | Pfad-Modus: bis hierher Zeilen der Pfad-Dateien ein Paket |
| `PATH_PACKET_SIZE` | 3000 | Pfad-Modus: obere Paketgröße beim Teilen |
| `MARKER_HEX` | 6 | Hexzeichen der Paket-Marke `dr-<paket>-<hex>` |
| `BLOCK_MAX_CHARS` | 30000 | Zeichen je `packets/<id>.md`, Kopfzeile eingeschlossen; darüber wird gekappt, mit Zahl |
| `MERGE_LINE_GAP` | 3 | `merge`: Funde derselben Datei mit höchstens diesem Abstand werden ein Fund |
| `RAISE_DEPTH` | 2 | `raise`-Stellen transitiv im selben Modul bzw. in derselben Unit |
| `FLAG_DEPTH` | 4 | Weg eines geänderten Schlüsselwort-Arguments durch so viele Funktionen |
| `AMBIGUOUS_MAX` | 3 | mehr gleichnamige Definitionen ohne Importbezug: nichts statt Raten, gezählt |
| `LEVELS`, `PROFILE_LEVELS` | siehe „Stufe je Profil“ | Stufen von `/code-review` und der Standard je Profil |
| `EINORDNUNG_MAX_LINES` | 8 | nur bei `split: false`: Textzeilen der Einordnung ab `## Einordnung` (siehe „Bericht prüfen“); den Teil davor schreibt das Skript |

## Bereich und Zählung

`review_kit.py plan --range <bereich> [--profile standard|checkpoint] [--focus bugs|security|quality] [--level <stufe>] [--verify] [--split-at N] [--since <lauf>[,<lauf>…]] [--soll-file <datei>] [--with-tests]`

Statt eines Bereichs nimmt `plan` Pfade ([Pfad-Modus](#pfad-modus)).

| Eingabe | gilt als |
| --- | --- |
| `BASIS..ZIEL` | gezählt ab der Merge-Basis bis ZIEL; Commit-Messages aus `git log BASIS..ZIEL` |
| eine Revision `X` | `X^..X` (erster Parent); beim Wurzel-Commit leerer Baum..`X` |
| ohne `--range` | `HEAD`, also der letzte Commit |
| `A...B` | abgelehnt, zwei Punkte zählen schon ab der Merge-Basis |

- Gezählt werden hinzugefügte plus gelöschte Zeilen aus `git diff --numstat --no-renames`.
  Eine Umbenennung ist eine gelöschte und eine neue Datei. Binärdateien zählen 0, `.skills/`
  zählt nie.
- `plan.json` trägt `mode` (`range` oder `path`; ohne Feld gilt `range`) und hält den Bereich
  aufgelöst fest: `range` als SHAs `<basis>..<ziel>` (beim
  Wurzel-Commit nur `<ziel>`, dazu `root: true`), `base` (Merge-Basis oder leerer Baum),
  `target`, `log_base` (aufgelöste BASIS, beim Wurzel-Commit `null`).
- Profil `checkpoint` geht nur mit Fokus `bugs` und nur mit `--soll-file`. Ohne die Datei
  bricht `plan` mit Exit 1 ab und legt keinen Lauf an. `--soll-file` steht danach in
  `_meta.soll_file`.
- Ohne reviewte Datei bricht `plan` mit „nichts zu reviewen“ ab und legt keinen Lauf an.

Die Ausgabe beginnt mit `Lauf: <lauf>`. Die Lauf-ID hat die Form
`<JJJJ-MM-TT>-<HHMMSS>-<kurz-sha>-<4 Zufallszeichen>` (UTC). Zwei Läufe in derselben Sekunde
bekommen verschiedene IDs. Alles liegt unter `.skills/cache/deep-review/<lauf>/`.

## Stufe je Profil und Zeile `Reviews:`

`plan` schreibt die Stufe für `/code-review <stufe>` als `level` ins Plan-Objekt, ein Wert aus
`LEVELS = ("low", "medium", "high", "xhigh", "max")`. Ohne `--level` gilt der Standard des
Profils (`PROFILE_LEVELS`), gemessen in der Sonde B auf einem Paket mit drei eingebauten Fehlern:

| Profil | Stufe |
| --- | --- |
| `standard` | `medium` |
| `checkpoint` | `high` |

- `--level max` gibt es nur, wenn der Nutzer es ausdrücklich will. Fokus `security` hat keine
  Stufe (`/security-review` oder ein Review im Hauptkontext kennt keine); `--level` ändert dort
  nichts.
- Ein Plan aus Spec 26 ohne `level` liest sich mit dem Standard seines Profils.
- Die Stufe, mit der ein Review wirklich lief, steht im Ergebnis (`record`, siehe
  `review-brief.md`). Liegt sie unter der des Plans, nimmt `record` es an und `audit` nennt
  das Paket unter `below_level`; `complete` ändert das nicht. Ein Folgelauf übernimmt nur
  Ergebnisse, deren Stufe mindestens die des neuen Plans ist (der `plan`-Ausgabe nach
  `Übergangen: …`).
- Die Zeile `Reviews: <n> × /code-review <stufe>` steht in der Ausgabe von `plan`, damit der
  Nutzer die Kosten vor dem Lauf sieht, und im Bericht (dort mit `; unter der Stufe: <paket>
  (<stufe>)`). Bei Fokus `security` lautet sie `Reviews: 1 × /security-review oder Review im
  Hauptkontext`.

## Nicht reviewt: `not_reviewed`

Je Datei `{"file", "reason"}`. Diese Dateien zählen nicht zu `changed_lines` und kommen in
kein Paket. Der Bericht führt sie unter „Nicht geprüft“.

| Grund (`reason`) | Dateien |
| --- | --- |
| `keine Quelldatei: Doku` | `.md`, `.markdown`, `.rst`; ohne Endung `NEWS`, `CHANGES`, `CHANGELOG`, `AUTHORS`, `LICENSE`, `COPYING` |
| `keine Quelldatei: Bild` | `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.ico`, `.svg`, `.webp`, `.tif`, `.tiff` |
| `keine Quelldatei: Delphi-Projekt oder Ressource` | `.dproj`, `.res` |
| `Testdatei: nur mit --with-tests` | `test_*.py`, `*_test.py`, alles unter `tests/` oder `unittests/` (Groß/Klein egal); `.pas`, deren Name ein Glied `Test` oder `Tests` hat |
| `Quelldatei mit Nicht-UTF-8-Pfad — nicht reviewt` | Quelldatei, deren Pfad kein UTF-8 ist (escapte Form) |
| `Pfad ist kein UTF-8` | dasselbe für Doku, Bilder und Tests |

Delphi-Testregel: Der Name ohne Endung wird an `.` und `_` geteilt, jedes Stück an
Wortgrenzen und Ziffern. `Shop.Tests.Cart.pas`, `CartTEST.pas` und `JSONTest.pas` sind
Testdateien, `Testament.pas` und `LATEST.pas` nicht. `--with-tests` nimmt Tests auf. Doku,
Bilder und Projektdateien bleiben auch dann draußen.

## Schnittregel

1. Bis `split_at` geänderte Zeilen: ein Paket `p1` mit allen Dateien, `split: false`.
2. Darüber werden die Dateien nach Pfad sortiert und nach Verzeichnis gruppiert. Die Gruppen
   kommen in der Reihenfolge ihres ersten Auftretens.
3. Die Gruppen füllen der Reihe nach Pakete bis `packet_size`. Ein Paket nimmt mehrere
   Verzeichnisse auf. Passt eine Gruppe nicht mehr ins laufende Paket, beginnt sie ein neues.
4. Eine Gruppe, die allein größer als `packet_size` ist, wird an Dateigrenzen geteilt. Ihre
   letzte Teilmenge kann sich das Paket mit der nächsten Gruppe teilen.
5. Eine Datei über `packet_size` ist ein eigenes Paket oder wird in Spannen geteilt
   ([Spannen](#spannen-in-großen-dateien)); eine kleinere Datei nie.
6. **Vorrang:** Datei ganz vor Verzeichnis zusammen vor Paketgröße.
7. Ergibt der Schnitt nur ein Paket, bleibt es bei `p1` und `split: false`.
8. IDs `p1`, `p2`, … in dieser Reihenfolge. Fokus `security`: immer ein Paket `s1` über alle
   Dateien, nie geteilt.

Beispiel mit `packet_size` 600 (1.760 Zeilen, also geteilt):

| Datei | Zeilen | Paket | warum |
| --- | --- | --- | --- |
| `src/api/routes.py` | 120 | `p1` | Gruppe `src/api` (320) passt ganz |
| `src/api/schema.py` | 200 | `p1` | |
| `src/core/engine.py` | 450 | `p2` | Gruppe `src/core` (700) ist zu groß, wird an Dateigrenzen geteilt |
| `src/core/rules.py` | 250 | `p3` | 450 + 250 > 600, also neues Paket |
| `src/util/text.py` | 90 | `p3` | Gruppe `src/util` (90) passt zu `rules.py` (340) |
| `tools/gen_tables.py` | 650 | `p4`, `p5` | Datei über 600, geteilt in Spannen (siehe unten) |

Je Paket stehen im Plan `id`, `files`, `changed_lines`, `range`, `reused_from` (immer
`null`, übernommen wird je Datei, siehe Folgeläufe) und bei Spannen `spans`. Die Paket-Marke
`marker` trägt erst `counterparts` ein, nicht `plan`.

## Spannen in großen Dateien

Eine Datei mit mehr als `packet_size` geänderten Zeilen wird in Spannen geteilt, jede ein
Paket. Eine Spanne ist ein Zeilenbereich der Datei am Ziel (1-basiert, inklusiv); `spans` im
Paket ist eine Liste `{file, lines: [von, bis]}`. Eine neue Datei mit 1.300 Zeilen ergibt bei
600 mindestens drei Spannen.

- **Schnitt:** Die Spannen decken die Datei lückenlos und tragen je höchstens `packet_size`
  geänderte Zeilen. Geschnitten wird vor einer Definition der obersten Ebene, fehlt eine, nach
  einer Leerzeile, sonst nach genau so vielen Zeilen, dass die Grenze erreicht ist. Die Grenzen
  an Definitionen kennen Python (`def`, `async def`, `class`; mit Dekoratoren gilt deren erste
  Zeile) und Delphi (Routine in Spalte 0 nach `implementation`); alle anderen Sprachen schneiden
  an Leerzeilen. Ein Schnitt vor einer Definition oder nach einer Leerzeile gilt nur, wenn die
  Spanne danach `SPAN_MIN_SHARE` × `packet_size` geänderte Zeilen trägt, damit die Importe vor
  der ersten Klasse kein eigenes Paket werden. Gelöschte Zeilen zählen an ihrem Anker, der
  ersten Zeile des Hunks am Ziel. Jede Spanne trägt mindestens eine geänderte Zeile. Ausnahme
  von der Grenze: Eine Zeile, deren Gewicht allein `packet_size` übersteigt (etwa viele
  gelöschte Zeilen an einem Anker), ist eine Spanne für sich und trägt mehr.
- **Nicht geteilt** wird eine Datei, die am Ziel fehlt, leer ist oder keine reguläre Datei ist,
  oder die an der Basis keine reguläre Datei war (Symlink, Submodul). Ein Typwechsel bleibt ein
  ganzes Datei-Paket, dessen Diff ihn vollständig zeigt. Ergibt das Teilen nur eine Spanne,
  bleibt die Datei ganz.
- **Reihenfolge:** Die Spannen einer Datei sind aufeinanderfolgende Pakete. Gruppen und
  Dateien davor und danach füllen Pakete wie in der Schnittregel.
- **Modus:** Eine Modusänderung (etwa `chmod +x`) einer geteilten Datei erscheint genau einmal,
  im Paket der ersten Spanne, und nur, wenn die Datei an der Basis eine reguläre Datei war.
- **Sichtbar** ist die Spanne im Plan (`spans`), in der Ausgabe von `plan` (`p1: 1 Datei(en),
  594 Zeilen, Spanne big.py:1-594`) und im Bericht (Spalte Dateien, `1 (big.py:1-594)`).

## Paket-Bereich: was der Reviewer sieht

`review_kit.py counterparts --run <lauf>` baut zuerst je Paket den reviewbaren Bereich und trägt
ihn als `range` ins Paket ein. Danach schreibt es `packets/<id>.md` (der Paketblock) und
`packets/<id>.prompt.md` (der Auftrag, siehe unten). Die Ausgabe nennt je Paket den Bereich und
den Pfad der `prompt.md`. Den Bereich gibst du an `/code-review`. Die Gegenstellen sammelt
schon `plan`, einmal, und legt sie im Laufordner ab; `counterparts` liest sie von dort. Live
sammelt es alle Sprachen nur, wenn der Speicher fehlt oder nicht zum Plan passt; sonst nur
Delphi (Sammler mit `on_demand`), wenn der Speicher nach `--since` Delphi-Dateien trägt, die in
keinem Paket stehen.

| Fall | `range` des Pakets | Hilfscommits |
| --- | --- | --- |
| `split: false`, kein Wurzel-Commit | Originalbereich `<basis>..<ziel>` | keine |
| Fokus `security` (`s1`), kein Wurzel-Commit | Originalbereich | keine |
| `split: true` | `<von>..<bis>` | ja |
| Paket mit Spanne | `<von>..<bis>`, nur die Zeilen der Spanne im Diff | ja |
| Pfad-Modus | `<von>..<bis>`, auch bei einem Paket | ja ([Pfad-Modus](#pfad-modus)) |
| Wurzel-Commit (`root: true`) | `<von>..<bis>`, auch bei einem Paket | ja, Basis ist der leere Baum |
| nach `--since` mit Übernahme (ohne Übernahme bleibt der Plan unverändert) | `<von>..<bis>`, auch bei einem Paket | ja |

Die Hilfscommits liegen unter `refs/deep-review/<lauf>/<id>/von` und `…/bis`. Gebaut werden
sie über einen temporären Index mit der Identität `deep-review <deep-review@localhost>`.
HEAD, Index und Arbeitsbaum bleiben unberührt.

- `von`: Baum von ZIEL, die Paketdateien auf dem Stand der Basis (fehlt eine dort, wird sie
  entfernt). Parent ist ZIEL, die Message lautet `deep-review <lauf> <id>: Basis`. Eine Datei
  mit Spanne steht in `von` außerhalb der Spanne auf dem Stand des Ziels und innerhalb auf dem
  der Basis (bei einer neuen Datei fehlen die Zeilen der Spanne); `bis` bleibt der Baum des
  Ziels.
- `bis`: Baum von ZIEL, Parent `von`, die Message sind die Commit-Messages des Bereichs (das
  Soll).
- `git diff von..bis` zeigt also genau die Paketdateien. Der Baum ist der volle Code von ZIEL,
  `git log von..bis` liefert das Soll in einem Commit.
- Ausnahme: Kollidiert eine Paketdatei auf dem Stand der Basis als Datei/Ordner mit einem Pfad
  außerhalb des Pakets, fehlt dieser fremde Pfad in `von` und in `bis`.

Der Reviewer liest den Arbeitsbaum, nicht ZIEL. Deshalb schreibt jeder Bau Hinweise unter
`notes` im Plan, je `{packet, kind, files, text}`. Der Bericht nennt sie.

| `kind` | wann |
| --- | --- |
| `target_not_head` | ZIEL ist nicht HEAD |
| `worktree_differs` | Paketdateien im Arbeitsbaum weichen von ZIEL ab (`files` nennt sie) |
| `worktree_unknown` | Index fehlt, der Arbeitsbaum ist nicht geprüft |

Bei `split: false` mit HEAD als ZIEL und sauberem Arbeitsbaum gibt es keine Refs und keine
`notes`, außer in den Fällen der Tabelle mit Hilfscommits auch bei einem Paket (Pfad-Modus,
Wurzel-Commit, Übernahme nach `--since`). Das ist der Anti-Zeremonie-Fall: ein `/code-review` über den Originalbereich, ein
Bericht, dessen Einordnung höchstens `EINORDNUNG_MAX_LINES` Textzeilen hat. Den Teil vor
`## Einordnung` schreibt `report`, `audit` vergleicht ihn Zeile für Zeile; eine eigene Grenze
hat nur die Einordnung.

Der Auftrag `packets/<id>.prompt.md` ist die Datei, die der Reviewer liest: Kopfzeile, ein
Hinweis „Rückgabeformat und Paket-Marke stehen am Ende dieser Datei“, Auftrag nach Profil und
Fokus, Bereich (bei Spanne mit `datei:von-bis`), Stufe, im Profil `checkpoint` das Soll, der
Paketblock, bei Delphi-Dateien `delphi.md`, das Rückgabeformat und als **letzte Zeile**
`Paket-Marke: <marke>`. Auftrag und Block sind so eine Datei: Wer den Auftrag weitergibt, gibt
den Block mit. Die Marke steht auch in `plan.json` beim Paket und ist eine Auskunft, kein
Beleg ([review-brief.md](review-brief.md#rückgabeformat)). Über 40.000 Zeichen nennt `counterparts`
die Größe, abgebrochen wird nicht.

Die Kopfzeile von `packets/<id>.md` endet auf `| counterparts: <n> -->`: die Zahl der
Gegenstellen des Pakets, maschinenlesbar. Der Bericht liest die Spalte
Gegenstellen aus diesem Feld, nicht aus dem Text des Blocks; nur ohne Block (`counterparts`
lief noch nicht) zählt er aus dem Speicher von `plan`. Nur bei einem Block
ohne dieses Feld (Lauf vor dieser Regel) gilt die alte Zählzeile `<n> Stelle(n) nach der
Sammelregel`; ohne beides (Fokus `quality`) ergibt sich „—“.

## Pfad-Modus

`review_kit.py plan --path <pfad>[,<pfad>…] [--target <ziel>] [--profile …] [--soll-file <datei>] [--focus …] [--level …] [--verify] [--with-tests]`
(`--soll-file` ist bei `--profile checkpoint` Pflicht)
prüft Dateien, die keinen Diff haben. Ein Pfad (Ordner rekursiv oder Datei, relativ zum Repo)
wird wie ein Bereich vom leeren Stand bis zum Ziel behandelt, analog zum Wurzel-Commit: Die
Dateien des Pfads am Ziel gelten als neu, jede ihrer Zeilen zählt.

- **Ziel:** `--target` (nur mit `--path`, Standard `HEAD`). Geprüft wird der Stand am Ziel, nicht
  der Arbeitsbaum wie bei `/code-review <pfad>`; weicht der Arbeitsbaum ab, steht der Hinweis
  `worktree_differs` unter `notes`.
- **Grenzen:** bis `PATH_SPLIT_AT` (6000) Zeilen ein Paket `p1` mit `split: false`, darüber
  Pakete nach der Schnittregel bis `PATH_PACKET_SIZE` (3000), eine größere Datei in Spannen.
  Fokus `security` bleibt ein Paket `s1`. Die Grenzen sind gesetzt, gemessen ist nur ein Pfad mit
  5.308 Zeilen ohne Verlust.
- **Nicht möglich:** `--since` und `--split-at` mit `--path` enden mit Exit 1 (der Pfad-Modus
  prüft einen Stand ohne frühere Läufe; seine Grenze ist `PATH_SPLIT_AT`). Die Dateien einordnen sich wie
  im Bereichsmodus: Doku, Bilder, Projektdateien und (ohne `--with-tests`) Tests stehen unter
  `not_reviewed`; `.skills/` zählt nie.
- **Plan:** `plan.json` hat `mode: "path"` und `paths`; `range` ist `<baum>..<ziel>` (ein
  Diff-Bereich über den Baum des Ziels ohne die Pfad-Dateien, kein Log-Bereich), `log_base` ist
  `null`, `root` `false`. Jedes Paket hat `range: null`, den reviewbaren Bereich liefern die
  Hilfscommits von `counterparts` (`von` = Ziel ohne die Paketdateien, `bis` = Ziel). Der Bericht
  nennt den Pfad statt des Bereichs; die Message von `bis` nennt Pfade und Ziel, ein Verlauf
  als Soll gehört nicht dazu.
- **Gegenstellen:** Weil jede Zeile als geändert zählt, bekäme jeder Aufruf einen Eintrag. Der
  Block eines Pakets enthält darum nur Einträge, bei denen ein Ort (Gegenstelle, `raise`/`throw`,
  Weg) die Dateien oder Spannen des Pakets verlässt, auch in ein anderes Paket desselben Pfads.
  Einträge, die ganz im Paket liegen, fehlen, weil dieses Paket sie selbst liest; das sagt ein
  Satz im Block (`PATH_BLOCK_NOTE`, beginnt mit „Pfad-Modus (…)“). Besitz-Defaults der RTL
  (Delphi) bleiben immer. `plan` sammelt für den ganzen Pfad und verwirft die internen Einträge
  erst danach; ein großer Pfad kostet entsprechend Zeit.

## Datei-Schlüssel

`plan` schreibt je reviewter Datei einen Eintrag in `file_keys`:

| Feld | Inhalt |
| --- | --- |
| `key` | SHA-256 über den Inhalt am ZIEL und die Gegenstellen-Zeilen ihrer geänderten Stellen |
| `changed_lines` | geänderte Zeilen, zum Neupacken im Folgelauf |
| `base_blob`, `target_blob` | Stand an der gezählten Basis und am ZIEL: `<modus>:<blob-sha>`, `absent` (fehlt), `gitlink:<commit>` (Submodul) |
| `reused_from` | `null`, im Folgelauf die Lauf-ID, deren Funde übernommen sind |

- Inhalt aus Git am ZIEL, nie aus dem Arbeitsbaum. Ein Symlink zählt mit Link und Inhalt
  seines Ziels im Repo, ein Submodul mit seinem Commit, eine gelöschte Datei mit eigener Marke.
- Gegenstellen-Zeilen sind die Zeilen der Einträge zu dieser Datei aus dem Paketblock:
  Überschrift, Signatur, `wirft:` und `raise … at <datei>:<zeile>`. Ändert sich eine
  Gegenstelle, auch nur ihre Zeilennummer, ändert sich der Schlüssel des Aufrufers.
- Fokus `quality` sammelt keine Gegenstellen. Der Schlüssel deckt dann nur den Inhalt.
- Ein Schlüssel gilt je Datei, auch bei einer Datei mit Spannen.

## Folgeläufe: `--since`

`plan --range <bereich> --since <lauf>[,<lauf>…]` übernimmt je Datei die Funde früherer
Läufe. `--since` wirkt nur beim Anlegen eines Laufs. Einem bestehenden Lauf lässt es sich
nicht nachträglich geben, denn `plan` legt immer einen neuen Lauf an und hat kein `--run`. Wer
die Funde früherer Läufe übernehmen will, startet einen neuen Lauf mit
`plan --range <bereich> --since <lauf>`. Intern prüft `plan_since`, dass der eben angelegte Lauf
noch frisch ist: nicht schon mit `--since` geplant, ohne `results/`, `packets/` und Refs.

Eine Datei wird übernommen, wenn alles zutrifft:

1. Der frühere Lauf hat denselben Fokus und ein passendes Profil (`SINCE_PROFILES`). Beide
   Profile reviewen denselben Bereich. Im Profil `checkpoint` ersetzt die Datei aus
   `--soll-file` die Commit-Messages als Soll, und dieses Soll ist mindestens so genau. Darum
   übernimmt ein `standard`-Plan aus `standard`- und `checkpoint`-Läufen, ein
   `checkpoint`-Plan nur aus `checkpoint`-Läufen, denn ein `standard`-Lauf hatte nur die
   Commit-Messages. Eine Kette darf Läufe beider erlaubten Profile mischen. Andere Läufe
   werden still übergangen.
2. Er hat die Datei reviewt, das heißt ihr Paket hat ein angenommenes `results/<id>.json` (oder
   er hat sie selbst übernommen), und zwar mit demselben `key`. Bei einer Datei mit Spannen
   muss jedes ihrer Pakete ein Ergebnis haben; `outside` und `packet_files` zählen die Datei bei
   jedem ihrer Pakete. Die gespeicherte Stufe des Ergebnisses ist mindestens die des neuen Plans
   (siehe „Stufe je Profil“).
3. Die **Abdeckungskette** schließt sich. Der `base_blob` des passenden Laufs gleicht dem
   `base_blob` des neuen Plans. Oder er gleicht dem `target_blob` eines anderen angegebenen
   Laufs, der die Datei ebenfalls reviewt hat, und so weiter bis zur neuen Basis. Beispiel:
   Der neue Lauf zählt `t0..t2`, Lauf A hat `t1..t2` reviewt, das reicht allein nicht. Mit Lauf
   A0 über `t0..t1` schließt sich `t0→t1→t2`.

Passen mehrere Läufe, gilt der jüngste. Verglichen wird erst der Zeitteil der Lauf-ID, bei
Gleichstand die jüngste mtime seiner `results/*.json`, zuletzt die ID selbst. Die Kette ist die
kürzeste, bei gleicher Länge die über jüngere Läufe.

Was im Plan steht:

- Die übernommene Datei hat `reused_from` (der passende Lauf), `reused_chain` (alle Läufe der
  Kette, der jüngste zuerst) und `findings`. Das sind die Funde aller Kettenglieder zu dieser
  Datei. Gleiche `file`, `line` und `summary` kommen nur einmal vor, dann der jüngere Fund.
  Jeder Fund trägt `run`, den Lauf, der ihn gemeldet hat. Ein weiterer Folgelauf gibt `run`
  unverändert weiter, auch an den Funden unter `outside`.
- Funde eines früheren Pakets zu einer Datei außerhalb des Pakets (etwa zur Definition einer
  Gegenstelle) stehen getrennt unter `outside`, je `{finding, packet_files, file_blob}`. Bei
  jedem Folgelauf wird neu geprüft: Übernommen wird ein solcher Fund nur, wenn alle
  `packet_files` übernommen werden, der tragende Lauf in ihrer `reused_chain` steht und die
  Fund-Datei am neuen ZIEL denselben `file_blob` hat. Sonst entfällt er, und das neue Review
  sieht die Stelle wieder.
- Die übrigen Dateien werden nach der Schnittregel neu gepackt (`p1`, …). Alle Pakete bekommen
  `range: null` und später Hilfscommits, denn der volle Bereich zeigte die übernommenen Dateien
  wieder. `split` ist dann `true`, `notes` entfallen, `changed_lines` bleibt die Zahl des
  ganzen Bereichs.
- Bleibt keine Datei übrig, ist `packets` leer, und die Ausgabe sagt „Pakete: keine — alle
  Dateien übernommen“.

Hatte der frühere Lauf zu einem Fund ein Urteil (`verify`/`verdict`, nächster Abschnitt), trägt
ihn der übernommene Fund mit; ein `widerlegt` ist im Folgelauf nicht wieder offen. Das gilt,
solange der Text des Funds gleich bleibt, und nur für das geltende Urteil des früheren Laufs.

`merge` und `audit` zählen übernommene Funde wie eigene. Ein unlesbarer oder fehlender
früherer Plan bricht den Folgelauf ab, auch wenn er wegen Fokus oder Profil übergangen würde.

## Vereinigen der Funde

`merge --run <lauf>` legt Funde derselben Datei zusammen, ohne abzustimmen. Alle Pakete
bleiben in `packets`, alle ursprünglichen Funde in `sources`. Die Regel ist nicht transitiv:
Ein Fund eröffnet eine Gruppe. Ein späterer kommt hinein, wenn sein Anfang höchstens
`MERGE_LINE_GAP` Zeilen nach dem Ende dieses ersten Funds liegt oder seine Spanne die eines
Glieds überschneidet. 10 und 12 werden ein Fund. Aus 10, 13 und 16 werden zwei: 10 mit 13,
dann 16. `20-22` und 25 werden einer. Funde ohne Zeile bleiben für sich.

Bei einem übernommenen Fund nennt `sources[].reused_from` den Lauf, der ihn gemeldet hat
(`run` im Plan), nicht den Lauf, aus dem der Folgelauf die Datei übernahm. So lässt sich der
Fund mit der Fix-Runde genau dieses Laufs abgleichen. Das `reused_from` des vereinigten Funds
ist das seiner ersten übernommenen Quelle. Pläne ohne `run` an den Funden (vor dieser Regel
geschrieben) nennen weiter den Lauf aus `file_keys`.

## Prüfen: `verify` und `verdict`

Mit `plan --verify`, im Profil `checkpoint` ohnehin (`verify: true` im Plan), braucht jeder
Fund ohne `evidence` ein Urteil, sonst ist der Lauf nicht vollständig. `verify` schreibt die
Aufträge auch ohne dieses Feld; nur `audit` und der Bericht verlangen die Urteile erst mit
`verify: true`.

| Schritt | Wirkung |
| --- | --- |
| `verify --run <lauf>` | schreibt je Fund ohne `evidence` und ohne Urteil `verify/<n>.md` (`n` = Nummer in `findings.json`) und löscht vorher die alten Aufträge (die Arbeitsordner bleiben); braucht ein `merge` zu diesem Plan; Text des Auftrags in [review-brief.md](review-brief.md#prüfer-auftrag-für-verify) |
| `verdict --run <lauf> <datei\|->` | nimmt `{"key", "urteil", "beleg"}` an und schreibt `verdicts/<key>.json` (mit `_meta`); `--number n` nur, wenn der Prüfer keinen `key` zurückgab: der Schlüssel kommt dann aus der Kopfzeile von `verify/<n>.md` |
| `merge --run <lauf>` | trägt `verdict` und `verdict_evidence` in `findings.json` ein |

- Der `key` ist ein Hash aus `file`, `line`, `summary` und `failure_scenario` des vereinigten
  Funds. Ändert ein späteres `merge` Text oder Zeile, ist es ein neuer Fund und offen. Das
  Urteil wirkt erst nach dem nächsten `merge`.
- `widerlegt` ohne `beleg` weist `verdict` ab, ebenso ein anderes Urteil als `bestätigt`,
  `widerlegt`, `unklar`. Ein zweites Urteil ersetzt das erste (so lässt sich ein `unklar`
  nachprüfen); das ersetzte bleibt unter `history`.
- Funde mit `evidence` gelten als belegt und bekommen keinen Auftrag. `findings.json` und der
  Bericht behalten jeden Fund samt Urteil; `fix-task` (subagent-dev) lässt `widerlegt` weg.
- `audit` meldet bei `verify: true` die Nummern ohne Urteil unter `unverified`, ein Urteil in
  `findings.json`, das nicht zu `verdicts/` passt (etwa von Hand geschrieben), unter
  `forged_verdicts` und ein Urteil, das `verdicts/` inzwischen überholt hat, unter
  `stale_verdicts` (`merge` fehlt). Alle drei machen `complete` zu `false`; nur `unverified`
  hängt an `verify: true`, `forged_verdicts` und `stale_verdicts` prüft `audit` immer.

## Bericht prüfen: die Einordnung

`report --run <lauf>` schreibt `report.md` ganz aus den Daten des Laufs; der Hauptagent schreibt
keine Zeile davon, sondern fügt nur den Abschnitt `## Einordnung` an. Ein erneutes `report`
ersetzt auch eine angefügte Einordnung.
`audit` vergleicht alles vor der ersten Zeile `## Einordnung` mit dem Text von `report`. Für
die Einordnung danach gelten zwei einfache Regeln. Vorher werden HTML-Kommentare `<!-- … -->`
entfernt, auch über mehrere Zeilen; Text davor und danach bleibt je auf seiner Zeile.
`<!--` und `-->` zählen nur außerhalb von Inline-Code: in einer Backtick-Spanne derselben
Zeile (`` `<!--` ``) sind sie Text.

- **Keine Vollständigkeit bei Lücken.** Meldet das Audit `missing`, `stale`,
  `lost_findings`, `unverified` (nur bei `verify: true`), `forged_verdicts` oder
  `stale_verdicts`, ist jede Zeile ein Eintrag in `report_mismatch`, die eines der Wörter
  `vollständig`, `fertig`, `komplett` (auch mit -e, -em, -en, -er, -es) als ganzes Wort
  enthält, Groß/Klein egal, und nicht zugleich `unvollständig`. Englische Wörter zählen
  nicht: ``audit meldet `complete: false` `` zitiert das Audit-Feld und meldet nicht.
  Es gibt keine Suche nach Verneinungen: „nicht vollständig“ meldet, „unvollständig“ nicht.
  „Vollständigkeit“ und „fertigstellen“ sind andere Wörter. „un-vollständig“
  ist nicht die Schreibweise `unvollständig` und meldet. „Die Abdeckung ist unvollständig;
  vollständig wird sie erst nach p3.“ meldet nicht.
- **Kurz bei einem Paket.** Bei `split: false` höchstens `EINORDNUNG_MAX_LINES` Textzeilen,
  ohne die Überschrift, ohne Leerzeilen und ohne Zeilen, die nach dem Entfernen der
  Kommentare leer sind.

Das Werkzeug gilt als `/code-review`, wenn sein Name (nach `record`) `/code-review` ist oder mit
`/code-review ` beginnt, etwa `/code-review high`; die Normalisierung steht unter „Werkzeugname
und Git Bash“. Dann steht im Bericht der Hinweis zu `--max-findings`. `record` verlangt dort
wie bei jedem Werkzeug mit Stufe eine `stufe`.

## Fortsetzen eines Laufs

`plan` hat kein `--run`. Ein Lauf entsteht nur durch ein erfolgreiches `plan`, und ein
gescheitertes `plan` hinterlässt keinen Laufordner. Fortgesetzt wird mit den folgenden
Befehlen und `--run <lauf>`, nie mit einem zweiten `plan` über denselben Bereich. Das gäbe
einen zweiten Lauf.

| Befehl | wiederholbar? |
| --- | --- |
| `counterparts --run <lauf>` | ja: vorhandene Bereiche bleiben, solange ihre Refs stehen, fehlende werden neu gebaut, `packets/*.md` überschrieben |
| `record --run <lauf> --packet <id> --tool <werkzeug> <datei>` | je Paket genau einmal; ein zweites Ergebnis wird abgewiesen |
| `merge --run <lauf>`, `verify --run <lauf>`, `report --run <lauf>`, `audit --run <lauf>` | ja |
| `verdict --run <lauf> <datei>` | je Fund beliebig oft; das jüngste Urteil gilt |

Welche Pakete noch fehlen, nennt `audit` unter `missing`. Nur diese Pakete werden noch
reviewt und mit `record` angenommen.

## Aufräumen: `cleanup`

| Aufruf | löscht |
| --- | --- |
| `cleanup --run <lauf>` | alle Refs unter `refs/deep-review/<lauf>/` |
| `cleanup --stale --run <lauf>` | die Refs aller anderen Läufe, die von `<lauf>` bleiben |
| `cleanup --stale` | alle Refs unter `refs/deep-review/` |

- Refs gelten für alle Worktrees eines Repos. `--stale` löscht auch die eines Laufs, der in
  einem anderen Worktree noch läuft.
- Danach steht in jedem betroffenen `plan.json` wieder `range: null` (nach Kräften). Ein
  späteres `counterparts` baut neu.
- Objekte, HEAD, Index, Arbeitsbaum und `.skills/cache/deep-review/` bleiben.
- `--stale` nur, wenn kein anderer Lauf offen ist.

## Ablage

| Was | Wo |
| --- | --- |
| Läufe | `.skills/cache/deep-review/<lauf>/` mit `plan.json`, `counterparts.json`, `packets/`, `results/`, `findings.json`, `verify/`, `verdicts/`, `report.md`, `audit.json` |
| Hilfscommits | `refs/deep-review/<lauf>/<id>/von` und `…/bis` im Git des Repos |
| Schutz vor `git add -A` | `.skills/cache/deep-review/.gitignore` mit dem Inhalt `*`; `plan` legt sie an, wenn sie fehlt, und nennt es in der Ausgabe. Die `.gitignore` des Repos, Arbeitsbaum, Index und HEAD bleiben unberührt |

Jede Datei des Skripts trägt eine Kopfzeile `<!-- skill: deep-review | schema: 1 | generated: …
-->` bzw. ein `_meta`; das notierte Kommando ist relativ zum Skill-Ordner.

## Werkzeugname und Git Bash

`record --tool` nimmt `code-review` und `security-review` ohne Schrägstrich. Git Bash unter
Windows schreibt ein Argument, das mit `/` beginnt, in einen Windows-Pfad um
(`C:/Program Files/Git/code-review`), und die Kopfzeile des Berichts passte dann nie. `record`
speichert `/code-review` und `/security-review`, auch aus einem so umgeschriebenen Pfad, und der
Bericht übernimmt das gespeicherte Werkzeug aus `results/<id>.json` (`_meta.tool`).
„Review ohne /code-review“ und „Review ohne /security-review“ beginnen nicht mit `/` und bleiben,
wie sie sind. Eine Stufe im Namen (`code-review high`) wird zu `/code-review high`
normalisiert.

Exit-Codes aller Befehle: 0 Erfolg, 1 Fehler (Meldung auf stderr) oder `audit` mit Lücke
(`audit.json` ist trotzdem geschrieben), 2 falscher Aufruf.
