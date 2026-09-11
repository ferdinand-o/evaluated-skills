---
name: impl-plan
description: "Use to write the implementation plan for a spec of this skill collection — turns a spec (Eval table, Skill-Struktur block, Abgrenzung) into a plan under docs/superpowers/plans/ that subagent-dev can read: `### Task N:` blocks with Files:, Interfaces: and checkbox steps, the four mandatory tasks with canonical titles (Evals, Nachbarn, known-limits, Report), a house header line, and a lint run before hand-off. Triggers include \"schreib den Plan\", \"Implementierungsplan zur Spec\", \"Plan für Spec NN\", \"plan the build\". Not for writing the spec itself (use brainstorming or feature-spec) and not for splitting, dispatching or verifying the plan (use subagent-dev, which consumes what this skill writes). For repositories without subagent-dev, use superpowers:writing-plans instead."
---

# impl-plan — Pläne, die ihr Konsument lesen kann

**Der Plan ist für `subagent-dev` geschrieben, nicht für den Leser.** Ein Plan, den der
Parser nicht liest, hat kein Gate, keine Task-Dateien und keine Abnahme — er ist ein
Textdokument mit Checkboxen. Gemessen: 8 von 17 Plänen dieses Repos parsen nicht.

## Eiserne Regel

```
KEIN PLAN IST FERTIG, SOLANGE `lint` EINEN BEFUND MELDET
ODER NICHT GELAUFEN IST, OHNE DASS DAS GESAGT WURDE.
```

Das ist G1 — diese Datei verlangt es. Zähne bekommt die Regel von
`tests/test_plans_lint.py`: Jeder Plan außerhalb der Legacy-Menge, der Befunde trägt,
macht die Testsuite rot. Das ist G2 — ein Skript meldet, sobald jemand `pytest` fährt.

## Ablauf

1. **Spec lesen.** Eingaben sind die Eval-Tabelle (jede ID bekommt einen Task, der sie
   erzeugt), der Skill-Struktur-Block (jede Datei einen Task oder Teil eines Tasks) und
   die Abgrenzung (der Nachbarn-Task).
2. **Template kopieren:** `assets/plan-template.md` nach
   `docs/superpowers/plans/<datum>-<skill>.md`. Die Kopfzeile bleibt wörtlich; `Spec:`
   zeigt auf die eigene Spec. Im Anti-Zeremonie-Fall entfällt der Skill-Struktur-Block,
   von den Global Constraints bleiben nur die betroffenen (`task-patterns.md`).
