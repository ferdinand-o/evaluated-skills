---
name: work-plan
description: "Use to write an implementation plan for work in any repository — a feature-spec draft, an architecture-map or rest-api-architect finding, an issue or the user's own words become a plan under docs/plans/ that subagent-dev can read: `### Task N:` blocks with Files:, Interfaces: and checkbox steps, a final task titled Verifikation with the repo's own check command, and a lint run before hand-off. Below the threshold (at most two files, no new public interface, no ordering) the answer is \"Kein Plan nötig\" and no file. Triggers include \"schreib einen Plan\", \"Implementierungsplan\", \"plan the work\", \"wie gehen wir das an\". Not for plans to a spec of this skill collection (use impl-plan, which adds the collection's mandatory tasks), not for writing the spec (use feature-spec), not for dispatching the plan (use subagent-dev), and not for a plan that only lives in the conversation (use the built-in plan mode)."
---

# work-plan — ein Plan für fremde Repos, den subagent-dev lesen kann

**Der Plan ist für `subagent-dev` geschrieben, und er endet mit dem Befehl, der ihn
abnimmt.** Ein Plan ohne Verifikation ist eine Absichtserklärung; ein Plan, den der Parser
nicht liest, hat kein Gate.

## Eiserne Regel

```
KEIN PLAN OHNE VERIFIKATIONS-TASK UND OHNE LINT-LAUF —
ODER OHNE DEN AUSDRÜCKLICHEN VERMERK „UNGEPRÜFT";
UND KEIN PLAN FÜR EINE ÄNDERUNG, DIE KEINEN BRAUCHT.
```

Den Plan zeigen ist G1 — diese Datei verlangt es. Der Lint ist G2 — ein Skript meldet.

## Ablauf

1. **Anlass prüfen.** Ein Plan lohnt sich, wenn mindestens eines gilt: die Arbeit berührt
   mehr als zwei Dateien, sie schafft eine neue öffentliche Schnittstelle, oder ihre
   Schritte hängen in einer Reihenfolge voneinander ab. Gilt nichts davon: „Kein Plan
   nötig", dazu der direkte Weg in zwei, drei Sätzen — und keine Datei.
2. **Quelle festhalten.** Liegt ein feature-spec-Entwurf vor (`docs/specs/wip/…`,
   Kopfzeile `skill: feature-spec`), zeigt `**Spec:**` darauf. Sonst steht unter
   `**Auftrag:**` der Wortlaut des Nutzers, ein Issue-Link oder der Pfad eines Befunds —
   `ARCHITECTURE.md` von architecture-map, ein Brownfield-Bericht von rest-api-architect.
   Genau eine Quelle. Was du dafür annimmst, steht in `- Annahme:`-Zeilen, sonst
   `- Annahme: keine`. Keine erfundenen Anforderungen.
3. **Repo lesen.** Der Verifikationsbefehl kommt aus der CLAUDE.md-Zeile `Verifikation:`
   (setup-repo), sonst aus `Makefile`, `package.json` oder `pyproject.toml`. Fehlt er:
   „Verifikation: keine — ungeprüft". Pfade, Module und Tests stammen aus dem Repo, nicht
   aus der Erinnerung.
4. **Tasks schneiden** nach `references/task-patterns.md`: Code-Task mit fünf Steps
   (Test schreiben, Rot sehen, Implementieren, Grün sehen, Commit), Doku- oder
   Konfig-Task mit drei Steps. Teile nur, wo ein Reviewer die eine Task ablehnen und die
   Nachbar-Task annehmen könnte. Bei einer feature-spec-Quelle zitiert jeder Titel eines
   Akzeptanzkriteriums (`### …` unter `## Akzeptanzkriterien`) wörtlich in einem Task.
5. **Verifikations-Task als letzter Task**, Titel wörtlich `Verifikation`: `- Test:` mit
   der Datei, die den Befehl definiert; `Consumes:` gleich allen `Produces:` der
   Code-Tasks; `Produces: (nichts Neues)`; ein Step führt den Befehl aus und nennt
   Erwartung und Ergebnis.
