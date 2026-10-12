---
name: setup-repo
description: "Use when a repository is to be set up for Claude Code so that every session — local, cloud or CI — knows how to verify its work — \"richte das Repo ein\", \"setup-repo\", \"CLAUDE.md und Regeln aus dem Repo ableiten\", \"prüf die Repo-Einrichtung\". Invoked only as /setup-repo (plan, apply, check). Not for the personal config directory (use setup-user) and not for deciding which tests are missing (use testing-strategy)."
disable-model-invocation: true
---

# setup-repo — ein Repo, in dem Claude weiß, wann es fertig ist

**Eiserne Regel:** *Kein Verifikationsbefehl und keine aus dem Repo geerntete Regel ohne
Beleg — was fehlt, steht als „ungeprüft" da, nie erfunden. Nichts außerhalb von
`.skills/cache/setup-repo/` wird geschrieben, bevor der Plan gezeigt und bestätigt ist.*
G1 — diese Datei verlangt das Zeigen; dass Plan und Bestand seit der Planung unverändert
sind und das Budget hält, meldet das Skript (G2).

Warum es die Skill gibt: Cloud-Sessions lesen nur das Repo, und Plugins laden dort nicht.
Was in jeder Session gelten muss — Verifikationsbefehl, knappe CLAUDE.md, Regeln mit
Quelle, Freigaben —, gehört deshalb committet ins Repo.

## Ablauf

1. **Ziel nennen.** Die Repo-Wurzel (`git rev-parse --show-toplevel`); die erste Zeile der
   Antwort nennt sie.
2. **plan (Default):**
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/detect_repo.py"
   python "${CLAUDE_SKILL_DIR}/scripts/harvest_rules.py"
   ```
   Lies `.skills/cache/setup-repo/candidates.json` und vergib je Kandidat eine Klasse nach
   `references/rules-harvest.md`: `ableitbar`, `werkzeug` (ein konfiguriertes Werkzeug prüft
   es schon — `checked_by` ist der Beleg), `regel` (mit `paths`, wo sie nur einen Teil
   betrifft). Dann:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/plan_repo.py" --classes '{"c1": "werkzeug", "c2": "regel"}'
   ```
   Optionen: `--with-verify-hook`, `--without-goal-hook`, `--deny-secrets`. Schreibt nur `plan.md`. Zeig dem
   Nutzer die Ansicht daraus: Verifikation mit Quelle, Kandidaten mit Klasse, Budget,
   Plugins, Hooks, Änderungen. Dann endet der Lauf; angewendet wird in einem späteren Aufruf.
3. **apply**, erst nach ausdrücklicher Bestätigung des gezeigten Plans:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/apply_repo.py"
   ```
   Bricht es mit „Hash passt nicht", „Bestand geändert" oder „uncommittete Änderungen" ab,
   wird neu geplant, nie der Block von Hand angepasst.
4. **check:**
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/apply_repo.py" --check
   ```
   Trockener apply gegen den Bestand, Budget, Hook-Probe; schreibt nur `check.md` mit
   „keine Abweichung" oder je Abweichung einer Zeile. Ohne Plan (frischer Clone, Cloud)
   stehen die klassenabhängigen Punkte als „ungeprüft — kein Plan".

Ohne Antwort auf Rückfragen (`claude -p`) bleiben Kandidaten „offen", und der Plan nennt
sie; `apply` wendet nur einen vorhandenen, bestätigten Plan an.

**Übergabe nach apply**, wörtlich eine von drei Formen aus `apply.md`:

- „angewendet und geprüft" — dazu: wirkt ab der nächsten Session, committen ist Sache des
  Nutzers.
- „angewendet, ungeprüft — <Grund>" — etwa „make fehlt" auf einer Maschine ohne Werkzeug.
- „abgebrochen — <Grund>" — nichts außerhalb des Caches wurde berührt.

## Verifikation

Der Befehl stammt aus vorhandenen Einträgen: ein Ziel `check`, `verify`, `ci` oder
`validate` in `Makefile`, `justfile`, `package.json` oder `pyproject.toml`, sonst `lint`,
`typecheck` und `test` verbunden mit `&&`. Bei Delphi wird der Build aus der `.dproj`
abgeleitet und als „abgeleitet" markiert — nicht freigegeben, kein Hook. Gibt es nichts,
heißt die Zeile „Verifikation: keine — ungeprüft", und der Bericht nennt testing-strategy.
Neue Runner-Ziele legt die Skill nicht an.

**Verifikations-Hook (opt-in, G3):** `verify_stop.py` hält das Turn-Ende an, solange der
Befehl aus der Zeile `Verifikation:` der CLAUDE.md rot ist, höchstens dreimal in Folge je
Session; danach lässt er es zu und meldet „rot nach drei Versuchen". Fehlt das Programm,
meldet er „ungeprüft — … fehlt". Jede Meldung geht über `systemMessage`.

