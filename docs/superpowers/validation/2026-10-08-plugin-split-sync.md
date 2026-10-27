<!-- skill: subagent-dev | schema: 1 | generated: von Hand nach docs/superpowers/plans/2026-10-08-plugin-split.md, Task 1 -->

# Sync-Messung für Spec 20 (Aufgabe 0)

Stand: 2026-10-08. Plan: `docs/superpowers/plans/2026-10-08-plugin-split.md`, Task 1.
Probe-Branch: `claude/plugin-split-sync-probe` (Commit `d6f119c`), verwaist, enthält nur
den Wegwerf-Marketplace.

## Schritt 1: Vorher messen

Vom Nutzer am 2026-10-08 aus einer lokalen Session mit installiertem Plugin
`evaluated-skills` gemeldet, Skills-Eintrag aus `/context`:

| Skill | Tokens |
| --- | --- |
| debug-ledger | ~300 |
| motion-landing | ~280 |
| explain | ~280 |
| impl-plan | ~270 |
| learning-coach | ~260 |
| architecture-map | ~230 |
| exercise-forge | ~210 |
| human-prose | ~190 |
| dev-report | ~170 |
| enterprise-ui | ~160 |
| feature-spec | ~150 |
| handoff | ~120 |
| sql-schema-architect, rest-api-architect, verified-research, review-context, testing-strategy, visual-summary, skill-forge, subagent-dev, ui-architect | je < 20 |

Befund: 21 Skills geladen, `cad-parts` fehlt wie vorgesehen. Die zwölf ersten tragen
zusammen rund 2 620 Tokens; neun Skills stehen mit weniger als 20 Tokens da, also
praktisch nur mit ihrem Namen. Das passt zu einem überlaufenden Listing-Budget, bei dem
Descriptions wegfallen (skills-Doku); ungeprüft ist, ob das hier die Ursache ist. Neun
Skills, darunter testing-strategy, review-context und subagent-dev, wären dann für das
Routing ohne Description. Die Session-Art und die Herkunft des Plugins (CLI-Marketplace
oder claude.ai-Sync) sind noch offen.

## Schritt 2: Wegwerf-Branch

Gebaut und gepusht. Inhalt:

- `.claude-plugin/marketplace.json` mit `probe-a` (`source: "./plugins/probe-a"`,
  `defaultEnabled: true`) und `probe-b` (`source: "./plugins/probe-b"`,
  `defaultEnabled: false`), je `strict: false`, kein `version`, keine `plugin.json`.
- je eine Skill `probe-a-skill` und `probe-b-skill`.
- `.claude/settings.json` mit `"enabledPlugins": {"probe-x@synced": false}` für eine
  nicht installierte ID.

`claude plugin validate .` mit CLI 2.1.294: „Validation passed".

Vergleichswert CLI-Weg, mit einem Wegwerf-`CLAUDE_CONFIG_DIR` gemessen: Nach
`claude plugin marketplace add <pfad>` und `install` beider Plugins zeigt
`claude plugin list` `probe-a` aktiv und `probe-b` deaktiviert, je aus dem eigenen
Quellordner gelesen. Die User-Settings tragen `probe-a@plugin-split-probe: true` und
`probe-b@plugin-split-probe: false`.

## Schritt 3: Sync-Weg in claude.ai

Nicht gemessen, weil es nichts zu messen gibt. Angaben des Nutzers vom 2026-10-08:

- Die `/context`-Werte aus Schritt 1 stammen aus einer lokalen Session, das Plugin ist
  per CLI-Marketplace angebunden.
- Der Ordner `plugins/synced/` enthält nur Skills, keine Plugins mit Skills.
- Plugins werden in Cloud-Sessions nicht eingebunden (vom Nutzer als Bug gemeldet,
  noch offen); dort helfen nur Projekt-Skills, also setup-repo.
- Beim Einbinden eines Plugins per Repository auf claude.ai lässt sich kein Branch
  wählen; ein Wegwerf-Branch wäre dort gar nicht prüfbar.

Damit trägt die Begründung für eigene Quellordner mit generierten Kopien nicht mehr:
Spec 20 brauchte sie nur, weil der Sync-Weg eine `skills`-Liste nicht als Filter liest.
Auf dem CLI-Weg filtert die Liste. Der Probe-Branch ließ sich aus der Cloud-Session nicht löschen (Proxy: kein Schreibzugriff auf Branch-Löschungen); der Nutzer löscht `claude/plugin-split-sync-probe` auf GitHub.

## Schritt 4: Entscheidung

Spec 20 wird auf den CLI-Weg umgestellt: drei Einträge mit `source: "./"` und
`skills`-Liste, keine Plugin-Kopien. Die Projekt-Kopien unter `.claude/skills/` bleiben,
weil Cloud-Sessions nur sie laden.

Ergebnis: Stopp — Prämisse des Sync-Wegs entfällt, Spec 20 und Plan werden vereinfacht.
