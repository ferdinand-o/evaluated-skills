# Spec 17 – skill-forge: Skills, die ihr eigenes Gate passieren

## Problem

Die Hausmethode zum Bau einer Skill steht in vier Dokumenten und fünfzehn Reports
(Spec 00, `docs/artifact-header.md`, `docs/skill-building-pitfalls.md`,
`docs/known-limits.md`) und wird beim Bau weder geladen noch geprüft. Die Prüfung, auf
die diese Spec sich stützt (`docs/assessment-writing-skills-writing-plans.md`, §2 bis §7),
liegt auf dem Branch `claude/assessment-writing-skills-plans` und ist noch nicht auf main. Gemessen am
Stand nach dem Merge von Spec 16, über alle 20 Skills:

| Regel aus der Hausmethode | Stand |
| --- | --- |
| Pflicht-Anti-Zeremonie-Eval (Spec 00 §2) | 3 Skills ohne `evals.json`; von den 17 übrigen nennen 2 den Begriff nirgends, 7 nur in `notes` oder unter einer anderen ID, 8 tragen einen Eval mit `anti-ceremony` in der ID |
| Abschnitt in `known-limits.md` | 6 von 20 fehlen |
| Report-Pflichtsektion „Was nicht gemessen wurde" | unter mindestens sechs verschiedenen Namen („Was ich nicht verifizieren konnte", „Was nicht verifiziert werden konnte", …) |
| Description ohne Prozessbeschreibung | 17 von 20 Descriptions tragen Prozessverben (runs, builds, generates, produces, …) |
| Gate-Sprache (Spec 00 §4) | 6 Treffer auf „blockiert/erzwingt" ohne Hook — alle sechs sind Negationen oder Mechanismus-Beschreibungen, kein echter Verstoß |
| Frontmatter, SKILL.md ≤ 150 Zeilen, Tier-Deklaration je Skript | sauber; `learning-coach` liegt exakt auf 150 |

Die installierten Alternativen widersprechen der Hausmethode: `superpowers:writing-skills`
verbietet jede Prozessbeschreibung in der Description und rechnet in Wörtern statt
Zeilen; Anthropics `skill-creator` bringt ein eigenes `evals.json`-Schema (`expected_output`,
`assertions`) mit, das mit `evalkit` inkompatibel ist, und seine Description („create a
skill … run evals to test a skill") gewinnt heute jedes „bau mir eine Skill". Wer das sagt,
bekommt eine Skill, die das Repo nicht laden kann.

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
  verbietet. Hier gilt: Der Lint läuft immer; Evals werden nur fällig, wenn der Diff
  Frontmatter, den Contract-Abschnitt oder einen Token berührt, den eine Assertion in
  `evals.json` nennt. Mechanisch, nicht als Ermessen.
- **Alles G1 außer dem Lint (G2).** Kein Hook. Die SKILL.md sagt „verlangt" und „meldet",
  nie „blockiert".
- **SKILL.md ≤ 150 Zeilen.** Die 19-Punkte-Prüfliste liegt in `references/`, nicht im Body.
- **Altlast per Register**, wie bei Spec 16: Der Repo-Test lintet alle Skills, bekannte
  Befunde stehen eingefroren je Skill, das Register darf nur schrumpfen. Kein Umbau
  bestehender Skills in dieser Spec.
- **Selbstbezug ist Pflicht, nicht Problem:** `skill-forge` wird nach seiner eigenen
  Methode gebaut. Der erste Lauf des Lints gilt dem eigenen Ordner, mit leerem Register.

Vorab entschieden (Brainstorming 2026-09-10):

1. **Description-Doktrin:** Trigger und Abgrenzungsklausel bleiben Pflicht (Spec 00 §5);
   Prozessbeschreibungen entfallen für neue Skills. Spec 00 §5 wird um den Satz ergänzt,
   der Lint prüft ihn grob (Prozessverben). Bestehende Descriptions werden nicht
   umgeschrieben; sie stehen im Register.
2. **Altlast:** Register, kein Aufräumen.
3. **Baseline-Lauf ohne Skill (`--without-skill` im Harness):** eigene, kleine Spec.
   Diese Spec fordert ihn in `known-limits` ein und baut ihn nicht.

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
4. **Lint:**
   ```bash
   python skills/skill-forge/scripts/lint_skill.py skills/<name> --base <rev> --out .skills/cache/skill-forge/lint.json
   ```
   Ohne `--base` ist `evals_due` ungeprüft, nie „nein". Fehlt das Skript (fremde
   Installation), lautet die Übergabe „ungeprüft — Lint nicht verfügbar".
5. **Evals**, wenn `evals_due` oder neue Skill: `evalkit`-Schema, ein Prompt je Eval,
   Diskriminator-Frage in `notes`, Anti-Zeremonie-Eval mit ID-Präfix `anti-ceremony-`.
