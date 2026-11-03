---
name: decide
description: "Use when Claude itself faces a question during ongoing work — two readings that lead to different work, or a choice a user rule in .skills/decide/rules.md covers —, before any step that is expensive to undo (schema or migration, dependency, deletion, push, external side effect), even one the user ordered, or when the user types /decide. Triggers include \"/decide\", \"entscheide selbst\", \"soll ich fragen oder machen\", \"was hast du selbst entschieden\", \"offene Entscheidungen\". Not for the assumptions of a feature spec draft (use feature-spec) and not for the assumptions of a plan (use work-plan)."
---

# decide — eigene Fragen nach Umkehrbarkeit, belegt statt still

**Eiserne Regel:** Eine große Entscheidung führt Claude ohne Freigabe nie aus, und eine
kleine fällt es nie ohne Belegzeile — gesucht wo, gefunden was. Einordnung, Themenwahl,
Untergrenze und das Unterlassen des teuren Schritts verlangt diese Datei (G1); Belegzeile,
Optionenzahl, Regeln, Auftragsprüfung und `check` meldet `decide_log.py` (G2). Es hält
niemanden an, einen Hook gibt es nicht.

## Ablauf

Jeder Aufruf unten steht mit vollem Pfad und läuft so, wie er dasteht, sobald `<…>` und `…`
ersetzt sind; keine Shell-Variable, sie überlebt den nächsten Bash-Aufruf nicht. Werte mit
führendem `-` als `--decision=-v`.

0. **Regeln lesen.** Einmal je Sitzung vor der ersten Einordnung:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" rules
   ```
   Das Thema eines Eintrags wählt Claude, wo eins passt, wörtlich aus dieser Liste.
1. **Untergrenze.** decide gilt nur für eine eigene Frage, bei der mindestens zwei Lesarten
   zu verschiedener Arbeit führen: Die Wahl merkt jemand außerhalb der geänderten Stelle (ein
   Test, ein Aufrufer, ein Leser des Logs, ein anderes Modul). Reihenfolge von Funktionen
   in einer Datei, lokale Namen, Formatierung, Importreihenfolge: ohne Eintrag entscheiden,
   auch wenn das Repo die Antwort zeigt. Eine Frage, deren Thema eine Regel trifft, liegt nie
   darunter. Ruft `/decide <frage>` eine Frage darunter auf, lautet die Antwort
   „Keine Entscheidung nötig“ mit dem Grund; es entsteht keine Datei.
2. **Einordnen.** Groß ist, was eine Handlung aus `references/reversibility.md` auslöst oder
   dessen Thema eine Regel `immer fragen` trifft; alles andere ist klein. Vorrang: konkreter
   Auftrag vor Regel vor eigener Einordnung. Hat der Nutzer genau diesen Schritt beauftragt
   (Handlung und Gegenstand stehen im Auftrag, etwa „nimm httpx als Abhängigkeit auf“), ist er
   freigegeben — ablegen, dann ausführen:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" add --class gross --topic "<thema>" \
     --question "<frage>" --key "<kategorie>:<pfad>" \
     --approved-by-request "<auftrag wörtlich>"
   ```
   Ein Auftrag mit offenem Ergebnis („überarbeite die Hilfe zu --verbose“) gibt die Aufgabe
   frei, nicht die Wahl darin. Nur wegen einer Regel groß:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" add --class gross --topic "<regelthema>" \
     --question "<frage>" --key "rule:<regelthema>" --option "A: …" --option "B: …" --recommendation "…"
   ```
3. **Klein.** Beleg suchen in Repo, Spec, Tests, Doku. Müsste die Suche voraussichtlich
   mehr als zwei Dateien lesen, erarbeitet sie ein Sonnet-Subagent mit einem Auftrag (6).
   Dann eintragen und weiterarbeiten; ohne Treffer meldet das Skript den Eintrag als Annahme:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" add --class klein --topic "<thema>" \
     --question "<frage>" --decision "<wahl>" --evidence "gesucht: … — Treffer: <datei:zeile>"
   ```
