# Bericht: Skill `subagent-dev` (Spec 09)

Branch `feat/subagent-dev`, Basis `0831fb7` (`specs/skill-foundation`).
Acht Commits, `a689e5f` (Plan) bis zu diesem Bericht (`1da445e` zuletzt vor
dem Bericht). 172/172 Tests grün (`.venv/bin/pytest`). `run_evals.py` nicht
ausgeführt (Auftrag).

## Basis-Abweichung und fehlende Eingabe

Der Auftrag verlangte, vor allem anderen `git log --oneline -1` gegen
`0831fb7` zu prüfen; der tatsächliche `HEAD` dieses Worktrees war
`9d8265e` (Merge von `cad-parts-skill`). Wie im Auftrag für diesen Fall
vorgesehen: `git checkout -B feat/subagent-dev specs/skill-foundation`
ausgeführt, danach zeigte `git log --oneline -1` `0831fb7`.

`brief-common.md` (Fundament-Contract, Arbeitsweise, real aufgetretene
Fehlerklassen) existierte an keinem durchsuchten Pfad — weder im genannten
Scratchpad noch anderswo im Dateisystem. Statt zu blockieren, wurde die
Grundlage aus dem bereits gebauten Teil des Repos rekonstruiert:
`specs/Spec 00 – skill-foundation.md`, `docs/artifact-header.md`,
`docs/known-limits.md`, die gebaute Skill `skills/dev-report/` (SKILL.md,
`collect.py`, Tests, Evals) als Stilvorbild, sowie `evalkit/` direkt
gelesen (`schema.py`, `assertions.py`, `workspace.py`). Diese Quellen decken
Artefakt-Vertrag, Eval-Vertrag, Tier-Regeln und Gate-Ehrlichkeit inhaltlich
ab; was fehlt, ist nur die kuratierte Zusammenfassung selbst. Risiko: eine
Konvention, die ausschließlich in `brief-common.md` gestanden hätte und in
keinem gelesenen Artefakt sichtbar ist, könnte hier fehlen.

## Gebaute Artefakte

```
skills/subagent-dev/
├── SKILL.md                        (97 Zeilen, ≤150-Grenze eingehalten)
├── references/
│   ├── task-file.md                (Schema + Beispiel + Grenzen)
│   ├── research-fanout.md          (Rückgabe-Schema, Artefakt-Persistenz, Synthese-Disziplin)
│   └── merge-protocol.md           (Reihenfolge, Interface-Bruch als Gate-Fehler)
└── scripts/
    └── plan_to_tasks.py            (Tier 1, generate + verify)

tests/test_subagent_dev_plan_to_tasks.py   (26 Tests)

evals/subagent-dev/evals.json               (4 Evals: 3 contract, 1 behavior)
evals/fixtures/plan-hidden-overlap/         (git:true, 2 Tasks, verdeckte Config-Überlappung)
evals/fixtures/plan-mini-two-tasks/         (git:true, 2 disjunkte Tasks — Anti-Zeremonie-Fall)
evals/fixtures/plan-disjoint-batch/         (git:true, 4 disjunkte Tasks + simuliertes Dispatch-Ergebnis mit Signatur-Drift)
evals/fixtures/research-scan-target/        (git:true, 12 Dateien, 3 mit TODO(security))

docs/superpowers/plans/2026-08-17-subagent-dev.md   (Implementierungsplan, committed vor der Umsetzung)
```

## Was `plan_to_tasks.py` tut

**`generate PLAN [--tasks 1,2] [--out-dir DIR]`** parst `### Task N:`-Blöcke
im `superpowers:writing-plans`-Format (`Files:`, `Interfaces:`, Steps),
maskiert dabei Codezäune (```` ``` ````) — sonst hätte der Parser das im
eigenen Implementierungsplan zitierte Beispiel-Plan-Snippet für echte
Task-Struktur gehalten, ein Fehler, den der Smoke-Test gegen den eigenen
Plan tatsächlich aufgedeckt hat. Baut eine Überlappungsmatrix aus zwei
Signalen: Datei-/Verzeichnis-Präfix-Kollision und ein Interface-Symbol, das
eine Task konsumiert und eine andere produziert (Backtick-Erkennung,
Text-Heuristik). Ein Task ohne parsbaren `Files:`-Block gilt als
unbekannt-und-überlappt-mit-allen — konservativ nach Vorab-Entscheidung B2.
Verdikt: `parallel` nur ab drei überlappungsfreien Paketen; `sequential`,
wenn eine echte Kopplung eine Reihenfolge erzwingt, aber die Schwelle nicht
erreicht wird; `no-delegate`, wenn alle Tasks überlappungsfrei sind, aber zu
wenige, um den Dispatch-Overhead zu rechtfertigen (der Anti-Zeremonie-Fall,
Eval 2). Schreibt `.skills/cache/tasks/gate.json` (mit `_meta`-Kopf) und je
Task eine Handoff-Datei mit sechs Prosa-Sektionen plus eingebettetem
` ```json `-Block.

**`verify --task-file PATH --worktree DIR [--base REF] [--out PATH]`** ist
ein Werkzeug, das Spec 09 in der Skill-Struktur-Skizze nicht als eigenes
Skript nennt, aber im Approach-Abschnitt ausdrücklich für die "mechanische
Abnahme" fordert (Allowlist eingehalten, Produces-Signaturen vorhanden und
typkonform). Statt eines zweiten Skripts wurde es als zweites Unterkommando
desselben Tier-1-Skripts gebaut. Allowlist-Prüfung über `git diff`/`git
status` gegen die deklarierte Datei-Liste (exakt oder Verzeichnis-Präfix).
Produces-Prüfung liest den Zielcode ausschließlich per `ast.parse` — nie
`import` (Vorab-Entscheidung A3) — und vergleicht Name + Arity (Parameteranzahl,
`self`/`cls` nicht mitgezählt); Typen werden nicht geprüft, das wird als
Grenze benannt, nicht verschwiegen (`references/task-file.md`). `--out`
schreibt das Ergebnis zusätzlich als `_meta`-JSON-Artefakt, ohne das Eval 3
keine mechanische Assertion außer über Agent-Ausgabe hätte.

