# Spec 23 – checkpoint

## Zweck

Mitten im Gespräch, auf „Zwischenstand" oder „wo stehen wir", gibt die Skill zwei
Blöcke aus und sonst nichts: `Recap:` mit höchstens drei Sätzen, was bisher entschieden
wurde, und `Open:` mit den Punkten, die noch keine Entscheidung haben. Keine Datei,
kein Vorschlag, keine Rückfrage.

## Tier

Tier 0. Kein Skript, keine Datei. Die Evals prüfen die Ausgabe direkt.

## Contract

- Die Antwort enthält die Tokens `Recap:` und `Open:` wörtlich, in dieser Reihenfolge,
  je am Zeilenanfang.
- Unter `Recap:` stehen höchstens drei Sätze.
- Ist nichts offen, steht unter `Open:` genau „—".
- Kein dritter Block. Insbesondere kein Ausblick, keine Empfehlung.

## Evals

| # | id | Klasse | Fixture | Assertions |
| --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-nothing-open-stays-two-blocks` | contract | Gespräch mit einer Entscheidung | `output_matches "^Recap:"`; `output_matches "^Open:\s*—"`; `must_not output_matches "^Next"` |
| 2 | `recap-and-open-both-present` | contract | Gespräch mit drei Entscheidungen | `output_matches "^Recap:"`; `output_matches "^Open:"` |
| 3 | `recap-stays-under-four-sentences` | behavior | Gespräch mit drei Entscheidungen | ein Judge-Claim mit Zahl |

## Nachbarn

`handoff-note` (22) schreibt die Übergabe als Datei am Session-Ende; `checkpoint` ist
der flüchtige Zwischenstand davor. Die Routing-Matrix in Spec 00 §5 bekommt die Zeile
für 23.
