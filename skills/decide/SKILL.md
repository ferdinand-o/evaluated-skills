---
name: decide
description: "Use when Claude itself faces a question during ongoing work — two readings that lead to different work, or a choice a user rule in .skills/decide/rules.md covers —, before any step that is expensive to undo (schema or migration, dependency, deletion, push, external side effect), even one the user ordered, or when the user types /decide. Triggers include \"/decide\", \"entscheide selbst\", \"soll ich fragen oder machen\", \"was hast du selbst entschieden\", \"offene Entscheidungen\". Not for the assumptions of a feature spec draft (use feature-spec) and not for the assumptions of a plan (use work-plan)."
---

# decide — eigene Fragen nach Umkehrbarkeit, belegt statt still

**Eiserne Regel:** Eine große Entscheidung führt Claude ohne Freigabe nie aus, und eine
kleine fällt es nie ohne Belegzeile — gesucht wo, gefunden was. Einordnung, Untergrenze und das
Unterlassen des teuren Schritts verlangt diese Datei (G1); Belegzeile, Optionenzahl, Regeln und
`check` meldet `decide_log.py` (G2); angehalten wird nur mit dem Hook (G3).

## Ablauf

Jeder Aufruf läuft, wie er dasteht, sobald `<…>`, `…` ersetzt sind; Werte mit `-` vorn als `--decision=-v`.
Sitzung: `--session`, sonst `CLAUDE_CODE_SESSION_ID`, sonst Exit 1. Fehlt `.skills/cache/` in der `.gitignore`, sagt das die Antwort.

0. **Regeln lesen.** Einmal je Sitzung vor der ersten Einordnung; das Thema eines Eintrags
   wählt Claude, wo eins passt, wörtlich aus der Liste:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" rules
   ```
1. **Untergrenze.** decide gilt nur für eine eigene Frage, bei der mindestens zwei Lesarten
   zu verschiedener Arbeit führen und die Wahl jemand außerhalb der geänderten Stelle merkt
   (Test, Aufrufer, Leser des Logs, anderes Modul). Reihenfolge in einer Datei, lokale Namen,
   Formatierung, Importreihenfolge: ohne Eintrag entscheiden. Eine Regel-Frage liegt nie darunter.
   `/decide <frage>` darunter: „Keine Entscheidung nötig“ mit Grund, keine Datei.
2. **Einordnen.** Groß ist, was eine Handlung aus `references/reversibility.md` auslöst oder
   dessen Thema eine Regel `immer fragen` trifft (`nie fragen` stuft nie herab); sonst klein. Vorrang: konkreter
   Auftrag vor Regel vor eigener Einordnung. Stehen Handlung und Gegenstand im Auftrag („nimm
   httpx als Abhängigkeit auf“), ist der Schritt freigegeben — Zitat ablegen, nicht fragen:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" add --class gross --topic "<thema>" --question "<frage>" --key "<kategorie>:<pfad>" --approved-by-request "<auftrag wörtlich>"
   ```
   Ein Auftrag mit offenem Ergebnis („überarbeite die Hilfe zu --verbose“) gibt die Aufgabe
   frei, nicht die Wahl darin. Nur wegen einer Regel groß: Schlüssel `rule:<regelthema>`, sonst wie 4.
3. **Klein.** Beleg suchen in Repo, Spec, Tests, Doku; sind es voraussichtlich mehr als zwei
   Dateien, erarbeitet ihn ein Sonnet-Subagent (5, 6). Eintragen, weiterarbeiten; ohne Treffer
   meldet das Skript den Eintrag als Annahme:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" add --class klein --topic "<thema>" --question "<frage>" --decision "<wahl>" --evidence "gesucht: … — Treffer: <datei:zeile>"
   ```
4. **Groß.** Nach `references/option-memo.md`: zwei bis vier Optionen mit Folgen und
   Umkehrbarkeit, Empfehlung mit Grund; der Aufruf legt Block `D-<n>` in `docs/big-decisions.md` an:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" add --class gross --topic "<thema>" --question "<frage>" --key "<kategorie>:<pfad>" --option "A: …" --option "B: …" --recommendation "…"
   ```
   Bis zur Freigabe unterbleibt die ganze Antwort auf die große Frage; übrige Arbeit läuft weiter.
   - **Beaufsichtigt** (`AskUserQuestion` da): gebündelt stellen, Antwort eintragen
     (`--reject` statt `--answer` für abgelehnt), handeln:
     ```bash
     python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" resolve D-<n> --answer "…"
     ```
   - **Unbeaufsichtigt** (`claude -p` ohne Host, Subagent): Block bleibt offen, Schritt unterbleibt, Übergabe nennt `D-<n>`.
