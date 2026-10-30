# Spec 27: subagent-dev-checkpoints — Reviews dort, wo ein Fehler wandern kann, und das Modell je Task aus dem Plan

Skill-Spezifikation · Zyklus 27 · Entscheidung: das Gate von subagent-dev legt beim Planen aus dem ganzen Plan je Task das Implementierungsmodell und die Review-Prüfpunkte fest; zwischen den Prüfpunkten prüfen `verify` (erweitert um Abnehmer-Check und Hinweise) und ein Haiku-Agent nur den Vertrag, am Prüfpunkt reviewt deep-review im Profil `checkpoint` den Bereich seit dem letzten Prüfpunkt · Abgeglichen mit Spec 00, Spec 09, Spec 24 und Spec 26 · Überarbeitet nach unabhängigem Review (2026-10-30, Opus: Pflicht- und Verifikations-Tasks zählen nicht als Abnehmer, Schnittstelle von `checkpoint` mit init/status/mark und Git-Refs, finaler Prüfpunkt über den Plan mit übernommenen Urteilen, Arity mit Default-Parametern, Nicht-Python ungeprüft, Regeln aus dem ganzen Plan trotz `--tasks`, Fix-Pfad nach einem Prüfpunkt, Lauf-ID für `--since`, Projekt-Kopie, Basislinie vor dem Bau, runlog committet mit Tokens, Fixtures mit `.gitignore` und Tags)

## Problem

subagent-dev nimmt heute jede Task zweistufig ab: `verify` mechanisch, dann
„`/code-review` im Selbst-Modus gegen die Task-Datei als Soll. Fixes im selben Worktree,
max. 2 Runden, dann Eskalation an den Nutzer" (`skills/subagent-dev/SKILL.md`, Schritt 5).
Der Nutzer arbeitet mit feature-spec, work-plan und subagent-dev und berichtet am
2026-10-30: Beim Ablauf Task, Review, Fix, nächste Task war das Review oft sehr umfangreich,
obwohl nur ein paar Zeilen geändert waren, und ging stark ins Limit. Spec 09 hatte die
Alternative schon genannt: „die gestufte Variante (Review nur für kritische Pakete) bleibt
als dokumentierter Sparmodus erwähnt". Diese Spec macht daraus den Standard.

Seltener reviewen hat einen Preis: Ein Fehler in einer Task, auf der spätere aufbauen,
wandert weiter. Welche Tasks das sind, steht im Plan in `Produces:` und `Consumes:`, die
das Gate heute nur für die Überlappung liest. Im Review simuliert über die 13 jüngeren Pläne
unter `docs/superpowers/plans/`: Prüfpunkte nach den Regeln unten ergeben 34 Prüfpunkte auf
133 Tasks, also rund jede vierte statt jeder Task.

Ob das das Limit-Problem löst, ist offen: Ein Review am Prüfpunkt deckt mehr Code ab und
kostet mehr als eines je Task. Wie viel ein Review je Task heute kostet, hat niemand
gemessen. Deshalb beginnt der Bau mit einer Basislinie (Next steps).

Das Modell je Task wählt heute niemand; jeder Dispatch läuft mit dem Modell der Sitzung.
Der Nutzer will zwischen Opus und Sonnet wechseln (2026-10-30).

## Constraints

Änderung an einer bestehenden Skill. Tier 1 bleibt: alles in `scripts/plan_to_tasks.py`,
nur Stdlib, aufgerufen über `"${CLAUDE_SKILL_DIR}/scripts/plan_to_tasks.py"` (Spec 25).
Gate-Grade: Modellwahl, Prüfpunkte, Abnehmer-Check, Hinweise und Größen-Trigger fällt das
Skript (G2); Dispatch mit dem Modell, Haiku-Vertragsprüfung, Review und Fix am Prüfpunkt
verlangt die SKILL.md (G1). Kein Hook. SKILL.md bleibt unter 150 Zeilen (heute 123); dafür
entfallen die Kostentabelle und die Anti-Rationalisierungszeile „Review pro Task ist zu
teuer", Details wandern in neue References.

