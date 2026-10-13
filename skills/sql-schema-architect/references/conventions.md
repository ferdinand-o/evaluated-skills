# Das Konventions-Preset

`assets/conventions.json` ist die eine Entscheidung pro Feld, einmal
getroffen, nie pro Tabelle neu verhandelt. JSON, nicht YAML (R1) — die
Python-Stdlib kennt kein YAML, und PyYAML ist in dieser Umgebung nicht
installiert. `lint_schema.py` liest das Preset direkt.

## Override

Ein Projekt überschreibt das Default-Preset unter
`.skills/sql-schema-architect/conventions.json` (Spec 00 §1, Klasse
Konfiguration — nutzergepflegt, committed). Das Override ersetzt einzelne
Top-Level-Schlüssel, es muss das Preset nicht vollständig duplizieren:

```json
{ "required_columns": ["created_at"] }
```

überschreibt nur `required_columns`; `types`, `naming` usw. bleiben aus dem
Default-Preset erhalten.

## Die Felder

### `naming`

- **`table_case` / `column_case`**: `snake_case`, mechanisch geprüft
  (`^[a-z][a-z0-9_]*$`). Ein Verstoß wie `userEmail` oder `UserTable`
  erzeugt einen Lint-Befund.
- **`table_plurality_preference`**: `plural` als Präferenz — dokumentiert,
  **nicht** mechanisch erzwungen. Grammatische Singular/Plural-Erkennung
  ist ohne Wörterbuch nicht zuverlässig automatisierbar (`status`, `data`
  sind im Englischen ambig); eine Regel, die das trotzdem versucht, wäre
  eine Assertion, die nichts zuverlässig bewacht. Die Präferenz gehört in
  die Entwurfs-Konversation, nicht in `lint_schema.py`.

### `types`

- **`primary_key_style: bigint_identity`** — Default-PK ist `bigint
  identity`. UUID ist erlaubt, aber nur mit dokumentiertem Grund im
  Tabellen-Steckbrief (`uuid_primary_key_allowed_with_reason`).
- **`timestamp_type: timestamptz`**, `reject_datetime_without_timezone` —
  `DateTime` ohne `timezone=True` wird geflaggt. Naive Timestamps sind der
  Klassiker für stille Zeitzonenfehler.
- **`string_type_default: text`**, `reject_varchar` — jede
  `String(n)`/`VARCHAR(n)`-Nutzung wird geflaggt, ohne Ausnahme-Mechanismus
  per Kommentar-Marker. Ein Kommentar, der die Prüfung stillschweigend
  abschaltet, wäre selbst die Falle, vor der `brief-common.md` warnt: eine
  Assertion, die durch eine triviale Umformulierung umgangen werden kann.
  Ein begründeter `varchar`-Einsatz gehört ins PR-Review, nicht in einen
  Bypass-Kommentar.

### `required_columns`

Spaltennamen, die jede Tabelle tragen muss — Default `created_at`,
`updated_at`. `lint_schema.py` prüft nur Anwesenheit, nicht Typ oder
Nullability der Spalte selbst (das deckt `types` bereits ab, wenn die
Spalte existiert).

### `soft_delete`

`mode: explicit_per_table` — es gibt keine globale Soft-Delete-Vorgabe.
Jede Tabelle entscheidet bewusst im Steckbrief (`assets/table-template.md`,
Sektion „Soft-Delete"), kein Reflex à la „hat ja jede Tabelle eine
`deleted_at`-Spalte".

### `foreign_keys`

`ondelete_required: true` — jeder `ForeignKey(...)`-Aufruf ohne `ondelete`
erzeugt einen Lint-Befund. Dem Datenbank-Default zu überlassen ist keine
Entscheidung, sondern das Fehlen einer.

### `table_steckbrief`

`required_sections` und `path_template` — steuert, wo `lint_schema.py` nach
Steckbriefen sucht und welche Sektionen es verlangt. Siehe
`assets/table-template.md` für die Vorlage und den Contract-Abschnitt der
SKILL.md für die Konsequenz einer fehlenden Sektion.
