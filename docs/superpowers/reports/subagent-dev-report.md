# Bericht: Skill `subagent-dev` (Spec 09)

Branch `feat/subagent-dev`, Basis `0831fb7` (`specs/skill-foundation`).
Erstfassung: acht Commits, `a689e5f` (Plan) bis `a5cdfcc` (Bericht),
172/172 Tests grün. Fix-Runde 1 nach unabhängigem Review: siehe unten,
192/192 Tests grün, D1–D3 im zentralen Bestätigungslauf verifiziert.
Fix-Runde 2 nach demselben Bestätigungslauf: `research-fanout-stays-distilled`
blieb systematisch rot (66, dann 64 Zeilen gegen ein Budget von 60) — siehe
„Fix-Runde 2" unten. `run_evals.py` nicht ausgeführt (Auftrag); beide
Bestätigungsläufe liefen zentral, nicht in dieser Session.

## Fix-Runde 2 — Findings-Datei zu lang, Budget nicht angehoben

Zwei Läufe des Evals `research-fanout-stays-distilled` lieferten 66 bzw.
64 Zeilen gegen das Limit von 60 — keine Schwankung, ein systematischer
Überschuss. Nachgerechnet: Drei Funde (die Fixture `research-scan-target`
enthält genau drei `TODO(security)`-Marker) à drei Zeilen (Aussage, Beleg,
Konfidenz) plus Kopfzeile sind zwölf bis fünfzehn Zeilen — es standen also
rund fünfzig Zeilen Beiwerk in der generierten Datei. Das Budget wurde
**nicht** angehoben; stattdessen wurde `references/research-fanout.md` und
`SKILL.md` verschärft: ein Fund ist genau drei Zeilen, eine explizite
Verbotsliste (kein Vorgehensbericht, keine Wiederholung des Auftrags, keine
Zusammenfassung der Zusammenfassung, keine wiederholten Pfadangaben, kein
Meta-Kommentar über den Fan-out) und ein durchgerechnetes Beispiel (elf
Zeilen für drei Funde, exakt an `research-scan-target` orientiert). Details
in `docs/known-limits.md` unter „## subagent-dev — Fix-Runde 2".

**Ehrlich benannt:** Der tatsächliche Inhalt der überlangen Findings-Datei
aus dem Bestätigungslauf lag dieser Session nicht vor — der Lauf geschah
zentral. Die Diagnose (Vorgehensbericht/Meta-Ebene/Wiederholung als
wahrscheinlichste Füllung) stützt sich auf die Rechnung und auf die Lücken
im vorherigen, unterspezifizierten Schema, nicht auf eine
Zeile-für-Zeile-Analyse der echten Ausgabe. Ob die Verschärfung reicht, zeigt
erst der nächste zentrale Lauf.

## Fix-Runde nach Review

Ein unabhängiges Review fand drei Defekte (D1–D3) und vier Lücken (L1–L4),
alle drei Defekte reproduziert — gemeinsame Form: der Mechanismus meldete
Sicherheit, die er nicht geprüft hatte. Alle drei Defekte behoben, mit
Regressionstests gegen die im Review reproduzierten Fälle; zwei der vier
Lücken (L2, L3) mitgezogen, weil sie an denselben Funktionen hingen und mit
vertretbarem Aufwand behebbar waren; L1 und L4 bewusst nur dokumentiert.
Details, Restrisiken und die konkrete Begründung je Punkt stehen in
`docs/known-limits.md` unter „## subagent-dev" — hier nur die Kurzfassung:

- **D1 — `verify` meldete PASS für eine übersprungene Allowlist-Prüfung.**
  Ohne `--base` gibt es jetzt kein `"pass"`, sondern `"unverified"`.
- **D2 — Datei-Überlappung übersah Case-Drift, absolut/relativ, Globs und
  Umbenennungen.** Pfadvergleich normalisiert jetzt Groß-/Kleinschreibung
  und Backslashes, vergleicht per Präfix *und* Suffix, behandelt Globs als
  ihre Wurzel; eine `Rename:`-Zeile wird erkannt (beide Pfade in die
  Allowlist), jede andere unerkannte `Files:`-Zeile erzwingt `files_unknown`.
- **D3 — Interface-Überlappung hatte kein Äquivalent zu `files_unknown` und
  behauptete aktiv „keine Überlappung", ohne gesucht zu haben.** Prosa ohne
  Backtick-Symbol markiert die Task jetzt `interfaces_unknown` (sichtbar im
  `gate.json`) und erzwingt Serialisierung; die Begründungstexte sprechen
  jetzt von „erkannter" statt bloßer Überlappung.