Ablage (Spec 00 §1):

| Datei | Klasse | Inhalt |
| --- | --- | --- |
| `.skills/cache/tasks/gate.json` | Ephemera | wie bisher, je Task zusätzlich `model`, `model_reason`, `consumers`; dazu `checkpoints` |
| `.skills/cache/tasks/task-<N>-<slug>.md` | Ephemera | wie bisher, dazu Abschnitt Modell und Abnehmer; Maschinenblock mit `model` und `consumers` |
| `.skills/cache/tasks/review-state.json` | Ephemera | `_meta`, `plan`, `base`, `last_reviewed`, `last_run`, `reviewed_tasks` |
| `.skills/cache/tasks/checkpoint.json` | Ephemera | `_meta`, Ergebnis von `checkpoint status` |
| `.skills/cache/tasks/contract-task-<N>.md` | Ephemera | Kopfzeile, Ergebnis der Vertragsprüfung |
| `.skills/subagent-dev/runlog.jsonl` | Konfiguration, committet | erste Zeile `_meta`, dann je Runde und je Prüfpunkt eine Zeile |

Die Schlüssel in `gate.json` bleiben abwärtskompatibel; neue kommen dazu, alte ändern sich
nicht, Schema bleibt 1. Je Task stehen die Schlüssel in der Reihenfolge `id`, `title`,
`files`, `files_unknown`, `interfaces_unknown`, `model`, `model_reason`, `consumers`.

Das Review am Prüfpunkt ruft deep-review (Spec 26) im Hauptkontext auf. Fehlt deep-review,
läuft `/code-review` über denselben Bereich, und die Übergabe sagt „Review ohne
Abdeckungsnachweis". In diesem Repo lädt deep-review über die Projekt-Kopie (Spec 26).

## Approach

**Eiserne Regel:** *Kein Dispatch ohne festgelegtes Modell und ohne bekannten nächsten
Prüfpunkt — und keine Task, die eine Vorleistung verwendet, startet, bevor diese den
Abnehmer-Check bestanden hat.* Die Regel verlangt die SKILL.md (G1); `verify` meldet den
Abnehmer-Bruch (G2).

### Skill-Struktur

```
skills/subagent-dev/
├── SKILL.md                         Schritt 2 mit Modell, Prüfpunkten und checkpoint init; Schritt 4 Dispatch mit Modell; Schritt 5 verify, Vertragsprüfung, checkpoint status, Review nur am Prüfpunkt; Fix-Pfad; Eskalation zu Opus; Kostentabelle und Zeile „Review pro Task" entfallen
├── references/checkpoints.md        Regeln M0–M3 und C1–C5, Abnehmer, review-state, Aufruf von deep-review und Ersatz durch /code-review, Fix-Pfad, runlog
├── references/contract-check.md     Auftrag an den Haiku-Agenten: Steps gegen Diff, Änderungen ohne Bezug zu einem Step, Hinweise aus verify
├── references/task-file.md          Abschnitt Modell und Abnehmer; Maschinenblock mit model und consumers
├── references/merge-protocol.md     Zeile 3 „mechanisch + `/code-review`" → verify, Vertragsprüfung, Prüfpunkt; Abschluss mit finalem Prüfpunkt
└── scripts/plan_to_tasks.py         Tier 1 — generate mit model, consumers, checkpoints aus dem ganzen Plan; verify mit consumer_check und hints; neu checkpoint init/status/mark, fix-task, log

skills/work-plan/references/task-patterns.md   optionale Zeile **Modell:** unter dem Task-Titel; Abnehmer-Task beginnt mit einem Test gegen die Vorleistung
skills/impl-plan/references/task-patterns.md   dieselbe optionale Zeile
skills/test-first/SKILL.md           Abgrenzung: verify liest log.md als Hinweis (Spec 24, Out of scope, neu verhandelt)
.claude/skills/subagent-dev/, .claude/skills/impl-plan/   Projekt-Kopien über sync_skills.py
evals/subagent-dev/evals.json        fünf neue Evals, siehe unten
evals/fixtures/plan-fanout/, plan-fanout-override/, plan-fanout-dispatched/, cp-size/   je fixture.json mit "git": true
tests/test_subagent_dev_plan_to_tasks.py   neue Fälle, siehe Tests (Repo)
tests/test_skills_lint.py            Register: subagent-dev ohne anti-ceremony-eval und report-section; KNOWN_FINDINGS_MAX_PAIRS 77
docs/known-limits.md                 Abschnitt subagent-dev um Prüfpunkte und Modellwahl ergänzt
docs/superpowers/reports/subagent-dev-report.md   neuer Abschnitt mit Basislinie und „## Was nicht gemessen wurde"
```

