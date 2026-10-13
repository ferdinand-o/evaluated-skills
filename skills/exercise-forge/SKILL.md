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
   startet mit `verification = {"method": "not_run", "detail": "Blind-Gate
   noch nicht gelaufen", "checked_at": null, "protocol": null}` — kein
   `status`-Feld (siehe Contract unten).
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
5. **Bei `suspicious`:** Lies die zitierte Begründung des Blind-Lösers im
   `detail`-Feld und beurteile selbst, ob sie trägt (das Gate markiert nur den
   Verdacht, es urteilt nicht — siehe Contract unten). Trägt sie: Distraktor
   schärfen (MC), Kriterium lockern (offene Frage), Test entschärfen (Coding)
   oder Vorderseite präzisieren (Flashcard), **dann `verify_blind.py` erneut
   aufrufen** — nicht "nochmal überlegen", sondern der Skriptaufruf selbst.
   Trägt sie nicht (nur falsch geraten): derselbe erneute Skriptaufruf reicht,
   ohne etwas an der Aufgabe zu ändern — nie die Musterlösung ändern, nur weil
   der Blind-Löser abwich. **Bis zu diesem erneuten Aufruf bleibt der
   abgeleitete Status `suspicious`.** Du erklärst den Fund in deiner Antwort —
   das ändert das zugrundeliegende `protocol` nicht mit; nur ein neuer
   Skriptlauf tut das (siehe Contract).
6. **Export:**
   ```bash
   python skills/exercise-forge/scripts/export.py --exercises <pfad> --out-dir docs/exercises
   ```
   Schreibt `docs/exercises/<thema>.md` (Aufgaben/Lösungen getrennt) und
   `docs/exercises/<thema>-anki.csv`. Jede Aufgabe trägt sichtbar ihren
   Verifikationsstatus — `[geprüft]` nur bei `verified`, sonst
   `[UNGEPRÜFT: <Grund>]` bzw. den Tag `suspicious`/`unverified` in der CSV.

## Contract

- **Blind-Verifikation ist Pflicht-Gate, keine Ausnahme.** Jede Aufgabe trägt
  ein `verification`-Objekt (`method`, `detail`, `checked_at`, `protocol`).
  **Es gibt kein `status`-Feld.** `verified`/`suspicious`/`unverified` sind
  keine Werte, die irgendwo stehen — sie werden aus `protocol` abgeleitet,
  jedes Mal neu, von jedem, der sie braucht.
- **Drei Fix-Runden, um dahin zu kommen — jede vorherige Fassung wurde
  gemessen und war zu schwach.** (1) Eine reine Doktrin ("schreib `status`
  nie selbst") reichte nicht: eine Session setzte `status: "verified"`,
  nachdem sie einen Konflikt bereits gemeldet hatte. (2) `export.py` beim
  Rendern von `status` zu entkoppeln (`derive_status_from_protocol()`) schloss
  die Lücke fürs Übungsblatt, ließ den Widerspruch aber im Aufgaben-JSON selbst
  stehen — einem Artefakt, das auch `learning-coach` (Zyklus 14) liest.
  (3) Erst das Entfernen des Feldes schließt die Lücke an der Quelle: Ohne
  `status` gibt es nichts, dem ein `[geprüft]` widersprechen könnte. Die
  Ableitungsregel steht in `references/task-schemas.md` — dort auch der
  Hinweis für `learning-coach`, dieselbe Regel nachzuziehen.
- **Melden ersetzt nicht Markieren — das gilt weiter, ist aber jetzt Doktrin
  über einer strukturellen Tatsache, nicht die einzige Verteidigung.** Du
  schreibst `verification` nie selbst; ohne `status`-Feld gibt es darin
  ohnehin nichts mehr zu fälschen, das ein Rendering beeinflussen würde.
- Eine Aufgabe ohne vollständigen Prüfnachweis (fehlendes/unpassendes
  `protocol`) wird als ungeprüft exportiert, nicht stillschweigend als
  geprüft.
- Coding-Musterlösungen müssen ihre eigene Testsuite bestehen, bevor eine
  Blind-Lösung überhaupt getestet wird — scheitert die Musterlösung, ist die
  Aufgabe fehlerhaft, kein Blind-Löser-Problem.
- **Was das MC-Gate wirklich leistet:** Wählt der Blind-Löser einen
  Distraktor, markiert das Gate die Aufgabe als `suspicious` — jede Fehlwahl
  identisch, unabhängig davon, ob die Begründung trägt. Das ist eine
  Markierung zur menschlichen Durchsicht, **kein Urteil darüber, ob die
  Begründung valide war**. Ob ein `suspicious`-Treffer einen kaputten
  Distraktor aufdeckt oder nur eine falsch geratene, eigentlich funktionierende
  Falle war, entscheidest du beim Review — das Gate liefert dafür die zitierte
  Begründung des Blind-Lösers, kein Verdikt.
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
| „Ich hab den Fund doch erklärt, das reicht" | Melden ersetzt nicht Markieren. Nur ein Skriptlauf ändert `protocol` (und damit den abgeleiteten Status) — deine Erklärung allein tut es nicht. |

## Abgrenzung

- **learning-coach** (Zyklus 14) — liest das Aufgaben-JSON dieser Skill als
  Schnittstelle, führt aber Lernstand und Fälligkeit; diese Skill erzeugt und
  prüft nur die Aufgaben selbst.
- **visual-summary** — ad-hoc Zusammenfassungen beliebiger Inhalte, kein
  geprüftes Lernmaterial.
- Ohne verfügbare `claude`-CLI (Blind-Löser) oder `pytest` (Coding-Tests)
  bleiben betroffene Aufgaben `unverified` — die Skill exportiert sie trotzdem,
  sichtbar markiert, statt den Export zu verweigern.
