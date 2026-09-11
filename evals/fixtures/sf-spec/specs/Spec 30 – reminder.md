# Spec 30 – reminder

**Zweck:** Auf „erinner mich an X" schreibt die Skill eine Zeile `Reminder: X` nach
`reminders.md` im Projektwurzelverzeichnis und antwortet mit genau dieser Zeile, sonst
nichts. Bestehende Zeilen bleiben; die neue kommt ans Ende.

**Tier:** 0, kein Skript. Abgrenzung: `handoff` (Übergabe am Sitzungsende) und
`note-tag` (taggt Notizen, schreibt keine Erinnerungen).
