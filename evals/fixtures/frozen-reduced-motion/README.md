# Kaputter reduced-motion-Zustand: Panel verschwindet statt statisch zu bleiben

`styles.css` setzt `.panel { display: none; }` unter
`prefers-reduced-motion: reduce` — der Inhalt ist damit für Nutzer mit
reduzierter Bewegung komplett unsichtbar, nicht bloß unanimiert. Das ist
genau der Fall, den motion-landings Budget-Contract verbietet: „nicht
animiert, nicht kaputt, nicht leer". Der Eval prüft, ob der Fix den Inhalt
bei reduzierter Bewegung sichtbar und statisch zeigt, statt ihn zu
verstecken.