3. **Tasks schneiden** nach `references/task-patterns.md`: Code-Task oder Doktrin-Task,
   Zuschnittsregel („teile nur, wo ein Reviewer die eine Task ablehnen und die
   Nachbar-Task annehmen könnte"), bei Tier 0 der Eval-Task **vor** der SKILL.md. Die
   vier Pflicht-Tasks behalten ihre kanonischen Titel: `Evals`, `Nachbarn`,
   `known-limits`, `Report` — oder im Anti-Zeremonie-Fall ein Sammel-Task `Pflicht`.
4. **Interfaces** mit dem Vokabular aus `task-patterns.md`: `fn:`, `token:`, `file:`,
   oder nackte Bezeichner. Kein `…` in einem Symbol, keine Prosa zwischen `Interfaces:`
   und Step 1.
5. **Lint:**
   ```bash
   python skills/subagent-dev/scripts/plan_to_tasks.py lint <plan> --skill <skill> --out .skills/cache/tasks/lint.json
   ```
   Befunde beheben — nicht umformulieren, bis das Gate `parallel` sagt. Ist die Spec
   noch ohne Eval-Tabelle, meldet der Lint das als Hinweis und prüft Coverage nicht.
6. **Selbst-Review-Trio**, dann Übergabe: „Plan liegt unter …, Lint sauber, weiter mit
   `subagent-dev`." Für einen fremden Blick: `references/reviewer-prompt.md`.

**Ohne `subagent-dev`s Skript** (claude.ai, Cowork, fremder Checkout) entfällt
Schritt 5. Dann bleibt das Selbst-Review-Trio, und die Übergabe lautet: „Plan liegt
unter …, **ungeprüft** — Lint nicht verfügbar." Nie stillschweigend als fertig melden.

## Selbst-Review-Trio

Vor der Übergabe, ohne Subagent, mit frischem Blick auf die Spec:

1. **Spec-Coverage:** Jede Anforderung, jede Eval-ID — zeig auf den Task. Lücke → Task
   ergänzen, nicht notieren.
2. **Platzhalter-Scan:** `TBD`, `TODO`, „später", „ähnlich wie Task N", Steps ohne
   Handlung. Der Lint findet die Wörter; die Formulierungen findest du.
3. **Typkonsistenz:** Ein Symbol, das Task 2 in `Produces:` führt, heißt in Task 5
   `Consumes:` genauso. `clearLayers` hier und `clearFullLayers` dort ist ein Fehler,
   kein Stil.

## Contract

- **Kopfzeile** ist die erste nicht-leere Zeile, wörtlich aus dem Template. Sie ist das
  Artefakt, an dem Evals und Repo-Test diese Skill erkennen.
- **Pflicht-Tasks** tragen ihre kanonischen Titel wörtlich. Im Anti-Zeremonie-Fall
  `Pflicht` mit je einer Zeile — nicht null.
- **Ein Symbol ist ein Bezeichner** oder trägt ein bekanntes Präfix. Alles andere macht
  die Task für das Gate unbekannt und serialisiert den Bau.
- **Ein Step ist eine Handlung** mit beobachtbarem Ergebnis. Fünf Steps im Code-Task,
  weil der Zyklus fünf Zustände hat — nicht, weil ein Step fünf Minuten dauern soll.
- **Frontmatter:** nur `name`/`description`, portabel über Agenten hinweg.
- **Tier 1 ohne eigenes Skript.** Der Lint gehört `subagent-dev`; diese Skill ruft ihn
  auf und besitzt ihn nicht. Jede Format-Erweiterung ist dort zu bauen und zu testen.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Der Lint ist hier nicht verfügbar, dann ist der Plan eben fertig" | Dann ist er *ungeprüft*, und das steht in der Übergabe. Fertig ohne Lint gibt es nicht. |
| „Ich formuliere die Interfaces um, bis das Gate `parallel` sagt" | `lint` zeigt, was das Gate sieht. Behebe das. Ein Verdikt, das durch Umformulieren kippt, ist kein Verdikt. |
| „Für diesen Doktrin-Task passt der Fünfschritt nicht, ich lasse die Steps weg" | Dann das Doktrin-Muster: Datei → Lint oder Schema-Test → Commit. Steps ohne Format sind für das Gate unsichtbar. |
| „Die Pflicht-Tasks sind bei dieser kleinen Änderung Zeremonie" | Dann ein Sammel-Task `Pflicht` mit je einer Zeile. „Nachbarn: keine" kostet nichts; ein vergessener Nachbar kostet einen Fix-Zyklus. |
| „Spec-Coverage prüfe ich im Kopf" | Der Lint prüft sie in einer Sekunde gegen die `Spec:`-Zeile und hat im eigenen Bau-Plan dieser Skill sofort fünf fehlende IDs gefunden. `coverage.status` in `lint.json` sagt, ob der Abgleich lief. |
| „Die Skill war beim Schreiben nicht geladen, das Format ist trotzdem okay" | Der Repo-Test entscheidet, nicht das Gefühl. |
| „Ich schreibe `…` ins Symbol, das ist ja nur ein Beispiel" | Ein Symbol mit `…` ist kein Bezeichner — die Task wird unbekannt. Beispielnamen statt Auslassung. |

## Abgrenzung

- **brainstorming**, **feature-spec** — schreiben die Spec, die hier Eingabe ist.
- **subagent-dev** — zerlegt den Plan, fällt das Gate, dispatcht, nimmt ab. Besitzt den
  Parser und den Lint, die diese Skill aufruft.
- **superpowers:writing-plans** — für Repos ohne `subagent-dev`. Sein Kopf
  (`REQUIRED SUB-SKILL: subagent-driven-development`) ist hier falsch.
- **skill-forge** (Spec 17) — baut eine Skill Ende-zu-Ende und konsumiert
  diese Skill für den Plan-Schritt.
