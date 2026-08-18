# Choreografie-Doktrin: Dramaturgie statt Effekt-Sammlung

Der häufigste Fehler eines animierten Landing Pages ist nicht zu wenig
Bewegung, sondern zu viel gleichverteilte Bewegung — jede Sektion fliegt,
dreht, federt, und nichts sticht heraus. Diese Skill kodiert das
Gegenmittel als Regel, nicht als Geschmacksfrage.

## Ein Höhepunkt pro Seite

Der Storyboard-Contract (SKILL.md) erzwingt das strukturell: genau eine
Szene trägt die Markierung „Höhepunkt". Alles andere ist Vorbereitung oder
Nachklang. Das ist die eine Regel, gegen die jede andere Entscheidung in
diesem Dokument abgewogen wird.

**Testfrage beim Storyboard-Entwurf:** Wenn du eine zweite Szene als
Höhepunkt markieren willst, ist mindestens eine davon keiner — welche?

## Spannungsbogen

1. **Hero-Reveal** — die Seite lädt, orchestriert (nicht alle Elemente
   gleichzeitig). Setzt den Ton, ist noch nicht der Höhepunkt.
2. **Ruhige Szenen** — Scroll-Telling, Stagger-Grid, Marquee. Bewegung
   folgt hier der Lesegeschwindigkeit, nicht umgekehrt: Ein Nutzer, der
   schnell scrollt, verpasst nichts Notwendiges, weil der Inhalt ohne JS
   ohnehin lesbar ist (Budget-Contract in SKILL.md).
3. **Der Höhepunkt** — meist `canvas-moment` oder ein besonders
   orchestriertes `scroll-telling`. Die einzige Stelle, an der die Skill
   den Aufwand einer aufwendigeren Technik (GSAP, Canvas) rechtfertigt.
4. **Closing-CTA** — ruhig, klar, keine Konkurrenz zum Höhepunkt. Eine
   Handlungsaufforderung, kein zweites Feuerwerk.

## Pacing

- Bewegung beginnt, wenn der Nutzer sie auslöst (Scroll, Viewport-Eintritt),
  nie automatisch mit Verzögerung — das ist die Wurzel von
  Scroll-Hijacking-artigem Verhalten, auch wenn kein Scroll gekapert wird.
- Eine Szene, die beim ersten Betrachten nicht verstanden wird, ist zu
  schnell oder zu überladen — nicht durch mehr Bewegung reparieren, durch
  weniger.
- Ruhepausen zwischen Szenen sind Teil der Dramaturgie, nicht ihr Fehlen.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Noch ein Parallax-Layer wertet die Sektion auf" | Wertet sie nicht auf, wenn sie nicht der Höhepunkt ist — verteilt nur Aufmerksamkeit weg vom einen Moment, der sie verdient. |
| „Der Kunde wollte 'wow' auf jeder Sektion" | „Wow" ist ein Budget, kein Preis pro Sektion. Ein Storyboard mit einem Höhepunkt liefert mehr „wow" an der Stelle, die zählt, als sieben verwässerte. |
| „GSAP kann das eleganter, nehmen wir es überall" | Tech-Tree zuerst: CSS Scroll-Driven trägt die meisten Szenen. GSAP ist für die eine, die es wirklich braucht. |
| „Reduced-motion ist ein Nice-to-have für später" | Pflicht-Gate (SKILL.md). Eine Szene ohne definierten reduced-motion-Zustand ist unfertig, nicht „noch ohne Extra". |
