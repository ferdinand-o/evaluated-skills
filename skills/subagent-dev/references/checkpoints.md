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
Profil (`standard` geht vor `checkpoint`) und der Art nach `CHECKPOINT_KINDS`:
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
| nach Review und Fix | `python plan_to_tasks.py checkpoint mark --commit <ref> --run <lauf> --tasks <ids>` (je Lauf ein Aufruf, siehe Fix-Pfad) | `last_reviewed` = SHA von `<ref>`; `<lauf>` an `runs` (`none` hängt nichts an); IDs an `reviewed_tasks` |

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

Ist `due` wahr, reviewt **deep-review** (Spec 26) im Hauptkontext den `range` aus
`checkpoint.json` in Paketen mit Nachweis je Paket: `last_reviewed..HEAD`, am finalen
Prüfpunkt `base..HEAD`. Die Schalter für den Plan von deep-review kommen aus
`checkpoint.json`:

| Schalter | Quelle | Wert |
| --- | --- | --- |
| `--range` | `range` | Bereich seit dem letzten `mark` |
| `--profile checkpoint` oder `--profile standard` | `profile` | wie gemeldet; Fokus bleibt `bugs` |
| `--soll-file <datei>` | subagent-dev | nur und immer im Profil `checkpoint` (deep-review lehnt es sonst ab). Eine Regel: Das Soll sind die Task-Dateien des Bereichs (Tasks seit dem letzten `mark`), geschrieben nach `.skills/cache/tasks/soll-<prüfpunkt>.md` (`<prüfpunkt>` wie im runlog, etwa `before-5` oder `final`). Bei der Nachprüfung einer Fix-Runde kommt `fix-task.md` dieser Runde dazu, und zwar als ihre Kopie `.skills/cache/tasks/fix-task-<prüfpunkt>-<runde>.md` (Fix-Pfad, Schritt 1), denn `fix-task` überschreibt `fix-task.md` jede Runde, und `_meta.soll_file` hält nur den Pfad: Task-Dateien und Kopie gehen zusammen als `soll-<prüfpunkt>-<runde>.md` an deep-review. Im Profil `standard` ist das Soll die Commit-Messages des Bereichs |
| `--since <lauf>[,<lauf>…]` | `since_runs` | am finalen Prüfpunkt alle Läufe aus `runs`; bei der Nachprüfung eines Fixes der Lauf des Prüfpunkts (Fix-Pfad, Schritt 4); sonst weglassen |

- **`--since` wirkt je Datei.** Eine Datei übernimmt die Funde eines früheren Laufs, wenn ihr
  Datei-Schlüssel (Inhalt am ZIEL und Gegenstellen-Zeilen ihrer geänderten Stellen) gleich
  ist und sich die Abdeckungskette bis zur neuen Basis schließt. Neu reviewt werden die
  übrigen Dateien und die Aufrufer, deren Gegenstellen sich geändert haben.
- **Das Profil ist das aus `checkpoint.json`**, nicht das einer Zeile der Tabelle oben:
  Fallen Gründe zusammen (C1–C4, C5, rote Gesamttests), meldet `status` das höhere:
  `standard` geht vor `checkpoint`. Meldet es `checkpoint`,
  gehört `--soll-file` dazu. Der finale Prüfpunkt meldet so immer `standard`, auch wenn C5
  oder rote Gesamttests auf ihn fallen — dann `--profile standard`, ohne `--soll-file`.
- **Übernommen wird nach Profil und Fokus** (deep-review, `SINCE_PROFILES`): Beide Profile
  reviewen denselben Bereich, `checkpoint` mit den Task-Dateien statt der Commit-Messages
  als Soll, einem Soll mindestens so genau. Also übernimmt ein `standard`-Lauf aus
  `standard`- und `checkpoint`-Läufen, ein `checkpoint`-Lauf nur aus `checkpoint`-Läufen (ein
  `standard`-Lauf hatte nur die Commit-Messages); der Fokus muss gleich sein, andere Läufe übergeht
  deep-review still. Der finale Prüfpunkt übernimmt so aus allen Läufen in `runs`, auch aus
  den Zwischen-Prüfpunkten im Profil `checkpoint` und deren Nachprüfungen.
