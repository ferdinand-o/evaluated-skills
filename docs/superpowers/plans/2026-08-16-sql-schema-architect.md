# sql-schema-architect Implementation Plan

**Ziel:** Eine Skill, die Postgres-Schema-Entwürfe und Alembic-Migrationen
maschinell prüft statt sie der Disziplin des Nutzers zu überlassen. Das
Schema ist eine dokumentierte Entscheidung (Steckbrief pro Tabelle,
maschinell auf Existenz/Vollständigkeit geprüft), die Migration ein
reversibler, lock-bewusster Schritt (Gefahrenklasse pro Operation,
maschinell klassifiziert).

**Spec:** `specs/Spec 08 – sql-schema-architect.md`, gebunden an
`specs/Spec 00 – skill-foundation.md`. Sechs Entscheidungen aus dem Auftrag
sind bindend (R1–R6, siehe unten) und werden hier nicht neu verhandelt.

**Warum diese Skill anders behandelt wird:** Sie berät über Operationen, die
in Produktion Tabellen sperren und Daten unwiederbringlich löschen. Zwei
Konsequenzen zwingend für die Implementierung:

1. **Nichts wird importiert.** `migration_gate.py` liest eine
   Alembic-Revision mit `ast`, führt sie nie aus. `gen_erd.py` liest
   SQLAlchemy-Models mit `ast`, importiert sie nie — sonst öffnet die Skill
   eine DB-Verbindung, während sie nur das Schema erfassen soll.
2. **Unbekanntes ist nie grün.** `op.execute()` mit rohem SQL ist statisch
   nicht klassifizierbar. Es wird als eigener Zustand geführt
   (`review_required`), der ein sonst grünes/gelbes Urteil nie überschreibt
   in Richtung „bestanden" — ein Gate, das Unbekanntes für harmlos hält, ist
   schlimmer als keines.

## Bindende Entscheidungen (aus dem Auftrag, nicht verhandelbar)

- **R1** Preset ist JSON (`assets/conventions.json`), kein YAML — PyYAML
  fehlt hier. Projekt-Override unter `.skills/sql-schema-architect/conventions.json`.
  `assets/table-template.md` bleibt Markdown.
- **R2** `migration_gate.py` bleibt Tier 1, analysiert die Revision statisch
  mit `ast`. Kein Import der Revision.
- **R3** `gen_erd.py` liest Models statisch mit `ast` (Tier 1, nicht Tier 2
  wie in Spec 08 vermerkt — sqlalchemy ist hier nicht installiert und der
  Import-Verbot-Grund zieht ohnehin stärker). Statisch nicht Erreichbares
  wird sichtbar im Diagramm markiert, nie stillschweigend weggelassen.
- **R4** `lint_schema.py` ist Tier 1 im Kern (die conventions.json-Prüfungen
  brauchen kein sqlfluff), sqlfluff ist eine optionale Erweiterung mit
  sichtbarer Degradationszeile, wenn es fehlt (Spec 00 §3/§4 — kein stilles
  Überspringen).
- **R5** Keine Zeilenzahl-Schwelle für „große Tabelle". Jede Bestandstabelle
  gilt als potenziell groß, solange der Nutzer nichts anderes sagt. Die
  Gefahrenklasse hängt an der Operation, nicht an einer geratenen Größe.
- **R6** G3 nur mit vom Nutzer installiertem Hook (`assets/hooks/migration-gate.json`,
  nie automatisch installiert). Ohne Hook ist das Gate G2. Die geltende
  Härte steht in **jeder** Ausgabe von `migration_gate.py`, mechanisch
  ermittelt (Hook-Datei in `.claude/settings*.json` gefunden oder nicht),
  nicht nur behauptet.

## Architektur

