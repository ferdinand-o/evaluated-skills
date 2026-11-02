# Vertragsprüfung durch einen Haiku-Agenten

Nach einem `verify` mit Verdikt `pass` verlangt die SKILL.md (G1) eine Vertragsprüfung: ein
Haiku-Agent vergleicht je Task die Steps der Task-Datei mit dem Diff. Das kann `verify`
nicht; es prüft nur Allowlist, `Produces` und Abnehmer. Der Agent sucht **keine Bugs**,
das ist das Review am Prüfpunkt (`references/checkpoints.md`). Ein grünes Haiku-Review gäbe
falsche Sicherheit, deshalb heißt das Ergebnis immer „Vertrag geprüft", nie „reviewed" und
nie „geprüft und freigegeben". Der Nutzer kann die Vertragsprüfung abschalten; die Übergabe
sagt dann „Vertragsprüfung abgeschaltet".

## Eingaben

| Eingabe | Quelle |
| --- | --- |
| Task-Datei | `.skills/cache/tasks/task-<N>-….md` (Akzeptanzkriterien mit dem Text der Steps) |
| Diff | `git diff <basis>...HEAD` im Worktree der Task, dieselbe Basis wie `verify --base` |
| `verify`-Ergebnis | `.skills/cache/tasks/verify-task-<N>.json` (aus `verify --out`) |

Bei `fail` oder `unverified` läuft keine Vertragsprüfung; dann gilt zuerst der Fix-Pfad.

## Auftrag (wörtlich an den Agenten, Modell `haiku`)

> Du prüfst den Vertrag von Task `<N>`, nicht die Qualität des Codes. Lies die Task-Datei,
> den Diff und das `verify`-Ergebnis. Ändere keinen Code, führe keine Tests aus, suche
> keine Bugs und bewerte keinen Stil.
>
> 1. Gehe die Steps unter „Akzeptanzkriterien" der Reihe nach durch. Markiere jeden als
>    `erledigt` oder `fehlt`, nichts dazwischen. `erledigt` braucht einen Beleg
>    `Datei:Zeile` aus dem Diff (Zeilennummer der neuen Fassung). Für `fehlt` nenne, was der
>    Step verlangt und im Diff nicht vorkommt.
> 2. Liste jede Änderung im Diff, die zu keinem Step gehört, mit `Datei:Zeile` und einem
>    Satz. Eine Änderung in einer Allowlist-Datei kann trotzdem ohne Bezug sein.
> 3. Übernimm die Einträge unter `hints` aus dem `verify`-Ergebnis unverändert mit `kind`,
>    `path`, `line` und `text`. Bewerte sie nicht.
> 4. Schreibe `.skills/cache/tasks/contract-task-<N>.md` im Format unten, Kopfzeile zuerst.
>    Die Ergebniszeile lautet „Vertrag geprüft" mit der Zahl der fehlenden Steps. Benutze
>    nie die Wörter „reviewed" oder „freigegeben".
> 5. Antworte mit der Ergebniszeile und dem Pfad der Datei, sonst nichts.

## Hinweis-Arten aus `verify`

Die Arten heißen wörtlich wie in `collect_hints`; sie ändern das Verdikt nie.

| `kind` | Bedeutung |
| --- | --- |
| `platzhalter` | hinzugefügte Zeile trifft das Platzhalter-Muster des Plan-Lints |
| `debug-ausgabe` | hinzugefügte Zeile mit einer Debug-Ausgabe |
| `sofort-grün` | Test im test-first-Log, der beim ersten Lauf grün war |
| `log-fehlt` | kein test-first-Log im Worktree |
| `diff-ungeprüft` | `verify` lief ohne `--base`, der Diff blieb ungeprüft |

## Auswertung im Hauptagenten

Fehlt ein Step, ist die Vertragsprüfung durchgefallen: die Task fixt im selben Worktree
(höchstens zwei Runden, dann Opus bzw. Eskalation, siehe SKILL.md). Änderungen ohne Bezug
und Hinweise stehen in der Übergabe; allein lösen sie keine Fix-Runde aus.

## Beispiel

```markdown
<!-- skill: subagent-dev | schema: 1 | generated: Vertragsprüfung nach references/contract-check.md, Task 4, Basis a1b2c3d -->

# Vertragsprüfung Task 4: CSV-Export

**Ergebnis:** Vertrag geprüft — 1 von 3 Steps fehlt

| Step | Stand | Beleg |
| --- | --- | --- |
| 1 Export-Funktion schreiben | erledigt | `src/export.py:12` |
| 2 Kopfzeile mit Spaltennamen | erledigt | `src/export.py:20` |
| 3 Test für leere Tabelle | fehlt | kein Test mit leerer Tabelle in `tests/test_export.py` |

## Änderungen ohne Bezug zu einem Step

- `src/export.py:41` — Hilfsfunktion zum Runden von Beträgen, kein Step verlangt sie

## Hinweise aus verify

- `debug-ausgabe` `src/export.py:33` — Ausgabe der Zeilenzahl
- `sofort-grün` `.skills/cache/test-first/log.md` — test_export_header
```
