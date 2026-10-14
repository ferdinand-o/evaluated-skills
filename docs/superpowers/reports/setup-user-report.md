<!-- skill: skill-forge | schema: 1 | generated: von Hand nach skills/skill-forge/assets/skill-template/report.md -->
# setup-user — Abschlussbericht (Abschnitt A)

Gebaut nach `specs/Spec 21 – setup-user.md` und
`docs/superpowers/plans/2026-10-09-setup-user.md`, Tier 1, vom 2026-10-09 bis
2026-10-11 sequenziell im Hauptkontext (Gate: alle 14 Tasks gekoppelt). Abschnitt B
(Plugin-Routing, `route_check.py`, Eval 5) wartet auf Spec 23.

## Was entstanden ist

- `skills/setup-user/SKILL.md` (112 Zeilen) mit den Modi plan, apply und check, nur als
  Slash-Befehl (`disable-model-invocation: true`, im Lint über `CLAUDE_CODE_ONLY`).
- Drei Werkzeuge: `inspect_config.py` schreibt `plan.md` mit einem kanonischen
  JSON-Block, dessen Hash Ort, Zeilenenden und Kopfzeile nicht kennt;
  `apply_config.py` prüft Hash und Bestand, legt Backups an und schreibt `settings.json`
  zuletzt; `verify_install.py` führt nur Befehle aus, deren Skript einem Asset gleicht,
  in einer Sandbox, und schreibt mit `--write-check` den Prüfbericht `check.md`.
- Zwei Laufzeitskripte für das Config-Verzeichnis: `statusline.py` aus der Statusline
  des Nutzers (Anzeige byte-gleich, Cache und Kontextzustand neu) und `context_hint.py`,
  der `UserPromptSubmit`-Hook, der nie etwas anhält.
- Drei References, ein CLAUDE.md-Gerüst, vier Regeln, das Hook-Fragment, die Liste
  bekannter Statusline-Hashes.
- Vier Evals mit vier Fixtures und ein Fixture-Test, der jeden Eval mit den Skripten
  nachspielt und an seinen eigenen Assertionen misst.
- Nachbarn: handoff nennt setup-user, die Routing-Matrix in Spec 00 und README hat eine
  Zeile, Spec 00 §5 die Ausnahme für Claude-Code-spezifische Skills, `cc-dev` listet die
  Skill.

## Die Entscheidungen, die den Bau geprägt haben

- **Die Statusline kam vom Nutzer.** Sie lag nicht im Repo; der Plan machte ihre Übergabe
  zu Task 1 und baute alles andere vorher. Eine korrigierte Fassung aus dem Review gab es
  nicht, die Korrektur entstand als Asset aus dem Original.
- **Für `check.md` fehlte ein Skript.** Der Plan hatte keins, Eval 1 bindet aber daran.
  Fix-Runde von Task 8: `verify_install.py --write-check`. Dabei fiel auf, dass die
  Sandbox relative Skriptpfade vom falschen Verzeichnis aus startete; Befehle laufen jetzt
  vom Arbeitsverzeichnis aus, wie in Claude Code.
- **References ohne Kopfzeile.** Der Plan verlangte eine; im Repo trägt keine Reference
  eine, und die Lint-Regel prüft nur `assets/`. Der Plan wurde angepasst.
- **Ein Token, den `verify` nie hätte finden können.** Task 9 sollte
  `context_hint.py || true` produzieren; im JSON steht dazwischen ein maskiertes
  Anführungszeichen. Ersetzt durch `UserPromptSubmit`.

## Was gemessen wurde

Endstand der Suite: 1 406 grün, 3 übersprungen, 2 rot — beide vorbestehend:
`test_rest_api_architect_gate` (Spectral) und der Lint-Registertest für mobile-audit
(auf main schon rot). `lint_skill.py skills/setup-user` ohne Befund.

Ende-zu-Ende auf einem Temp-Config-Verzeichnis mit der Statusline des Nutzers als
Bestand: Der Plan erkennt sie am Hash als eigene, `apply` stellt sie auf das Asset um und
behält `padding`, trägt den Hook ein, `verify_install.py` meldet „geprüft"; das
Temp-Home blieb leer.

Eval-Läufe außerhalb des Harness, wie bei den anderen Skills der Sammlung: Workspace über
`evalkit.workspace.prepare()`, ein Opus-Subagent mit nichts als dem Prompt und dem
Hinweis auf `.claude/skills/`, Bewertung mit `evalkit.runner.grade()` gegen die Baseline;
als Ausgabe für `output_matches` diente die Übergabe des Agenten.

