<!-- skill: visual-summary | schema: 1 | generated: visual-summary skill (Format: one-pager, Medium: markdown) -->
*One-Pager · {{DATUM}} · Slug: {{SLUG}}*

# {{KERNTHESE}}

## Belege

<!-- REPEAT: beleg (genau drei, wenn das Material sie hergibt — sonst weniger, nie erfunden) -->
- {{BELEG_TEXT}}[^{{REF_ID}}]
<!-- /REPEAT -->

## {{CHART_TITEL}}

<!-- Chart-Slot: nur befüllen, wenn ein Datenpunkt-Set eine Frage beantwortet, die
     die Kernthese aufwirft (references/charts.md). Sonst diese gesamte Sektion
     inklusive Überschrift entfernen — keine Alibi-Tabelle. Ein Chart ist im
     Markdown immer eine Tabelle der Datenpunkte, nie ein Bild. -->
| {{SPALTE_1}} | {{SPALTE_2}} |
| --- | --- |
<!-- REPEAT: chart_row -->
| {{ROW_LABEL}} | {{ROW_WERT}}[^{{REF_ID}}] |
<!-- /REPEAT -->

## Quellen

<!-- REPEAT: quelle -->
[^{{REF_ID}}]: {{LOCATOR}} — „{{AUSZUG}}"{{KONFIDENZ_ZUSATZ}}
<!-- /REPEAT -->