- **Übernommene Funde können schon behoben sein.** Wurde ein Fund in `a.py` in der
  aufgerufenen `b.py` behoben, ohne die Gegenstellen-Zeilen von `a.py` zu ändern, bleibt der
  Schlüssel von `a.py` gleich, und `--since` bringt den alten Fund zurück. Vor einer
  Fix-Runde am finalen Prüfpunkt gleicht der Hauptagent die übernommenen Funde mit den
  Fix-Runden der Läufe in `since_runs` ab: `sources[].reused_from` in `findings.json` nennt
  je Fund den Lauf, der ihn gemeldet hat. Nennt die Kopie `fix-task-<prüfpunkt>-<runde>.md`
  der Runde, die die Funde dieses Laufs bearbeitet hat, den Fund (gleiche Datei und
  `summary`, die Zeile kann sich verschoben haben) und ist der Fix gemergt, lässt er ihn nur
  aus der Eingabe des nächsten `fix-task` weg: Er schreibt eine gekürzte Kopie von
  `findings.json` ohne diese Funde nach `.skills/cache/tasks/findings-<prüfpunkt>-<runde>.json`
  (`<runde>` die Runde, die sie bearbeitet) und gibt sie an `fix-task`; das `findings.json`
  des Laufs ändert er nicht. Im Lauf von deep-review bleibt
  der Fund in `findings.json` und im Bericht, sonst meldet `audit` `lost_findings` oder
  `report_mismatch`; der Bericht darf ihn mit „laut fix-task-<prüfpunkt>-<runde> behoben“
  kennzeichnen. Nur die übrigen gehen in den Fix-Pfad.
- **Keine Grenze von Verifikationen.** deep-review vereinigt die Funde aller Pakete in
  `.skills/cache/deep-review/<lauf>/findings.json`, ohne abzustimmen und ohne Status
  `offen`; jeder Fund außer einem widerlegten geht in den Fix-Pfad.
- **Prüfen vor dem Bericht** (Profil `checkpoint` oder `--verify`): nach `merge` erst
  `verify --run <lauf>`, je Auftrag ein Prüfer (Sonnet), der den Schlüssel des Funds aus dem
  Auftrag im Objekt zurückgibt (`{"key", "urteil", "beleg"}`; das Urteil hängt am Schlüssel,
  nicht an der Nummer), `verdict --run <lauf> <datei>`, dann erneut `merge`; danach `report` und
  `audit`. Fehlt einem Auftrag das Urteil, meldet `audit` `unverified`, und der Lauf ist
  unvollständig.
- **Übergabe:** deep-review nennt Lauf-ID, Bericht, Zahl der Funde und Abdeckung. Sagt sie
  „unvollständig", fehlen Pakete: den Lauf mit seinen Befehlen und `--run <lauf>` fortsetzen,
  nie mit einem zweiten `plan` über denselben Bereich (das gäbe einen zweiten Lauf). Erst
  dann `mark`. Ohne Funde folgt `checkpoint mark --commit HEAD --run <lauf> --tasks <ids>`,
  sonst der Fix-Pfad (dort auch das `mark`).

**Ersatz ohne deep-review** (Repo ohne die Skill): `/code-review --max-findings all <range>`
im Hauptkontext, das Soll als Kontext dazu. Ohne den Schalter meldet `/code-review` höchstens
zehn Funde, und ein Prüfpunkt über mehrere Tasks bekäme nicht mehr Plätze als ein Review
über eine. Der finale Durchgang prüft ohne `--since` alles noch einmal, bleibt aber ein
einzelnes Review statt eines je Task. Danach `checkpoint mark --run none`; die Übergabe
sagt wörtlich:

> Review ohne Abdeckungsnachweis

## Fix-Pfad nach einem Prüfpunkt

