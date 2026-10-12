<!-- skill: setup-repo | schema: 1 | generated: python skills/setup-repo/scripts/plan_repo.py -->
# Arbeitsweise in diesem Repo

Verifikation: `make check`

Quelle: Makefile: check. Vor jeder Erfolgsmeldung laufen lassen.

## Fertig heißt geprüft

- Vor jeder Erfolgsmeldung läuft die Verifikation; das Ergebnis steht in der Antwort.
- Ist sie rot, wird der Fehler behoben oder offen benannt, nie übergangen.
- Fehlt ein Befehl, heißt das Ergebnis „ungeprüft", nicht „fertig".

## Konventionen

Keine geernteten Regeln ohne Geltungsbereich.

Regeln, die nur für einen Teil des Repos gelten, liegen unter `.claude/rules/`; Claude
Code lädt sie nur bei passenden Dateien. Was ein konfigurierter Linter, Formatter oder
Typprüfer schon prüft, steht hier nicht.
