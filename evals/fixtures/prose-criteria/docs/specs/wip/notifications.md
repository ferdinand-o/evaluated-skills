<!-- skill: feature-spec | schema: 1 | generated: feature-spec Draft für "Notifications" -->
# Feature: Notifications

## Problem
Nutzer verpassen Aufgaben mit Fälligkeitsdatum, weil nichts an sie
erinnert. Die Codebase hat bereits einen E-Mail-Versand, aber keine
geplanten Erinnerungen.

## Non-Goals
- Kein plattformübergreifendes Settings-Sync — nur dieses Gerät.
- Keine SMS- oder Push-Kanäle, nur E-Mail.

## Annahmen
- Annahme: Erinnerungen laufen über den bestehenden `EmailService` —
  widersprich, falls du einen neuen Kanal willst.

## Ansatz
Ein geplanter Job prüft stündlich fällige Aufgaben und verschickt bei
Treffer eine E-Mail über den bestehenden `EmailService`.

## Akzeptanzkriterien

### Erinnerungsmail wird verschickt
- Given eine Aufgabe hat ein Fälligkeitsdatum in 24 Stunden
- When der geplante Erinnerungs-Job läuft
- Then verschickt `EmailService` eine Erinnerungsmail

### Erinnerung bei Verschiebung
Wenn der Nutzer das Fälligkeitsdatum einer Aufgabe verschiebt, für die
bereits eine Erinnerung geplant war, soll die alte Erinnerung storniert und
eine neue passend zum neuen Datum eingeplant werden. Das System merkt sich
dafür den letzten geplanten Erinnerungszeitpunkt pro Aufgabe.

## Offene Fragen
- Soll eine bereits verschickte (nicht nur geplante) Erinnerung bei
  Verschiebung nachträglich korrigiert werden? — Entscheider: du.