### Abnehmer

Abnehmer einer Task sind die späteren Tasks, deren `Consumes` ein `Produces`-Symbol dieser
Task nennt (Logik von `_interface_dependency`). Nicht als Abnehmer zählen Tasks, deren Titel
mit `Verifikation`, `Evals`, `Nachbarn`, `known-limits` oder `Report` beginnt — sie
konsumieren laut work-plan bzw. impl-plan alle `Produces` und würden jede Task zur
Vorleistung machen (im Review gemessen: 56 statt 28 Treffer bei 198 Tasks). Tasks mit
`interfaces_unknown` haben keine erkennbaren Abnehmer; das Gate nennt sie in `reasoning`, für
sie greift nur der Größen-Trigger.

Alle Regeln rechnen über den ganzen Plan, auch wenn `generate --tasks` nur eine Teilmenge
ausgibt; so bekommt dieselbe Task bei jedem Aufruf dasselbe Modell.

### Modell je Task

`generate` setzt je Task `model` (`opus` oder `sonnet`) und `model_reason`. Die erste Regel,
die greift, gilt:

| # | Regel | Modell | `model_reason` |
| --- | --- | --- | --- |
| M0 | Direkt unter dem Task-Titel, vor `**Files:**`, steht eine Zeile `**Modell:** opus` oder `**Modell:** sonnet` (Wert ohne Groß-/Kleinschreibung, Zeile verankert) | wie angegeben | `Plan` |
| M1 | mindestens zwei Abnehmer | opus | `Vorleistung für Task …` |
| M2 | ein Pfad unter `Files:` enthält ein Risikowort: Pfad zerlegt an `/`, `_`, `-`, `.` und an Großbuchstaben, verglichen ohne Groß-/Kleinschreibung mit `auth`, `login`, `session`, `security`, `crypto`, `permission`, `migration`, `migrations`, `payment`, `billing`; oder er endet auf `.sql` | opus | `Risikopfad …` |
| M3 | mindestens fünf `Create`/`Modify`-Pfade | opus | `Breite: N Dateien` |
| — | sonst | sonnet | `Standard` |

`LoginForm.pas` trifft `login`, `authors.py` trifft nichts. Ein anderer Wert hinter
`**Modell:**` ist ein Lint-Befund und fällt auf M1 bis M3 zurück. Der Dispatch übergibt
`model` an das Agent-Werkzeug.

### Prüfpunkte

`generate` schreibt `checkpoints`, eine Liste aus `kind`, `task` (die Task, vor oder nach der
geprüft wird; bei `final` `null`), `profile` und `reasons`. Die Bedingungen von M1 und M2
gelten hier unabhängig von M0.

