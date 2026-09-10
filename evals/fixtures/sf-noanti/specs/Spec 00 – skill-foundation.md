# Spec 00 – skill-foundation (Auszug für diese Fixture)

## §3 Tiers

Tier 0: keine Skripte, nur Doktrin. Tier 1: Python-Stdlib. Ein übersprungenes Gate
meldet nie Erfolg.

## §4 Gate-Sprache

G1 „verlangt" (Doktrin), G2 „meldet" (Skript ohne Hook), G3 „blockiert" (nur mit Hook
unter `assets/hooks/`). Nichts nennt sich härter, als sein Mechanismus ist.

## §5 Routing

Frontmatter: `name` und `description`. Die Description nennt Trigger und eine
Abgrenzung gegen die stärksten Konkurrenten; was die Skill tut, steht im Body.

| Anlass | zuständig | nicht |
| --- | --- | --- |
| Notiz taggen | note-tag (21) | handoff |
| Skill bauen oder ändern | skill-forge (17) | skill-creator |
