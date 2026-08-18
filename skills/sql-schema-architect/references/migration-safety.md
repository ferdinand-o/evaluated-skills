# Migrationssicherheit: Lock-Verhalten, Marker, Rezepte

Diese Tabelle ist keine unabhängige Meinung — sie beschreibt exakt, was
`scripts/migration_gate.py` mechanisch klassifiziert. Weicht ein Verhalten
hier von der Skript-Ausgabe ab, ist die Skript-Ausgabe die Wahrheit.

## Warum keine Zeilenzahl-Schwelle (R5)

Die Gefahrenklasse hängt an der **Operation**, nicht an einer geratenen
Tabellengröße. Ein Tabellen-Rewrite ist gefährlich, weil er die Tabelle
umschreibt — ob sie heute zehn oder zehn Millionen Zeilen hat, weiß die
Skill nicht und kann es nicht wissen, ohne die Produktionsdatenbank zu
befragen. Jede Bestandstabelle gilt als potenziell groß, solange der
Nutzer nichts anderes sagt. Eine geratene Schwelle erzeugt genau die
falsche Sicherheit: „auf der Dev-DB war es in zwei Sekunden durch."

## Klassifikationstabelle je Operation

| `op.*`-Aufruf | Bedingung | Klasse | Begründung |
| --- | --- | --- | --- |
| `create_table` | immer | grün | keine bestehenden Zeilen betroffen |
| `add_column` | `nullable=True` | grün | additiv, Metadaten-only |
| `add_column` | `nullable=False` + `server_default` gesetzt, Bestandstabelle | gelb | kurzer Lock zur Validierung, PG-Version-abhängig ob Metadaten-only — konservativ als gelb behandelt |
| `add_column` | `nullable=False`, kein Default, Bestandstabelle | **rot** | vollständiger Table-Rewrite möglich |
| `add_column` | jede Variante auf einer Tabelle, die in derselben Revision per `create_table` entsteht | grün | keine bestehenden Zeilen, Rewrite-Gefahr entfällt |
| `create_index` | `postgresql_concurrently=True` | grün | kein Langzeit-Lock auf Schreibzugriffe |
| `create_index` | auf einer in derselben Revision neu erstellten Tabelle | grün | keine bestehenden Zeilen |
| `create_index` | ohne CONCURRENTLY, Bestandstabelle | **rot** | sperrt Schreibzugriffe für die gesamte Bauzeit |
| `drop_index` | immer | gelb | kurzer exklusiver Lock |
| `drop_column` | immer | gelb | Lock kurz, aber **irreversibler Datenverlust** — `downgrade()` kann die Spalte neu anlegen, nicht ihren Inhalt |
| `create_foreign_key` | Quelltabelle in derselben Revision neu erstellt | grün | keine bestehenden Zeilen zu validieren |
| `create_foreign_key` | Bestandstabelle | **rot** | validiert beim Anlegen alle Zeilen unter Lock |
| `alter_column` | nur `nullable=True` (lockern) | grün | reine Metadatenänderung |
| `alter_column` | `nullable=False`, Bestandsspalte | **rot** | Full-Table-Scan unter Lock, sofern kein validiertes CHECK-Constraint vorausging |
| `alter_column` | `type_=` gesetzt (Typänderung) | **rot** | konservativ als Rewrite behandelt — keine Sonderfälle geraten |
| `alter_column` / `rename_table` | Umbenennung | gelb | bricht laufenden Code, der den alten Namen nutzt |
| `bulk_insert` | immer | gelb | Schreiblast, sollte in Batches laufen |
| `drop_table` | immer | **rot** | irreversibel, unabhängig von der aktuellen Zeilenzahl (R5) |
| `execute(...)` (rohes SQL) | immer | **nicht bewertbar** | statisch nicht klassifizierbar — wird nie automatisch grün, siehe unten |
| unbekannte `op.*`-Methode | immer | **nicht bewertbar** | dieselbe Behandlung wie `execute()` — neue Alembic-Version, Tippfehler, o. Ä. |

Mehrere Operationen gemischter Klassen in einer Revision: **die höchste
gewinnt** (rot > gelb > grün). `execute()` und unbekannte Methoden fließen
nie als grün in dieses Maximum ein — sie heben den Gesamtstatus auf
mindestens `review_required`, selbst wenn jede bekannte Operation grün ist.