| # | Regel | Prüfpunkt | Profil |
| --- | --- | --- | --- |
| C1 | eine Task erfüllt M1 oder M2 und hat einen Abnehmer | `before` dem ersten Abnehmer | `checkpoint` |
| C2 | eine Task erfüllt M2 | `after` dieser Task | `standard` |
| C3 | das Gate-Urteil ist `parallel` | `group` nach dem Merge der Gruppe | `checkpoint` |
| C4 | immer | `final` nach der letzten Task, die keine Verifikations-Task ist | `standard` |
| C5 | zur Laufzeit: ab 400 geänderten Zeilen seit dem letzten Prüfpunkt, oder rote Gesamttests nach einem Merge (nach deren Behebung) | beim nächsten `checkpoint status` | `checkpoint` |

Fallen zwei Prüfpunkte zwischen dieselben Tasks, bleibt einer mit allen Gründen und dem
höheren Profil. Jeder Prüfpunkt reviewt den Bereich `last_reviewed..HEAD`. Der finale
Prüfpunkt reviewt `base..HEAD`, übernimmt aber mit deep-review `--since <last_run>` die
Urteile aller Einheiten, deren Paket sich seit dem letzten Prüfpunkt nicht geändert hat;
neu geprüft werden nur der Rest und die Aufrufer über Task-Grenzen.

### `checkpoint`

- `checkpoint init --base <ref>` nach `generate`: schreibt `review-state.json` mit `base` und
  `last_reviewed` = aufgelöster SHA von `<ref>` (jede Git-Ref, aufgelöst mit
  `git rev-parse`), `last_run: null`.
- `checkpoint status --after-task <N> [--tests-red]` nach jedem Merge: liest `gate.json` und
  `review-state.json`, zählt mit `git diff --numstat <last_reviewed>..HEAD` hinzugefügte plus
  gelöschte Zeilen (Binärdateien zählen 0 und stehen in `binary_files`) und schreibt
  `checkpoint.json` mit `due`, `reasons`, `range`, `changed_lines`, `profile` und `since_run`.
  Fällig ist es an einem geplanten Prüfpunkt nach Task N oder vor Task N+1, ab 400 Zeilen und
  mit `--tests-red`. Fehlt `review-state.json`, ist es fällig mit dem Grund „review-state
  fehlt — Basis unbekannt" und ohne Bereich.
- `checkpoint mark --commit <ref> --run <lauf> --tasks <liste>` nach einem Review, dessen
  Funde behoben und mit `--since` nachgeprüft sind: setzt `last_reviewed` auf den Commit nach
  dem Fix und `last_run` auf die Lauf-ID von deep-review.

### Fix-Pfad nach einem Prüfpunkt

Bringt ein Prüfpunkt Funde mit Status `bestätigt` oder `plausibel`, schreibt
`fix-task --verdicts <lauf>/verdicts.jsonl` eine Task-Datei (Allowlist: die Dateien der
Funde; Akzeptanz: je Fund behoben und mit Test belegt). Ein Agent arbeitet sie in einem
frischen Worktree vom integrierten Stand ab, mit dem höchsten Modell der betroffenen Tasks.
Danach `verify`, Merge, Gesamttests, deep-review `--since <lauf>` im selben Profil, dann
`checkpoint mark`. Höchstens zwei Fix-Runden je Prüfpunkt, dann Eskalation an den Nutzer.

### Abnehmer-Check, Hinweise und Vertragsprüfung

`generate` schreibt in den Maschinenblock jeder Task-Datei `consumers`: je Abnehmer dessen ID
und die Symbole mit der Arity, die er im `Consumes` erwartet. `verify` prüft sie gegen die
Allowlist-Dateien und schreibt `consumer_check` mit `present`, `missing`, `arity_mismatch`,
`ambiguous` oder `unchecked`:

- `fn:` in Python per `ast`: passend, wenn die erwartete Arity zwischen der Zahl der
  Pflichtparameter und der Zahl aller Parameter liegt oder `*args` vorhanden ist; ohne Arity
  im `Consumes` zählt nur die Präsenz.