```
skills/sql-schema-architect/
├── SKILL.md
├── references/
│   ├── conventions.md
│   ├── migration-safety.md      # Klassifikationstabelle, Marker-Konventionen, Rezepte
│   └── modeling.md              # inkl. Array-statt-Relation-Antipattern (Eval 2)
├── assets/
│   ├── conventions.json
│   ├── table-template.md
│   └── hooks/migration-gate.json
└── scripts/
    ├── gen_erd.py
    ├── lint_schema.py
    └── migration_gate.py
evals/sql-schema-architect/evals.json
evals/fixtures/{production-trap,array-vs-relation,missing-downgrade,convention-violations,green-additive}/
tests/test_sql_schema_architect_{migration_gate,gen_erd,lint_schema}.py
```

### Datenfluss und Artefakte (Spec 00 §1)

| Artefakt | Klasse | Ort | committed |
| --- | --- | --- | --- |
| `docs/schema/<table>.md` (Steckbrief) | Wissen | `docs/schema/` | ja |
| `docs/schema/erd.md` (generiertes ER-Diagramm) | Wissen | `docs/schema/` | ja |
| `.skills/sql-schema-architect/conventions.json` (Override) | Konfiguration | `.skills/<skill>/` | ja |
| `.skills/cache/migration-gate-report.json` | Ephemera | `.skills/cache/` | nein |
| `.skills/cache/lint-schema-report.json` | Ephemera | `.skills/cache/` | nein |

Alle Markdown-Artefakte tragen die Kopfzeile aus `docs/artifact-header.md`
als erste nicht-leere Zeile. JSON-Artefakte tragen `_meta` nach Konvention.

### migration_gate.py — Kerndesign

**Extraktion (ast, kein Import):**
- `ast.parse` auf die Revisionsdatei.
- `upgrade()`/`downgrade()` per Funktionsname finden.
- Innerhalb `upgrade()`: jeder `ast.Call`, dessen `func` ein `Attribute` mit
  `value == Name("op")` ist, wird als Operation erfasst (`op.add_column`,
  `op.alter_column`, `op.create_index`, `op.execute`, …).
- Argumente werden nicht `literal_eval`t (das würde an `sa.Column(...)`,
  `sa.String(50)` scheitern), sondern per `ast.unparse()` in Text verwandelt
  und mit gezielten Regeln (Substring/Regex auf den unparsten Text)
  klassifiziert — z. B. `nullable=False` als Kwarg-Text, `String(` vs.
  `Text` im Typ-Ausdruck, `postgresql_concurrently=True`.
- `op.create_table(...)`-Aufrufe im selben Revisions-Body sammeln die
  Tabellennamen, die *in dieser Revision neu entstehen* — Operationen auf
  ihnen sind nie „Bestandstabelle", selbst wenn sie sonst riskant wären
  (z. B. NOT NULL beim Anlegen ist keine Rewrite-Gefahr).

**Klassifikation je Operation** (Tabelle lebt in `migration-safety.md`,
gespiegelt als Python-Datenstruktur):

| Operation | grün | gelb | rot |
| --- | --- | --- | --- |
| `create_table` | immer | | |
| `add_column` nullable=True | immer | | |
| `add_column` nullable=False + `server_default` | | immer (PG-Version unbekannt → konservativ) | |
| `add_column` nullable=False ohne Default, auf Bestandstabelle | | | immer |
| `create_index` mit `postgresql_concurrently=True` | immer | | |
| `create_index` auf in-Revision neuer Tabelle | immer | | |
| `create_index` ohne CONCURRENTLY auf Bestandstabelle | | | immer |
| `drop_index` | | immer | |
| `drop_column` | | immer (Auflage: Datenverlust, downgrade kann Daten nicht wiederherstellen) | |
| `create_foreign_key` auf in-Revision neuer Tabelle | immer | | |
| `create_foreign_key` auf Bestandstabelle | | | immer (validiert alle Zeilen) |
| `alter_column` nur `nullable=True` (lockern) | immer | | |
| `alter_column` `nullable=False` auf Bestandsspalte | | | immer |
| `alter_column` mit `type_=` (Typänderung) | | | immer (konservativ, keine Sonderfälle geraten) |
| `rename_table` / Spalten-Rename | | immer (Auflage: rückwärtskompatibler Rollout) | |
| `bulk_insert` | | immer (Auflage: in Batches) | |
| `drop_table` | | | immer (irreversibel, unabhängig von Größe) |
| `execute(...)` (rohes SQL) | — nie automatisch grün — | **unknown/review_required**, immer separat ausgewiesen |
| unbekannte `op.*`-Methode | — nie automatisch grün — | **unknown/review_required** |

