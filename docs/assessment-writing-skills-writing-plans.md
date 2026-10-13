<!-- skill: -- | schema: 1 | generated: von Hand, Prüfung am 2026-09-02 gegen obra/superpowers@b36e082 (v6.3.0) und den Repo-Stand 875779d -->
# Prüfung: Eigene Nachfolger für `superpowers:writing-plans` und `superpowers:writing-skills`?

**Kurzantwort.** Ja für beide — aber nicht als „bessere" Allzweck-Fassungen, sondern
als Eigentümer zweier Verträge, die dieses Repo schon hat und die niemand lädt oder
prüft: das Plan-Format, das `subagent-dev` konsumiert (16 von 17 Plänen bedienen es
nicht), und die Hausmethode für den Skill-Bau aus Spec 00, `skill-building-pitfalls.md`,
`artifact-header.md` und 1.500 Zeilen `known-limits.md`, der weder superpowers noch
Anthropics `skill-creator` entsprechen und in drei Punkten widersprechen. Der größte
Teil des Werts liegt in zwei Tier-1-Lintern (G2), nicht in Doktrin; die Skills lohnen
zusätzlich wegen Routing gegen die installierte Konkurrenz und wegen der Muster für
Doktrin-Tasks, die es nirgends gibt. Reihenfolge: Plan-Lint zuerst (klein, ohne Spec),
dann Spec 16 `impl-plan`, dann Spec 17 `skill-forge`, die `impl-plan` konsumiert.

Alles Weitere ist Beleg. Was ich gemessen habe, steht mit Zahl; was ich nur gelesen
oder vermutet habe, ist so markiert (§8).

## 1 · Was geprüft wurde

| Quelle | Stand | Umfang |
| --- | --- | --- |
| `obra/superpowers`, `skills/writing-plans` | b36e082, 2026-08-12 (v6.3.0) | SKILL.md 171 Zeilen + `plan-document-reviewer-prompt.md` |
| `obra/superpowers`, `skills/writing-skills` | dito | SKILL.md 679 Zeilen + `anthropic-best-practices.md` (1.150), `testing-skills-with-subagents.md` (384), `persuasion-principles.md`, Graphviz-Konventionen |
| Kontext dazu | dito | `executing-plans`, `subagent-driven-development` (568 + drei Prompt-Vorlagen), `brainstorming` |
| Anthropic `skill-creator` | im Nutzerprofil synchronisiert (`~/.claude/skills/synced/…/skill-creator`) | SKILL.md 485 Zeilen, drei Agent-Prompts, acht Skripte, Eval-Viewer, eigenes `evals.json`-Schema |
| Dieses Repo | 875779d (`main`) plus Branch `claude/explain-skill-spec` für Spec 15 | Spec 00, drei Konventions-Dokumente, 17 Pläne, 14 Reports, 16 `evals.json`, 19 SKILL.md, `plan_to_tasks.py` mit 46 Tests, Git-Historie |

Methode: mechanische Messungen, wo möglich (Parser über alle Pläne, Zeilen- und
Wortzählung, Eval-Zählung, Sektions-Häufigkeiten), sonst Lektüre. Keine Evals
gefahren — der Harness läuft in dieser Umgebung nicht (`known-limits.md`, „Betrieb").

## 2 · Wie Skills hier wirklich entstehen

Die Pipeline, die 16 Skills durchlaufen haben, steht in keinem Dokument, aber in
allen Reports:

1. **Spec** per `brainstorming` nach `specs/Spec NN – <skill>.md`. Format ist das
   Brainstorming-Template (Problem / Constraints / Approach / Alternatives / Out of
   scope / Open questions / Next steps) plus eine Kopfzeile „Skill-Spezifikation ·
   Zyklus N/14 · Entscheidung: …", eine Eval-Tabelle und eine Abgrenzungstabelle.
2. **Plan** nach `docs/superpowers/plans/<datum>-<skill>.md`, nominell im
   `superpowers:writing-plans`-Format.
3. **Bau** im Hauptkontext oder durch einen Builder-Subagenten mit Brief und
   „Rulings" (Reports nennen `brief-common.md`, `rulings-final-four.md`, „Koordinator").
4. **Unabhängiger Review** durch einen Subagenten, dann **Fix-Runden** (bis zu fünf,
   `exercise-forge-report.md`).
5. **Evals** in `evals/<skill>/evals.json`, geschrieben und — wo der Harness lief —
   gefahren; Ergebnisse als Stichprobe gelesen.
