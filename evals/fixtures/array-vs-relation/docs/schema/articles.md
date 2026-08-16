<!-- skill: sql-schema-architect | schema: 1 | generated: von Hand nach assets/table-template.md ausgefüllt -->
# Tabelle: articles

## Zweck
Redaktionelle Artikel der Plattform.

## Owner
Content-Team

## Erwartetes Wachstum
Mittleres, stetiges Wachstum.

## Hauptzugriffsmuster
Lookup per `id` beim Anzeigen; Liste sortiert nach `created_at` auf der
Startseite.

## Soft-Delete
Nein — Artikel werden veröffentlicht oder gelöscht, kein Papierkorb.

## FK-Verhalten
Aktuell keine Fremdschlüssel.
