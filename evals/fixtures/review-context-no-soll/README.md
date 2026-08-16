# Fixture: review-context-no-soll

Ein Repo mit genau einem deklarierten Commit über der Baseline. Kein
`docs/specs/wip/`, kein `docs/decisions.md`, keine PR-Beschreibung wird
mitgegeben. `find_commit_message_soll()` zählt einen einzelnen Commit nicht
als Soll (Tautologie-Vermeidung) — der Fall ist also bewusst so konstruiert,
dass `resolve_soll()` `source == "none"` liefert.