6. **Report** unter `docs/superpowers/reports/` mit einer Pflichtsektion, die in
   mindestens fünf Varianten heißt („Was ich nicht verifizieren konnte", „Was NICHT gemessen
   wurde", …), und ein Abschnitt in `docs/known-limits.md`.
7. **Nachbarn nachziehen:** Routing-Matrix an zwei Orten, Abgrenzungssätze der
   Nachbar-Skills (erst Spec 15 hat das als eigenen Task gefasst).

Keine Stufe außer 5 hat einen Mechanismus. Alles andere ist G1 — und die Pitfalls-Datei
hält fest, was das gekostet hat: „Kein Autor hat seinen eigenen schwersten Fehler
selbst gefunden."

## 3 · Befund `writing-plans`

### 3.1 Was superpowers liefert

Fair gelesen ist die Skill gut: Plan-Kopf (Goal / Architecture / Tech Stack / Spec /
Global Constraints), `### Task N:` mit `Files:` (Create/Modify/Test) und
`Interfaces:` (Consumes/Produces mit Signaturen), Steps im Checkbox-Format, eine
Verbotsliste für Platzhalter („TBD", „similar to Task N", „add error handling"), ein
Selbst-Review in drei Fragen (Spec-Abdeckung, Platzhalter, Typkonsistenz), ein
Reviewer-Prompt mit brauchbarer Kalibrierung („only flag issues that would cause real
problems during implementation") und eine Regel zum Task-Zuschnitt. Der
`Interfaces:`-Block ist genau das, worauf `plan_to_tasks.py` aufsetzt; Spec 09 hat das
Format bewusst als Grundlage gewählt.

### 3.2 Gemessen: Das Format hält nicht

`python skills/subagent-dev/scripts/plan_to_tasks.py generate` über alle 17 Pläne:

| Plan | parsbar | Tasks | `files_unknown` | `interfaces_unknown` | Verdikt |
| --- | --- | --- | --- | --- | --- |
| 2026-07-10 cad-parts | ja | 12 | 1 | 8 | sequential |
| 2026-08-14 eval-harness | ja | 8 | 0 | 2 | sequential |
| 2026-08-15 dev-report | ja | 6 | 0 | 1 | sequential |
| 2026-08-15 feature-spec | **nein** (`## Task`) | — | — | — | — |
| 2026-08-15 motion-landing | **nein** (`## Task`) | — | — | — | — |
| 2026-08-15 review-context | ja | 7 | 7 | 0 | sequential |
| 2026-08-15 verified-research | **nein** (`### Task 1 —` statt `:`) | — | — | — | — |
| 2026-08-15 visual-summary | ja | 7 | 7 | 0 | sequential |
| 2026-08-16 debug-ledger | **nein** (nummerierte Liste) | — | — | — | — |
| 2026-08-16 rest-api-architect | **nein** (`### Task 1 —`) | — | — | — | — |
| 2026-08-16 sql-schema-architect | **nein** (`## Task-Reihenfolge`) | — | — | — | — |
| 2026-08-16 testing-strategy | **nein** (`## Tasks`, Liste) | — | — | — | — |
| 2026-08-17 architecture-map | **nein** (`## Task`) | — | — | — | — |
| 2026-08-17 exercise-forge | ja | 8 | 8 | 0 | sequential |
| 2026-08-17 learning-coach | ja | 4 | 4 | 0 | sequential |
| 2026-08-17 subagent-dev | ja | 5 | 0 | 3 | sequential |
| 2026-09-01 explain (Branch) | ja | 6 | 0 | 0 | sequential |

- **7 von 17 sind für den eigenen Konsumenten unlesbar.** Zwei davon nur wegen eines
  Gedankenstrichs statt Doppelpunkts im Header; fünf haben das Task-Format ganz
  aufgegeben (H2-Header, nummerierte Listen).
- **Von den 10 lesbaren tragen 9 Unsicherheits-Flags**, meist weil `**Files:**` als
  Inline-Aufzählung statt Bullet-Zeilen geschrieben wurde (`**Files:** Create \`a\`,
  \`b\``) oder `Interfaces:` ohne `Consumes:`/`Produces:`-Label. Das Gate serialisiert
  dann konservativ — mit einer Begründung, die nicht die tatsächliche Kopplung nennt,
  sondern die Schreibweise.
- **Der einzige saubere Plan ist explain**, und der war es nicht von Anfang an: Commit
  644aa34 („Plan ins writing-plans-Format") hat ihn nachträglich umgebaut; dabei kippte
  das Gate-Urteil dreimal (`sequential`, `parallel`, `sequential`), nur durch
  Umformulierungen des `Interfaces:`-Blocks (`known-limits.md` auf dem explain-Branch).
- **In 17 Plänen hat das Gate noch nie `parallel` gesagt.** Entweder sind Skill-Pläne
  wirklich gekoppelt — plausibel, SKILL.md, References und Evals hängen aneinander —
  oder die Blöcke sind so ungenau, dass das konservative Gate immer schließt. Beides
  spricht für ein Format, das *vor* dem Gate geprüft wird, nicht erst darin.
- **Der vorgeschriebene Plan-Kopf** („For agentic workers: REQUIRED SUB-SKILL: Use
  superpowers:subagent-driven-development") steht in 4 von 17 Plänen — und ist in
  diesem Repo falsch, weil hier `subagent-dev` vorgeschaltet wird. 13 Pläne haben ihn
  stillschweigend weggelassen.
- **Sprache:** drei deutsche Pläne tragen englische Step-Namen aus der Vorlage („Write
  the failing test"), die übrigen haben eigene erfunden.
- **Commit 907ed8c (explain-Branch):** Der explain-Plan deklarierte `sources/effort-topic.md`, gebaut
  wurde `sources/kestrel-handshake.md`. Beim sequenziellen Bau läuft kein `verify`,
  also hat es niemand gemeldet.

**Lesart:** Das ist kein Qualitätsproblem der superpowers-Skill, sondern ein
Durchsetzungs- und Trigger-Problem. `writing-plans` ist reine G1-Doktrin: Nichts prüft
den Plan, nachdem er geschrieben ist, und wenn die Skill beim Schreiben nicht geladen
war (Hauptkontext, claude.ai, Builder-Brief), entsteht ein freies Format. Die sieben
unparsbaren Pläne sehen genau so aus.

### 3.3 Was hier fehlt — und superpowers nicht liefern kann

1. **Ein G2-Gate für das Format.** `lint_plan.py` (Tier 1): Kopf-Felder vorhanden,
   `Spec:` zeigt auf eine existierende Datei, jede Task mit `### Task N:`-Header,
   `Files:` als Bullet-Zeilen mit bekannten Verben, `Interfaces:` mit
   `Consumes:`/`Produces:`, Backtick-Symbole entweder gültige Bezeichner oder ein
   erklärtes Vokabular (siehe 4.), keine Prosa zwischen `Interfaces:` und Step 1,
   Steps im Checkbox-Format, Platzhalter-Scan. **Derselbe Parser wie
   `plan_to_tasks.py`** — sonst gibt es zwei Wahrheiten über das Format, und die
   Pitfalls-Datei hat „parallel gebaute Schnittstellen" schon zweimal als Fehlerklasse.
2. **Repo-Pflichtinhalte, die kein Plan systematisch trägt:** Tier pro Skript, G1/G2/G3
   pro Gate, Kopfzeile pro Artefakt, Bootstrap- und Degradationsregel, der
   Anti-Zeremonie-Eval als eigener Step, ein Report-Task mit der Pflichtsektion, ein
   known-limits-Task, ein Nachbarn-Task. Spec 15 hat Task 5 („Nachbarn nachziehen")
   und Task 6 (Report) aus Erfahrung erfunden; ein Template macht sie zur Regel.
3. **Muster für Doktrin-Tasks.** superpowers' fünf Schritte (Test schreiben, rot sehen,
   implementieren, grün sehen, committen) passen für Code. Die Mehrzahl der Tasks
   hier schreibt `SKILL.md`, `references/*.md`, `evals.json`, Fixtures — dafür gibt
   es kein Muster, und jeder Plan improvisiert eines. Der explain-Plan hat mit „Evals
   zuerst bei Tier 0" ein gutes gefunden; es steht nur dort.
4. **Interface-Symbole jenseits von Python-Bezeichnern.** `Unverified:`, `Next:`,
   `effort-ladder` sind keine Bezeichner; `extract_produced_symbols()` liefert null
   Symbole, `_has_unrecognized_prose()` schlägt nicht an — das Gate öffnet still
   (Fail-Open, `known-limits.md`, explain-Branch). Ein eigenes Format kann ein
   Vokabular festlegen (etwa `token:Next`, `file:docs/x.md`, `fn:parse(line)`), statt
   an einer Regex für Bezeichner zu hängen.
5. **Routing.** Der Kopf verweist auf `subagent-driven-development`, der
   „Execution Handoff" bietet zwei superpowers-Optionen an; das Repo will
   `subagent-dev` → `/code-review`. Jeder mit superpowers erzeugte Plan trägt einen
   falschen Wegweiser, der wieder gestrichen wird.
6. **Spec-Vertrag mechanisch.** Die Specs hier haben eine Eval-Tabelle mit IDs.
   „Spec coverage" ist bei superpowers eine Selbst-Review-Frage; hier ginge sie per
   Skript: jede Eval-ID der Spec-Tabelle hat einen Task, jede ID in `evals.json`
   kommt in der Spec vor.

### 3.4 Was übernommen werden sollte

Der `Interfaces:`-Block, die Platzhalter-Verbotsliste, das Selbst-Review-Trio, die
Regel zum Task-Zuschnitt („split only where a reviewer could reject one task while
approving its neighbor"), der Reviewer-Prompt samt Kalibrierung. **Nicht** übernehmen:
2–5-Minuten-Steps als Dogma, „Announce at start", den Handoff-Dialog — das ist die
Zeremonie, die Spec 00 §2 als systemisches Risiko benennt.

### 3.5 Urteil

**Ja, mit Zuschnitt.** Nicht „besseres writing-plans", sondern Eigentümer des
Plan-Formats, das `subagent-dev` konsumiert. Der kleinste wertvolle Schritt braucht
keine Skill: `lint_plan.py` neben `plan_to_tasks.py` plus ein `assets/plan-template.md`.
Die Skill selbst lohnt aus zwei Gründen: **Routing** — die Kollision mit
`superpowers:writing-plans` ist dieselbe, die das Repo mit `debug-ledger` gegen
`systematic-debugging` und `subagent-dev` gegen `subagent-driven-development` schon
zweimal durch eine eigene, schärfer beschriebene Skill gelöst hat — und die
**Doktrin-Task-Muster**, die nur eine Skill zum richtigen Zeitpunkt in den Kontext
bringt. Name nach der Artefakt-Konvention (`feature-spec`, `debug-ledger`,
`dev-report`): `impl-plan`. Umfang: Tier 1, ein Skript (Parser wiederverwendet),
Template, SKILL.md ≤ 150 Zeilen, vier bis fünf Evals — ein normaler Zyklus.

## 4 · Befund `writing-skills`

### 4.1 Drei Lehren nebeneinander

| Dimension | `superpowers:writing-skills` | Anthropic `skill-creator` | Hausmethode (Spec 00 + Pitfalls + Praxis) |
| --- | --- | --- | --- |
| Grundidee | TDD für Doktrin: Baseline ohne Skill, Druckszenarien, Rationalisierungstabelle, „Match the Form to the Failure" | Entwurf → Testprompts mit/ohne Skill → Grader → Viewer → Iteration; Description-Optimierer per `claude -p` | Spec → Plan → Bau → Review → Fix-Runden → Evals → Report → known-limits |
| Umfang SKILL.md | < 500 Wörter, häufig geladene < 200 | < 500 Zeilen | ≤ 150 Zeilen; gemessen 61–150 Zeilen, aber 17 von 19 über 500 Wörtern — das superpowers-Budget ist hier durchgehend und bewusst verletzt |
| Description | nur Trigger, **nie** Workflow („Use when…", 3. Person) | Was **und** Wann, bewusst „pushy" gegen Undertriggering | Trigger **plus** Abgrenzungsklausel gegen zwei Konkurrenten (Spec 00 §5); in der Praxis mit Workflow-Zusammenfassung — widerspricht superpowers direkt |
| Evals | Druckszenarien per Subagent, Meta-Test („warum hast du trotzdem C gewählt?") | eigenes `evals.json` (`prompt`, `expected_output`, `assertions`), Baseline-Läufe, `benchmark.json`, Viewer | `evalkit`-Schema (`class`, `fixture`, `must`, `must_not`, acht Assertion-Typen), Anti-Zeremonie-Pflicht, Diskriminator-Frage, Ergebnisse als Stichprobe |
| Gate-Härte | G1 durchgehend („NO SKILL WITHOUT A FAILING TEST FIRST") | Skripte für Eval-Lauf, Packaging, Description-Loop | G1/G2/G3 deklariert, Sprachregelung, Skript-Tier, Sichtbarkeitsregel |
| Artefakte fremder Repos | — | — | Kopfzeile, Bootstrap, Konsumentenregel, `.skills/`-Pfade, drei begründete Ausnahmen |
| SKILL.md-Struktur | Overview / When to Use / Core Pattern / Quick Reference / Common Mistakes | frei, imperativ, „explain the why" statt MUSS | Eiserne Regel / Ablauf / Contract / Anti-Rationalisierung / Abgrenzung — gemessen: Abgrenzung 16/19, Contract 12, Ablauf 11, Anti-Rationalisierung 13 |
| Nachbarn | — | — | Abgrenzung in beide Richtungen, Routing-Matrix an zwei Orten, Erzeuger und Konsument nebeneinanderlegen (zweimal gescheitert: learning-coach ↔ exercise-forge) |
| Sprache | Englisch | Englisch | Deutsch als Dokumentsprache, englische Bezeichner und Descriptions |

Die stärksten Stücke der Fremdskills, die hier fehlen: superpowers' **„Match the Form
to the Failure"** (Verbot vs. Rezept vs. Pflichtslot vs. Konditional, je nach
Fehlerart — mit der Beobachtung, dass Verbote bei Form-Fehlern nach hinten losgehen)
und **Micro-Tests mit Kontrollgruppe** (fünf Wiederholungen, Varianz als Metrik);
skill-creators **Trigger-Eval-Set** (20 realistische Anfragen, davon acht bis zehn
Beinahe-Treffer, die *nicht* auslösen dürfen) und der **Baseline-Lauf ohne Skill** als
Standard.

### 4.2 Wurde superpowers' Methode hier je befolgt?

Einmal: `cad-parts` (2026-07-10) hat eine RED-Baseline ohne Skill dokumentiert
(`docs/superpowers/validation/`). Seit dem Harness (2026-08-14) nie wieder — kein
Report nennt einen Lauf ohne Skill. Der Ersatz ist die Diskriminator-Frage pro Eval
(„Könnte das Basismodell ohne diese Skill dieselbe Ausgabe erzeugen?", Spec 15) plus
unabhängiger Review. Das ist eine Entscheidung, keine Nachlässigkeit: Druckszenarien
messen Disziplin-Skills; die Skills hier sind zu neun Zehnteln Artefakt-Skills, für die
das Harness-Modell besser passt. Ein eigenes `writing-skills` muss das aussprechen:
RED heißt hier Diskriminator-Frage plus Baseline-Lauf, *wenn* der Harness verfügbar
ist — nicht Druckszenario.

### 4.3 Die ungeschriebene Prüfliste

Aus Reports, Fix-Runden und Pitfalls destilliert; **fett**, was mechanisch prüfbar ist
und in `lint_skill.py` gehört:

1. **Frontmatter nur `name` und `description`** (Spec 00 §5).
2. **SKILL.md ≤ 150 Zeilen**; learning-coach liegt exakt darauf.
3. **Description nennt Trigger und mindestens eine Abgrenzung** („Not for …").
4. **Kein „blockiert", „erzwingt", „stellt sicher", solange kein `assets/hooks/`
   existiert** (Spec 00 §4; Specs 06–09 haben es getan).
5. **Jedes Skript deklariert seinen Tier im Kopf; Tier 1 importiert nur Stdlib**
   (`ast` gegen `sys.stdlib_module_names`).
6. **`evals/<skill>/evals.json` existiert, lädt über `load_evals`, enthält einen
   Anti-Zeremonie-Eval.** `known-limits.md` nennt das als Spec-Lücke; gemessen fehlt
   ein solcher Eval nach Wortlaut in `feature-spec` und `motion-landing`.
7. **Judge-Claims ohne Konjunktion** — „und", „UND", „statt" im Claim sind ein
   Warnsignal (`known-limits.md`, „Judge": die Kette ist milder als ihre Teile).
8. **Fixture-Vorbedingung:** Ein Eval, dessen Assertion Artefakte im Workspace
   erwartet, braucht `"git": true` — sechs Evals auf einmal falsch rot.
9. **Assets tragen die Kopfzeile** (`ARTIFACT_HEADER_RE` über `assets/*.md`), oder
   die Ausnahme steht in `artifact-header.md`.
10. **Routing-Matrix in `README.md` und Spec 00 §5 kennt die Skill.**
11. **Jede in „Abgrenzung" genannte Nachbar-Skill nennt diese Skill zurück.**
12. **Report hat die Pflichtsektion** — unter *einem* Namen statt sieben.
13. **`known-limits.md` hat einen Abschnitt** — 13 Abschnitte für 16 Skills.
14. Assertions hängen an Artefakten, die *nur* diese Skill erzeugt (16 fremde Skills
    sind sichtbar) — teilweise prüfbar: `output_matches` ohne skill-eigenes Token ist
    verdächtig.
15. Erzeuger und Konsument einer Schnittstelle nebeneinanderlegen, bevor beide
    „fertig" heißen (Pfad und Form, zweimal gescheitert).
16. Jedes Beispiel gegen die Regel prüfen, unter der es steht („Beispiele schlagen
    Vorschriften").
17. Die eine Frage an jeder Stelle, die ein Urteil ausgibt: „Wo meldet etwas Erfolg,
    ohne geprüft zu haben?" — `all([])`, null Treffer aus nichtleerer Eingabe,
    übersprungene Gates.
18. Ein Contract verspricht nicht mehr, als sein Gate hält; „Doktrin ist G1 und kann
    versagen" — was mechanisch prüfbar ist, wird nicht appelliert.
19. Der Skriptaufruf ist repo-relativ (`python skills/<skill>/scripts/x.py`) und
    scheitert in jeder installierten Form — repo-weit ungelöst (`known-limits.md`,
    learning-coach Fix-Runde 4). Eine Bau-Skill ist der Ort, das einmal zu
    entscheiden, nicht 16-mal.

Punkte 1–13 sind ein Vormittag Tier-1-Code. Punkte 14–19 sind Doktrin — und genau die,
die ohne eine Skill zum richtigen Zeitpunkt nicht im Kontext sind: Die Pitfalls-Datei
sagt „lies das vor dem Bau", und nichts lädt sie.

### 4.4 Wo die Fremdskills der Hausmethode widersprechen

Das muss entschieden werden, nicht gemittelt:

1. **Description-Doktrin.** superpowers: nie Workflow, weil der Agent sonst der
   Description statt dem Body folgt (belegt mit dem Zwei-Reviews-Fall). Spec 00 §5:
   Abgrenzungsklausel Pflicht; Praxis: Workflow-Zusammenfassungen in fast jeder
   Description. Beide Seiten haben hier einen Beleg — `visual-summary` triggerte
   nicht, Ursache saß in der Description; `testing-strategy` Fix-Runde 3 fand „einen
   echten Skill-Defekt in der `description`". Nichts im Repo misst, welche Doktrin
   trifft. Meine Empfehlung: Trigger und Abgrenzung behalten, Prozess-Zusammenfassungen
   streichen — als Spec-00-Änderung, die `lint_skill.py` grob prüft (Prozessverben wie
   „runs", „builds", „generates" in der Description → Warnung). Das ist eine Annahme,
   kein Befund.
2. **Budget:** Wörter (superpowers) gegen Zeilen (Spec 00). Das Repo hat Zeilen gewählt
   und lebt sie; dabei bleibt es.
3. **Eval-Schema:** skill-creators `evals.json` (`id` als Zahl, `prompt`,
   `expected_output`, `files`, `assertions`) ist mit `evalkit` inkompatibel. Die Skill
   ist im Nutzerprofil installiert, ihre Description ist breit („create a skill …
   run evals to test a skill") — sie würde in diesem Repo `evals/<skill>/evals.json`
   entweder überschreiben oder ein zweites Schema daneben legen. Das ist ein
   konkretes Risiko, kein theoretisches; eine eigene Skill muss diese Kollision in
   der Description gewinnen.
4. **Baseline:** skill-creators Läufe mit/ohne Skill sind die mechanisierte RED-Phase.
   `run_evals.py` kennt keinen Modus ohne Skill. Ein `--without-skill`-Flag wäre die
   billigste Harness-Erweiterung mit dem größten Erkenntnisgewinn: Die
   Diskriminator-Frage würde gemessen statt beantwortet. Außerhalb dieser Skill, aber
   sie sollte es einfordern.

### 4.5 Urteil

**Ja, mit größerem Hebel als bei den Plänen**, weil die Hausmethode existiert (rund
130 KB Dokumentation) und nur nicht geladen und nicht geprüft wird. Zuschnitt: kein
Nachbau von skill-creators Tooling, sondern (a) der Bauablauf aus §2 als Ablauf mit
Pflicht-Steps, (b) `lint_skill.py` (G2, Tier 1) für die Punkte 1–13, (c) die Pitfalls
als Prüfliste je Bauphase statt als Lesetext, (d) die Übernahmen aus §4.1, (e) die
Abgrenzung: `skill-creator` für Skills außerhalb dieser Sammlung oder ohne `evalkit`;
`superpowers:writing-skills` für Disziplin-Skills, die Druckszenarien brauchen.
Name: `skill-forge` — nach `exercise-forge`, weil beide ein Artefakt nur durch ein
Gate hindurch ausliefern.

**Anti-Zeremonie ist hier die eigentliche Designfrage.** superpowers verlangt „Edit
skill without testing? Delete it." — für einen geänderten Satz in einer SKILL.md ist
das genau die Zeremonie, die Spec 00 verbietet. Eigene Regel, mechanisch: Der Lint
läuft immer; Evals werden fällig, wenn der Diff Frontmatter, `## Contract` oder ein
Token berührt, das eine `evals.json`-Assertion nennt (das Muster von
`tests/test_explain_evals_schema.py`, verallgemeinert). Der Pflicht-Anti-Zeremonie-Eval
der Skill ist „ein Satz in einer bestehenden SKILL.md ändern" — Lint, Commit, sonst
nichts.

## 5 · Gegenargumente

- **Routing-Konkurrenz wächst.** 16 fremde plus 19 eigene Skills; jede neue
  Description ist ein Kollisionsrisiko, und Trigger-Verhalten schwankt zwischen
  Läufen (`known-limits.md`, „Stichprobe"). Beide neuen Skills haben installierte
  Gegenstücke mit breiten Descriptions. Ein Routing-Eval ohne Skill-Namen im Prompt
  ist Pflicht, und er wird eine Stichprobe bleiben.
- **Der Harness läuft in Cloud und Containern nicht** (root). Die Evals der neuen
  Skills werden wieder „geschrieben, nicht gefahren". Deshalb muss der Lint den
  Großteil des Werts tragen — er ist der einzige Teil, der überall misst.
- **Spec 00 hat „Konventions-Dokument statt Skill" schon einmal entschieden** — gegen
  eine `scaffold-skill`, weil Konventionen, die nur beim Scaffolding gelten, ab dem
  zweiten Handgriff driften. Das Argument trifft hier nicht: Beide Skills sind
  Prozess-Skills, keine Generatoren, und der Lint ist genau das „gelesene Dokument
  plus geteilter Runner", das Spec 00 als haltbarer beschreibt. Trotzdem gilt: Ein
  `docs/plan-conventions.md` plus Template plus Linter brächte etwa zwei Drittel des
  Werts von `impl-plan` ohne Skill. Der Rest — Routing gegen superpowers und die
  Doktrin-Task-Muster zum Schreibzeitpunkt im Kontext — ist der Skill-Anteil. Wer den
  für zu klein hält, baut nur den Linter.
- **Selbstbezug.** `skill-forge` müsste sich selbst nach der Methode bauen, die es
  vorschreibt. Das geht: Der erste Lauf des Lints gilt dem eigenen Ordner, der erste
  Eval-Lauf sich selbst. Es ist nur zu benennen, nicht zu vermeiden.
- **„Besser als superpowers" ist nicht das Ziel.** superpowers' Fassungen sind
  allgemein und gut; die hier vorgeschlagenen sind spezifisch für diese Sammlung und
  in dieser Sammlung besser. Als Upstream-Ersatz taugen sie nicht und sollen es nicht.

## 6 · Empfehlung und Reihenfolge

1. **Sofort, ohne Spec:** `plan_to_tasks.py` bekommt ein Unterkommando `lint` (oder
   ein `lint_plan.py` mit demselben Parser), das pro Task sagt, *warum*
   `files_unknown`/`interfaces_unknown` gesetzt ist, und bei unparsbarem Plan mit
   Exit ≠ 0 endet. Dazu der Fail-Closed-Fix für Backtick-Symbole ohne gültigen
   Bezeichner und eine Zeile in der Anti-Rationalisierungs-Tabelle gegen „Interfaces
   umformulieren, bis es `parallel` sagt". Beides steht auf dem explain-Branch als
   Befund und ist ein Nachmittag.
2. **Spec 16 `impl-plan`** per `brainstorming`, mit §3.3 als Constraints und §3.4 als
   Übernahmen. Skizze in §7.
3. **Spec 17 `skill-forge`**, konsumiert `impl-plan` für seinen Plan-Schritt. Skizze
   in §7.
4. **Spec 00 nachziehen:** Routing-Matrix („Plan schreiben → impl-plan, nicht
   superpowers:writing-plans"; „Skill bauen → skill-forge, nicht skill-creator, nicht
   superpowers:writing-skills"), die Description-Entscheidung aus §4.4.1, und den
   Anti-Zeremonie-Eval vom Konventions- zum Schema-Zwang machen (die Spec-Lücke aus
   `known-limits.md`).
5. **Nicht tun:** die sieben alten Pläne umschreiben (Historie, keine Konsumenten
   mehr); skill-creators Viewer und Benchmark nachbauen; Druckszenarien als Pflicht
   übernehmen.

## 7 · Entwurfsskizzen

Absichtlich kurz — das sind Eingaben für `brainstorming`, keine Specs.

### `impl-plan` (Spec 16)

**Problem.** Der Plan ist das einzige Artefakt, das zwischen Spec und Bau steht, und
das einzige, das `subagent-dev` maschinell liest — und 16 von 17 bedienen den Leser
nicht. Nichts prüft einen Plan nach dem Schreiben; die Vorlage kennt weder die
Pflichtinhalte dieser Sammlung noch Tasks, die keine Codetasks sind.

**Constraints.** Format bleibt aufwärtskompatibel zu `plan_to_tasks.py` (Header,
`Files:`, `Interfaces:`, Checkbox-Steps) — der Parser ist die Wahrheit, nicht die
Vorlage. Tier 1, Ablage weiter unter `docs/superpowers/plans/` (Pfadentscheidung
ratifiziert, nicht neu erfunden). Deutsch, englische Bezeichner. SKILL.md ≤ 150 Zeilen.
Gate-Sprache: der Lint **meldet**, er blockiert nicht.

**Approach.** Drei Dateien: `SKILL.md` (Ablauf: Spec lesen → Dateistruktur → Tasks
nach Zuschnittsregel → Lint → Selbst-Review → Übergabe an `subagent-dev`),
`assets/plan-template.md` (Kopf, Global Constraints, Task-Block je einmal als
Code-Task und als Doktrin-Task, Pflicht-Tasks Evals/Report/known-limits/Nachbarn),
`scripts/lint_plan.py` (Parser aus `plan_to_tasks.py` importiert oder dorthin
verlagert; Prüfungen aus §3.3 Punkt 1 und 6). Interface-Vokabular für Nicht-Code
(`token:`, `file:`, `fn:`) als Erweiterung des Parsers, fail-closed bei allem anderen.

**Evals.** (1) Anti-Zeremonie: Zwei-Task-Änderung an einer References-Datei ergibt
einen Plan unter 40 Zeilen, ohne Interfaces-Block, der trotzdem parst. (2) Spec mit
fünf Eval-IDs → jede hat einen Task (mechanisch: `file_matches`). (3) Prompt verlangt
einen Plan mit „TBD"-Stellen → Lint meldet sie, Plan wird nicht als fertig gemeldet.
(4) Doktrin-Task (SKILL.md + Tokens) → Interfaces tragen `token:`-Symbole, Gate
erkennt die Kopplung. (5) Routing: „schreib mir den Implementierungsplan zur Spec"
ohne Skill-Namen → Plan trägt die Kopfzeile dieser Skill, nicht den
superpowers-Kopf.

**Abgrenzung.** `feature-spec` und `brainstorming` liefern die Spec; `subagent-dev`
konsumiert den Plan; `superpowers:writing-plans` für Repos ohne `subagent-dev`.

**Offen.** Parser-Eigentum: bleibt er in `subagent-dev` (Konsument) oder wandert er zu
`impl-plan` (Erzeuger)? Spec 00s Konsumentenregel spricht für den Erzeuger als
Schema-Eigentümer. Zweitens: Soll `Spec coverage` hart sein — jede Eval-ID der Spec
braucht einen Task — oder nur gemeldet?

### `skill-forge` (Spec 17)

**Problem.** Die Hausmethode steht in vier Dokumenten und 14 Reports, wird beim Bau
nicht geladen und nirgends geprüft; die installierten Alternativen widersprechen ihr
im Description-Stil, im Budget und im Eval-Schema, und `skill-creator` würde
`evals.json` überschreiben.

**Constraints.** Kein eigener Eval-Runner (`evalkit` ist gesetzt), kein Viewer, kein
Packaging. Tier 1. Der Ablauf ist der aus §2, keine Neuerfindung. Anti-Zeremonie:
eine Satzänderung löst nur den Lint aus. Alles G1 außer dem Lint (G2). SKILL.md
≤ 150 Zeilen; die Prüfliste aus §4.3 in `references/`, nicht im Body.

**Approach.** `SKILL.md` (Ablauf: Spec → `impl-plan` → Bau → Lint → Evals → Report →
Nachbarn; Eiserne Regel: „Kein Fertig ohne Lint und ohne die Sektion ‚Was nicht
gemessen wurde'"), `references/checklist.md` (§4.3 als Prüfliste je Phase, mit
Quelle), `references/form-selection.md` (superpowers' „Match the Form to the
Failure", übersetzt und um die Pitfalls-Fälle ergänzt), `references/evals.md`
(Diskriminator-Frage, Judge-Zerlegung, Fixture-Vorbedingungen, Trigger-Eval-Set nach
skill-creator), `assets/skill-template/` (SKILL.md-Gerüst mit den fünf Hausabschnitten,
`evals.json`-Gerüst mit Anti-Zeremonie-Eval, Report-Gerüst mit der Pflichtsektion
unter einem Namen), `scripts/lint_skill.py` (§4.3 Punkte 1–13, mit „geprüft /
ungeprüft (Grund)" pro Punkt — Sichtbarkeitsregel).

**Evals.** (1) Anti-Zeremonie: „ändere in `handoff/SKILL.md` das Wort X" → Lint-Ausgabe
im Transcript, keine neue Eval-Datei, kein Report. (2) Neue Tier-0-Skill → Evals
stehen vor der SKILL.md im Plan. (3) SKILL.md mit „blockiert" ohne Hook-Asset → Lint
meldet. (4) `evals.json` ohne Anti-Zeremonie-Eval → Lint meldet, Skill wird nicht als
fertig gemeldet. (5) Routing: „bau mir eine Skill für X" → `evals/<x>/evals.json` im
`evalkit`-Schema, nicht im skill-creator-Schema (mechanisch: `load_evals` lädt sie).

**Abgrenzung.** `skill-creator` außerhalb dieser Sammlung; `superpowers:writing-skills`
für Disziplin-Skills mit Druckszenarien; `impl-plan` für den Plan; `subagent-dev` für
den Bau in Paketen.

**Offen.** Die Description-Doktrin (§4.4.1) muss vorher in Spec 00 entschieden sein,
sonst prüft der Lint eine Regel, die nicht gilt. Und: `--without-skill` im Harness —
außerhalb dieser Skill, aber ohne ihn bleibt die Diskriminator-Frage Selbstauskunft.

## 8 · Was nicht geprüft wurde

- Keine Evals gefahren; alle Aussagen über Trigger-Verhalten sind Lektüre der
  Reports, keine eigene Messung.
- superpowers in Version b36e082 gelesen; die auf dem Rechner des Nutzers installierte
  Fassung ist in dieser Umgebung nicht vorhanden und kann abweichen. Insbesondere ist
  der `Interfaces:`-Block upstream neuer als einige Pläne hier — ob die sieben
  unparsbaren Pläne gegen eine ältere Vorlage geschrieben wurden, weiß ich nicht.
- Dass diese sieben Pläne ohne geladene Skill entstanden, ist aus dem Format
  geschlossen, nicht beobachtet.
- Die Description-Doktrin (§4.4.1) hat je einen Beleg pro Seite und keine Messung;
  meine Empfehlung dort ist eine Annahme.
- Die Aufwandsschätzungen („ein Nachmittag", „ein Vormittag") sind Erfahrungswerte aus
  den Plänen dieses Repos, keine Telemetrie.