5. **Subagenten tragen nichts ein.** Jeder Auftrag an einen Subagenten (auch einen, der diese
   Datei selbst liest) endet wörtlich mit diesem Satz (G1):
   > Du arbeitest als Subagent. Trag keine Entscheidung und keine Frage mit decide_log.py ein und schreib nicht nach docs/big-decisions.md. Stößt du auf eine Frage mit zwei Lesarten oder auf einen teuer umkehrbaren Schritt, der nicht ausdrücklich in deinem Auftrag steht, entscheide und handle nicht, sondern nenn ihn in deiner Rückgabe: Frage, Optionen mit Belegen datei:zeile, Folgen, Umkehrbarkeit, Empfehlung. Der Hauptagent ordnet ihn ein.
6. **Auftrag schreiben.** Ohne Skript-Aufruf: nach `references/brief.md` direkt in den Prompt, Frage neutral, ohne Empfehlung (G1).
7. **Übergabe.** Hat die Aufgabe Dateien geändert, ist `check` mit genau einer Revision der letzte
   Aufruf vor der Antwort, auch nach einer Freigabe: Diff seit dem Commit vor der Aufgabe (`<rev>`;
   ohne eigenen Commit `HEAD`), mit Zusammenfassung und offenen Fragen. Die Antwort nennt jede
   gemeldete Stelle mit Grund und zitiert die Schlusszeile wörtlich: „ungeprüft: data-delete,
   unsaved-work, push, external, cost; teilweise: api, migration, dependency, permissions“. Ohne
   Aufruf kein Satz über das Ergebnis von `check`:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" check --range "<rev>"
   ```
   Ohne geänderte Datei ist der eine Aufruf `open`:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" open
   ```
   Ohne Git meldet `check` „ungeprüft — kein Git“; fehlt das Skript, sagt die Übergabe
   „ungeprüft — decide_log.py nicht verfügbar“ und nennt die Entscheidungen aus dem Gedächtnis.

## Optionaler Hook (G3)

`guard` fragt als `PreToolUse`-Hook auf Bash bei erkannten Befehlen (Push, Löschen, Verwerfen,
externe Wirkung) den Nutzer, bis er antwortet; er erkennt Muster und zerlegt keine Shell.
Installation: `scripts/decide_log.py` nach `.claude/hooks/` kopieren, `assets/hooks/decide-guard.json`
in `.claude/settings.json` oder `settings.local.json` mischen — nie selbst installieren. Fehlt die
Kopie, meldet er „Hook ungeprüft“ und hält nichts an. Ein beauftragter Push wird einmal mit
`--key push:<remote>/<branch>` abgelegt (Schritt 2); dann lässt der Hook ihn durch.

## Contract

- **Groß nie ohne Freigabe.** Ohne Block `freigegeben` unterbleibt der teure Schritt (G1);
  steht er im Diff dennoch, meldet `check` es (G2); ob die Fundstelle eines Belegs stimmt: G1.
- **Seltenes an den Nutzer.** Was `check` oder `guard` nicht einordnen kann (Bereich statt
  Revision: „ungeprüft — check nimmt eine Revision“; Bare-Repo; nicht schlichter Push), wird
  nicht nachgebaut, sondern als „ungeprüft — …“ oder Rückfrage weitergegeben, nie als sauber.
- **Kein Ausweichen.** Nach einer abgelehnten Rückfrage wiederholt Claude den Befehl nicht und
  sucht keinen anderen Weg zum selben Schritt; die Übergabe nennt ihn (G1).

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Den Beleg spare ich mir, das ist offensichtlich“ | Dann ist die Belegzeile ein Satz: `gesucht: … — Treffer: …`. |
| „Ich frage lieber nach, sicher ist sicher“ | Steht die Antwort im Repo, kostet die Frage den Nutzer, was eine Suche gekostet hätte. Erst suchen. |
| „Im -p-Lauf kann ich nicht fragen, also entscheide ich“ | Unbeaufsichtigt bleibt die große Frage offen; der teure Schritt unterbleibt. |
| „check würde hier nichts melden, das spare ich mir“ | Ein Satz über ein Prüfergebnis ohne Aufruf ist erfunden. Aufrufen, Schlusszeile zitieren. |
| „Der Hook fragt ja sowieso, den Push lege ich nicht ab“ | Ohne Hook fragt niemand. Ein beauftragter Push wird einmal abgelegt; dann lässt auch der Hook ihn durch. |
| „Der Hook hat abgelehnt, dann eben über `bash -c`“ | Die Ablehnung ist die Antwort. Nicht wiederholen, nicht ausweichen, in der Übergabe nennen. |

## Abgrenzung

- **feature-spec**, **work-plan** — deren Annahmen stehen dort als `Annahme:`-Zeilen; eigene
  Fragen außerhalb gehören hierher. **brainstorming**, **Plan-Modus** — Entwurfsfragen dorthin.
- sql-schema-architect, subagent-dev — decide legt nur ab, ob migriert wird; Task-Fragen ordnet
  der Hauptagent hier ein.
