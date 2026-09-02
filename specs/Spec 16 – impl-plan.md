# Spec 16: impl-plan — Pläne, die ihr Konsument lesen kann

Skill-Spezifikation · Zyklus 16 · Entscheidung: eine dünne Tier-1-Skill ohne eigenes Skript für die Schreibseite, ein Repo-Test für die Durchsetzung, Parser bleibt beim Konsumenten · Abgeglichen mit Spec 00 · Überarbeitet nach unabhängigem Review · Eingabe: `docs/assessment-writing-skills-writing-plans.md` (auf Branch `claude/assessment-writing-skills-plans`, bis zum Merge nicht auf `main`)

## Problem

Der Plan ist das einzige Artefakt zwischen Spec und Bau — und das einzige, das eine andere Skill maschinell liest. `subagent-dev` fällt sein Gate-Urteil aus den `Files:`- und `Interfaces:`-Blöcken. Gemessen mit `plan_to_tasks.py lint` über alle 17 Pläne dieses Repos (2026-09-02, Branch `claude/subagent-dev-plan-lint`): 8 parsen nicht, 8 tragen zwischen 14 und 78 Befunde, einer ist sauber — und der wurde nachträglich umgebaut. Das Gate hat noch nie `parallel` gesagt.

Die Ursache ist kein Qualitätsproblem von `superpowers:writing-plans`, sondern ein Trigger- und Durchsetzungsproblem: Die Skill ist reine Doktrin, nichts prüft den Plan nach dem Schreiben, und wenn sie beim Schreiben nicht geladen war — Hauptkontext, Builder-Brief, claude.ai —, entsteht ein freies Format. Dazu kennt ihre Vorlage weder die Pflichtinhalte dieser Sammlung (Evals, Report mit Pflichtsektion, known-limits, Nachbarn) noch Tasks, die keine Codetasks sind — und die Mehrzahl der Tasks hier schreibt `SKILL.md`, References und `evals.json`.

## Constraints

**Der Parser bleibt bei `subagent-dev`.** Kein Skill-Skript dieser Sammlung importiert ein anderes; wo zwei Skripte dieselbe Funktion brauchen, wird sie dupliziert und mit „Skripte bleiben eigenständig, Rulings A3" kommentiert (`due_topics.py:130`, `export.py:48`, `verify_blind.py:29`). Das Rulings-Dokument selbst liegt nicht im Repo — die Regel ist gelebte Konvention, keine zitierbare Quelle. Diese Spec **entscheidet** deshalb, statt zu zitieren: nicht duplizieren (zwei Wahrheiten über ein Format sind die Fehlerklasse aus `skill-building-pitfalls.md`, „Über Schnittstellen"), nicht importieren (Konvention), also bleibt der Parser dort, wo er getestet ist. `impl-plan` ruft ihn auf, besitzt ihn nicht. Folge: Jede Format-Erweiterung dieser Spec ist eine Änderung an `subagent-dev`s Skript und wird dort getestet.

**Nur diese Sammlung.** Das Template trägt die Pflicht-Tasks dieses Repos fest. Wer in einem fremden Repo plant, nimmt `superpowers:writing-plans`.

**Tier 1 ohne eigenes Skript.** Die Eiserne Regel dieser Skill hängt an einem Skriptaufruf (`plan_to_tasks.py lint`), also ist sie nicht Tier 0 — in claude.ai/Cowork läuft der Ablauf nicht vollständig. Das Skript gehört einer anderen Skill; die Degradationszeile nach Spec 00 §3 lautet: *Ohne `subagent-dev`s Skript bleibt das Selbst-Review-Trio, und der Plan gilt als „ungeprüft" — das wird bei der Übergabe gesagt, nie stillschweigend übergangen.* Ablage bleibt `docs/superpowers/plans/<datum>-<skill>.md`. Deutsch, englische Bezeichner. SKILL.md ≤ 150 Zeilen. Portables Frontmatter.

