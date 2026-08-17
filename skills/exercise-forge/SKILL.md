---
name: exercise-forge
description: Use when creating study exercises for a topic — multiple choice, open questions, coding tasks, or flashcards — that must be pedagogically sound before reaching a learner. Every exercise passes an independent blind-solve gate (a fresh agent solves it without seeing the model solution) before export to a Markdown worksheet or Anki CSV. Triggers include "Übungsaufgaben zu X", "Karteikarten erstellen", "Multiple-Choice-Fragen zu X", "Coding-Übung für X", "quiz me on X". Not for tracking what to review next or session state (use learning-coach) and not for ad-hoc content summaries (use visual-summary).
---

# exercise-forge — verifizierte Lernaufgaben

**Keine Aufgabe erreicht den Lernenden, die nicht blind gelöst wurde.** Ein
Subagent ohne Sicht auf die Musterlösung löst jede Aufgabe; weicht er ab, ist
die Aufgabe verdächtig — nicht der Blind-Löser.

## Ablauf

1. **Lernziel und Bloom-Ebene klären.** Erinnern → Flashcard, Verstehen →
   Multiple Choice, Anwenden/Analysieren → offene Frage oder Coding.
2. **Aufgabe erzeugen** nach `references/task-schemas.md` — Stamm, Optionen
   (MC), Musterlösung/Kriterien (offen), Musterlösung/Testsuite (Coding),
   Vorder-/Rückseite (Flashcard). Distraktoren nach `references/distractors.md`,
   Schwierigkeitsvektor nach `references/difficulty.md`. Jede neue Aufgabe
   startet mit `verification.status = "unverified"`, `method = "not_run"`.
3. **Ablegen** in der Aufgaben-JSON:
   `~/.skills/verified-research/research/<thema>.exercises.json`, oder
   projektlokal unter `.skills/verified-research/research/<thema>.exercises.json`,
   falls dieses Verzeichnis im Projekt existiert (Override gewinnt vor Home).
   Existiert die Datei noch nicht, kündige den Pfad an, bevor du sie anlegst.
4. **Blind-Gate:**
   ```bash
   python skills/exercise-forge/scripts/verify_blind.py --exercises <pfad> --id <id>
   python skills/exercise-forge/scripts/verify_blind.py --exercises <pfad> --all
   ```
   Für Coding-Aufgaben ruft das Skript automatisch `run_coding.py` (pytest)
   auf. Fehlt `pytest` oder die `claude`-CLI, wird das benannt gemeldet und die
   Aufgabe bleibt `unverified` — nie stillschweigend `verified`.
5. **Bei `suspicious`:** Distraktor schärfen (MC), Kriterium lockern (offene
   Frage), Test entschärfen (Coding) oder Vorderseite präzisieren (Flashcard).
   Erst danach erneut prüfen — nie die Musterlösung ändern, nur weil der
   Blind-Löser abwich.
6. **Export:**
   ```bash
   python skills/exercise-forge/scripts/export.py --exercises <pfad> --out-dir docs/exercises
   ```
   Schreibt `docs/exercises/<thema>.md` (Aufgaben/Lösungen getrennt) und
   `docs/exercises/<thema>-anki.csv`. Jede Aufgabe trägt sichtbar ihren
   Verifikationsstatus — `[geprüft]` nur bei `verified`, sonst
   `[UNGEPRÜFT: <Grund>]` bzw. den Tag `suspicious`/`unverified` in der CSV.

## Contract

- **Blind-Verifikation ist Pflicht-Gate, keine Ausnahme.** Jede Aufgabe im
  Export trägt ein `verification`-Objekt. `status: verified` entsteht
  ausschließlich durch das Blind-Gate — nie von Hand gesetzt.
- Eine Aufgabe ohne Prüfnachweis (oder mit `suspicious`) wird als ungeprüft
  exportiert, nicht stillschweigend als geprüft.
- Coding-Musterlösungen müssen ihre eigene Testsuite bestehen, bevor eine
  Blind-Lösung überhaupt getestet wird — scheitert die Musterlösung, ist die
  Aufgabe fehlerhaft, kein Blind-Löser-Problem.
- Ein Distraktor, den der Blind-Löser mit nachvollziehbarer Begründung wählt,
  ist kaputt — auch wenn er "eigentlich klar falsch" gemeint war.
- Flashcards: eine Information pro Karte. Fordert der Nutzer "20 Karten zu X",
  bleibt jede Karte atomar statt zu einer Karten-Müllhalde zu werden.
- "Eine Stufe schwerer" ändert den Schwierigkeitsvektor nachvollziehbar
  (Schritte, Vorwissen oder Transferdistanz) — nicht nur die Wortwahl im Stamm.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Die Lösung ist offensichtlich richtig" | Offensichtlich ist kein Prüfverfahren. Blind-Gate läuft immer. |
| „Der Distraktor ist halt knapp daneben" | Knapp daneben mit valider Begründung ist kaputt. |
| „Zehn Aufgaben auf einmal sparen Prüfzeit" | Ungeprüfte Menge ist kein Wert; das Gate skaliert mit. |
| „Schwierig heißt: klingt kompliziert" | Der Vektor entscheidet, nicht der Klang. |
| „pytest fehlt, ich sag einfach 'verified'" | Fehlende Werkzeuge sind ein benannter Befund, nie ein stilles Bestehen. |

## Abgrenzung

- **learning-coach** (Zyklus 14) — liest das Aufgaben-JSON dieser Skill als
  Schnittstelle, führt aber Lernstand und Fälligkeit; diese Skill erzeugt und
  prüft nur die Aufgaben selbst.
- **visual-summary** — ad-hoc Zusammenfassungen beliebiger Inhalte, kein
  geprüftes Lernmaterial.
- Ohne verfügbare `claude`-CLI (Blind-Löser) oder `pytest` (Coding-Tests)
  bleiben betroffene Aufgaben `unverified` — die Skill exportiert sie trotzdem,
  sichtbar markiert, statt den Export zu verweigern.
