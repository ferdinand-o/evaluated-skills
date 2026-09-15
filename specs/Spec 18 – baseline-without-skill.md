# Spec 18: Baseline ohne Skill — `--without-skill` im Harness, gelesen von skill-forge

Skill-Spezifikation · Zyklus 18 · Entscheidung: ein Flag am Runner plus eine Sichtbarkeitsprüfung aus dem `system.init`-Ereignis; kein Artefakt, kein neuer Eval, kein Contract-Satz · Abgeglichen mit Spec 00 · Überarbeitet nach unabhängigem Review

## Problem

Die Diskriminator-Frage („Könnte das Basismodell ohne diese Skill dieselbe Ausgabe
erzeugen?", `skills/skill-forge/references/evals.md`) wird je Eval *beantwortet*, nie
*gemessen*. Gemessen am 2026-09-15 über `evals/*/evals.json`: 97 Evals in 18 Dateien;
18 davon tragen das Wort „Diskriminator" in `notes` (explain 8, impl-plan 5, skill-forge
5), 79 nicht. Wer die Antwort schreibt, hat die Assertion geschrieben — derselbe
Selbst-Review, den `docs/assessment-brainstorming.md` bei Specs als wirkungslos
gemessen hat. Der Harness kennt keinen Lauf ohne installierte Skill: `evalkit/
workspace.py::prepare()` verlangt ein Skill-Verzeichnis mit `SKILL.md` und kopiert es
immer nach `.claude/skills/<name>/`.

