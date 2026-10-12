<!-- skill: setup-repo | schema: 1 | generated: python skills/setup-repo/scripts/plan_repo.py -->
# Ziele und entdeckte Arbeit

Gilt nur, solange `docs/goals.md` unter *Aktiv* mindestens ein Ziel hat; sonst nichts tun.
Kopfzeile von `docs/goals.md` zuerst prüfen; vor jedem Schreiben die Datei neu lesen.

Jede während der Arbeit entdeckte Aufgabe gehört in genau eine Klasse:

1. **Vom Nutzer verlangt** — steht im aktuellen Prompt: erledigen.
2. **Teil des Ziels** — nötig, damit „Fertig wenn" eintritt: erledigen.
3. **Trivial** — in einer Datei, die die Aufgabe ohnehin ändert, höchstens fünf Zeilen,
   keine neue öffentliche Schnittstelle, kein neuer Test nötig: erledigen, im Turn-Ende nennen.
4. **Neues Ziel** — alles andere: nicht umsetzen. Unter *Kandidaten* anhängen
   (`G<n>`, eins über dem höchsten `n` aller Tabellen), im Turn-Ende nennen.

Unter *Aktiv* trägt Claude nur ein, was der Nutzer ausdrücklich ein Ziel nennt, mit
prüfbarem „Fertig wenn", und schlägt die passende `/goal`-Zeile vor. Nach *Erledigt*
wandert ein Ziel nur mit Beleg (Befehl und Ergebnis).

Eine Meldung `[setup-repo] Geändert außerhalb des Bereichs …` heißt: Diese Dateien liegen
außerhalb der Bereiche aktiver Ziele. Ordne sie einer der vier Klassen zu und sag welcher.
Einen Merge-Konflikt in `docs/goals.md` nicht selbst lösen — fragen.
