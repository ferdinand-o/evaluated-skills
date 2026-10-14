# Prüfpunkte — für jedes Repo

Diese Punkte gelten unabhängig vom Stack und stehen in jedem `reviewer.md`.
Format je Zeile: `- **<id>** — <Prüfpunkt> Quelle: <Quelle>`.

## Prüfpunkte

- **gen-done-when** — Jede Bedingung unter „Fertig wenn" des Ziels ist belegt: durch eine Stelle im Diff oder durch einen Befehl mit Ergebnis. Quelle: Spec 22, Abschnitt „Review"; Zielregel `.claude/rules/goals.md`.
- **gen-scope** — Jede geänderte Datei liegt im Bereich des Ziels oder ist ein Hausartefakt, das der Bereichs-Hook ausnimmt. Quelle: Spec 22, Abschnitt „Bereichs-Hook"; `references/goals.md` von setup-repo.
- **gen-verification** — Der Verifikationsbefehl aus der CLAUDE.md-Zeile `Verifikation:` lief nach der letzten Änderung grün; fehlt die Zeile, heißt der Punkt „ungeprüft". Quelle: Spec 22, Eiserne Regel.