**Gate-Sprache (Spec 00 §4):** Der Lint **meldet** (G2). Der Repo-Test ist ebenfalls **G2** — ein Skript fällt das Urteil, der Aufruf `pytest` bleibt freiwillig; es gibt in diesem Repo keine CI und keinen Hook. Er macht die Testsuite rot, er blockiert nichts. Die SKILL.md **verlangt** (G1). Ein Hook-Snippet unter `assets/hooks/` nach dem Muster von Spec 00 §4 wäre G3 und ist bewusst nicht Teil dieser Spec (Open questions).

**Aus `writing-plans` übernommen:** der `Interfaces:`-Block, die Platzhalter-Verbotsliste, das Selbst-Review-Trio (Spec-Coverage, Platzhalter-Scan, Typkonsistenz), die Zuschnittsregel („teile nur, wo ein Reviewer die eine Task ablehnen und die Nachbar-Task annehmen könnte"), der Reviewer-Prompt samt Kalibrierung. **Nicht übernommen:** 2–5-Minuten-Steps als Dogma, „Announce at start", der Handoff-Dialog, der Kopf `REQUIRED SUB-SKILL: superpowers:subagent-driven-development` — er steht in 4 von 17 Plänen und ist hier falsch, weil `subagent-dev` vorgeschaltet wird.

## Approach

**Die Schreibseite ist eine dünne Skill; das Muskelgewebe ist ein Test.** `impl-plan` liefert Template, Ablauf und Prüfliste. `tests/test_plans_lint.py` sorgt dafür, dass ein neuer Plan im falschen Format die Testsuite rot macht — egal, wer ihn schrieb und ob eine Skill geladen war, sobald jemand die Suite fährt. Zusammen decken sie beide Ursachen: fehlendes Format-Wissen beim Schreiben und fehlende Prüfung danach. Ohne den Test wäre `impl-plan` exakt die G1-Skill, die `writing-plans` schon ist.

**Skill-Struktur:**

```
skills/impl-plan/
├── SKILL.md                    (Ablauf, Eiserne Regel, Degradation, Zuschnittsregel, Abgrenzung)
├── assets/
│   └── plan-template.md        (Kopfzeile, Kopf, Global Constraints, ein Code-Task,
│                                ein Doktrin-Task, die vier Pflicht-Tasks mit kanonischen Titeln)
└── references/
    ├── task-patterns.md        (Code-Task vs. Doktrin-Task, Evals-zuerst bei Tier 0,
    │                            Platzhalterliste, Interface-Vokabular)
    └── reviewer-prompt.md      (aus writing-plans, kalibriert auf die Pflichtinhalte)

evals/impl-plan/evals.json
evals/fixtures/ip-*/            (synthetische Specs, siehe Eval-Tabelle)
tests/test_plans_lint.py        (lintet jeden Plan außerhalb der Legacy-Menge)
skills/subagent-dev/scripts/plan_to_tasks.py   (vier Erweiterungen, siehe unten)
```

### Ablauf

1. **Spec lesen** — Eval-Tabelle, Skill-Struktur-Block, Abgrenzung sind die Eingaben; jede Eval-ID der Spec bekommt einen Task, der sie erzeugt.
2. **Dateistruktur** aus dem Skill-Struktur-Block der Spec übernehmen, nicht neu erfinden.
3. **Tasks schneiden** nach der Zuschnittsregel. Doktrin-Tasks folgen dem Doktrin-Muster (Datei → Lint oder Schema-Test → Commit), nicht dem TDD-Fünfschritt. Bei Tier-0-Skills steht der Eval-Task vor der SKILL.md — die Lehre aus Spec 15.
4. **Pflicht-Tasks** aus dem Template übernehmen, mit ihren **kanonischen Titeln**: `### Task N: Evals`, `### Task N: Report`, `### Task N: known-limits`, `### Task N: Nachbarn`. Die Titel sind wörtlich — sie sind das, woran Evals und Reviewer die Pflichtinhalte erkennen. Im Anti-Zeremonie-Fall (eine Änderung an ein, zwei Dateien einer bestehenden Skill) dürfen die vier zu **einem** Sammel-Task `### Task N: Pflicht` zusammengelegt werden, dessen Steps je eine Zeile sind.
5. **Lint:** `python skills/subagent-dev/scripts/plan_to_tasks.py lint <plan> --spec <spec> --out .skills/cache/tasks/lint.json`. Befunde beheben.
6. **Selbst-Review-Trio**, dann Übergabe: „Plan liegt unter …, Lint sauber" — oder „Lint nicht verfügbar, Plan ungeprüft" — „weiter mit `subagent-dev`."

**Eiserne Regel:** *Kein Plan gilt als fertig, solange `lint` einen Befund meldet oder nicht gelaufen ist, ohne dass das gesagt wurde.* G1 — die SKILL.md verlangt es. Zähne bekommt sie vom Repo-Test.

### Kopfzeile und Kopf

Erste nicht-leere Zeile nach `docs/artifact-header.md`. Ein Plan wird von Hand geschrieben, also nennt `generated` das Template, nicht ein Kommando:

```
<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->
```

Danach `**Goal:**`, `**Architecture:**`, `**Spec:**` (Backtick-Pfad, muss existieren). Die Kopfzeile ist das Artefakt, das nur diese Skill erzeugt — und damit der Diskriminator aller Evals: Ein Plan aus `writing-plans` trägt sie nicht, ein Basismodell auch nicht. `artifact_header` ist das Assertion-Primitiv dafür (`evalkit/schema.py`).

### Interface-Vokabular (Erweiterung des Parsers)

Nackte Bezeichner bleiben gültig. Dazu kommen drei Präfixe; alles andere bleibt fail-closed. Heute liefern alle drei Formen einen Fail-Closed-Befund, weil die Symbol-Regex Doppelpunkt und Slash ausschließt — der Parser muss sie kennen, bevor ein Plan sie benutzt.

| Form | Bedeutung | Gate | `verify` |
| --- | --- | --- | --- |
| `` `fn:parse(line)` `` | Aufrufbares, Name + Arity | Symbol-Überlappung, wie bisher | per `ast`, wie bisher |
| `` `token:Next` `` | wörtlicher Ausgabe-Token einer Doktrin | Symbol-Überlappung über den Token-Namen | Textsuche `Next` in den Allowlist-Dateien |
| `` `file:docs/x.md` `` | Lese-Abhängigkeit auf eine Datei, die ein anderer Task schreibt | Pfad-Überlappung gegen dessen `Files:` | nicht geprüft (kein Produces-Symbol) |

Symbole tragen eine `kind`. Ohne sie würde `check_produces` jeden `token:`-Eintrag als `missing` melden (kein `ast`-Fund) und `verify` für jeden Doktrin-Task rot — der Konsument, für den das Vokabular gebaut wird, bräche daran. `token:` schließt die Lücke, an der Spec 15 das Gate still geöffnet hat; `file:` schließt die, die der Fail-Closed-Fix laut gemacht hat (`Consumes: \`evals/explain/evals.json\`` ist eine echte Abhängigkeit, heute „unbekannt").

### Lint-Erweiterungen (in `subagent-dev`)

Vier Ergänzungen an `plan_to_tasks.py`, jede mit Test dort:

1. **Vokabular:** `extract_produced_symbols` erkennt die drei Präfixe und liefert `(kind, name, arity)`; `_interface_dependency` matcht `token:` über den Namen; `build_overlap_graph` bekommt eine dritte Schleife, die `file:`-Konsumpfade gegen die `Files:` anderer Tasks mit `_paths_overlap` prüft; `check_produces` prüft nach `kind`.
2. **`--spec <pfad>`:** Eval-IDs aus der Eval-Tabelle der Spec — erkannt über die Header-Zeile mit einer Spalte `id`, Werte in Backticks; das gibt es erst ab Spec 15, ältere Specs nennen Evals in Prosa, dort meldet der Lint „keine Eval-Tabelle" statt zu raten. Jede ID ohne Task ist ein Befund. `--skill <name>` nennt die `evals/<name>/evals.json`; jede ID dort, die in der Spec fehlt, ist ebenfalls einer.
3. **Kopfzeile:** fehlende oder fremde Kopfzeile ist ein Befund.
4. **`lint.json` trägt `_meta`** (`skill`, `schema`, `generated`) nach `docs/artifact-header.md` — es ist ein Artefakt und wird von `impl-plan` gelesen.

### Repo-Test

`tests/test_plans_lint.py` friert **nach Dateinamen** ein, nicht nach Befund-Zahl: `LEGACY_PLANS = frozenset({…})` mit den 16 Plänen vor Spec 15. Sie werden **nicht gelintet** — sie haben keine Konsumenten mehr, und eine Zahl zum Einfrieren gibt es für die 8 unparsbaren ohnehin nicht (`PlanParseError` ist eine Exception, kein Befund). Jeder Plan außerhalb der Menge muss lint-sauber sein. Ein zweiter Test prüft, dass die Menge nur schrumpft. Das ist robust gegen jede Schärfung des Lints: Sie kann nur neue Pläne treffen, nie die eingefrorenen. Der explain-Plan bleibt außerhalb der Menge und bekommt beim Bau die Kopfzeile, die er heute nicht hat.

### Anti-Rationalisierung (Auszug)

| Gedanke | Realität |
| --- | --- |
| „Die Skill war nicht geladen, das Format ist trotzdem okay" | Der Test entscheidet, nicht das Gefühl. |
| „Ich formuliere die Interfaces um, bis das Gate `parallel` sagt" | `lint` zeigt, was das Gate sieht. Behebe das — die Zeile steht schon in `subagent-dev`. |
| „Für diesen Doktrin-Task passt der TDD-Fünfschritt nicht, ich lasse die Steps weg" | Dann das Doktrin-Muster: Datei → Lint/Schema-Test → Commit. Steps ohne Format sind für das Gate unsichtbar. |
| „Die Pflicht-Tasks sind bei dieser kleinen Skill Zeremonie" | Dann ein Sammel-Task `Pflicht` mit je einer Zeile — nicht null. |
| „Lint ist hier nicht verfügbar, dann ist der Plan eben fertig" | Dann ist er *ungeprüft*, und das steht in der Übergabe. Fertig ohne Lint gibt es nicht. |

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| Implementierungsplan zu einer Spec dieser Sammlung | **impl-plan (16)** | superpowers:writing-plans (fremde Repos), brainstorming (die Spec davor) |
| Spec schreiben | brainstorming, feature-spec (03) | impl-plan |
| Plan in Pakete zerlegen, dispatchen, abnehmen | subagent-dev (09) | impl-plan |
| Skill bauen, Ende-zu-Ende | skill-forge (17, geplant) — konsumiert impl-plan | impl-plan |

`subagent-dev` verweist an **vier** Stellen auf `writing-plans`: in der Description („Use when a superpowers:writing-plans plan exists", „Not for writing the plan itself (use superpowers:writing-plans)", „or writing-plans first") und im Body (`SKILL.md:14` „Kein Plan → `superpowers:writing-plans` zuerst", `:108` „Kein Plan vorhanden → dort zuerst"). Alle vier zeigen nach dem Bau auf `impl-plan`. Dazu die Routing-Matrix an beiden Orten (Spec 00 §5, `README.md`).

### Evals

Ein Plan ist eine Datei; alle Evals sind mechanisch. **Der Lint ist im Eval-Workspace nicht verfügbar** — `evalkit/workspace.py::prepare()` kopiert nur das Skill-Verzeichnis, `subagent-dev`s Skript nicht. Deshalb hängt kein Eval an `lint.json`; die Lint-Disziplin wird vom Repo-Test und von `subagent-dev`s eigenen Tests gemessen, nicht von Agentenläufen. Pfade sind Globs (`evalkit/assertions.py::resolve_target` löst sie auf, alphabetisch erster Treffer) — deshalb bringt **keine** Fixture etwas unter `docs/superpowers/plans/` mit.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-two-task-change-stays-small` | contract | `ip-tiny`: eine bestehende Mini-Skill (SKILL.md + eine References-Datei) und eine Spec, die zwei Zeilen in der References-Datei ändert | `artifact_header` `docs/superpowers/plans/*.md`; `file_max_lines` 50 | Kopfzeile. Kürze könnte das Basismodell auch; die Kopfzeile plus Sammel-Task `Pflicht` nicht. 50 Zeilen: Kopf + zwei Tasks + Sammel-Task, gemessen am heutigen Lint (32 ohne Sammel-Task). |
| 2 | `spec-eval-ids-each-have-a-task` | contract | `ip-five`: Spec mit Eval-Tabelle (`id`-Spalte, fünf IDs), `specs/Spec 00` als Datei für den `Spec:`-Check | `artifact_header`; `file_matches` `^### Task \d+: Evals[\s\S]*<id>` je ID | Die IDs allein diskriminieren nicht — jedes Modell schreibt sie ab. Die Kopfzeile und der kanonische Task-Titel `Evals`, in dem sie stehen müssen, sind Hausvokabular. |
| 3 | `mandatory-tasks-carry-canonical-titles` | contract | `ip-five` | `file_matches` je `^### Task \d+: (Evals\|Report\|known-limits\|Nachbarn)$` | Vier wörtliche Titel, die `writing-plans` nicht kennt. |
| 4 | `doctrine-task-interfaces-carry-tokens` | contract | `ip-tier0`: Spec einer Tier-0-Skill mit zwei mandatierten Tokens in der Eval-Tabelle | `file_matches` `token:[\s\S]*token:`; `file_matches` `^### Task \d+: Evals[\s\S]*^### Task \d+: SKILL\.md` | `token:`-Vokabular und Evals-vor-SKILL.md-Reihenfolge existieren nur in `references/task-patterns.md`. |
| 5 | `routing-house-header-not-superpowers` | contract | `ip-five`; Prompt „schreib mir den Implementierungsplan zur Spec", ohne Skill-Namen | `artifact_header`; `must_not: file_matches` `REQUIRED SUB-SKILL` | Kopfzeile. **Routing-Evals sind stochastisch** (`docs/known-limits.md`, „Ein Eval-Ergebnis ist eine Stichprobe") — ein grüner Lauf beweist nichts, ein roter zeigt die Kollision mit `writing-plans`. |

Der Platzhalter-Eval aus der Prüfungsskizze ist gestrichen: Ein Prompt, der „TBD" verlangt, widerspricht der Eisernen Regel — ein doktrintreuer Agent korrigiert den Platzhalter, ein gehorsamer verletzt die Skill; der Eval misst Gehorsam, nicht Doktrin. Die Platzhalter-Erkennung ist in `subagent-dev`s Tests mechanisch abgedeckt.

**Template-Regel:** `assets/plan-template.md` wird vom Repo-Test als Fixture mitgelintet. Es darf deshalb keines der Platzhalterwörter enthalten (`TBD`, `TODO`, `<platzhalter>`) — Auslassungen heißen `…` — und sein `**Spec:**` zeigt auf `specs/Spec 00 – skill-foundation.md`.

## Alternatives considered

**Der Vertrag statt der Skill** — kein neuer Skill, nur `docs/plan-format.md` plus der Repo-Test. Beinahe gewählt: Er trifft die Diagnose („Trigger-Problem") direkt. Verworfen als *Alleinlösung*, weil „schreib mir den Implementierungsplan" irgendwo landen muss, das Template und Pflicht-Tasks lädt, und `subagent-dev`s Description vom Dispatch handelt. Der Test ist übernommen; die Skill bleibt dünn.

**Der Generator** — Tier-1-Skript, das aus der Spec das Plangerüst erzeugt. Verworfen: Die Specs sind handgeschriebene Prosa mit einem Codeblock und ab Spec 15 zwei Tabellen; ein Parser darauf ist spröde, und die Konvention „kein Import" hieße einen weiteren eigenständigen Markdown-Parser neben dem in `subagent-dev`.

**Der Reviewer-Prompt allein.** Verworfen: Das ist die Pipeline, die es schon gibt, und sie hat acht unparsbare Pläne nicht verhindert. Der Prompt ist übernommen, als Referenz, nicht als Mechanismus.

**Parser wandert zu `impl-plan`.** Sauberer nach der Konsumentenregel, verworfen: kein Import (Konvention), und ein Subprozess-JSON-Protokoll zwischen zwei Skills wäre eine Schnittstelle, die es heute nicht gibt — genau die Fehlerklasse „parallel gebaute Schnittstellen".

**Allowlist nach Befund-Zahl.** Verworfen nach dem Review: nicht monoton (ein Plan kann drei Kosmetik-Befunde verlieren und einen schweren gewinnen), für unparsbare Pläne gibt es keine Zahl, und jede Schärfung des Lints — schon die Kopfzeilen-Prüfung dieser Spec — hätte alle Zahlen falsch gemacht, ohne dass ein Plan angefasst wurde.

**Allgemeine Plan-Skill mit Repo-Profil.** Verworfen: ein Profilmechanismus, ein zweiter Konfigurationsort und Evals für zwei Modi, für einen heutigen Nutzer.

## Out of scope

Umschreiben der 16 Altpläne. Ein eigener Parser oder Linter in `impl-plan`. Planen für fremde Repos. Dispatch und Abnahme (`subagent-dev`). Die Skill-Bau-Prüfliste und der Skill-Linter (Spec 17). Die Description-Doktrin aus der Prüfung §4.4.1 (gehört zu Spec 00, vor Spec 17). Eine Harness-Änderung, die Fremd-Skripte in den Eval-Workspace kopiert (Open questions).

## Open questions

**Der Lint ist in keinem Eval-Workspace da — und das ist ein Repo-Problem, kein Spec-16-Problem.** `known-limits.md` hält fest, dass Skriptaufrufe repo-relativ sind und Tier 1 faktisch nur in diesem Checkout gilt. Hier wird es schärfer: Das Skript gehört einer *anderen* Skill. Ein `skills:`-Feld in `fixture.json`, das `prepare()` mit-installiert, würde es lösen — für alle Skills, nicht nur diese. Das ist eine Harness-Änderung und gehört in eine eigene Runde. Bis dahin messen die Evals dieser Spec das Format, nicht die Lint-Disziplin.

**Der Repo-Test macht Format-Drift an einem Ort sichtbar, der nichts mit Plänen zu tun hat.** Wer eine Zeile in `due_topics.py` ändert, sieht einen roten Plan-Test, wenn vorher ein Plan schlampig committet wurde. Beabsichtigt — Drift soll wehtun —, aber es ist die Stelle, an der so etwas zurückgebaut wird. Dann bleibt nur die Eiserne Regel, und die ist G1.

**Die Legacy-Menge ist ein Schuldenregister ohne Tilgungsplan.** Bewusst: Die 16 haben keine Konsumenten mehr. Der zweite Test verhindert, dass sie wächst; nichts verlangt, dass sie schrumpft.

**Zirkularität beim Bau.** Der Plan für diesen Bau entsteht, bevor Template, Vokabular und Kopfzeilen-Prüfung existieren. Er wird im heutigen Format geschrieben — nackte Bezeichner, keine Präfixe, Kopfzeile von Hand — und mit dem heutigen Lint geprüft; nach Task 1 wird er erneut gelintet und ist der erste Plan, den der Repo-Test außerhalb der Legacy-Menge prüft, sobald es ihn gibt.

**G3 als Opt-in.** Ein Pre-Commit-Snippet unter `assets/hooks/` würde den Repo-Test unabhängig davon machen, ob jemand `pytest` startet. Spec 00 §4 reserviert G3 für irreversiblen Schaden; ein schlampiger Plan ist keiner. Nicht gebaut, hier festgehalten.

**Was G1 bleibt:** die Zuschnittsregel, ob ein Step handlungsfähig ist, ob eine Task zu groß ist. Der Lint sieht Form, nicht Zuschnitt.

**Ungemessen:** Der Harness läuft in dieser Umgebung nicht als root. Die fünf Evals werden geschrieben und schema-validiert, nicht gefahren.

## Next steps

Reihenfolge nach Abhängigkeit: zuerst der **Plan für diesen Bau** im heutigen Format (siehe Zirkularität). Dann die **vier Erweiterungen in `subagent-dev`** mit Tests — Vokabular samt `kind` in `check_produces` zuerst, weil Template und Evals darauf aufsetzen. Dann `references/task-patterns.md` und `assets/plan-template.md`, das Template lint-sauber nach der Template-Regel. Dann `SKILL.md` mit Degradationszeile. Dann der **Repo-Test mit `LEGACY_PLANS`**, und der explain-Plan bekommt seine Kopfzeile. Dann Evals und Fixtures nach der Tabelle. Zuletzt Nachbarn: die vier Stellen in `subagent-dev` und die Routing-Matrix an beiden Orten.
