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
- **Abschnitt B.** Kein Routing, kein Plugin-Profil, kein Eval 5.

## Offen für die nächste Runde

- Erster echter Lauf auf dem Windows-PC je Config-Verzeichnis, danach auf der Devbox;
  dabei die Windows-Punkte oben messen und hier eintragen.
- Die vier Evals im Harness außerhalb eines Root-Containers fahren, mit und ohne Skill.
- Abschnitt B nach Spec 23.
- Die Kopfzeile von `plan.md` nennt den absoluten Erzeugungspfad; für versionierte
  Fixture-Pläne wäre der Pfad wie getippt (`cfg`) lesbarer.
