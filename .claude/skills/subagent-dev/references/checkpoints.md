# Prüfpunkte, Modell je Task, Fix-Pfad

Regeln aus Spec 27, so wie `plan_to_tasks.py` sie rechnet. Das Skript fällt Modell,
Prüfpunkte und Größen-Trigger und meldet sie in `gate.json` bzw. `checkpoint.json` (G2);
Dispatch mit dem Modell, Review am Prüfpunkt und Fix verlangt die SKILL.md (G1).
Alle Regeln rechnen über den ganzen Plan, auch mit `generate --tasks` — dieselbe Task
bekommt bei jedem Aufruf dasselbe Modell, C3 nimmt das Gate-Urteil des ganzen Plans.

## Abnehmer

Abnehmer einer Task sind die **späteren** Tasks (Plan-Reihenfolge), deren `Consumes` ein
`Produces`-Symbol dieser Task nennt (`consumers_of`). Je Abnehmer `{"task", "symbols"}`;
ein Symbol trägt seine Art als Präfix: `fn:name(arity)`, wenn der Abnehmer eine Arity
erwartet, `token:Name`; ein Symbol ohne Arity steht nackt als `name`. `verify` liest die Art
aus dem Präfix; ein nackter Name ohne Arity (auch aus einer alten Task-Datei) prüft es als `fn`.

| Fall | Abnehmer? |
| --- | --- |
| Titel genau `Verifikation`, `Evals`, `Nachbarn`, `known-limits`, `Report` oder `<Titel> —…` (`MANDATORY_TITLES`) | nein — konsumiert laut Plan alles |
| „Report und Runner-CLI" (kein ` —` nach dem Wort) | ja |
| Produzent mit `interfaces_unknown` | keine erkennbaren; für ihn greifen weder M1 noch C1, nur C5 |

`verify` prüft die Symbole als `consumer_check` mit derselben Arity-Regel wie `Produces`:
passend, wenn die erwartete Arity zwischen den positionalen Pflichtparametern und allen
positionalen Parametern liegt (`self`/`cls` nicht mitgezählt); mit `*args` entfällt die
Obergrenze, die Untergrenze der Pflichtparameter bleibt. Ein kwonly-Parameter ohne Default
macht jede Arity unpassend. Ohne Python-Datei in der Allowlist steht `unchecked`, nie
`present`; Einzelheiten in `references/contract-check.md`.

## Modell je Task (M0–M3)

`choose_model` setzt `model` und `model_reason`; die erste Regel, die greift, gilt.

| # | Bedingung | Modell | `model_reason` |
| --- | --- | --- | --- |
| M0 | Zeile `**Modell:** opus` oder `**Modell:** sonnet` (ohne Groß-/Kleinschreibung) irgendwo zwischen Titel und `**Files:**` | wie angegeben | `Plan` |
| M1 | mindestens `CONSUMERS_FOR_OPUS = 2` Abnehmer | opus | `Vorleistung für Task …` |
| M2 | ein Pfad unter `Files:` enthält ein Wort aus `RISK_WORDS` oder endet auf `.sql` | opus | `Risikopfad <pfad>` |
| M3 | mindestens `BREADTH_MIN_FILES = 5` verschiedene `Create`/`Modify`-Pfade | opus | `Breite: N Dateien` |
| — | sonst | sonnet | `Standard` |

- **M0:** Die Spec sagt „direkt unter dem Titel"; das Skript nimmt die Zeile überall vor
  `**Files:**` (bzw. vor dem ersten Step) — eine Zeile in einem Step zählt nicht. Ein
  anderer Wert gilt nicht: der Lint meldet ihn, es zählen M1 bis M3.
- **M2:** `RISK_WORDS` = `auth`, `login`, `session`, `security`, `crypto`, `permission`,
  `migration`, `migrations`, `payment`, `billing`. Der Pfad wird an `/`, `_`, `-`, `.` und
  vor jedem Großbuchstaben zerlegt: `LoginForm.pas` trifft `login`, `authors.py` nichts.
- Ohne Agent-Werkzeug (claude.ai) gibt es keinen Dispatch; `model` ist dann Empfehlung.

## Prüfpunkte (C1–C5)

