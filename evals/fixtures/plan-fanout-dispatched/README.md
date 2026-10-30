# Fixture: plan-fanout-dispatched

Der Plan aus `plan-fanout` und eine `CLAUDE.md` im ersten Commit mit Tag `base`;
der zweite Commit ist das Ergebnis von Task 1: `parse_order(line, strict)` ohne
Default. Task 3 und 4 erwarten `fn:parse_order(line)`, die `Produces`-Zeile von
Task 1 nennt keine Arity — nur der Abnehmer-Check von `verify` fängt die
Abweichung (`arity_mismatch`, Verdikt `fail`) — Spec 27, Eval 4.
