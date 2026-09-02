# Spec 22 – handoff-note

## Zweck

Am Ende einer Session schreibt die Skill `handoff.md` ins Projektwurzelverzeichnis:
was entschieden ist, was offen ist, wer als Nächstes dran ist. Eine bestehende
`handoff.md` wird ersetzt, nie fortgeschrieben — sonst wächst sie, bis niemand sie liest.

## Tier

Tier 1: `scripts/collect.py` (Stdlib) liest `git log` seit dem letzten `handoff.md`-Commit
und liefert die berührten Dateien als JSON. Fehlt Git, meldet das Skript
`ungeprüft — kein Git` und die Skill schreibt die Dateiliste von Hand. G2: das Skript
meldet, ein Hook fehlt.

## Contract

- `handoff.md` beginnt mit der Kopfzeile `<!-- skill: handoff-note | schema: 1 | generated: … -->`.
- Abschnitte in dieser Reihenfolge: `Decided`, `Open`, `Next owner`. Leere Abschnitte
  stehen trotzdem da, mit „—".
- Höchstens 40 Zeilen. Ist mehr zu sagen, gehört es in eine Datei, auf die `Open` zeigt.
- `Next owner` nennt genau einen Namen oder „unassigned".

## Evals

| # | id | Klasse | Fixture | Assertions |
| --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-one-line-note-stays-bare` | contract | leeres Repo, ein Commit | `artifact_header handoff.md`; `file_max_lines 12` |
| 2 | `note-carries-header` | contract | drei Commits | `artifact_header handoff.md` |
| 3 | `note-lists-open-items` | contract | Repo mit TODO-Datei | `file_matches handoff.md "^## Open"` |
| 4 | `stale-note-is-replaced` | contract | überlange handoff.md vorhanden | `file_max_lines handoff.md 40` |
| 5 | `note-names-next-owner` | contract | drei Commits | `file_matches handoff.md "^## Next owner\n\S"` |

## Nachbarn

`checkpoint` (23) hält einen Zwischenstand im Gespräch fest, ohne Datei. `note-tag` (21)
taggt einzelne Notizen. Die Routing-Matrix in Spec 00 §5 bekommt die Zeile für 22.