| Schritt | Inhalt |
| --- | --- |
| 1 | `python plan_to_tasks.py fix-task --verdicts <datei>` schreibt `.skills/cache/tasks/fix-task.md`. Eingabe: `findings.json` von deep-review (nach `merge`, Objekt mit `_meta` und `findings`; jeder Fund zählt, ein Paket-Ergebnis `results/<id>.json` wird abgewiesen), die JSON-Liste von `/code-review` (`file`, `line`, `summary`; jeder übernommene Fund zählt) oder `verdicts.jsonl` (nur Status `bestätigt`/`plausibel`, `FIX_STATUSES`). Ohne Fund fällt der Aufruf mit Exit 1. Danach `fix-task.md` nach `.skills/cache/tasks/fix-task-<prüfpunkt>-<runde>.md` kopieren: Die nächste Runde überschreibt sie, Schritt 4 und der finale Prüfpunkt gleichen mit der Kopie ab. |
| 2 | Allowlist: `path` und `related` jedes Funds (aus `findings.json` und der `/code-review`-Liste nur `file`); Akzeptanz je Fund „behoben und mit Test belegt"; Modell: das höchste der Tasks in `gate.json`, deren `files` die Funde berühren, sonst `opus`. |
| 3 | Ein Agent arbeitet sie in einem frischen Worktree vom integrierten Stand ab; dann `verify`, Merge, Gesamttests. |
| 4 | Nachprüfung: deep-review über `<prüfpunkt-basis>..HEAD` im selben Profil (Soll nach der Zeile `--soll-file` oben) mit `--since <lauf des Prüfpunkts>`, ab der zweiten Runde dazu die Läufe der Nachprüfungen davor. Vor dem Fix den `range` aus `checkpoint status` notieren, er lautet `<prüfpunkt-basis>..<vor-fix>`: `<vor-fix>` ist das ZIEL des reviewten Bereichs. Neu reviewt wird, was der Fix geändert hat, samt den Aufrufern, deren Gegenstellen sich dabei geändert haben (ein Fund in `a.py`, behoben in der aufgerufenen `b.py`: `a.py` steht wieder im Plan, wenn sich ihr Schlüssel geändert hat); der Rest kommt mit seinen Funden aus dem Lauf des Prüfpunkts. Darunter können schon behobene sein: Einen übernommenen Fund, den `fix-task-<prüfpunkt>-<runde>.md` einer Runde dieses Prüfpunkts nennt (gleiche Datei und `summary`, die Zeile kann sich verschoben haben), lässt der Hauptagent nur aus der Eingabe des nächsten `fix-task` weg; in `findings.json` und im Bericht bleibt er (sonst meldet `audit` `lost_findings` oder `report_mismatch`), und der Bericht darf ihn „laut fix-task-<prüfpunkt>-<runde> behoben“ nennen. Bleiben andere Funde, ist das die nächste Runde ab Schritt 1 mit einer gekürzten Kopie der `findings.json` ohne die schon behobenen, die der Hauptagent nach `.skills/cache/tasks/findings-<prüfpunkt>-<runde>.json` schreibt; das `findings.json` des Laufs ändert er nicht. Ein Fix nur an Tests oder Doku ändert keinen Schlüssel: `plan` übernimmt dann alle Dateien („Pakete: keine — alle Dateien übernommen“), und der Lauf zählt in Schritt 5 wie jeder. Lehnt `plan` mit „nichts zu reviewen“ ab (keine reviewbare Datei im Bereich), gibt es keinen Lauf der Nachprüfung: in Schritt 5 `--run none` für sie, und die Übergabe sagt es. Ohne deep-review `/code-review` nur über die Fix-Commits, `<vor-fix>..HEAD`. |
| 5 | `checkpoint mark` je Lauf, in dieser Reihenfolge, damit `runs` den ganzen Bereich deckt (der finale Prüfpunkt braucht beide für die Abdeckungskette): `--commit <vor-fix> --run <lauf des Prüfpunkts>`, dann je Nachprüfung `--commit <ihr Ende> --run <ihr lauf>` (ohne Lauf `--run none`), jeweils mit `--tasks <ids>`. Ohne deep-review einmal `--commit HEAD --run none`. |

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