Die Forderung steht viermal im Repo, gebaut ist sie nirgends: Spec 17 (Constraints,
Vorab-Entscheidung 3; Out of scope, erster Punkt), `references/evals.md` („Baseline ohne
Skill — die Forderung"), `docs/known-limits.md` (Abschnitt `## skill-forge`, „Gefordert,
nicht gebaut") und `docs/assessment-writing-skills-writing-plans.md` §4.4 Punkt 4.

Zwei Messungen vom 2026-09-15, auf denen der Zuschnitt steht:

- **Ein Lauf ohne Installation ist nicht automatisch ein Lauf ohne Skill.** 17 der 21
  Ordner unter `skills/` haben im Nutzerprofil (`~/.claude/skills/synced/…`) eine
  gleichnamige Skill (gezählt per Verzeichnisvergleich; ohne Gegenstück: cad-parts,
  explain, impl-plan, skill-forge). Ob der Agent sie sieht, entscheidet die CLI, nicht
  der Runner.
- **Die CLI sagt, was der Agent sieht.** Ein `claude -p`-Lauf (2.1.272, leeres
  Verzeichnis, `--setting-sources project --strict-mcp-config`, `--output-format
  stream-json`) liefert unter den ersten Ereignissen `{"type":"system","subtype":"init",…}`
  — im gemessenen Lauf als drittes, nach `active_goal` und `autocompact_state` — mit
  dem Feld `skills`: hier 19 Einträge (`deep-research`, `dataviz`, `code-review`,
  `debug`, `verify`, …), **keine** der 17 gleichnamigen Profil-Skills. Der Runner liest
  dieses Feld heute nicht (`evalkit/dispatch.py::assistant_text` überspringt alles
  außer `assistant`-Ereignissen).

## Constraints

- **Tier 1** (Spec 00 §3): `evalkit` ist Stdlib („Tier 1: nur Stdlib", Docstring von
  `run_evals.py`); nichts kommt hinzu.
- **Gate-Grade:** Die SKILL.md von `skill-forge` *verlangt* den Baseline-Lauf in Schritt
  5 (G1). Der Runner *meldet* (G2): Exit-Code und Report-Zeile je Eval, ein
  unmöglicher Baseline-Lauf als Harness-Fehler, nie als Ergebnis. Kein Hook — nichts
  hier blockiert einen Commit.
- **Kein Contract-Satz, kein neuer Eval für skill-forge — aber `evals_due: true`, und
  die fünf Evals werden gefahren.** `lint_skill.py::evals_due` legt die neun Patterns
  der eigenen `evals/skill-forge/evals.json` (darunter `(?i)diskriminator`,
  `"id": "anti-ceremony-`, `expected_output`) auf jede geänderte Zeile im ganzen
  Skill-Ordner, alte wie neue (`changed_lines`: `git diff <rev> -- skills/skill-forge`).
  Der Abschnitt „Baseline ohne Skill — die Forderung" in `references/evals.md` beginnt
  mit „Die Diskriminator-Frage wird heute *beantwortet*" (Zeile 107); ihn umzuschreiben
  trifft `(?i)diskriminator` — nachgemessen im Klon: `evals_due: True`. Die Spec nimmt
  das an, statt den Satz zu umschreiben, bis der Lint schweigt (das wäre die
  Rationalisierung aus `subagent-dev`s Tabelle): Die fünf Evals werden nach dem Bau
  gefahren, außerhalb des Harness wie beim dritten Lauf im Report, und der Report
  nennt den Grund aus `lint.json` wörtlich. Der Rückverweis in der Abgrenzung kommt
  als eigene Zeile hinter den skill-creator-Absatz, damit Zeile 100 (`expected_output`)
  unberührt bleibt und `evals_due_reason` genau den einen erwarteten Treffer nennt.
- **Abwärtskompatibel:** Ohne `--without-skill` und ohne `skills`-Feld im
  `init`-Ereignis ändert sich kein Verdikt. Die bestehenden Fake-CLI-Tests
  (`tests/test_runner.py`, Shell-Skripte ohne stream-json) bleiben grün, ohne Änderung.
- **SKILL.md ≤ 150 Zeilen:** `skills/skill-forge/SKILL.md` hat 107; die Ergänzung sind
  drei bis vier Zeilen.
- **Ablage nach `README.md` („Aufbau"):** Harness-Code unter `evalkit/`, der Runner
  als `run_evals.py` in der Wurzel (Spec 00 §2 nennt noch `evals/run_evals.py` — der
  Satz, den diese Spec dort ergänzt, zieht den Pfad nach), Tests unter `tests/`,
  Doktrin unter `skills/skill-forge/`. Kein neues Artefakt auf Platte — der Runner
  schreibt heute nichts (known-limits, „Kein Transcript wird persistiert"), und das
  bleibt außerhalb dieser Spec.
- **Ein Harness-Lauf ist hier nicht messbar:** `dispatch.py` setzt
  `bypassPermissions`, die CLI verweigert das unter uid 0 (known-limits, „Betrieb").
  Der Nachweis sind Unit-Tests mit Fake-CLI; der erste echte Lauf findet beim Nutzer
  statt.

## Approach

**Eiserne Regel:** *Kein Eval-Ergebnis ohne Sichtbarkeitsbefund.* Der Runner liest aus
dem `init`-Ereignis, welche Skills der Agent sah. Ein Lauf ohne Skill, in dem die
Skill trotzdem sichtbar war, und ein Lauf mit Skill, in dem sie fehlte, sind
Harness-Fehler (Exit 2) — nie PASS, nie FAIL. Fehlt das Feld, sagt der Report
„Sichtbarkeit ungeprüft" und das Verdikt bleibt, wie es heute ist.

### Skill-Struktur

```
skills/skill-forge/
├── SKILL.md                         Schritt 5: Baseline-Lauf nach dem zweiten Lauf; Lesart „grün ohne Skill = misst nichts"
├── references/evals.md              „Baseline ohne Skill": von der Forderung zur Anleitung — Aufruf, Lesart, was danach mit dem Eval passiert
├── assets/skill-template/report.md  „Was gemessen wurde": Zeile für die Baseline; „Was nicht gemessen wurde": die Baseline, wenn sie nicht lief
└── scripts/lint_skill.py            Tier 1, unverändert

run_evals.py, evalkit/runner.py      --without-skill; Sichtbarkeitsprüfung; Report-Modus
evalkit/dispatch.py                  visible_skills() aus dem init-Ereignis; Transcript.skills
evalkit/workspace.py                 prepare(skill_dir=None) installiert nichts
evalkit/report.py                    Baseline-Markierungen und Exit-Code-Umkehr
tests/test_dispatch.py, test_workspace.py, test_runner.py, test_report.py
specs/Spec 00 – skill-foundation.md  §2: ein Satz zur Baseline
README.md, docs/known-limits.md      Aufruf; Abschnitt skill-forge und „Isolation" nachziehen
```

### Ablauf

Im Harness, je Eval mit `--without-skill`:

1. `prepare(workdir, None, fixture)` — Fixture wie bisher, kein Skill-Ordner unter
   `.claude/skills/`. Bringt die Fixture selbst einen mit, bleibt er; Schritt 3 fängt
   das.
2. Derselbe Prompt, derselbe Judge, dieselbe Baseline (Snapshot) wie mit Skill.
3. `Transcript.skills` aus dem `init`-Ereignis — der Runner sucht im Stream nach
   `type: system, subtype: init`, nicht in der ersten Zeile; geprüft wird nur das
   Transcript des Eval-Agenten, nie das des Judge (`judge()` läuft über denselben
   `run_agent` in einem leeren Verzeichnis). Enthält es den Skill-Namen: Ergebnis
   `SKIP — Baseline unmöglich: <name> ohne Installation sichtbar (Profil, Plugin oder
   Fixture)`, Exit 2. Fehlt das Feld: Zusatz „Sichtbarkeit ungeprüft", weiter mit 4.
4. `grade()` wie bisher. Der Report markiert `[GRÜN OHNE SKILL] <id> — misst nichts`
   und `[ROT OHNE SKILL] <id>`; die Summenzeile zählt beide. Exit 0, wenn kein Eval
   ohne Skill grün war; Exit 1, sobald einer grün war; Exit 2 bei Harness-Fehler.

Ohne `--without-skill` gilt dieselbe Prüfung gespiegelt: Fehlt der Skill-Name im
`skills`-Feld, ist der Lauf `SKIP — Skill nicht sichtbar (Installation oder
Frontmatter?)`, Exit 2. Das fängt genau die Klasse „Skill wurde nie geladen": ein
Frontmatter, das die CLI nicht parst (known-limits, `## skill-forge`, „Der Lint parst
kein YAML": `impl-plan` und `debug-ledger` luden so nicht), eine fehlgeschlagene
Installation. Es fängt **nicht** die Fälle aus known-limits „Isolation" — dort war die
getestete Skill sichtbar, und eine fremde fing den Prompt ab oder erledigte die
Arbeit. Fehlt das Feld, bleibt alles wie heute.

In `skill-forge`, Schritt 5, nach „Vor jeder Fix-Runde ein zweiter Lauf": derselbe
Aufruf mit `--without-skill`. Ein Eval, der ohne Skill grün ist, wird umgebaut oder
gestrichen (`references/evals.md`), nie weichgespült; der Report nennt je Eval beide
Läufe. Die Lesart ist asymmetrisch wie bei Routing-Evals: **ein grüner Lauf ohne Skill
zeigt die Lücke, ein roter beweist nichts** — Stichprobe (known-limits, „Ein
Eval-Ergebnis ist eine Stichprobe").

### Contract

- **`--without-skill` fährt denselben Eval ohne Installation** — gleicher Prompt,
  gleiche Fixture, gleicher Judge. Mechanismus: `prepare(skill_dir=None)`.
- **Sichtbarkeit ist ein Befund, kein Default.** `visible_skills()` liefert die Menge
  aus dem `init`-Ereignis oder `None`; `None` heißt „ungeprüft" im Report, nie „nicht
  sichtbar". Ein Fake-CLI ohne stream-json erzeugt `None`.
- **Grün ohne Skill ist Exit 1.** Der Baseline-Modus kehrt die Bedeutung des
  Exit-Codes um und sagt es in der Summenzeile („2 grün ohne Skill — messen nichts").
- **Ein übersprungener Lauf meldet nie Erfolg.** Baseline unmöglich und Skill nicht
  sichtbar sind `skipped=True` mit dem Grund in `failures`, Exit 2 — wie heute Timeout
  und Schema-Fehler (`exit_code` liefert 2 nur bei `skipped` *und* `failures`,
  `evalkit/report.py`; ein Grund nur in `note` gäbe Exit 0).
- **Anti-Zeremonie-Fall:** Ein geänderter Satz in einer SKILL.md (`evals_due: false`)
  löst keinen Baseline-Lauf aus; die Baseline gehört zu Schritt 5 und läuft nur, wenn
  Evals fällig sind oder die Skill neu ist. Ein Skill, dessen Evals alle rot ohne Skill
  sind, bekommt eine Zeile im Report und sonst nichts.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| „misst dieser Eval etwas?" — Baseline ohne Skill fahren | **skill-forge** Schritt 5 mit `run_evals.py --without-skill` | skill-creator (eigener Harness: Subagenten mit und ohne Skill, `aggregate_benchmark.py` rechnet `with_skill` gegen `without_skill` — anderes Schema, außerhalb `evalkit`); impl-plan (16) prüft Coverage der Eval-IDs im Plan, nicht ihre Schärfe; subagent-dev (09) `verify` nimmt Tasks ab, keine Evals |

Rückverweise beim Bau: `impl-plan` und `subagent-dev` nennen `skill-forge` bereits;
`skill-forge`s Abgrenzung nennt `skill-creator` mit dem Satz zu seinem Eval-Schema —
dort kommt der Halbsatz „seine Baseline-Läufe sind Subagenten, nicht der Harness" dazu.

### Tests (Harness)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_visible_skills_reads_init_event` | `tests/test_dispatch.py` | `skills`-Feld → Menge, auch hinter führenden Fremd-Ereignissen (`active_goal`, `autocompact_state`); ohne `init`-Ereignis → `None`; kaputte Zeilen übersprungen |
| `test_prepare_without_skill_installs_nothing` | `tests/test_workspace.py` | `prepare(dest, None, fixture)`: kein `.claude/skills/`, Baseline ohne diesen Präfix |
| `test_without_skill_visible_skill_is_harness_error` | `tests/test_runner.py` | Fake-CLI schreibt ein `init`-Ereignis mit dem Skill-Namen → `skipped`, Grund nennt „Baseline unmöglich" |
| `test_without_skill_grades_when_skill_absent` | `tests/test_runner.py` | `init`-Ereignis ohne den Namen → `grade()` läuft, Note „ohne Skill" |
| `test_with_skill_missing_from_init_is_harness_error` | `tests/test_runner.py` | Normalmodus, Name fehlt im Feld → `skipped`, Exit 2 |
| `test_without_skills_field_verdict_is_unchanged` | `tests/test_runner.py` | Fake-CLI ohne stream-json → Verdikt wie heute, Note „Sichtbarkeit ungeprüft" |
| `test_baseline_report_marks_and_exit_code` | `tests/test_report.py` | `EvalResult.baseline=True`: `[GRÜN OHNE SKILL]`/`[ROT OHNE SKILL]`, Summenzeile, Exit 1 bei grün, 0 bei nur rot, 2 bei skip |

### Evals

Keine neue Eval-Zeile: Das Eval-Schema kann den Harness nicht fahren (kein
`evalkit` im Workspace, den `prepare()` anlegt), und die Ergänzung an `skill-forge`
ändert weder Frontmatter noch Contract. Gefahren werden trotzdem alle fünf bestehenden
Evals von skill-forge, weil `evals_due: true` erwartet ist (Constraints) — außerhalb
des Harness, zwei Läufe je Eval wie im dritten Lauf des Reports.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-one-sentence-change-lints-only` | contract | `sf-existing` (unverändert) | unverändert: `file_exists lint.json`, `file_matches "evals_due": false`, `file_unchanged evals.json` und Report | unverändert — bleibt der Pflicht-Eval; er ist zugleich der Anti-Zeremonie-Fall dieser Spec: ein Satz löst keinen Baseline-Lauf aus |
| 2–5 | `token-change-makes-evals-due`, `gate-word-without-hook-is-reported`, `missing-anti-ceremony-eval-is-reported`, `routing-new-skill-gets-house-evals` | contract | unverändert | unverändert | unverändert — werden gefahren, nicht geändert |

Erste Kandidaten für einen echten Baseline-Lauf, sobald der Harness beim Nutzer läuft:
die 79 Evals ohne Diskriminator-Notiz, beginnend bei den drei Evals mit ID-Präfix
`routing-` (`evals/impl-plan`, `evals/skill-forge`, `evals/testing-strategy`, gezählt per
grep) — dort ist Rot ohne Skill die Erwartung und Grün der Befund.

## Alternatives considered

**`--skills-dir` mit leerer `SKILL.md`** — funktioniert heute ohne Code:
`mkdir -p /tmp/leer/<name> && touch /tmp/leer/<name>/SKILL.md && python run_evals.py
--skill <name> --skills-dir /tmp/leer`; `prepare()` verlangt nur, dass die Datei
existiert, und die leere Skill erscheint nicht im `skills`-Feld (Reviewer-Messung,
2.1.272: nur in `slash_commands`) — als Baseline taugt der Trick also. Verworfen, weil
der Runner nicht weiß, dass es einer ist: Der Report sagt `PASS` für einen Eval, der
nichts misst, Exit 0, keine Sichtbarkeitsprüfung, kein Wort „ohne Skill" im Report.
Gewonnen hätte er, wenn es um einen einmaligen Blick statt um Schritt 5 ginge.

**`--baseline` als Doppellauf** — je Eval mit und ohne Skill in einem Aufruf, drei
Spalten (mit / ohne / unterscheidet). Verworfen: verdoppelt die Kosten je Aufruf, obwohl
der Lauf mit Skill in Schritt 5 schon stattgefunden hat; die Gegenüberstellung im
Report schreibt der Bauende aus zwei Summenzeilen. Gewinnt, sobald der Report
mechanisch entstehen soll.

**skill-creators Weg** — Subagenten mit und ohne Skill, Grader, `aggregate_benchmark.py`
mit Pass-Rate-Delta. Verworfen: anderes Eval-Schema (`expected_output`, `assertions`),
Ordnerbaum `with_skill/`/`without_skill/`, kein `evalkit`. Die Idee ist übernommen, der
Code nicht.

**Profil isolieren per `CLAUDE_CONFIG_DIR`** — ein leeres Konfigurationsverzeichnis mit
kopierten Anmeldedaten. Verworfen nach Messung: Unter `--setting-sources project` sah
der Agent keine der 17 gleichnamigen Profil-Skills, die Isolation ist für die Baseline
also nicht nötig; und der Versuch, `HOME` umzubiegen, endete bei „Not logged in"
(known-limits, „Isolation"). Gewinnt, falls sich die Messung auf dem Rechner des
Nutzers nicht wiederholen lässt — siehe Open questions.

**Ein Feld `baseline: true` je Eval im Schema** — Opt-in pro Eval. Verworfen: Das Flag
gilt für alle Evals gleich, und ein Opt-in lädt zu „dieser braucht das nicht" ein;
`evalkit/schema.py` bleibt unberührt.

**Die Antwort in `notes` genügt** (Status quo). Verworfen: 79 von 97 Evals haben sie
nicht, und wo sie steht, hat sie derselbe Kontext geschrieben wie die Assertion.

## Out of scope

- `--eval`-Filter, `--resume`, Persistieren des Transcripts, `--permission-mode`
  (alle in known-limits, „Betrieb") — jeweils eigene, kleine Änderung.
- Das Trigger-Eval-Set aus `references/evals.md` fahren.
- Die 79 Evals ohne Diskriminator-Notiz nachziehen. Register-Prinzip wie in Spec 17:
  Ein Eval wird umgebaut, wenn ein Baseline-Lauf ihn grün zeigt, nicht vorher.
- Pass-Rate-Deltas oder Benchmarks über mehrere Läufe (skill-creator).
- Ein Artefakt des Runners auf Platte (`--out`), auch wenn `docs/artifact-header.md`
  dafür die Kopfzeile hätte.

## Open questions

- *Annahme:* Das Feld `skills` im `init`-Ereignis ist stabil. Gemessen mit CLI 2.1.272;
  fehlt es in einer anderen Version, bleibt das Verdikt wie heute und der Report sagt
  „ungeprüft" — widersprich, falls das ein Harness-Fehler sein soll.
- *Annahme:* Die Sichtbarkeitsprüfung gilt auch für Läufe mit Skill (fehlender Name →
  Exit 2). Das ändert, was ein heute falsch roter oder falsch grüner Lauf meldet —
  widersprich, wenn sie nur die Baseline absichern soll.
- *Annahme:* Exit-Code-Umkehr im Baseline-Modus statt eines eigenen Codes. Ein
  CI-Aufruf mit `--without-skill` wird damit rot, sobald ein Eval nichts misst —
  widersprich, wenn Grün ohne Skill nur eine Warnung sein soll.
- *Annahme:* Kein Artefakt, keine Kopfzeile; der Report bleibt stdout.
- *Annahme:* Vier Schnittstellen, die die Tests brauchen: `run_one()` bekommt den
  Skill-Namen und `without_skill` als Parameter; `EvalResult` bekommt ein Feld
  `baseline: bool = False`, das `format_report()` und `exit_code()` lesen (keine neuen
  Parameter dort); `Transcript` bekommt `skills: frozenset[str] | None = None`; die
  Sichtbarkeitsprüfung liegt in `run_one()` und sieht nur das Transcript des
  Eval-Agenten. Widersprich, wenn der Modus lieber ein Parameter der Report-Funktionen
  sein soll.
- **Ungemessen auf dem Rechner des Nutzers:** ob die synchronisierten Profil-Skills
  dort unter `--setting-sources project` ebenfalls unsichtbar sind. Die Messung hier
  stammt aus dem Container; der erste echte `--without-skill`-Lauf beantwortet die
  Frage über Schritt 3 des Ablaufs — er meldet sonst „Baseline unmöglich" für 17 von
  21 Skills, und dann ist die `CLAUDE_CONFIG_DIR`-Variante an der Reihe.
- **Ungemessen:** ob die CLI im `skills`-Feld den Frontmatter-`name` oder den
  Ordnernamen listet — im Repo sind beide bei allen 21 Skills gleich (Reviewer-Zählung);
  der Runner vergleicht mit dem Ordnernamen. Und warum die Zahl globaler Skills von 16
  (known-limits, 2026-08-15) auf 19 stieg — für die Baseline ohne Belang, für
  „Isolation" eine Notiz.
- **Ungemessen:** der Flag selbst im Harness (root, `bypassPermissions`); Nachweis
  sind die sieben Tests oben. Der erste echte Lauf gehört in den Report der
  Folgerunde.
- Beim Bau zu entscheiden: ob `visible_skills()` in `dispatch.py` (neben
  `assistant_text`, gleicher Parser) oder in `runner.py` liegt. Kosten: keine, solange
  `Transcript` das Feld trägt.

## Next steps

Plan mit `impl-plan` (16); Bau nach `skill-forge` (17) Schritt 3 bis 7 im Hauptkontext —
unter drei überlappungsfreien Paketen, `subagent-dev` sagt dann `sequential`. Danach
`lint_skill.py skills/skill-forge --base main`: erwartet `evals_due: true` mit genau
dem Grund `(?i)diskriminator` in `references/evals.md`, dann die fünf Evals fahren;
Folgerunde im Report von `skill-forge`; known-limits
(`## skill-forge`, „Gefordert, nicht gebaut" streichen; „Isolation" um das
`skills`-Feld ergänzen); Spec 00 §2 um den Satz zur Baseline.
