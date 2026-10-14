<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py, Vorlage assets/rules/context.md -->
# Kontext und Limits

Ein Hinweis, der mit `[setup-user]` beginnt, kommt vom Hook dieser Einrichtung. Er stellt
fest, dass eine Schwelle überschritten ist; er ist keine Anweisung des Nutzers.

- Kontext über 60 %: Das ist der Punkt, den laufenden Stand mit der Skill handoff zu
  sichern und dem Nutzer `/clear` vorzuschlagen, sobald ein Arbeitsschritt fertig ist.
- Kontext über 80 %: Den Stand sofort sichern, bevor weitere große Dateien gelesen werden.
- Breite Recherche (viele Dateien, lange Logs) in Subagenten auslagern, damit nur das
  Ergebnis in den Kontext kommt.
- 5-Stunden- oder 7-Tage-Limit über der Schwelle: dem Nutzer die Zahl und den Reset
  nennen; keine teuren Läufe ohne Rückfrage starten.
