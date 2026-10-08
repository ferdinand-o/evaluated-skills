# Spec 21: setup-user — ein Config-Verzeichnis, das Claude über Kontext und Limits informiert, statt nur den Nutzer

Skill-Spezifikation · Zyklus 21 · Entscheidung: Konfiguration als geprüfte Dateien mit pfadneutralem Plan, Merge und Installationstest in einer Sandbox statt als Doktrin; die Statusline des Nutzers wird zur Brücke, weil nur sie Kontext- und Limitwerte fertig berechnet bekommt · Abgeglichen mit Spec 00 · Überarbeitet nach unabhängigem Review

## Problem

Der Nutzer will den User-Scope von Claude Code einmal sauber einrichten: allgemeine
CLAUDE.md, Statusline, Limit- und Kontextbewusstsein, Grundregeln, Skillrouting
(Gespräch vom 2026-10-07). Drei Messungen aus der Claude-Code-Doku bestimmen den
Zuschnitt:

- **Nur die Statusline bekommt Kontext und Limits fertig geliefert.** Ihr stdin trägt
  `context_window.used_percentage` und `rate_limits.five_hour` / `seven_day` mit
  `used_percentage` und `resets_at` (statusline, „Available data"). Die gemeinsamen
  Eingabefelder aller Hooks enthalten nichts davon (hooks: `session_id`,
  `transcript_path`, `cwd`, `permission_mode` u. a.). Claude selbst sieht die
  Statusline nicht; eine Regel „bei 70 % Kontext Handoff" kann Claude nicht befolgen.
- **Auto Memory ist für Gelerntes da, nicht für Vorgaben.** Standardmäßig hat jedes
  Projekt ein eigenes Verzeichnis, und Claude „skips anything your CLAUDE.md files
  already say" (memory, „Auto memory"). Persönliche Regeln für alle Projekte gehören
  nach `~/.claude/rules/` (memory, „User-level rules").
- **Cloud-Sessions lesen den User-Scope nicht.** `~/.claude/settings.json` und
  `.claude/settings.local.json` sind dort „not read" (settings, „Settings in cloud
  sessions"). Was überall gelten muss, gehört ins Repo (Spec 22).

Der Nutzer hat eine eigene Statusline in Python, die die Limits in
`~/.claude/usage-cache.json` zwischenspeichert. Am 2026-10-07 mit Beispiel-Eingaben
gemessen und in zwei Reviews nachgemessen: Ein Session-Start ohne `rate_limits`
überschreibt beide Werte mit `None`; der Pfad ignoriert `CLAUDE_CONFIG_DIR`, sodass
seine zwei Accounts auf dem Windows-PC denselben Cache teilen; `"context_window": null`
und leeres stdin enden mit Exit 1; unter Last lasen 14 bis 16 von 200 Lesevorgängen
kaputtes JSON. Die korrigierte Fassung zeigt dieselbe Anzeige (`cmp`), schreibt atomar
(200 von 200 gültig) und ist die Vorlage für das Asset. Laut Doku bricht Claude Code ein
laufendes Statusline-Skript ab, wenn ein neues Update kommt (statusline, „How status
lines work"). Mit CLI 2.1.292 gemessen (Review): Die Statusline läuft bei `claude -p`
nicht; Hooks laufen dort und erben `CLAUDE_CONFIG_DIR`.

## Constraints

Claude-Code-spezifisch ohne Portabilitätsanspruch. Vier Abweichungen von Spec 00, alle
hier begründet:

1. Frontmatter `disable-model-invocation: true` — laut Doku ist die Description dann
   „not in context". `lint_skill.py` erlaubt den Schlüssel nur für Skills auf der Liste
   `CLAUDE_CODE_ONLY = {"setup-user", "setup-repo"}`, nicht global.
2. Ablage unter `<config-dir>/setup-user/` statt `~/.skills/` (Spec 00 §1), weil jeder
   Account sein eigenes Config-Verzeichnis hat.
3. Die Skill schreibt in `settings.json` — Spec 00 sagt „installieren aber nie selbst
   in fremde `settings.json`". Hier ist es die eigene Datei des Nutzers, geschrieben nur
   nach gezeigtem und bestätigtem Plan.
4. Laufzeitdateien in JSON (`thresholds.json`, `state/*.json`, Limit-Cache) tragen
   `_meta` nach `docs/artifact-header.md`; der Limit-Cache behält zusätzlich seine
   bisherigen Schlüssel, weil das agent-dashboard sie liest.

Alle Skripte Tier 1, plattformübergreifend (Windows 11 und Linux-Devbox), kein jq, kein
Bash. Gate-Grade: dass der Plan gezeigt und bestätigt wurde, verlangt die SKILL.md (G1);
dass Plan und Bestand seit der Planung unverändert sind, meldet `apply_config.py` per
Hash (G2); der Kontext-Hinweis ist ein Hook, der meldet und nichts anhält. SKILL.md
≤ 150 Zeilen. Skripte referenziert über `${CLAUDE_SKILL_DIR}`. Nachbarskripte werden
nicht importiert. Plugin: `cc-dev` (Spec 20); als Plugin-Skill heißt der Aufruf
`/cc-dev:setup-user`, als Projekt-Installation in den Evals `/setup-user`.

## Approach

**Eiserne Regel:** *Nichts außerhalb von `<config-dir>/setup-user/` wird geschrieben,
bevor der Plan gezeigt und bestätigt ist — und keine Einrichtung heißt fertig, bevor
die installierten Befehle in einer Sandbox mit Beispiel-Eingabe gelaufen sind und das
erwartete Ergebnis geliefert haben.*

### Skill-Struktur

```
skills/setup-user/
├── SKILL.md                         Modi plan/apply/check, Interview, Eiserne Regel, Contract, Abgrenzung
├── references/settings-merge.md     welche Schlüssel gemischt, übernommen oder nie angefasst werden
├── references/thresholds.md         Schwellen, Wortlaut der Hinweise, Frische- und Wiederscharf-Regeln
├── references/routing.md            Plugin-Profile, Bestimmung aktiver Plugins, Plugin-Layout auf der Platte
├── references/superpowers-gaps.json Lückentabelle aus Spec 20 als Daten; Spec 23 und 24 ziehen sie nach
├── assets/CLAUDE.md                 Gerüst ≤ 40 Zeilen, Kopfzeile in Zeile 1
├── assets/rules/communication.md    Sprache, Ton, Antwortlänge
├── assets/rules/verification.md     keine Erfolgsmeldung ohne Beleg; Review-Befunde vor dem Umsetzen nachmessen (Spec 20)
├── assets/rules/context.md          was [setup-user]-Hinweise bedeuten: handoff, /clear, Subagents für breite Recherche
├── assets/rules/git.md              kein Commit und kein Push ohne Auftrag
├── assets/runtime/statusline.py     Tier 1 — Statusline des Nutzers (korrigiert 2026-10-07), Kennzeile, Kontextzustand je Session
├── assets/runtime/context_hint.py   Tier 1 — UserPromptSubmit-Hook: additionalContext beim Überschreiten einer Schwelle
├── assets/runtime/known-statusline-hashes.json   Hashes bekannter Fassungen der Nutzer-Statusline, LF-normalisiert
├── assets/hooks/context-hint.json   Hook-Fragment für settings.json; meldet, hält nichts an
├── scripts/inspect_config.py        Tier 1 — Bestandsaufnahme; Plan als Diff mit Platzhalter <config-dir> und Hash
├── scripts/apply_config.py          Tier 1 — wendet nur einen Plan mit passendem Hash an; Backup, Merge, atomar
├── scripts/route_check.py           Tier 1 — aktive Plugins, Kollisionen, superpowers:-Verweise, SessionStart-Hooks, Abschaltbedingung
└── scripts/verify_install.py        Tier 1 — führt die Befehle aus settings.json mit CLAUDE_CONFIG_DIR auf ein Temp-Verzeichnis aus

skills/skill-forge/scripts/lint_skill.py   CLAUDE_CODE_ONLY; disable-model-invocation nur dort erlaubt
skills/handoff/SKILL.md                    Abgrenzung: [setup-user]-Hinweise raten zu handoff (Rückverweis, nennt setup-user)
scripts/sync_plugins.py, plugins/cc-dev/skills/setup-user/   Zuordnung zu cc-dev (Spec 20)
specs/Spec 00 – skill-foundation.md        §5: Satz zur Ausnahme für Claude-Code-spezifische Skills; Matrixzeile setup-user
README.md                                  Matrixzeile setup-user
docs/known-limits.md                       Abschnitt setup-user
docs/superpowers/reports/setup-user-report.md   Report mit „Was nicht gemessen wurde"
evals/setup-user/evals.json                fünf Evals, siehe unten
evals/fixtures/su-aligned/, su-fresh/, su-planned/, su-own-statusline/, su-plugins/   je mit fixture.json
tests/test_setup_user_*.py                 siehe Tests (Repo)
```

Installiert im Config-Verzeichnis (`$CLAUDE_CONFIG_DIR`, sonst `~/.claude`):

```
<config-dir>/
├── CLAUDE.md, rules/*.md            nur angelegt, wenn nicht vorhanden; Vorhandenes bekommt nur bestätigte Ergänzungen
├── settings.json                    gemischt: statusLine, hooks.UserPromptSubmit, enabledPlugins, optional permissions.deny
├── usage-cache.json                 je Account; für den Standard-Account derselbe Pfad wie bisher
└── setup-user/
    ├── runtime/statusline.py, context_hint.py
    ├── state/context-<session_id>.json, hints-<session_id>.json
    ├── thresholds.json
    ├── backups/<zeitstempel>/…
    ├── plan.md                      Plan mit Hash, Kopfzeile in Zeile 1
    └── check.md                     Prüfbericht, Kopfzeile in Zeile 1
```

### Ablauf

1. **Ziel nennen.** `--config-dir` ausdrücklich, sonst `$CLAUDE_CONFIG_DIR`, sonst
   `~/.claude`; die erste Ausgabezeile nennt den aufgelösten Pfad. Mehrere
   Config-Verzeichnisse bekommen je einen Lauf.
2. **plan (Default).** `inspect_config.py` schreibt `plan.md`: Bestand, geplante
   Änderungen als Diff, Konflikte, Annahmen, Hash. Pfade im Plan stehen relativ zum
   Platzhalter `<config-dir>`; der Hash läuft über den Plantext und die Inhalte der
   betroffenen Dateien, ohne absolute Pfade, ohne Zeitstempel.
3. **Interview, höchstens drei Fragen** und nur, was nicht im Bestand steht: Sprache und
   Ton, Rechner und Shell, Git-Gewohnheiten. Ohne Antwort — etwa bei `claude -p` — nimmt
   der Plan die Werte aus den Assets und führt sie als Annahme.
4. **apply** in einem späteren Aufruf nach Bestätigung, nur mit explizitem
   `--config-dir`: `apply_config.py --plan <config-dir>/setup-user/plan.md` prüft den
   Hash, setzt `<config-dir>` als absoluten Pfad mit Schrägstrichen ein (auch unter
   Windows, weil Git Bash Backslashes entfernt; statusline, „Windows configuration"),
   legt Backups an, mischt, kopiert `runtime/`, schreibt `thresholds.json`. Danach
   `verify_install.py`. Übergabe „angewendet und geprüft" oder „angewendet, ungeprüft —
   <Grund>".
5. **check.** Bestand gegen Assets, `verify_install.py`, `route_check.py`; schreibt nur
   `check.md` mit Abweichungen oder „keine Abweichung". Ein ausstehender `plan.md` bleibt
   unberührt.

**Sandbox für die Prüfung.** `verify_install.py` legt ein Temp-Verzeichnis an, spielt
dort einen Beispielzustand oberhalb einer Schwelle ein und führt die Befehlsstrings aus
`settings.json` (Statusline und Hook) mit `CLAUDE_CONFIG_DIR` auf dieses Verzeichnis
aus. Erwartet werden eine Statusline-Ausgabe, eine Cache-Datei im Temp-Verzeichnis und
ein Hinweis des Hooks. Ein Hook, der schweigt, wo er melden müsste, ist ein Befund;
ebenso Exit 2 oder eine leere Statusline. Weil die Laufzeitskripte nur nach
`$CLAUDE_CONFIG_DIR` schreiben, bleiben echter Cache und Zustand unberührt.

**Vergleich in `check`.** Laufzeitdateien vergleicht `check` per Inhalts-Hash mit den
Assets. Kommandos in `settings.json` gelten als ausgerichtet, wenn ihr Skriptpfad —
absolut, mit `~` oder relativ zum Arbeitsverzeichnis — auf eine Datei mit passendem Hash
zeigt. Bei CLAUDE.md und `rules/` prüft `check` nur Kopfzeile und Budget, nicht den
Inhalt, weil das Interview sie anpasst.

**Statusline.** Die Statusline des Nutzers wird erkannt an der Kennzeile des Assets
oder an einem Hash aus `known-statusline-hashes.json` (Zeilenenden normalisiert). Dann
zeigt `statusLine` nach `apply` auf `runtime/statusline.py`; die alte Datei bleibt
liegen, die Anzeige bleibt gleich. Ist keine Statusline eingetragen, setzt `apply` das
Asset ein. Eine fremde Statusline bleibt eingetragen, und der Plan sagt
„Kontext-Hinweise nicht verfügbar — fremde Statusline schreibt keinen Kontextzustand";
der Hook wird trotzdem eingetragen: Ohne Zustand und Cache schweigt er, und er wirkt,
sobald der Nutzer auf die Asset-Statusline wechselt.
`verify_install.py` erwartet in diesem Fall keine Cache-Datei und führt relative
Skriptpfade vom Arbeitsverzeichnis aus. Das Asset schreibt zum Limit-Cache je Fenster `observed_at_epoch` dazu
und je Session `state/context-<session_id>.json`; einen fehlenden oder `null`-Wert
schreibt es als `null`, nicht als alten Wert. `session_id` wird vor der Verwendung im
Dateinamen auf `[A-Za-z0-9_-]` geprüft. Zustandsdateien älter als 24 Stunden räumt es
beim Schreiben ab.

**Kontext-Hinweis.** `context_hint.py` liest beim Absenden eines Prompts den Zustand der
eigenen `session_id` und den Limit-Cache. Kontext gilt, solange die `session_id` passt —
er ändert sich nur mit neuen Nachrichten, und danach läuft die Statusline. Ein
Limitfenster gilt, wenn sein `observed_at_epoch` höchstens zehn Minuten alt ist und
`resets_at_epoch` in der Zukunft liegt. Ein Hinweis kommt beim Überschreiten einer
Schwelle; fällt der Wert wieder darunter (nach `/compact`, nach einem Reset), wird die
Schwelle wieder scharf. Fehlt etwas oder ist es `null`, schweigt der Hook. Der Hinweis
ist als Feststellung formuliert, nicht als Anweisung — die Doku warnt, imperative Texte
könnten Claudes Schutz gegen Prompt-Injection auslösen (hooks, „Add context for
Claude") —, etwa „[setup-user] Kontext 63 % (Schwelle 60 %). Laut Nutzerregel
context.md ist das der Punkt für Handoff und /clear." Dass `UserPromptSubmit` auch bei
geplanten Aufgaben und Rückmeldungen von Subagents feuert, ist gewollt.

**Routing.** `route_check.py` bestimmt die im User-Scope aktiven Plugins aus
`enabledPlugins` der User-Settings, `defaultEnabled` und der Liste installierter
Plugins; Projekt-Settings bewertet es nicht. Es liest beide Ablagen
(`plugins/cache/<marketplace>/<plugin>/<version>/` mit `installed_plugins.json`, und
`plugins/synced/`; plugins/loading, „Find plugins on disk") und meldet
Namenskollisionen, Plugins mit `SessionStart`-Hook, Descriptions mit `superpowers:`
und den Stand der Abschaltbedingung aus Spec 20. Das Profil im Plan:

| Plugin | User-Scope |
| --- | --- |
| `cc-dev`, `cc-knowledge` | `true` |
| `cc-ui`, `cc-meta` | nicht gesetzt; an per Projekt (Spec 22) |
| superpowers (`@synced` oder `@<marketplace>`, wie gefunden) | `false`, erst wenn die Abschaltbedingung erfüllt ist; vorher bleibt es und der Plan sagt warum |
| engineering (Plugin mit `testing-strategy`, `debug`, `code-review`) | `false`, Annahme |

### Contract

- **Plan vor Schreiben.** `plan` und `check` schreiben nur `plan.md` bzw. `check.md` und
  Dateien im Temp-Verzeichnis der Prüfung. `apply` braucht explizites `--config-dir`;
  dass Plan und Bestand unverändert sind, meldet `apply_config.py` per Hash und bricht
  bei Abweichung ab (G2). Dass der Plan gezeigt wurde, bleibt G1.
- **Mischen, nie überschreiben.** Jede berührte Datei hat vorher ein Backup; Listen
  werden vereinigt; fremde Schlüssel bleiben; JSON wird vor dem Ersetzen geparst und
  atomar geschrieben; vorhandene CLAUDE.md und Regeldateien bekommen nur bestätigte
  Ergänzungen.
- **Geprüft heißt gelaufen.** `verify_install.py` führt die eingetragenen Befehle in der
  Sandbox aus und erwartet Ausgabe, Cache und Hinweis; ohne Lauf heißt die Übergabe
  „ungeprüft".
- **Hinweise sind selten und belegt.** Einer je Überschreiten einer Schwelle, nur mit
  gültigen Werten; sonst Schweigen. Der Hook hält keinen Prompt an.
- **Ein Account, ein Verzeichnis.** Cache, Zustand, Backups und Berichte liegen im
  jeweiligen Config-Verzeichnis.
- **Anti-Zeremonie-Fall:** `check` auf ein Verzeichnis, das dem Plan schon entspricht,
  ändert keine Datei außer `check.md` und meldet „keine Abweichung".

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| Statusline nach Freitext-Wunsch neu erzeugen | eingebautes `/statusline` | setup-user übernimmt eine vorhandene Statusline, erzeugt keine nach Wunsch |
| Sitzung sichern, wenn der Kontext voll wird | **handoff** | setup-user installiert nur den Hinweis, der dazu rät |
| persönliches Stimmprofil für eigene Texte | anthropic-skills:setup-writing-style | setup-user schreibt keine Stilregeln außer Sprache und Ton |
| Skill bauen oder ändern | skill-forge | setup-user ändert keine Skill, nur Plugin-Schalter |
| ein Repo einrichten | setup-repo (22) | setup-user — was in Cloud und CI gelten muss, gehört ins Repo |

In der SKILL.md steht nur **handoff** fett, weil nur dort ein Rückverweis entsteht;
`skill-forge` bleibt unfett, sonst meldet `rule_neighbors` ihn als `finding`.

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_statusline_keeps_cache_on_session_start` | `tests/test_setup_user_statusline.py` | Eingabe ohne `rate_limits` lässt beide Fenster stehen |
| `test_statusline_respects_config_dir` | dito | zwei `CLAUDE_CONFIG_DIR` → zwei Caches |
| `test_statusline_partial_window_keeps_observed_at` | dito | nur `five_hour` neu → `seven_day` behält seinen `observed_at_epoch` |
| `test_statusline_survives_null_and_empty_input` | dito | Exit 0, eine Zeile Ausgabe; `null`-Kontext wird als `null` geschrieben |
| `test_statusline_display_unchanged` | dito | Ausgabe gleich der Fassung vom 2026-10-07 bei voller Eingabe |
| `test_statusline_state_prunes_and_sanitizes` | dito | Zustandsdatei entsteht; älter als 24 h verschwindet; `session_id` mit `../` wird abgewiesen |
| `test_hint_once_and_rearms` | `tests/test_setup_user_hint.py` | zweiter Prompt über derselben Schwelle schweigt; nach Absinken und erneutem Überschreiten kommt wieder einer |
| `test_hint_silent_on_foreign_session_null_or_stale_limits` | dito | fremde `session_id`, `null`, Limitfenster älter als zehn Minuten oder abgelaufen |
| `test_hint_limits_without_statusline_state` | dito | kein Kontextzustand, gültiges Limitfenster → nur Limit-Hinweis |
| `test_hint_output_shape` | dito | `hookSpecificOutput.additionalContext`, Text beginnt mit `[setup-user]` |
| `test_plan_is_path_neutral` | `tests/test_setup_user_apply.py` | Plan für dasselbe Verzeichnis an zwei Orten → gleicher Hash |
| `test_apply_is_idempotent` | dito | zweiter `apply` mit neuem Plan erzeugt leeren Diff |
| `test_apply_refuses_changed_plan_or_state` | dito | geänderter Plan oder Bestand → Abbruch, keine Datei berührt |
| `test_apply_requires_explicit_config_dir` | dito | ohne `--config-dir` → Abbruch |
| `test_apply_keeps_foreign_keys_and_unions_lists` | dito | fremder Schlüssel bleibt, Listen vereinigt |
| `test_verify_runs_in_sandbox_only` | `tests/test_setup_user_verify.py` | nach dem Lauf keine neue oder geänderte Datei außerhalb des Temp-Verzeichnisses |
| `test_verify_flags_silent_hook_exit_2_and_empty_statusline` | dito | alle drei Fälle sind Befunde |
| `test_route_check_layouts_and_condition` | `tests/test_setup_user_route.py` | Fake-Plugins in beiden Ablagen; SessionStart-Hook, `superpowers:`-Verweis und Abschaltbedingung gemeldet |
| `test_fixture_plans_are_current` | `tests/test_setup_user_fixtures.py` | `plan.md` in `su-planned` und `su-own-statusline` gleicht einem neu erzeugten Plan; Laufzeitdateien in `su-aligned` gleichen den Assets |
| `test_gaps_json_matches_spec_20` | dito | `references/superpowers-gaps.json` und die Lückentabelle in Spec 20 nennen dieselben Zeilen und Status |

### Evals

Jeder Prompt nennt `--config-dir ./cfg`, weil der Eval-Agent das echte Home des
Aufrufers sieht (known-limits, Isolation). Die Skill ist nur über ihren Slash-Befehl
aufrufbar; mit CLI 2.1.292 gemessen (Review): Eine Skill mit
`disable-model-invocation: true` steht im `skills`-Feld des `init`-Ereignisses, und der
Slash-Aufruf mit `-p` läuft. Ohne installierte Skill antwortet der Agent auf
`/setup-user`, der Befehl sei nicht installiert, und ändert nichts — jeder Eval braucht
deshalb mindestens eine Assertion, die nur ein Lauf der Skill erfüllt.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-check-on-aligned-config-changes-nothing` | contract | `su-aligned` | `file_exists` und `artifact_header` auf `cfg/setup-user/check.md`; `file_matches` dort `keine Abweichung`; `file_unchanged` auf `cfg/settings.json`, `cfg/CLAUDE.md`, die vier Regeldateien und beide Laufzeitdateien — in `evals.json` je Datei eine Assertion, weil `file_unchanged` keinen Glob nimmt | `check.md` entsteht nur durch die Skill; die Fixture nutzt relative Skriptpfade, die `check` auflöst |
| 2 | `plan-is-default-and-writes-only-plan` | contract | `su-fresh` | `file_exists` und `artifact_header` auf `cfg/setup-user/plan.md`; `file_unchanged` `cfg/settings.json`; `file_absent` `cfg/CLAUDE.md` | ohne Skill entsteht kein `plan.md`; dass nur geplant wird, zeigen die beiden anderen Assertions |
| 3 | `apply-merges-existing-plan-and-backs-up` | contract | `su-planned` | `file_exists` `cfg/setup-user/backups/*/settings.json`; `file_matches` `cfg/settings.json` auf `"statusLine"`, auf `context_hint` und auf `"spinnerTipsEnabled": false`; `artifact_header` und `file_max_lines` 40 auf `cfg/CLAUDE.md` | Backup, Hook-Fragment und CLAUDE.md mit Kopfzeile entstehen nur durch `apply`; der fremde Schlüssel prüft das Mischen |
| 4 | `foreign-statusline-is-kept-while-hook-is-merged` | contract | `su-own-statusline` | `file_unchanged` `cfg/my-status.py`; `file_matches` `cfg/settings.json` auf `my-status` und auf `context_hint`; `file_exists` `cfg/setup-user/backups/*/settings.json` | Backup und Hook-Fragment nur durch `apply`; ohne Skill bliebe die Fixture unverändert und das Hook-Fragment fehlte |
| 5 | `superpowers-sessionstart-is-reported` | contract | `su-plugins` | `file_matches` `cfg/setup-user/check.md` auf `SessionStart` und auf `superpowers` | nur `route_check.py` liest Plugin-Hooks und schreibt `check.md` |

Prompts: 1 und 5 „/setup-user check --config-dir ./cfg", 2 „/setup-user --config-dir
./cfg", 3 und 4 „/setup-user apply --config-dir ./cfg — den Plan in
cfg/setup-user/plan.md habe ich gelesen und bestätige ihn". `su-planned` und
`su-own-statusline` bringen einen `plan.md` mit, den `inspect_config.py` erzeugt hat;
`test_fixture_plans_are_current` hält ihn aktuell. `su-fresh` und `su-planned` tragen
eine `cfg/settings.json` mit `"spinnerTipsEnabled": false`.

## Alternatives considered

**Kontext aus dem Transcript selbst berechnen.** Hooks bekommen `transcript_path`, und
dort stehen je Nachricht die Token-Zahlen, aus denen die Doku `used_percentage`
berechnet (im Review per grep gesehen). Das ginge auch bei `-p` und mit fremder
Statusline. Verworfen für den ersten Bau: Das Format ist nicht dokumentiert, und die
Fenstergröße steht nicht darin. Gewinnt, wenn kopflose Läufe Kontext-Hinweise brauchen.

**Hook als Plugin-Hook mit `${CLAUDE_PLUGIN_ROOT}`.** Kein Kopieren. Verworfen: Plugins
können keine `statusLine` mitbringen, also muss die Statusline ohnehin an einen stabilen
Ort; der Hook liest deren Zustand und gehört daneben. `${CLAUDE_PLUGIN_ROOT}` „changes
when the plugin updates" (plugins), und mit Spec 20 ist der Plugin-Root ein Quellordner
unter `plugins/`.

**`PreCompact`-Hook, der vor der Auto-Compaction den Stand sichert.** Laut hooks-Doku
kann er Compaction verhindern, aber keinen Kontext einspielen. Schreiben müsste er nach
`handoff.md`, die allein `handoff` gehört. Verworfen.

**Auto Memory mit Grundwissen vorbefüllen.** Mit `autoMemoryDirectory` oder
`CLAUDE_CODE_PROJECT_DIR_NAME` ließe sich ein gemeinsames Verzeichnis bauen (memory,
„Storage location"). Verworfen, weil Auto Memory Gelerntes aufnimmt und überspringt, was
CLAUDE.md sagt.

**Routing als Tabelle in der CLAUDE.md.** Gegen die SessionStart-Injektion von
superpowers wirkungslos (Spec 20). Gewinnt, sobald superpowers aus ist und nur
Restüberlappungen bleiben — dann als kurze Regel in `rules/`, nicht als Ersatz für die
Plugin-Schalter.

**`disable-model-invocation` global erlauben.** Einfacher im Lint, aber dann könnte jede
Skill der Sammlung ihre Description aus dem Kontext nehmen. Verworfen zugunsten der
Liste `CLAUDE_CODE_ONLY`.

**Statusline in Bash mit jq.** Auf dem Windows-PC fehlt jq meist, und die Statusline des
Nutzers ist bereits Python.

## Out of scope

Modell- und Effort-Voreinstellungen, MCP-Server, Output-Styles, ein
Benachrichtigungs-Hook, Synchronisation zwischen Rechnern, Änderungen am
agent-dashboard, Cloud-Sessions (Spec 22), das Installieren von Plugins (`/plugin`), eine
Erweiterung der Ausbruchsbeobachtung im Runner um `~/.claude/usage-cache.json` (heute
beobachtet er nur `~/.skills`; vorgemerkt für evalkit).

## Open questions

*Annahme:* Schwellen Kontext 60 % und 80 %; 5-Stunden-Limit 80 %; 7-Tage-Limit 85 %;
Limitfrische zehn Minuten; Aufräumen nach 24 Stunden — widersprich, falls nein.

*Annahme:* Budgets CLAUDE.md ≤ 40 Zeilen, je Regeldatei ≤ 20, zusammen ≤ 120 Zeilen
immer geladener User-Scope — widersprich, falls nein.

*Annahme:* Das engineering-Plugin geht im User-Scope aus, weil es mit testing-strategy,
debug-ledger und review-context überlappt — widersprich, falls nein.

*Annahme:* `permissions.deny` für `.env`-Dateien, `~/.ssh` und Zertifikatsschlüssel wird
im Plan angeboten, nicht gesetzt. Laut permissions-Doku (im Review zitiert) gilt ein
Read-Deny für die eingebauten Datei-Werkzeuge und erkannte Bash-Dateikommandos, nicht für
beliebige Unterprozesse wie ein Python-Skript; der Plan sagt das so.

*Annahme:* Das agent-dashboard liest den Limit-Cache (Angabe des Nutzers vom 2026-10-07;
früher fragte es `/usage` per headless-Aufruf ab). Der Cache des zweiten Accounts liegt
künftig unter `<cfgB>/usage-cache.json`. Ein Fenster bleibt nach seinem `resets_at` mit
altem Wert stehen; Leser prüfen `resets_at_epoch` selbst — widersprich, falls das
Dashboard dafür nicht angepasst werden soll.

**Wirkt `enabledPlugins` auf `superpowers@synced`?** Laut plugins/loading schreibt
`claude plugin disable <name>@synced` genau diesen Schlüssel in die User-Settings.
Offen ist nur, ob superpowers beim Nutzer `@synced` oder aus einem Marketplace kommt;
`route_check.py` entscheidet das am Bestand.

Ob `python` oder `py -3` im `statusLine`-Kommando unter Windows richtig ist, entscheidet
`inspect_config.py` am Bestand; gemessen ist es nicht. Die versionierten Fixture-Pläne
halten den Interpreter deshalb als Platzhalter `<python>`, nicht als festen Namen. Ob
`CLAUDE_CONFIG_DIR` auch die Plugin-Ablage verschiebt, ist nicht dokumentiert;
`route_check.py` sucht unter `<config-dir>/plugins/` und meldet „ungeprüft", wenn dort
nichts liegt. Ebenso ungemessen: ob `os.replace`
unter Windows scheitert, solange ein Leser die Datei offen hält.

Ungemessen bleibt, ob Hinweise das Verhalten tatsächlich ändern — ein Eval kann den
Kontextstand nicht herbeiführen. Gemessen werden nur Entstehen und Schweigen des
Hinweises (Tests).

## Next steps

Spec 20 zuerst bauen. Dann Plan mit `impl-plan` (16) und Bau nach `skill-forge` (17)
Schritt 3 bis 7. Erster echter Lauf auf dem Windows-PC je Config-Verzeichnis, danach auf
der Devbox.