| Eval | Ergebnis | Beobachtung |
| --- | --- | --- |
| 1 Anti-Zeremonie, check | bestanden | ein Aufruf `--write-check`, „keine Abweichung", zwei Hinweise auf relative Pfade, sonst nichts geschrieben |
| 2 plan als Default | bestanden | nur `plan.md`, Annahmen aus den Assets offen benannt, `apply` als nächster Schritt in eigenem Aufruf |
| 3 apply mischt und sichert | bestanden | „angewendet und geprüft, wirkt ab der nächsten Session", `spinnerTipsEnabled` erhalten, Backup |
| 4 fremde Statusline | bestanden | „angewendet, ungeprüft — fremde Statusline nicht ausgeführt", Hinweis, dass Kontext-Hinweise erst mit der Asset-Statusline wirken |

Vier von vier, ein Lauf je Eval — eine Stichprobe. Zwei Agenten bemerkten, dass die
Kopfzeile des Fixture-Plans den Pfad trägt, unter dem er erzeugt wurde; der Block nutzt
`<config-dir>`, Hash und Bestand stimmten.

## Was nicht gemessen wurde

- **Der Harness selbst.** `run_evals.py` bricht unter root ab; keiner der vier Evals lief
  im Harness, und `--without-skill` lief nicht. Ob ein Agent ohne Skill auf
  `/setup-user` wirklich nichts ändert, ist aus dem Review vom 2026-10-07 übernommen.
- **Windows.** `|| true` im Hook-Kommando, der Interpreter, die Vererbung von
  `CLAUDE_CONFIG_DIR` an die Statusline und `os.replace` bei offenem Leser misst erst der
  erste echte Lauf auf dem Windows-PC.
- **Die Wirkung der Hinweise.** Tests messen, dass der Hook meldet und schweigt; ob
  Claude danach anders handelt, misst nichts.
- **Hook-Änderungen mitten in der Session.** Die Übergabe sagt „wirkt ab der nächsten
  Session", gemessen ist das nicht.
- **Echte Nutzerdaten.** Die Statusline lief nur mit Beispiel-Eingaben; ob das
  agent-dashboard den erweiterten Cache (`_meta`, behaltene Fenster) liest, ist
  ungeprüft.

## Offen für die nächste Runde

- Erster echter Lauf auf dem Windows-PC je Config-Verzeichnis, danach auf der Devbox;
  dabei die Windows-Punkte oben messen und hier eintragen.
- Die vier Evals im Harness außerhalb eines Root-Containers fahren, mit und ohne Skill.
- Die Kopfzeile von `plan.md` nennt den absoluten Erzeugungspfad; für versionierte
  Fixture-Pläne wäre der Pfad wie getippt (`cfg`) lesbarer.

## Abschnitt B — Routing und Plugin-Profil (2026-10-14)

Gebaut nach `docs/superpowers/plans/2026-10-14-setup-user-b.md` (10 Tasks, das Gate
koppelte alle), sequenziell im Hauptkontext, jeder Task mit `verify` im sauberen Worktree
abgenommen; nach Spec 23 (work-plan) und Spec 24 (test-first).

### Was entstanden ist

- `scripts/route_check.py`: aktive Plugins aus `installed_plugins.json`, `synced/`,
  `enabledPlugins` und `defaultEnabled`; SessionStart-Hooks, Kollisionen,
  `superpowers:`-Verweise und die Abschaltbedingung (a) bis (c). Ausgabe als JSON (für den
  Plan) oder als Abschnitt `## Plugins` (für `check.md`), ohne absolute Pfade.
- `references/superpowers-gaps.json`: die Lückentabelle aus Spec 20 als Daten; keine
  Zeile heißt mehr „Lücke".
- `references/routing.md`: Profil, aktive Plugins, Layout mit Messung, Abschaltbedingung.
- `inspect_config.py` ruft `route_check.py` als Unterprozess auf und schreibt das Profil in
  den Plan; `apply_config.py` mischt `enabledPlugins`; `verify_install.py --write-check`
  hängt den Abschnitt `## Plugins` an `check.md`, ohne Abweichungen zu zählen.
- Eval 5 `superpowers-sessionstart-is-reported` mit Fixture `su-plugins`, deren
  `installPath`-Werte von einem anderen Rechner stammen; das Skript findet die Plugins über
  den Cache-Fallback.

