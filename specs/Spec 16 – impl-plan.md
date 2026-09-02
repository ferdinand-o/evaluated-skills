# Spec 16: impl-plan — Pläne, die ihr Konsument lesen kann

Skill-Spezifikation · Zyklus 16 · Entscheidung: eine Tier-0-Skill für die Schreibseite, ein Repo-Test für die Durchsetzung, Parser bleibt beim Konsumenten · Abgeglichen mit Spec 00 · Eingabe: `docs/assessment-writing-skills-writing-plans.md`

## Problem

Der Plan ist das einzige Artefakt zwischen Spec und Bau — und das einzige, das eine andere Skill maschinell liest. `subagent-dev` fällt sein Gate-Urteil aus den `Files:`- und `Interfaces:`-Blöcken. Gemessen über alle 17 Pläne dieses Repos: 8 parsen gar nicht, 8 weitere tragen zwischen 2 und 78 Lint-Befunde, das Gate hat noch nie `parallel` gesagt. Ein einziger Plan ist sauber, und der wurde nachträglich umgebaut.

Die Ursache ist kein Qualitätsproblem von `superpowers:writing-plans`, sondern ein Trigger- und Durchsetzungsproblem: Die Skill ist reine Doktrin, nichts prüft den Plan nach dem Schreiben, und wenn sie beim Schreiben nicht geladen war — Hauptkontext, Builder-Brief, claude.ai —, entsteht ein freies Format. Dazu kennt ihre Vorlage weder die Pflichtinhalte dieser Sammlung (Evals, Report mit Pflichtsektion, known-limits, Nachbarn) noch Tasks, die keine Codetasks sind — und die Mehrzahl der Tasks hier schreibt `SKILL.md`, References und `evals.json`.

## Constraints

**Der Parser bleibt bei `subagent-dev`.** Regel A3 dieser Sammlung — „Skripte bleiben eigenständig" — verbietet Importe zwischen Skill-Skripten; die Skizze in der Prüfung („Parser importiert oder verlagert") war damit nicht umsetzbar. Entschieden: `plan_to_tasks.py` mit `lint` ist die eine Wahrheit über das Format, und sie liegt beim Konsumenten, der sie lesen muss. `impl-plan` ruft sie auf, besitzt sie nicht. Folge: Jede Format-Erweiterung dieser Spec ist eine Änderung an `subagent-dev`s Skript und wird dort getestet.

**Nur diese Sammlung.** Das Template trägt die Pflicht-Tasks dieses Repos fest. Wer in einem fremden Repo plant, nimmt `superpowers:writing-plans`.

**Tier 0.** Kein eigenes Skript. Der einzige Code dieser Spec — der Repo-Test und die Lint-Erweiterungen — liegt außerhalb der Skill. Ablage bleibt `docs/superpowers/plans/<datum>-<skill>.md` (ratifiziert, nicht neu erfunden). Deutsch, englische Bezeichner. SKILL.md ≤ 150 Zeilen. Portables Frontmatter.

**Gate-Sprache (Spec 00 §4):** Der Lint **meldet** (G2). Der Repo-Test **blockiert** die Testsuite (G3 im Sinne von Spec 00: unabhängig vom Modell). Die SKILL.md **verlangt** (G1). Nichts davon wird mit dem falschen Wort beschrieben.

