# Spec 26: review-plan — ein Plan, dessen Behauptungen über das Repo geprüft sind, bevor ein Builder ihnen glaubt

Skill-Spezifikation · Zyklus 26 · Entscheidung: ein eigenes Tier-1-Skript gleicht den Plan mechanisch mit dem Repo ab, ein Reviewer mit frischem Kontext beurteilt den Rest und baut riskante Tasks in einer Kopie nach; die Skill schreibt ein Urteil in einen Unterordner neben den Plan und ändert den Plan nie · Abgeglichen mit Spec 00 · Überarbeitet nach unabhängigem Review

> **Status: Entwurf, nicht gebaut.** Geschrieben am 2026-10-08 als „Spec 25"; umnummeriert auf 26, weil Spec 25 inzwischen `skill-dir` ist. Verweise auf Spec 20 beziehen sich auf den Stand vor dessen Bau (`plugins/<plugin>/skills/`, `scripts/sync_plugins.py`); gebaut wurde die Projekt-Installation unter `.claude/skills/` mit `scripts/sync_skills.py`. Der Nutzen des mechanischen Teils ist ungemessen (siehe Open questions).

## Problem

Ein Plan dieser Sammlung wird heute zweimal geprüft, aber nie gegen das Repo, für das
er gilt. `plan_to_tasks.py lint` prüft die Form (Kopf, Tasks, Steps, Platzhalter) und
ob jede Eval-ID der Spec in einem Task vorkommt. Wie weit das trägt, steht in
`docs/known-limits.md`, Abschnitt `impl-plan`: „Die Coverage findet eine ID, die
irgendwo in einem Task-Block steht — nicht, ob der Task sie *baut*. Das prüft der
Reviewer, kein Regex." Der Reviewer-Prompt von impl-plan
(`skills/impl-plan/references/reviewer-prompt.md`) prüft Vollständigkeit,
Spec-Abgleich, Zuschnitt, Pflichtinhalte, Reihenfolge und Baubarkeit; eine Pflicht,
Behauptungen über Dateien, Symbole und Tests nachzumessen, hat er nicht — anders als
der Spec-Reviewer (`skills/skill-forge/references/spec-reviewer-prompt.md`, Kategorie
„Fakten über das Repo"). `subagent-dev verify` prüft Dateien und Symbole erst nach dem
Bau.

Ein Plan fügt der Spec Behauptungen hinzu, die kein Spec-Review sieht: die
`**Files:**`-Listen je Task, die `Consumes`-Symbole, die Befehle in den Steps. Was
dabei fehlen kann, zeigt der Review dieser Spec selbst. Ihre erste Fassung listete die
Dateien eines Plans auf; der Reviewer baute die Änderung in einer Kopie nach und ließ
die Suite laufen: `test_installed_copies_match_originals_bytewise` wurde rot, weil die
Projekt-Kopien unter `.claude/skills/impl-plan/` und `.claude/skills/subagent-dev/`
fehlten, und `grep` fand zwei weitere Verweise auf die zu löschende Datei
(`skills/skill-forge/references/reviewer-prompt.md:7`,
`skills/impl-plan/references/task-patterns.md:74`). Die enge Folgenregel (siehe
`impact` unten), als Wegwerfskript gegen `HEAD` gefahren, nennt für dieselbe
Dateiliste fünf betroffene Dateien, alle echt: die drei fehlenden Kopien sowie den
Verweis in skill-forge und dessen Kopie. Den Verweis in `task-patterns.md` findet sie
nicht, weil er keinen Pfad trägt.

Wie viel der mechanische Teil an echten Plänen findet, ist dagegen offen gemessen: Die
Regeln `file-*`, `symbol-unknown` und `command-path` lieferten im Review an den vier
jüngsten Plänen unter `docs/superpowers/plans/` keinen Befund, die enge Folgenregel an
allen fünf Plänen außerhalb von `LEGACY_PLANS` keine Folge (je gegen den Stand vor dem
Plan-Commit). Diese Pläne entstanden vor PR #16, also ohne Projekt-Kopien. Der Wert
liegt deshalb weniger im Abgleich allein als in der Pflicht, jede Folge zu beantworten
und Riskantes nachzubauen — und in Plänen aus fremden Repos, die kein Spec-Review
hinter sich haben.

Der Lint selbst ist im Eval-Workspace einer anderen Skill nicht vorhanden: „Der Lint
ist im Eval-Workspace nicht verfügbar … das Skript von `subagent-dev` liegt dort nicht"
(known-limits, `impl-plan`).

Der Nutzer will am 2026-10-08 eine Skill, die jede Einzelheit eines
Implementierungsplans verifiziert und ein generelles Review macht, als eigene Spec 26;
Spec 20 bis 22 werden parallel bearbeitet und bleiben unberührt.

## Constraints

Tier 1: `scripts/check_plan.py` mit eigenem Parser für das Planformat; kein Import
fremder Skill-Skripte (`skills/skill-forge/assets/spec-template.md`, Constraints). Dass
beide Parser dieselben Tasks und Pfade sehen, hält ein Repo-Test fest. Gate-Grade:
`check_plan.py` meldet (G2), auch im Prüfmodus `audit` für die Urteilsdatei; das Urteil
selbst verlangt die SKILL.md (G1); einen Hook gibt es nicht. Ablage nach Spec 00 §1:
das Urteil als Wissen in `<plan-ordner>/reviews/<plan-stamm>.review.md` (committet,
Kopfzeile; `<plan-stamm>` ist der Dateiname des Plans ohne `.md`), Prüf- und
Lint-Ergebnis als Ephemera unter `.skills/cache/review-plan/` (`_meta`). Bootstrap-Regel
(Spec 00 §1): Der erste Lauf in einem Repo ohne `reviews/` neben dem Plan nennt beide
Pfade, bevor er schreibt. Portables Frontmatter, nur `name` und `description`.
SKILL.md ≤ 150 Zeilen. Skriptaufrufe in der Zweiform der übrigen Skills
(known-limits, „Der Skriptpfad ist eine dokumentierte Zweiform"; Vorbild
`skills/human-prose/SKILL.md`): `python skills/review-plan/scripts/check_plan.py …`,
darunter `# installiert: python .claude/skills/review-plan/scripts/check_plan.py …`;
im Eval-Workspace liegt die Skill unter `.claude/skills/review-plan/`. Die Skill ändert
den Plan nie. Sie
liest Pläne im Format von impl-plan und von `superpowers:writing-plans`
(Task-Überschriften, `**Files:**`; `**Interfaces:**` nur, wo vorhanden). Weil die Skill
beim Arbeiten an der Sammlung gebraucht wird, kommt sie auch als Projekt-Kopie unter
`.claude/skills/` (PR #16, `REPO_DEV_SKILLS`).

## Approach

**Eiserne Regel:** *Kein Urteil „freigegeben", solange `check_plan.py` einen Befund
meldet oder nicht gelaufen ist — und jede Aussage des Urteils über das Repo nennt den
Befehl, mit dem sie gemessen wurde.*

### Skill-Struktur

```
skills/review-plan/
├── SKILL.md                         Ablauf, Eiserne Regel, Größenregel, Urteilsregeln, Contract, Abgrenzung
├── references/reviewer-prompt.md    Reviewer mit frischem Kontext: die sechs Kategorien aus impl-plan plus Fakten nachmessen, Folgen beantworten, Riskantes in einer Kopie nachbauen
├── references/checks.md             was check_plan.py prüft und was nicht, Schema von check.json, wie Befund, Hinweis und Folge zu lesen sind
├── assets/review-template.md        Gerüst der Urteilsdatei, Kopfzeile in Zeile 1
└── scripts/check_plan.py            Tier 1 — Plan gegen das Repo; Unterbefehl audit prüft die Urteilsdatei gegen check.json

skills/impl-plan/SKILL.md            Schritt 6 übergibt an review-plan statt an den eigenen Prompt; Contract-Zeile „Jede Format-Erweiterung ist dort zu bauen und zu testen" nennt den zweiten Parser in review-plan
skills/impl-plan/references/reviewer-prompt.md   entfällt; der Inhalt geht in skills/review-plan/references/reviewer-prompt.md auf
skills/impl-plan/references/task-patterns.md     Zeile 74 „ein Befund im Reviewer-Prompt" zeigt auf review-plan
skills/skill-forge/references/reviewer-prompt.md Zeile 7 „Kalibrierung und Format sind die aus impl-plan/references/reviewer-prompt.md" zeigt auf review-plan
skills/subagent-dev/SKILL.md         Abgrenzung: review-plan prüft vor dem Bau, verify nach dem Bau
.claude/skills/review-plan/          Projekt-Kopie; tests/test_project_skills_copy.py bekommt review-plan in REPO_DEV_SKILLS
.claude/skills/impl-plan/, .claude/skills/skill-forge/, .claude/skills/subagent-dev/   dieselben Änderungen und dieselbe Löschung wie in skills/, byte-gleich
.claude-plugin/marketplace.json      review-plan in der skills-Liste von evaluated-skills (Stand HEAD; Spec 20 schafft die Liste ab, siehe Open questions)
specs/Spec 00 – skill-foundation.md, README.md   Matrixzeile review-plan
docs/known-limits.md                 Abschnitt review-plan
docs/superpowers/reports/review-plan-report.md   Report mit „Was nicht gemessen wurde"
evals/review-plan/evals.json         fünf Evals, siehe unten
evals/fixtures/rp-small/, rp-missing-file/, rp-impact/, rp-ignored/   je fixture.json mit "git": true
tests/test_review_plan_check.py, tests/test_review_plan_parser_parity.py
```

`tests/test_plans_lint.py` bleibt unverändert: `_all_plans()` globt nur `*.md` direkt in
`docs/superpowers/plans/`, der Unterordner `reviews/` liegt außerhalb.

### Was `check_plan.py` prüft

Je Task liest es `**Files:**` (Verben `Create`, `Modify`, `Test`, `Delete`, `Rename`),
`**Interfaces:**` (`Consumes:`, `Produces:`, Präfixe `fn:`, `token:`, `file:`) und die
Befehle der Steps. Ein Befehl ist ein Backtick-Abschnitt in einem Step, der mit
`python`, `python3`, `pytest`, `bash`, `sh`, `node` oder `npx` beginnt; geprüft werden
seine Argumente, die wie ein Pfad aussehen (enthalten `/` und enden auf eine
Dateiendung). Geprüft wird gegen `git rev-parse HEAD`, im Ergebnis als `base`
vermerkt:

| Regel | Art | prüft |
| --- | --- | --- |
| `file-missing` | Befund | `Modify`-, `Delete`- oder `Rename`-Pfad existiert nicht und entsteht in keinem früheren Task |
| `file-exists` | Befund | `Create`-Pfad existiert schon und wird in keinem früheren Task gelöscht |
| `file-ignored` | Befund | `Create`- oder `Modify`-Pfad ist gitignoriert (`git check-ignore`) |
| `test-new` | Hinweis | `Test`-Pfad existiert nicht — wird angelegt? |
| `symbol-unknown` | Befund | ein `Consumes`-Symbol steht weder im Repo noch im `Produces` irgendeines Tasks des Plans; `fn:` per `ast` in Python-Dateien, sonst Textsuche; `file:` als Pfad. Die Reihenfolge ist Sache des Reviewers, weil Tier-0-Pläne den Eval-Task bewusst vor den Task stellen, der die Symbole produziert (`task-patterns.md`, „Evals zuerst bei Tier 0") |
| `command-path` | Befund | ein Pfad-Argument eines Befehls existiert nicht und entsteht weder in einem früheren noch im selben Task |
| `impact` | Folge | siehe unten |

**`impact` eng gefasst.** Für jeden `Modify`-Pfad: Dateien mit identischem Blob
(`git ls-tree -r HEAD`, Projekt-Kopien und Vendoring; leere Dateien ausgenommen), dazu
bei `.py` die Dateien, die das Modul importieren oder es per `load_script("<pfad>")`
laden (`tests/conftest.py` nimmt den Repo-Pfad, nicht den Stamm). Für jeden `Delete`-
oder `Rename`-Pfad zusätzlich jede Datei, die den Pfad wörtlich nennt, jede Datei, die
ihn ohne das führende `skills/` oder `.claude/skills/` nennt
(`impl-plan/references/x.md`), und jede Datei desselben Skill-Ordners oder seiner Kopie,
die ihn relativ nennt (`references/x.md`). Historische Ordner zählen nicht (`docs/superpowers/plans/`, `docs/superpowers/reports/`,
`specs/`). Dateien, die im Plan schon stehen, sind keine Folge. TS/JS-Importpfade und
Delphi-`uses` kommen hinzu, sind in diesem Repo aber ungemessen. Wörtliche Pfade bei
`Modify` sucht die Regel bewusst nicht: `docs/known-limits.md` steht in 101 Dateien
(`git grep -l -F`), und Anti-Zeremonie-Pläne aus impl-plan ändern genau diese Datei.

Was das Skript nicht kann, steht als `unchecked` mit Grund im Ergebnis, nie als
bestanden: kein Git (dann keine Regel `file-ignored`, kein `base`, kein `impact`), kein
`**Interfaces:**`-Block, kein erkannter Task. Zählstellen in Prosa („dreizehn Regeln")
und Verweise ohne Pfad („ein Befund im Reviewer-Prompt") findet es nicht; die sind
Sache des Reviewers.

**Schema von `check.json`** (in `references/checks.md` festgehalten, Schlüssel in dieser
Reihenfolge): `_meta` (skill, schema, generated), `plan`, `base`, `entries` — eine Liste
nur der Treffer, je Eintrag `rule`, `kind` (`finding`, `hint` oder `impact`), `task`
(Zahl), `path`, `detail` —, und `unchecked` (je `rule`, `reason`). Bei `impact` ist
`path` die betroffene Datei, `detail` nennt den geänderten Pfad des Tasks. Regeln ohne Treffer
stehen nirgends. Damit bindet ein Muster wie
`"rule":\s*"file-ignored",\s*"kind":\s*"finding"` nur an einen echten Befund.

### Ablauf

1. **Plan bestimmen** — Pfad aus dem Auftrag, sonst die neueste `.md` direkt unter
   `docs/superpowers/plans/`; die erste Ausgabezeile nennt ihn.
2. **Lint**, nur für Pläne mit der Kopfzeile von impl-plan: wenn `plan_to_tasks.py`
   erreichbar ist (`skills/subagent-dev/scripts/` im selben Repo, installiert
   `.claude/skills/subagent-dev/scripts/`), `lint` mit `--out
   .skills/cache/review-plan/lint.json`. Sonst „Lint ungeprüft — Skript nicht
   verfügbar". Pläne ohne diese Kopfzeile (etwa aus `superpowers:writing-plans`)
   bekommen keinen Lint; das Urteil sagt „Lint nicht anwendbar".
3. **Abgleich**: `python skills/review-plan/scripts/check_plan.py <plan> --out
   .skills/cache/review-plan/check.json`.
4. **Größenregel**: mindestens ein und höchstens zwei Tasks, kein Eintrag mit `kind`
   `finding` oder `impact`, kein Lint-Befund und kein `unchecked` außer „kein
   `**Interfaces:**`-Block" — dann kein Reviewer; das Urteil entsteht aus Lint und
   Abgleich und sagt „ohne Reviewer (kleiner Plan)". Fehlende Interfaces sperren die
   Regel nicht, weil Pläne aus `superpowers:writing-plans` den Block nicht kennen; sie
   stehen unter „Nicht geprüft". Ein Plan ohne erkannte Task oder ohne Git fällt nie
   unter die Größenregel.
5. **Reviewer** nach `references/reviewer-prompt.md`: ein Subagent mit frischem Kontext,
   der Plan, Spec, `check.json` und, falls vorhanden, `lint.json` bekommt, nie die
   Konversation. Auf Wunsch des Nutzers läuft er auf einem anderen Modell. Er prüft die
   sechs Kategorien des bisherigen Prompts, misst jede Behauptung über das Repo selbst
   nach, beantwortet jede Folge aus `check.json`, prüft, ob jeder Task seine Eval-IDs
   tatsächlich baut, sucht Verweise ohne Pfad und Zählstellen, und baut Tasks mit Folgen
   oder mit Änderungen an geteilten Tests, Registern oder Manifesten in einer Kopie nach
   (Kopie unter einem Temp-Pfad, nur die Änderung, die die Folge auslöst, dann die
   betroffenen Tests).
6. **Nachmessen**: Die tragenden Befunde des Reviewers prüft der Hauptagent selbst nach,
   bevor sie ins Urteil gehen; abgelehnte Befunde stehen mit Grund darin.
7. **Urteil** nach `assets/review-template.md` in `reviews/` neben dem Plan: Zeile
   `Urteil:` mit `freigegeben`, `freigegeben mit Auflagen` oder `nicht freigegeben`;
   Befunde mit Beleg-Befehl; eine Zeile je Folge mit „im Plan nachziehen" oder
   „unbetroffen, weil …"; „Nicht geprüft". Danach `python
   skills/review-plan/scripts/check_plan.py audit <urteil> --check
   .skills/cache/review-plan/check.json`. Übergabe: Urteil und Pfad; bei „nicht
   freigegeben" zurück an impl-plan.

**Urteilsregeln.** `nicht freigegeben` bei einem Befund aus `check_plan.py`, einem
Lint-Befund, einem blockierenden Befund des Reviewers, einer Folge ohne Antwort oder
einer Folge mit „im Plan nachziehen" — dann fehlt dem Plan ein Task, und er geht an
impl-plan zurück. `freigegeben mit Auflagen` bei wichtigen Befunden ohne Blockade, bei
`unchecked` außer fehlenden Interfaces (etwa kein Git), bei „Nachbau ungeprüft" und bei
„Lint ungeprüft" für einen Plan mit impl-plan-Kopfzeile; die Auflage nennt den
nachzuholenden Check. Sonst `freigegeben`. `audit` meldet ein Urteil, das
`freigegeben` oder `freigegeben mit Auflagen` sagt, obwohl `check.json` einen Eintrag
mit `kind` `finding` trägt oder eine Folgezeile „im Plan nachziehen" sagt, und jede
Folge aus `check.json` ohne Zeile, die ihren Pfad und eine der beiden Antworten („im
Plan nachziehen", „unbetroffen, weil …") enthält.

### Contract

- **Gemessen, nicht geglaubt.** Jede Repo-Aussage im Urteil nennt ihren Befehl; was nicht
  gemessen werden konnte, steht unter „Nicht geprüft".
- **Der Plan bleibt unverändert.** Die Skill schreibt nur das Urteil unter `reviews/`
  sowie `check.json` und `lint.json` unter `.skills/cache/review-plan/`.
- **Ein übersprungener Check meldet nie Erfolg.** Fehlt Lint, Git oder ein
  Interfaces-Block, steht das im Urteil unter „Nicht geprüft"; `check.json` führt die
  Regel als `unchecked`. Wie weit das das Urteil senkt, sagen die Urteilsregeln.
- **Folgen werden beantwortet.** Jede Datei aus `impact` bekommt im Urteil eine Zeile;
  `audit` meldet fehlende (G2).
- **Anti-Zeremonie-Fall:** Ein Plan mit ein oder zwei Tasks ohne Befund, ohne Folge und
  ohne `unchecked` (fehlende Interfaces ausgenommen) bekommt Lint (falls anwendbar), Abgleich und eine kurze Urteilsdatei —
  keinen Reviewer, keine Nachbau-Kopie.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| Implementierungsplan schreiben | **impl-plan** (Specs dieser Sammlung), superpowers:writing-plans (fremde Repos, bis Spec 23) | review-plan — schreibt und ändert keinen Plan |
| Plan zerlegen, parallelisieren, nach dem Bau abnehmen | **subagent-dev** (`generate`, `verify`) | review-plan — prüft vor dem Bau |
| Spec vor dem Plan prüfen | skill-forge, Schritt 1 (`spec-reviewer-prompt.md`) | review-plan — prüft Pläne, keine Specs |
| Code eines Diffs prüfen | `/code-review`, superpowers:requesting-code-review | review-plan — prüft den Plan, nicht den Code |

Rückverweise beim Bau: `impl-plan` (Schritt 6 und Abgrenzung) und `subagent-dev`
(Abgrenzung) nennen review-plan wörtlich.

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_file_rules` | `tests/test_review_plan_check.py` | `file-missing`, `file-exists`, `Create` nach `Delete` erlaubt, `Test`-Pfad fehlt → Hinweis |
| `test_gitignored_create_and_no_git` | dito | gitignorierter `Create`-Pfad → Befund; ohne Git → `unchecked`, nie bestanden |
| `test_symbol_rules` | dito | `fn:` per `ast` gefunden; in einem späteren Task produziert → kein Befund; `token:` per Text; unbekannt → Befund; ohne Interfaces → `unchecked` |
| `test_command_paths` | dito | Befehl mit fehlendem Skript → Befund; Skript aus früherem oder demselben Task → nichts; Backtick ohne Befehlswort → ignoriert |
| `test_impact_scan` | dito | byte-gleiche Kopie, Python-Import, `load_script("<pfad>")`, wörtlicher Pfad bei `Delete`, Pfad ohne `skills/` in einem anderen Skill-Ordner (`impl-plan/references/x.md`), relativer Pfad im selben Skill-Ordner → Folge; relativer Pfad gleichen Namens in einem anderen Skill-Ordner, leere Datei mit gleichem Blob, Treffer unter `specs/`, wörtlicher Pfad bei `Modify`, Datei schon im Plan → keine Folge |
| `test_check_json_schema` | dito | Schlüsselreihenfolge, `_meta` mit skill, schema, generated; `base` mit HEAD; Regeln ohne Treffer fehlen in `entries`; bei `impact` ist `path` die betroffene Datei |
| `test_audit` | dito | `freigegeben` und `freigegeben mit Auflagen` trotz Befund → gemeldet; trotz Folge „im Plan nachziehen" → gemeldet; Folge ohne Zeile oder nur unter „Nicht geprüft" → gemeldet; sauberes Urteil → nichts |
| `test_short_verdict_fits_limit` | dito | ein Urteil nach `assets/review-template.md` für einen kleinen Plan ohne Befund, ohne Folge und ohne Interfaces bleibt unter der Grenze von Eval 1 (25 Zeilen) |
| `test_parser_parity` | `tests/test_review_plan_parser_parity.py` | für jeden Plan außerhalb `LEGACY_PLANS`: dieselben Tasks und Pfade wie `plan_to_tasks.py` (das Verb speichert `plan_to_tasks.py` nicht) |

### Evals

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-small-clean-plan-gets-no-reviewer` | contract | `rp-small` | `file_exists` und `artifact_header` auf `docs/plans/reviews/small.review.md`; `file_matches` dort `^Urteil: freigegeben$` und `(?i)ohne Reviewer`; `file_max_lines` dort 25; `file_unchanged` `docs/plans/small.md` | Urteilsdatei mit Kopfzeile, die Größenregel-Zeile und die Kürze entstehen nur durch die Skill; ob tatsächlich kein Subagent lief, misst der Eval nicht |
| 2 | `missing-file-denies-release` | contract | `rp-missing-file` | `file_matches` `.skills/cache/review-plan/check.json` auf `"rule":\s*"file-missing",\s*"kind":\s*"finding"`; `file_matches` `docs/plans/reviews/feature.review.md` auf `^Urteil: nicht freigegeben$`; `file_matches` dort auf `src/legacy_export.py`; `file_unchanged` `docs/plans/feature.md` | `check.json` schreibt nur `check_plan.py`, und nur ein echter Treffer steht in `entries`; ein Basismodell könnte die fehlende Datei bemerken, aber nicht in diesem Artefakt |
| 3 | `unplanned-impact-is-answered` | contract | `rp-impact` | `file_matches` `check.json` auf `"kind":\s*"impact",\s*"task":\s*\d+,\s*"path":\s*"tests/test_report.py"`; `file_matches` `docs/plans/reviews/feature.review.md` auf `tests/test_report\.py.*(im Plan nachziehen\|unbetroffen)` | die Fixture ändert `src/report.py`, `tests/test_report.py` importiert es und steht in keinem Task; nur die Folgenanalyse schreibt den Eintrag, und die Urteilsregel verlangt eine Antwortzeile, nicht nur eine Erwähnung |
| 4 | `gitignored-create-is-reported` | contract | `rp-ignored` | `file_matches` `check.json` auf `"rule":\s*"file-ignored",\s*"kind":\s*"finding"`; `file_matches` `docs/plans/reviews/feature.review.md` auf `^Urteil: nicht freigegeben$`; `file_matches` dort auf `build/report.json` | `git check-ignore` läuft nur im Skript, und das Urteil muss den ignorierten Pfad nennen |
| 5 | `routing-plan-review-without-skill-name` | contract | `rp-small` | `file_exists` `docs/plans/reviews/small.review.md` | stochastisch: ein roter Lauf zeigt, dass die Description auf die Frage nicht anspringt oder eine global installierte Skill gewinnt (im Harness sichtbar, darunter `code-review`; known-limits, „Isolation"); impl-plan konkurriert nur, wenn sie beim Nutzer global installiert ist; ein grüner Lauf beweist nichts |

Prompts: 1 „Prüf den Plan docs/plans/small.md mit review-plan.", 2 „Review den Plan
docs/plans/feature.md mit review-plan.", 3 und 4 wie 2, 5 „Ist der Plan in
docs/plans/small.md baureif?". Die Fixtures liegen als Git-Repos mit `docs/plans/`,
einer kurzen Spec mit Eval-Tabelle und dem Code, auf den die Pläne zeigen; ihre Pläne
tragen keine impl-plan-Kopfzeile und keinen `**Interfaces:**`-Block (Form von
`superpowers:writing-plans`), der Lint ist also nicht anwendbar, und kein Eval hängt an
ihm. Im Muster von Eval 3 steht in `evals.json` ein `|`; `\|` maskiert es nur für die
Tabelle. `rp-small` hat zwei Tasks und prüft damit auch, dass fehlende Interfaces die
Größenregel nicht sperren. `rp-ignored` bringt eine `.gitignore` mit `build/` mit, die der Harness
beim `git add -A` beachtet. Die Fixtures stehen nicht unter `docs/superpowers/plans/`
und berühren `tests/test_plans_lint.py` nicht.

## Alternatives considered

**Nur den Reviewer-Prompt von impl-plan schärfen.** Kein neues Skript, keine neue Skill.
Verworfen: ohne mechanischen Abgleich sucht der Reviewer Kopien und Importe jedes Mal
von Hand, ohne Urteilsdatei bleibt das Ergebnis im Chat, und für Pläne aus fremden Repos
gibt es keinen Einstieg. Hätte gewonnen, wenn Pläne nur aus impl-plan kämen; der
gemessene Nullbefund an den alten Plänen spricht in diese Richtung und steht deshalb in
Open questions.

**Der Abgleich als Unterbefehl von `plan_to_tasks.py`.** Ein Parser statt zwei.
Verworfen, weil das Skript im Eval-Workspace dieser Skill fehlt (known-limits,
`impl-plan`) und in fremden Repos ohne subagent-dev nicht da ist. Der Paritätstest hält
die beiden Parser zusammen. Gewinnt, wenn der Harness Nachbar-Skills mitinstallieren
kann.

**`impact` als Volltextsuche nach jedem geänderten Pfad.** Im Review gemessen: 30 bis
173 Folgen je Plan an den fünf Plänen außerhalb von `LEGACY_PLANS`, und die
Anti-Zeremonie-Form von impl-plan (`ANTI_CEREMONY_PLAN` in
`tests/test_impl_plan_evals_schema.py`) hätte die Größenregel nie erreicht. Verworfen
zugunsten der engen Fassung.

**Das Urteil direkt neben dem Plan.** Macht `tests/test_plans_lint.py` rot, weil
`_all_plans()` jede `.md` im Planordner als Plan liest (im Review in einer Kopie
gemessen), und Schritt 1 fände als „neuesten Plan" oft ein Urteil. Verworfen zugunsten
von `reviews/`.

**Der Reviewer korrigiert den Plan selbst.** Schneller, aber Prüfer und Autor
verschmelzen, und der nächste Lauf prüft die eigene Korrektur. Verworfen.

**Alle Tasks in einer Kopie nachbauen.** Das wäre der Bau selbst. Verworfen zugunsten
gezielter Nachbauten der Tasks mit Folgen.

**Die Skill nur per Slash-Befehl aufrufbar machen (`disable-model-invocation`).** Spart
die Description im Kontext. Verworfen: impl-plan soll direkt übergeben können, und der
Schlüssel hängt an der Liste `CLAUDE_CODE_ONLY` aus Spec 21, die parallel bearbeitet
wird.

**Ein Hook, der `subagent-dev` ohne Urteil anhält.** Kein irreversibler Schaden, also
kein Grund für G3 (Spec 00 §4). Verworfen.

## Out of scope

Pläne schreiben oder korrigieren (impl-plan; für fremde Repos Spec 23). Specs prüfen
(skill-forge). Code prüfen (`/code-review`). Zählstellen in Prosa und Verweise ohne Pfad
mechanisch finden. Pläne ohne Task-Struktur (Freitext) mechanisch prüfen — dort meldet
das Skript `unchecked`, die Größenregel greift nicht, und der Reviewer arbeitet ohne
Abgleich. CI-Anbindung. Die Zuordnung zu einem der Plugins aus Spec 20.

## Open questions

*Annahme:* Größenregel „ein oder zwei Tasks, kein Befund, keine Folge, kein `unchecked`"
— die Anti-Zeremonie-Form von impl-plan hat zwei Tasks und fällt darunter. Widersprich,
falls nein.

*Annahme:* Das Urteil liegt unter `<plan-ordner>/reviews/` und wird committet —
widersprich, falls es unter `docs/superpowers/reports/` liegen soll.

*Annahme:* Lint ungeprüft bei einem Plan mit impl-plan-Kopfzeile ergibt höchstens
`freigegeben mit Auflagen`; bei Plänen ohne diese Kopfzeile ist der Lint nicht
anwendbar und verhindert `freigegeben` nicht.

*Annahme:* Plugin. Bis Spec 20 gebaut ist, gehört review-plan zu `evaluated-skills`. Danach
liegt `evaluated-dev` nahe (Pläne aus fremden Repos, subagent-dev liegt dort), kostet aber
Description-Budget in einem Plugin mit `defaultEnabled: true` (Spec 20: 6 318 Zeichen);
`evaluated-meta` läge neben impl-plan, ist aber außerhalb dieses Repos aus. Die Entscheidung
und die Zeile in der Tabelle von Spec 20 gehören zu Spec 20.

Der Nutzen des mechanischen Teils an Plänen aus impl-plan ist nicht belegt: null
Befunde und null Folgen an den Altplänen, fünf echte Folgen an der Dateiliste dieser
Spec (Wegwerfskript, nicht im Repo; `test_impact_scan` bildet die Fälle nach).
Der erste echte Einsatz (siehe Next steps) ist die Messung; findet der Abgleich dort
nichts, was der Reviewer nicht ohnehin findet, gewinnt die erste Alternative.

Wie viele Folgen die enge `impact`-Regel in einem großen fremden Repo meldet, ist
ungemessen; TS/JS-Importe und Delphi-`uses` sind ungemessen. Zu viele Folgen machen die
Größenregel wirkungslos und das Urteil lang.

Spec 20 ändert dieselben Dateien `skills/skill-forge/references/reviewer-prompt.md` und
`skills/impl-plan/SKILL.md` (Spec 20, Skill-Struktur) und führt generierte Kopien unter
`plugins/<plugin>/skills/` samt `scripts/sync_plugins.py` ein. Der Bau von Spec 26 folgt
deshalb nach dem von Spec 20, nimmt dessen Stand als Basis, und der Plan ergänzt die
Dateiliste um die dann nötigen Kopien und den Manifest-Eintrag.

*Annahme:* Der Nachbau in einer Kopie braucht ein Temp-Verzeichnis mit Schreibrecht und
eine lauffähige Testsuite; fehlt beides, steht im Urteil „Nachbau ungeprüft".

Der Parser-Paritätstest deckt nur die fünf Pläne außerhalb von `LEGACY_PLANS` ab (21
Pläne, 16 eingefroren; `tests/test_plans_lint.py`) und nur Tasks und Pfade; ob der
eigene Parser Pläne aus `superpowers:writing-plans` in fremden Repos genauso liest, ist
ungemessen.

Wie der Reviewer auf einem anderen Modell läuft, hängt am Harness (in Claude Code das
`model`-Feld des Agent-Werkzeugs); in anderen Umgebungen läuft er auf demselben Modell.

Die Evals sind ungefahren, bis der Harness beim Nutzer läuft (known-limits, „Betrieb").

## Next steps

Plan mit `impl-plan` (16) und Bau nach `skill-forge` (17) Schritt 3 bis 7, nach dem Bau
von Spec 20. Erster echter Einsatz am Plan für Spec 20, sobald er geschrieben ist — mit
dem Vergleich, was Abgleich und Reviewer jeweils fanden.
