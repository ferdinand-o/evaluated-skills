# Merge-Protokoll

Gilt nach jeder abgenommenen Task (`verify` und Vertragsprüfung, siehe SKILL.md und
`contract-check.md`), egal ob sie parallel oder sequenziell entstand. Ein Review läuft
nicht je Task, sondern nur an den Prüfpunkten, die `checkpoint status` nach dem Merge
meldet (`checkpoints.md`).

## Reihenfolge

**Sequenziell in Abhängigkeitsreihenfolge des Plans** — nicht in
Fertigstellungsreihenfolge. Eine Task, die per `Consumes:` von einer anderen
abhängt, merged nach ihrem Produzenten, selbst wenn sie zuerst fertig wurde.
`gate.json`s `components` nennt, welche Tasks als zusammenhängend erkannt
wurden; innerhalb einer Komponente ist die Plan-Reihenfolge (Task-ID) die
Merge-Reihenfolge, sofern der Plan nichts anderes vorgibt.

**Kein „alles auf einmal mergen und hoffen".** Jeder Merge ist ein eigener
Schritt mit eigenem Testlauf danach — ein gescheiterter Testlauf zeigt dann
genau, welcher Merge ihn verursacht hat.

## Nach jedem Merge

Tests des Gesamtstands laufen — nicht nur die Tests der gemergten Task. Eine
Task, die für sich grün war, kann im Zusammenspiel mit einer anderen rot
werden; genau das soll dieser Schritt fangen, bevor die nächste Task darauf
aufbaut.

Danach `checkpoint status --after-task <N>`, bei roten Gesamttests nach deren Behebung
mit `--tests-red`. Ist ein Prüfpunkt fällig, startet die nächste Task erst nach dem
Review über den gemeldeten `range`, dem Fix seiner Funde und `checkpoint mark`.

## Fix-Runden je Task

Fällt `verify` oder die Vertragsprüfung durch, fixt die Task im selben Worktree,
höchstens zwei Runden. Lief sie mit Sonnet, folgt ein Versuch mit Opus in einem frischen
Worktree von derselben Basis, mit der Task-Datei und den Ergebnissen der gescheiterten
Runden; danach Eskalation an den Nutzer. Das gilt für jede Task einzeln, gemergt wird
erst nach bestandenem `verify`.

## Interface-Brüche

Ein Interface-Bruch zwischen zwei gemergten Paketen (Task B ruft eine
Signatur von Task A auf, die nicht passt) ist **per Definition ein
Gate-Fehler** — die Überlappungserkennung hätte diese Abhängigkeit als
Interface-Overlap erkennen und die beiden Tasks nicht unabhängig voneinander
laufen lassen sollen (oder `verify` hätte die abweichende `Produces`-Signatur
vor dem Merge fangen müssen).

- Den Bruch **jetzt** beheben — der laufende Merge blockiert sonst alles
  Nachfolgende.
- **Als Lesson im Plan vermerken**, nicht nur im Code fixen: eine Zeile unter
  dem betroffenen Task, die benennt, welches Symbol wie abwich und warum die
  Erkennung es nicht fing (fehlendes Backtick-Symbol in `Produces:`, ein
  Interface, das nur in Prosa ohne Backticks beschrieben war, ein
  `verify`-Lauf, der übersprungen wurde). Diese Lessons sind der Grund, warum
  ein Interface-Bruch hier ein Gate-Fehler heißt und nicht nur "Pech" — sie
  verbessern das nächste Gate-Urteil, nicht nur diesen einen Merge.

## Abschluss

Wenn alle Tasks eines Plans gemerged und die Gesamttests grün sind, folgt ein finaler
Prüfpunkt über `base..HEAD` (Profil `standard`), mit Fix-Pfad wie an jedem Prüfpunkt.
Erst danach ist der Plan fertig im Sinn dieser Skill. Was danach kommt (Branch-Abschluss, PR),
ist nicht Teil dieses Protokolls.
