# Routing — Plugin-Profil, aktive Plugins, Abschaltbedingung

`scripts/route_check.py` liest nur; `inspect_config.py` nimmt seinen Bericht in den Plan,
`verify_install.py --write-check` hängt ihn als `## Plugins` an `check.md`. Plugin-Befunde
sind Information, keine Abweichung.

## Plugin-Profil

| Plugin | User-Scope |
| --- | --- |
| `cc-dev`, `cc-setup`, `cc-knowledge` | nicht gesetzt; `defaultEnabled: true` genügt |
| `cc-ui` | nicht gesetzt; an per Projekt (setup-repo) |
| superpowers (`@synced` oder `@<marketplace>`, wie gefunden) | `false`, erst wenn die Abschaltbedingung erfüllt ist; vorher bleibt es, und der Plan sagt warum |
| engineering (erkannt am Plugin-Namen `engineering`, nie ein Plugin `cc-*`) | `false`, Annahme |

**Gesetzte Werte dreht das Profil nie um.** Steht ein Plugin schon in `enabledPlugins`,
führt der Plan es als Konflikt. Erst die Antwort `plugins_off` (Liste von Plugin-IDs, an
`inspect_config.py --answers`) macht daraus einen Patch.

Gemessen am 2026-10-14 (CLI 2.1.296, Wegwerf-Config-Verzeichnis): `claude plugin install
cc-dev@cc-skills` schreibt `"enabledPlugins": {"cc-dev@cc-skills": true}` selbst. Jedes
per CLI installierte Plugin hat also einen gesetzten Wert — superpowers wird deshalb in
der Regel ein Konflikt sein, und der Nutzer entscheidet einmal ausdrücklich.

## Aktive Plugins

Je Plugin-ID gilt, in dieser Reihenfolge:

1. `enabledPlugins[<id>]` der User-Settings, wenn es ein Wahrheitswert ist (`explicit`).
2. `defaultEnabled` des Marketplace-Eintrags.
3. sonst an — installiert heißt geladen.

Projekt-Settings bewertet `route_check.py` nicht; ein Projekt kann `cc-ui` einschalten,
ohne dass der User-Scope davon weiß.

## Layout auf der Platte

```
<config-dir>/plugins/
├── installed_plugins.json      {"version": 2, "plugins": {"<name>@<marketplace>": [{"scope", "installPath", "version", …}]}}
├── known_marketplaces.json     {"<marketplace>": {"source", "installLocation", …}}
├── cache/<marketplace>/<plugin>/<version>/    bei einem lokalen Marketplace mit source "./" die ganze Repo-Kopie
└── synced/<ordner>/.claude-plugin/plugin.json  Plugin-ID <name>@synced
```

- `installPath` zeigt auf den Cache-Ordner. Zeigt er ins Leere (kopiertes
  Config-Verzeichnis, anderer Rechner), sucht das Skript unter
  `$CLAUDE_CODE_PLUGIN_CACHE_DIR`, sonst `<config-dir>/plugins/cache`, nach
  `<marketplace>/<plugin>/<version>` und nimmt die jüngste Version.
- Die Skills eines Plugins stehen in der `skills`-Liste seines Marketplace-Eintrags
  (`.claude-plugin/marketplace.json` im Installationsordner), sonst unter `skills/*/`.
- Hooks: `hooks/hooks.json` im Plugin-Ordner und das Feld `hooks` des Eintrags (Pfad,
  Liste von Pfaden oder inline). Gemeldet wird je SessionStart-Gruppe
  `<plugin> · SessionStart-Hook · <matcher>`, ohne Matcher `*`.
- Ohne `plugins/` oder ohne ein einziges installiertes Plugin heißt der Bericht
  „ungeprüft — keine Plugins unter <config-dir>/plugins".

## Abschaltbedingung (Spec 20)

| Teil | Bedingung | Quelle |
| --- | --- | --- |
| (a) | keine Zeile mit Status „Lücke" | `references/superpowers-gaps.json` |
| (b) | keine Description eines aktiven Plugins außer superpowers enthält `superpowers:` | `SKILL.md` der Skills aus dem installierten Bestand |
| (c) | jede Datei der Zeilen mit Status „Regel" liegt unter `<config-dir>/rules/` | `rules` je Zeile; im Plan zählt eine Regel, die derselbe Plan anlegt |

(b) prüft den installierten Stand, nicht die Quelle: Ein Plugin-Cache von gestern kann
noch Verweise tragen, die das Repo heute nicht mehr hat. Dann hilft
`claude plugin update`, nicht ein neuer Plan.

## Kollisionen

Eine Skill gleichen Namens in zwei aktiven Plugins oder in einem Plugin und unter
`<config-dir>/skills/`. Plugin-Skills tragen zwar ihren Namensraum (`cc-dev:feature-spec`),
aber beim Routing entscheidet die Description — zwei gleich benannte Skills konkurrieren.
