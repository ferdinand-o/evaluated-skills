# Entscheidungsgedächtnis: was in `docs/decisions.md` gehört

Nach einem abgeschlossenen Entwurf erntet die Skill Grundsatzentscheidungen —
nicht den ganzen Entwurf, nicht Feature-Details. `docs/decisions.md` ist die
Gedächtnisstütze, die künftige Scans lesen, damit dieselbe Frage nicht zwei
Mal gestellt wird.

## Die Ernte-Frage

> Würde ein künftiges, thematisch anderes Feature dieselbe Grundsatzfrage
> noch einmal aufwerfen, wenn diese Zeile fehlte?

Ja → ernten. Nein, weil die Antwort nur für dieses eine Feature gilt →
nicht ernten.

## Erntbar (Beispiele)

- Fehlerformat: „Alle API-Fehler folgen `{status, message}`, kein
  verschachteltes `error`-Objekt."
- State-Management-Muster: „Neue Client-Features nutzen den bestehenden
  Store unter `src/store/`, kein zweites State-System."
- Namenskonvention: „Event-Namen sind `<domäne>.<aktion>`, Kleinbuchstaben,
  Punkt getrennt."
- Architekturentscheidung: „Hintergrundjobs laufen über den bestehenden
  Scheduler (`src/scheduler.py`), kein neuer Cron-Prozess."
- Bibliothekswahl mit Begründung: „Datumsrechnung über `src/dates.py`
  (Wrapper), nicht direkt über eine Drittbibliothek — Grund: Zeitzonen-Bugs
  in Zyklus 4."

## Nicht erntbar (Beispiele)

- „Der Export-Button ist blau." — Feature-Detail, keine Grundsatzfrage.
- „Die Erinnerungsmail wird 24 Stunden vorher verschickt." — gilt nur für
  dieses eine Feature, keine Wiederverwendung außerhalb.
- „Wir nennen das Feature intern 'Reminder v2'." — Namensgebung dieses einen
  Features, keine Konvention.
- Eine Annahme, der der Nutzer widersprochen hat, ohne dass daraus eine neue
  Regel für künftige Features folgt — Korrektur eines Einzelfalls ist keine
  Grundsatzentscheidung.

Im Zweifel: nicht ernten. Eine fehlende Zeile kostet höchstens eine erneute
Nachfrage beim nächsten Feature; eine falsch geerntete Zeile verzerrt jeden
künftigen Scan, der sie für „bereits entschieden" hält.

## Format der Zeile

```
- <Datum> — <Entscheidung in einem Satz>. (Anlass: <Feature-Spec-Name>)
```

Beispiel:

```
- 2026-08-15 — Alle API-Fehler folgen `{status, message}`, kein
  verschachteltes `error`-Objekt. (Anlass: fälligkeits-erinnerung)
```

Append-only, chronologisch. Keine Umsortierung nach Thema — das wäre eine
stille Veränderung gewachsener Historie (siehe unten).

## Datei-Kopfzeile

`docs/decisions.md` trägt die Artefakt-Kopfzeile wie jedes Wissens-Artefakt
(`docs/artifact-header.md`):

```
<!-- skill: feature-spec | schema: 1 | generated: feature-spec Ernte nach "<Feature>" -->
```

Existiert die Datei noch nicht, kündigt die Skill die Erstanlage an (Spec 00
Bootstrap-Regel) statt sie stillschweigend zu erzeugen.

## Beim Scan lesen

Ein künftiger Entwurf liest `docs/decisions.md` vollständig und setzt
Entschiedenes als gegeben voraus, statt es erneut zu erfragen. Widerspricht
die neue Anfrage einer bestehenden Zeile, gehört das in den Entwurf — als
Annahme, die den Konflikt benennt, oder als offene Frage, nicht als
stillschweigende Neuentscheidung.

Fehlt die Kopfzeile oder passt das Schema nicht (Konsumenten-Regel, Spec 00
§1), scannt die Skill trotzdem weiter, ohne die Datei zu lesen, und sagt,
dass sie übersprungen wurde.

## Die 30-Einträge-Warnung

`docs/decisions.md` bleibt flach — keine automatische Gliederung nach
Themen. Ab 30 Zeilen nennt die Skill das im Output („`docs/decisions.md` hat
34 Einträge — eine Gliederung nach Themen wäre fällig"), gliedert aber nicht
selbst um. Das ist eine G1-Regel (Selbstauskunft, Spec 00 §4): kein Skript
zählt das mechanisch, die Skill zählt es im Gespräch und sagt es. Die
Umgliederung bleibt eine bewusste Handlung des Nutzers — automatisches
Umsortieren wäre ein Schreibzugriff auf gewachsene Historie ohne Anlass.
