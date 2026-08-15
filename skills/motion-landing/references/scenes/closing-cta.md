# Closing-CTA — ruhiger Abschluss, kein zweites Feuerwerk

**Die Demo für diesen Szenen-Typ fehlt noch.** `assets/scenes/` enthält nur
Demos für `hero-reveal`, `scroll-telling`, `sticky-pin` und `canvas-moment`
(Entscheidung im Auftrag: vier real getestete Demos statt sieben halb
geprüfte). Wer eine `closing-cta`-Szene braucht, baut sie von Hand nach
diesem Rezept — ohne die Absicherung durch einen bereits gelaufenen
`verify.py`-Durchlauf gegen diese konkrete Demo.

## Mechanik

Die letzte Sektion der Seite — Handlungsaufforderung, oft mit Formular
oder Button. Bewusst zurückhaltend animiert: Die Choreografie-Doktrin
(`references/choreography.md`) verlangt genau einen Höhepunkt, und das ist
per Definition nicht diese Szene.

- **Technik:** `animation-timeline: view()` für ein einfaches Ein- und
  Hochblenden beim Erreichen, dieselbe Mechanik wie Hero-Reveal, aber ohne
  mehrteilige Orchestrierung — ein Element, eine Animation.
- Animiert werden `opacity` und `transform` (`translateY`), nichts
  Aufwendigeres.
- Kein Canvas, kein GSAP — wenn diese Szene eine aufwendigere Technik zu
  brauchen scheint, ist wahrscheinlich der Höhepunkt falsch platziert, nicht
  der Closing-CTA zu schwach.

## Parameter

- Timing: dezent, keine lange Sequenz — der Nutzer ist am Ende der Seite,
  Wartezeit vor der Handlungsaufforderung kostet Konversion.

## Fallstricke

- **Closing-CTA wird zum heimlichen zweiten Höhepunkt.** Ein Formular mit
  Partikel-Hintergrund oder aufwendiger Mehrschritt-Animation konkurriert
  mit dem eigentlichen Höhepunkt weiter oben — Verstoß gegen die
  Choreografie-Doktrin, auch wenn der Storyboard-Contract formal nur eine
  Markierung „Höhepunkt" erlaubt (die semantische Verletzung bleibt
  trotzdem eine).
- **CTA-Button selbst wird animiert statt nur die Sektion.** Ein pulsierender
  oder vibrierender Button wirkt schnell aufdringlich statt einladend —
  wenn überhaupt, ein sehr dezenter Hover-/Focus-State, keine
  Dauer-Animation.

## reduced-motion

Sektion und Button erscheinen direkt im Endzustand, kein Ein-/Hochblenden.
