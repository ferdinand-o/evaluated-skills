<!-- skill: sql-schema-architect | schema: 1 | generated: von Hand nach assets/table-template.md ausgefüllt -->
# Tabelle: orders

## Zweck
Speichert Kundenbestellungen für den Checkout-Flow.

## Owner
Commerce-Team

## Erwartetes Wachstum
Bestandstabelle in Produktion, unbekannte aktuelle Größe — als potenziell
groß behandelt (R5).

## Hauptzugriffsmuster
Lookup per `id` beim Checkout-Abschluss; Listenabfragen per `status` im
Bestell-Dashboard.

## Soft-Delete
Nein — Bestellungen werden storniert (`status`), nie gelöscht.

## FK-Verhalten
Aktuell keine Fremdschlüssel.
