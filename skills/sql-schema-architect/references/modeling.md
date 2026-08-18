# Modellierung: Normalisierung, JSONB-Grenzen, Partitionierung

## Das Array-statt-Relation-Antipattern

**Erkennungsmerkmal:** Eine Array-Spalte, deren Elemente IDs oder Namen
einer anderen Entität sind — `tag_ids integer[]`, `category_names text[]`,
`assignee_ids bigint[]`, `role_names text[]`. Das ist keine Datenmodellierung,
das ist eine versteckte 1:n- oder n:m-Beziehung, die die Datenbank nicht
als solche kennt.

**Warum das ein Fehler ist, nicht nur Geschmack:**

- Kein Fremdschlüssel, also keine referenzielle Integrität — ein gelöschtes
  Tag hinterlässt eine tote ID im Array, unbemerkt.
- Kein Index, der eine einzelne Zuordnung effizient findet
  (`WHERE tag_id = ANY(tags)` scannt; ein GIN-Index hilft nur für exakte
  Array-Operatoren, nicht für Joins mit Tag-Metadaten).
- Keine Spalten an der Beziehung selbst — sobald ein Tag ein Erstellungs-
  datum oder eine Sortierposition braucht, gibt es dafür keinen Platz.
- `JOIN`, `GROUP BY`, `COUNT() ... GROUP BY tag` werden unnötig umständlich
  (`unnest()` überall).

**Das richtige Muster:**

- **1:n** (eine Entität gehört zu genau einer anderen, z. B. `orders.user_id`
  zeigt auf `users.id`): eine Fremdschlüssel-Spalte auf der n-Seite. Kein
  Array nötig.
- **n:m** (z. B. Artikel haben mehrere Tags, Tags gehören zu mehreren
  Artikeln): eine Junction-Tabelle (`article_tags` mit `article_id`,
  `tag_id`, beide als Fremdschlüssel, zusammengesetzter Primärschlüssel oder
  eigener `id`). Das ist der Fall, den ein Array am häufigsten fälschlich
  ersetzt.

**Wann ein Array trotzdem legitim ist:** Werte ohne eigene Identität, die
nie einzeln abgefragt, verknüpft oder mit Metadaten versehen werden —
z. B. `preferred_languages text[]` mit ISO-Codes, die nie in eine
`languages`-Tabelle mit eigenen Zeilen aufgelöst werden. Der Test: *Wird
dieser Wert jemals mit einem `JOIN` verknüpft oder braucht er eine eigene
Spalte?* Wenn ja, ist es keine Werteliste, sondern eine Relation.

## Normalisierung vs. Lesepfad

Normalisierung ist der Default, keine Ideologie. Denormalisieren ist eine
bewusste, dokumentierte Entscheidung (gehört in den Steckbrief unter
„Hauptzugriffsmuster"), wenn ein konkreter Lesepfad das rechtfertigt — ein
Dashboard, das pro Anfrage fünf Tabellen joinen müsste, für einen Wert, der
sich selten ändert. Ohne einen benannten Lesepfad ist Denormalisierung nur
vorgezogene Komplexität ohne Gegenwert.

## JSONB-Grenzen

JSONB ist geeignet für:

- Wirklich variable, pro Zeile unterschiedliche Attribute (Formular-
  Antworten mit dynamischen Feldern, Webhook-Payloads, Audit-Snapshots).
- Daten, die nie gefiltert, gejoint oder aggregiert werden — nur gelesen
  und angezeigt.

JSONB ist **nicht** geeignet, sobald eines davon zutrifft:

- Ein Feld wird regelmäßig in `WHERE`- oder `JOIN`-Bedingungen verwendet →
  eigene Spalte, ggf. mit Index.
- Das Schema der JSONB-Struktur ist für alle Zeilen identisch → das ist
  kein variables Attribut, das ist eine Tabelle, die noch keine Spalten
  bekommen hat.
- Referenzielle Integrität wird gebraucht (ein Feld im JSONB zeigt auf die
  ID einer anderen Tabelle) → das ist wieder das Array-Antipattern in
  JSONB-Verkleidung.

## Partitionierung — ab wann

Auch hier keine Zeilenzahl-Schwelle (konsistent mit R5 bei Migrationen).
Partitionierung lohnt sich bei einem qualitativen Signal, nicht bei einer
geratenen Zahl:

- Abfragen filtern fast immer auf denselben Bereich (Zeitraum, Mandant) und
  könnten Partitionen komplett überspringen (Partition Pruning).
- Wartungsoperationen (Löschen alter Daten, Reindexierung) sollen pro
  Partition statt auf der Gesamttabelle laufen.
- Unbegrenztes Wachstum ohne natürliches Ende (Zeitreihen, Ereignis-Logs).

Ohne mindestens eines dieser Signale ist Partitionierung vorgezogene
Komplexität — Indizes und ein sauberes Schema lösen die meisten
Performance-Probleme, bevor Partitionierung nötig wird.