- `token:` per Textsuche wie heute.
- Liegt keine Python-Datei in der Allowlist (Delphi, TS), steht `unchecked` mit Grund.
- Eine Task-Datei ohne `consumers` (vor dieser Spec erzeugt) ergibt `unchecked`, nie
  `present`.

`missing`, `arity_mismatch` und `ambiguous` machen das Verdikt `fail`.

`hints` meldet in den hinzugefügten Zeilen gegen `--base` Platzhalter (Muster des
Plan-Lints) und Debug-Ausgaben (`print(`, `console.log(`, `Writeln(`, `OutputDebugString(`),
dazu aus `.skills/cache/test-first/log.md` im Worktree Tests mit `sofort-grün` und fehlendes
Log. Hinweise ändern das Verdikt nicht. Spec 24 nannte „das Lesen des Logs durch
`subagent-dev verify`" Out of scope; hier liest `verify` es nur als Hinweis.

Nach einem `pass` prüft ein Haiku-Agent nach `references/contract-check.md` mit Task-Datei,
Diff und `verify`-Ergebnis, was das Skript nicht kann: je Step `erledigt` oder `fehlt`, und
Änderungen ohne Bezug zu einem Step. Er schreibt `contract-task-<N>.md`; das Ergebnis heißt
„Vertrag geprüft", nie „reviewed". Der Nutzer kann die Vertragsprüfung abschalten.

**Fix-Runden je Task:** Fällt `verify` oder die Vertragsprüfung durch, fixt die Task im
selben Worktree, höchstens zwei Runden. Lief sie mit Sonnet, folgt ein Versuch mit Opus in
einem frischen Worktree von derselben Basis, mit der Task-Datei und den Ergebnissen der
gescheiterten Runden; danach Eskalation an den Nutzer.

**runlog:** `plan_to_tasks.py log` schreibt je Runde und je Prüfpunkt eine Zeile nach
`.skills/subagent-dev/runlog.jsonl`: Plan, Task oder Prüfpunkt, Modell, Grund, Verdikte,
`subagent_tokens` aus der Rückmeldung des Agent-Werkzeugs, Funde je Prüfpunkt und die Task,
deren Dateien sie betreffen. Damit lassen sich die Regeln und die 400 Zeilen über mehrere
Pläne nachjustieren.

### Contract

- **Modell aus dem ganzen Plan, mit Grund.** Jede Task in `gate.json` trägt `model` und
  `model_reason`, unabhängig von `--tasks`; die Wahl fällt das Skript (G2), den Dispatch mit
  diesem Modell verlangt die SKILL.md (G1).
- **Vorleistung vor Abnehmer.** `verify` meldet einen Abnehmer-Bruch als `fail`; nicht
  prüfbare Sprachen stehen als `unchecked`, nie als `present`.
- **Review nur am Prüfpunkt, über den Bereich seit dem letzten.** Zwischen Prüfpunkten
  laufen `verify` und die Vertragsprüfung; `checkpoint status` meldet, wann ein Review fällig
  ist.
- **Vertrag ist kein Review.** `contract-task-<N>.md` und die Übergabe nennen den Schritt
  „Vertrag geprüft".
- **Ein übersprungener Check meldet nie Erfolg:** ohne `review-state.json` ist ein Prüfpunkt
  fällig; ohne `--base` bleibt `verify` `unverified`.
- **Anti-Zeremonie-Fall:** Ein Plan mit zwei Tasks ohne Vorleistung und ohne Risikopfad
  bekommt Sonnet für beide und nur den finalen Prüfpunkt.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| wann reviewt wird und mit welchem Modell eine Task gebaut wird | **subagent-dev** | deep-review — prüft, plant nicht |