4. **Groß.** Vorlage nach `references/option-memo.md`: zwei bis vier Optionen mit Folgen und
   Umkehrbarkeit, Empfehlung mit Grund. Der Aufruf legt Block `D-<n>` in `docs/big-decisions.md`
   an (erste Anlage: „angelegt: docs/big-decisions.md“):
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" add --class gross --topic "<thema>" \
     --question "<frage>" --key "<kategorie>:<pfad>" --option "A: …" --option "B: …" --recommendation "…"
   ```
   Bis zur Freigabe unterbleibt die ganze Antwort auf die große Frage, nicht nur ihr teuerster
   Teil; die übrige Arbeit läuft weiter, große Fragen sammeln.
   - **Beaufsichtigt** (`AskUserQuestion` in der Werkzeugliste): gebündelt stellen, Antwort
     eintragen (`--reject` statt `--answer "…"` für abgelehnt), handeln:
     ```bash
     python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" resolve D-<n> --answer "…"
     ```
   - **Unbeaufsichtigt** (`claude -p` ohne Permission-Host, jeder Subagent): Block bleibt
     offen, der teure Schritt unterbleibt, die Übergabe nennt `D-<n>`.
5. **Subagenten tragen nichts ein.** Jeder Auftrag an einen Subagenten, den der Hauptagent
   ohne `brief` losschickt, endet wörtlich mit diesem Satz (kein Skript prüft das, G1):
   > Du arbeitest als Subagent. Trag keine Entscheidung und keine Frage mit decide_log.py ein und schreib nicht nach docs/big-decisions.md. Stößt du auf eine Frage mit zwei Lesarten oder auf einen teuer umkehrbaren Schritt, der nicht ausdrücklich in deinem Auftrag steht, entscheide und handle nicht, sondern nenn ihn in deiner Rückgabe: Frage, Optionen mit Belegen datei:zeile, Folgen, Umkehrbarkeit, Empfehlung. Der Hauptagent ordnet ihn ein.

   Liest ein Subagent diese Datei selbst, gilt derselbe Satz.
6. **Auftrag aus `brief`.** Der erste Aufruf schreibt `.skills/cache/decide/<session>/brief-<n>.md`
   mit sechs Feldern als Überschriften `## <Feld>` (`references/brief.md`) und nennt den Pfad.
   Das Skript füllt Schon entschieden, Feste Vorgaben und Rückgabe (mit dem Satz aus 5); der
   Hauptagent füllt Frage (neutral, keine Empfehlung), Anlass und Wo nachsehen. Der zweite prüft
   die Datei vor dem Dispatch:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" brief --topic "<thema>"
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" brief --check "<datei>"
   ```
7. **Übergabe.** Hat die Aufgabe Dateien geändert, prüft `check` den Diff seit dem Commit vor
   der Aufgabe (`<rev>`; ohne eigenen Commit `HEAD`; auch `<a>..<b>` und `<a>...<b>`). Jede gemeldete Stelle nennt die
   Antwort mit Grund, die Zeile „ungeprüft: data-delete, …“ wörtlich. Dann `summary` — nur wenn
   es Einträge gibt — und `open`:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" check --range "<rev>"
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" summary
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" open
   ```
   Ohne Git meldet `check` „ungeprüft — kein Git“.
   Fehlt das Skript, sagt die Übergabe „ungeprüft — decide_log.py nicht verfügbar“ und nennt
   die Entscheidungen aus dem Gedächtnis als solche.

Sitzung ist `--session`, sonst `CLAUDE_CODE_SESSION_ID`; fehlen beide, endet jeder schreibende
Aufruf mit Exit 1. Steht `.skills/cache/` nicht in der `.gitignore`, sagt die Antwort beim
ersten Protokoll, dass ein unversionierter Ordner entstanden ist.

## Contract

- **Klein nur mit Beleg.** Ein kleiner Eintrag ohne passende Belegzeile schreibt nichts
  (Exit 1); „nichts gefunden“ macht den Eintrag zur Annahme. Ob die Fundstelle stimmt: G1.
- **Groß nie ohne Freigabe.** Ohne Block `freigegeben` unterbleibt der teure Schritt (G1);
  steht er im Diff dennoch, meldet `check` es (G2).
- **Auftrag ist Freigabe.** Handlung und Gegenstand im Auftrag: Zitat ablegen, nicht fragen.
- **Regeln wirken in eine Richtung.** `immer fragen` stuft hoch; `nie fragen` stuft eine
  große Frage nie herab.
- **Sichtbar ungeprüft.** `check` sieht `data-delete`, `push`, `external` nicht; die
  Übergabe gibt die Zeile „ungeprüft: …“ weiter, nie „geprüft“.
- **Kein wertender Auftrag.** Die Prüfung mit `brief` (Schritt 6) meldet Länge, fremde Felder
  und Wertwörter; andere Wertungen bleiben G1.
- **Anti-Zeremonie:** Eine Wahl unter der Untergrenze erzeugt keinen Eintrag, keine Datei,
  keine Liste.
- **Frontmatter:** nur `name`/`description`. Tier 1, `decide_log.py` nur Stdlib.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Das ist klein, ich mach's einfach“ | Steht die Handlung in `reversibility.md`, ist sie groß, egal wie kurz der Diff ist. |
| „Den Beleg spare ich mir, das ist offensichtlich“ | Dann ist die Belegzeile ein Satz: `gesucht: … — Treffer: …`. Ohne sie ist es eine Annahme. |
| „Ich frage lieber nach, sicher ist sicher“ | Eine Frage, deren Antwort im Repo steht, kostet den Nutzer, was eine Suche gekostet hätte. Erst suchen. |
| „Im -p-Lauf kann ich nicht fragen, also entscheide ich“ | Unbeaufsichtigt bleibt die große Frage offen; der teure Schritt unterbleibt, die Übergabe nennt `D-<n>`. |
| „Der Nutzer hat es doch verlangt, trotzdem frage ich“ | Ein ausdrücklicher Auftrag ist die Freigabe. Zitat ablegen, ausführen. |
| „Der Subagent soll wissen, was ich denke“ | Dann bestätigt er es nur. Frage neutral, keine Empfehlung im Auftrag. |

## Abgrenzung

- **feature-spec** — Annahmen eines Spec-Entwurfs stehen dort als `Annahme:`-Zeilen; eigene
  Fragen außerhalb eines Entwurfs gehören hierher.
- **work-plan** — Annahmen eines Plans stehen in `- Annahme:`-Zeilen dort; Fragen
  außerhalb eines Plans gehören hierher.
- **brainstorming** und der eingebaute **Plan-Modus** — Fragen beim Entwerfen gehören dorthin.
- sql-schema-architect — decide legt die Frage ab, ob migriert wird; wie, prüft
  `migration_gate.py`.
- subagent-dev — decide ändert dessen Prüfpunkte nicht; Fragen aus Tasks ordnet der
  Hauptagent hier ein.
