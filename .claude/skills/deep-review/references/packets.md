# Pakete: Plan, Schnittregel, Bereiche, Folgeläufe

Referenz für den Hauptagenten. Was `review_kit.py plan` zählt und schneidet, was der Reviewer
je Paket sieht, wie ein Folgelauf Funde übernimmt und wie ein Lauf fortgesetzt und aufgeräumt
wird. Was im Paketblock steht, beschreibt `counterparts.md`.

## Grenzwerte

Am Kopf von `review_kit.py` (E7). Der Bericht nennt sie.

| Konstante | Wert | Bedeutung |
| --- | --- | --- |
| `SPLIT_AT` | 800 | bis hierher geänderte Zeilen: ein Paket über den Originalbereich (`--split-at N` ersetzt den Wert) |
| `PACKET_SIZE` | 600 | obere Paketgröße beim Teilen; `packet_size` = kleiner von 600 und `split_at` |
| `BLOCK_MAX_CHARS` | 30000 | Zeichen je `packets/<id>.md`, Kopfzeile eingeschlossen; darüber wird gekappt, mit Zahl |
| `MERGE_LINE_GAP` | 3 | `merge`: Funde derselben Datei mit höchstens diesem Abstand werden ein Fund |
| `RAISE_DEPTH` | 2 | `raise`-Stellen transitiv im selben Modul bzw. in derselben Unit |
| `FLAG_DEPTH` | 4 | Weg eines geänderten Schlüsselwort-Arguments durch so viele Funktionen |
| `AMBIGUOUS_MAX` | 3 | mehr gleichnamige Definitionen ohne Importbezug: nichts statt Raten, gezählt |
| `REPORT_BASE_LINES` | 20 | Anti-Zeremonie-Fall: Bericht höchstens 20 Zeilen plus eine je Fund (Kopfzeile nicht gezählt) |

## Bereich und Zählung

`review_kit.py plan --range <bereich> [--profile standard|checkpoint] [--focus bugs|security|quality] [--split-at N] [--since <lauf>[,<lauf>…]] [--soll-file <datei>] [--with-tests]`

| Eingabe | gilt als |
| --- | --- |
| `BASIS..ZIEL` | gezählt ab der Merge-Basis bis ZIEL; Commit-Messages aus `git log BASIS..ZIEL` |
| eine Revision `X` | `X^..X` (erster Parent); beim Wurzel-Commit leerer Baum..`X` |
| ohne `--range` | `HEAD`, also der letzte Commit |
| `A...B` | abgelehnt, zwei Punkte zählen schon ab der Merge-Basis |

- Gezählt werden hinzugefügte plus gelöschte Zeilen aus `git diff --numstat --no-renames`.
  Eine Umbenennung ist eine gelöschte und eine neue Datei. Binärdateien zählen 0, `.skills/`
  zählt nie.
- `plan.json` hält den Bereich aufgelöst fest: `range` als SHAs `<basis>..<ziel>` (beim
  Wurzel-Commit nur `<ziel>`, dazu `root: true`), `base` (Merge-Basis oder leerer Baum),
  `target`, `log_base` (aufgelöste BASIS, beim Wurzel-Commit `null`).
- Profil `checkpoint` geht nur mit Fokus `bugs` und nur mit `--soll-file`. Ohne die Datei
  bricht `plan` mit Exit 1 ab und legt keinen Lauf an. `--soll-file` steht danach in
  `_meta.soll_file`.
- Ohne reviewte Datei bricht `plan` mit „nichts zu reviewen“ ab und legt keinen Lauf an.

Die Ausgabe beginnt mit `Lauf: <lauf>`. Die Lauf-ID hat die Form
`<JJJJ-MM-TT>-<HHMMSS>-<kurz-sha>-<4 Zufallszeichen>` (UTC). Zwei Läufe in derselben Sekunde
bekommen verschiedene IDs. Alles liegt unter `.skills/cache/deep-review/<lauf>/`.

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
5. Eine Datei wird nie geteilt. Eine Datei über `packet_size` ist ein eigenes Paket.
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
| `tools/gen_tables.py` | 650 | `p4` | Datei über 600, eigenes Paket |

Je Paket stehen im Plan `id`, `files`, `changed_lines`, `range` und `reused_from` (immer
`null`, übernommen wird je Datei, siehe Folgeläufe).

## Paket-Bereich: was der Reviewer sieht

`review_kit.py counterparts --run <lauf>` baut zuerst je Paket den reviewbaren Bereich und trägt
ihn als `range` ins Paket ein. Danach schreibt es `packets/<id>.md`. Die Ausgabe nennt je Paket
den Bereich. Den gibst du an `/code-review`.

| Fall | `range` des Pakets | Hilfscommits |
| --- | --- | --- |
| `split: false`, kein Wurzel-Commit | Originalbereich `<basis>..<ziel>` | keine |
| Fokus `security` (`s1`), kein Wurzel-Commit | Originalbereich | keine |
| `split: true` | `<von>..<bis>` | ja |
| Wurzel-Commit (`root: true`) | `<von>..<bis>`, auch bei einem Paket | ja, Basis ist der leere Baum |
| nach `--since` mit Übernahme (ohne Übernahme bleibt der Plan unverändert) | `<von>..<bis>`, auch bei einem Paket | ja |

Die Hilfscommits liegen unter `refs/deep-review/<lauf>/<id>/von` und `…/bis`. Gebaut werden
sie über einen temporären Index mit der Identität `deep-review <deep-review@localhost>`.
HEAD, Index und Arbeitsbaum bleiben unberührt.

- `von`: Baum von ZIEL, die Paketdateien auf dem Stand der Basis (fehlt eine dort, wird sie
  entfernt). Parent ist ZIEL, die Message lautet `deep-review <lauf> <id>: Basis`.
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
`notes`. Das ist der Anti-Zeremonie-Fall: ein `/code-review` über den Originalbereich, ein
Bericht von höchstens `REPORT_BASE_LINES` Zeilen plus einer je Fund.

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
   er hat sie selbst übernommen), und zwar mit demselben `key`.
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

## Fortsetzen eines Laufs

`plan` hat kein `--run`. Ein Lauf entsteht nur durch ein erfolgreiches `plan`, und ein
gescheitertes `plan` hinterlässt keinen Laufordner. Fortgesetzt wird mit den folgenden
Befehlen und `--run <lauf>`, nie mit einem zweiten `plan` über denselben Bereich. Das gäbe
einen zweiten Lauf.

| Befehl | wiederholbar? |
| --- | --- |
| `counterparts --run <lauf>` | ja: vorhandene Bereiche bleiben, solange ihre Refs stehen, fehlende werden neu gebaut, `packets/*.md` überschrieben |
| `record --run <lauf> --packet <id> --tool <werkzeug> <datei>` | je Paket genau einmal; ein zweites Ergebnis wird abgewiesen |
| `merge --run <lauf>`, `audit --run <lauf>` | ja |

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

Exit-Codes aller Befehle: 0 Erfolg, 1 Fehler (Meldung auf stderr) oder `audit` mit Lücke
(`audit.json` ist trotzdem geschrieben), 2 falscher Aufruf.
