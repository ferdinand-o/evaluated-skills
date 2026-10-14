# Spec 21: setup-user — ein Config-Verzeichnis, das Claude über Kontext und Limits informiert, statt nur den Nutzer

Skill-Spezifikation · Zyklus 21 · Entscheidung: Konfiguration als geprüfte Dateien mit kanonischem, pfadneutralem Plan, Merge und Installationstest in einer Sandbox statt als Doktrin; die Statusline des Nutzers wird zur Brücke, weil nur sie Kontext- und Limitwerte fertig berechnet bekommt; Plugin-Routing ist ein zweiter Bauabschnitt nach Spec 23 · Abgeglichen mit Spec 00 · Überarbeitet nach unabhängigem Review (zweite Runde 2026-10-08: Hook blockiert nie, Sandbox führt nur Asset-Befehle aus, Plan als JSON-Block)

## Problem

Der Nutzer will den User-Scope von Claude Code einmal sauber einrichten: allgemeine
CLAUDE.md, Statusline, Limit- und Kontextbewusstsein, Grundregeln, Skillrouting
(Gespräch vom 2026-10-07). Drei Messungen aus der Claude-Code-Doku bestimmen den
Zuschnitt:

- **Nur die Statusline bekommt Kontext und Limits fertig geliefert.** Ihr stdin trägt
  `context_window.used_percentage` und `rate_limits.five_hour` / `seven_day` mit
  `used_percentage` und `resets_at` in Epoch-Sekunden (statusline, „Available data").
  `rate_limits` erscheint nur für Pro und Max nach der ersten API-Antwort, jedes Fenster
  kann einzeln fehlen, und `used_percentage` kann früh `null` sein. Die gemeinsamen
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
lines work"). Mit CLI 2.1.292 gemessen (erstes Review): Die Statusline läuft bei
`claude -p` nicht; Hooks laufen dort und erben `CLAUDE_CONFIG_DIR`.

Ein `UserPromptSubmit`-Hook, der mit Exit 2 endet, lässt laut hooks-Doku den Prompt nicht durch.
Python endet mit Exit 2, wenn die Skriptdatei fehlt, und `argparse` tut es bei einem
Aufruffehler (im zweiten Review gemessen). Ein fehlendes oder fehlerhaftes Hook-Skript
würde also jeden Prompt abweisen.

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

Alle Skripte Tier 1, plattformübergreifend (Windows 11 und Linux-Devbox), kein jq.
Gate-Grade: dass der Plan gezeigt und bestätigt wurde, verlangt die SKILL.md (G1); dass
Plan und Bestand seit der Planung unverändert sind, meldet `apply_config.py` per Hash
(G2); der Kontext-Hinweis ist ein Hook, der meldet und nichts anhält. Das sichern drei
Dinge: `context_hint.py` fängt jede Ausnahme ab, nutzt kein `argparse` und endet immer
mit 0; das eingetragene Kommando endet auf `|| true`; `apply` schreibt `settings.json`
erst, wenn `runtime/` kopiert und per Hash geprüft ist. Das Hook-Fragment liegt unter
`assets/settings/`, nicht unter `assets/hooks/`, weil dieser Ordner `gate-language` im
Lint pauschal auf `pass` setzt und der Hook kein G3 ist. SKILL.md ≤ 150 Zeilen. Skripte
referenziert über `${CLAUDE_SKILL_DIR}`. Nachbarskripte werden nicht importiert. Plugin:
`cc-dev` (Spec 20); als Plugin-Skill heißt der Aufruf `/cc-dev:setup-user`, als
Projekt-Installation in den Evals `/setup-user`.

Gebaut wird in zwei Abschnitten. **Abschnitt A:** Statusline, Kontext-Hinweis,
`plan`/`apply`/`check`, Sandbox-Prüfung, Regeln und CLAUDE.md, Evals 1 bis 4.
**Abschnitt B**, erst wenn Spec 23 gebaut ist: `route_check.py`,
`superpowers-gaps.json`, `references/routing.md`, das Plugin-Profil in `enabledPlugins`
und Eval 5. Vorher wäre die Abschaltbedingung ohnehin nicht erfüllt (Spec 20, zwei
Zeilen „Lücke"); Abschnitt A fasst `enabledPlugins` nicht an.

## Approach

**Eiserne Regel:** *Nichts außerhalb von `<config-dir>/setup-user/` wird geschrieben,
bevor der Plan gezeigt und bestätigt ist — und keine Einrichtung heißt fertig, bevor
die installierten Befehle in einer Sandbox mit Beispiel-Eingabe gelaufen sind und das
erwartete Ergebnis geliefert haben.*

### Skill-Struktur

```
skills/setup-user/
├── SKILL.md                         Modi plan/apply/check, Interview, Eiserne Regel, Contract, Abgrenzung
├── references/settings-merge.md     welche Schlüssel gemischt, übernommen oder nie angefasst werden; Identität eigener Einträge; JSON-Format
├── references/plan-format.md        kanonischer JSON-Block im Plan: Felder, Normalisierung, Hash
├── references/thresholds.md         Schwellen, Wortlaut der Hinweise, Merker und Wiederscharf-Regeln
├── references/routing.md            (Abschnitt B) Plugin-Profile, Bestimmung aktiver Plugins, Plugin-Layout auf der Platte
├── references/superpowers-gaps.json (Abschnitt B) Lückentabelle aus Spec 20 als Daten, Quelle für Spec 23 und 24
├── assets/CLAUDE.md.tmpl            Gerüst ≤ 40 Zeilen, Kopfzeile in Zeile 1; Endung .tmpl, damit Claude Code die Datei beim Arbeiten im Ordner nicht als Anweisung lädt
├── assets/rules/communication.md    Sprache, Ton, Antwortlänge; Kopfzeile in Zeile 1
├── assets/rules/verification.md     keine Erfolgsmeldung ohne Beleg; Review-Befunde vor dem Umsetzen nachmessen (Spec 20); Kopfzeile
├── assets/rules/context.md          was [setup-user]-Hinweise bedeuten: handoff, /clear, Subagents für breite Recherche; Kopfzeile
├── assets/rules/git.md              kein Commit und kein Push ohne Auftrag; Kopfzeile
├── assets/runtime/statusline.py     Tier 1 — Statusline des Nutzers (korrigiert 2026-10-07), Kennzeile, Kontextzustand je Session
├── assets/runtime/context_hint.py   Tier 1 — UserPromptSubmit-Hook: additionalContext beim Überschreiten einer Schwelle; endet immer mit 0
├── assets/runtime/known-statusline-hashes.json   Hashes bekannter Fassungen der Nutzer-Statusline, LF-normalisiert
├── assets/settings/context-hint.json   Hook-Fragment für settings.json; meldet, hält nichts an
├── scripts/inspect_config.py        Tier 1 — Bestandsaufnahme; plan.md mit Ansicht und kanonischem JSON-Block samt Hash
├── scripts/apply_config.py          Tier 1 — wendet nur einen Plan mit passendem Hash an; Backup, runtime/ zuerst, settings.json zuletzt, atomar
├── scripts/route_check.py           (Abschnitt B) Tier 1 — aktive Plugins, Kollisionen, superpowers:-Verweise, SessionStart-Hooks, Abschaltbedingung
└── scripts/verify_install.py        Tier 1 — führt die Asset-Befehle aus settings.json in einer Sandbox aus; fremde Befehle nicht

skills/skill-forge/scripts/lint_skill.py   CLAUDE_CODE_ONLY; disable-model-invocation nur dort erlaubt
tests/test_skill_forge_lint.py             Fälle für CLAUDE_CODE_ONLY
skills/handoff/SKILL.md                    Abgrenzung: [setup-user]-Hinweise raten zu handoff (Rückverweis, nennt setup-user); Projekt-Kopie über sync_skills.py
.claude-plugin/marketplace.json            setup-user in der skills-Liste von cc-dev (Spec 20)
specs/Spec 00 – skill-foundation.md        §5: Satz zur Ausnahme für Claude-Code-spezifische Skills; Matrixzeile setup-user
README.md                                  Matrixzeile setup-user
docs/known-limits.md                       Abschnitt setup-user
docs/superpowers/reports/setup-user-report.md   Report mit „Was nicht gemessen wurde"
evals/setup-user/evals.json                vier Evals in Abschnitt A, Eval 5 in Abschnitt B
evals/fixtures/su-aligned/, su-fresh/, su-planned/, su-own-statusline/, su-plugins/ (B)   je mit fixture.json
tests/test_setup_user_*.py                 siehe Tests (Repo)
```

Installiert im Config-Verzeichnis (`$CLAUDE_CONFIG_DIR`, sonst `~/.claude`):

```
<config-dir>/
├── CLAUDE.md, rules/*.md            nur angelegt, wenn nicht vorhanden; Vorhandenes bekommt nur bestätigte Ergänzungen
├── settings.json                    gemischt: statusLine.command, hooks.UserPromptSubmit, optional permissions.deny; in Abschnitt B enabledPlugins
├── usage-cache.json                 je Account; für den Standard-Account derselbe Pfad wie bisher
└── setup-user/
    ├── runtime/statusline.py, context_hint.py
    ├── state/context-<session_id>.json, hints-<session_id>.json, limit-hints.json
    ├── thresholds.json
    ├── backups/<JJJJMMTT-hhmmss>/…
    ├── plan.md                      Kopfzeile in Zeile 1, Ansicht, kanonischer JSON-Block mit Hash
    └── check.md                     Prüfbericht, Kopfzeile in Zeile 1
```

### Ablauf

1. **Ziel nennen.** `--config-dir` ausdrücklich, sonst `$CLAUDE_CONFIG_DIR`, sonst
   `~/.claude`; die erste Ausgabezeile nennt den aufgelösten Pfad. Mehrere
   Config-Verzeichnisse bekommen je einen Lauf.
2. **plan (Default).** `inspect_config.py` schreibt `plan.md`. Oben steht die Ansicht für
   den Nutzer: Bestand, geplante Änderungen als Diff, Konflikte, Annahmen. Darunter steht
   ein Codeblock mit Info-String `json setup-user-plan`: Schema-Version, aufgelöster
   Interpreter, Interview-Antworten, je Zieldatei die Operation mit vollständigem
   Inhalt bzw. Merge-Patch, und je betroffener Bestandsdatei ein Basis-Hash. `apply` liest
   nur diesen Block. Der Hash läuft über den Block in kanonischer Form (Schlüssel
   sortiert, UTF-8, LF), ohne das Feld `hash` selbst. Die Kopfzeile in Zeile 1 und die
   Ansicht liegen außerhalb. Bestandsinhalte werden vor dem Hashen LF-normalisiert, und
   der absolute Pfad des Config-Verzeichnisses wird durch `<config-dir>` ersetzt. So ist
   der Hash unabhängig von Ort, Zeilenenden und `core.autocrlf`.
3. **Interview, höchstens drei Fragen** und nur, was nicht im Bestand steht: Sprache und
   Ton, Rechner und Shell, Git-Gewohnheiten. Claude übergibt die Antworten an
   `inspect_config.py --answers <json>`; das Skript setzt sie in CLAUDE.md und Regeln ein,
   der Plan trägt die fertigen Inhalte. Ohne Antwort — etwa bei `claude -p` — nimmt der
   Plan die Werte aus den Assets und führt sie als Annahme. Den Interpreter bestimmt
   `inspect_config.py` am Bestand: aus einem vorhandenen `statusLine`-Kommando, sonst
   `--python`, sonst `python3`; er steht im Block und damit im Hash.
4. **apply** in einem späteren Aufruf nach Bestätigung, nur mit `--config-dir` auf der
   Kommandozeile; `$CLAUDE_CONFIG_DIR` zählt nicht als ausdrücklich. Ein nicht
   existierendes Verzeichnis lehnt `apply` ab und legt es nie an.
   `apply_config.py --plan <config-dir>/setup-user/plan.md` prüft den Hash und die
   Basis-Hashes, setzt `<config-dir>` als absoluten Pfad mit Schrägstrichen ein (auch
   unter Windows, weil Git Bash Backslashes entfernt; statusline, „Windows
   configuration"), legt Backups an und schreibt in dieser Reihenfolge: `runtime/`
   kopieren und per Hash prüfen, `thresholds.json`, CLAUDE.md und Regeln, zuletzt
   `settings.json`. Bricht ein Schritt ab, bleibt `settings.json` unberührt. Danach
   `verify_install.py`. Übergabe „angewendet und geprüft, wirkt ab der nächsten Session"
   oder „angewendet, ungeprüft — <Grund>".
5. **check.** Bestand gegen Assets, `verify_install.py`, in Abschnitt B `route_check.py`;
   schreibt nur `check.md` mit Abweichungen oder „keine Abweichung". Ein eingetragenes
   Hook- oder Statusline-Skript, das fehlt, ist die erste Abweichung. Ein ausstehender
   `plan.md` bleibt unberührt.

**Sandbox für die Prüfung.** `verify_install.py` führt nur Befehle aus, deren Skriptpfad
auf eine Datei zeigt, deren Hash einem Asset gleicht. Jeder andere Befehl — die alte
Statusline des Nutzers, eine fremde Statusline — wird nicht ausgeführt und erscheint als
„ungeprüft (fremd, nicht ausgeführt)". Für die Asset-Befehle legt das Skript ein
Temp-Verzeichnis an, spielt dort einen Beispielzustand oberhalb einer Schwelle ein und
startet den Befehlsstring über `bash -c`, weil Claude Code Hooks und Statusline unter
Windows über Git Bash ausführt; fehlt `bash`, heißt das Ergebnis „ungeprüft — keine
bash". `CLAUDE_CONFIG_DIR`, `HOME` und `USERPROFILE` zeigen auf das Temp-Verzeichnis,
jeder Befehl hat 10 Sekunden. Erwartet werden eine Statusline-Ausgabe, eine Cache-Datei
im Temp-Verzeichnis und ein Hinweis des Hooks in der Form unten. Ein Hook, der schweigt,
wo er melden müsste, ist ein Befund; ebenso ein Exit ungleich 0, eine leere Statusline
oder stdout, das nicht genau ein JSON-Objekt ist.

**Vergleich in `check`.** Laufzeitdateien vergleicht `check` per Inhalts-Hash mit den
Assets. Kommandos in `settings.json` gelten als ausgerichtet, wenn ihr Skriptpfad auf eine
Datei mit passendem Hash zeigt. Ein relativer Skriptpfad gilt in Claude Code nur im
jeweiligen Arbeitsverzeichnis; `check` meldet ihn deshalb als Hinweis „nur im
Arbeitsverzeichnis gültig", nicht als Abweichung. Bei CLAUDE.md und `rules/` prüft
`check` nur Kopfzeile und Budget, nicht den Inhalt, weil das Interview sie anpasst.

**Mischen.** Eigene Einträge erkennt `apply` am Skriptpfad-Suffix
`setup-user/runtime/context_hint.py` bzw. `setup-user/runtime/statusline.py`; ein
vorhandener eigener Eintrag wird ersetzt, nicht verdoppelt. In `statusLine` ersetzt
`apply` nur `command`; `type`, `padding` und `refreshInterval` bleiben. Fremde Schlüssel
bleiben, Listen werden vereinigt. Geschrieben wird mit Einrückung 2, ohne ASCII-Escapes,
in der vorhandenen Schlüsselreihenfolge, mit LF und abschließendem Zeilenumbruch.
Backup-Ordner heißen `JJJJMMTT-hhmmss`, bei Kollision mit `-2`, `-3` dahinter.

**Statusline.** Die Statusline des Nutzers wird erkannt an der Kennzeile des Assets
oder an einem Hash aus `known-statusline-hashes.json` (Zeilenenden normalisiert). Dann
zeigt `statusLine` nach `apply` auf `runtime/statusline.py`; die alte Datei bleibt
liegen, die Anzeige bleibt gleich. Ist keine Statusline eingetragen, setzt `apply` das
Asset ein. Eine fremde Statusline bleibt eingetragen, und der Plan sagt
„Kontext-Hinweise nicht verfügbar — fremde Statusline schreibt keinen Kontextzustand";
der Hook wird trotzdem eingetragen: Ohne Zustand und Cache schweigt er, und er wirkt,
sobald der Nutzer auf die Asset-Statusline wechselt.

Das Asset liest stdin als Bytes und dekodiert UTF-8 mit Ersetzung, weil Python unter
Windows Pipes sonst mit der ANSI-Codepage liest und an Emoji scheitert. Es gibt zuerst
die Statuszeile aus und schreibt danach. Das Config-Verzeichnis ist
`$CLAUDE_CONFIG_DIR`, sonst das Verzeichnis drei Ebenen über der eigenen Datei, sonst
`~/.claude`. Im Limit-Cache gilt je Fenster: Fehlt das Fenster oder ist es `null`, oder
ist `used_percentage` `null`, bleibt der alte Wert dieses Fensters stehen. Der
Kontextzustand `state/context-<session_id>.json` dagegen wird bei fehlendem oder
`null`-Wert als `null` geschrieben, nicht mit dem alten Wert. `session_id` wird vor der
Verwendung im Dateinamen auf `[A-Za-z0-9_-]` geprüft. Geschrieben wird über eine
Temp-Datei und `os.replace`; scheitert das, etwa unter Windows bei offenem Leser, folgen
bis zu drei Versuche im Abstand von 50 ms, danach bleibt die alte Datei. Zustandsdateien,
deren Änderungszeit älter als 24 Stunden ist, und liegengebliebene `*.tmp` älter als eine
Stunde räumt es beim Schreiben ab. Das Skript endet immer mit 0.

**Kontext-Hinweis.** `context_hint.py` liest beim Absenden eines Prompts den Zustand der
eigenen `session_id` und den Limit-Cache. Kontext gilt, solange die `session_id` passt —
er ändert sich nur mit neuen Nachrichten, und danach läuft die Statusline. Ein
Limitfenster gilt, solange sein `resets_at_epoch` in der Zukunft liegt; ein älterer Wert
über der Schwelle ist eine wahre Untergrenze, weil ein Limit im Fenster nur steigt.

Merker: Für den Kontext hält `state/hints-<session_id>.json` je Schwelle „gemeldet"; fällt
der Wert unter die Schwelle (nach `/compact`), wird sie wieder scharf. Für Limits hält
`state/limit-hints.json` Schlüssel aus Fenster, Schwelle und `resets_at_epoch`; ein neues
Fenster hat einen neuen Schlüssel und ist damit von selbst wieder scharf, über alle
Sessions des Accounts hinweg. Der Hook liest und berührt seine Merkerdatei bei jedem
Lauf, damit das Aufräumen nach 24 Stunden eine laufende Session nicht trifft. Je Prompt
kommt höchstens ein Hinweistext; je Art nennt er nur die höchste neu überschrittene
Schwelle, niedrigere zählen als gemeldet.

Ausgabe: genau ein JSON-Objekt auf stdout,
`{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "…"}}`,
sonst nichts — beim Schweigen leeres stdout. Fehlt etwas oder ist es `null`, schweigt
der Hook. Der Hinweis ist als Feststellung formuliert, nicht als Anweisung — die Doku
warnt, imperative Texte könnten Claudes Schutz gegen Prompt-Injection auslösen (hooks,
„Add context for Claude") —, etwa „[setup-user] Kontext 63 % (Schwelle 60 %). Laut
Nutzerregel context.md ist das der Punkt für Handoff und /clear." Dass
`UserPromptSubmit` auch bei geplanten Aufgaben und Rückmeldungen von Subagents feuert,
ist gewollt. Das eingetragene Kommando lautet
`<python> "<config-dir>/setup-user/runtime/context_hint.py" || true`.

**Routing (Abschnitt B).** `route_check.py` bestimmt die im User-Scope aktiven Plugins
aus `enabledPlugins` der User-Settings, `defaultEnabled` und
`<config-dir>/plugins/installed_plugins.json`; es folgt dort dem Feld `installPath`,
weil Plugins aus einem lokalen Marketplace an Ort und Stelle laden, und beachtet
`CLAUDE_CODE_PLUGIN_CACHE_DIR`. Synchronisierte Plugins liest es unter `plugins/synced/`.
Projekt-Settings bewertet es nicht. Es meldet Namenskollisionen, Plugins mit
`SessionStart`-Hook (je Zeile „<plugin> · SessionStart-Hook · <matcher>"), Descriptions
mit `superpowers:` und den Stand der Abschaltbedingung aus Spec 20 mit ihren drei Teilen.
Teil (c) gilt als erfüllt, wenn die Regeldateien der Zeilen mit Status „Regel" im
Config-Verzeichnis liegen. Ausdrücklich gesetzte Werte des Nutzers in `enabledPlugins`
dreht das Profil nie um; der Plan führt sie als Konflikt. *Gemessen beim Bau (2026-10-14, CLI 2.1.296):* `claude plugin install`
schreibt den Wert `true` selbst in `enabledPlugins`; jedes per CLI installierte Plugin
gilt damit als gesetzt. Der Plan führt superpowers und engineering deshalb in der Regel
als Konflikt, und erst die Antwort `plugins_off` (Liste von Plugin-IDs) macht daraus einen
Patch (`references/routing.md`). Das Profil im Plan:

| Plugin | User-Scope |
| --- | --- |
| `cc-dev`, `cc-knowledge` | nicht gesetzt; `defaultEnabled: true` genügt |
| `cc-ui` | nicht gesetzt; an per Projekt (Spec 22) |
| superpowers (`@synced` oder `@<marketplace>`, wie gefunden) | `false`, erst wenn die Abschaltbedingung erfüllt ist; vorher bleibt es und der Plan sagt warum |
| engineering (erkannt am Plugin-Namen `engineering`, nie ein Plugin `cc-*`) | `false`, Annahme |

### Contract

- **Plan vor Schreiben.** `plan` und `check` schreiben nur `plan.md` bzw. `check.md` und
  Dateien im Temp-Verzeichnis der Prüfung. `apply` braucht `--config-dir` auf der
  Kommandozeile; dass Plan und Bestand unverändert sind, meldet `apply_config.py` per
  Hash und bricht bei Abweichung ab (G2). Dass der Plan gezeigt wurde, bleibt G1.
- **Mischen, nie überschreiben.** Jede berührte Datei hat vorher ein Backup; eigene
  Einträge werden ersetzt, nicht verdoppelt; Listen werden vereinigt; fremde Schlüssel
  bleiben; JSON wird vor dem Ersetzen geparst und atomar geschrieben; vorhandene
  CLAUDE.md und Regeldateien bekommen nur bestätigte Ergänzungen.
- **Der Hook hält nie etwas an.** Exit 0 in jedem Fall, `|| true` im Kommando,
  `settings.json` zuletzt geschrieben, fehlendes Skript als erste Abweichung in `check`.
- **Geprüft heißt gelaufen.** `verify_install.py` führt die eingetragenen Asset-Befehle
  in der Sandbox aus und erwartet Ausgabe, Cache und Hinweis; fremde Befehle und ein Lauf
  ohne bash heißen „ungeprüft".
- **Hinweise sind selten und belegt.** Höchstens einer je Prompt, je Schwelle einmal
  bis zum Wiederscharfwerden, nur mit gültigen Werten; sonst Schweigen.
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
`skill-forge` bleibt unfett, sonst meldet `rule_neighbors` ihn als `finding`. Der
Rückverweis in `skills/handoff/SKILL.md` erreicht die Projekt-Kopie unter
`.claude/skills/` über `sync_skills.py` (Spec 20).

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_statusline_keeps_cache_on_session_start` | `tests/test_setup_user_statusline.py` | Eingabe ohne `rate_limits` lässt beide Fenster stehen |
| `test_statusline_keeps_window_on_explicit_null` | dito | `five_hour: null` und `used_percentage: null` lassen den alten Wert des Fensters stehen |
| `test_statusline_respects_config_dir` | dito | zwei `CLAUDE_CONFIG_DIR` → zwei Caches; ohne Variable das Verzeichnis über der Skriptdatei |
| `test_statusline_partial_window_keeps_other_window` | dito | nur `five_hour` neu → `seven_day` bleibt unverändert |
| `test_statusline_survives_null_empty_and_non_ascii_input` | dito | Exit 0, eine Zeile Ausgabe; `null`-Kontext wird als `null` geschrieben; UTF-8 mit Emoji und ungültige Bytes brechen nichts |
| `test_statusline_display_unchanged` | dito | Ausgabe gleich der Fassung vom 2026-10-07 bei voller Eingabe |
| `test_statusline_state_prunes_and_sanitizes` | dito | Zustandsdatei entsteht; Änderungszeit älter als 24 h verschwindet; alte `*.tmp` verschwinden; `session_id` mit `../` wird abgewiesen |
| `test_statusline_classification` | dito | Kennzeile oder bekannter Hash → umgestellt; keine Statusline → Asset; fremde → bleibt, Plan nennt den Grund |
| `test_hint_once_and_rearms` | `tests/test_setup_user_hint.py` | zweiter Prompt über derselben Schwelle schweigt; nach Absinken und erneutem Überschreiten kommt wieder einer; neues Limitfenster ist wieder scharf |
| `test_hint_one_text_per_prompt_highest_threshold` | dito | Sprung von 50 auf 85 % → ein Hinweis mit Schwelle 80, Schwelle 60 gilt als gemeldet |
| `test_hint_silent_on_foreign_session_null_or_expired_limits` | dito | fremde `session_id`, `null`, `resets_at_epoch` in der Vergangenheit |
| `test_hint_limits_without_statusline_state` | dito | kein Kontextzustand, gültiges Limitfenster → nur Limit-Hinweis |
| `test_hint_exit_zero_on_any_error` | dito | kaputtes JSON auf stdin, nicht lesbarer Zustand, Ausnahme im Code → Exit 0, leeres stdout |
| `test_hint_output_shape` | dito | stdout ist genau ein JSON-Objekt mit `hookEventName` `UserPromptSubmit` und `additionalContext`, Text beginnt mit `[setup-user]` |
| `test_plan_is_path_and_eol_neutral` | `tests/test_setup_user_apply.py` | dasselbe Verzeichnis an zwei Orten und mit CRLF-Bestand → gleicher Hash; andere Kopfzeile → gleicher Hash |
| `test_apply_is_idempotent` | dito | zweiter `apply` mit neuem Plan erzeugt leeren Diff und keinen zweiten Hook-Eintrag |
| `test_apply_refuses_changed_plan_or_state` | dito | geänderter Block oder Bestand → Abbruch, keine Datei berührt |
| `test_apply_requires_explicit_existing_config_dir` | dito | ohne `--config-dir` oder mit nicht existierendem Verzeichnis → Abbruch, nichts angelegt |
| `test_apply_writes_settings_last` | dito | Fehler beim Kopieren von `runtime/` → `settings.json` unverändert |
| `test_apply_keeps_foreign_keys_and_statusline_options` | dito | fremder Schlüssel bleibt, Listen vereinigt, `padding` und `refreshInterval` bleiben; Backup enthält den alten Inhalt |
| `test_verify_runs_in_sandbox_only` | `tests/test_setup_user_verify.py` | nach dem Lauf keine neue oder geänderte Datei außerhalb des Temp-Verzeichnisses, auch nicht unter `HOME` |
| `test_verify_skips_foreign_commands` | dito | fremde und alte Statusline werden nicht ausgeführt und als „ungeprüft (fremd, nicht ausgeführt)" gemeldet |
| `test_verify_flags_silent_hook_nonzero_exit_and_empty_statusline` | dito | alle drei Fälle sind Befunde |
| `test_fixture_plans_are_current` | `tests/test_setup_user_fixtures.py` | Block in `plan.md` von `su-planned` und `su-own-statusline` gleicht einem neu erzeugten; Laufzeitdateien in `su-aligned` gleichen den Assets |
| `test_disable_model_invocation_only_for_claude_code_only` | `tests/test_skill_forge_lint.py` | Schlüssel bei setup-user → pass, bei einer anderen Skill → finding |
| `test_route_check_layouts_and_condition` (B) | `tests/test_setup_user_route.py` | Fake-Plugins in Cache, lokalem Marketplace und `synced/`; SessionStart-Hook, `superpowers:`-Verweis und alle drei Teile der Abschaltbedingung gemeldet; `cc-dev` nie als engineering erkannt |
| `test_profile_keeps_explicit_user_values` (B) | dito | ausdrücklicher Nutzerwert in `enabledPlugins` bleibt und steht als Konflikt im Plan |
| `test_gaps_json_names_match_spec_20` (B) | `tests/test_setup_user_fixtures.py` | jede Zeile in `superpowers-gaps.json` nennt Skills aus der Lückentabelle in Spec 20; Status prüft der Test nicht, weil er sich mit Spec 23 und 24 ändert |

### Evals

Jeder Prompt nennt `--config-dir ./cfg`, weil der Eval-Agent das echte Home des
Aufrufers sieht (known-limits, Isolation). Die Skill ist nur über ihren Slash-Befehl
aufrufbar; mit CLI 2.1.292 gemessen (erstes Review): Eine Skill mit
`disable-model-invocation: true` steht im `skills`-Feld des `init`-Ereignisses, und der
Slash-Aufruf mit `-p` läuft. Ohne installierte Skill antwortet der Agent auf
`/setup-user`, der Befehl sei nicht installiert. Weil die Plan-Ansicht aber alles
beschreibt und ein hilfsbereiter Agent sie von Hand umsetzen könnte, bindet jeder Eval
an mindestens ein Artefakt, das nur die Skripte erzeugen. Vor der Abnahme läuft jeder
Eval einmal mit `--without-skill` (Spec 18).

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-check-on-aligned-config-changes-nothing` | contract | `su-aligned` | `file_exists` und `artifact_header` auf `cfg/setup-user/check.md`; `file_matches` dort `keine Abweichung` und `nur im Arbeitsverzeichnis gültig`; `file_max_lines` 60 auf `check.md`; `file_unchanged` auf `cfg/settings.json`, `cfg/CLAUDE.md`, die vier Regeldateien und beide Laufzeitdateien, je Datei eine Assertion; `file_absent` `cfg/setup-user/plan.md` und `cfg/setup-user/backups/*/settings.json` | `check.md` mit Kopfzeile entsteht nur durch die Skill; Plan und Backup dürfen nicht entstehen, ein „reparierender" Agent fällt |
| 2 | `plan-is-default-and-writes-only-plan` | contract | `su-fresh` | `file_exists` und `artifact_header` auf `cfg/setup-user/plan.md`; `file_matches` dort `setup-user-plan`; `file_unchanged` `cfg/settings.json`; `file_absent` `cfg/CLAUDE.md` | den JSON-Block schreibt nur `inspect_config.py`; dass nur geplant wird, zeigen die beiden anderen Assertions |
| 3 | `apply-merges-existing-plan-and-backs-up` | contract | `su-planned` | `file_matches` `cfg/setup-user/backups/*/settings.json` auf `"spinnerTipsEnabled": false`; `file_matches` `cfg/settings.json` auf `"statusLine"`, auf `context_hint` und auf `"spinnerTipsEnabled": false`; `file_matches` `cfg/setup-user/runtime/context_hint.py` auf die Kennzeile; `file_matches` `cfg/setup-user/thresholds.json` auf `"_meta"`; `artifact_header` und `file_max_lines` 40 auf `cfg/CLAUDE.md`; `output_matches` `angewendet` | Kennzeile, `thresholds.json` mit `_meta` und Backup mit Alt-Inhalt entstehen nur durch `apply_config.py`; der fremde Schlüssel prüft das Mischen |
| 4 | `foreign-statusline-is-kept-while-hook-is-merged` | contract | `su-own-statusline` | `file_unchanged` `cfg/my-status.py`; `file_matches` `cfg/settings.json` auf `my-status` und auf `context_hint`; `file_exists` `cfg/setup-user/backups/*/settings.json`; `file_matches` `cfg/setup-user/thresholds.json` auf `"_meta"`; `output_matches` `ungeprüft` | `thresholds.json` und Backup nur durch `apply`; die fremde Statusline wird nicht ausgeführt, die Übergabe sagt deshalb „ungeprüft" |
| 5 | `superpowers-sessionstart-is-reported` | contract | `su-plugins` (B) | `file_matches` `cfg/setup-user/check.md` auf `superpowers · SessionStart-Hook` | nur `route_check.py` schreibt die Zeile in diesem Format; eine feste Überschriftenliste trifft das Muster nicht |

Prompts: 1 und 5 „/setup-user check --config-dir ./cfg", 2 „/setup-user --config-dir
./cfg", 3 und 4 „/setup-user apply --config-dir ./cfg — den Plan in
cfg/setup-user/plan.md habe ich gelesen und bestätige ihn". `su-planned` und
`su-own-statusline` bringen einen `plan.md` mit, den `inspect_config.py --python python3`
erzeugt hat; `test_fixture_plans_are_current` hält ihn aktuell. `su-fresh` und
`su-planned` tragen eine `cfg/settings.json` mit `"spinnerTipsEnabled": false`.
`su-aligned` nutzt relative Skriptpfade, weil eine Fixture keine absoluten tragen kann;
daher der Hinweis in Eval 1.

## Alternatives considered

**Kontext aus dem Transcript selbst berechnen.** Hooks bekommen `transcript_path`, und
dort stehen je Nachricht die Token-Zahlen, aus denen die Doku `used_percentage`
berechnet (im Review per grep gesehen). Das ginge auch bei `-p` und mit fremder
Statusline. Verworfen für den ersten Bau: Das Format ist nicht dokumentiert, und die
Fenstergröße steht nicht darin. Gewinnt, wenn kopflose Läufe Kontext-Hinweise brauchen.

**Hook als Plugin-Hook mit `${CLAUDE_PLUGIN_ROOT}`.** Kein Kopieren. Verworfen: Plugins
können keine `statusLine` mitbringen, also muss die Statusline ohnehin an einen stabilen
Ort; der Hook liest deren Zustand und gehört daneben. `${CLAUDE_PLUGIN_ROOT}` „changes
when the plugin updates" (plugins), und in Cloud-Sessions laden Plugins nicht.

**Plan nur als Markdown-Diff.** So stand es in der ersten Fassung. Verworfen, weil
`apply` aus einem Diff die Inhalte nicht sicher gewinnt und der Hash an Kopfzeile, Pfaden
und Zeilenenden hing.

**Fremde Statusline in der Sandbox mit ausführen.** Prüfte mehr. Verworfen, weil die alte
Statusline `CLAUDE_CONFIG_DIR` ignoriert und Beispielwerte in den echten Cache schriebe.

**Limitwerte nur zehn Minuten lang gültig.** So stand es in der ersten Fassung.
Verworfen, weil ein Limit im Fenster nur steigt und die Frist genau den ersten Prompt
nach einer Pause stumm schaltete.

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
beobachtet er nur `~/.skills`; vorgemerkt für evalkit). Abschnitt B vor Spec 23 (gebaut 2026-10-14, nach Spec 23 und 24).

## Open questions

*Annahme:* Schwellen Kontext 60 % und 80 %; 5-Stunden-Limit 80 %; 7-Tage-Limit 85 %;
Aufräumen nach 24 Stunden Änderungszeit — widersprich, falls nein.

*Annahme:* Budgets CLAUDE.md ≤ 40 Zeilen, je Regeldatei ≤ 20, zusammen ≤ 120 Zeilen
immer geladener User-Scope — widersprich, falls nein.

*Annahme:* Das engineering-Plugin geht im User-Scope aus, weil es mit testing-strategy,
debug-ledger und review-context überlappt — widersprich, falls nein.

*Annahme:* `permissions.deny` für `.env`-Dateien, `~/.ssh` und Zertifikatsschlüssel wird
im Plan angeboten, nicht gesetzt. Laut permissions-Doku gilt ein Read-Deny für die
eingebauten Datei-Werkzeuge und erkannte Bash-Dateikommandos, nicht für beliebige
Unterprozesse wie ein Python-Skript; der Plan sagt das so.

*Annahme:* Das agent-dashboard liest den Limit-Cache (Angabe des Nutzers vom 2026-10-07;
früher fragte es `/usage` per headless-Aufruf ab). Der Cache des zweiten Accounts liegt
künftig unter `<cfgB>/usage-cache.json`. Ein Fenster bleibt nach seinem `resets_at` mit
altem Wert stehen; Leser prüfen `resets_at_epoch` selbst — widersprich, falls das
Dashboard dafür nicht angepasst werden soll.

**Wirkt `enabledPlugins` auf `superpowers@synced`?** Laut plugins/loading schreibt
`claude plugin disable <name>@synced` genau diesen Schlüssel in die User-Settings.
Offen ist nur, ob superpowers beim Nutzer `@synced` oder aus einem Marketplace kommt;
`route_check.py` entscheidet das am Bestand.

Laut settings-Doku verschiebt `CLAUDE_CONFIG_DIR` auch die Plugin-Ablage;
`route_check.py` sucht deshalb unter `<config-dir>/plugins/` und meldet „ungeprüft",
wenn dort nichts liegt.

Ungemessen sind auf dem Windows-PC: ob `|| true` im Hook-Kommando dort greift, ob
`python` oder `py -3` der richtige Interpreter ist, ob `CLAUDE_CONFIG_DIR` an das
Statusline-Kommando vererbt wird und ob `os.replace` bei offenem Leser scheitert. Die
Statusline in VS Code und Desktop ist ungemessen. Ebenso offen ist, ob eine mitten in
der Session geänderte Hook-Konfiguration sofort greift; die Übergabe sagt deshalb „wirkt
ab der nächsten Session".

Ungemessen bleibt, ob Hinweise das Verhalten tatsächlich ändern — ein Eval kann den
Kontextstand nicht herbeiführen. Gemessen werden nur Entstehen und Schweigen des
Hinweises (Tests).

## Next steps

Spec 20 zuerst bauen. Dann Plan mit `impl-plan` (16) für Abschnitt A und Bau nach
`skill-forge` (17) Schritt 3 bis 7. Erster echter Lauf auf dem Windows-PC je
Config-Verzeichnis, mit den offenen Windows-Messungen als Abnahme; danach auf der Devbox.
Abschnitt B nach Spec 23.
