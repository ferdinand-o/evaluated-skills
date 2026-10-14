# settings.json mischen

`apply_config.py` schreibt die `settings.json` des Nutzers nur nach gezeigtem und
bestätigtem Plan. Mischen heißt: nur die Schlüssel unten, alles andere bleibt Byte für
Byte im Sinn des Inhalts erhalten.

## Was apply anfasst

| Schlüssel | Regel |
| --- | --- |
| `statusLine.command` | nur `command`; `type`, `padding`, `refreshInterval` und andere Felder bleiben. Fehlt `statusLine`, entsteht `{"type": "command", "command": …}` |
| `hooks.UserPromptSubmit` | ein eigener Eintrag mit dem Hook-Fragment aus `assets/settings/context-hint.json`; vorhandene fremde Einträge bleiben |
| `permissions.deny` | nur, wenn der Nutzer das Angebot im Plan bestätigt hat; Liste wird vereinigt |
| `enabledPlugins` | nur die Plugin-IDs aus dem Profil (`references/routing.md`), je auf `false`; andere Einträge bleiben. Ein schon gesetzter Wert kommt nur in den Patch, wenn die Antwort `plugins_off` die ID nennt |

## Was apply nie anfasst

Jeden anderen Schlüssel, auch unbekannte. Eine fremde Statusline (weder Kennzeile noch
bekannter Hash) bleibt eingetragen; der Plan sagt „Kontext-Hinweise nicht verfügbar —
fremde Statusline schreibt keinen Kontextzustand".

## Eigene Einträge erkennen

Ein Eintrag gehört setup-user, wenn sein Kommando einen Skriptpfad enthält, der auf
`setup-user/runtime/context_hint.py` bzw. `setup-user/runtime/statusline.py` endet
(Schrägstriche und Backslashes gleich behandelt). Ein vorhandener eigener Eintrag wird
ersetzt, nicht verdoppelt; so bleibt ein zweiter `apply` ohne Wirkung.

## Kommandos

- Statusline: `<python> "<config-dir>/setup-user/runtime/statusline.py"`
- Hook: `<python> "<config-dir>/setup-user/runtime/context_hint.py" || true`

`<config-dir>` wird beim `apply` als absoluter Pfad mit Schrägstrichen eingesetzt, auch
unter Windows, weil Git Bash Backslashes entfernt. `|| true` ist das zweite Netz, falls
das Skript fehlt: Ein `UserPromptSubmit`-Hook mit Exit 2 ließe den Prompt nicht durch.

## Schreibformat

Einrückung 2, `ensure_ascii=False`, Schlüsselreihenfolge des Bestands, neue Schlüssel
hinten, LF, Zeilenumbruch am Ende. Geschrieben wird über eine Temp-Datei im selben
Verzeichnis und `os.replace`.

## Reihenfolge und Backups

1. Backup jeder Datei, die gleich geändert wird, nach
   `<config-dir>/setup-user/backups/JJJJMMTT-hhmmss/` (bei Kollision `-2`, `-3`).
2. `runtime/` kopieren und jede Kopie per Hash gegen den Block prüfen.
3. `thresholds.json`.
4. CLAUDE.md und `rules/*.md` (nur `create` oder bestätigtes `append`).
5. Zuletzt `settings.json`.

Bricht ein Schritt ab, bleibt `settings.json` unberührt; ein Hook, dessen Skript fehlt,
wird so nie eingetragen.
