# Spec 00 – skill-foundation (Auszug für diese Fixture)

## §2 Evals

Jede Skill hat `evals/<skill>/evals.json`. Zwei Klassen: `contract` (nur mechanische
Assertions: `file_exists`, `file_matches`, `file_max_lines`, `artifact_header`,
`output_matches`) und `behavior` (genau ein `judge`-Claim). Genau ein Prompt je Eval.
**Pflicht: mindestens ein Anti-Zeremonie-Eval** — der triviale Fall, in dem die Skill
klein bleiben muss, mit einer artefaktgebundenen Assertion.

## §3 Tiers

Tier 0: keine Skripte, nur Doktrin. Tier 1: Python-Stdlib. Ein übersprungenes Gate
meldet nie Erfolg.

## §4 Gate-Sprache

G1 „verlangt" (Doktrin), G2 „meldet" (Skript ohne Hook), G3 „blockiert" (nur mit Hook).
Nichts nennt sich härter, als sein Mechanismus ist.

## §5 Routing

| Anlass | zuständig |
| --- | --- |
| Notiz taggen | note-tag (21) |
| Übergabe an die nächste Session schreiben | handoff-note (22) |
| Zwischenstand im Gespräch festhalten | checkpoint (23) |