| das Review am Prüfpunkt selbst | **deep-review** (26), sonst `/code-review` | subagent-dev prüft nur Vertrag und Signaturen |
| Plan schreiben, optionale Zeile `**Modell:**` setzen | **work-plan** (23), **impl-plan** (16) | subagent-dev schreibt keine Tasks oder Modellzeilen in den Plan; Lessons nach dem Merge-Protokoll wie bisher |
| Rot vor Grün je Test | **test-first** (24) | subagent-dev liest das Log nur als Hinweis |

Rückverweise beim Bau, je mit dem Wort subagent-dev: work-plan und impl-plan
(`references/task-patterns.md`), test-first (Abgrenzung); deep-review nennt subagent-dev
schon nach Spec 26.

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_consumers_exclude_mandatory_tasks` | `tests/test_subagent_dev_plan_to_tasks.py` | Verifikation, Evals, Nachbarn, known-limits, Report sind keine Abnehmer; `interfaces_unknown` hat keine |
| `test_model_rules` | dito | M0 schlägt M1 bis M3; M0 nur direkt unter dem Titel; M1 ab zwei Abnehmern; M2 trifft `auth_service.py`, `LoginForm.pas`, `x.sql`, nicht `authors.py`; M3 ab fünf Pfaden ohne `Test`-Zeilen; ungültiger Wert → Lint-Befund und Rückfall |
| `test_rules_use_whole_plan_with_tasks_filter` | dito | `--tasks 3,4` ändert weder Modell noch Abnehmer noch Prüfpunkte |
| `test_checkpoint_placement` | dito | C1 vor dem ersten Abnehmer; C2 nach Risikotask; C3 nur bei `parallel`; C4 vor der Verifikations-Task oder am Ende; Zusammenfallen mit allen Gründen und höherem Profil |
| `test_verify_consumer_check` | dito | present, missing, arity_mismatch, ambiguous; Default-Parameter und `*args` passen; Nicht-Python → unchecked; alte Task-Datei ohne `consumers` → unchecked |
| `test_verify_hints` | dito | Platzhalter und Debug-Ausgaben nur in hinzugefügten Zeilen; `sofort-grün` und fehlendes Log aus test-first; Verdikt unverändert |
| `test_checkpoint_command` | dito | init löst Tags auf; status fällig an geplantem Prüfpunkt, ab 400 Zeilen, mit `--tests-red`, sonst nicht; Binärdateien zählen 0; ohne review-state fällig ohne Bereich; mark setzt Commit und Lauf |
| `test_fix_task_from_verdicts` | dito | Allowlist aus den Dateien `bestätigt`/`plausibel`; `widerlegt` und `offen` nicht |
| `test_gate_json_keys_backward_compatible` | dito | alle bisherigen Schlüssel mit unveränderten Werten an den bestehenden Fixtures; neue Schlüssel in der festgelegten Reihenfolge |

### Evals

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-mini-plan-gets-only-final-checkpoint` | contract | `plan-mini-two-tasks` | `file_matches` `.skills/cache/tasks/gate.json` auf `"kind":\s*"final"`; must_not `file_matches` dort auf `"kind":\s*"(before\|after\|group)"` und auf `"model":\s*"opus"` | `checkpoints` und `model` schreibt nur `generate`; ohne Skill entsteht kein `gate.json` |
| 2 | `fanout-producer-gets-opus-and-checkpoint` | contract | `plan-fanout` | `file_matches` `.skills/cache/tasks/gate.json` auf `"id":\s*1,[^{}]*"model":\s*"opus",\s*"model_reason":\s*"Vorleistung` und auf `"kind":\s*"before",\s*"task":\s*3` | Task 1 liefert `parse_order`, das Task 3 und 4 verwenden; Task 2 ist unabhängig, Task 5 heißt `Verifikation`; nur M1 und C1 ergeben genau diese Einträge |
| 3 | `plan-model-line-overrides-rules` | contract | `plan-fanout-override` | `file_matches` `.skills/cache/tasks/gate.json` auf `"id":\s*1,[^{}]*"model":\s*"sonnet",\s*"model_reason":\s*"Plan"` | wie `plan-fanout`, aber Task 1 trägt unter dem Titel `**Modell:** sonnet`; ohne M0 stünde dort opus |
| 4 | `consumer-check-catches-arity-drift` | contract | `plan-fanout-dispatched` | `file_matches` `.skills/cache/tasks/verify-task-1.json` auf `"consumer_check"`, auf `"status":\s*"arity_mismatch"` und auf `"verdict":\s*"fail"` | Task 1 liefert `parse_order(line, strict)` ohne Default, Task 3 erwartet `fn:parse_order(line)`; die `Produces`-Zeile von Task 1 nennt keine Arity, der bisherige `verify` meldet `pass` (im Review mit `.gitignore` gemessen) |
| 5 | `checkpoint-due-by-size` | contract | `cp-size` | `file_matches` `.skills/cache/tasks/checkpoint.json` auf `"due":\s*true` und auf `"changed_lines":\s*430` | `review-state.json` zeigt auf den Tag `reviewed`, danach kamen genau 430 Zeilen dazu, ohne geplanten Prüfpunkt nach Task 3; nur `checkpoint status` zählt das |