`place_checkpoints` schreibt `checkpoints` in `gate.json`, je Eintrag `kind`, `task`,
`profile`, `reasons`, in Plan-Reihenfolge. Die Bedingungen von M1/M2 gelten hier
unabhängig von M0.

| # | Bedingung | `kind`, `task` | `profile` |
| --- | --- | --- | --- |
| C1 | Task erfüllt M1 oder M2 und hat mindestens einen Abnehmer | `before`, erster Abnehmer | `checkpoint` |
| C2 | Task erfüllt M2 | `after`, diese Task | `standard` |
| C3 | Gate-Urteil `parallel` | `group`, höchste ID der Gruppe | `checkpoint` |
| C4 | immer | `final`, `null` — nach der letzten Task, die nicht `Verifikation` heißt | `standard` |
| C5 | zur Laufzeit: ab `SIZE_TRIGGER_LINES = 400` geänderten Zeilen seit `last_reviewed`, oder `--tests-red` | beim nächsten `checkpoint status` | `checkpoint` |

Fallen zwei Prüfpunkte auf dieselbe Stelle, bleibt einer mit allen Gründen, dem höheren
Profil (`standard` über `checkpoint`, Reihenfolge in `PROFILES`) und der Art nach `CHECKPOINT_KINDS`:
`final` > `group` > `after` > `before` (mit deren `task`). Liegt die Stelle eines
Prüfpunkts hinter der von `final` (C3 mit einer Gruppe, die die Verifikation enthält), wird er
mit `final` zusammengelegt. Die Spec nennt nur Gründe und
Profil; die Art legt das Skript fest. Anti-Zeremonie-Fall: zwei Tasks ohne Vorleistung
und ohne Risikopfad bekommen `sonnet` und nur den finalen Prüfpunkt.

## Ablauf mit `review-state.json`

Ablage unter `.skills/cache/tasks/` (Ephemera, je mit `_meta`).

| Schritt | Aufruf | Wirkung |
| --- | --- | --- |
| nach `generate` | `python plan_to_tasks.py checkpoint init --base <ref>` | `review-state.json`: `plan`, `base` = `last_reviewed` = SHA von `<ref>`, `runs: []`, `reviewed_tasks: []` |
| nach jedem Merge | `python plan_to_tasks.py checkpoint status --after-task <N> [--tests-red]` | `checkpoint.json`: `due`, `reasons`, `range`, `changed_lines`, `binary_files`, `profile`, `since_runs` |
| nach Review und Fix | `python plan_to_tasks.py checkpoint mark --commit <ref> --run <lauf> --tasks <ids>` | `last_reviewed` = SHA von `<ref>`; `<lauf>` an `runs` (`none` hängt nichts an); IDs an `reviewed_tasks` |

`status` findet die geplanten Prüfpunkte nach Task N über `plan_order` in `gate.json`
(Reihenfolge des ganzen Plans, auch bei `--tasks`), nie als ID + 1: IDs können Lücken
haben. `before M` ist fällig nach der Task, die im Plan vor M steht; `after`/`group` nach
ihrer `task`; `final` nach der letzten Nicht-Verifikations-Task. Weitere Regeln:

- `changed_lines` = hinzugefügte plus gelöschte Zeilen in `last_reviewed..HEAD`
  (`git diff --numstat`), ohne `.skills/` (das committete runlog löst nichts aus);
  Binärdateien zählen 0 und stehen in `binary_files`.
- `range` ist `last_reviewed..HEAD`, am finalen Prüfpunkt `base..HEAD` mit
  `since_runs` = alle `runs` (für deep-review `--since`, siehe unten).
- Fehlt `review-state.json`, meldet `status` den Prüfpunkt fällig mit dem Grund
  `review-state fehlt — Basis unbekannt`, ohne Bereich (E7). Fehlt `gate.json`, fällt
  `status` mit Exit 1.
- Jede Git-Ref (Branch, Tag, SHA) wird mit `git rev-parse` aufgelöst.

## Review am Prüfpunkt

