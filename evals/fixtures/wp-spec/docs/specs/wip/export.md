<!-- skill: feature-spec | schema: 1 | generated: feature-spec Draft für "CSV-Export" -->
# Feature: CSV-Export der Berichte

## Problem
Berichte gibt es nur als Text auf der Konsole. Wer sie in einer Tabellenkalkulation
weiterrechnen will, tippt sie ab.

## Non-Goals
- Kein Excel-Format, keine Formatierung der Zahlen.

## Annahmen
- Annahme: Trennzeichen ist das Komma — widersprich, falls nein.

## Ansatz
`src/report.py` liefert die Zeilen, `src/cli.py` bekommt eine Option; ein neues Modul
`src/export.py` schreibt die Datei mit `csv.writer`.

## Akzeptanzkriterien

### CSV hat eine Kopfzeile
- Given ein Bericht mit zwei Zeilen
- When er als CSV geschrieben wird
- Then trägt die erste Zeile der Datei die Spaltennamen

### Option --csv schreibt die Datei
- Given das Kommando `report`
- When es mit `--csv out.csv` läuft
- Then liegt `out.csv` mit allen Zeilen des Berichts vor

### Leerer Bericht ergibt nur die Kopfzeile
- Given ein Bericht ohne Zeilen
- When er als CSV geschrieben wird
- Then enthält die Datei genau eine Zeile mit den Spaltennamen

## Offene Fragen
- Soll `--csv -` auf die Standardausgabe schreiben? — Entscheider: Produkt.

---
Quellen: src/report.py, src/cli.py · Übersprungene Quellen: keine