**Plugins je Repo:** `enabledPlugins` kommt in `.claude/settings.local.json`, nie in die
committete Datei. `cc-ui` an, wenn ein Frontend erkannt ist; ein Plugin, dessen Skills als
Projekt-Kopie unter `.claude/skills/` liegen, aus. Ohne gefundene ID: „ungeprüft —
Plugin-ID nicht gefunden".

## Ziele

`apply` legt einen leeren Ledger `docs/goals.md` an (*Aktiv*, *Kandidaten*, *Erledigt*)
und die immer geladene Regel `.claude/rules/goals.md`; vorhandene bleiben unberührt. Die
Skill erfindet keine Ziele. Ein Ziel unter *Aktiv* trägt ein prüfbares „Fertig wenn" und
einen Bereich aus Pfad-Globs. Solange eines aktiv ist, ordnet die Regel entdeckte Arbeit
in vier Klassen: vom Nutzer verlangt, Teil des Ziels, trivial — erledigen; alles andere
wird Kandidat. Der Bereichs-Hook `goal_scope.py` (vorausgewählt, abwählbar mit
`--without-goal-hook`) meldet Dateien, die ein Turn außerhalb der Bereiche geändert hat:
dem Nutzer sofort, Claude beim nächsten Prompt. Er hält nie etwas an. Schema, Glob-Dialekt
und Klassen: `references/goals.md`.

Format, Mischregeln und Hash: `references/plan-format.md`.

## Contract

- **Belegt oder ungeprüft.** Jeder Verifikationsbefehl stammt aus einem Runner-Eintrag
  oder ist als abgeleitet markiert; jede geerntete Regel hat im Plan Quelle und Klasse.
- **Werkzeug vor Prosa.** Was ein konfigurierter Linter, Formatter oder Typprüfer prüft,
  wird keine Regelzeile — weder in Rules noch in der CLAUDE.md.
- **Budget.** Immer geladene Zeilen (CLAUDE.md samt Importen plus Rules ohne `paths`)
  ≤ 150; eine Überschreitung meldet `plan_repo.py` als Befund.
- **AGENTS.md bleibt lesbar.** Eine neue CLAUDE.md neben `AGENTS.md` importiert es.
- **Neue Ziele werden Kandidaten.** Die Regel verlangt die vier Klassen (G1); der
  Bereichs-Hook meldet, hält nichts an und löst keinen Folgeturn aus.
- **Sichtbar oder gar nicht.** Jede Meldung eines Stop-Hooks geht über `systemMessage`.
- **Mischen, nie überschreiben; kein Commit.** Fremde Settings-Schlüssel und Hooks
  bleiben, Listen werden vereinigt; unversionierte Zieldateien bekommen ein Backup.
- **Anti-Zeremonie:** `check` auf ein eingerichtetes Repo ändert nur `check.md` und meldet
  „keine Abweichung"; ein Repo ohne Tests bekommt keinen erfundenen Testbefehl; ohne
  aktives Ziel schweigen Regel und Hook.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „`npm test` gibt es bestimmt, das trage ich als Verifikation ein" | Ohne Eintrag kein Befehl. „Verifikation: keine — ungeprüft" ist das ehrliche Ergebnis, testing-strategy der nächste Schritt. |
| „`line-length = 100` ist eine wichtige Regel, die gehört in die CLAUDE.md" | ruff prüft sie schon. Klasse `werkzeug`, keine Zeile — jede Zeile kostet Budget in jeder Session. |
| „Der Nutzer will es eingerichtet haben — ich wende gleich an" | Bestätigt wird der gezeigte Plan, nicht der Wunsch. Ohne gezeigten `plan.md` kein `apply`. |
| „Der Hash passt nicht, ich korrigiere den Block schnell" | Dann bestätigt der Nutzer etwas, das er nie gesehen hat. Neu planen, neu zeigen. |
| „Ich committe gleich mit, das spart dem Nutzer einen Schritt" | Die Skill committet nie; der Nutzer prüft den Diff. |

## Abgrenzung

- **testing-strategy** — welche Tests fehlen und wie man sie schneidet; setup-repo
  übernimmt nur vorhandene Befehle.
- **review-context** — baut das Kontextpaket für einen Diff; setup-repo richtet kein
  Review ein.
- **handoff** — sichert den Stand einer Sitzung in `handoff.md`; `docs/goals.md` ist der
  Zielstand über Sitzungen hinweg.
- `/code-review` — sucht Fehler im Code eines Diffs.
- setup-user — der persönliche User-Scope; was nur für mich gilt, gehört nicht ins
  committete Repo.
- `/init` — erzeugt eine CLAUDE.md ohne Budget, Belege und Plan; setup-repo liest eine
  vorhandene wie jede andere Datei.