In Eval 1 steht `\|` nur für die Tabelle; in `evals.json` ist es `|`. `[^{}]*` hält das
Muster in Eval 2 und 3 innerhalb des Task-Objekts.

**Fixtures:** Alle tragen eine `.gitignore` mit `.skills/cache/` und `.claude/`, sonst zählt
`check_allowlist` die installierte Skill und die Task-Dateien als Verstöße. In
`plan-fanout-dispatched` liegen Plan und `CLAUDE.md` im ersten `commits`-Eintrag mit Tag
`base`, das Ergebnis von Task 1 in einem zweiten; `verify` läuft mit `--worktree .` und
`--base base`. In `cp-size` trägt der erste `commits`-Eintrag den Tag `reviewed`, der zweite
fügt genau 430 Zeilen hinzu; `review-state.json` und `gate.json` liegen als Dateien der
Fixture unter `.skills/cache/tasks/` und nennen `reviewed` als `last_reviewed`.

Prompts: 1 „Ich habe einen Plan unter docs/superpowers/plans/mini-two-tasks.md. Nutze
subagent-dev: Gate, Modell je Task und Prüfpunkte.", 2 und 3 dasselbe für
`docs/plans/fanout.md`, 4 „Task 1 aus docs/plans/fanout.md wurde dispatcht und liegt im
letzten Commit, Basis ist der Tag base. Nutze subagent-dev und prüf Task 1 mit verify,
Ergebnis nach .skills/cache/tasks/verify-task-1.json.", 5 „Task 3 aus docs/plans/fanout.md
ist gemergt. Prüf mit subagent-dev, ob jetzt ein Review fällig ist." Vor der Abnahme läuft
jeder Eval einmal ohne Skill (Spec 18).

## Alternatives considered

**Review nach jeder Task, nur kleiner** (deep-review in Tiefe `quick` je Task). Verworfen:
Der Sockel je Subagent bleibt je Task, und die Wechselwirkung zweier Tasks sieht keines der
Einzelreviews. Gewinnt, wenn die Basislinie zeigt, dass ein `quick`-Review je Task weniger
kostet als ein Prüfpunkt je vier Tasks.

**Nur ein Review am Ende des Plans.** Verworfen: Ein Fehler in einer Vorleistung wandert
durch alle Abnehmer. Der Abnehmer-Check fängt Signaturbrüche, keine Logikfehler; dafür steht
C1 vor dem ersten Abnehmer, und der Abnehmer beginnt mit einem Test gegen die Vorleistung.

