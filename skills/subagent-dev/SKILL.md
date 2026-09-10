---
name: subagent-dev
description: Use when an impl-plan plan exists (or a superpowers:writing-plans plan, for repos without impl-plan) and you must decide which of its tasks can be delegated to parallel subagents. Runs plan_to_tasks.py to build a file/interface overlap matrix, gate the delegation decision mechanically (parallel only for ≥3 disjoint packages, default to sequential when in doubt), and generate a handoff Task-Datei per task instead of pasting history. Adds a mechanical `verify` step (allowlist + Produces-signature check via ast, never import) that superpowers:subagent-driven-development does not have. Not for writing the plan itself (use impl-plan) and not for auftragslose ad-hoc delegation without a plan (use superpowers:subagent-driven-development directly, or impl-plan first).
---

# subagent-dev — Gate vor Dispatch, Task-Datei statt Historie

**Delegation ist eine berechnete Entscheidung.** `plan_to_tasks.py` fällt sie
mechanisch — auch "nicht parallelisieren" ist ein Ergebnis mit Begründung,
kein Fehlschlag.

## Ablauf

1. **Plan vorhanden?** Kein Plan → `impl-plan` zuerst. Diese Skill parst nur
   `### Task N:`-Blöcke im Format des impl-plan-Templates (aus `writing-plans`
   übernommen).
2. **Gate fällen und Task-Dateien erzeugen:**
   ```bash
   python skills/subagent-dev/scripts/plan_to_tasks.py generate docs/superpowers/plans/<plan>.md
   ```
   Schreibt `.skills/cache/tasks/gate.json` (Verdikt + Begründung) und je Task
   eine Handoff-Datei. Sagt das Gate `sequential` und du verstehst nicht warum:
   `plan_to_tasks.py lint <plan>` nennt pro Task den Grund für
   `files_unknown`/`interfaces_unknown`, Prosa im Interfaces-Block, Platzhalter
   und fehlende Steps — und endet mit Exit 2, wenn der Plan gar nicht parst. `--tasks 3,4,5` beschränkt auf eine Teilmenge, z. B. die
   noch offenen Tasks eines laufenden Plans.
3. **Verdikt lesen, nicht überstimmen:**
   - `parallel` → die genannte `parallel_group` läuft je in einem eigenen
     Git-Worktree (Isolation ist Default bei parallelen Schreibzugriffen).
   - `sequential`/`no-delegate` → ein Agent nach dem anderen, oder Hauptkontext.
     Unter drei überlappungsfreien Paketen lohnt der Dispatch-Overhead nicht.
4. **Dispatch:** Jeder Agent bekommt genau seine Task-Datei aus
   `.skills/cache/tasks/task-<N>-<slug>.md` plus Worktree — nie die
   Konversationshistorie, nie den ganzen Plan. Siehe
   [references/task-file.md](references/task-file.md) für das Schema.
5. **Abnahme (zweistufig):**
   ```bash
   python skills/subagent-dev/scripts/plan_to_tasks.py verify \
     --task-file .skills/cache/tasks/task-3-x.md --worktree <pfad> --base <commit-vor-dispatch> \
     --out .skills/cache/tasks/verify-task-3.json
   ```
   Mechanisch zuerst: Allowlist eingehalten (`git diff`/`git status` gegen die
   Task-Datei) und deklarierte `Produces`-Signaturen per `ast` vorhanden
   (Name + Arity, nie Typ — Stdlib prüft keine Typen ohne Import, und
   importiert wird fremder Code hier nie). **Ohne `--base` bleibt das Verdikt
   höchstens `unverified`, nie `pass`** — ein übersprungener Check meldet nie
   Erfolg. `--out` schreibt das Ergebnis zusätzlich als Artefakt, nicht nur
   auf stdout. Erst danach `/code-review` im Selbst-Modus gegen die
   Task-Datei als Soll. Fixes im selben Worktree, max. 2 Runden, dann
   Eskalation an den Nutzer.
6. **Merge:** sequenziell nach Plan-Abhängigkeit, Tests nach jedem Merge.
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

## Kostenrichtwerte (grobe Schätzwerte, keine Telemetrie)

| Muster | Größenordnung |
| --- | --- |
| Agent-Spawn (Task-Datei + Worktree-Setup) | ~1–2k Tokens Overhead pro Task |
| Review-Pass (mechanisch + code-review) | ~1 zusätzlicher Agent-Aufruf pro Task |
| Konfliktbedingtes Serialisieren statt Parallelisieren | 0 Zusatzkosten — nur Wall-Clock |
| Übersehene Überlappung, Merge-Konflikt | ein zerstörter Arbeitsstand — teurer als jede Review-Runde |

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

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Vier Agents wirken produktiver" | Die Überlappungsmatrix entscheidet, nicht das Gefühl. |
| „Der Agent braucht mehr Kontext, ich gebe ihm die Historie" | Dann ist die Task-Datei unvollständig — Datei verbessern, nicht Kontext fluten. |
| „Review pro Task ist zu teuer" | Ein kollidierter Merge kostet mehr als alle Reviews zusammen. |
| „Recherche mache ich schnell selbst" | Flutet das Rohmaterial den Hauptkontext, ist Fan-out billiger. |
| „Die zwei Tasks teilen sich ja nur eine Konfigdatei, das ist doch harmlos" | Genau das ist die Überlappung, die das Gate suchen soll. |
| „Ich formuliere die Interfaces um, bis das Gate `parallel` sagt" | Das Gate ist nur so hart wie die Disziplin dessen, der `Files:`/`Interfaces:` schreibt. Ein Verdikt, das durch Umformulieren kippt, ohne dass sich ein Aufgabenzuschnitt ändert, ist kein Verdikt — `lint` zeigt, was das Gate wirklich sieht; behebe das, statt es zu umgehen. |
| „Ich erkläre kurz, wie ich gesucht habe, das hilft beim Nachvollziehen" | Das Vorgehen gehört nicht in die Findings-Datei — sie ist für Ergebnisse, nicht für den Prozess. Eine Datei mit drei Funden und fünfzig Zeilen Beiwerk hat den Zweck des Fan-outs verfehlt, selbst wenn jeder Satz stimmt. |

## Abgrenzung

- **impl-plan** — erzeugt den Plan, den diese Skill konsumiert, lint-sauber.
  Kein Plan vorhanden → dort zuerst. `superpowers:writing-plans` bleibt die
  Ausnahme für Repos ohne diese Sammlung.
- **superpowers:subagent-driven-development** — die 503-Zeilen-Referenz für
  den *Ablauf* (Fix-Loop, Modellwahl, Ledger). Diese Skill ersetzt sie nicht,
  sondern liefert ihr vorgeschaltet: ein mechanisches Gate statt einer
  Textempfehlung, eine generierte Task-Datei statt einer von Hand komponierten
  Dispatch-Prompt, und `verify` als mechanische Abnahme vor dem Review. Liegt
  bereits ein Plan vor und die Frage ist „parallel oder sequenziell, und was
  bekommt jeder Agent", gehört sie hierher; danach kann der eigentliche
  Dispatch-Loop `subagent-driven-development` folgen.
- **`/code-review`** — die zweite Abnahmestufe nach der mechanischen Prüfung.
