<!-- skill: sql-schema-architect | schema: 1 | generated: von Hand nach assets/table-template.md ausgefüllt -->
# Tabelle: <name>

## Zweck
<Wofür existiert diese Tabelle — ein bis zwei Sätze, keine Spaltenliste.>

## Owner
<Team oder Person, die bei Fragen zu dieser Tabelle zuständig ist.>

## Erwartetes Wachstum
<Größenordnung und Wachstumsrichtung, so genau wie bekannt — "unbekannt,
Bestandstabelle" ist eine gültige, ehrliche Angabe (siehe R5: keine
geratene Zeilenzahl-Schwelle).>

## Hauptzugriffsmuster
<Die Abfragen, die diese Tabelle tatsächlich bedienen muss — sie begründen
jeden Index. Kein Index ohne einen Eintrag hier.>

## Soft-Delete
<Ja/Nein und Begründung. Kein Reflex, sondern eine bewusste Entscheidung
pro Tabelle.>

## FK-Verhalten
<ON DELETE-Verhalten je Fremdschlüssel, explizit benannt — nicht dem
Datenbank-Default überlassen.>