**Haiku sucht je Task Bugs.** Verworfen: Auch starke Modelle finden in Benchmarks nur einen
Teil der Fehler (Recall 7,5 % bis 49,2 % bei PR-Bots, Entelligence-Benchmark; Sonnet 4.5 als
Agent 10,1 %, AACR-Bench; Konzeptdokument zu Spec 26). Ein grünes Haiku-Review gäbe falsche
Sicherheit; Haiku prüft deshalb nur den Vertrag.

**Vertragsprüfung ganz weglassen** (Vorschlag im Review: verify reicht). Erwogen, weil
Allowlist, Signaturen, Platzhalter und test-first-Log schon das Skript prüft. Behalten auf
Wunsch des Nutzers für das, was nur ein Modell sieht (Step erledigt, Änderung ohne Bezug),
und abschaltbar; das runlog zeigt, ob sie etwas findet.

**Das Modell wählt der Hauptagent nach Gefühl.** Verworfen: nicht reproduzierbar und nicht
kalibrierbar.

**Haiku als drittes Implementierungsmodell.** Verworfen auf Wunsch des Nutzers.

## Out of scope

Das Review selbst (deep-review, Spec 26). Kosten oder Limit in Echtzeit lesen (setup-user,
Spec 21). Das Modell des Hauptagenten. Automatische Kalibrierung der Regeln aus dem runlog.
Abbruch eines Plans beim Limit — Prüfpunkte schreiben `review-state.json`, ein Lauf lässt
sich dort mit handoff unterbrechen und fortsetzen.

## Open questions

*Annahme:* Größen-Trigger bei 400 geänderten Zeilen, angelehnt an die 200 bis 400 Zeilen je
Review der Cisco/SmartBear-Studie (Herstellerstudie, nicht für Modelle gemessen) —
widersprich, falls niedriger.

*Annahme:* Risikowörter in M2, die Breite von fünf Dateien in M3 und die Titel der
Pflicht-Tasks, die nicht als Abnehmer zählen, sind gesetzt, nicht gemessen. Nebenläufigkeit
und Algorithmen mit Sonderfällen erkennt das Skript nicht; dafür gibt es die Zeile
`**Modell:**`.

*Annahme:* Nach zwei gescheiterten Runden mit Sonnet ist ein Versuch mit Opus billiger als
weitere Runden — ungemessen, das runlog misst es.

*Annahme:* Das runlog liegt committet unter `.skills/subagent-dev/`, weil es über mehrere
Pläne und Worktrees hinweg gelesen wird; Spec 00 §1 nennt dort nutzergepflegte
Konfiguration, das runlog ist maschinengeschrieben — widersprich, falls es nach `docs/`
gehört.

*Annahme:* Schema bleibt 1, weil nur Schlüssel dazukommen.

Tasks mit `interfaces_unknown` bekommen weder M1 noch C1. Im Plan zu cad-parts sind das 11
von 12 Tasks; dort trägt nur der Größen-Trigger. Ein konservativer Prüfpunkt nach jeder
solchen Task hieße Review je Task — genau das Problem dieser Spec.

Ob das Agent-Werkzeug in jeder Umgebung `model` annimmt und `subagent_tokens` zurückgibt,
ist nur in Claude Code beobachtet; ohne diese Angabe schreibt `log` die Tokens als `null`.
Ob `/code-review` als Ersatz einen Commit-Bereich annimmt, ist ungemessen.

## Next steps

Vor dem Bau: Basislinie. Drei echte Pläne des Nutzers im heutigen Ablauf, je Review die
`subagent_tokens` und die Funde notieren, im Report festhalten. *Annahme:* Abnahme, wenn die
Review-Tokens je Plan um mindestens 40 % sinken, bei mindestens gleich vielen bestätigten
Funden über alle Prüfpunkte. Danach Plan mit `impl-plan` (16) und Bau nach `skill-forge` (17)
Schritt 3 bis 7, nach dem Bau von Spec 26; bis dahin greift der Ersatz durch `/code-review`.