Gesamtklasse einer Revision = Maximum der bekannten Klassifikationen
(rot > gelb > grün). `unknown`-Operationen fließen **nicht** in dieses
Maximum als „grün" ein; sie werden separat gelistet und heben den Gesamt-
Status auf mindestens `review_required`, selbst wenn alle bekannten
Operationen grün wären.

**Kontraktprüfungen (mechanisch, führen zu `violation`):**
- `upgrade()` fehlt in der Datei → Verstoß.
- `downgrade()` fehlt, oder Body ist leer (`pass`/nur Docstring) → Verstoß,
  **außer** begründete Einbahn-Migration: Body besteht (neben optionalem
  Docstring) einzig aus `raise NotImplementedError("<Grund>")` mit
  Grund-Text > 5 Zeichen. Das ist idiomatisches Alembic-Muster für
  bewusst irreversible Migrationen — kein neuer Kommentar-Dialekt.
- Gesamtklasse `rot` ohne **Mehrschritt-Plan-Marker**: eine Zeile im
  Datei-Text, die `Mehrschritt-Plan:` (case-insensitiv) enthält, gefolgt
  von mehr als zehn Zeichen Beschreibung auf derselben Zeile. Fehlt der
  Marker bei roter Klassifikation → Verstoß, **abgelehnt**.

**Exit-Codes:** `0` bestanden (grün/gelb, Verträge erfüllt, keine unknown
Operationen), `1` Verstoß (Kontrakt verletzt), `2` `review_required`
(keine Verträge verletzt, aber mind. eine `unknown`-Operation — niemals
stillschweigend als bestanden gemeldet).

**Härte-Erkennung (R6):** `detect_hook_installed(repo)` liest
`.claude/settings.json` und `.claude/settings.local.json` (beide optional,
fehlend ⇒ kein Hook) und sucht nach dem literalen Pfad-Fragment
`sql-schema-architect/scripts/migration_gate.py` innerhalb eines
`PreToolUse`-Hook-Eintrags. Gefunden → „Härte: G3 (Hook aktiv) — blockiert.",
sonst „Härte: G2 (kein Hook installiert) — meldet, blockiert nicht.". Diese
Zeile steht in jeder Text- und JSON-Ausgabe (`hardness`-Feld), nicht nur in
der Doku.

**Hook-Modus:** `--hook-check` liest ein JSON-Objekt von stdin (Claude Code
PreToolUse-Kontrakt: `tool_name`, `tool_input.command`). Ist `tool_name`
nicht `Bash` oder matcht `command` kein Alembic-Apply-Muster
(`alembic\s+upgrade`), Exit 0 (keine Meinung, durchlassen). Sonst werden
alle `.py`-Dateien unter `--versions-dir` (Default `alembic/versions`)
klassifiziert; jede `violation` oder jedes `review_required` blockiert
(Exit 2, Begründung auf stderr) — nur ein vollständig grünes/gelbes Bild
ohne unknown-Operationen lässt den Bash-Aufruf durch.

### gen_erd.py — Kerndesign

- `ast.parse` auf eine Datei oder alle `.py` unter einem Verzeichnis.
- Klassen mit `__tablename__ = "<literal>"` als Modelle erkannt.
  `__tablename__` als Nicht-Literal (z. B. `f"{prefix}_users"`, ein
  Funktionsaufruf) → Tabelle **nicht** übersprungen, sondern mit
  Klassenname und Warnung „`__tablename__` nicht statisch auflösbar"
  aufgenommen.