**Aus `writing-plans` übernommen:** der `Interfaces:`-Block, die Platzhalter-Verbotsliste, das Selbst-Review-Trio (Spec-Coverage, Platzhalter-Scan, Typkonsistenz), die Zuschnittsregel („teile nur, wo ein Reviewer die eine Task ablehnen und die Nachbar-Task annehmen könnte"), der Reviewer-Prompt samt Kalibrierung. **Nicht übernommen:** 2–5-Minuten-Steps als Dogma, „Announce at start", der Handoff-Dialog, der Kopf mit `REQUIRED SUB-SKILL: superpowers:subagent-driven-development` — hier wird `subagent-dev` vorgeschaltet, der Kopf war in 4 von 17 Plänen ein falscher Wegweiser.

## Approach

**Die Schreibseite ist eine dünne Skill; das Muskelgewebe ist ein Test.** `impl-plan` liefert Template, Ablauf und Prüfliste. `tests/test_plans_lint.py` sorgt dafür, dass ein Plan im falschen Format die Testsuite rot macht — egal, wer ihn schrieb und ob irgendeine Skill geladen war. Zusammen decken sie beide Ursachen: fehlendes Format-Wissen beim Schreiben und fehlende Prüfung danach. Ohne den Test wäre `impl-plan` exakt die G1-Skill, die `writing-plans` schon ist.

**Skill-Struktur:**

```
skills/impl-plan/
├── SKILL.md                    (Ablauf, Eiserne Regel, Zuschnittsregel, Abgrenzung)
├── assets/
│   └── plan-template.md        (Kopfzeile, Kopf, Global Constraints, ein Code-Task,
│                                ein Doktrin-Task, die vier Pflicht-Tasks)
└── references/
    ├── task-patterns.md        (Code-Task vs. Doktrin-Task, Evals-zuerst bei Tier 0,
    │                            Platzhalterliste, Interface-Vokabular)
    └── reviewer-prompt.md      (aus writing-plans, kalibriert auf die Pflichtinhalte)

evals/impl-plan/evals.json
evals/fixtures/ip-*/            (synthetische Specs mit Eval-Tabelle)
tests/test_plans_lint.py        (lintet jeden Plan unter docs/superpowers/plans/)
skills/subagent-dev/scripts/plan_to_tasks.py   (Lint-Erweiterungen, siehe unten)
```

### Ablauf

1. **Spec lesen** — Eval-Tabelle, Skill-Struktur-Block, Abgrenzung sind die Eingaben; jede Eval-ID der Spec bekommt einen Task, der sie erzeugt.
2. **Dateistruktur** aus dem Skill-Struktur-Block der Spec übernehmen, nicht neu erfinden.
3. **Tasks schneiden** nach der Zuschnittsregel. Doktrin-Tasks folgen dem Doktrin-Muster, nicht dem TDD-Fünfschritt (`references/task-patterns.md`). Bei Tier-0-Skills steht der Eval-Task vor der SKILL.md — die Lehre aus Spec 15: Ohne Code sind die Evals das einzige Messinstrument.
4. **Pflicht-Tasks** aus dem Template übernehmen: Evals, Report mit der Sektion „Was nicht gemessen wurde", known-limits, Nachbarn (Routing-Matrix an beiden Orten, Abgrenzungssätze).
5. **Lint:** `python skills/subagent-dev/scripts/plan_to_tasks.py lint <plan> --spec <spec> --out .skills/cache/tasks/lint.json`. Befunde beheben. Die JSON-Datei ist das Artefakt, an dem Evals hängen.
6. **Selbst-Review-Trio**, dann Übergabe: „Plan liegt unter …, Lint sauber, weiter mit `subagent-dev`."

**Eiserne Regel:** *Kein Plan gilt als fertig, solange `lint` einen Befund meldet.* Das ist G1 — die SKILL.md verlangt es. Was der Regel Zähne gibt, ist der Repo-Test.

### Kopfzeile und Kopf

Erste nicht-leere Zeile nach der Artefakt-Konvention (`docs/artifact-header.md`):

```
<!-- skill: impl-plan | schema: 1 | generated: python skills/subagent-dev/scripts/plan_to_tasks.py lint <plan> -->
```

Danach `**Goal:**`, `**Architecture:**`, `**Spec:**` (Backtick-Pfad, muss existieren). Die Kopfzeile ist zugleich der Routing-Diskriminator: Ein Plan aus `writing-plans` trägt sie nicht.

### Interface-Vokabular (Erweiterung des Parsers)

Nackte Bezeichner bleiben gültig. Dazu kommen drei Präfixe, additiv, alles andere bleibt fail-closed:

| Form | Bedeutung | Überlappung im Gate |
| --- | --- | --- |
| `` `fn:parse(line)` `` | Aufrufbares, Name + Arity | Symbol-Überlappung, wie bisher |
| `` `token:Next` `` | wörtlicher Ausgabe-Token einer Doktrin | Symbol-Überlappung über den Token-Namen |
| `` `file:docs/x.md` `` | Lese-Abhängigkeit auf eine Datei, die ein anderer Task schreibt | Pfad-Überlappung gegen dessen `Files:` |

`token:` schließt die Lücke, an der Spec 15 das Gate still geöffnet hat. `file:` schließt die zweite, die der Fail-Closed-Fix laut gemacht hat: `Consumes: \`evals/explain/evals.json\`` ist eine echte Abhängigkeit und wird jetzt als solche erkannt statt als „unbekannt" serialisiert.

### Lint-Erweiterungen (in `subagent-dev`)

Drei Ergänzungen an `plan_to_tasks.py lint`, jede mit Test dort:

- **`--spec <pfad>`:** Eval-IDs aus der Eval-Tabelle der Spec extrahieren (Spalte `id`, Backtick-Werte); jede ID, die in keinem Task des Plans vorkommt, ist ein Befund. Umgekehrt jede ID aus `evals/<skill>/evals.json`, die in der Spec fehlt — falls die Datei schon existiert. Gemeldet, nicht blockiert.
- **Kopfzeile:** fehlende oder fremde Kopfzeile ist ein Befund.
- **Vokabular:** `fn:`/`token:`/`file:` werden extrahiert; `file:` fließt in die Pfad-Überlappung des Gates ein.

### Repo-Test

`tests/test_plans_lint.py` ruft `lint_plan()` über jede Datei unter `docs/superpowers/plans/` auf. Eine **eingefrorene Allowlist** nennt die 16 Altpläne, die heute Befunde tragen oder nicht parsen — mit ihrem heutigen Befund-Stand als Zahl. Regel: Ein Plan außerhalb der Liste muss lint-sauber sein; ein Plan in der Liste darf nicht *schlechter* werden als eingefroren. Wer einen Altplan anfasst, macht ihn sauber und streicht ihn, oder lässt ihn stehen. Die Altpläne werden nicht umgeschrieben (Historie, keine Konsumenten mehr).

### Anti-Rationalisierung (Auszug)

| Gedanke | Realität |
| --- | --- |
| „Die Skill war nicht geladen, das Format ist trotzdem okay" | Der Test entscheidet, nicht das Gefühl. Rot ist rot. |
| „Ich formuliere die Interfaces um, bis das Gate `parallel` sagt" | `lint` zeigt, was das Gate sieht. Behebe das, statt es zu umgehen — die Zeile steht schon in `subagent-dev`. |
| „Für diesen Doktrin-Task passt der TDD-Fünfschritt nicht, ich lasse die Steps weg" | Dann das Doktrin-Muster: Datei → Lint/Schema-Test → Commit. Steps ohne Format sind für das Gate unsichtbar. |
| „Die Pflicht-Tasks sind bei dieser kleinen Skill Zeremonie" | Report und Nachbarn sind bei jeder Skill Pflicht; bei einer Zwei-Task-Änderung sind sie je eine Zeile, nicht null. |
| „Spec-Coverage prüfe ich im Kopf" | `--spec` prüft sie in einer Sekunde. Der Kopf hat in 17 Plänen keinen einzigen Coverage-Befund gemeldet. |

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| Implementierungsplan zu einer Spec dieser Sammlung | **impl-plan (16)** | superpowers:writing-plans (fremde Repos), brainstorming (die Spec davor) |
| Spec schreiben | brainstorming, feature-spec (03) | impl-plan |
| Plan in Pakete zerlegen, dispatchen, abnehmen | subagent-dev (09) | impl-plan |
| Skill bauen, Ende-zu-Ende | skill-forge (17, geplant) — konsumiert impl-plan | impl-plan |

Zeilen in der Routing-Matrix an beiden Orten (Spec 00 §5, `README.md`). `subagent-dev`s Description sagt heute „Kein Plan vorhanden → superpowers:writing-plans zuerst" — muss auf `impl-plan` zeigen.

### Evals

Ein Plan ist eine Datei. Anders als bei Spec 15 sind deshalb **alle** Evals mechanisch — kein Judge. Die Fixtures sind synthetische Specs mit Eval-Tabelle.

| # | id | Klasse | Fixture | Prüft | Mechanismus |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-two-task-change-stays-small` | contract | `ip-tiny-spec` | Pflicht-Anti-Zeremonie: Spec verlangt eine Zwei-Zeilen-Änderung an einer References-Datei | `file_exists` Plan, `file_max_lines` 40, `file_matches` lint.json `"status": "clean"` |
| 2 | `spec-eval-ids-each-have-a-task` | contract | `ip-spec-five-evals` | Coverage | fünf `file_matches` auf den Plan, je eine Eval-ID |
| 3 | `placeholders-are-reported` | contract | `ip-spec-five-evals` | Prompt verlangt, einen Step „TBD" zu lassen | `file_matches` lint.json `Platzhalter`; `must_not: file_matches` lint.json `"status": "clean"` |
| 4 | `doctrine-task-interfaces-carry-tokens` | contract | `ip-tier0-spec` | Spec einer Tier-0-Skill mit zwei mandatierten Tokens | `file_matches` Plan `token:` zweimal; Eval-Task steht vor dem SKILL.md-Task (`file_matches` auf die Task-Reihenfolge) |
| 5 | `routing-house-header-not-superpowers` | contract | `ip-spec-five-evals` | „schreib mir den Implementierungsplan zur Spec", ohne Skill-Namen | `file_matches` Plan `skill: impl-plan`; `must_not: file_matches` `REQUIRED SUB-SKILL` |

Jeder Eval hängt an einem Artefakt, das nur diese Skill erzeugt — die Kopfzeile, die `lint.json`, das `token:`-Vokabular. Das Basismodell ohne Skill schreibt Pläne ohne Kopfzeile und ohne Lint-Artefakt; `writing-plans` schreibt den superpowers-Kopf.

## Alternatives considered

**Der Vertrag statt der Skill** — kein neuer Skill, nur `docs/plan-format.md` plus der Repo-Test. Beinahe gewählt: Er trifft die Diagnose („Trigger-Problem") direkt. Verworfen als *Alleinlösung*, weil „schreib mir den Implementierungsplan" irgendwo landen muss, das Template und Pflicht-Tasks lädt, und `subagent-dev`s Description vom Dispatch handelt, nicht vom Schreiben. Der Test ist übernommen; die Skill bleibt dünn.

**Der Generator** — Tier-1-Skript, das aus der Spec das Plangerüst erzeugt. Verworfen: 15 handgeschriebene Specs sind Prosa mit einem Codeblock und zwei Tabellen; ein Parser darauf ist spröde, und A3 hieße ein dritter Markdown-Parser im Repo — für einen Nutzer.

**Der Reviewer-Prompt allein.** Verworfen: Das ist die Pipeline, die es schon gibt, und sie hat acht unparsbare Pläne nicht verhindert. Der Prompt ist übernommen, als Referenz, nicht als Mechanismus.

**Parser wandert zu `impl-plan`.** Sauberer Zuschnitt nach der Konsumentenregel, verworfen wegen A3 (kein Import) und weil ein Subprozess-JSON-Protokoll zwischen zwei Skills eine Schnittstelle wäre, die es heute nicht gibt — die Pitfalls-Datei hat parallel gebaute Schnittstellen zweimal als Fehlerklasse.

**Allgemeine Plan-Skill mit Repo-Profil.** Verworfen: ein Profilmechanismus, ein zweiter Konfigurationsort und Evals für zwei Modi, für einen heutigen Nutzer.

## Out of scope

Umschreiben der 16 Altpläne. Ein eigener Parser oder Linter in `impl-plan`. Planen für fremde Repos. Der Dispatch und die Abnahme (`subagent-dev`). Die Skill-Bau-Prüfliste und der Skill-Linter (Spec 17). Die Description-Doktrin aus der Prüfung §4.4.1 (gehört zu Spec 00, vor Spec 17).

## Open questions

**Der Repo-Test macht Format-Drift an einem Ort sichtbar, der nichts mit Plänen zu tun hat.** Wer eine Zeile in `due_topics.py` ändert, sieht einen roten Plan-Test, wenn jemand vorher einen Plan schlampig committet hat. Das ist beabsichtigt — Drift soll wehtun — aber es ist die Stelle, an der diese Spec am ehesten zurückgebaut wird. Wenn das passiert, bleibt nur die Eiserne Regel, und die ist G1.

**Die Allowlist ist ein Schuldenregister ohne Tilgungsplan.** 16 Pläne sind eingefroren; nichts zwingt, sie je sauber zu machen. Bewusst: Sie haben keine Konsumenten mehr. Aber die Liste ist auch die Stelle, an der ein neuer schlampiger Plan „versehentlich" landen könnte. Der Test sollte die Liste als Konstante mit Kommentar führen, nicht aus einer Datei lesen.

**`--spec` erkennt Eval-IDs aus einer Tabelle, deren Form nie festgelegt wurde.** Die Specs 11 bis 15 haben eine `id`-Spalte mit Backtick-Werten; frühere Specs nennen Evals in Prosa. Der Check gilt damit für neue Specs, für alte meldet er „keine Eval-Tabelle gefunden" statt zu raten.

**Was G1 bleibt:** die Zuschnittsregel, ob ein Step handlungsfähig ist, ob eine Task zu groß ist. Der Lint sieht Form, nicht Zuschnitt. Der Reviewer-Prompt deckt das ab — als Selbstauskunft, nicht als Mechanismus.

**Ungemessen:** Der Harness läuft in dieser Umgebung nicht als root (`docs/known-limits.md`, „Betrieb"). Die fünf Evals werden geschrieben und schema-validiert, nicht gefahren.

## Next steps

Reihenfolge nach Abhängigkeit, nicht nach Aufzählung: zuerst die **Lint-Erweiterungen in `subagent-dev`** (`--spec`, Kopfzeile, Vokabular) mit Tests, weil Template und Evals darauf aufsetzen. Dann `references/task-patterns.md` und `assets/plan-template.md` — das Template muss selbst lint-sauber sein und wird im Test als Fixture mitgeprüft. Dann `SKILL.md`. Dann der **Repo-Test mit eingefrorener Allowlist**, gegen die 17 heutigen Pläne gemessen. Dann Evals und Fixtures. Zuletzt Nachbarn: Routing-Matrix an beiden Orten, `subagent-dev`s Description und Ablauf-Schritt 1 auf `impl-plan`. Der Plan für diesen Bau ist der erste, der mit `impl-plan`s eigenem Template geschrieben wird — und der erste, den der Repo-Test von Anfang an prüft.
