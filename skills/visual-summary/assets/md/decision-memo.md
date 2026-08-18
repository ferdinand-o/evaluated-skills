<!-- skill: visual-summary | schema: 1 | generated: visual-summary skill (Format: decision-memo, Medium: markdown) -->
*Decision-Memo · {{DATUM}} · Slug: {{SLUG}}*

# {{ENTSCHEIDUNGSFRAGE}}

## Optionen

<!-- Referenzmarken ([^n]) sind dokumentweit fortlaufend nummeriert (1, 2, 3, ...)
     — NICHT pro REPEAT-Block neu bei 1, auch nicht über Optionen, Risiken und
     Quellenliste hinweg. {{REF_ID}}, {{REF_ID_2}}, {{REF_ID_3}} sind
     Slot-Namen für verschiedene Textstellen innerhalb einer Zeile, KEIN
     eigener Zähler — jeder Slot bekommt trotzdem die nächste fortlaufende
     Dokumentnummer. Derselbe Beleg behält seine Nummer bei jeder Erwähnung.
     Die Quellenliste am Dokumentende enthält jede vergebene Nummer genau
     einmal; jede im Text vergebene Marke hat dort ihren Eintrag. Gegenprobe
     im Selbst-Audit, SKILL.md. -->
| Option | Für | Gegen | Aufwand/Risiko |
| --- | --- | --- | --- |
<!-- REPEAT: option (max. vier Zeilen — mehr heißt: nicht genug vorgefiltert) -->
| {{OPTION_NAME}} | {{OPTION_FUER}}[^{{REF_ID}}] | {{OPTION_GEGEN}}[^{{REF_ID_2}}] | {{OPTION_AUFWAND}} |
<!-- /REPEAT -->

## Empfehlung

> {{EMPFEHLUNG_TEXT}}[^{{REF_ID_3}}]

## Risiken

<!-- REPEAT: risiko ("Keine erkennbaren Risiken." wenn keine da sind, nicht weglassen) -->
- {{RISIKO_TEXT}}[^{{REF_ID}}]
<!-- /REPEAT -->

## Offene Punkte

{{OFFENE_PUNKTE}}

## Quellen

<!-- REPEAT: quelle -->
[^{{REF_ID}}]: {{LOCATOR}} — „{{AUSZUG}}"{{KONFIDENZ_ZUSATZ}}
<!-- /REPEAT -->
