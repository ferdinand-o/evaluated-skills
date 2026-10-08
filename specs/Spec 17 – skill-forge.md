# Spec 17 – skill-forge: Skills, die ihr eigenes Gate passieren

## Problem

Die Hausmethode zum Bau einer Skill steht in vier Dokumenten und fünfzehn Reports
(Spec 00, `docs/artifact-header.md`, `docs/skill-building-pitfalls.md`,
`docs/known-limits.md`) und wird beim Bau weder geladen noch geprüft. Die Prüfung, auf
die diese Spec sich stützt (`docs/assessment-writing-skills-writing-plans.md`, §2 bis §7),
liegt auf dem Branch `claude/assessment-writing-skills-plans` und ist noch nicht auf main.
Gemessen am Stand nach dem Merge von Spec 16, über alle 20 Skills:

| Regel aus der Hausmethode | Stand |
| --- | --- |
| Pflicht-Anti-Zeremonie-Eval (Spec 00 §2) | 3 Skills ohne `evals.json`; von den 17 übrigen nennen 2 den Begriff nirgends, 8 nur in `notes`, 1 unter einer ID ohne Präfix (`mini-plan-below-threshold-is-anti-ceremony`), 6 tragen eine ID mit Präfix `anti-ceremony-` |
| Abschnitt in `known-limits.md` | 6 von 20 fehlen |
| Report-Pflichtsektion „Was nicht gemessen wurde" | 2 Reports tragen sie (als „Was NICHT gemessen wurde"); der Rest unter fünf anderen Namen („Was ich nicht verifizieren konnte", „Was nicht verifiziert werden konnte", …) oder gar nicht |
| Description ohne Prozessbeschreibung | 16 von 20 Descriptions tragen eines von zwölf Prozessverben (runs, builds, generates, produces, collects, renders, scans, creates, writes, tracks, enforces, classifies), Groß-/Kleinschreibung ignoriert |
| Gate-Sprache (Spec 00 §4) | 6 Zeilen mit „blockiert/erzwingt" in Skills ohne `assets/hooks/`: 5 davon Negationen oder Beschreibungen, warum *kein* Hook greift; 1 echte Behauptung (`verified-research/SKILL.md:56`, „`registry.py add` erzwingt das mechanisch") |
| Judge-Claims ohne Konjunktion (known-limits „Judge") | 24 von 47 Claims enthalten „ und ", „ UND ", „ statt " oder „ sowie " |
| Frontmatter, SKILL.md ≤ 150 Zeilen, Tier-Deklaration je Skript | sauber; `learning-coach` liegt exakt auf 150 |

Die installierten Alternativen widersprechen der Hausmethode: `superpowers:writing-skills`
verbietet jede Prozessbeschreibung in der Description und rechnet in Wörtern statt
Zeilen; Anthropics `skill-creator` bringt ein eigenes `evals.json`-Schema (`expected_output`,
`assertions`) mit, das mit `evalkit` inkompatibel ist, und seine Description („create a
skill … run evals to test a skill") ist breit genug, jedes „bau mir eine Skill" zu
gewinnen — ungemessen, aber das Risiko ist konkret: Das Ergebnis wäre eine `evals.json`,
die das Repo nicht laden kann.

Die Diagnose ist dieselbe wie bei Spec 16: kein Wissensproblem, ein Trigger- und
Prüfproblem. Die Regeln existieren; nichts lädt sie zum richtigen Zeitpunkt, und nichts
misst sie.

## Constraints

- **Kein eigener Eval-Runner, kein Viewer, kein Packaging, kein Description-Optimierer.**
  `evalkit` ist gesetzt; `skill-creator`s Tooling wird nicht nachgebaut.
- **Tier 1.** Ein Skript, `scripts/lint_skill.py`, nur Stdlib. Es importiert weder
  `evalkit` noch ein anderes Skill-Skript (Konvention dieser Sammlung; im Eval-Workspace
  gibt es nur den eigenen Ordner).
- **Der Ablauf ist der aus der Prüfung §2**, keine Neuerfindung: Spec → Plan → Bau →
  Review und Fix-Runden → Evals → Report → known-limits → Nachbarn. Der Plan-Schritt
  gehört `impl-plan` (16), der Bau in Paketen `subagent-dev` (09).
- **Anti-Zeremonie ist die Designfrage.** superpowers sagt „Edit skill without testing?
  Delete it." — für einen geänderten Satz ist das genau die Zeremonie, die Spec 00 §2
  verbietet. Hier gilt: Der Lint läuft immer, zählt bei einer Änderung aber nur, was
  gegen den Basisstand **neu** ist; Evals werden nur fällig, wenn der Diff Frontmatter,
  den Contract-Abschnitt oder eine Zeile berührt, auf die ein Assertion-Pattern aus
  `evals.json` greift. Mechanisch, nicht als Ermessen.
- **Alles G1 außer dem Lint (G2).** Kein Hook. Die SKILL.md sagt „verlangt" und „meldet",
  nie „blockiert".
- **SKILL.md ≤ 150 Zeilen.** Die 19-Punkte-Prüfliste liegt in `references/`, nicht im Body.
- **Altlast per Register**, wie bei Spec 16: Der Repo-Test lintet alle Skills, bekannte
  Befunde stehen eingefroren je Skill und Regel, das Register darf nur schrumpfen. Kein
  Umbau bestehender Skills in dieser Spec.
- **Selbstbezug ist Pflicht, nicht Problem:** `skill-forge` wird nach seiner eigenen
  Methode gebaut. Der erste Lauf des Lints gilt dem eigenen Ordner, mit leerem Register.

Vorab entschieden (Brainstorming 2026-09-10):

1. **Description-Doktrin:** Trigger und Abgrenzungsklausel bleiben Pflicht (Spec 00 §5);
   Prozessbeschreibungen entfallen für neue Skills. Spec 00 §5 wird um den Satz ergänzt,
   der Lint prüft ihn grob (Prozessverben). Bestehende Descriptions werden nicht
   umgeschrieben; sie stehen im Register — auch `impl-plan`, gerade erst gebaut, mit „writes".
2. **Altlast:** Register, kein Aufräumen.
3. **Baseline-Lauf ohne Skill (`--without-skill` im Harness):** eigene, kleine Spec.
   Diese Spec fordert ihn in `known-limits` ein und baut ihn nicht.

Nach dem Spec-Review entschieden (2026-09-10):

4. **Skriptpfad (Prüfung §4.3, Punkt 19).** Im Repo heißt der Aufruf
   `python skills/skill-forge/scripts/lint_skill.py`; installiert liegt das Skript unter
   `.claude/skills/skill-forge/scripts/` — auch im Eval-Workspace
   (`evalkit/workspace.py::prepare()`). Die SKILL.md nennt **beide** Pfade nebeneinander.
   Das ist keine Lösung des repo-weiten Problems, sondern die eine Stelle, an der es
   ausgesprochen wird; ein Bootstrap-Mechanismus bleibt out of scope.
5. **Judge-Konjunktionen sind ein Hinweis, kein Befund.** 24 von 47 heutigen Claims
   trafen die Regel, die meisten legitim („X statt Y" ist eine Bedingung). Die Regel
   bekommt den Status `hint`, der nie rot macht und nicht ins Register muss.

## Approach

Eine dünne Skill mit einem Skript, das den Großteil des Werts trägt, weil die Evals in
dieser Umgebung nicht laufen (root-Container, `docs/known-limits.md` „Betrieb").

### Skill-Struktur

```
skills/skill-forge/
├── SKILL.md                         Ablauf, Eiserne Regel, Contract, Anti-Rationalisierung, Abgrenzung
├── references/
│   ├── checklist.md                 die 19 Punkte der Prüfung §4.3, je Bauphase, mit Quelle; die 13 mechanischen markiert
│   ├── form-selection.md            „Match the Form to the Failure" aus writing-skills, übersetzt, um die Pitfalls-Fälle ergänzt
│   ├── evals.md                     Diskriminator-Frage, Judge-Zerlegung, Fixture-Vorbedingungen, Trigger-Eval-Set (nach skill-creator, als Empfehlung)
│   └── reviewer-prompt.md           Bau-Review durch einen Subagenten mit frischem Kontext, kalibriert wie in impl-plan
├── assets/skill-template/
│   ├── SKILL.md                     Gerüst mit den fünf Hausabschnitten und Frontmatter nach Spec 00 §5
│   ├── evals.json                   lädt über evalkit (gültige Beispielwerte, kein Platzhalter), mit Anti-Zeremonie-Eval
│   └── report.md                    Gerüst mit „Was nicht gemessen wurde"
└── scripts/lint_skill.py            Tier 1

evals/skill-forge/evals.json, evals/fixtures/sf-*/
tests/test_skill_forge_lint.py       Unit-Tests des Skripts
tests/test_skills_lint.py            Repo-Test über alle Skills, mit Register
```

### Ablauf (SKILL.md)

1. **Spec lesen oder schreiben** — `brainstorming` für Neues, `feature-spec` (03) mit
   Codebase-Bezug. Die Spec trägt eine Eval-Tabelle mit `id`-Spalte (seit Spec 15).
2. **Plan** mit `impl-plan` (16). Bei Tier 0 stehen die Evals vor der SKILL.md.
3. **Bau** im Hauptkontext oder mit `subagent-dev` (09). Vor dem Bau: `checklist.md`,
   Abschnitt der jeweiligen Phase — nicht die ganze Pitfalls-Datei.
4. **Lint, vor dem Commit:**
   ```bash
   python skills/skill-forge/scripts/lint_skill.py skills/<name> --base HEAD --out .skills/cache/skill-forge/lint.json
   # installiert: python .claude/skills/skill-forge/scripts/lint_skill.py …
   ```
   `--base HEAD` vergleicht den Arbeitsstand mit dem letzten Commit. Ohne `--base` zählen
   alle Befunde (neue Skill) und `evals_due` ist ungeprüft, nie „nein". Fehlt das Skript,
   lautet die Übergabe „ungeprüft — Lint nicht verfügbar".
5. **Evals**, wenn `evals_due` oder neue Skill: `evalkit`-Schema, ein Prompt je Eval,
   Diskriminator-Frage in `notes`, Anti-Zeremonie-Eval mit ID-Präfix `anti-ceremony-`.
6. **Review** durch einen Subagenten mit `reviewer-prompt.md`, dann Fix-Runden; jede
   Fix-Runde endet mit Lint.
7. **Report** mit „Was nicht gemessen wurde", Abschnitt in `known-limits.md`, Nachbarn
   (Routing-Matrix an beiden Orten, Rückverweise). Der Lint prüft alle drei.

**Eiserne Regel:** *Keine Skill gilt als fertig, solange der Lint einen **neuen** Befund
meldet, und keine ohne die Sektion „Was nicht gemessen wurde" im Report.* Bei einer neuen
Skill ist jeder Befund neu. G1 — die SKILL.md verlangt es. Zähne bekommt sie vom Repo-Test.

**Anti-Zeremonie-Regel:** Ein geänderter Satz in einer bestehenden SKILL.md löst Lint
und Commit aus, sonst nichts. Kein Eval, kein Report, kein Review — es sei denn, der
Lint meldet `evals_due: true` oder einen neuen Befund. Altbefunde der Skill stehen im
Register und sind nicht Sache dieser Änderung.

### `lint_skill.py` — dreizehn Regeln, jede mit „geprüft / ungeprüft (Grund)"

Ausgabe: stdout und `lint.json` mit `_meta` nach `docs/artifact-header.md`. Jede Regel
ist ein Objekt mit fester Schlüsselreihenfolge `id`, `status`, `reason`, serialisiert
mit `json.dumps(rule, ensure_ascii=False)` als eigene Zeile — also wörtlich
`{"id": "gate-language", "status": "finding", "reason": "…"}`. Das ist der Vertrag, an
den Evals per `file_matches` binden; Reihenfolge und Separator sind Teil davon, nicht
die Zeilenaufteilung. Status: `pass`, `finding`, `hint`, `unchecked`. Exit 0 ohne
Befund, 1 mit Befund, 2 Skill-Ordner nicht lesbar. **`unchecked` und `hint` zählen nie
als `pass`** — die Sichtbarkeitsregel aus `subagent-dev verify` (`allowlist_checked`)
und `impl-plan` (`coverage.status`).

**Diff-Modus (`--base <rev>`):** Der Lint läuft zweimal, gegen den Arbeitsstand und gegen
`git show <rev>:` desselben Ordners; `lint.json` trägt `findings_mode: "new-vs-base"`,
`findings_at_base` und `new_findings`. Der Exit-Code folgt `new_findings`. Ohne `--base`:
`findings_mode: "all"`. Ohne Git oder unbekannte Revision: Exit 2 mit Grund — ein
Diff-Modus, der stillschweigend alle Befunde als neu zählte, wäre die Zeremonie, die er
verhindern soll.

| id | Regel | Quelle | ungeprüft, wenn |
| --- | --- | --- | --- |
| `frontmatter` | nur `name`, `description`, optional `license`/`version`/`metadata`/`allowed-tools` | Spec 00 §5 | — |
| `skill-md-lines` | SKILL.md ≤ 150 Zeilen | Spec 00 §5 | — |
| `description` | nennt einen Trigger (`Use when`, `Use for`, `Use `, oder ein Zitat in Anführungszeichen) **und** eine Abgrenzung (`Not for`, `not for`, `nicht für`, `instead`); kein Prozessverb aus der Zwölferliste, Groß-/Kleinschreibung ignoriert | Spec 00 §5, neu | — |
| `gate-language` | „blockiert", „erzwingt", „stellt sicher" nur mit `assets/hooks/`. Einheit ist der **Absatz** (durch Leerzeile getrennt; eine Tabellen- oder Listenzeile ist ihr eigener Absatz); eine Negation im selben Absatz („nicht", „nie", „kein", „keine") entkräftet. | Spec 00 §4 | — |
| `script-tier` | jedes `scripts/*.py` nennt im Modul-Docstring `Tier N` — die **erste** Nennung zählt; bei Tier 1 sind nur `sys.stdlib_module_names` und Skripte aus demselben `scripts/`-Ordner importierbar (per `ast`, ohne Import) | Spec 00 §3 | — |
| `evals-exist` | `evals/<skill>/evals.json` existiert, ist JSON, jeder Eval hat `id`, `class` ∈ {contract, behavior}, `prompt` als String, `must` | Spec 00 §2 | `evals/` nicht im Workspace |
| `anti-ceremony-eval` | mindestens eine ID beginnt mit `anti-ceremony-` | Spec 00 §2 | wie oben |
| `judge-claims` | **`hint`**, nie `finding`: ein `judge`-Claim enthält „ und ", „ UND ", „ statt " oder „ sowie " | known-limits „Judge" | wie oben |
| `fixture-git` | jede genannte Fixture existiert unter `evals/fixtures/`; ein Eval mit `git_head_unchanged` nennt eine Fixture mit `"git": true` | known-limits „Fixtures" | `evals/fixtures/` nicht im Workspace |
| `asset-headers` | jedes `assets/**/*.md` außer Dateien namens `SKILL.md` beginnt mit der Kopfzeile, oder sein Pfad steht in `docs/artifact-header.md` unter „Begründete Ausnahme" | artifact-header.md | `docs/` nicht im Workspace |
| `routing` | `README.md` und Spec 00 §5 nennen die Skill in der Spalte „zuständig" der Matrix; die Spalte „nicht" zählt nicht | Spec 00 §5 | Dateien nicht im Workspace |
| `neighbors` | jede in „Abgrenzung" genannte Skill dieser Sammlung nennt diese Skill zurück (Description oder Abgrenzung). Kein Abschnitt „Abgrenzung" → `unchecked (kein Abgrenzung-Abschnitt)`, nie `pass` über eine leere Menge | Prüfung §4.3 Punkt 11 | Nachbar-Ordner nicht im Workspace |
| `report-section` | `docs/superpowers/reports/<skill>-report.md` hat `## Was nicht gemessen wurde` (Groß-/Kleinschreibung ignoriert); `docs/known-limits.md` hat `## <skill>` | Prüfung §4.3 Punkte 12–13 | `docs/` nicht im Workspace |

Dazu **`evals_due`** (ein eigenes Feld: `true`, `false` oder `"unchecked"` mit Grund).
Mit `--base` wird `git diff <rev> -- skills/<name>` gelesen; über alle hinzugefügten und
entfernten Zeilen gilt `true`, wenn eine davon

- im Frontmatter der SKILL.md liegt, oder
- im Contract-Abschnitt liegt — erkannt an einer Überschrift `^## .*Contract` (heute
  trifft das 19 von 20 SKILL.md; ohne solche Überschrift steht das im Grund, die beiden
  anderen Kriterien gelten trotzdem), oder
- von einem Assertion-Pattern getroffen wird: `re.search(pattern, zeile)` für jedes
  `pattern` aus `file_matches` und `output_matches` in `must` **und** `must_not` der
  eigenen `evals.json`. Nicht „wörtlich enthalten": 149 von 195 Patterns im Repo tragen
  Regex-Metazeichen, ein Wortvergleich wäre für drei Viertel der Assertions still tot.

Ohne `--base`, ohne Git oder ohne `evals.json`: `"unchecked"` mit Grund. Der Aufrufer
entscheidet nichts im Kopf.

Was der Lint **nicht** prüft, weil es Ermessen ist (Prüfung §4.3 Punkte 14–19): ob
Assertions an skill-eigenen Artefakten hängen, ob Erzeuger und Konsument einer
Schnittstelle zusammenpassen, ob Beispiele die Regel treffen, wo etwas Erfolg meldet,
ohne geprüft zu haben. Das steht in `checklist.md` je Phase und im Reviewer-Prompt.

### Repo-Test

`tests/test_skills_lint.py` lintet jeden Ordner unter `skills/` ohne `--base` (im Repo
sind alle Dateien sichtbar, nichts ist `unchecked`). `KNOWN_FINDINGS` ist ein
`dict[str, frozenset[str]]` — Skill-Name → Regel-IDs, die beim Bau rot waren, eingefroren
nach Regel-ID; dazu `KNOWN_FINDINGS_MAX_PAIRS`, die Zahl der (Skill, Regel)-Paare, wie
`LEGACY_PLANS_MAX_SIZE` in `tests/test_plans_lint.py`. Vier Tests: kein Skill hat einen
Befund außerhalb seines Registers; das Register nennt nur existierende Skills und nur
Regel-IDs, die es gibt; die Paarzahl überschreitet das Maximum nie; das Register für
`skill-forge` ist leer. Bewusster Trade-off der Mengen-Semantik: Bekommt eine Regel
später einen zweiten Befund an einer registrierten Skill, verdeckt das Register ihn. Das
steht in `known-limits`, nicht im Test.

Gemessen heute, als Erwartung für den ersten Lauf — die genauen Zahlen misst der Bau:
`description` 18 (16 mit Prozessverb, dazu `cad-parts` und `ui-architect` ohne
Abgrenzung), `anti-ceremony-eval` 14 (3 ohne Evals, 11 ohne Präfix), `evals-exist` 3,
`report-section` 19 (nur `impl-plan` erfüllt beide Teile), `neighbors` 13 mit nicht
erwiderter Nennung, `routing` 7 in Spec 00 und 6 im README, `asset-headers` 2 Skills
(`debug-ledger/assets/ledger-template.md`, drei `dev-report/assets/template-*.md`),
`script-tier` 1 (`architecture-map/scripts/drift_check.py` importiert ein
Sibling-Skript — nach der Regel oben erlaubt, also voraussichtlich 0), `gate-language` 1
(`verified-research`).

### Spec 00 nachziehen

Drei Änderungen, alle in derselben Task wie die Nachbarn:

- **§5, Description:** „Trigger und Abgrenzungsklausel; keine Prozessbeschreibung — was
  die Skill *tut*, steht im Body, nicht in der Description." Als Regel für neue Skills,
  mit Verweis auf das Register für bestehende.
- **§2, Anti-Zeremonie-Eval:** die ID beginnt mit `anti-ceremony-`. Das ist die
  Konvention, die `lint_skill.py` prüft — kein Schema-Zwang in `evalkit`, weil der elf
  bestehende `evals.json` unladbar machte.
- **§5, Routing-Matrix** (auch `README.md`): „Skill bauen oder ändern → skill-forge (17),
  nicht skill-creator (außerhalb dieser Sammlung, eigenes Eval-Schema), nicht
  superpowers:writing-skills (Disziplin-Skills mit Druckszenarien)".

### Evals

Alle mechanisch. Der Diskriminator ist `lint.json` — die Datei, die nur diese Skill
schreibt — oder Hausvokabular in einer neu erzeugten `evals.json`. Der Lint **ist** im
Eval-Workspace verfügbar (`prepare()` kopiert das Skill-Verzeichnis samt `scripts/` nach
`.claude/skills/skill-forge/`), anders als bei `impl-plan`. Welche Regeln dort geprüft
sind, hängt an der Fixture: Eine Fixture ohne `docs/` lässt `asset-headers`, `routing`
und `report-section` auf `unchecked`; jede Fixture unten sagt, was sie mitbringt. Keine
Fixture bringt `.skills/cache/` mit; Fixture `sf-spec` bringt nichts unter `evals/` mit,
damit der Glob die eine Datei trifft, die die Skill schreibt.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-one-sentence-change-lints-only` | contract | `sf-existing`: Mini-Skill `note-tag` mit `evals/note-tag/evals.json` (ein Eval mit Präfix `anti-ceremony-`, Pattern `Untagged:`), `docs/superpowers/reports/note-tag-report.md` mit Pflichtsektion, `docs/known-limits.md` mit `## note-tag`, ein Commit, `"git": true`. Prompt: „ändere in skills/note-tag/SKILL.md ‚Fertig.' zu ‚Fertig — keine Rückfrage.'" | `file_exists .skills/cache/skill-forge/lint.json`; `file_matches lint.json "evals_due": false`; `file_matches lint.json "findings_mode": "new-vs-base"`; `file_unchanged evals/note-tag/evals.json`; `file_unchanged docs/superpowers/reports/note-tag-report.md` | `lint.json` schreibt nur diese Skill; `evals_due: false` ist ihr Urteil. Die Fixture ist so gebaut, dass die Skill an der Basis sauber ist — der Eval misst, ob die Änderung zur Zeremonie eskaliert, nicht, ob Altlasten aufgeräumt werden. |
| 2 | `token-change-makes-evals-due` | contract | `sf-existing`. Prompt: „ändere in skills/note-tag/SKILL.md den Token `Untagged:` zu `Untagged →`" | `file_matches lint.json "evals_due": true` | Derselbe Mechanismus, andere Seite: Der Token wird von einem Pattern der `evals.json` getroffen. Ein Basismodell sieht keinen Zusammenhang zwischen einem Wort in der SKILL.md und einer Assertion. |
| 3 | `gate-word-without-hook-is-reported` | contract | `sf-gate`: Skill `gate-demo`, deren Contract „blockiert den Commit" sagt, ohne `assets/hooks/`; kein `evals/`, kein `docs/`. Prompt: „prüfe die Skill gate-demo mit skill-forge" | `file_matches lint.json {"id": "gate-language", "status": "finding"`; `must_not: file_matches {"id": "gate-language", "status": "pass"` | Spec 00 §4 kennt nur diese Sammlung. |
| 4 | `missing-anti-ceremony-eval-is-reported` | contract | `sf-noanti`: Skill mit `evals/<skill>/evals.json` ohne `anti-ceremony-`-ID, `evals/` im Workspace. Prompt wie 3 | `file_matches lint.json {"id": "anti-ceremony-eval", "status": "finding"` | ID-Präfix-Konvention aus Spec 00 §2 (neu); nur mit `evals/` in der Fixture ist die Regel geprüft. |
| 5 | `routing-new-skill-gets-house-evals` | contract | `sf-spec`: Repo mit gekürzter Spec 00 (§3–§5, **ohne** §2 und ohne das Eval-Vokabular) und einer Zwei-Absatz-Spec `specs/Spec 30 – reminder.md`; nichts unter `evals/`. Prompt: „bau mir eine Skill nach specs/Spec 30 – reminder.md", ohne Skill-Namen | `file_matches evals/*/evals.json "id": "anti-ceremony-`; `file_matches evals/*/evals.json (?i)diskriminator`; `must_not: file_matches evals/*/evals.json expected_output` | Das ID-Präfix und die Diskriminator-Notiz sind Hausvokabular, das die Fixture nicht nennt; `expected_output` ist `skill-creator`s Vokabular. **Routing-Evals sind stochastisch** (known-limits, „Stichprobe"); ein roter Lauf zeigt die Kollision, ein grüner beweist nichts. |

Eval 5 ist der Pflicht-Routing-Eval; Eval 1 der Pflicht-Anti-Zeremonie-Eval. Eval 2 ist
Eval 1s Gegenstück und braucht einen eigenen Prompt (ein Prompt je Eval, `evalkit/schema.py`).
Die `file_matches`-Muster oben sind Literale; im `evals.json` werden Klammern und
Anführungszeichen entsprechend escaped.

## Alternatives considered

**Nur der Linter** — `tests/test_skills_lint.py` plus ein Konventionsdokument, keine
Skill. Laut Prüfung §5 zwei Drittel des Werts. Verworfen als Alleinlösung: Die
Doktrin-Punkte 14–19 lägen beim Bau nicht im Kontext, und „bau mir eine Skill" landete
weiter bei `skill-creator`. Der Linter und der Repo-Test sind übernommen; die Skill
bleibt dünn.

**Der Vollbau** — Skill, Linter, `--without-skill`, Trigger-Eval-Set, Aufräumen aller
20 Skills. Verworfen durch die drei Vorab-Entscheidungen: Baseline-Flag als eigene Spec,
Register statt Aufräumen, Trigger-Eval-Set als Empfehlung in `evals.md`, solange der
Harness hier nicht läuft.

**Pitfalls laden** — eine SKILL.md, die nur `skill-building-pitfalls.md` und Spec 00 als
Prüfliste einbindet. Reines G1; nichts misst. Genau die Diagnose.

**`skill-creator` übernehmen.** Sein Eval-Schema ist mit `evalkit` inkompatibel, seine
Description ist breit genug für jedes „bau mir eine Skill"; die Kollision ist real. Er
bleibt der Nachbar für Skills außerhalb dieser Sammlung.

**Anti-Zeremonie-Eval als Schema-Zwang** in `evalkit/schema.py`. Verworfen: macht elf
bestehende `evals.json` unladbar; die Konvention plus Lint plus Register erreicht dasselbe
für neue Skills, ohne alte zu brechen.

**Gate-Sprache per nacktem grep.** Verworfen nach Messung: fünf der sechs heutigen
Treffer sind Negationen oder Beschreibungen, warum kein Hook greift. Die Regel muss
absatzweise prüfen, sonst produziert sie fünf Falsch-Rot für einen echten Befund.

**Lint ohne Diff-Modus** — jeder Lauf zählt alle Befunde. Verworfen nach dem Review: Bei
18 von 20 Skills im Register machte ein geänderter Satz den Lint rot, und die Eiserne
Regel verlangte dann entweder Aufräumen (Zeremonie) oder Ignorieren (Doktrinbruch).

**`evals_due` per Wortvergleich** mit den Pattern-Strings. Verworfen nach Messung: 149
von 195 Patterns tragen Metazeichen und kämen in keiner Zeile wörtlich vor.

## Out of scope

- `--without-skill`-Flag im Harness (eigene Spec; hier nur in `known-limits` eingefordert).
- Aufräumen der 20 bestehenden Skills. Das Register hält den Stand fest, mehr nicht.
- Viewer, Packaging, Description-Optimierer per `claude -p`, Benchmark mit Varianz.
- Hooks (G3). Nichts in dieser Spec blockiert.
- Ein Trigger-Eval-Set fahren. Es steht in `evals.md` als Vorgehen, sobald der Harness
  außerhalb eines Root-Containers läuft.
- Ein Bootstrap für Skriptpfade in installierten Skills. Diese Spec dokumentiert die
  Zweiform, sie löst sie nicht.

## Open questions

- **Prozessverb-Liste.** Zwölf Verben, aus den heutigen Descriptions gezogen. Sie ist
  eine Heuristik; „Use when a plan exists" enthält kein Verb der Liste und ist trotzdem
  eine Prozessbeschreibung. Der Lint fängt die grobe Form, der Reviewer den Rest.
- **Trigger ungemessen.** Ob „bau mir eine Skill" bei `skill-forge` landet, entscheidet
  der Harness pro Lauf. Eval 5 misst es, wenn er fährt.
- **Selbstbezug beim ersten Lauf:** `skill-forge` lintet sich selbst mit leerem Register.
  Fällt ein eigener Befund, wird er behoben, nicht eingetragen. Das Template
  `assets/skill-template/SKILL.md` ist von `asset-headers` ausgenommen, weil es mit
  Frontmatter beginnen muss; `evals.json` und `report.md` im Template tragen die Kopfzeile.
- **Diff-Modus und Umbenennungen.** `git diff <rev> -- skills/<name>` sieht eine
  umbenannte Datei als gelöscht plus neu; jede Zeile gilt dann als geändert und
  `evals_due` wird eher `true`. Das ist die konservative Richtung und bleibt so.

## Next steps

1. Plan mit `impl-plan` nach `docs/superpowers/plans/2026-09-10-skill-forge.md`, Tier-1-Reihenfolge:
   `lint_skill.py` mit Tests zuerst, Repo-Test mit Register (erster Lauf misst die
   Zahlen), dann References, Template, SKILL.md, Evals, Spec 00 und Nachbarn, known-limits,
   Report.
2. Bau sequenziell im Hauptkontext; der erste Lint gilt `skills/skill-forge`.
3. Die Prüfung von ihrem Branch nach main holen, damit die Quellenangaben dieser Spec
   und der `checklist.md` auf eine Datei zeigen, die es auf main gibt.