6. **Review** durch einen Subagenten mit `reviewer-prompt.md`, dann Fix-Runden; jede
   Fix-Runde endet mit Lint.
7. **Report** mit „Was nicht gemessen wurde", Abschnitt in `known-limits.md`, Nachbarn
   (Routing-Matrix an beiden Orten, Rückverweise). Der Lint prüft alle drei.

**Eiserne Regel:** *Keine Skill gilt als fertig ohne sauberen Lint und ohne die Sektion
„Was nicht gemessen wurde" im Report.* G1 — die SKILL.md verlangt es. Zähne bekommt sie
vom Repo-Test.

**Anti-Zeremonie-Regel:** Ein geänderter Satz in einer bestehenden SKILL.md löst Lint
und Commit aus, sonst nichts. Kein Eval, kein Report, kein Review — es sei denn, der
Lint meldet `evals_due: true`.

### `lint_skill.py` — dreizehn Regeln, jede mit „geprüft / ungeprüft (Grund)"

Ausgabe: stdout und `lint.json` mit `_meta` nach `docs/artifact-header.md`. Jede Regel
ist **eine Zeile** in `lint.json` (`{"id": "...", "status": "pass|finding|unchecked", "reason": "..."}`),
damit Evals sie per `file_matches` binden können, ohne JSON zu parsen. Exit 0 sauber,
1 Befunde, 2 Skill-Ordner nicht lesbar. **`unchecked` zählt nie als `pass`** — die
Sichtbarkeitsregel aus `subagent-dev verify` (`allowlist_checked`) und `impl-plan`
(`coverage.status`).