- **L2 (verbessert) — `check_produces` sammelt jetzt alle gleichnamigen
  `ast`-Definitionen statt der zuletzt besuchten; `ambiguous` statt eines
  geratenen Ergebnisses, wenn keine passt und mehrere existieren.**
- **L3 (behoben) — `check_allowlist` teilt eine `git status`-Rename-Zeile
  (`"alt -> neu"`) jetzt in zwei echte Pfade statt einen unmatchbaren.**

Alle vier Eval-Fixtures wurden nach dem Fix erneut gegen die geänderten
Funktionen durchgerechnet (nicht über `run_evals.py`, sondern direkt gegen
`parse_plan`/`build_overlap_graph`/`gate_verdict`/`check_allowlist`/
`check_produces`): Verdikte für `plan-hidden-overlap` (`sequential`),
`plan-mini-two-tasks` (`no-delegate`) und `plan-disjoint-batch` (`parallel`,
Gruppe `[1,2,3,4]`) sind unverändert; das Verify-Szenario aus Eval 3 liefert
weiterhin `"ok": false` mit `arity_mismatch`, jetzt zusätzlich mit
`"allowlist_checked": false` und `"verdict": "fail"` im Artefakt.

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
├── SKILL.md                        (107 Zeilen, ≤150-Grenze eingehalten)
├── references/
│   ├── task-file.md                (Schema + Beispiel + Grenzen)
│   ├── research-fanout.md          (Rückgabe-Schema, Artefakt-Persistenz, Synthese-Disziplin)
│   └── merge-protocol.md           (Reihenfolge, Interface-Bruch als Gate-Fehler)
└── scripts/
    └── plan_to_tasks.py            (Tier 1, generate + verify)

