---
name: subagent-dev
description: Use when a superpowers:writing-plans plan exists and you must decide which of its tasks can be delegated to parallel subagents. Runs plan_to_tasks.py to build a file/interface overlap matrix, gate the delegation decision mechanically (parallel only for ≥3 disjoint packages, default to sequential when in doubt), and generate a handoff Task-Datei per task instead of pasting history. Adds a mechanical `verify` step (allowlist + Produces-signature check via ast, never import) that superpowers:subagent-driven-development does not have. Not for writing the plan itself (use superpowers:writing-plans) and not for auftragslose ad-hoc delegation without a plan (use superpowers:subagent-driven-development directly, or writing-plans first).
---

# subagent-dev — Gate vor Dispatch, Task-Datei statt Historie

**Delegation ist eine berechnete Entscheidung.** `plan_to_tasks.py` fällt sie
mechanisch — auch "nicht parallelisieren" ist ein Ergebnis mit Begründung,
kein Fehlschlag.

## Ablauf

1. **Plan vorhanden?** Kein Plan → `superpowers:writing-plans` zuerst. Diese
   Skill parst nur `### Task N:`-Blöcke im `writing-plans`-Format.
2. **Gate fällen und Task-Dateien erzeugen:**
   ```bash
   python skills/subagent-dev/scripts/plan_to_tasks.py generate docs/superpowers/plans/<plan>.md
   ```
   Schreibt `.skills/cache/tasks/gate.json` (Verdikt + Begründung) und je Task
   eine Handoff-Datei. `--tasks 3,4,5` beschränkt auf eine Teilmenge, z. B. die
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
     --task-file .skills/cache/tasks/task-3-x.md --worktree <pfad> --base <commit-vor-dispatch>
   ```
   Mechanisch zuerst: Allowlist eingehalten (`git diff`/`git status` gegen die
   Task-Datei) und deklarierte `Produces`-Signaturen per `ast` vorhanden
   (Name + Arity, nie Typ — Stdlib prüft keine Typen ohne Import, und
   importiert wird fremder Code hier nie). Erst danach `/code-review` im
   Selbst-Modus gegen die Task-Datei als Soll. Fixes im selben Worktree,
   max. 2 Runden, dann Eskalation an den Nutzer.
6. **Merge:** sequenziell nach Plan-Abhängigkeit, Tests nach jedem Merge.
   Ein Interface-Bruch zwischen zwei Paketen ist ein Gate-Fehler (Überlappung
   falsch beurteilt) — als Lesson im Plan vermerken, nicht einfach fixen und
   weiter. Details: [references/merge-protocol.md](references/merge-protocol.md).
7. **Recherche-/Analyse-Fan-out** (großer Codebase-Scan, der den Hauptkontext
   fluten würde) läuft unabhängig vom Gate: siehe
   [references/research-fanout.md](references/research-fanout.md).

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
- **Überlappung ist konservativ:** unparsbare/leere `Files:`, oder ein
  Interface-Symbol, das eine andere Task konsumiert, gilt als Abhängigkeit.
  Im Zweifel keine Parallelisierung.
- **Parallel nur ab drei überlappungsfreien Paketen.**

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Vier Agents wirken produktiver" | Die Überlappungsmatrix entscheidet, nicht das Gefühl. |
| „Der Agent braucht mehr Kontext, ich gebe ihm die Historie" | Dann ist die Task-Datei unvollständig — Datei verbessern, nicht Kontext fluten. |
| „Review pro Task ist zu teuer" | Ein kollidierter Merge kostet mehr als alle Reviews zusammen. |
| „Recherche mache ich schnell selbst" | Flutet das Rohmaterial den Hauptkontext, ist Fan-out billiger. |
| „Die zwei Tasks teilen sich ja nur eine Konfigdatei, das ist doch harmlos" | Genau das ist die Überlappung, die das Gate suchen soll. |

## Abgrenzung

- **superpowers:writing-plans** — erzeugt den Plan, den diese Skill konsumiert.
  Kein Plan vorhanden → dort zuerst.
- **superpowers:subagent-driven-development** — die 503-Zeilen-Referenz für
  den *Ablauf* (Fix-Loop, Modellwahl, Ledger). Diese Skill ersetzt sie nicht,
  sondern liefert ihr vorgeschaltet: ein mechanisches Gate statt einer
  Textempfehlung, eine generierte Task-Datei statt einer von Hand komponierten
  Dispatch-Prompt, und `verify` als mechanische Abnahme vor dem Review. Liegt
  bereits ein Plan vor und die Frage ist „parallel oder sequenziell, und was
  bekommt jeder Agent", gehört sie hierher; danach kann der eigentliche
  Dispatch-Loop `subagent-driven-development` folgen.
- **`/code-review`** — die zweite Abnahmestufe nach der mechanischen Prüfung.