**Heute (deep-review, Spec 26, pausiert):** Ist `due` wahr, läuft
`/code-review --max-findings all <range>` im Hauptkontext über den `range` aus
`checkpoint.json` — ohne den Schalter meldet `/code-review` höchstens zehn Funde, und ein
Prüfpunkt über mehrere Tasks bekäme nicht mehr Plätze als ein Review über eine: `last_reviewed..HEAD`, am finalen
Prüfpunkt `base..HEAD`. Der finale Durchgang ist der einzige, der das Zusammenspiel aller
Tasks sieht; ohne `--since` prüft er alles noch einmal, bleibt aber ein einzelnes Review
statt eines je Task. Danach
`checkpoint mark --run none`; die Übergabe sagt wörtlich:

> Review ohne Abdeckungsnachweis

**Soll:** subagent-dev schreibt die Task-Dateien des Bereichs (Tasks seit dem letzten
`mark`) in eine Datei unter `.skills/cache/tasks/` und gibt sie dem Review als Soll mit.

**Später mit deep-review:** Profil `checkpoint` als `--profile checkpoint`, Profil
`standard` als `--depth standard`, das Soll als `--soll-file`. Der finale Prüfpunkt reviewt
`base..HEAD` mit `--since` über alle Läufe aus `since_runs` und übernimmt so die Urteile
unveränderter Einheiten; neu geprüft werden der Rest und die Aufrufer über Task-Grenzen.
`mark` bekommt dann die Lauf-ID, die deep-review in seiner Übergabe nennt.

## Fix-Pfad nach einem Prüfpunkt

| Schritt | Inhalt |
| --- | --- |
| 1 | `python plan_to_tasks.py fix-task --verdicts <datei>` schreibt `.skills/cache/tasks/fix-task.md`. Eingabe: `verdicts.jsonl` (nur Status `bestätigt`/`plausibel`, `FIX_STATUSES`) oder die JSON-Liste von `/code-review` (`file`, `line`, `summary`; jeder übernommene Fund zählt). Ohne Fund fällt der Aufruf mit Exit 1. |
| 2 | Allowlist: `path` und `related` jedes Funds; Akzeptanz je Fund „behoben und mit Test belegt"; Modell: das höchste der Tasks in `gate.json`, deren `files` die Funde berühren, sonst `opus`. |
| 3 | Ein Agent arbeitet sie in einem frischen Worktree vom integrierten Stand ab; dann `verify`, Merge, Gesamttests. |
| 4 | Nachprüfung: heute `/code-review` nur über den Bereich des Fix-Commits; später deep-review `--since <lauf>` im selben Profil. |
| 5 | `checkpoint mark --commit <fix-commit> --run none --tasks <ids>` (später: Lauf-ID der Nachprüfung). |

Höchstens **zwei Fix-Runden je Prüfpunkt**, dann Eskalation an den Nutzer. Diese Grenze
verlangt die SKILL.md; anders als in E8 der Spec (`MAX_FIX_ROUNDS = 2`) steht sie nicht
als Konstante im Skript.

## runlog

`python plan_to_tasks.py log --plan <plan> (--task <N> | --checkpoint <kind>) --model <m>
--reason <grund> [--verdict <v>]… [--subagent-tokens <n>] [--findings <n>]
[--finding-task <N>]` hängt eine Zeile an `.skills/subagent-dev/runlog.jsonl` an
(committet; Zeile 1 `_meta`, nur bei neuer Datei). Je Runde und je Prüfpunkt eine Zeile.

| Schlüssel (`RUNLOG_KEYS`) | Inhalt |
| --- | --- |
| `plan`, `task` / `checkpoint` | Plan; Task der Runde oder Art des Prüfpunkts |
| `model`, `reason` | Modell und `model_reason` (bzw. Grund des Prüfpunkts) |
| `verdicts` | aus `--verdict`, mehrfach angebbar |
| `subagent_tokens` | aus der Rückmeldung des Agent-Werkzeugs; fehlt sie, `null` |
| `findings`, `finding_task` | Funde des Prüfpunkts und die Task, deren Dateien sie betreffen |

Fehlende Felder stehen als `null`. Das runlog dient dazu, die Regeln und die 400 Zeilen
über mehrere Pläne nachzujustieren; das Skript kalibriert nichts selbst.