tests/test_subagent_dev_plan_to_tasks.py   (46 Tests, davon 20 aus der Fix-Runde)

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
  semantische Analyse. Seit der Fix-Runde (D3) macht Prosa ohne Backtick-
  Symbol die Task konservativ `interfaces_unknown` (überlappt mit allem);
  was das nicht auffängt, sind zwei *unterschiedlich benannte* Backtick-
  Symbole, die dieselbe Sache meinen. Dokumentiert in `references/task-file.md`.
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
........................................................................ [ 37%]
........................................................................ [ 75%]
................................................                         [100%]
192 passed in 3.33s
```

46 davon für diese Skill (`tests/test_subagent_dev_plan_to_tasks.py`; 26 aus
der Erstfassung, 20 aus der Fix-Runde), 146 bestehend und unverändert grün.

## Folgerunde: `lint-spec` (2026-09-11)

Aus `docs/assessment-brainstorming.md` §6 Punkt 3 (Branch `claude/assessment-brainstorming`):
`plan_to_tasks.py lint-spec <spec>` prüft die Skill-Spec, die `impl-plan` liest, mit
demselben Parser wie den Plan — neun Regeln (header, review-note, sections, eval-table,
skill-structure, tier, abgrenzung, gate-language, placeholders), Nummern-Cutoff 18,
`tests/test_specs_lint.py` als Repo-Test, `tests/test_subagent_dev_spec_lint.py` für
die Regeln. Eigentum hier, weil der Konsument des Formats sein Eigentümer ist
(`impl-plan` Contract); der Aufruf steht in `skill-forge` Schritt 1 und `impl-plan`
Schritt 1. Bau und Fix-Runde nach zwei Reviews sind im Report von `skill-forge`
protokolliert (Abschnitt „Folgerunde: Spec-Review"); die Grenzen stehen in
`docs/known-limits.md` unter „subagent-dev — `lint-spec`".

## Basislinie Spec 27

Gemessen am 2026-10-30 auf gemergter Historie, vor dem Bau (Spec 27, Next steps). Zwei statt drei Pläne, auf Wunsch des Nutzers (Limit sparen): `docs/superpowers/plans/2026-10-13-test-first.md` (7 Tasks) und `docs/superpowers/plans/2026-10-14-skill-dir.md` (10 Tasks), zusammen 17 Task-Commits (`git log --format='%h %s' | grep -E '^[0-9a-f]+ (test-first|skill-dir) Task [0-9]+'`). Das ist die Vergleichsbasis für Task 18; derselbe Befehl und dieselben Flags müssen dort wieder laufen.

Befehl je Task-Commit `C`, nacheinander (nie parallel), in einem frischen Worktree (`git worktree add --detach <scratch>/bl/C C`, danach `git worktree remove --force`):

```
timeout 600 claude -p "/code-review C^..C" --output-format json --allowedTools "Bash(git:*)" Read Grep Glob > <scratch>/bl/out/C.json
```

Rohantworten liegen unter `<scratch>/bl/out/<C>.json`, nicht im Repo (Scratchpad der Sitzung, Spec-Vorgabe war `.skills/cache/`). Modell aller Läufe laut `modelUsage`: `claude-opus-5-5`. Alle 17 Läufe endeten mit Exit 0, `subtype: success`, `is_error: false`; kein Abbruch, kein Timeout, keine Wiederholung.

**Tokens:** Der Block `usage` der JSON-Antwort ist bei `/code-review` durchgängig 0 (der Lauf ist ein lokales Kommando, `local_command: code_review`, `num_turns: 0`). Die tatsächlichen Tokens stehen in `modelUsage`; die Tabellen nennen diese Werte. Task 18 muss dieselbe Quelle nehmen. „Gesamt" ist die Summe aus Input, Output, Cache-Read und Cache-Creation. Für den Abnahmewert (Review-Tokens um 40 % senken) ist „Gesamt" die Vergleichsgröße, hilfsweise `total_cost_usd`.

**Funde:** Zahl der Elemente des JSON-Arrays in `result`; in allen 17 Läufen maschinenlesbar. Nachprüfung am Code (Abnahmekriterium „bestehen eine Nachprüfung") ist in dieser Basislinie nicht erfolgt; die Zahlen sind unnachgeprüfte Meldungen des Reviewers.

### Plan 2026-10-13-test-first (7 Tasks)

| Task | Commit | Kosten USD | Input | Output | Cache-Read | Cache-Creation | Gesamt | Funde |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 tdd_log.py | `9e65061` | 0.45 | 12 | 6,005 | 250,014 | 55,667 | 311,698 | 9 |
| 2 references/cycle.md | `45dd704` | 0.35 | 10 | 6,519 | 200,158 | 35,442 | 242,129 | 9 |
| 3 SKILL.md | `c45519a` | 0.57 | 26 | 8,762 | 744,950 | 49,059 | 802,797 | 9 |
| 4 fünf Evals mit Fixtures tf-docs, tf-f... | `d1db44f` | 0.59 | 24 | 10,028 | 693,015 | 49,388 | 752,455 | 7 |
| 5 Nachbarn | `3da3904` | 0.39 | 20 | 5,521 | 490,136 | 37,159 | 532,836 | 8 |
| 6 known-limits | `0040ddb` | 0.66 | 32 | 10,523 | 909,876 | 52,571 | 973,002 | 9 |
| 7 Report | `036c153` | 0.60 | 32 | 11,626 | 803,924 | 41,148 | 856,730 | 9 |
| **Summe** | | **3.60** | **156** | **58,984** | **4,092,073** | **320,434** | **4,471,647** | **60** |

### Plan 2026-10-14-skill-dir (10 Tasks)

| Task | Commit | Kosten USD | Input | Output | Cache-Read | Cache-Creation | Gesamt | Funde |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 architecture-map | `677ddbd` | 0.42 | 12 | 7,162 | 289,736 | 44,628 | 341,538 | 10 |
| 2 Hook-Vorlagen rufen die Kopie unter .... | `f6a9aea` | 0.31 | 8 | 4,859 | 167,989 | 36,314 | 209,170 | 10 |
| 3 cc-dev-Skills rufen ihre Skripte über... | `3fc173c` | 0.65 | 34 | 9,296 | 1,041,234 | 50,834 | 1,101,398 | 6 |
| 4 cc-knowledge und cc-ui über ${CLAUDE_... | `337fac8` | 0.52 | 24 | 7,095 | 634,604 | 50,138 | 691,861 | 10 |
| 5 impl-plan, skill-forge und Template ü... | `1f7d83b` | 0.46 | 24 | 6,682 | 600,974 | 41,458 | 649,138 | 8 |
| 6 Lint-Regel script-paths | `be69eaf` | 0.58 | 30 | 9,779 | 816,888 | 43,454 | 870,151 | 10 |
| 7 Eval repo-relative-script-path-is-rep... | `4c85808` | 0.54 | 30 | 6,851 | 835,984 | 46,987 | 889,852 | 6 |
| 8 Nachbarn | `b62a6d9` | 0.36 | 16 | 6,830 | 344,628 | 30,684 | 382,158 | 8 |
| 9 known-limits | `ec58ea5` | 0.76 | 42 | 11,140 | 1,266,635 | 55,817 | 1,333,634 | 9 |
| 10 Report | `4861c42` | 0.44 | 22 | 7,980 | 531,266 | 35,217 | 574,485 | 8 |
| **Summe** | | **5.04** | **242** | **77,674** | **6,529,938** | **435,531** | **7,043,385** | **85** |

Beide Pläne zusammen: 8.64 USD, 11,515,032 Tokens gesamt (136,658 Output), 145 Funde in 17 Läufen.

**Auffälligkeiten.** In 15 von 17 Läufen verweigerte die Berechtigungsliste (`Bash(git:*)`) einzelne Bash-Aufrufe des Reviewers, der andere Programme als `git` starten wollte (`permission_denials` in den Rohantworten); die Läufe liefen trotzdem durch. Der Reviewer sieht damit nur Lesezugriff plus `git`, was für die Wiederholung an den Prüfpunkten gleich bleiben muss.

### Anhang: Funde je Lauf

Je Fund `Datei:Zeile`, dann Kurzfassung (höchstens 80 Zeichen). Nicht nachgeprüft.

**`9e65061` test-first Task 1: tdd_log.py — Zustandsmodell red/green/ref** (9 Funde)

- `skills/test-first/scripts/tdd_log.py:78` missing_program sets expect_program=True after every operator token, includin...
- `skills/test-first/scripts/tdd_log.py:87` Shell builtins and keywords (cd, source, ., export, if) are checked with shut...
- `skills/test-first/scripts/tdd_log.py:242` record() checks the state against one read of the log, runs the command for u...
- `skills/test-first/scripts/tdd_log.py:124` section_rows skips every line that starts with | Test or | ---.
- `skills/test-first/scripts/tdd_log.py:230` The timeout cleanup calls proc.communicate() with no timeout.
- `skills/test-first/scripts/tdd_log.py:180` compose() treats an empty existing log ('' rather than None) as having a head.
- `skills/test-first/scripts/tdd_log.py:70` missing_program is a verbatim copy of skills/setup-repo/assets/runtime/verify...
- `skills/test-first/scripts/tdd_log.py:255` record() reads and parses the whole log twice per call: once for the state ch...
- `tests/test_test_first_log.py:112` Dead or no-op test code: cells is used for only one weak assertion, the last...

**`45dd704` test-first Task 2: references/cycle.md — Zustandsmodell, Ver** (9 Funde)

- `skills/test-first/references/cycle.md:61` The go, cargo and jest commands in the runner table exit 0 when the name filt...
- `skills/test-first/references/cycle.md:59` The -k year_is_filled form makes pytest collect the whole suite, so a collect...
- `skills/test-first/references/cycle.md:59` A misspelled or not-yet-written test selector makes pytest exit 4 or 5, and t...
- `skills/test-first/references/cycle.md:61` The filter forms -run TestYearIsFilled, cargo test year_is_filled, -t "year i...
- `skills/test-first/references/cycle.md:22` 'Ein red nach Grün beginnt einen neuen Zyklus' is wrong for a red call that c...
- `skills/test-first/references/cycle.md:46` The 'Das Verhalten gibt es schon' path says to keep the test, but the doc doe...
- `skills/test-first/references/cycle.md:37` 'Die Test-ID ist meist der Testname: ohne Leerzeichen' conflicts with the vit...
- `skills/test-first/references/cycle.md:19` The doc drops the spec's Windows caveat: under cmd.exe, exit 127 does not mea...
- `skills/test-first/references/cycle.md:72` 'Grenzen des Rot' tells the agent to read the output before the first red, bu...

**`c45519a` test-first Task 3: SKILL.md — Zyklus je Verhalten mit tdd_lo** (9 Funde)

- `skills/test-first/SKILL.md:24` The script path is set once as the shell variable T="${CLAUDE_SKILL_DIR}/..."...
- `skills/test-first/SKILL.md:43` SKILL.md says a new task starts with start and that the script reports when ....
- `skills/test-first/SKILL.md:29` SKILL.md never says that tdd_log.py runs the test command from the repo root...
- `skills/test-first/SKILL.md:30` Step 3 tells the agent to read the output to rule out a missing runner module...
- `skills/test-first/SKILL.md:3` The description only triggers on "füge X hinzu" for new code *with tests* and...
- `skills/test-first/SKILL.md:3` The description says the skill is "not for docs", which pushes the router awa...
- `skills/test-first/SKILL.md:35` The steps never cover the ungeprüft outcome (missing program, exit 127 or the...
- `skills/test-first/SKILL.md:42` status only reads the last log section, but the SKILL's rule for when to run...
- `skills/test-first/SKILL.md:26` Step 1 says the ID is usually the test name, with no spaces and no |, but man...

**`d1db44f` test-first Task 4: fünf Evals mit Fixtures tf-docs, tf-featu** (7 Funde)

- `evals/test-first/evals.json:107` Eval 5 (explicit-waiver-says-untested) has nothing that catches a test being...
- `evals/test-first/evals.json:87` Eval 4 (pressure-still-red-first) leaves out the artifact_header check and th...
- `evals/test-first/evals.json:66` Eval 3 (green-on-first-run-is-flagged) never checks that a slugify test was a...
- `evals/test-first/evals.json:43` The red-before-green pattern only matches rows with the same test ID.
- `tests/test_test_first_fixtures.py:149` The Eval 3 simulation feeds tdd_log.py's stdout to grade() as the agent's out...
- `evals/test-first/evals.json:13` Eval 1 only checks that 'Hello' appears somewhere in README.md.
- `evals/test-first/evals.json:7` The Eval 1 prompt has mismatched quotes around Helo: a German low-9 opening q...

**`3da3904` test-first Task 5: Nachbarn — testing-strategy und debug-led** (8 Funde)

- `.claude/skills/testing-strategy/SKILL.md:3` The mirrored project copies of testing-strategy and debug-ledger now send use...
- `skills/work-plan/references/task-patterns.md:11` The new sentence says red and green go through test-first, which records comm...
- `skills/test-first/SKILL.md:3` The description was reworded from 'superpowers:test-driven-development' to 't...
- `tests/test_marketplace.py:261` The whole of skills/test-first/SKILL.md is exempted from every ROUTING_TARGET...
- `tests/test_marketplace.py:256` The bare substring 'test-driven-development' is now a forbidden routing targe...
- `skills/testing-strategy/SKILL.md:128` The Abgrenzung describes test-first as the cycle 'während der Implementierung...
- `README.md:104` The routing matrix's new test-first row lists 'superpowers:test-driven-develo...
- `specs/Spec 00 – skill-foundation.md:85` The new row uses doubled parentheses like 'testing-strategy (05) (welche Test...

**`0040ddb` test-first Task 6: known-limits — Rot heißt Exit ≠ 0, ein Te** (9 Funde)

- `skills/test-first/scripts/tdd_log.py:122` section_rows() skips any row starting with '| Test ' or '| ---' as a table he...
- `docs/known-limits.md:2037` The section does not say that the shutil.which pre-check treats shell builtin...
- `docs/known-limits.md:2041` The log is called the record of the work, but nothing says writes are unlocke...
- `docs/known-limits.md:2041` The section does not say that a selector matching zero tests exits 0 under go...
- `docs/known-limits.md:2030` The 'Rot heißt Exit ≠ 0' bullet leaves out pytest selector errors: a mistyped...
- `docs/known-limits.md:2044` 'Nicht committet' is stated without conditions, but in target repos without ....
- `docs/known-limits.md:2039` The Windows timeout limit is described as untested but not fixed.
- `docs/known-limits.md:2049` It says Spec 20 measured nine skills without description 'im Listing' of cc-d...
- `docs/known-limits.md:2037` The Windows bullet says only that exit 127 'means nothing' on Windows.

**`036c153` test-first Task 7: Report — Eval-Läufe mit und ohne Skill, A** (9 Funde)

- `docs/superpowers/reports/test-first-report.md:33` The report says the process group fixes the timeout hang.
- `docs/superpowers/reports/test-first-report.md:50` The 'nach dem Fix' column shows 1/1 for Evals 2-4, copied from 'erste Fassung'.
- `docs/superpowers/reports/test-first-report.md:63` The headline lesson ('what is said in the exception belongs in the descriptio...
- `docs/superpowers/reports/test-first-report.md:100` The report admits the description reached 1032 characters after the fix, whic...
- `docs/superpowers/reports/test-first-report.md:43` The failing suite test (test_rest_api_architect_gate) is attributed to missin...
- `docs/superpowers/reports/test-first-report.md:9` 'Was entstanden ist' leaves out several artifacts the template asks for: test...
- `docs/superpowers/reports/test-first-report.md:87` 'Was nicht gemessen wurde' leaves out limits that docs/known-limits.md lists...
- `docs/superpowers/reports/test-first-report.md:14` 'scripts/tdd_log.py' is given without the skills/test-first/ prefix.
- `docs/superpowers/reports/test-first-report.md:1` The header comment keeps 'skill: skill-forge'.

**`677ddbd` skill-dir Task 1: architecture-map — Aufrufe über ${CLAUDE_S** (10 Funde)

- `skills/architecture-map/scripts/drift_check.py:115` The .replace("\\", "/") branch for Windows paths never takes effect, because...
- `skills/architecture-map/scripts/drift_check.py:136` Swapping in the absolute path of drift_check's own script makes the script-ex...
- `skills/architecture-map/scripts/extract_py.py:289` The generated command is built by joining --root {args.root}, --files and --o...
- `skills/architecture-map/SKILL.md:79` The drift-check step is advertised as a CI step ('als CI-Schritt'), but the c...
- `skills/architecture-map/scripts/extract_py.py:289` The command now recorded in committed ARCHITECTURE.md headers and footers (py...
- `skills/architecture-map/scripts/drift_check.py:114` resolve_script assumes the script is always parts[1].
- `skills/architecture-map/scripts/drift_check.py:160` The check() docstring and the guard's error message are stale: they still say...
- `skills/architecture-map/scripts/extract_py.py:289` f"python scripts/extract_py.py " is an f-string with no placeholders, which i...
- `skills/architecture-map/scripts/drift_check.py:102` OWN_SCRIPTS includes analyze_graph.py, but drift_check only re-runs graph ext...
- `.claude/skills/architecture-map/scripts/drift_check.py:102` Every change is copied byte for byte into both skills/architecture-map/ and ....

**`f6a9aea` skill-dir Task 2: Hook-Vorlagen rufen die Kopie unter .claud** (10 Funde)

- `skills/sql-schema-architect/assets/hooks/migration-gate.json:10` The new hook command calls the copied migration_gate.py with only --versions-...
- `skills/sql-schema-architect/scripts/migration_gate.py:33` detect_hook_installed now matches .claude/hooks/migration_gate.py in settings...
- `skills/sql-schema-architect/assets/hooks/migration-gate.json:10` The check for a missing script runs before any command filtering, so the 'Hoo...
- `skills/sql-schema-architect/assets/hooks/migration-gate.json:10` Unlike the debug-ledger hook, which uses os.environ.get('CLAUDE_PROJECT_DIR')...
- `skills/debug-ledger/assets/hooks/check-ledger.json:10` The inline Python prints non-ASCII text ('ungeprüft —') with ensure_ascii=Fal...
- `skills/debug-ledger/assets/hooks/check-ledger.json:10` The touched hook still matches "git commit" not in cmd as a plain substring a...
- `skills/debug-ledger/SKILL.md:108` The new installation copies a snapshot of check_ledger.py / migration_gate.py...
- `skills/sql-schema-architect/scripts/migration_gate.py:579` The generated: header labels (migration_gate.py:579, lint_schema.py:251, gen_...
- `tests/test_skill_dir_paths.py:49` The test always runs the hook with cwd=repo and CLAUDE_PROJECT_DIR set, so th...
- `tests/test_skill_dir_paths.py:95` assert sys.version_info >= (3, 8) at the end of test_hook_scripts_are_standal...

**`3fc173c` skill-dir Task 3: cc-dev-Skills rufen ihre Skripte über ${CL** (6 Funde)

- `skills/rest-api-architect/SKILL.md:27` Now that gate.py is called through ${CLAUDE_SKILL_DIR}, the files it needs ar...
- `docs/known-limits.md:2011` This commit deletes the work-plan sentence that pointed to docs/known-limits....
- `skills/subagent-dev/scripts/plan_to_tasks.py:1098` The _meta.generated reproduction command is still hard-coded as python skills...
- `skills/dev-report/SKILL.md:29` The calls now depend on ${CLAUDE_SKILL_DIR}, but dev-report, review-context,...
- `skills/impl-plan/SKILL.md:49` impl-plan (and its .claude/skills/impl-plan copy), skill-forge and skill-forg...
- `skills/subagent-dev/references/task-file.md:36` The example header lines in task-file.md (lines 36 and 45, plus the .claude c...

**`337fac8` skill-dir Task 4: cc-knowledge und cc-ui über ${CLAUDE_SKILL** (10 Funde)

- `skills/verified-research/references/delta-mode.md:87` This line now says to call registry.py --repo .
- `evals/verified-research/evals.json:50` The eval prompts at lines 50 and 91 still tell the agent to run skills/verifi...
- `skills/mobile-audit/scripts/audit_static.py:265` The commit says mobile-audit is now "ohne <skill-dir>", but audit_static.py (...
- `skills/exercise-forge/scripts/export.py:364` The script still writes the repo-relative python skills/exercise-forge/script...
- `skills/human-prose/scripts/measure.py:430` measure_meta still writes generated: python skills/human-prose/scripts/measur...
- `skills/motion-landing/scripts/verify.py:357` generated_cmd still hardcodes python skills/motion-landing/scripts/verify.py,...
- `skills/learning-coach/assets/learner-template.md:1` The learner.md template header (and learner-schema.md lines 20 and 79, verifi...
- `skills/learning-coach/SKILL.md:62` Only the due call was converted to ${CLAUDE_SKILL_DIR}.
- `skills/verified-research/references/rating-rubric.md:4` The new pointer says to use the add call "wie in der SKILL.md, Register-Phase...
- `skills/mobile-audit/SKILL.md:40` Stage 2 (audit_devices.py) has no call at all.

**`1f7d83b` skill-dir Task 5: impl-plan, skill-forge und Template über $** (8 Funde)

- `skills/skill-forge/SKILL.md:38` Step 4 used to run the source lint_skill.py (skills/skill-forge/scripts/...).
- `skills/impl-plan/SKILL.md:49` The lint now calls ${CLAUDE_SKILL_DIR}/../subagent-dev/scripts/plan_to_tasks.py.
- `skills/skill-forge/SKILL.md:25` The same lint-spec call through ../subagent-dev also runs the project copy in...
- `skills/skill-forge/references/checklist.md:27` Checklist item 19 still asks whether the SKILL.md names both paths (skills/<n...
- `skills/setup-repo/references/rules-harvest.md:39` The bash fence now holds only an argument fragment ('--classes '{...}''), not...
- `skills/skill-forge/scripts/lint_skill.py:835` The lint output header (generated:) and the usage docstring on line 11 still...
- `skills/skill-forge/assets/skill-template/SKILL.md:17` The template's call '${CLAUDE_SKILL_DIR}/scripts/….py' points at a file that...
- `skills/skill-forge/SKILL.md:28` The new fallback condition 'Liegt subagent-dev nicht neben dieser Skill' cann...

**`be69eaf` skill-dir Task 6: Lint-Regel script-paths — repo-relative Au** (10 Funde)

- `tests/test_skill_dir_paths.py:128` The neighbor-boundary check uses same_plugin or both_project, so passing one...
- `skills/skill-forge/scripts/lint_skill.py:625` SKILL.md is only checked for skills/<name>/scripts/ and <skill-dir>/scripts/.
- `skills/skill-forge/scripts/lint_skill.py:629` The hook-asset check only looks for skills/<name>/scripts/.
- `skills/skill-forge/scripts/lint_skill.py:627` The reference check only flags ${CLAUDE_SKILL_DIR} lines that also contain lo...
- `skills/skill-forge/scripts/lint_skill.py:620` The generated: exemption is a plain substring test on the whole line, so any...
- `tests/test_skill_dir_paths.py:100` SKILL_DIR_CALL only matches [A-Za-z0-9_]+\.py, so hyphenated or non-.py scrip...
- `evals/skill-forge/evals.json:1` Spec 25 lists eval 7 repo-relative-script-path-is-reported, the fixture evals...
- `docs/known-limits.md:1915` known-limits still says lint_skill.py has 'vierzehn Regeln' (fourteen), while...
- `skills/skill-forge/scripts/lint_skill.py:627` The hook pattern duplicates the first alternative of REPO_RELATIVE_SCRIPT_RE...
- `tests/test_skill_forge_lint.py:615` The _script_paths helper calls the full ls.lint_skill(skill) (all 15 rules pl...

**`4c85808` skill-dir Task 7: Eval repo-relative-script-path-is-reported** (6 Funde)

- `evals/fixtures/sf-relpath/fixture.json:1` The sf-relpath fixture does not include the docs/artifact-header.md that Spec...
- `tests/test_skill_forge_evals_schema.py:187` The grip test's negative control runs against listed-x in sf-relpath, while t...
- `tests/test_skill_forge_evals_schema.py:193` Unlike the parallel orphan test (lines 155-156), the new test never checks th...
- `tests/test_skill_forge_evals_schema.py:199` The anti-ceremony assertion inside the new test has no failure message (, pat...
- `docs/known-limits.md:1970` known-limits still says "Die sechs Evals binden nur an Regeln, die in ihrer F...
- `evals/skill-forge/evals.json:43` The anti-ceremony eval's new script-paths pass pattern only holds if the agen...

**`b62a6d9` skill-dir Task 8: Nachbarn — test_no_file_refs_across_plugin** (8 Funde)

- `tests/test_marketplace.py:89` The new /\.\./ alternative only matches when a slash comes right before .., s...
- `tests/test_marketplace.py:107` findall returns non-overlapping matches, and a skills/<a>/ match uses up the...
- `tests/test_marketplace.py:96` The extended check still scans only skills/ originals of listed skills.
- `tests/test_marketplace.py:89` This duplicates the existing test_neighbor_paths_stay_inside_a_plugin / SKILL...
- `tests/test_skill_dir_paths.py:129` The existing neighbor invariant (the one this commit duplicates) accepts same...
- `tests/test_marketplace.py:89` /../<name>/ is matched anywhere, not only after ${CLAUDE_SKILL_DIR}.
- `tests/test_marketplace.py:287` The new regression test only checks _SKILL_REF.findall on two literals.
- `tests/test_marketplace.py:111` The finding message changed from -> skills/{other}/ to -> {other}/, so it no...

**`ec58ea5` skill-dir Task 9: known-limits — fünf überholte Stellen zu S** (9 Funde)

- `docs/known-limits.md:824` The commit set out to update every outdated note about script paths but misse...
- `docs/known-limits.md:1941` The doc says the script-paths rule reports every repo-relative call ('meldet...
- `docs/known-limits.md:1685` The Marketplace entry says that today every call reads ${CLAUDE_SKILL_DIR}/sc...
- `docs/known-limits.md:2054` The skill-dir section says every script call is python "${CLAUDE_SKILL_DIR}/s...
- `docs/known-limits.md:2070` The section says generated headers still read python skills/<name>/scripts/…...
- `docs/known-limits.md:1547` The learning-coach entry is now headed 'Behoben' (fixed), and the deleted tex...
- `docs/known-limits.md:1726` The heading says 'behoben' (fixed) for scripts in other repos, but cross-skil...
- `docs/known-limits.md:1996` The work-plan section now says the path reaches dispatch in another repo, but...
- `docs/known-limits.md:1548` The rewritten learning-coach bullet sits directly above ## exercise-forge wit...

**`4861c42` skill-dir Task 10: Report — Messung, Umstellung, Evals im Ha** (8 Funde)

- `docs/superpowers/reports/skill-dir-report.md:59` The report says every failure was re-run against main, but skill-forge has 2...
- `docs/superpowers/reports/skill-dir-report.md:70` 'Eval 7 bestand in drei von vier Läufen' counts three manual claude -p runs o...
- `docs/superpowers/reports/skill-dir-report.md:46` The failing test is given as test_rest_api_architect_gate, but that is a test...
- `docs/superpowers/reports/skill-dir-report.md:17` The neighbours bullet names only impl-plan and skill-forge as calling ${CLAUD...
- `docs/superpowers/reports/skill-dir-report.md:72` 'Was nicht gemessen wurde' leaves out the three standard entries from skill-f...
- `docs/superpowers/reports/skill-dir-report.md:44` 'Was gemessen wurde' omits the lint result the template asks for (lint_skill....
- `docs/superpowers/reports/skill-dir-report.md:4` The header leaves out the template's required plan path and 'Tier …' line, an...
- `docs/superpowers/reports/skill-dir-report.md:54` The table column 'ohne Skill' holds '0/7 grün' for skill-forge.

## Was nicht gemessen wurde

- **Fix-Kreislauf:** Die Basislinie misst nur die Kosten eines einzelnen `/code-review`-Laufs je Task-Commit. Die Schleife zwischen Autor und Reviewer (Fund beheben, erneut prüfen, höchstens `MAX_FIX_ROUNDS` Runden) wurde nicht nachgespielt; der Wert der Basislinie ist deshalb eine Untergrenze für die Review-Kosten je Task, nicht die Gesamtkosten des Verfahrens.
- **Stufe von `/code-review` im Headless-Lauf:** Der Aufruf `claude -p "/code-review C^..C"` nennt keine Stufe (low bis max). Welche Stufe headless gilt, ist nicht festgestellt; laut Skill-Beschreibung gilt ohne Angabe die zuletzt getippte Stufe, ob und welche `-p` dafür vorfindet, wurde nicht geprüft. Das Modell war laut `modelUsage` `claude-opus-5-5`. Die Läufe der Task 18 müssen mit demselben Befehl und derselben Installation laufen, sonst ist der Vergleich nicht belastbar.
- **Dritter Plan:** Spec 27 sieht drei Pläne und höchstens 30 Tasks vor; gemessen wurden auf Wunsch des Nutzers (Limit sparen) nur zwei Pläne mit 17 Tasks. Die Summen sind deshalb nicht mit einer Drei-Pläne-Messung vergleichbar.
- **Nachprüfung der Funde:** Ob ein Fund am Code besteht, wurde nicht geprüft; „Funde" zählt Meldungen. Das Abnahmekriterium „mindestens gleich viele Funde, die eine Nachprüfung bestehen" kann erst Task 18 prüfen, mit einer Stichprobe der Funde dieses Anhangs.
- **Schwankung zwischen Läufen:** Jeder Task-Commit wurde genau einmal gemessen; die Streuung eines wiederholten Laufs derselben Task ist unbekannt.
- **Tokens im `usage`-Block:** siehe oben, dort durchgängig 0; gemessen wurde über `modelUsage`.
