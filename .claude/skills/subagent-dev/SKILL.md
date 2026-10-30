---
name: subagent-dev
description: Use when an impl-plan plan exists (or a work-plan plan for repos outside this collection) and you must decide which of its tasks can be delegated to parallel subagents. Runs plan_to_tasks.py to build a file/interface overlap matrix, gate the delegation decision mechanically (parallel only for ≥3 disjoint packages, default to sequential when in doubt), and generate a handoff Task-Datei per task instead of pasting history. Also the place for "welches Modell für welche Task" and "wann reviewen" — the script picks opus or sonnet per task from the whole plan and sets review checkpoints where an error could travel to later tasks, instead of a review after every task. Adds a mechanical `verify` step (allowlist + Produces-signature check via ast, never import) that a plain Agent dispatch does not have. Not for writing the plan itself (use impl-plan) and not for auftragslose ad-hoc delegation without a plan (use the built-in Agent tool directly, or work-plan first).
---

# subagent-dev — Gate vor Dispatch, Task-Datei statt Historie

**Delegation ist eine berechnete Entscheidung.** `plan_to_tasks.py` fällt sie
mechanisch — auch "nicht parallelisieren" ist ein Ergebnis mit Begründung,
kein Fehlschlag. Dasselbe gilt für das Modell je Task und die Review-Prüfpunkte.

## Eiserne Regel

```
KEIN DISPATCH OHNE FESTGELEGTES MODELL UND OHNE BEKANNTEN NÄCHSTEN PRÜFPUNKT —
UND KEINE TASK, DIE EINE VORLEISTUNG VERWENDET, STARTET, BEVOR DIESE DEN
ABNEHMER-CHECK BESTANDEN HAT.
```

Das verlangt diese Datei (G1); `verify` meldet den Abnehmer-Bruch (G2).

## Ablauf

1. **Plan vorhanden?** Kein Plan → `impl-plan` (Spec dieser Sammlung) oder `work-plan`
   (jedes andere Repo) zuerst. Diese Skill parst nur `### Task N:`-Blöcke mit der
   Kopfzeile eines der beiden Templates (Format aus `writing-plans` übernommen).
2. **Gate fällen und Task-Dateien erzeugen:**
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/plan_to_tasks.py" generate docs/superpowers/plans/<plan>.md
   ```
   Schreibt `.skills/cache/tasks/gate.json` (Verdikt, Begründung, je Task `model`,
   `model_reason` und `consumers`, dazu `checkpoints`) und je Task eine Handoff-Datei.
   Modell und Prüfpunkte rechnet das Skript über den ganzen Plan (Regeln M0–M3, C1–C5:
   [references/checkpoints.md](references/checkpoints.md)). Danach einmal
   `plan_to_tasks.py checkpoint init --base <commit-vor-der-ersten-Task>`. Sagt das Gate `sequential` und du verstehst nicht warum:
   `plan_to_tasks.py lint <plan>` nennt pro Task den Grund für
   `files_unknown`/`interfaces_unknown`, Prosa im Interfaces-Block, Platzhalter
   und fehlende Steps — und endet mit Exit 2, wenn der Plan gar nicht parst. `--tasks 3,4,5` beschränkt auf eine Teilmenge, z. B. die
   noch offenen Tasks eines laufenden Plans. Denselben Parser nutzt
   `plan_to_tasks.py lint-spec <spec>` für die Spec davor (Kopfzeile mit
   Review-Vermerk, Eval-Tabelle, Skill-Struktur, Abgrenzung; ab Spec 18 Exit 1 bei
   Befund, ältere melden nur) — Eigentum beim Konsumenten des Formats, Aufruf aus
   `skill-forge` Schritt 1.
3. **Verdikt lesen, nicht überstimmen:**
   - `parallel` → die genannte `parallel_group` läuft je in einem eigenen
     Git-Worktree (Isolation ist Default bei parallelen Schreibzugriffen).
   - `sequential`/`no-delegate` → ein Agent nach dem anderen, oder Hauptkontext.
     Unter drei überlappungsfreien Paketen lohnt der Dispatch-Overhead nicht.
4. **Dispatch:** Jeder Agent bekommt genau seine Task-Datei aus
   `.skills/cache/tasks/task-<N>-<slug>.md` plus Worktree und läuft mit dem `model`
   aus `gate.json` (Feld `model` des Agent-Werkzeugs) — nie mit der
   Konversationshistorie, nie mit dem ganzen Plan. Siehe
   [references/task-file.md](references/task-file.md) für das Schema.
5. **Abnahme je Task:**
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/plan_to_tasks.py" verify \
     --task-file .skills/cache/tasks/task-3-x.md --worktree <pfad> --base <commit-vor-dispatch> \
     --out .skills/cache/tasks/verify-task-3.json
   ```
   Mechanisch: Allowlist eingehalten, `Produces`-Signaturen und `consumer_check`
   (passt die Vorleistung zu dem, was ihre Abnehmer erwarten?) per `ast` (Name +
   Arity, nie Typ, nie Import); `hints` meldet Platzhalter, Debug-Ausgaben und das
   test-first-Log, ohne das Verdikt zu ändern. **Ohne `--base` bleibt das Verdikt
   höchstens `unverified`, nie `pass`.** Nach `pass` prüft ein Haiku-Agent den Vertrag
   ([references/contract-check.md](references/contract-check.md)) — das Ergebnis heißt
   „Vertrag geprüft", nie „reviewed". Fällt eins davon durch: Fix im selben Worktree,
   höchstens zwei Runden; lief die Task mit Sonnet, ein Versuch mit Opus in frischem
   Worktree; dann Eskalation an den Nutzer.
