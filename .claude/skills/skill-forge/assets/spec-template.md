<!-- skill: skill-forge | schema: 1 | generated: von Hand nach skills/skill-forge/assets/spec-template.md — beim Kopieren diese Zeile entfernen: Specs sind Wissen, kein erzeugtes Artefakt -->
# Spec NN: neue-skill — ein Satz, der sagt, was danach anders ist

Skill-Spezifikation · Zyklus NN · Entscheidung: … (die eine Entscheidung, die den Zuschnitt trägt) · Abgeglichen mit Spec 00

<!-- Nach Schritt 1 von skill-forge (Review durch einen Subagenten, references/spec-reviewer-prompt.md)
     kommt an die Kopfzeile: „· Überarbeitet nach unabhängigem Review". lint-spec verlangt den Vermerk ab Spec 18. -->

## Problem

Was fehlt, für wen, und woran man es heute merkt — mit Zahl, wenn es eine gibt, und
mit der Quelle der Zahl. Zwei bis vier Sätze. Was hier steht, hat jemand gemessen oder
der Nutzer gesagt; alles andere gehört unter Open questions als `Annahme:`.

## Constraints

Tier des Skripts (Spec 00 §3) und warum; Gate-Grad je Gate (G1 „verlangt", G2 „meldet",
G3 nur mit `assets/hooks/`); Ablage nach Spec 00 §1; SKILL.md ≤ 150 Zeilen; Deutsch mit
englischen Bezeichnern; kein Import fremder Skill-Skripte. Was der Harness prüfen
kann, steht in `evalkit/schema.py` — ein Eval, der etwas anderes verlangt, ist keiner.

## Approach

**Eiserne Regel:** ein Satz — die Zusage, die diese Skill gibt und ein normales
Gespräch nicht.

### Skill-Struktur

```
skills/neue-skill/
├── SKILL.md                     Ablauf, Eiserne Regel, Contract, Anti-Rationalisierung, Abgrenzung
├── references/…                 je Datei ein Halbsatz, wofür
├── assets/…                     Gerüste mit Kopfzeile (docs/artifact-header.md)
└── scripts/check.py             Tier 1 — was es prüft, was es meldet
```

### Ablauf

Die Schritte, wie sie in der SKILL.md stehen werden — mit dem Schritt, an dem das
Skript läuft, und dem Wortlaut der Übergabe, wenn es fehlt („ungeprüft — …", nie „fertig").

### Contract

Jede Zusage in einem Satz, mit dem Mechanismus dahinter. Der Anti-Zeremonie-Fall
ausdrücklich: Was löst der triviale Fall aus, und was nicht.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| … (der Anlass in der Sprache des Nutzers) | **neue-skill** | impl-plan (16) — der Plan danach; superpowers:writing-skills — Disziplin-Skills mit Druckszenarien |

Die zwei stärksten Konkurrenten mit Namen, und was dort besser liegt. Jeder genannte
Nachbar bekommt beim Bau einen Rückverweis (`lint_skill.py`, Regel `neighbors`).

### Evals

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-<fall>-stays-small` | contract | empty-dir | `file_exists` auf das eigene Artefakt; `file_absent` auf den Report | nur diese Skill schreibt die Datei an diesem Ort |
| 2 | `<zusage>-appears-verbatim` | contract | … | `output_matches` auf ein Token des Contracts | das Token ist Vokabular der Doktrin, ein Basismodell sagt es anders |
| 3 | `routing-<anlass>-without-skill-name` | contract | … | dasselbe Artefakt wie in 1 | stochastisch — ein roter Lauf zeigt die Kollision, ein grüner beweist nichts |

Je Eval ein Prompt. Assertion-Typen nur aus `evalkit/schema.py`. Das Artefakt entsteht
im Workspace, den `prepare()` anlegt — Skripte anderer Skills sind dort nicht da.

## Alternatives considered

Je Option ein Absatz: was sie war, warum nicht — mit der Bedingung, unter der sie doch
gewonnen hätte. Die verworfene Option steht hier, damit sie in drei Wochen nicht
wieder auftaucht.

## Out of scope

Was bewusst nicht gebaut wird, mit dem Nachbarn, der es stattdessen tut.

## Open questions

Was entschieden aussieht, aber niemand entschieden hat, steht hier als Zeile
`*Annahme:* … — widersprich, falls nein.` Was der Bau entscheiden muss, mit dem, was
die Entscheidung kostet. Was ungemessen bleibt (Harness, Trigger), ausdrücklich.

## Next steps

Plan mit `impl-plan` (16); Bau nach `skill-forge` (17) Schritt 3 bis 7.
