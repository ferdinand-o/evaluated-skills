# Fixture: plan-disjoint-batch

Ein Plan mit vier vollständig unabhängigen Tasks — der Fall, in dem das Gate
`"parallel"` urteilen soll (mindestens drei überlappungsfreie Pakete, Spec 09
Approach). Zusätzlich liegt unter `dispatched-task-1/` das simulierte
Ergebnis eines bereits dispatchten Agenten für Task 1: er hat `batch_parse`
mit der falschen Anzahl Parameter geschrieben. Der Eval-Harness kann keinen
echten zweiten Agenten-Dispatch auslösen (siehe `docs/known-limits.md`); die
Fixture legt den abweichenden Code deshalb vorgefertigt an, und der Eval-
Prompt bittet die Skill, ihn mit `verify` mechanisch zu prüfen, *bevor* ein
Review stattfindet (Spec 09, Eval 3).