6. **Merge und Prüfpunkt:** sequenziell nach Plan-Abhängigkeit, Tests nach jedem
   Merge, dann `plan_to_tasks.py checkpoint status --after-task <N>` (bei roten
   Gesamttests nach deren Behebung mit `--tests-red`). Nur wenn `due` wahr ist, läuft
   das Review über den gemeldeten `range` — `/code-review`, solange deep-review fehlt;
   die Übergabe sagt dann „Review ohne Abdeckungsnachweis". Funde → `fix-task`, Fix in
   frischem Worktree, `verify`, Merge, Review des Fixes, dann
   `checkpoint mark --commit HEAD --run <lauf|none> --tasks <liste>`; höchstens zwei
   Fix-Runden je Prüfpunkt. Je Runde und Prüfpunkt eine Zeile über
   `plan_to_tasks.py log`. Zum Schluss der finale Prüfpunkt über `base..HEAD`.
   Ein Interface-Bruch zwischen zwei Paketen ist ein Gate-Fehler (Überlappung
   falsch beurteilt) — als Lesson im Plan vermerken, nicht einfach fixen und
   weiter. Details: [references/merge-protocol.md](references/merge-protocol.md).
7. **Recherche-/Analyse-Fan-out** (großer Codebase-Scan, der den Hauptkontext
   fluten würde) läuft unabhängig vom Gate: siehe
   [references/research-fanout.md](references/research-fanout.md). Die
   Findings-Datei enthält **nur** Fund-Zeilen (Aussage, Beleg, Konfidenz) —
   kein Vorgehensbericht, keine Wiederholung des Auftrags, keine
   Zusammenfassung der Zusammenfassung. Drei Funde sind zwölf bis fünfzehn
   Zeilen, nicht sechzig.

## Contract

- **Kein Dispatch ohne Task-Datei.** Ein Agent, der nur einen Prosa-Satz
  bekommt, ist kein delegierter Task — das ist der Fehler, den diese Skill
  beheben soll.
- **Schreiben außerhalb der Allowlist lässt die Abnahme scheitern** (G2, Spec
  00 §4: das Skript fällt das Urteil, der Aufruf bleibt freiwillig — ein Hook
  hilft hier nicht, weil Agents in eigenen Worktrees laufen).
- **Ein übersprungener Check meldet nie Erfolg.** `verify` ohne `--base`
  liefert `unverified`, nie `pass`; `check_produces` liefert `ambiguous`
  statt eines geratenen PASS, wenn mehrere gleichnamige Definitionen
  existieren und keine eindeutig zur erwarteten Signatur passt.
