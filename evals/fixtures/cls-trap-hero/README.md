# CLS-Falle: Hero fliegt per margin-top ein

`styles.css` animiert `.hero` über `margin-top` — jeder Frame verschiebt
den nachfolgenden Inhalt neu, das ist ein klassischer Layout-Shift und
verstößt gegen die NEVER-Liste von `motion-landing` (nur `transform`/
`opacity` animieren). Der Eval prüft, ob der Fix `margin-top` durch
`transform: translateY(...)` ersetzt, nicht nur den Zahlenwert ändert.
