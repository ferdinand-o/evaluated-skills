# Spec 08: sql\-schema\-architect — Postgres\-Schema und sichere Migrationen

Skill\-Spezifikation · Zyklus 8/14 · Entscheidung: PostgreSQL\-first, Alembic, Query\-Tuning ausgelagert · Abgeglichen mit Spec 00

## Problem

Schema\-Design passiert heute in Prosa und landet ungeprüft als CREATE TABLE; Migrationen entstehen ohne Down\-Pfad und ohne Gefahrenbewusstsein — die Migration, die auf leerer Dev\-DB harmlos aussieht und in Produktion die Tabelle sperrt (NOT NULL ohne Default, Typ\-Änderung, Index ohne CONCURRENTLY), ist der Klassiker. Konventionen driften pro Tabelle, und niemand dokumentiert, wozu eine Tabelle existiert und wie sie wächst. „database\-migration" steht entsprechend seit Monaten unbesetzt auf den Community\-Gap\-Listen.

## Constraints

PostgreSQL\-first — Tiefe vor Breite (Lock\-Verhalten, CONCURRENTLY, partielle Indizes konkret; andere DBs später als Adapter\-Reference). Migrations\-Tooling: Alembic/SQLAlchemy; das Destruktiv\-Gate analysiert Alembic\-Operationen statt rohem SQL, weil `op.*`\-Aufrufe maschinenlesbar sind — deterministische Erkennung statt Regex\-Raterei. Query\-/Index\-Tuning per EXPLAIN ist ausgelagert (spätere Geschwister\-Skill); Index\-Entscheidungen beim *Entwurf* gehören aber hierher. Portables Frontmatter.

## Approach

**Das Schema ist eine dokumentierte Entscheidung, die Migration ein reversibler, lock\-bewusster Schritt — beides maschinell geprüft.**

**Skill\-Struktur:**

```
sql-schema-architect/
├── SKILL.md                 (Doktrin, Workflow, Contract, Gefahren-Übersicht)
├── references/
│   ├── conventions.md       (Preset erklärt: Naming, Typen, Keys, Soft-Delete)
│   ├── migration-safety.md  (Lock-Verhalten je Operation, sichere Muster, Backfill-Rezepte)
│   └── modeling.md          (Normalisierung vs. Lesepfad, JSONB-Grenzen, Partitionierung ab wann)
├── assets/
│   ├── conventions.yaml     (Preset; Projekt-Override: .skills/sql-schema-architect/)
│   ├── table-template.md    (Tabellen-Steckbrief: Zweck, Owner, Wachstum, Zugriffsmuster)
│   └── hooks/migration-gate.json  (G3-Snippet, Spec 00 §4 — nie automatisch installiert)
├── scripts/
│   ├── gen_erd.py           (Tier 2; Models/DDL → Mermaid-ER-Diagramm, generiert statt gezeichnet)
│   ├── lint_schema.py       (Tier 2: sqlfluff + conventions.yaml-Checks; G2)
│   └── migration_gate.py    (Tier 1; Alembic-Revision → Gefahrenklasse + Auflagen; G3 mit Hook)
└── evals/evals.json
```

**Konventions\-Preset (Defaults, überschreibbar):** snake\_case, Singular\-Tabellennamen verboten oder erlaubt — einmal entschieden in conventions.yaml, nie pro Tabelle; `bigint identity` als Default\-PK (UUID nur mit dokumentiertem Grund); `timestamptz` statt `timestamp`; `text` statt `varchar(n)` ohne echten Grund; Pflicht\-Spalten `created_at`/`updated_at`; Soft\-Delete ist eine explizite Entscheidung pro Tabelle (Steckbrief\-Feld), kein Reflex; FK\-Verhalten (ON DELETE) immer explizit.

**Workflow Entwurf:** Domänenmodell → `gen_erd.py` erzeugt das ER\-Diagramm aus den SQLAlchemy\-Models (generiert, nie von Hand — Drift\-Schutz wie bei Spec 10s Architektur\-Graphen) → DDL/Models nach Preset → pro Tabelle ein Steckbrief aus `table-template.md`\: Zweck, Owner, erwartetes Wachstum, Hauptzugriffsmuster (Letzteres begründet die Index\-Entscheidungen beim Entwurf). Die Steckbriefe leben nach Spec 00 als Wissens\-Artefakte in `docs/schema/`\; damit sie nicht verrotten, prüft `lint_schema.py` ihre Existenz und Vollständigkeit mit — die Pflege ist damit maschinell eingefordert statt Disziplinfrage. Contract: keine Tabelle ohne Steckbrief, kein Index ohne benanntes Zugriffsmuster.

