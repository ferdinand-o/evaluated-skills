# Delta-Modus: Wissensdatei-Schema und Differenz-Recherche

Eine Datei pro Thema, kein Themenbaum (R10). Flach bleiben, bis es weh tut, statt eine
Hierarchie zu erfinden, bevor es Inhalte gibt — dieselbe Regel gilt in dieser Sammlung
schon für `docs/decisions.md` und `docs/debugging/INDEX.md`.

## Ort

`.skills/verified-research/research/<thema>.md`, projektlokal, sobald
`.skills/verified-research/` im Projekt existiert — sonst
`~/.skills/verified-research/research/<thema>.md`
(`scripts/registry.py` implementiert diese Auflösung in `resolve_base_dir()`, dieselbe
Logik gilt für das Register). `<thema>` ist ein kurzer, sprechender Slug
(Kleinbuchstaben, Bindestriche) — kein UUID, keine Zeitstempel im Dateinamen.

## Kopfzeile

Erste nicht-leere Zeile, nach der allgemeinen Artefakt-Konvention:

```
<!-- skill: verified-research | schema: 1 | generated: python skills/verified-research/scripts/registry.py --repo . topics -->
```

## Sektionen

```
# <Thema>

<!-- skill: verified-research | schema: 1 | generated: ... -->

## Bekannt

- <Aussage>. [Tier <1-3>, Quelle: <adresse>] (Stand: <Datum>)
...

## Neu seit <Datum des letzten Standes>

- <Aussage>. [Tier <1-3>, Quelle: <adresse>] (Stand: <Datum>)
...

## Offene Fragen

- <Frage, die die letzte Recherche nicht klären konnte>
...
```

`## Bekannt` überschreibt bei jedem Lauf nicht die Vorläufer-Fakten — sie bleiben stehen
(mit ihrem ursprünglichen Stand-Datum), es sei denn, `spotcheck.py` degradiert sie oder
die neue Recherche widerlegt sie explizit (dann Vermerk direkt am Claim, nicht
kommentarlos gestrichen). `## Neu` ist nur bei tatsächlichen Neuigkeiten vorhanden —
ohne welche endet die Wissensdatei nach `## Bekannt` (ggf. `## Offene Fragen`), und der
Bericht sagt das kurz und explizit statt eine leere Sektion zu erzeugen.

## Ablauf im Delta-Lauf

1. Wissensdatei lesen, falls vorhanden. Das „Stand"-Datum der jüngsten Zeile ist der
   Ausgangspunkt für „was ist seither passiert".
2. Register-Phase + freie Suche laufen **nur** auf die Differenz: neue Entwicklungen,
   geänderte Sachlage, die in „Offene Fragen" notierten Lücken. Nicht die gesamte
   Wissensdatei neu recherchieren — das ist der Fehler, den die Anti-Rationalisierungs-
   Tabelle in SKILL.md („Delta sparen wir uns, ich recherchiere frisch") benennt.
3. Ergebnis in `## Neu seit <Datum>` schreiben, `## Bekannt` unverändert lassen (bis auf
   Degradierungen aus Schritt 4).
4. `spotcheck.py` läuft wie gehabt auch über neue *und* alte Claims, wenn die alte
   Quelle sich seither geändert haben könnte (z. B. eine Web-Seite ohne Versionierung).
5. Wissensdatei speichern, Bericht trennt „Bekannt" von „Neu" in der gleichen
   Überschriften-Sprache wie die Datei — der Mensch soll den Unterschied ohne
   Vergleichsarbeit sehen.

## Ohne Neuigkeiten

Bestätigt die Differenz-Recherche nichts Neues, bleibt `## Neu` weg und der Bericht ist
ein Satz: „Keine Neuigkeiten seit <Datum> — <Kernfakt kurz wiederholt>." Das ist der
Erfolgsfall dieser Skill, kein unvollständiges Ergebnis, und rechtfertigt keine
Zeremonie.

## 30-Themen-Warnung

`scripts/registry.py --repo . topics` zählt `*.md`-Dateien unter `research/` und warnt
ab `TOPIC_WARNING_THRESHOLD` (30). Die Warnung ist eine Empfehlung an den Nutzer, selbst
über eine Gliederung zu entscheiden — die Skill gliedert nicht automatisch um. Flach
bleibt der Standard, auch über der Schwelle, bis der Nutzer etwas anderes anordnet.