| id | Regel | Quelle | ungeprüft, wenn |
| --- | --- | --- | --- |
| `frontmatter` | nur `name`, `description`, optional `license`/`version`/`metadata`/`allowed-tools` | Spec 00 §5 | — |
| `skill-md-lines` | SKILL.md ≤ 150 Zeilen | Spec 00 §5 | — |
| `description` | nennt einen Trigger („Use when/for", Anführungszeichen-Trigger) **und** eine Abgrenzung („Not for", „nicht für"); kein Prozessverb (`runs`, `builds`, `generates`, `produces`, `collects`, `renders`, `scans`, `creates`, `writes`, `tracks`, `enforces`, `classifies`) | Spec 00 §5, neu | — |
| `gate-language` | „blockiert", „erzwingt", „stellt sicher" nur mit `assets/hooks/`; **satzweise, Negation im selben Satz entkräftet** („blockiert nicht", „kein Hook erzwingt") | Spec 00 §4 | — |
| `script-tier` | jedes `scripts/*.py` nennt „Tier N" im Modul-Docstring; Tier 1 importiert nur `sys.stdlib_module_names` (per `ast`, ohne Import) | Spec 00 §3 | — |
| `evals-exist` | `evals/<skill>/evals.json` existiert, ist JSON, jeder Eval hat `id`, `class` ∈ {contract, behavior}, genau einen `prompt`, `must` | Spec 00 §2 | `evals/` nicht im Workspace |
| `anti-ceremony-eval` | mindestens eine ID beginnt mit `anti-ceremony-` | Spec 00 §2 | wie oben |
| `judge-claims` | kein `judge`-Claim enthält „ und ", „ UND ", „ statt ", „ sowie " | known-limits „Judge" | wie oben |
| `fixture-git` | ein Eval mit `git_head_unchanged` nennt eine Fixture mit `"git": true`; jede genannte Fixture existiert | known-limits „Fixtures" | `evals/fixtures/` nicht im Workspace |
| `asset-headers` | jedes `assets/**/*.md` beginnt mit der Kopfzeile oder steht als Ausnahme in `docs/artifact-header.md` | artifact-header.md | `docs/` nicht im Workspace |
| `routing` | `README.md` und Spec 00 §5 nennen die Skill in der Matrix | Spec 00 §5 | Dateien nicht im Workspace |
| `neighbors` | jede in „Abgrenzung" genannte Skill dieser Sammlung nennt diese Skill zurück (Description oder Abgrenzung) | Prüfung §4.3 Punkt 11 | `skills/` der Nachbarn nicht im Workspace |
| `report-section` | `docs/superpowers/reports/<skill>-report.md` hat `## Was nicht gemessen wurde`; `docs/known-limits.md` hat `## <skill>` | Prüfung §4.3 Punkte 12–13 | `docs/` nicht im Workspace |

Dazu **`evals_due`** (kein Regel-Status, ein eigenes Feld): mit `--base <rev>` wird
`git diff <rev> -- skills/<name>` gelesen; `true`, wenn der Diff Frontmatter-Zeilen,
den Abschnitt `## Contract` oder eine Zeile berührt, die einen `pattern`-String aus
`evals.json` wörtlich enthält. Ohne `--base`, ohne Git oder ohne `evals.json`:
`"evals_due": "unchecked"` mit Grund. Der Aufrufer entscheidet nichts im Kopf.

Was der Lint **nicht** prüft, weil es Ermessen ist (Prüfung §4.3 Punkte 14–19): ob
Assertions an skill-eigenen Artefakten hängen, ob Erzeuger und Konsument einer
Schnittstelle zusammenpassen, ob Beispiele die Regel treffen, wo etwas Erfolg meldet,
ohne geprüft zu haben. Das steht in `checklist.md` je Phase und im Reviewer-Prompt.

### Repo-Test

`tests/test_skills_lint.py` lintet jeden Ordner unter `skills/` mit den Regeln 1–13
(im Repo sind alle Dateien sichtbar, nichts ist `unchecked`). `KNOWN_FINDINGS` ist ein
`dict[str, frozenset[str]]` — Skill-Name → Regel-IDs, die beim Bau rot waren, eingefroren
nach Regel-ID, nicht nach Zahl. Drei Tests: kein Skill hat einen Befund außerhalb seines
Registers; das Register nennt nur existierende Skills und nur Regel-IDs, die es gibt;
das Register für `skill-forge` ist leer. Ein Skill verlässt das Register, wenn ihn jemand
sauber macht; hinein kommt niemand.

Erwartete Größe des Registers beim Bau, gemessen heute: `description` bei 17 Skills,
`anti-ceremony-eval` bei 12 (3 ohne Evals, 9 ohne ID-Präfix), `report-section` bei 19
(nur zwei Reports tragen die Sektion unter diesem Namen, und einer der beiden Skills hat
keinen known-limits-Abschnitt; 6 Skills fehlen dort), `evals-exist` bei 3. Die genauen Zahlen misst der erste Lauf; die Spec erfindet sie nicht.

### Spec 00 nachziehen

Drei Änderungen, alle in derselben Task wie die Nachbarn:

- **§5, Description:** „Trigger und Abgrenzungsklausel; keine Prozessbeschreibung — was
  die Skill *tut*, steht im Body, nicht in der Description." Als Regel für neue Skills,
  mit Verweis auf das Register für bestehende.
- **§2, Anti-Zeremonie-Eval:** die ID beginnt mit `anti-ceremony-`. Das ist die
  Konvention, die `lint_skill.py` prüft — kein Schema-Zwang in `evalkit`, weil der neun
  bestehende `evals.json` unladbar machte.
- **§5, Routing-Matrix** (auch `README.md`): „Skill bauen oder ändern → skill-forge (17),
  nicht skill-creator (außerhalb dieser Sammlung, eigenes Eval-Schema), nicht
  superpowers:writing-skills (Disziplin-Skills mit Druckszenarien)".

### Evals

Alle mechanisch. Der Diskriminator ist `lint.json` — die Datei, die nur diese Skill
schreibt — oder das `evalkit`-Vokabular in einer neu erzeugten `evals.json`. Der Lint
**ist** im Eval-Workspace verfügbar (`evalkit/workspace.py::prepare()` kopiert das
Skill-Verzeichnis samt `scripts/`), anders als bei `impl-plan`; die Regeln 6–13 sind dort
aber `unchecked`, weil `docs/`, `README.md` und fremde Skills fehlen. Die Evals binden
deshalb an Regeln 1–5 und an `evals_due`. Pfade sind Globs, wo ein Name generiert wird.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-one-sentence-change-lints-only` | contract | `sf-existing`: Mini-Skill `note-tag` mit `evals.json` (ein Eval, `pattern` `Untagged:`), Report mit Pflichtsektion, ein Commit; Prompt: „ändere in skills/note-tag/SKILL.md ‚Fertig.' zu ‚Fertig — keine Rückfrage.'" | `file_exists .skills/cache/skill-forge/lint.json`; `file_matches lint.json "evals_due":\s*false`; `file_unchanged evals/note-tag/evals.json`; `file_unchanged docs/superpowers/reports/note-tag-report.md` | `lint.json` schreibt nur diese Skill; `evals_due: false` ist ihr Urteil, kein Gefühl. Ohne Skill gibt es keine Datei — und `writing-skills` verlangte einen Test. |
| 2 | `token-change-makes-evals-due` | contract | `sf-existing`; Prompt: „ändere in skills/note-tag/SKILL.md den Token `Untagged:` zu `Untagged →`" | `file_matches lint.json "evals_due":\s*true` | Derselbe Diff-Mechanismus, andere Seite: Der Token steht in einem `pattern` der `evals.json`. Ein Basismodell sieht keinen Zusammenhang zwischen SKILL.md-Wort und Assertion. |
| 3 | `gate-word-without-hook-is-reported` | contract | `sf-gate`: Skill, deren Contract „blockiert den Commit" sagt, ohne `assets/hooks/`; Prompt: „prüfe die Skill gate-demo mit skill-forge" | `file_matches lint.json "id": "gate-language", "status": "finding"`; `must_not: file_matches "id": "gate-language", "status": "pass"` | Spec 00 §4 kennt nur diese Sammlung. |
| 4 | `missing-anti-ceremony-eval-is-reported` | contract | `sf-noanti`: Skill mit `evals.json` ohne `anti-ceremony-`-ID, `evals/` im Workspace; Prompt wie 3 | `file_matches lint.json "id": "anti-ceremony-eval", "status": "finding"` | ID-Präfix-Konvention aus Spec 00 §2 (neu). |
| 5 | `routing-new-skill-gets-evalkit-schema` | contract | `sf-spec`: Repo mit gekürzter Spec 00 und einer Zwei-Absatz-Spec; Prompt: „bau mir eine Skill nach specs/Spec 30 – reminder.md", ohne Skill-Namen | `file_matches evals/*/evals.json "class":\s*"(contract\|behavior)"`; `must_not: file_matches evals/*/evals.json expected_output` | `evalkit`-Vokabular gegen `skill-creator`-Vokabular. **Routing-Evals sind stochastisch** (known-limits, „Stichprobe"); ein roter Lauf zeigt die Kollision, ein grüner beweist nichts. |

Eval 5 ist der Pflicht-Routing-Eval; Eval 1 der Pflicht-Anti-Zeremonie-Eval. Eval 2 ist
Eval 1s Gegenstück und braucht einen eigenen Prompt (ein Prompt je Eval, `evalkit/schema.py`).

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
Description gewinnt jedes „bau mir eine Skill"; die Kollision ist real. Er bleibt der
Nachbar für Skills außerhalb dieser Sammlung.

**Anti-Zeremonie-Eval als Schema-Zwang** in `evalkit/schema.py`. Verworfen: macht neun
bestehende `evals.json` unladbar; die Konvention plus Lint plus Register erreicht dasselbe
für neue Skills, ohne alte zu brechen.

**Gate-Sprache per nacktem grep.** Verworfen nach Messung: alle sechs heutigen Treffer sind
Negationen. Die Regel muss satzweise prüfen, sonst produziert sie sechs Falsch-Rot und
null echte Befunde.

## Out of scope

- `--without-skill`-Flag im Harness (eigene Spec; hier nur in `known-limits` eingefordert).
- Aufräumen der 20 bestehenden Skills. Das Register hält den Stand fest, mehr nicht.
- Viewer, Packaging, Description-Optimierer per `claude -p`, Benchmark mit Varianz.
- Hooks (G3). Nichts in dieser Spec blockiert.
- Ein Trigger-Eval-Set fahren. Es steht in `evals.md` als Vorgehen, sobald der Harness
  außerhalb eines Root-Containers läuft.

## Open questions

- **Falsch-Rot der Judge-Regel.** „ und " in einem Judge-Claim ist ein Warnsignal, kein
  Beweis. Beim Bau wird die Regel über alle bestehenden `evals.json` gefahren und die
  Trefferzahl in `known-limits` festgehalten; liegt sie hoch und sind die Treffer legitim,
  wird die Regel auf „ UND " und „ statt " eingeengt. Entscheidet der Bau, mit Messung.
- **Prozessverb-Liste.** Zwölf Verben, aus den heutigen Descriptions gezogen. Sie ist
  eine Heuristik; „Use when a plan exists" enthält kein Verb der Liste und ist trotzdem
  eine Prozessbeschreibung. Der Lint fängt die grobe Form, der Reviewer den Rest.
- **Trigger ungemessen.** Ob „bau mir eine Skill" bei `skill-forge` landet, entscheidet
  der Harness pro Lauf. Eval 5 misst es, wenn er fährt.
- **Selbstbezug beim ersten Lauf:** `skill-forge` lintet sich selbst mit leerem Register.
  Fällt ein eigener Befund, wird er behoben, nicht eingetragen.

## Next steps

1. Plan mit `impl-plan` nach `docs/superpowers/plans/2026-09-10-skill-forge.md`, Tier-1-Reihenfolge:
   `lint_skill.py` mit Tests zuerst, Repo-Test mit Register (erster Lauf misst die
   Zahlen), dann References, Template, SKILL.md, Evals, Spec 00 und Nachbarn, known-limits,
   Report.
2. Spec-Review durch einen Subagenten mit frischem Kontext, wie bei Spec 16.
3. Bau sequenziell im Hauptkontext; der erste Lint gilt `skills/skill-forge`.
4. Die Prüfung von ihrem Branch nach main holen, damit die Quellenangaben dieser Spec
   und der `checklist.md` auf eine Datei zeigen, die es auf main gibt.