**Workflow Migration:** Alembic\-Revision erzeugen (up *und* down — ein leerer `downgrade()` ist ein Regelverstoß, außer als begründete Einbahn\-Migration markiert) → `migration_gate.py` klassifiziert jede Operation nach Gefahrenklasse: **grün** (additiv, locksicher), **gelb** (kurze Locks — Auflagen: `lock_timeout` setzen, Off\-Peak\-Hinweis), **rot** (Tabellen\-Rewrite oder Langzeit\-Lock — Pflicht: sicheres Mehrschritt\-Muster aus migration\-safety.md, z. B. Spalte nullable ergänzen → Backfill in Batches → NOT NULL via validiertem CHECK\-Constraint; Index nur CONCURRENTLY). Rote Migration ohne Mehrschritt\-Plan wird abgelehnt. Dies ist neben `check_ledger.py` das einzige **G3**\-Gate der Sammlung (Spec 00 §4): Mit dem installierten Hook aus `assets/hooks/` blockiert es tatsächlich; ohne Hook bleibt es G2 und meldet nur. Welche Härte gerade gilt, gehört sichtbar in die Ausgabe — bei irreversiblem Schaden darf niemand raten müssen.

**Anti\-Rationalisierungs\-Tabelle (Auszug):** „Dev\-DB war in 2 Sekunden durch" → leere DB beweist nichts; die Gefahrenklasse zählt. „Down\-Pfad schreibe ich, wenn ich ihn brauche" → dann existiert er nicht, wenn du ihn brauchst. „varchar(255), wie immer" → wie immer ist kein Grund; Preset sagt text. „Der Index schadet ja nicht" → jeder Index kostet Schreiblast; ohne Zugriffsmuster kein Index.

**Evals:** (1) Die Produktions\-Trap: NOT\-NULL\-Spalte auf große Bestandstabelle — kommt das Mehrschritt\-Muster statt der naiven Ein\-Zeilen\-Migration? (2) Schema\-Wunsch mit verstecktem 1:n\-Fehler (Array\-Spalte, wo Relation hingehört) — greift modeling.md? (3) Migration ohne downgrade() — schlägt der Contract an? (4) Konventions\-Bruch (varchar(50), camelCase) — findet lint\_schema.py alles, ohne dass das LLM danach suchen muss?

## Alternatives considered

Multi\-DB\-Generik verworfen: Die gefährlichen Details (Locks, Rewrites) sind DB\-spezifisch; Generik erzeugt falsche Sicherheit — Adapter\-References können später folgen (Promotion\-Muster wie Spec 05). Rohe SQL\-Migrationspaare statt Alembic verworfen (Nutzer\-Stack ist Alembic; das Gate profitiert von maschinenlesbaren op.\*\-Aufrufen). Integriertes Query\-Tuning verworfen — eigene Spur mit eigenem Werkzeug (EXPLAIN ANALYZE braucht eine laufende DB mit realistischen Daten; anderes Betriebsmodell als Entwurfs\-Arbeit). pgTAP\-Tests je Migration erwogen, zugunsten des Gates vertagt.

## Out of scope

Query\-/Index\-Optimierung am Bestand (Geschwister\-Skill), MySQL/SQLite/andere DBs, ORM\-Wahl\-Beratung, Daten\-Seeding, Backup/Restore\-Prozeduren, DB\-Betrieb (Vacuum, Monitoring).

## Open questions

Schwelle, ab der „große Tabelle" gilt (Zeilenzahl aus Statistiken vs. pauschal ab Klasse gelb)?

## Next steps

conventions.yaml und migration\-safety.md zuerst (sie tragen Gate und Entwurf); migration\_gate.py mit den drei Gefahrenklassen implementieren und gegen bekannte Fallen testen; gen\_erd.py auf SQLAlchemy\-Models; die Produktions\-Trap als ersten Eval fahren; Description schärfen (triggert bei Schema/Migration/Tabellen\-Entwurf, routet Query\-Tuning explizit aus).
