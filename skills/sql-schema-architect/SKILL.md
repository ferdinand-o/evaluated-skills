---
name: sql-schema-architect
description: Use when designing a Postgres schema or writing/reviewing an Alembic migration — classifies every migration operation by lock/rewrite danger, enforces reversibility, and requires a documented table steckbrief before any table ships. Triggers include "Migration schreiben", "Schema entwerfen", "Tabelle anlegen", "NOT NULL hinzufügen", "Spalte migrieren", "ER-Diagramm". Not for query/index tuning on existing data (a sibling skill, not yet built) and not for generic ORM/framework advice unrelated to schema or migrations.
---

# sql-schema-architect — Schema ist Entscheidung, Migration ist Risiko

**Das Schema ist eine dokumentierte Entscheidung, die Migration ein
reversibler, lock-bewusster Schritt — beides maschinell geprüft.**
PostgreSQL-first, Alembic/SQLAlchemy. Diese Skill ist die gefährlichste der
Sammlung: Sie berät über Operationen, die in Produktion Tabellen sperren und
Daten unwiederbringlich löschen.

## Die eiserne Regel

```
KEINE MIGRATION OHNE migration_gate.py. KEINE TABELLE OHNE STECKBRIEF.
```

Weder eine Revision ausführen noch Modelle importieren — beides öffnet
Datenbankverbindungen oder wendet Änderungen an. Alles hier liest statisch
mit `ast`.

## Ablauf Entwurf

1. Domänenmodell besprechen, `references/modeling.md` gegen versteckte
   1:n/n:m-Fehler prüfen (Array-Spalte statt Relation ist der Klassiker).
2. Models nach `assets/conventions.json` schreiben (Projekt-Override unter
   `.skills/sql-schema-architect/conventions.json`).
3. `python "${CLAUDE_SKILL_DIR}/scripts/gen_erd.py" <models-pfad>`
   erzeugt `docs/schema/erd.md` — generiert, nie von Hand gezeichnet.
   Statisch nicht Auflösbares (dynamische `__tablename__`, Mixin-Ketten)
   erscheint sichtbar als Warnung im Diagramm, nie stillschweigend weg.
4. Pro Tabelle ein Steckbrief aus `assets/table-template.md` nach
   `docs/schema/<table>.md`: Zweck, Owner, erwartetes Wachstum,
   Hauptzugriffsmuster (begründet jeden Index).
5. `python "${CLAUDE_SKILL_DIR}/scripts/lint_schema.py" <models-pfad>`
   — Naming, Typen, Pflichtspalten, FK-Verhalten, Steckbrief-Vollständigkeit.
   Meldet sqlfluff-Verfügbarkeit **immer sichtbar**, auch wenn es fehlt.
   Spalten im SQLAlchemy-2.0-`Mapped[T]`-Stil ohne explizites Typ-Argument
   sind für die Typ-Prüfung ebenfalls sichtbar unauflösbar (Befund
   `type_coverage`) statt stillschweigend als geprüft zu gelten.

## Ablauf Migration

1. Alembic-Revision erzeugen, `upgrade()` **und** `downgrade()`. Ein leerer
   `downgrade()` ist ein Regelverstoß, außer als begründete Einbahn-Migration
   (`raise NotImplementedError("<Grund>")`, siehe `references/migration-safety.md`).
2. `python "${CLAUDE_SKILL_DIR}/scripts/migration_gate.py" <revision-datei-oder-verzeichnis>`
   klassifiziert jede Operation: **grün** (additiv, locksicher), **gelb**
   (kurzer Lock — `lock_timeout` setzen, Off-Peak-Hinweis), **rot**
   (Tabellen-Rewrite/Langzeit-Lock).
3. **Rot ohne Mehrschritt-Plan-Marker wird abgelehnt**, ebenso ein Marker
   ohne erkennbare Struktur (mindestens zwei Begriffe aus
   nullable/backfill/batch/constraint/valid/concurrently/revision — reine
   Länge reicht nicht mehr, siehe `references/migration-safety.md`). Auch
   mit einem strukturierten Plan wird eine rote Migration nicht
   automatisch `pass`: der Inhalt ist statisch nicht vollständig prüfbar,
   die Ausgabe meldet `review_required`, manuelle Freigabe nötig.
4. `op.execute()` mit rohem SQL, jede unbekannte `op.*`-Methode und jede
   Spaltendefinition, die der Scanner nicht auflösen kann (z. B. eine
   `add_column`-Spalte aus einem Funktionsaufruf statt Inline-Call oder
   lokaler Variable), sind **nicht bewertbar** — die Ausgabe meldet
   `review_required`, niemals `pass`. Ebenso: enthält `upgrade()`
   erkennbaren Code, aus dem der Scanner aber keine einzige Operation
   lesen konnte (Aufrufe über `self.`/Modul-Attribute, Variablen oder
   Imports werden nicht verfolgt — siehe `references/migration-safety.md`),
   wird das als eigener Verstoß gemeldet, nie als „0 Operationen, pass".
