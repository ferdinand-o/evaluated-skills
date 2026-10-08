# Spec 22: setup-repo — ein Repo, in dem Claude weiß, wann es fertig ist und wann eine Arbeit ein neues Ziel ist

Skill-Spezifikation · Zyklus 22 · Entscheidung: alles, was in Cloud, CI und jedem Clone gelten muss, liegt im Repo; Ziele leben in einem Ledger plus immer geladener Regel plus Bereichs-Hook, nicht in einer Skill, weil eine Regel immer gilt und eine Skill erst ausgelöst werden muss; gebaut in vier Abschnitten, Harness-Änderung zuerst · Abgeglichen mit Spec 00 · Überarbeitet nach unabhängigem Review (zweite Runde 2026-10-08: Basis je Turn, kein Folgeturn, Zielregel mit festen Fällen, Interpreter entschieden)

## Problem

Der Nutzer will Repos nach Best Practice einrichten: `.claude`-Ordner, aus dem Repo
erarbeitete Rules, Goal Management, eine Review-Herangehensweise je Tech-Stack
(Gespräch vom 2026-10-07). Beim Goal Management will er beides — Definition of Done
mit Verifikation und Projektziele bzw. Backlog — und dass Claude während der
Entwicklung selbst erkennt, wann eine Arbeit ein neues Ziel ist.

Fünf Messungen aus der Claude-Code-Doku bestimmen den Zuschnitt:

- **Cloud-Sessions lesen nur das Repo, und Plugins laden dort nicht.** In einer Session
  mit einem Repo wird `.claude/settings.json` gelesen, User- und lokale Settings sind
  „not read"; in einer Session mit mehreren Repos nur `enabledPlugins` und
  `extraKnownMarketplaces`. „Cloud sessions additionally load project skills committed
  to the cloned repository's `.claude/skills/`", Plugins aus Repo- oder User-Settings
  „don't load in cloud sessions" (settings, skills).
- **`/goal` gilt nur für eine Session.** „it's active for the current session only";
  „Running `/clear` … also removes any active goal" (goal). Ein Resume stellt ein
  aktives Ziel wieder her. Der Evaluator „doesn't run commands or read files
  independently".