## Der review_required-Zustand ist kein Fehler des Gates

Ein Gate, das Unbekanntes für harmlos hält, ist schlimmer als keines. Trifft
`migration_gate.py` auf `op.execute()`, eine unbekannte Methode, eine
Spaltendefinition, die es nicht auflösen kann (siehe unten), oder einen
roten Plan, dessen Inhalt es nicht verifizieren kann, meldet es **nicht
bewertbar, manuell prüfen** — unabhängig davon, wie harmlos die Sache
tatsächlich aussieht. Exit-Code `2` (nicht `0`) macht das mechanisch
sichtbar. Das ist Fleiß, kein Bug: keiner dieser Fälle gilt automatisch als
bestanden.

## Sichtbarkeitsgrenzen des Scanners — wo „nicht gesehen" beginnt

Ein internes Review (Runde 2) fand drei Wege, auf denen eine gefährliche
Operation am Scanner vorbeikam, ohne dass er das meldete — die schwerste
Fehlerrichtung bei dieser Skill. Alle drei sind behoben; die verbleibenden
Grenzen stehen hier, damit niemand mehr raten muss, was der Scanner sieht.

**Hilfsfunktionen im selben Modul werden verfolgt, alles andere nicht.**
Ruft `upgrade()` eine andere, im selben File definierte Funktion auf
(`def upgrade(): _apply()`), folgt der Scanner ihr rekursiv, mit
Zyklenschutz. Was er **nicht** verfolgt: `self.methode()`,
`modul.funktion()`, Aufrufe über eine Variable, Methoden auf Klassen,
importierte Funktionen, dynamisch aufgelöste Aufrufe (`getattr(...)`).
Solche Fälle bleiben für den Scanner unsichtbar — die Operationen darin
tauchen nirgends auf, weder grün noch `unknown`.

**Deshalb ist „0 gefundene Operationen" bei einem nicht-leeren `upgrade()`
ein eigener Befund, kein `pass`.** Enthält `upgrade()` erkennbar Code
(mehr als nur `pass` oder einen Docstring), liefert der Scanner aber keine
einzige `op.*`-Operation, wird die Revision **abgelehnt** — mit der
Begründung „nicht analysiert, keine automatische Freigabe möglich". Eine
Revision, die ausschließlich über nicht verfolgte Wege operiert, sieht
sonst wie eine leere, harmlose Revision aus; das ist sie nicht.

**`add_column` löst einfache lokale Variablen auf, mehr nicht.**
`op.add_column("orders", sa.Column("status", sa.Text(), nullable=False))`
und

```python
col = sa.Column("status", sa.Text(), nullable=False)
op.add_column("orders", col)
```

werden identisch klassifiziert — die zweite Form wurde vor der Fix-Runde
fälschlich grün, weil `nullable=False` nur im inneren `Column(...)`-Aufruf
stand. Aufgelöst werden nur Zuweisungen **direkt im Funktionsrumpf**, nicht
in `if`/`for`-Blöcken und nicht über mehrere Funktionen hinweg. Was nicht
aufgelöst werden kann (Rückgabewert eines Funktionsaufrufs, Zuweisung in
einem verschachtelten Block, Import), ist `unknown` — nie grün, weil
`nullable`/`server_default` dann nicht einsehbar sind.

## Kontrakt: downgrade() und der Mehrschritt-Plan-Marker

**Leerer `downgrade()` ist ein Regelverstoß**, außer als begründete
Einbahn-Migration markiert. Die zulässige Form ist idiomatisches Alembic:

```python
def downgrade():
    raise NotImplementedError("Datenverlust wäre irreversibel, siehe ADR-12")
```

Der Grund-Text muss mehr als fünf Zeichen tragen — ein bloßes
`raise NotImplementedError` ohne Begründung zählt weiterhin als leer.

**Rote Migrationen brauchen einen Mehrschritt-Plan-Marker mit erkennbarer
Struktur, nicht bloß Länge.** Eine Zeile irgendwo in der Revisionsdatei
(Kommentar oder Docstring), die `Mehrschritt-Plan:` enthält, gefolgt von
mindestens zwei unterschiedlichen Begriffen aus diesem Vokabular:
`nullable`, `backfill`, `batch`, `constraint`, `valid`, `concurrently`,
`revision`. Eine erste Fassung dieser Prüfung verlangte nur mehr als zehn
beliebige Zeichen — ein interner Review zeigte, dass der Kommentar
`# Mehrschritt-Plan: siehe unten unten` (19 hohle Zeichen) dieselbe rote
Migration ohne jeden echten Plan durchließ. Die Struktur-Prüfung schließt
diese Lücke, ohne mehr Genauigkeit zu behaupten, als sie hat:

