---
name: setup-user
description: "Use when the user wants to set up or check their personal Claude Code config directory — \"richte meinen User-Scope ein\", \"setup-user\", \"prüf meine Claude-Konfiguration\", \"Statusline und Kontext-Hinweise einrichten\". Invoked only as /setup-user (plan, apply, check). Not for generating a statusline from a free-text wish (use the built-in /statusline) and not for configuring a repository for cloud sessions and CI (use setup-repo)."
disable-model-invocation: true
---

# setup-user — ein Config-Verzeichnis, das Claude über Kontext und Limits informiert

**Eiserne Regel:** *Nichts außerhalb von `<config-dir>/setup-user/` wird geschrieben,
bevor der Plan gezeigt und bestätigt ist — und keine Einrichtung heißt fertig, bevor die
installierten Befehle in einer Sandbox mit Beispiel-Eingabe gelaufen sind und das
erwartete Ergebnis geliefert haben.* G1 — diese Datei verlangt das Zeigen; dass Plan und
Bestand seit der Planung unverändert sind, meldet `apply_config.py` per Hash (G2).

Warum es die Skill gibt: Nur die Statusline bekommt Kontext- und Limitwerte fertig
geliefert, und Claude sieht die Statusline nicht. Die Statusline schreibt die Werte
deshalb in Dateien, und ein `UserPromptSubmit`-Hook meldet Claude das Überschreiten einer
Schwelle. Der Hook hält nie einen Prompt an.

## Ablauf

1. **Ziel nennen.** `--config-dir` ausdrücklich, sonst `$CLAUDE_CONFIG_DIR`, sonst
   `~/.claude`. Die erste Zeile der Antwort nennt den aufgelösten Pfad. Mehrere
   Config-Verzeichnisse (mehrere Accounts) bekommen je einen eigenen Lauf.
2. **Interview, höchstens drei Fragen**, nur was nicht im Bestand steht: Sprache und Ton,
   Rechner und Shell, Git-Gewohnheiten. Ohne Antwort (etwa bei `claude -p`) gelten die
   Asset-Werte, und der Plan führt sie als Annahme.
3. **plan (Default):**
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/inspect_config.py" --config-dir <pfad> --answers '{"language": "Deutsch"}'
   ```
   Schreibt nur `<config-dir>/setup-user/plan.md`. Zeig dem Nutzer die Ansicht daraus:
   Statusline-Befund, Plugins, Änderungen, Annahmen. Dann endet der Lauf; angewendet wird
   in einem späteren Aufruf.

   **Plugins:** Der Plan schlägt das Profil aus `references/routing.md` vor — superpowers
   aus, sobald die Abschaltbedingung aus Spec 20 erfüllt ist, engineering aus als
   Annahme. Steht ein Plugin schon in `enabledPlugins` (eine Installation per CLI setzt
   `true`), führt der Plan es als Konflikt und dreht es nie selbst um. Frag den Nutzer
   einmal; nur ein ausdrückliches Ja geht als `"plugins_off": ["<id>"]` in `--answers`,
   dann neu planen.
4. **apply**, erst nach ausdrücklicher Bestätigung und nur mit `--config-dir` auf der
   Kommandozeile:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/apply_config.py" --plan <pfad>/setup-user/plan.md --config-dir <pfad>
   python "${CLAUDE_SKILL_DIR}/scripts/verify_install.py" --config-dir <pfad>
   ```
   Bricht `apply` mit „Hash passt nicht" oder „Bestand geändert" ab, wird neu geplant,
   nie der Block von Hand angepasst.
5. **check:**
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/verify_install.py" --config-dir <pfad> --write-check
   ```
   Prüflauf und Vergleich mit den Assets; schreibt nur
   `<config-dir>/setup-user/check.md` mit Kopfzeile, mit Abweichungen oder „keine
   Abweichung". Ein fehlendes Hook- oder Statusline-Skript ist die erste Abweichung.
   Ein relativer Skriptpfad steht als Hinweis „nur im Arbeitsverzeichnis gültig" da, nicht
   als Abweichung. Ein ausstehender `plan.md` bleibt unberührt. Am Ende steht der
   Abschnitt `## Plugins` aus `route_check.py`: aktive Plugins, SessionStart-Hooks,
   Kollisionen, `superpowers:`-Verweise, Stand der Abschaltbedingung — Information, keine
   Abweichung. Nenn dem Nutzer die SessionStart-Hooks und den Stand der Bedingung.

**Übergabe nach apply**, wörtlich eine von zwei Formen:

- „angewendet und geprüft, wirkt ab der nächsten Session" — `verify_install.py` ohne
  Befund und ohne „ungeprüft".