## Abweichungen von der Spec-Skizze

1. **Eval-Pfad:** Spec 09 skizziert `subagent-dev/evals/evals.json` innerhalb
   des Skill-Ordners. Spec 00 §2 (später ratifiziert, Widersprüche einzelner
   Specs löst sie ausdrücklich auf) legt den geteilten Baum
   `evals/<skill>/evals.json` + `evals/fixtures/` fest — so bereits umgesetzt
   für `dev-report` und `handoff`. Diesem Präzedenzfall gefolgt.
2. **`verify` als zweites Unterkommando statt zweitem Skript** — siehe oben.
3. **Gate-Verdikt in drei statt zwei Werten** (`parallel`/`sequential`/
   `no-delegate` statt nur `parallel`/`sequential`), um Eval 2 (Spec 09) und
   den Pflicht-Anti-Zeremonie-Eval (Spec 00 §2) gleichzeitig zu erfüllen:
   ein Testlauf während der Implementierung zeigte, dass zwei überlappungsfrei
   *und* zwei überlappend gekoppelte Tasks sonst identisch als "sequential"
   erschienen wären — ein Unterschied, den die Spec-Formulierung „kommt
   'nicht delegieren' mit Begründung" für den Fall ohne jede Kopplung
   ausdrücklich verlangt.

## Bekannte Grenzen

- **Interface-Überlappung ist eine Backtick-Text-Heuristik**, keine
  semantische Analyse. Ein in Prosa ohne Backticks erwähntes Symbol wird
  nicht erkannt; dann greift nur noch die Datei-Überlappung. Dokumentiert in
  `references/task-file.md`.
- **`verify` prüft Arity, nicht Typen.** Eine Signatur mit korrekter
  Parameterzahl, aber falschem Rückgabetyp, fällt nicht auf — Typprüfung
  ohne Import ist mit Stdlib-`ast` allein nicht robust genug, ein Import
  wäre die Ausnahme von A3, die diese Skill nicht macht.
- **Eval 4 (Recherche-Fan-out) ist eine `behavior`-Klasse mit Judge-Claim.**
  Die Struktur- und Inhalts-Assertions auf der Findings-Datei sind
  mechanisch, aber ob der Hauptkontext tatsächlich „schlank blieb" (keine
  Rohauszüge zitiert wurden), lässt sich laut `docs/known-limits.md`
  („Keine inhaltliche Formprüfung") nur mit einem Judge beurteilen.
- **Der `verify`-Eval (3) simuliert den zweiten Dispatch**, statt ihn
  auszulösen — der Harness kann laut `docs/known-limits.md` keinen
  verschachtelten Agenten-Dispatch fahren. Die Fixture legt das abweichende
  Ergebnis vorab an; der Eval prüft nur, dass die Skill es fängt, wenn sie
  darauf angesetzt wird, nicht, dass sie es von selbst anfordert.
- **Kostenrichtwerte in SKILL.md sind Schätzwerte**, keine Telemetrie (offene
  Frage aus Spec 09 „Kostenmodell: statische Richtwerte oder gemessene
  Werte" — hier für statische Richtwerte entschieden, mangels vorhandener
  Lauf-Historie).

## Offene Fragen aus der Spec

Beide Open Questions aus Spec 09 sind unentschieden geblieben (nicht Teil
dieses Auftrags): Worktree-Aufräum-Politik bei Eskalation (behalten zur
Diagnose vs. sofort löschen), und ob das Kostenmodell künftig aus gemessenen
Läufen statt statischer Richtwerte gespeist werden soll.

## Testergebnis

```
.venv/bin/pytest -q
........................................................................ [ 41%]
........................................................................ [ 83%]
............................                                             [100%]
172 passed in 3.28s
```

26 davon neu für diese Skill (`tests/test_subagent_dev_plan_to_tasks.py`),
146 bestehend und unverändert grün.
