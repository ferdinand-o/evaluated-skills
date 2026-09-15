<!-- skill: skill-forge | schema: 1 | generated: von Hand nach skills/skill-forge/assets/skill-template/report.md -->
# human-prose — Abschlussbericht

Gebaut nach `specs/Spec 19 – human-prose.md` und
`docs/superpowers/plans/2026-09-15-human-prose.md`. Tier 1, gebaut am 2026-09-15
sequenziell im Hauptkontext (Gate: alle neun Tasks über `measure.py` und die drei
Tokens gekoppelt). Eingabe war der Entwurf des Nutzers, Version 0.1
(`docs/superpowers/specs/2026-09-15-menschlich-schreiben-v0.1.md`); die Spec ging
vorher durch Brief, Template, unabhängigen Review (dreizehn Befunde, drei blockierend)
und `lint-spec`.

## Was entstanden ist

```
skills/human-prose/SKILL.md              92 Zeilen (Grenze 150)
skills/human-prose/references/rules.md   der Entwurf, Abschnitte 0 bis 6 und 9, Phrasen zusätzlich als Muster
skills/human-prose/references/revise.md  Modus B in sieben Schritten, Ein-Zug-Verhalten, Berichtsformat
skills/human-prose/scripts/measure.py    Tier 1 — vierzehn Prüfpunkte, fünf Urteile, measure.json
evals/human-prose/evals.json             5 Evals, alle contract; Fixtures hp-empty, hp-cache, hp-vague
tests/test_human_prose_measure.py        30 Tests (Textmodell, Prüfpunkte, CLI, rules.md-Abgleich)
tests/test_human_prose_evals_schema.py   6 Tests
```

Nachgezogen: Routing-Matrix in Spec 00 §5 und `README.md`, Abgrenzungssätze in
`explain`, `visual-summary`, `dev-report`, `handoff`, Abschnitt `## human-prose` in
`docs/known-limits.md`.

## Die Entscheidungen, die den Bau geprägt haben

**Die Skill wartet nie.** Der Entwurf sagt in Abschnitt 7 „wird gefragt statt
erfunden". Der Review fand, dass ein Eval mit angehaltener Skill in einem `-p`-Zug nie
grün wird. Jetzt schreibt die Skill um, lässt die Lücke allgemein und fragt am Ende mit
`Rückfrage:`; im Chat füllt die zweite Runde die Lücke, im `-p`-Modus bleibt sie offen.
Gefragt wird trotzdem, erfunden nie. Kostet: ein Text aus einem Lauf trägt offene Stellen.

**Phrasen sind Muster, keine Literale.** Die Wortliste aus R4.1 traf Beispiel 1 Vorher
wörtlich einmal; zwei Lückenmuster finden drei. `rules.md` führt die Listen zusätzlich
als Muster, ein Test hält sie wortgleich mit dem Skript. Kostet: eine andere Beugung
geht weiter durch.

**Vierzehn Zeilen, fünf Urteile.** Die zehn Prüfpunkte aus Abschnitt 8 plus die vier
Frequenzregeln, die der Entwurf beziffert (R1.4, R4.5, R4.6, R2.4); was kein Skript
beurteilt (R3.1, R5.3, R5.4, R2.3 zweiter Punkt, R5.2), steht unter `judgement` und
zählt nie als bestanden.

**Ein Treffer ist kein Muster.** Raten wie „eines je 300 Wörter" gelten mit
`max(1, …)`: In einer 60-Wörter-Mail ist ein Partizip-Anhängsel erlaubt, sonst wäre
jede Mail mit einem Doppelpunkt rot. Ein Behauptungsabsatz beginnt bei drei Sätzen;
kürzere Absätze sind Zäsur (R2.3), keine Behauptung.

**Der Rückverweis in `explain` nennt die Tokens nicht wörtlich.** Eine Zeile mit
`Next:` in dessen Abgrenzung hätte `evals_due: true` ausgelöst, ohne dass sich der
Contract von `explain` ändert. Das steht in known-limits, damit es keine stille
Umformulierung ist.

## Was gemessen wurde

- **1235 Tests grün**, 36 neu; ein vorbestehender Fehlschlag außerhalb
  (`rest-api-architect`, Spectral über npx).
- **Lint:** `lint_skill.py skills/human-prose` — 13 Regeln, alle `pass` nach Task 9;
  die vier Nachbarn mit `--base main` ohne neuen Befund und `evals_due: false`.
- **Die sechs Beispieltexte des Entwurfs, Prüfpunkt × Text**, als Erwartungswerte in
  den Tests:

| Regel | B1 vorher | B1 nachher | B2 vorher | B2 nachher | B3 vorher | B3 nachher |
| --- | --- | --- | --- | --- | --- | --- |
| R1.1 Zeichen | pass | pass | finding (1) | pass | pass | pass |
| R4.1/R4.2 Phrasen | finding (3) | pass | finding (4) | pass | pass | pass |
| R4.3 Partizip | pass (1 erlaubt) | pass | pass (1 erlaubt) | pass | pass | pass |
| R2.1 Streuung | finding (kein Satz ≤ 6) | pass | unchecked (1 Satz) | unchecked (3 Sätze) | pass | finding (kein Satz ≥ 20) |
| R2.2 Konnektor | pass | pass | pass | pass | pass | pass |
| R3.5 Rahmen | finding | pass | pass | pass | pass | pass |
| R5.1 Konkretion | finding | pass | unchecked | finding (Heuristik) | finding | unchecked |

Zwei Nachher-Texte sind rot, einer ungeprüft, und das bleibt so: R2.1 verlangt einen
Satz mit zwanzig Wörtern auch in einer Vier-Satz-Mail, R5.1 sieht im englischen
Fließtext von Beispiel 2 kein konkretes Element. Das sind Befunde über die Regeln,
nicht über die Texte; die Schwellen sind geschätzt.

- **Der Entwurf selbst** durch das Skript (1.530 Wörter ohne Zitate): 25,5 -ung je 1000
  (Grenze 15), 35 Doppelpunkte (erlaubt 10), Exit 1 — in der Spanne, die Spec 19 nennt.
- Jede Zahl hier ist nachgemessen, nicht aus dem Plan abgeschrieben.

## Was nicht gemessen wurde

**Die Evals im Harness** — nicht gefahren (root, `bypassPermissions`,
`docs/known-limits.md`, „Betrieb"). Der Lauf mit Subagenten außerhalb des Harness
steht unten.

**Der Trigger** — ob „das klingt nach KI, überarbeite" bei dieser Skill landet und
nicht bei `visual-summary`, entscheidet der Harness pro Lauf; Eval 5 misst es, wenn
er fährt.

**Die Baseline** — `--without-skill` (Spec 18) ist nicht gefahren; bei Eval 1
entscheidet dann die Register-Zeile, ob er etwas misst.

**Das Stilprofil** — `my-writing-style` ist nicht installiert; „Profil gewinnt, Skript
bleibt" ist Doktrin ohne Lauf.

**Die Heuristiken auf echten Texten** — Passiv, Fragment, Konkretion und Satzgrenze
sind an sechs Beispielen geprüft, nicht an einem Korpus.

## Offen für die nächste Runde

- Fünf bis zehn eigene Texte des Nutzers als Fixture, dann Schwellen messen statt
  schätzen (Spec 19, Open questions).
- R2.1 für Register `kurz` entscheiden: gilt „ein Satz mit zwanzig Wörtern" in einer
  Vier-Satz-Mail? Der Entwurf sagt ja, das Beispiel sagt nein.
- `--without-skill` über die fünf Evals, sobald der Harness beim Nutzer läuft.