- Spalten: `Assign`/`AnnAssign` im Klassenkörper, deren Wert ein Call zu
  `Column(...)` oder `mapped_column(...)` ist. Typ-Ausdruck per
  `ast.unparse()` auf das erste positionale Argument (oder die Annotation
  bei `mapped_column`). `ForeignKey(...)` als verschachtelter Call in den
  Argumenten → Ziel-Tabelle.Spalte extrahiert (Text-Parse des ersten
  Strings, z. B. `"users.id"`).
- `relationship(...)`-Aufrufe liefern zusätzliche benannte Kanten
  (Zielklasse als erstes Argument), ergänzen aber nie die primären
  FK-Kanten — die bleiben die verlässliche Quelle.
- Mixins/Vererbung über eine Ebene hinaus (Basisklasse ist nicht direkt
  `Base`/`DeclarativeBase`, und die Klasse selbst hat kein eigenes
  `__tablename__`) → Klasse als „nicht auflösbare Mixin-Kette" markiert,
  im Diagramm als Kommentarzeile sichtbar, nicht stillschweigend
  ausgelassen.
- Output: Mermaid `erDiagram`-Text plus ein Warnungs-Block als
  `%%`-Kommentare am Ende. Geschrieben nach `docs/schema/erd.md` mit
  Artefakt-Kopfzeile.

### lint_schema.py — Kerndesign

Mechanisch, ohne sqlfluff, immer lauffähig:

1. **Naming** — Tabellen-/Spaltennamen aus `gen_erd`s Scan-Funktion
   wiederverwendet; Regex `^[a-z][a-z0-9_]*$` prüft snake_case. Nicht
   automatisiert: grammatische Singular/Plural-Erkennung — die ist ohne
   Wörterbuch nicht zuverlässig entscheidbar und würde eine Assertion
   erzeugen, die nichts bewacht (siehe `brief-common.md`). Das bleibt
   dokumentierte Präferenz in `conventions.md`, kein Lint-Befund.
2. **Typen** — `String(n)`/`VARCHAR` im unparsten Typ-Text ohne
   dokumentierten Grund (kein begleitender Kommentar `# grund:`) → Befund.
   `DateTime` ohne `timezone=True` → Befund.
3. **Pflichtspalten** — `created_at`/`updated_at` (aus `conventions.json`)
   fehlen auf einer Tabelle → Befund.
4. **FK-Verhalten** — `ForeignKey(...)`-Call ohne `ondelete`-Kwarg → Befund.
5. **Steckbrief-Vertrag** — für jede gefundene Tabelle: existiert
   `docs/schema/<table>.md`? Trägt sie die Artefakt-Kopfzeile? Sind die
   Pflicht-Sektionen (Zweck, Owner, Erwartetes Wachstum,
   Hauptzugriffsmuster) vorhanden **und** nicht leer? Fehlt eine Datei
   oder Sektion → Befund. Hat die Tabelle einen Index (aus dem Modell-Scan,
   `Index(...)`/`index=True`) und die Hauptzugriffsmuster-Sektion ist leer
   → eigener Befund „Index ohne benanntes Zugriffsmuster".
6. **sqlfluff (optional)** — `shutil.which("sqlfluff")`. Gefunden: auf
   `*.sql`-Dateien im Scan-Pfad angewendet, Befunde gemappt. Fehlt:
   Ausgabe trägt wörtlich „sqlfluff nicht installiert — SQL-Formatprüfung
   übersprungen, Kernprüfungen liefen trotzdem" (Spec 00 §3/§4).

Exit-Code `0` ohne Befunde, `1` mit mindestens einem Befund (G2 — meldet,
blockiert nicht). Schreibt `.skills/cache/lint-schema-report.json`.

## Edge Cases, die explizit getestet werden

- Revision ganz ohne `upgrade()`.
- Mehrere Operationen gemischter Klassen in einer Revision → höchste
  gewinnt.
- `op.execute()` mit rohem SQL → `review_required`, nie `pass`, auch wenn
  alle anderen Operationen grün sind.
- Unbekannte `op.*`-Methode (Tippfehler, neue Alembic-Version) → dieselbe
  Behandlung wie `execute()`.