5. Die Ausgabe von `migration_gate.py` nennt in jedem Lauf die geltende
   Härte: **G2** ohne installierten Hook (meldet, blockiert nicht) oder
   **G3** mit installiertem Hook aus `assets/hooks/migration-gate.json`
   (blockiert `alembic upgrade` tatsächlich). Dieser Hook wird nie
   automatisch installiert — der Nutzer übernimmt ihn bewusst: zuerst
   `mkdir -p .claude/hooks && cp "${CLAUDE_SKILL_DIR}/scripts/migration_gate.py" .claude/hooks/`,
   dann das Fragment in `.claude/settings.json` mischen. Fehlt die Kopie, meldet der
   Hook „ungeprüft" und hält nichts an. Bekannte
   Grenze: Indirektion über ein Makefile-Target oder CI-Skript, dessen
   Bash-Aufruf den Text „alembic upgrade" nicht enthält, umgeht den Hook.

## Contract

- Keine Tabelle ohne Steckbrief unter `docs/schema/`, keine Steckbrief-
  Datei ohne Artefakt-Kopfzeile und die vier Pflichtsektionen mit Inhalt.
- Kein Index ohne benanntes Zugriffsmuster — `lint_schema.py` prüft das an
  der Hauptzugriffsmuster-Sektion, nicht am Wortlaut.
- Jede Migration braucht `downgrade()`, begründet oder nicht.
- Jede rote Migration braucht den strukturierten Mehrschritt-Plan-Marker;
  auch damit bleibt sie `review_required`, nie automatisch `pass`.
- Jeder Fremdschlüssel braucht ein explizites `ondelete`.
- `op.execute()` ist niemals automatisch grün — manuelle Prüfung ist
  Pflicht, keine Kür.

## Leerfälle

- **Kein Modell-Verzeichnis vorhanden:** `gen_erd.py`/`lint_schema.py`
  melden 0 Tabellen, kein Fehler — es gibt nichts zu diagrammieren oder zu
  prüfen. Sag das, statt eine leere Modellierung zu erfinden.
- **Keine Migrations-Dateien im Zielpfad:** `migration_gate.py` bricht mit
  Exit 1 und einer expliziten Meldung ab, statt stillschweigend „bestanden"
  zu melden — leer ist kein grünes Urteil.
- **sqlfluff fehlt:** `lint_schema.py` sagt das wörtlich in jeder Ausgabe;
  die Konventions-Prüfungen laufen trotzdem vollständig (R4).
- **Kein Hook installiert:** Härte ist G2, das steht in jeder
  `migration_gate.py`-Ausgabe — nie nur in der Doku behauptet.
- **Additive, locksichere Änderung auf einer neuen Tabelle:** kein
  Gefahren-Repertoire ausbreiten. Kurz antworten, `migration_gate.py`
  laufen lassen, fertig.

## Anti-Rationalisierungs-Tabelle

| Gedanke | Realität |
| --- | --- |
| „Auf der Dev-DB war es in zwei Sekunden durch" | Eine leere DB beweist nichts. Die Gefahrenklasse zählt, nicht die gemessene Zeit. |
| „Den Down-Pfad schreibe ich, wenn ich ihn brauche" | Dann existiert er nicht, wenn du ihn brauchst. `downgrade()` jetzt oder begründet als Einbahn. |
| „varchar(255), wie immer" | Wie immer ist kein Grund. Preset sagt `text`. |
| „Der Index schadet ja nicht" | Jeder Index kostet Schreiblast. Ohne Zugriffsmuster im Steckbrief kein Index. |
| „Das `op.execute()` ist nur ein Kommentar-Update, harmlos" | Statisch nicht unterscheidbar von gefährlichem SQL. Manuell prüfen, immer. |
| „Kein Hook installiert, also ist es eh nur eine Empfehlung" | G2 meldet trotzdem — die Klassifikation gilt unabhängig von der Härte. |
| „Ein Array für die Tags reicht doch" | Versteckte n:m-Beziehung ohne Integrität, Index oder Metadaten-Spalten — siehe `modeling.md`. |

## Abgrenzung

- **Query-/Index-Tuning am Bestand** (EXPLAIN ANALYZE, laufende Produktions-
  DB mit echten Daten) ist eine eigene, nicht gebaute Geschwister-Skill —
  andere Betriebsart, braucht eine Verbindung, die diese Skill bewusst nie
  öffnet.
- Generische ORM-Wahl-Beratung, Daten-Seeding, Backup/Restore und DB-Betrieb
  (Vacuum, Monitoring) sind hier nicht behandelt.
- Diese Skill ist PostgreSQL-first; andere Datenbanken sind out of scope.
