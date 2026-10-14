# Ziele — Ledger, Bereiche, Klassen

`docs/goals.md` ist der Zielstand über Sitzungen hinweg; `/goal` gilt nur für eine
Session, und sein Evaluator liest keine Dateien. Die Regel `.claude/rules/goals.md` sagt
Claude, wie entdeckte Arbeit einzuordnen ist; der Bereichs-Hook `goal_scope.py` meldet,
wenn Dateien außerhalb der Bereiche aktiver Ziele geändert wurden.

## Ledger

Kopfzeile `<!-- skill: setup-repo | schema: 1 | … -->` in Zeile 1. Wer die Datei liest,
prüft sie zuerst; fehlt sie oder ist das Schema unbekannt, wird nichts daraus abgeleitet.
Drei Tabellen, in dieser Reihenfolge:

| Tabelle | Spalten | Inhalt |
| --- | --- | --- |
| `## Aktiv` | `id`, Ziel, Fertig wenn, Bereich, seit | was gerade verfolgt wird |
| `## Kandidaten` | `id`, Kandidat, entdeckt bei, Grund, am | entdeckte Arbeit, die ein neues Ziel wäre |
| `## Erledigt` | `id`, Ziel, Beleg, am | die letzten zehn; Älteres liegt in Git |

*Aktiv* plus *Kandidaten* sind der Backlog. Beim Einrichten entsteht der Ledger leer; die
Skill erfindet keine Ziele.

**IDs** heißen `G<n>`, mit `n` eins größer als das höchste `n` in allen drei Tabellen.
Vor jedem Schreiben die Datei neu lesen und nur anhängen. Zwei Sessions können beim
Mergen kollidieren; einen Konflikt in `docs/goals.md` löst Claude nicht selbst, es fragt.

**Fertig wenn** folgt der `/goal`-Doku: ein messbarer Endzustand, die Prüfung, die ihn
zeigt, und was sich nicht ändern darf — etwa „`make check` grün, `test_dates.py` deckt den
29. Februar ab, öffentliche API von `dates.py` unverändert". Ohne prüfbares „Fertig wenn"
kein Eintrag unter *Aktiv*.

**Aktiv** entsteht nur, wenn der Nutzer etwas ausdrücklich ein Ziel nennt; dann schlägt
Claude die passende `/goal`-Zeile aus „Fertig wenn" vor. Nach *Erledigt* wandert ein Ziel
mit Beleg (Befehl und Ergebnis).

## Bereich

Pfad-Globs relativ zur Repo-Wurzel, durch Kommas getrennt, in einer Zelle:

- `**` passt auf beliebig viele Ordner, `*` und `?` nur innerhalb eines Pfadteils.
- Trenner ist immer `/`, Groß- und Kleinschreibung zählen, geschweifte Klammern gibt es
  nicht.
- Ein Glob mit `/` am Ende (`src/`) gilt als `src/**`.
- Eine leere Zelle heißt: kein Bereich. Der Hook übergeht dieses Ziel.

## Die vier Klassen entdeckter Arbeit

Gilt nur, solange *Aktiv* mindestens ein Ziel hat.

| Klasse | Wann | Folge |
| --- | --- | --- |
| Vom Nutzer verlangt | steht im aktuellen Prompt | erledigen |
| Teil des Ziels | nötig, damit „Fertig wenn" eintritt | erledigen |
| Trivial | in einer Datei, die die Aufgabe ohnehin ändert, höchstens fünf Zeilen, keine neue öffentliche Schnittstelle, kein neuer oder geänderter Test nötig | erledigen und im Turn-Ende nennen |
| Neues Ziel | alles andere | nicht umsetzen, unter *Kandidaten* eintragen, im Turn-Ende nennen |

Beispiel: Ziel G1 „Tippfehler in `greet.py`" mit Bereich `src/greet.py`. Beim Lesen fällt
ein falsches Schaltjahr in `src/dates.py` auf — nicht verlangt, nicht nötig für G1, keine
Datei der Aufgabe: Kandidat, `src/dates.py` bleibt unverändert.

## Bereichs-Hook

`goal_scope.py` läuft an `UserPromptSubmit` und `Stop`.

- **UserPromptSubmit:** hält die Basis des Turns fest (HEAD und je geänderter oder
  unversionierter Datei einen Inhalts-Hash). Liegt eine offene Meldung aus dem letzten
  Turn vor, gibt er sie als `additionalContext` aus und löscht sie.
- **Stop:** bestimmt die im Turn geänderten Dateien (Commits des Turns zählen mit; was
  vorher schon uncommittet war, zählt nur, wenn es sich weiter ändert). Liegt eine Datei
  außerhalb der Bereiche aller aktiven Ziele und wurde sie in der Session noch nicht
  gemeldet, gibt er `systemMessage` aus und merkt sich die Meldung für den nächsten
  Prompt. Er hält das Turn-Ende nie an.

Ausgenommen, weil sie keine Zielarbeit sind: `docs/goals.md`, `handoff.md`,
`docs/debugging/`, `docs/decisions.md`, `docs/specs/wip/`, `docs/plans/`, `.claude/`, `.skills/`,
`CLAUDE.md`, `.gitignore`.

Schweigen: ohne Repo-Commit, ohne `docs/goals.md`, ohne aktives Ziel mit Bereich.
Einmal je Session `systemMessage` mit Grund: fehlende oder unbekannte Kopfzeile des
Ledgers, gescheiterter git-Aufruf. Zustand: `.skills/cache/setup-repo/goal-scope.json`
mit `_meta`, oder der Pfad in `SETUP_REPO_GOAL_STATE` (für Proben); unlesbar heißt
Neustart, Einträge älter als sieben Tage fallen weg.