- **Überlappung ist konservativ:** unparsbare/leere `Files:`, eine
  Files:-Zeile mit unbekanntem Vokabular, Prosa ohne Backtick-Symbol in
  `Consumes:`/`Produces:`, ein Backtick-Ausdruck, der weder Bezeichner noch
  bekanntes Präfix ist (fail-closed), ein Interface-Symbol, das eine andere Task
  konsumiert, oder eine `file:`-Abhängigkeit auf eine Datei, die eine andere Task
  schreibt, gilt jeweils als Abhängigkeit. Drei Präfixe sind bekannt:
  `fn:parse(line)` (Aufrufbares, `verify` prüft per `ast`), `token:Next`
  (Doktrin-Token, `verify` prüft per Textsuche), `file:docs/x.md`
  (Lese-Abhängigkeit, geht in die Pfad-Überlappung, nie in Produces). Datei-Pfade werden dabei
  Groß-/Kleinschreibungs- und Backslash-normalisiert und absolut gegen
  relativ sowie Glob-Muster gegen ihre Wurzel verglichen. Im Zweifel keine
  Parallelisierung.
- **Parallel nur ab drei überlappungsfreien Paketen.**
- **Vorleistung vor Abnehmer.** `verify` meldet `missing`, `arity_mismatch` und
  `ambiguous` im `consumer_check` als `fail`; nicht prüfbare Sprachen stehen als
  `unchecked` und machen das Verdikt höchstens `unverified`.
- **Review nur am Prüfpunkt, über den Bereich seit dem letzten.** Ohne
  `review-state.json` meldet `checkpoint status` einen Prüfpunkt als fällig.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Vier Agents wirken produktiver" | Die Überlappungsmatrix entscheidet, nicht das Gefühl. |
| „Der Agent braucht mehr Kontext, ich gebe ihm die Historie" | Dann ist die Task-Datei unvollständig — Datei verbessern, nicht Kontext fluten. |
| „Sicher ist sicher, ich reviewe trotzdem nach jeder Task" | Der Prüfpunkt sieht das Zusammenspiel mehrerer Tasks, das Review je Task nicht; `checkpoint status` sagt, wann es fällig ist. |
| „Die Task ist klein, Opus schadet nicht" / „Sonnet reicht schon" | Das Modell steht mit Grund in `gate.json`. Ist es falsch, gehört die Zeile `**Modell:**` in den Plan, nicht ein Bauchgefühl in den Dispatch. |
| „Recherche mache ich schnell selbst" | Flutet das Rohmaterial den Hauptkontext, ist Fan-out billiger. |
| „Die zwei Tasks teilen sich ja nur eine Konfigdatei, das ist doch harmlos" | Genau das ist die Überlappung, die das Gate suchen soll. |
| „Ich formuliere die Interfaces um, bis das Gate `parallel` sagt" | Das Gate ist nur so hart wie die Disziplin dessen, der `Files:`/`Interfaces:` schreibt. Ein Verdikt, das durch Umformulieren kippt, ohne dass sich ein Aufgabenzuschnitt ändert, ist kein Verdikt — `lint` zeigt, was das Gate wirklich sieht; behebe das, statt es zu umgehen. |
| „Ich erkläre kurz, wie ich gesucht habe, das hilft beim Nachvollziehen" | Das Vorgehen gehört nicht in die Findings-Datei — sie ist für Ergebnisse, nicht für den Prozess. Eine Datei mit drei Funden und fünfzig Zeilen Beiwerk hat den Zweck des Fan-outs verfehlt, selbst wenn jeder Satz stimmt. |

## Abgrenzung

- **impl-plan** — erzeugt den Plan, den diese Skill konsumiert, lint-sauber.
  Kein Plan vorhanden → dort zuerst.
- **work-plan** — derselbe Plan für Repos außerhalb dieser Sammlung: Quelle Spec oder
  Auftrag, Verifikation als letzter Task. `lint` kennt beide Kopfzeilen.
- Das eingebaute **Agent**-Werkzeug — Delegation ohne Plan, ohne Gate und ohne
  `verify`. Liegt ein Plan vor und die Frage ist „parallel oder sequenziell, und was
  bekommt jeder Agent", gehört sie hierher.
- `/code-review` — das Review am Prüfpunkt, solange `deep-review` (Spec 26) nicht gebaut
  ist; subagent-dev prüft selbst nur Vertrag und Signaturen.
- test-first — Rot vor Grün je Test; subagent-dev liest dessen Log nur als Hinweis.