- `downgrade()` mit `pass` (leer) vs. mit `raise NotImplementedError("...")`
  (begründeter Einwegpfad) vs. ganz fehlend.
- `add_column` NOT NULL auf einer Tabelle, die in derselben Revision per
  `create_table` entsteht → grün, nicht rot.
- `create_index` ohne CONCURRENTLY auf einer neu erstellten vs. einer
  Bestandstabelle.
- Hook-Erkennung: Datei fehlt, Datei ohne Treffer, Datei mit Treffer in
  `settings.json` vs. `settings.local.json`.
- `gen_erd`: `__tablename__` als f-String (nicht auflösbar), Mixin ohne
  eigenes `__tablename__`, leeres Modell-Verzeichnis.
- `lint_schema`: Tabelle ganz ohne Steckbrief-Datei, Steckbrief mit leerer
  Pflichtsektion, Steckbrief mit allen Sektionen aber fehlender Kopfzeile.

## Evals

Fixtures brauchen `"git": true`, wo Artefakte im Repo erwartet werden.
Assertions hängen an das, was nur diese Skill erzeugt: die
`migration-gate-report.json`-Klassifikation, den Steckbrief unter
`docs/schema/` samt Kopfzeile, `docs/schema/erd.md`, die
`lint-schema-report.json`-Befundliste.

1. **`production-trap`** (behavior) — Fixture mit Bestandstabelle
   (Model + vorherige Migration), Prompt verlangt NOT-NULL-Spalte ohne
   Default auf dieser Tabelle. Muss: Mehrschritt-Muster im Ergebnis
   (mehrere Revisionsdateien oder expliziter Plan), `migration_gate`-Report
   zeigt nicht `pass` für einen naiven Einzelschritt.
2. **`array-vs-relation`** (behavior) — Schema-Wunsch mit `tag_ids
   integer[]`-artigem Vorschlag im Prompt. Muss: Antwort verweist auf
   Junction-Tabelle/FK statt Array, `modeling.md`-Anti-Pattern greift.
3. **`missing-downgrade`** (contract) — Migration ohne `downgrade()`
   vorgelegt. Muss: `migration-gate-report.json` meldet den Verstoß
   namentlich.
4. **`convention-violations`** (contract) — Modell mit `varchar(50)` und
   camelCase-Spalte. Muss: `lint-schema-report.json` enthält beide Befunde,
   ohne dass das Modell selbst suchen musste.
5. **`green-additive`** (contract, Pflicht-Anti-Zeremonie) — additive,
   locksichere Spalte auf einer neuen Tabelle. Muss: kurze Antwort, keine
   ausgebreitete Gefahren-Tour; `migration-gate-report.json` zeigt `pass`
   mit ausschließlich grünen Operationen.

## Task-Reihenfolge

1. Plan committen (dieser Schritt).
2. `assets/conventions.json`, `assets/table-template.md` — sie tragen alle
   drei Skripte.
3. `migration_gate.py` + `tests/test_sql_schema_architect_migration_gate.py`
   (TDD: Extraktion → Klassifikation → Kontraktprüfungen → Hook-Erkennung →
   `--hook-check` → CLI/Report). Größtes und riskantestes Stück zuerst.
4. `gen_erd.py` + `tests/test_sql_schema_architect_gen_erd.py`.
5. `lint_schema.py` + `tests/test_sql_schema_architect_lint_schema.py`
   (importiert Scan-Funktionen aus `gen_erd.py`, keine Duplikation).
6. `references/migration-safety.md`, `references/conventions.md`,
   `references/modeling.md`.
7. `SKILL.md`, `assets/hooks/migration-gate.json`.
8. `evals/sql-schema-architect/evals.json` + fünf Fixtures. Nur mechanisch
   validieren (`load_evals`), nicht ausführen.
9. Volle Testsuite grün, README/Routing-Matrix ergänzen falls nötig,
   Abschlussbericht schreiben.

Commits klein und häufig, nach jedem grün laufenden Schritt.