```python
# Mehrschritt-Plan: Spalte nullable ergänzt (Revision abc123), Backfill in
# Batches (Revision def456), NOT NULL über validiertes CHECK-Constraint (diese Revision)
def upgrade():
    op.alter_column("orders", "customer_id", nullable=False)
```

Ohne Marker wird eine rote Migration **abgelehnt** (`violation`). Mit
Marker, aber ohne die geforderte Struktur, ebenfalls **abgelehnt** — die
Form allein reicht nicht. Mit Marker **und** erkennbarer Struktur wird sie
**nicht** automatisch „pass": Ob der beschriebene Plan tatsächlich zu den
vorliegenden Operationen passt, ob die genannten Revisionen existieren, ob
das Backfill wirklich in Batches läuft — das kann statische Analyse nicht
prüfen. Die ehrliche Ausgabe ist `review_required`: „roter Plan mit
erkennbarer Schrittstruktur vorhanden — Inhalt ist mit statischer Analyse
nicht vollständig prüfbar, manuelle Freigabe nötig". Die Klasse bleibt rot.

## Sichere Mehrschritt-Muster

### NOT NULL auf einer Bestandsspalte

1. Spalte nullable ergänzen (grün).
2. Backfill in Batches, außerhalb der Peak-Zeit, mit `lock_timeout` gesetzt
   (eigene Revision oder Anwendungscode, nicht Teil des Gates).
3. `CHECK (spalte IS NOT NULL) NOT VALID` hinzufügen (schnell, kein Scan).
4. `VALIDATE CONSTRAINT` (scannt, aber ohne `ACCESS EXCLUSIVE`-Lock für die
   Dauer des Scans).
5. `NOT NULL` setzen — mit dem validierten Constraint ist das jetzt
   metadaten-only.

### Index auf einer Bestandstabelle

Immer `CONCURRENTLY`:

```python
def upgrade():
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_orders_customer_id", "orders", ["customer_id"],
            postgresql_concurrently=True,
        )
```

`CONCURRENTLY` kann nicht innerhalb einer Transaktion laufen — Alembic-
Revisionen laufen standardmäßig in einer; `autocommit_block()` schaltet das
für den Block ab.

### Fremdschlüssel auf einer Bestandstabelle

1. `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY (...) REFERENCES ... NOT VALID`
   (schnell).
2. `ALTER TABLE ... VALIDATE CONSTRAINT ...` (scannt, kein Langzeit-Lock).

### Typänderung

Es gibt keinen generischen sicheren Einzelschritt. Für den häufigen Fall
„Spalte breiter machen" (`varchar(n)` auf größeres `n`, oder `varchar` auf
`text`) ist die native PostgreSQL-Operation metadaten-only — aber
`migration_gate.py` rät das nicht aus dem Typausdruck, sondern klassifiziert
konservativ als rot. Wer diesen Sonderfall nutzt, dokumentiert die
PostgreSQL-Version und den Mehrschritt-Plan-Marker trotzdem explizit.

### Spalte löschen

`drop_column` ist gelb bezüglich des Locks, aber der Datenverlust ist
endgültig. Sicheres Muster: Anwendungscode zuerst so ändern, dass die
Spalte nicht mehr gelesen wird (separater Rollout), erst danach die
Migration mit `drop_column` — nie im selben Deploy wie die letzte Lesestelle.

## Härte-Sprachregelung (R6, Spec 00 §4)

`migration_gate.py` ist ohne installierten Hook ein **G2**-Gate: Es urteilt
und meldet, blockiert aber nicht. Erst mit dem installierten Hook aus
`assets/hooks/migration-gate.json` wird es **G3** und blockiert tatsächlich
den `alembic upgrade`-Aufruf. Welche Härte gerade gilt, mechanisch ermittelt
(nicht behauptet), steht in **jeder** Ausgabe des Skripts — Text- wie
JSON-Modus, siehe `hardness`-Feld im Report.