6. **Ablegen und linten.** `assets/plan-template.md` nach
   `docs/plans/<JJJJ-MM-TT>-<slug>.md` kopieren, Kopfzeile wörtlich lassen. Gibt es
   `docs/plans/` noch nicht, legst du es an und nennst den Pfad in der Antwort — die Bitte
   um einen Plan ist die Einwilligung. Dann:
   ```bash
   python "${CLAUDE_SKILL_DIR}/../subagent-dev/scripts/plan_to_tasks.py" lint docs/plans/<datei>.md
   ```
   Befunde beheben, nicht umformulieren.
7. **Zeigen und übergeben:** Pfad, Tasks in einer Zeile je Task, Verifikationsbefehl. Dann
   „Plan liegt unter …, Lint sauber, weiter mit subagent-dev".

**Ohne das Skript** (nur work-plan installiert, claude.ai, `CLAUDE_SKILL_DIR` leer)
entfällt der Lint. Die Übergabe heißt dann: „Plan liegt unter …, **ungeprüft** — Lint
nicht verfügbar." Nie stillschweigend als fertig melden. subagent-dev ruft seine eigenen
Skripte heute repo-relativ auf; in einem fremden Repo reicht der Weg bis zum Lint, nicht
bis zum Dispatch (`docs/known-limits.md`).

## Contract

- **Kein Plan ohne Anlass.** Unter der Schwelle aus Schritt 1 „Kein Plan nötig", keine
  Datei. Ein Tippfehler bekommt keinen Plan.
- **Quelle oder Annahme.** Jede Anforderung im Plan steht in der Spec, im Auftrag oder in
  einer `- Annahme:`-Zeile.
- **Verifikation zuletzt.** Der letzte Task heißt `Verifikation`, nennt den Befehl oder
  „keine — ungeprüft" und ist lint-fähig.
- **Lesbar für subagent-dev.** Kopfzeile `<!-- skill: work-plan | schema: 1 | … -->` als
  erste Zeile, Task-Blöcke, Interfaces mit `fn:`, `token:`, `file:` oder nackten
  Bezeichnern; `lint` sauber, oder die Übergabe sagt „ungeprüft".
- **Frontmatter:** nur `name`/`description`. **Tier 1 ohne eigenes Skript** — der Lint
  gehört subagent-dev; jede Format-Erweiterung wird dort gebaut und getestet.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Ein Plan schadet nie, ich schreibe lieber einen" | Für eine Datei ohne neue Schnittstelle kostet er mehr als die Änderung. „Kein Plan nötig" ist eine vollständige Antwort. |
| „Den Testbefehl weiß ich, `pytest` passt schon" | Der Befehl steht in CLAUDE.md oder im Runner des Repos. Ein geratener Befehl prüft das falsche. |
| „Die Verifikation steckt ja in jedem Code-Task" | Jeder Code-Task prüft sich selbst. Der letzte Task prüft das Ganze — und hält das Gate am Ende. |
| „Der Nutzer will sicher auch X, das nehme ich mit" | Dann `- Annahme:` und eine Zeile in der Übergabe. Eine stille Anforderung ist erfunden. |
| „Lint ist hier nicht verfügbar, dann ist der Plan eben fertig" | Dann ist er *ungeprüft*, und das steht in der Übergabe. |
| „Ich formuliere die Interfaces um, bis der Lint still ist" | Der Lint zeigt, was das Gate sieht. Behebe das. |

## Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| Implementierungsplan zu einer Spec dieser Sammlung | **impl-plan** | work-plan — die Sammlung hat eigene Pflicht-Tasks |
| was gebaut werden soll, mit Akzeptanzkriterien | **feature-spec** | work-plan beginnt bei der fertigen Spec |
| Plan zerlegen, Gate, Dispatch, Abnahme | **subagent-dev** | work-plan schreibt den Plan und dispatcht nicht |
| Befund zur Architektur oder zur API, der Arbeit nach sich zieht | **architecture-map**, **rest-api-architect** | work-plan plant die Arbeit, der Befund bleibt dort |
| der Rot-Grün-Zyklus innerhalb eines Code-Tasks | test-first | work-plan nennt den Zyklus nur als Steps |
| Plan im Gespräch ohne Datei | eingebauter Plan-Modus | work-plan — die Datei ist für subagent-dev |
