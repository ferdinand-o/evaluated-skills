<!-- skill: visual-summary | schema: 1 | generated: visual-summary skill (Format: decision-memo, Medium: markdown) -->
*Decision-Memo · {{DATUM}} · Slug: {{SLUG}}*

# {{ENTSCHEIDUNGSFRAGE}}

## Optionen

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