### Entscheidungen

- **Erst gemessen, dann geplant.** In einem Wegwerf-Config-Verzeichnis lief `claude
  plugin marketplace add` mit diesem Repo und `claude plugin install cc-dev@cc-skills`.
  Ergebnis: `installed_plugins.json` in Version 2, `installPath` unter
  `plugins/cache/cc-skills/cc-dev/<sha12>` mit der ganzen Repo-Kopie — und
  `"enabledPlugins": {"cc-dev@cc-skills": true}` in den User-Settings.
- **Gesetzte Werte bleiben, auch die der CLI.** Weil die Installation `true` schreibt,
  wäre jedes Plugin „ausdrücklich gesetzt". Die Regel der Spec blieb trotzdem: Der Plan
  führt den Wert als Konflikt, und nur die Antwort `plugins_off` macht daraus einen Patch.
  Ein stilles Abschalten von superpowers wäre die schlechtere Fehlerart. Spec 21 trägt die
  Messung nach.
- **Unterprozess statt Import.** `inspect_config.py` und `verify_install.py` rufen
  `route_check.py` auf; so bleibt die Regel „Nachbarskripte werden nicht importiert", und
  ein fehlendes oder kaputtes Skript heißt „ungeprüft" statt Absturz.
- **Plugins informieren, sie weichen nicht ab.** Ein SessionStart-Hook ist kein Fehler der
  Einrichtung; der Anti-Zeremonie-Fall auf `su-aligned` meldet weiter „keine Abweichung".

### Was gemessen wurde

Suite: 1 534 grün, 3 übersprungen, 1 rot (`test_rest_api_architect_gate`, Spectral fehlt
in der Umgebung). `lint_skill.py skills/setup-user` ohne Befund.

`route_check.py` gegen die echte CLI-Installation: `cc-dev@cc-skills` aktiv über
`enabledPlugins`, 14 Skills aus der `skills`-Liste erkannt, Abschaltbedingung am
installierten Bestand erfüllt (keine Lücke, kein `superpowers:`-Verweis im Cache von
heute, Regel installiert).

Echte kopflose Sessions (`claude -p` mit `--allowedTools`, `--permission-mode
acceptEdits`, CLI 2.1.296), je ein Lauf, bewertet mit `evalkit.runner.grade()`:

| Eval | mit Skill | ohne Skill |
| --- | --- | --- |
| 1 `anti-ceremony-check-on-aligned-config-changes-nothing` | bestanden | — |
| 2 `plan-is-default-and-writes-only-plan` | bestanden | — |
| 3 `apply-merges-existing-plan-and-backs-up` | bestanden | — |
| 4 `foreign-statusline-is-kept-while-hook-is-merged` | bestanden | — |
| 5 `superpowers-sessionstart-is-reported` | bestanden | nicht bestanden |

Evals 1 bis 4 liefen erneut, weil sich SKILL.md geändert hat (`evals_due`). Im Lauf zu
Eval 5 nannte Claude den Hook, die erfüllte Bedingung und fragte, statt abzuschalten:
„Das Plugin steht in `enabledPlugins`. Ich schalte es deshalb nicht selbst ab." Ohne
Skill prüfte der Agent von Hand, schrieb kein `check.md` und meldete als Befund, dass in
der Fixture das Hook-Skript `session-start.sh` fehlt — die Fixture trägt nur
`hooks.json`, weil `route_check.py` das Skript nicht liest.

Beim Bau gefunden: `superpowers-gaps.json` nennt `test-driven-development` als Datenwert
und machte `test_no_superpowers_routing_targets` rot. `verify` je Task fährt nur die Tests
des Tasks; erst die Suite vor dem Report fand es. Behoben in einem eigenen Commit.

### Was nicht gemessen wurde

- **Ein Marketplace aus GitHub und `plugins/synced/` mit Inhalt.** Gemessen ist nur der
  lokale Marketplace; der synchronisierte Ordner hier ist leer.
- **Der echte superpowers-Cache des Nutzers.** Matcher und Hook-Ort stammen aus der
  Fixture, nicht aus seiner Installation.
- **Ob `enabledPlugins: false` superpowers wirklich ausschaltet** — weder hier noch beim
  Nutzer gelaufen.
- **Eval 5 mit Wiederholung und Evals 1 bis 4 ohne Skill** in diesem Durchgang.