- „angewendet, ungeprüft — <Grund>" — etwa „fremde Statusline nicht ausgeführt" oder
  „keine bash". Nie „fertig" ohne Prüflauf.

## Statusline

- **Eigene** (Kennzeile `# setup-user: statusline` oder ein Hash aus
  `assets/runtime/known-statusline-hashes.json`): `statusLine` zeigt danach auf
  `runtime/statusline.py`, die alte Datei bleibt liegen, die Anzeige bleibt gleich.
- **Keine**: `apply` setzt das Asset ein.
- **Fremde**: bleibt eingetragen. Der Plan sagt „Kontext-Hinweise nicht verfügbar —
  fremde Statusline schreibt keinen Kontextzustand". Der Hook wird trotzdem eingetragen
  und schweigt, bis der Nutzer wechselt.

Was gemischt, ersetzt und nie angefasst wird: `references/settings-merge.md`. Format,
Normalisierung und Hash des Plans: `references/plan-format.md`. Schwellen, Merker und
Wortlaut der Hinweise: `references/thresholds.md`. Plugin-Profil, aktive Plugins und
Abschaltbedingung: `references/routing.md`, Lückentabelle `references/superpowers-gaps.json`.

## Contract

- **Plan vor Schreiben.** `plan` und `check` schreiben nur `plan.md` bzw. `check.md` und
  Dateien in der Sandbox der Prüfung. `apply` braucht `--config-dir` auf der
  Kommandozeile und ein existierendes Verzeichnis; es legt keins an.
- **Mischen, nie überschreiben.** Backup jeder berührten Datei unter
  `setup-user/backups/`; eigene Einträge werden ersetzt, nicht verdoppelt; fremde
  Schlüssel bleiben; vorhandene CLAUDE.md und Regeln bekommen nur bestätigte Ergänzungen.
- **Der Hook hält nie etwas an.** Er endet immer mit 0, das Kommando trägt `|| true`,
  und `settings.json` wird als Letztes geschrieben.
- **Geprüft heißt gelaufen.** `verify_install.py` führt nur Befehle aus, deren Skript
  einem Asset gleicht, mit `CLAUDE_CONFIG_DIR`, `HOME` und `USERPROFILE` in einem
  Temp-Verzeichnis. Fremde Befehle laufen nie.
- **Hinweise sind selten und belegt:** höchstens einer je Prompt, je Schwelle einmal bis
  zum Wiederscharfwerden, nur mit gültigen Werten; sonst Schweigen.
- **Anti-Zeremonie:** `check` auf ein Verzeichnis, das dem Plan schon entspricht, ändert
  keine Datei außer `check.md` und meldet „keine Abweichung".

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Der Nutzer hat ja gesagt, er will es eingerichtet haben — ich wende gleich an" | Bestätigt wird der gezeigte Plan, nicht der Wunsch. Ohne gezeigten `plan.md` kein `apply`. |
| „Die alte Statusline läuft schon, die prüfe ich gleich mit" | Sie ignoriert `CLAUDE_CONFIG_DIR` und schriebe Beispielwerte in den echten Cache. Fremd heißt: nicht ausführen, „ungeprüft" sagen. |
| „superpowers ist laut Bedingung abschaltbar, der Nutzer will das bestimmt" | Ein gesetzter Wert ist eine Entscheidung, auch wenn die CLI sie getroffen hat. Fragen, und nur ein Ja wird `plugins_off`. |
| „Der Hash passt nicht, ich korrigiere den Block schnell von Hand" | Dann bestätigt der Nutzer etwas, das er nie gesehen hat. Neu planen, neu zeigen. |
| „verify schweigt sich aus, das ist schon gut gegangen" | Ohne Lauf heißt die Übergabe „angewendet, ungeprüft — Grund". |
| „Ich schreibe die Regel direkt in die vorhandene CLAUDE.md, das ist praktischer" | Vorhandenes bekommt nur bestätigte Ergänzungen; der Plan zeigt sie vorher. |

## Abgrenzung

- **handoff** — sichert den Sitzungsstand; setup-user installiert nur den Hinweis, der
  bei hohem Kontext dazu rät (`rules/context.md`).
- `/statusline` (eingebaut) — erzeugt eine Statusline nach Freitext-Wunsch; setup-user
  übernimmt eine vorhandene und erzeugt keine nach Wunsch.
- setup-repo — richtet ein Repo ein; was in Cloud-Sessions und CI gelten muss, gehört
  dorthin, denn Cloud-Sessions lesen den User-Scope nicht.
- skill-forge — baut und ändert Skills; setup-user ändert keine Skill.
- anthropic-skills:setup-writing-style — Stimmprofil; setup-user schreibt keine
  Stilregeln außer Sprache und Ton.