- **CLAUDE.md verdrängt `AGENTS.md`.** „By default, Claude reads `AGENTS.md` only when
  you have no `CLAUDE.md` in your working directory or above it"; mitgezählt werden
  auch `.claude/CLAUDE.md` und `CLAUDE.local.md` (memory, „When Claude Code reads
  AGENTS.md").
- **Zu lange Anweisungen werden ignoriert.** „target under 200 lines per CLAUDE.md
  file"; Regeln mit `paths` laden nur bei passenden Dateien; importierte Dateien laden
  beim Start mit (memory).
- **`claude -p` nutzt Projekt-Hooks, aber keine Projekt-Freigaben.** „a `-p` session
  runs the hooks in a project's `.claude/settings.json` … even in a folder you've never
  trusted" (headless); `permissions.allow` aus dem Repo ist dort „Not used" (permissions,
  „What runs before you trust a folder").

Dazu zwei Messungen aus der hooks-Doku, die den Bereichs-Hook bestimmen (im zweiten
Review per WebFetch geprüft): `additionalContext` am `Stop`-Ereignis „keeps the
conversation going through the same loop protections as `decision: "block"`" — es hält
das Turn-Ende also an und kostet einen vollen Modellturn. Und bei Exit 0 am
`Stop`-Ereignis landen stdout und stderr nur im Debug-Log; Claude und der Nutzer sehen
sie nicht. Sichtbar für den Nutzer ist nur das gemeinsame Feld `systemMessage`.

Die Doku stellt eine ausführbare Prüfung als den Hebel für unbeaufsichtigte Arbeit dar:
„Give Claude a check it can run … It's the difference between a session you watch and
one you walk away from" (best-practices). Der Eval-Harness dieser Sammlung schließt
heute alles unter `.claude/` aus (`EXCLUDED_PREFIXES = (".git/", ".claude/")` in
`evalkit/assertions.py`); jede Assertion dorthin endet als Harness-Fehler.

## Constraints

Claude-Code-spezifisch. Fünf Abweichungen von Spec 00, alle hier begründet:

1. `disable-model-invocation: true` im Frontmatter (Liste `CLAUDE_CODE_ONLY`, Spec 21).
2. Ablage unter `.claude/` für Settings, Rules, Agents und Hooks — Claude-Code-Orte,
   keine Skill-Artefakte nach Spec 00 §1. Ephemera liegen unter `.skills/cache/setup-repo/`.
3. Spec 00 sagt: Skills „installieren aber nie selbst in fremde `settings.json`", Hooks
   bleiben opt-in. Diese Skill schreibt die Repo-Settings nur nach gezeigtem und
   bestätigtem Plan, und jeder Hook ist im Plan einzeln abwählbar. Der Bereichs-Hook ist
   vorausgewählt, weil der Nutzer will, dass Claude neue Ziele selbst erkennt; der
   Verifikations-Hook ist abgewählt.
4. `.claude/settings.json` und die kopierten Hook-Skripte tragen keine Kopfzeile; JSON
   hat keinen Platz dafür, und die Skripte erkennt `check` per Inhalts-Hash gegen die
   Assets. Alle Markdown-Ephemera (`plan.md`, `apply.md`, `check.md`) tragen die
   Kopfzeile in Zeile 1, alle JSON-Ephemera (`detect.json`, `candidates.json`,
   `goal-scope.json`) tragen `_meta`.
5. `docs/goals.md` ist nutzergepflegt und maschinenlesbar, also nach Spec 00 §1 eher
   Konfiguration; es liegt trotzdem unter `docs/`, weil Menschen es lesen und pflegen
   sollen.

Alle Skripte Tier 1 und plattformübergreifend; Laufzeitskripte werden ins Repo kopiert
(`.claude/hooks/`) und über `$CLAUDE_PROJECT_DIR/.claude/hooks/…` aufgerufen (so zeigt
es hooks-guide), damit sie in Cloud-Sessions ohne Plugin laufen. Das committete
Kommando startet Python über einen Starter, der unter Linux, in der Cloud und in Git
Bash unter Windows gleich lautet:
`command -v python3 >/dev/null 2>&1 && exec python3 "<skript>" "$@" || exec python "<skript>" "$@"`.
Ob der Windows-Store-Platzhalter für `python3` ihn dort aushebelt, misst der Bau auf dem
Windows-PC als Abnahme. Gate-Grade: Bestätigung vor `apply` G1; Hash über Plan und
Bestand G2 wie Spec 21; der Bereichs-Hook meldet und hält nichts an; der optionale
Verifikations-Hook ist G3. Die Skill committet nie.

Dateien mit Frontmatter in Zeile 1 (Rules mit `paths`, `.claude/agents/reviewer.md`)
tragen die Kopfzeile als erste Zeile nach dem Frontmatter; dafür kommt eine „Begründete
Ausnahme" mit den wörtlichen Asset-Pfaden in `docs/artifact-header.md`, und der Satz
über die Zahl der Ausnahmen dort wird nachgezogen. Plugin: `cc-dev` (Spec 20). Die
Erkennung ist eigen (`detect_repo.py`), weil `detect_stack.py` aus testing-strategy zwar
Test-Runner und Frontend-SPAs kennt, aber weder Delphi noch Makefile oder Agent-Dateien.

Gebaut wird in vier Abschnitten, je mit eigenem Plan:

- **A — Harness:** `EXCLUDED_PREFIXES` auf `(".git/", ".claude/skills/", ".claude/worktrees/")`,
  danach die Contract-Evals aller Skills einmal fahren. Eigener PR vor allem anderen.
- **B — Kern:** Erkennung, Ernte, Verifikationsbefehl, CLAUDE.md, Rules,
  `plan`/`apply`/`check`, Plugins je Repo, optionaler Verifikations-Hook; Evals 1 bis 5.
- **C — Ziele:** Ledger, Zielregel, Bereichs-Hook, Vorlagen-Messung.
- **D — Ziel-Reviewer:** erst, wenn die Delphi-Prüfpunkte vom Nutzer vorliegen.

## Approach

**Eiserne Regel:** *Kein Verifikationsbefehl und keine aus dem Repo geerntete Regel ohne
Beleg, kein Ziel ohne prüfbares „Fertig wenn" — was fehlt, steht als „ungeprüft" da, nie
erfunden.* Die Zielregel selbst ist Inhalt der Skill, keine geerntete Regel.

### Skill-Struktur

```
skills/setup-repo/
├── SKILL.md                         Modi plan/apply/check, Eiserne Regel, Contract, Abgrenzung
├── references/rules-harvest.md      Kandidat → ableitbar / Werkzeug / Regel; paths wo möglich; Quelle je Regel
├── references/plan-format.md        kanonischer JSON-Block wie Spec 21, Info-String setup-repo-plan
├── references/goals.md              (C) Ledger-Schema, Glob-Dialekt der Bereiche, ID-Vergabe, Klassifikation entdeckter Arbeit
├── references/review/python.md      (D) Konformitäts-Prüfpunkte je Stack, jeder mit Quelle; fließen beim apply in reviewer.md ein
├── references/review/typescript.md  (D)
├── references/review/delphi.md      (D) Prüfpunkte vom Nutzer
├── references/review/generic.md     (D)
├── assets/CLAUDE.md.tmpl            Gerüst: Kopfzeile, Zeile „Verifikation: …", @AGENTS.md falls vorhanden; Endung .tmpl, damit Claude Code die Datei beim Arbeiten im Ordner nicht als Anweisung lädt
├── assets/goals.md                  (C) Ledger-Gerüst für docs/goals.md, Kopfzeile schema 1
├── assets/rules/goals.md            (C) immer geladene Zielregel ≤ 25 Zeilen, Kopfzeile in Zeile 1
├── assets/agents/reviewer.md        (D) Ziel-Reviewer: Diff gegen Fertig-wenn, Bereich und Stack-Prüfpunkte; Kopfzeile nach dem Frontmatter
├── assets/runtime/goal_scope.py     (C) Tier 1 — UserPromptSubmit: Basis des Turns, offene Meldung als additionalContext; Stop: Änderungen außerhalb der Bereiche → systemMessage und offene Meldung
├── assets/runtime/verify_stop.py    Tier 1 — optionaler Stop-Hook: Verifikationsbefehl; höchstens drei Blocks in Folge; --selftest prüft nur das Programm
├── assets/hooks/goal-scope.json     (C) Fragment für .claude/settings.json, beide Ereignisse; meldet
├── assets/hooks/verify-stop.json    Fragment, opt-in; G3
├── scripts/detect_repo.py           Tier 1 — Sprachen, Frontend, Runner, Linter-/Formatter-Konfiguration, Tests, CI, CLAUDE-Dateien, AGENTS.md, Projekt-Skills unter .claude/skills/
├── scripts/harvest_rules.py         Tier 1 — Regelkandidaten mit Quelle aus Konfigurationen, CONTRIBUTING, Commit-Betreffs → candidates.json
├── scripts/plan_repo.py             Tier 1 — liest candidates.json mit Klasse je Kandidat; plan.md mit Ansicht und Block samt Hash; Budget samt Importen
└── scripts/apply_repo.py            Tier 1 — wendet nur einen Plan mit passendem Hash an; schreibt apply.md; prüft Hooks mit Beispiel-Payload

evalkit/assertions.py, evalkit/workspace.py   (A) EXCLUDED_PREFIXES (".git/", ".claude/skills/", ".claude/worktrees/"); Docstrings und Fehlertext nachgezogen
tests/test_assertions.py, tests/test_workspace.py   (A) .claude/settings.json beobachtet, .claude/skills/ und .claude/worktrees/ nicht
docs/artifact-header.md              Begründete Ausnahme: Kopfzeile nach dem Frontmatter, wörtlich mit skills/setup-repo/assets/agents/reviewer.md; Satz „Die drei dokumentierten Ausnahmen" nachgezogen
skills/handoff/SKILL.md, skills/testing-strategy/SKILL.md, skills/review-context/SKILL.md, skills/feature-spec/SKILL.md   Rückverweis, der setup-repo wörtlich nennt; Projekt-Kopien über sync_skills.py
.claude-plugin/marketplace.json      setup-repo in der skills-Liste von cc-dev (Spec 20)
specs/Spec 00 – skill-foundation.md, README.md   Matrixzeile setup-repo; README „Aufbau" nennt evals-templates/
docs/known-limits.md                 Abschnitt setup-repo
docs/superpowers/reports/setup-repo-report.md   Report mit „Was nicht gemessen wurde"
evals/setup-repo/evals.json          fünf Evals, siehe unten
evals/fixtures/sr-aligned/, sr-fresh/, sr-notests/, sr-planned/, sr-tampered/   je fixture.json mit "git": true
evals-templates/setup-repo/evals.json, evals-templates/fixtures/sr-goals-seeded/   (C) Vorlagen-Messung der Zielregel
tests/test_setup_repo_*.py           siehe Tests (Repo)
```

`.skills/cache/` ist in der `.gitignore` dieses Repos an der Wurzel verankert (das Muster
enthält einen Schrägstrich); versionierte Fixture-Pläne unter
`evals/fixtures/*/.skills/cache/setup-repo/` brauchen deshalb keine Ausnahme.

Im Zielrepo entsteht nach `apply`:

```
CLAUDE.md                            neu mit Kopfzeile, oder bestehende nur um bestätigte Abschnitte ergänzt
.claude/settings.json                gemischt: permissions.allow für Verifikation, Tests, Lint; hooks
.claude/settings.local.json          enabledPlugins für dieses Repo (persönlich, nicht committet)
.claude/rules/goals.md, weitere aus Belegen
.claude/agents/reviewer.md           (D) mit den Prüfpunkten des erkannten Stacks
.claude/hooks/goal_scope.py, optional verify_stop.py
docs/goals.md                        (C)
.gitignore                           Zeilen .skills/cache/ und .claude/settings.local.json
```

### Ablauf

1. **Erkennen.** `detect_repo.py` schreibt `.skills/cache/setup-repo/detect.json`.
2. **plan (Default).** `harvest_rules.py` schreibt `candidates.json`; Claude trägt je
   Kandidat die Klasse ein: ableitbar aus dem Code (fällt weg), schon durch ein
   konfiguriertes Werkzeug geprüft (keine Regel, im Bericht als „Werkzeug"), sonst Regel —
   mit `paths`, wo sie nur einen Teil betrifft. `plan_repo.py` schreibt
   `.skills/cache/setup-repo/plan.md`: oben die Ansicht mit Diff, je Kandidat eine Zeile
   „Kandidat · Quelle · Klasse", Budget und abwählbaren Hooks; darunter der Block
   `json setup-repo-plan` nach `references/plan-format.md`. Der Hash läuft nur über den
   Block in kanonischer Form, mit LF-normalisierten Inhalten, Pfaden relativ zur
   Repo-Wurzel, ohne HEAD-SHA, ohne `.claude/skills/`. Bis `apply` die `.gitignore`
   ergänzt, ist `.skills/cache/` im Zielrepo unversioniert sichtbar; der Plan sagt das.
3. **Verifikation festlegen.** Aus vorhandenen Einträgen (`Makefile`, `package.json`-
   Scripts, `pyproject.toml`, `justfile`): der Befehl, der Lint, Typprüfung und schnelle
   Tests verbindet, notfalls zusammengesetzt aus vorhandenen Zielen (`make lint && make
   test`). Bei Delphi wird der Build aus der `.dproj` abgeleitet und im Bericht als
   „abgeleitet" markiert; ein abgeleiteter Befehl kommt nicht in `permissions.allow`.
   Gibt es nichts, steht in der CLAUDE.md „Verifikation: keine — ungeprüft", und der
   Bericht nennt `testing-strategy`. Neue Runner-Ziele legt die Skill nicht an.
4. **apply** in einem späteren Aufruf nach Bestätigung: `apply_repo.py --plan
   .skills/cache/setup-repo/plan.md`. Verweigert wird, wenn der Hash nicht passt oder
   eine versionierte Zieldatei uncommittete Änderungen hat. Unversionierte Zieldateien
   wie `.claude/settings.local.json` bekommen vorher ein Backup unter
   `.skills/cache/setup-repo/backups/<JJJJMMTT-hhmmss>/`. Danach jeden Hook mit
   Beispiel-Payload ausführen; `verify_stop.py` läuft dabei nur mit `--selftest`, das
   prüft, ob das Programm des Verifikationsbefehls existiert, ohne ihn zu starten.
   Existiert `AGENTS.md` ohne eine der drei CLAUDE-Dateien, enthält die neue CLAUDE.md
   direkt unter der Kopfzeile `@AGENTS.md`; das Budget zählt die importierten Zeilen
   mit. `apply` schreibt in jedem Fall `.skills/cache/setup-repo/apply.md` mit Ergebnis
   oder Abbruchgrund.
5. **check.** Bestand gegen Plan; Budget; Hooks laufen; Ledger-Kopfzeile lesbar. Liest
   die Klassen aus dem letzten Plan, klassifiziert nicht neu; fehlt der Plan (frischer
   Clone, Cloud), stehen klassenabhängige Punkte als „ungeprüft — kein Plan". Schreibt
   `check.md`.

Ohne Antwort auf Rückfragen (`claude -p`) nimmt der Plan Annahmen und führt sie im
Bericht; `apply` wendet nur einen vorhandenen Plan an. `permissions.deny` für Secrets
bietet der Plan an wie Spec 21, mit demselben Hinweis, dass ein Read-Deny beliebige
Unterprozesse nicht erfasst; gesetzt wird es nur nach Bestätigung.

**Plugins je Repo.** `enabledPlugins` nach Spec 20 kommt in `.claude/settings.local.json`,
nicht in die committete Datei — die Plugins stammen aus der persönlichen Sammlung des
Nutzers und laden in der Cloud ohnehin nicht. `cc-ui` an, wenn `detect_repo.py` ein
Frontend erkennt. Ein Plugin, dessen Skills im Repo als Projekt-Kopie unter
`.claude/skills/` liegen, geht aus, damit nichts doppelt erscheint. Die Plugin-ID
(`<name>@<marketplace>` oder `<name>@synced`) liest `detect_repo.py` aus
`installed_plugins.json` und `plugins/synced/` des Config-Verzeichnisses, ohne Code aus
setup-user zu importieren. Findet es keine ID, schreibt `apply` nichts und der Bericht
sagt „ungeprüft — Plugin-ID nicht gefunden". Im Repo `cc-skills` regelt Spec 20 den
Schalter für `cc-dev` bereits in der committeten Datei; `check` meldet das nicht als
Abweichung.

**Verifikations-Hook (opt-in).** `verify_stop.py` hält das Turn-Ende an, solange der
Verifikationsbefehl rot ist, höchstens dreimal in Folge je Session (eigener Zähler im
Zustand, unabhängig von `stop_hook_active`). Danach lässt er das Ende zu und gibt
`systemMessage` „rot nach drei Versuchen" aus. Ist der Befehl nicht ausführbar
(Programm fehlt), endet er mit 0 und `systemMessage` „ungeprüft — <Werkzeug> fehlt",
etwa beim Delphi-Build auf der Linux-Devbox. Die Claude-Code-Obergrenze von acht Blocks
ohne Tool-Aufruf (hooks-guide) bleibt als zweites Netz.

**Ziele (Abschnitt C).** `docs/goals.md` hat drei Tabellen: *Aktiv* (`id`, Ziel, Fertig
wenn, Bereich, seit), *Kandidaten* (`id`, Kandidat, entdeckt bei, Grund, am), *Erledigt*
(`id`, Ziel, Beleg, am; die letzten zehn, Älteres liegt in Git). *Aktiv* plus
*Kandidaten* sind der Backlog. IDs heißen `G<n>`, mit `n` eins größer als das höchste
`n` in allen drei Tabellen; vor jedem Schreiben liest Claude die Datei neu und hängt nur
an. Beim Einrichten entsteht der Ledger leer; die Skill erfindet keine Ziele. „Fertig
wenn" folgt der `/goal`-Doku: ein messbarer Endzustand, die Prüfung, die ihn zeigt, und
was sich nicht ändern darf.

Der Bereich sind Pfad-Globs relativ zur Repo-Wurzel, getrennt durch Kommas, in einer
Zelle. Dialekt: `**` passt auf beliebig viele Ordner, `*` und `?` innerhalb eines
Pfadteils, Trenner ist immer `/`, Groß- und Kleinschreibung zählen, geschweifte Klammern
gibt es nicht. Ein Ziel mit leerem Bereich hat keinen Bereich; der Hook übergeht es.

Die Regel `.claude/rules/goals.md` gilt nur, solange *Aktiv* mindestens ein Ziel hat.
Dann ordnet sie jede während der Arbeit entdeckte Aufgabe in genau eine von vier Klassen:

1. **Vom Nutzer verlangt** — steht im aktuellen Prompt: erledigen.
2. **Teil des Ziels** — nötig, damit „Fertig wenn" eintritt: erledigen.
3. **Trivial** — in einer Datei, die die aktuelle Aufgabe ohnehin ändert, höchstens fünf
   Zeilen, keine neue öffentliche Schnittstelle, kein neuer oder geänderter Test nötig:
   erledigen und im Turn-Ende nennen. Ein kleiner Bugfix fällt darunter.
4. **Neues Ziel** — alles andere: nicht umsetzen, als Kandidat eintragen, im Turn-Ende
   nennen. Der Nutzer befördert Kandidaten nach *Aktiv*.

Ein Eintrag unter *Aktiv* entsteht nur, wenn der Nutzer etwas ausdrücklich ein Ziel
nennt; dann schlägt Claude die passende `/goal`-Zeile aus „Fertig wenn" vor. Bevor ein
Ziel nach *Erledigt* wandert, läuft der Ziel-Reviewer (Abschnitt D, sofern
eingerichtet); dann wandert es mit Beleg (Befehl und Ergebnis). Gleichzeitige Sessions
können beim Mergen von `docs/goals.md` kollidieren; Claude löst einen solchen Konflikt
nicht selbst, sondern fragt.

**Bereichs-Hook.** `goal_scope.py` macht die vierte Klasse prüfbar, soweit Dateien sie
zeigen, und läuft an zwei Ereignissen:

- **`UserPromptSubmit`:** Er hält die Basis dieses Turns fest — HEAD und für jede
  geänderte oder unversionierte Datei einen Inhalts-Hash (`git status --porcelain -z`).
  Liegt aus dem letzten Turn eine offene Meldung vor, gibt er sie als
  `hookSpecificOutput.additionalContext` aus und löscht sie.
- **`Stop`:** Er bestimmt die Dateien, die sich in diesem Turn geändert haben: alles aus
  `git diff <basis-HEAD> --name-only -z` und `git ls-files --others --exclude-standard
  -z`, dessen Inhalt nicht mehr dem Basis-Hash gleicht, plus gelöschte Dateien. So
  zählen Commits des Turns mit, und was schon vor dem Turn uncommittet war, zählt nur,
  wenn es sich weiter ändert. Pfade sind relativ zur Repo-Wurzel
  (`git rev-parse --show-toplevel`), auch wenn die Session in einem Unterordner läuft.
  Liegt eine Datei außerhalb der Bereiche aller aktiven Ziele und wurde sie in dieser
  Session noch nicht gemeldet, schreibt er eine offene Meldung in den Zustand und gibt
  `systemMessage` aus, etwa „[setup-repo] Geändert außerhalb des Bereichs von G3:
  src/dates.py. Laut Zielregel: vom Nutzer verlangt, Teil des Ziels, trivial oder ein
  Kandidat." Er hält das Turn-Ende nicht an und löst keinen Folgeturn aus.

Claude sieht die Meldung damit beim nächsten Prompt, der Nutzer sofort. Ausgenommen sind
`docs/goals.md`, `handoff.md`, `docs/debugging/`, `docs/decisions.md`,
`docs/specs/wip/`, `.claude/`, `.skills/`, `CLAUDE.md` und `.gitignore` — Artefakte der
Sammlung und der Einrichtung, die keine Zielarbeit sind. Ohne Repo-Commit, ohne
`docs/goals.md`, ohne aktives Ziel schweigt er. Fehlt die Kopfzeile des Ledgers oder ist
sie unbekannt, oder scheitert ein git-Aufruf, gibt er einmal je Session `systemMessage`
mit dem Grund aus und schweigt sonst (Konsumenten-Regel, Sichtbarkeits-Regel). Den
Zustand `.skills/cache/setup-repo/goal-scope.json` (Schlüssel `session_id`, mit `_meta`)
schreibt er atomar; ist er unlesbar, beginnt er neu. Einträge älter als sieben Tage räumt
er beim Schreiben ab. Er endet immer mit 0.

**Review (Abschnitt D).** Der Ziel-Reviewer prüft einen Diff gegen „Fertig wenn" und
„Bereich" des Ziels und gegen die Konformitäts-Prüfpunkte des erkannten Stacks, die
`apply` aus `references/review/` in `reviewer.md` schreibt (etwa: neue öffentliche
Funktion hat einen Test, neue Abhängigkeit steht im Manifest). Jeder Prüfpunkt trägt
seine Quelle; einer ohne Quelle steht als „ungeprüft" da. Jeder Befund trägt ein
Failure-Szenario. Fehler im Code selbst sucht er nicht — das ist `/code-review`,
„reviews the current diff for bugs" (best-practices). Den offenen Zuschnitt von Spec 04
berührt das nicht. Das Kontextpaket von `review-context` liest er nur, wenn der
Hauptagent es im selben Lauf erzeugt und den Pfad übergeben hat: Die Datei trägt `_meta`,
aber nur einen symbolischen Bereich wie `HEAD~1..HEAD`, keinen SHA.

### Contract

- **Belegt oder ungeprüft.** Jeder Verifikationsbefehl stammt aus vorhandenen
  Runner-Einträgen oder ist als abgeleitet markiert; jede geerntete Regel hat im Bericht
  Quelle und Klasse; ohne Beleg „ungeprüft".
- **Werkzeug vor Prosa.** Was ein schon konfigurierter Linter, Formatter oder Typprüfer
  prüft, wird keine Regelzeile — weder in Rules noch in der CLAUDE.md.
- **Budget.** Immer geladene Zeilen (CLAUDE.md samt Importen plus Rules ohne `paths`)
  ≤ 150; `plan_repo.py` meldet Überschreitung als Befund (G2).
- **AGENTS.md bleibt lesbar.** Eine neue CLAUDE.md neben `AGENTS.md` importiert es.
- **Mischen, nie überschreiben; kein Commit.** Bestehende `.claude/settings.json` wird
  gemischt wie in Spec 21; `apply` verweigert versionierte Zieldateien mit uncommitteten
  Änderungen, sichert unversionierte vorher und committet nie.
- **Sichtbar oder gar nicht.** Jede Meldung eines Stop-Hooks geht über `systemMessage`;
  nichts landet nur im Debug-Log.
- **Neue Ziele werden Kandidaten.** Die Regel verlangt die vier Klassen (G1); der Hook
  meldet Dateien außerhalb der Bereiche, hält aber nichts an und löst keinen Folgeturn
  aus.
- **Anti-Zeremonie-Fall:** `check` auf ein eingerichtetes Repo ändert nur `check.md` und
  meldet „keine Abweichung"; ein Repo ohne Tests bekommt keinen erfundenen Testbefehl; ein
  Tippfehler-Prompt erzeugt keine Ledger-Zeile (Vorlagen-Messung); ohne aktives Ziel
  schweigen Regel und Hook.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| welche Tests fehlen, Teststrategie | **testing-strategy** | setup-repo übernimmt nur vorhandene Befehle |
| Kontextpaket für einen Diff | **review-context** | setup-repo richtet nur den Ziel-Reviewer ein, der es liest |
| Fehler im Code eines Diffs finden | `/code-review` | der Ziel-Reviewer prüft Zielerfüllung, Bereich und Konformität |
| Sitzungsstand übergeben | **handoff** | `docs/goals.md` ist Zielstand über Sitzungen, `handoff.md` der Stand einer Sitzung |
| neues Feature spezifizieren | **feature-spec** | ein Ziel nennt Fertig-wenn und Bereich, keine Spec |
| eigenen User-Scope einrichten | setup-user (21) | setup-repo — was nur für mich gilt, gehört nicht ins committete Repo |

Rückverweise beim Bau, je mit dem Wort setup-repo: `handoff` nennt `docs/goals.md` unter
„Einstiegspunkte", wenn es existiert (Konsumenten-Regel, Kopfzeile lesen);
`testing-strategy`, `review-context` und `feature-spec` bekommen je einen Halbsatz in
ihrer Abgrenzung. Kein Eval-Pattern dieser vier trifft einen solchen Halbsatz (im ersten
Review geprüft), `evals_due` entsteht also nicht.

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_claude_dir_observed_except_skills_and_worktrees` | `tests/test_assertions.py`, `tests/test_workspace.py` | (A) `.claude/settings.json` im Snapshot und prüfbar; `.claude/skills/` und `.claude/worktrees/` weiter ausgenommen; Fehlertext nennt beide |
| `test_detect_python_ts_delphi_frontend_none` | `tests/test_setup_repo_detect.py` | Sprache, Frontend, Runner und Tests in Mini-Fixtures; Delphi über `.dproj`; alle drei CLAUDE-Dateien; Projekt-Skills unter `.claude/skills/` |
| `test_detect_plugin_ids` | dito | ID aus `installed_plugins.json` und aus `plugins/synced/`; keine ID → leer |
| `test_harvest_marks_tool_rules` | `tests/test_setup_repo_harvest.py` | `line-length` aus ruff-Konfiguration wird Kandidat mit Quelle; `plan_repo.py` macht bei Klasse Werkzeug keine Regelzeile daraus |
| `test_budget_counts_unscoped_rules_and_imports` | `tests/test_setup_repo_plan.py` | Rules mit `paths` zählen nicht, importiertes `AGENTS.md` zählt |
| `test_plan_hash_is_path_head_and_eol_neutral` | dito | dasselbe Repo an zwei Orten, mit verschiedenem HEAD, mit CRLF-Bestand und installierter Skill → gleicher Hash |
| `test_agents_md_is_imported` | dito | `AGENTS.md` ohne CLAUDE-Datei → Plan enthält `@AGENTS.md` unter der Kopfzeile |
| `test_apply_refuses_dirty_target_and_changed_plan` | `tests/test_setup_repo_apply.py` | uncommittete versionierte Zieldatei oder geänderter Block → Abbruch mit Grund in `apply.md`; unversionierter `.claude/skills/` stört nicht |
| `test_apply_backs_up_local_settings_and_ignores_them` | dito | vorhandene `.claude/settings.local.json` wird gesichert und gemischt; `.gitignore` bekommt die Zeile |
| `test_apply_merges_existing_settings` | dito | vorhandene `hooks.Stop` und `permissions` bleiben, Listen vereinigt |
| `test_fixture_plans_are_current` | `tests/test_setup_repo_fixtures.py` | Blöcke in `sr-planned`, `sr-aligned` und `sr-tampered` gleichen neu erzeugten, `sr-tampered` bis auf die eine absichtliche Änderung; die Bestandsdateien in `sr-aligned` gleichen den Assets |
| `test_goal_scope_turn_baseline` | `tests/test_setup_repo_goal_scope.py` | (C) vorher uncommittete, unveränderte Datei → keine Meldung; im Turn committete, gestagete, ungestagete und gelöschte Datei außerhalb → eine Meldung; Nicht-ASCII-Name; Session im Unterordner |
| `test_goal_scope_reports_each_file_once_and_defers_context` | dito | (C) dieselbe Datei im nächsten Turn → keine neue Meldung; offene Meldung erscheint beim nächsten `UserPromptSubmit` als `additionalContext` und danach nicht mehr |
| `test_goal_scope_globs` | dito | (C) `src/**`, `*` in einem Pfadteil, Groß- und Kleinschreibung, leere Bereichszelle, Komma-Liste |
| `test_goal_scope_ignores_house_artifacts` | dito | (C) nur `docs/goals.md`, `handoff.md`, `.claude/`, `.skills/`, `CLAUDE.md`, `.gitignore` geändert → keine Meldung |
| `test_goal_scope_silent_or_visible` | dito | (C) kein `docs/goals.md`, kein aktives Ziel, Repo ohne Commit → nichts; fremde Kopfzeile oder git-Fehler → einmal `systemMessage`; kaputter Zustand → Neustart |
| `test_goal_scope_output_shape` | dito | (C) Stop: nur `systemMessage`, nie `decision` oder `additionalContext`; UserPromptSubmit: `hookEventName` und `additionalContext`, Text beginnt mit `[setup-repo]`; Exit immer 0 |
| `test_verify_stop_counts_and_missing_tool` | `tests/test_setup_repo_verify_stop.py` | grün → 0; rot → 2 bis zum dritten Mal, dann 0 mit `systemMessage` „rot nach drei Versuchen"; fehlendes Programm → 0 mit `systemMessage` „ungeprüft"; `--selftest` startet den Befehl nicht |
| `test_launcher_command_runs` | dito | der Starter aus den Fragmenten läuft unter bash mit `python3` und, wenn `python3` fehlt, mit `python` |

### Evals

Voraussetzung: Abschnitt A. Ohne installierte Skill ändert ein Agent auf `/setup-repo`
nichts (für `/setup-user` im ersten Review gemessen, hier übertragen). Weil die
Plan-Ansicht aber alles beschreibt und ein hilfsbereiter Agent sie von Hand umsetzen
könnte, bindet jeder Eval an ein Artefakt, das nur die Skripte erzeugen. Vor der Abnahme
läuft jeder Eval einmal mit `--without-skill` (Spec 18). In der Tabelle steht `\|` für
ein Regex-`|`; in `evals.json` wird es ein einfaches `|`.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-check-on-aligned-repo-changes-nothing` | contract | `sr-aligned` | `file_exists` und `artifact_header` auf `.skills/cache/setup-repo/check.md`; `file_matches` dort `keine Abweichung`; `file_unchanged` einzeln auf `CLAUDE.md`, `.claude/settings.json`, `.claude/rules/goals.md`, `.claude/hooks/goal_scope.py`, `docs/goals.md`; `file_absent` `.skills/cache/setup-repo/apply.md`; `git_head_unchanged` | `check.md` mit Kopfzeile entsteht nur durch die Skill; die Fixture hat keine offenen Kandidaten, damit die Klassen des letzten Plans genügen |
| 2 | `plan-from-repo-writes-only-report` | contract | `sr-fresh` | `file_exists` `.skills/cache/setup-repo/plan.md` und `detect.json`; `file_matches` Plan auf `setup-repo-plan`, auf `Verifikation:.*make check` und auf `(?i)line.?length.{0,120}Werkzeug`; `file_absent` `CLAUDE.md` und `.claude/settings.json` | den Block und `detect.json` schreiben nur die Skripte; die Fixture trägt `line-length = 100` in `pyproject.toml`, und nur die Klassifikation der Skill schreibt „Werkzeug" in die Kandidatenzeile |
| 3 | `plan-without-tests-says-unverified` | contract | `sr-notests` | `file_matches` Plan auf `Verifikation: keine`; `file_matches` Plan auf `setup-repo-plan` | ohne Skill kein Plan; mit Skill der Wortlaut der Doktrin statt eines erfundenen Befehls |
| 4 | `apply-executes-plan-faithfully` | contract | `sr-planned` | `file_matches` `CLAUDE.md` auf `Verifikation:.*make check`; `must_not` `file_matches` `CLAUDE.md` auf `(?i)line.?length\|100 Zeichen`; `file_max_lines` `CLAUDE.md` 125; `file_matches` `.claude/settings.json` auf `make check` und auf `goal_scope`; `file_matches` `.skills/cache/setup-repo/apply.md` auf `angewendet`; `file_matches` `.gitignore` auf `settings\.local\.json`; `git_head_unchanged` | `apply.md` schreibt nur `apply_repo.py`; gemessen wird, dass der versionierte Plan treu umgesetzt wird, nicht die Klassifikation (die messen 2 und 3) |
| 5 | `apply-refuses-tampered-plan` | contract | `sr-tampered` | `file_matches` `.skills/cache/setup-repo/apply.md` auf `(?i)hash`; `file_absent` `CLAUDE.md` und `.claude/settings.json` | der Block wurde nach dem Hashen geändert; nur `apply_repo.py` prüft den Hash und schreibt den Abbruchgrund, ein Agent ohne Skill setzt den Plan um oder schweigt |

Prompts: 1 „/setup-repo check", 2 und 3 „/setup-repo", 4 und 5 „/setup-repo apply — den
Plan in .skills/cache/setup-repo/plan.md habe ich gelesen und bestätige ihn". Das Budget
in Eval 4 ist 150 minus die 25 Zeilen der Zielregel; die Fixture hat keine weitere Regel
ohne `paths` und kein `AGENTS.md`. `sr-planned` und `sr-tampered` bringen den Plan unter
`.skills/cache/setup-repo/plan.md` mit. Zielregel, Ledger und Bereichs-Hook kommen erst
mit Abschnitt C: In Abschnitt B fehlen in Eval 1 die `file_unchanged`-Assertions auf
`.claude/rules/goals.md`, `.claude/hooks/goal_scope.py` und `docs/goals.md` und in Eval 4
die Assertion auf `goal_scope`, und die Fixtures tragen diese Dateien nicht. Abschnitt C
ergänzt Fixtures, Pläne und Assertions.

### Vorlagen-Messung der Zielregel (Abschnitt C, außerhalb des Eval-Vertrags)

Ob Claude entdeckte Arbeit tatsächlich als Kandidat einträgt, misst kein Eval dieser
Skill: Rules laden beim Sessionstart, die Regel muss also schon in der Fixture liegen.
Ein solcher Lauf wäre ohne installierte Skill genauso grün und misst nach Spec 18 nichts
über die Skill — er misst die Vorlage. Deshalb liegt er in
`evals-templates/setup-repo/evals.json` mit Fixture
`evals-templates/fixtures/sr-goals-seeded/` und läuft mit `run_evals.py --evals-dir
evals-templates`, von Hand, Ergebnis als Quote im Report. Fixture: eingerichtetes Repo,
aktives Ziel „Tippfehler in greet.py beheben" mit Bereich `src/greet.py`, ein
offensichtlicher, nicht verwandter Fehler in `src/dates.py`. Zwei Fälle:

- Prompt „Behebe den Tippfehler in greet.py (Ziel G1)." — erwartet: Zeile unter
  *Kandidaten* mit `dates`, `src/dates.py` unverändert.
- Prompt „Ändere in README.md ‚Helo' zu ‚Hello'." — erwartet: keine neue Zeile unter
  *Aktiv* und *Kandidaten*; die Änderung ist vom Nutzer verlangt.

Weil der Bereichs-Hook keinen Folgeturn mehr auslöst und `-p` nur einen Turn hat,
beeinflusst er diese Läufe nicht; eine Fixture-Variante ohne Hook ist nicht nötig.

## Alternatives considered

**Ziele nur über `/goal`.** Verworfen: `/goal` endet mit einer neuen Session und mit
`/clear`, und der Evaluator liest keine Dateien.

**Ziele in `handoff.md`.** Verworfen: `handoff` schreibt die Datei jedes Mal komplett neu
und besitzt sie allein.

**Zielmanagement als eigene Skill.** Als Projekt-Skill liefe sie sogar in der Cloud.
Verworfen, weil eine Skill erst über ihre Description ausgelöst werden muss — beim
beiläufig entdeckten Nebenbefund passiert das nicht —, während eine Regel ohne `paths`
immer geladen ist. Gewinnt, wenn die Regel über 25 Zeilen wächst.

**Bereichs-Hook mit `additionalContext` am `Stop`-Ereignis.** So stand es in der ersten
Fassung. Claude sähe die Meldung sofort, aber jede Meldung hielte das Turn-Ende an und
kostete einen Modellturn, oft nur für die Antwort „war verlangt". Verworfen zugunsten der
Meldung beim nächsten Prompt. Gewinnt, wenn die Vorlagen-Messung zeigt, dass die
verzögerte Meldung zu spät kommt.

**Basis einmal je Session.** So stand es in der ersten Fassung. Verworfen, weil vorher
uncommittete Dateien, ein `git pull` und ein Resume Tage später falsche Meldungen
auslösten und Commits im ersten Turn unsichtbar blieben.

**Ein prompt-basierter Stop-Hook, der jeden Turn auf neue Ziele beurteilt.** Erkennt mehr
als Dateipfade, kostet aber je Turn einen Modellaufruf und ist stochastisch. Gewinnt, wenn
die Bereichsprüfung in der Vorlagen-Messung zu grob ist.

**Ein neues Runner-Ziel `verify` anlegen.** Ein Eingriff in `Makefile` oder
`package.json`, den der Nutzer nicht bestellt hat. Verworfen.

**Assertions auf Beobachtbares außerhalb von `.claude/` umlegen statt den Harness zu
ändern.** Dann prüfte jeder Eval einen Bericht statt das Ergebnis. Verworfen; in beiden
Reviews simuliert: Mit `(".git/", ".claude/skills/")` wird kein bestehender Test rot.

**`verify_stop.py` mit frühem Ende bei `stop_hook_active`, wie hooks-guide empfiehlt.**
Dann blockiert er nur einmal und lässt das Turn-Ende danach auch bei Rot zu. Verworfen
zugunsten eines eigenen Zählers mit drei Versuchen; gewinnt, wenn drei Folgeturns zu
teuer sind.

**`/init` statt eigener CLAUDE.md-Erzeugung.** `/init` erzeugt die CLAUDE.md; mit
`CLAUDE_CODE_NEW_INIT=1` führt es laut commands-Doku auch durch Skills, Hooks und
persönliche Memory-Dateien (im ersten Review zitiert). Es kennt weder Budget noch Ledger
noch Bereichs-Hook. Verworfen als alleiniger Weg; die Skill liest eine vorhandene
CLAUDE.md wie jede andere.

**Alles in einem Bau.** So stand es in der ersten Fassung. Verworfen, weil Harness,
Kern, Ziele und Reviewer unabhängig voneinander fertig werden und der Reviewer auf
Prüfpunkte des Nutzers wartet.

## Out of scope

GitHub-Integration (`/install-github-app`, Code Review), `.mcp.json`, LSP-Plugins, das
Schreiben von Tests (`testing-strategy`), Fehlersuche im Code (`/code-review`, Spec 04),
verschachtelte CLAUDE.md-Dateien in Monorepos, die agentische Pipeline auf der Devbox,
ein SHA im Kontextpaket von `review-context` und `docs/goals.md` als Soll-Quelle dort
(beides als Verbesserung für review-context vormerken), das Anlegen neuer
Werkzeug-Konfigurationen.

## Open questions

*Annahme:* Budget 150 immer geladene Zeilen, Zielregel ≤ 25 Zeilen, „trivial" höchstens
fünf Zeilen, *Erledigt* behält zehn, Verifikations-Hook drei Versuche, Hook-Zustand
sieben Tage — widersprich, falls nein.

*Annahme:* Claude kann `/goal` nicht selbst setzen, weil es ein eingebauter Befehl und
keine Skill ist; die Regel lässt Claude die Zeile vorschlagen. Beim Bau messen.

*Annahme:* Das Ledger-Schema bleibt stabil genug für die Devbox-Pipeline; jede
Strukturänderung zählt `schema` hoch. Die Pipeline läuft mit `-p` und bekommt dort die
`permissions.allow`-Regeln des Repos nicht; sie braucht `--allowedTools`, User-Settings
oder den dokumentierten Trust-Eintrag `projects["<path>"].hasTrustDialogAccepted`.
Läuft sie mit `--bare` — laut headless-Doku künftig Standard für `-p` —, lädt sie weder
CLAUDE.md noch Rules noch Hooks; dann wirkt setup-repo dort nicht. Mit `-p` sieht Claude
die Meldung des Bereichs-Hooks nie, weil es keinen nächsten Prompt gibt.

Der Starter im Hook-Kommando ist entschieden; ungemessen ist nur, ob der
Windows-Store-Platzhalter `python3` ihn unter Windows aushebelt. Messen auf dem
Windows-PC ist Abnahme des Baus; scheitert es, wird die Exec-Form mit `"args": []`
(hooks-guide) geprüft.

Die Harness-Änderung betrifft alle Skills: Der Judge-Prompt sieht künftig auch geänderte
Dateien unter `.claude/` außer `.claude/skills/` und `.claude/worktrees/`. Abschnitt A
fährt deshalb die Contract-Evals aller Skills einmal.

Was gehört in `references/review/delphi.md`? Der Nutzer kennt Delphi; die Prüfpunkte
sollen von ihm kommen. Abschnitt D wartet darauf.

Ungemessen bleibt, ob die Bereichsprüfung neue Ziele zuverlässig genug erkennt, und ob
die Stack-Prüfpunkte im Reviewer greifen — kein Eval und kein Test misst das; die
Vorlagen-Messung deckt nur die Zielregel.

## Next steps

Spec 20 und 21 zuerst (Plugin-Quellordner, Lint-Liste `CLAUDE_CODE_ONLY`). Dann
Abschnitt A als eigener PR mit Lauf aller Contract-Evals. Danach je Abschnitt ein Plan
mit `impl-plan` (16) und Bau nach `skill-forge` (17) Schritt 3 bis 7: B, dann C mit der
Vorlagen-Messung, dann D, sobald die Delphi-Prüfpunkte vorliegen. Den Starter auf dem
Windows-PC messen.
