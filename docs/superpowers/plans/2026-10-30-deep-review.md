<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# deep-review Implementation Plan

**Goal:** Ein großer Bereich oder ein Prüfpunkt wird nicht mehr in einem `/code-review` über
alles geprüft, in dem Funde verloren gehen, sondern in Paketen, denen ein Skript die
Gegenstellen der geänderten Aufrufe mitgibt — und `review_kit.py audit` meldet jedes Paket
ohne Ergebnis, bevor ein Bericht „vollständig" sagt.

**Architecture:** Tier 1. Der einzige Code ist `skills/deep-review/scripts/review_kit.py`
(Stdlib) mit den Unterbefehlen `plan`, `counterparts`, `record`, `merge`, `audit`,
`cleanup`; er schreibt unter `.skills/cache/deep-review/<lauf>/` und Hilfscommits unter
`refs/deep-review/<lauf>/`, importiert nie Zielcode. Python-Gegenstellen über `ast` (Vorbild:
`docs/superpowers/reports/review-bench/counterparts.py`), Delphi über einen Text-Scanner. Die
Reviews führen `/code-review` und `/security-review` im Hauptkontext aus; das verlangt die
SKILL.md (G1). Dazu eine kleine Erweiterung in subagent-dev: `fix-task` liest `findings.json`.

**Reihenfolge wegen des vollen Lint-Registers:** `tests/test_skills_lint.py` lintet jeden
Ordner unter `skills/` mit einer `SKILL.md`, und das Register ist voll (77 von 77). Die
SKILL.md entsteht deshalb erst, wenn Evals, Routing, Rückverweise, known-limits und der Report
mit „## Was nicht gemessen wurde" liegen; im selben Task kommen Plugin-Zuordnung und
Projekt-Kopie dazu, weil `test_every_skill_in_exactly_one_plugin` und
`test_project_copies_match_originals` eine `SKILL.md` verlangen. So ist die Suite nach jedem
Task grün.

**Lesson aus Spec 23 und 24:** Fixture-Werte nie wörtlich als Beispiel in SKILL.md oder
References verwenden — sonst diskriminiert der Eval nicht.

**Tech Stack:** Python 3.11+ Stdlib für Skript und Tests; Git-Plumbing (`read-tree`,
`update-index`, `write-tree`, `commit-tree`, `update-ref`); Markdown für Skill, References,
Evals.

**Spec:** `specs/Spec 26 – deep-review.md`

**Stand 2026-11-02:** Plan neu geschnitten nach der Neufassung der Spec; Task 1 aus dem Plan
vom 2026-10-30 ist gebaut und bleibt.

## Global Constraints

- **E1 — Tier 1, nur Stdlib.** `review_kit.py` importiert nichts außerhalb der Stdlib, der
  Docstring nennt „Tier 1"; Aufruf in der SKILL.md als
  `python "${CLAUDE_SKILL_DIR}/scripts/review_kit.py"`, nie in References (Regel
  `script-paths`). Ohne `/code-review` läuft dieselbe Paketfolge nach
  `references/review-brief.md`; der Bericht sagt „Review ohne /code-review".
- **E2 — Gate-Sprache:** Abdeckung der Pakete, verlorene Funde und Berichtskonsistenz meldet
  `audit` (G2); dass je Paket ein Review lief, verlangt die SKILL.md (G1). Kein Hook, kein
  „blockiert".
- **E3 — Kopfzeile je Artefakt:** `plan.json`, `results/*.json`, `findings.json`,
  `audit.json` per `_meta` (Skill, Schema 1, Kommando); `packets/*.md` und `report.md` mit
  `<!-- skill: deep-review | schema: 1 | … -->`. Eine Funktion schreibt alle JSON-Dateien:
  `ensure_ascii=False`, feste Schlüsselreihenfolge, repo-relative POSIX-Pfade.
- **E4 — SKILL.md ≤ 150 Zeilen**, portables Frontmatter, Details in `references/`.
- **E5 — Anti-Zeremonie-Eval** `anti-ceremony-small-range-one-packet`, gebunden an
  `file_matches` auf `plan.json`, `artifact_header`, `file_max_lines` und
  `git_head_unchanged`.
- **E6 — Nichts im Arbeitsbaum des Nutzers.** Hilfscommits nur über einen temporären Index
  (`GIT_INDEX_FILE`) und `update-ref` unter `refs/deep-review/<lauf>/`, Identität per
  `GIT_AUTHOR_*`/`GIT_COMMITTER_*` = `deep-review <deep-review@localhost>`; HEAD, Index und
  Arbeitsbaum bleiben unverändert. Pfade unter `.skills/` zählen nie.
- **E7 — Grenzwerte als Konstanten** am Kopf von `review_kit.py` mit den Namen
  `SPLIT_AT = 800`, `PACKET_SIZE = 600`, `BLOCK_MAX_CHARS = 30000`, `MERGE_LINE_GAP = 3`,
  `RAISE_DEPTH = 2`, `FLAG_DEPTH = 4`, `AMBIGUOUS_MAX = 3`, `REPORT_BASE_LINES = 20`; der
  Report nennt sie.

## Skill-Struktur

```
skills/deep-review/
├── SKILL.md
├── references/packets.md, counterparts.md, review-brief.md, delphi.md
├── assets/report-template.md
└── scripts/review_kit.py

evals/deep-review/evals.json
evals/fixtures/dr-seeded/ (gebaut), dr-split/, dr-contract/, dr-delphi/
tests/test_deep_review_kit.py
skills/subagent-dev/scripts/plan_to_tasks.py (fix-task), skills/subagent-dev/references/checkpoints.md
docs/superpowers/reports/deep-review-report.md, docs/known-limits.md
skills/review-context/, subagent-dev/, debug-ledger/, test-first/ (Abgrenzung)
specs/Spec 00 – skill-foundation.md, specs/Spec 27 – subagent-dev-checkpoints.md, README.md,
.claude-plugin/marketplace.json, scripts/sync_skills.py, .claude/skills/deep-review/ und die Kopien der Nachbarn
```

### Task 1: dr-seeded und Basislinie

Gebaut am 2026-10-30 (Plan vom 2026-10-30, Task 1): Fixtures `dr-seeded` und
`dr-seeded-clean` mit je `README.md`, `test_seeded_fixtures`, Basislinie im Report. Bleibt
unverändert; `dr-seeded` ist die Fixture des Anti-Zeremonie-Evals (402 Zeilen, unter
`SPLIT_AT`).

**Files:**
- Create: `evals/fixtures/dr-seeded/fixture.json`
- Create: `evals/fixtures/dr-seeded/README.md`
- Create: `evals/fixtures/dr-seeded-clean/fixture.json`
- Create: `evals/fixtures/dr-seeded-clean/README.md`
- Create: `docs/superpowers/reports/deep-review-report.md`
- Test: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `token:dr-seeded`, `token:Was nicht gemessen wurde`

- [x] **Step 1: Test schreiben** — `test_seeded_fixtures`.
- [x] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k seeded_fixtures`.
- [x] **Step 3: Fixtures bauen** — fünf Fehler mit Vertrag außerhalb des Diffs.
- [x] **Step 4: Basislinie messen** — `/code-review` und Sonnet je drei Läufe.
- [x] **Step 5: Grün sehen**, volle Suite; Commit.

### Task 2: Lauf-ID, JSON-Schreiber und Schnittregel

**Files:**
- Create: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `fn:new_run_id(sha)`, `fn:write_json(path, meta, payload)`, `fn:numstat(repo, rng)`, `fn:classify(path, with_tests)`, `fn:cut_packets(files, packet_size)`, `fn:build_plan(repo, rng, profile, focus, split_at, with_tests)`

- [ ] **Step 1: Test schreiben** — `test_run_ids_do_not_collide` (zwei IDs in derselben
      Sekunde mit gleichem SHA verschieden, Form `JJJJ-MM-TT-HHMMSS-<kurz-sha>-<4>`);
      `test_plan_single_packet_below_threshold` (Git-Repo im `tmp_path` mit 30 geänderten
      Zeilen: ein Paket `p1`, `range` = Originalbereich, `split: false`; eine Datei unter
      `.skills/` zählt nicht); `test_plan_cut_rule` (synthetische Dateiliste: Gruppen in
      Pfadreihenfolge, zwei kleine Verzeichnisse in einem Paket, eine Gruppe über
      `packet_size` an Dateigrenzen geteilt, eine Datei über `packet_size` allein, IDs
      `p1…`, `packet_size` = kleiner von 600 und `split_at`); `test_plan_not_reviewed`
      (Markdown und `tests/test_x.py` unter `not_reviewed` mit Grund, mit `with_tests`
      reviewt; Umbenennung zählt als gelöschte und neue Datei).
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k "run_ids or plan_"`.
- [ ] **Step 3: Implementieren** — Konstanten aus E7; `numstat` über
      `git diff --numstat --no-renames` (Binärdateien 0); `classify` mit den Mustern der Spec
      (Doku, Bilder, `.dproj`, `.res`; Tests `test_*.py`, `*_test.py`, `tests/`,
      `unittests/`, `*Test*.pas`); `cut_packets` nach der Schnittregel; `build_plan`
      schreibt `plan.json` mit den Schlüsseln der Spec in fester Reihenfolge; Fokus
      `security` ergibt ein Paket `s1` über den ganzen Bereich; `write_json` mit `_meta`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 3: Paket-Bereiche und cleanup

**Modell:** opus

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:build_plan(repo, rng, profile, focus, split_at, with_tests)`
- Produces: `fn:make_packet_range(repo, run_id, packet, base, target)`, `fn:cleanup(repo, run_id, stale)`

- [ ] **Step 1: Test schreiben** — `test_plan_packet_range_shows_only_the_packet`: Repo mit
      geänderter, neuer und gelöschter Datei in zwei Paketen; `git diff --name-status
      von..bis` je Paket nennt genau seine Dateien (M, A, D); `bis^{tree}` = Baum von ZIEL;
      `git status --porcelain`, Index-Hash und HEAD vor und nach gleich, auch mit einer
      ungespeicherten Änderung im Arbeitsbaum; im Repo ohne `user.name` baubar; Message von
      `bis` = Commit-Messages des Bereichs; `cleanup` hinterlässt keine Ref unter
      `refs/deep-review/<lauf>/`, `cleanup --stale` keine eines anderen Laufs.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k packet_range`.
- [ ] **Step 3: Implementieren** — temporärer Index nach E6: `read-tree ZIEL`, je
      Paketdatei `update-index --cacheinfo` mit Modus und Blob aus BASIS oder
      `--force-remove`, `write-tree`, `commit-tree` (von: Parent ZIEL; bis: Baum von ZIEL,
      Parent von), `update-ref refs/deep-review/<lauf>/<id>/von|bis`; `range` des Pakets in
      `plan.json`; bei `split: false` keine Refs; Hinweis im Plan, wenn ZIEL nicht HEAD ist
      oder der Arbeitsbaum in Paketdateien von ZIEL abweicht; `cleanup` über
      `update-ref --stdin`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 4: Gegenstellen für Python

Der Abnehmer des Prototyps: `counterparts.py` aus review-bench ist gemessen; seine
Auflösungsregeln (Importe der Datei, spezifischster Importpfad, voll qualifizierte
Modulpfade, „ohne Importbezug und mehr als drei gleichnamige: nichts") gehen unverändert über.

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:build_plan(repo, rng, profile, focus, split_at, with_tests)`, `fn:make_packet_range(repo, run_id, packet, base, target)`
- Produces: `fn:collect_python(repo, rng, files)`, `fn:render_block(packet, entries, unresolved, cap)`, `token:wirft:`

- [ ] **Step 1: Test schreiben** — `test_counterparts_python_except_and_raises` (Repo mit
      `app/groups.py`, das `except (ValueError, LookupError)` um einen Aufruf in
      `vendor/lib.py` verengt, der `TypeError` wirft: Block enthält `wirft:` mit
      `TypeError` und die `raise`-Zeile in `vendor/lib.py`); `test_counterparts_python_flag_flow`
      (geändertes `strict=False` → Weg über zwei Funktionen bis `if not strict`; ein Aufruf
      `pkg.mod.Klasse(...)` löst auf `pkg/mod.py` auf, nicht auf eine gleichnamige Klasse
      anderswo); `test_counterparts_python_no_guessing` (`.values()` ohne Importbezug bei
      vier gleichnamigen Definitionen: nicht im Block, `unresolved` zählt 1);
      `test_counterparts_cap` (über `BLOCK_MAX_CHARS` → gekappt, Zahl der weggelassenen
      Stellen im Block).
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k counterparts_python`.
- [ ] **Step 3: Implementieren** — geänderte Zeilen je Paket aus `git diff -U0` über den
      Paket-Bereich; Index aller Definitionen unter dem Repo per `ast` (Syntaxfehler
      überspringen und zählen); Sammelregel der Spec; Zeilenformat
      `- Gegenstelle <Name> [<datei>:<zeile>]: <Signatur>`, `  wirft: <Typen>`,
      `    raise <Typ> at <datei>:<zeile>`, `  geändert: <arg>=<wert>; Weg:`;
      `counterparts --run <lauf>` schreibt `packets/<id>.md` mit Kopfzeile.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 5: Gegenstellen für Delphi

**Modell:** opus

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:render_block(packet, entries, unresolved, cap)`
- Produces: `fn:mask_pascal(text)`, `fn:collect_delphi(repo, rng, files)`

- [ ] **Step 1: Test schreiben** — `test_counterparts_delphi`: Units `Tree.pas`
      (`TQueryTree = class(TObjectList<TNode>)`, Konstruktor mit `inherited Create(True)`,
      `procedure Parse(const S: string; AMax: Integer = 0)` im `interface`-Teil, `raise
      EParse.Create` in der Implementierung) und `Query.pas` (`uses Tree`; der Diff ersetzt
      `ATree.Remove(N)` durch `ATree.Extract(N)` auf einem Parameter `ATree: TQueryTree` und
      ruft `Parse(S)`): Block nennt die Klassendeklaration, `inherited Create(True)`, den
      Besitz-Default von `TObjectList`, den Kopf mit `AMax: Integer = 0` und `raise EParse`;
      ein `end` in einem String und in `{ … }`- und `//`-Kommentaren verschiebt nichts.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k counterparts_delphi`.
- [ ] **Step 3: Implementieren** — `mask_pascal` blendet `'…'`-Strings, `{ }`, `(* *)` und
      `//` aus, Zeilen bleiben erhalten; Methodenköpfe `procedure|function|constructor|
      destructor TKlasse.Name` im `implementation`-Teil, Rumpf über `begin`/`case`/`try`/
      `asm`/`record` gegen `end`; `uses`-Listen von `interface` und `implementation`; Typ des
      Empfängers aus Parameterliste, `var`-Abschnitt oder Klassenfeld; Klassendeklaration mit
      Basisklasse und `inherited Create(…)`; Besitz-Default für `TObjectList<…>` und
      `TObjectDictionary<…>`; dasselbe Zeilenformat wie Python.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 6: Datei-Schlüssel und --since

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:collect_python(repo, rng, files)`, `fn:collect_delphi(repo, rng, files)`, `fn:cut_packets(files, packet_size)`
- Produces: `fn:file_keys(repo, target, files, entries)`, `fn:apply_since(plan, run_dirs)`

- [ ] **Step 1: Test schreiben** — `test_since_per_file`: Lauf A über `t0..t1` mit Funden zu
      `a.py` und `b.py`; Lauf B über `t0..t2`, in dem `a.py` gleich blieb, `b.py` sich
      änderte und `c.py` die Gegenstelle von `a.py` ist und sich änderte: `a.py` wird neu
      reviewt (Schlüssel über die Gegenstelle geändert), ohne Änderung an `c.py` übernimmt
      `a.py` die Funde aus A mit `reused_from`; `b.py` neu; zwei frühere Läufe mit derselben
      Datei → der jüngere gilt.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k since`.
- [ ] **Step 3: Implementieren** — Schlüssel je Datei = SHA-256 über Inhalt am ZIEL und die
      Gegenstellen-Zeilen (Signatur, `raise`) ihrer Stellen; `plan --since` liest
      `plan.json` und `results/*.json` früherer Läufe, übernimmt Funde je Datei, packt die
      übrigen Dateien neu; übernommene Dateien stehen in `file_keys` mit `reused_from`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 7: record, merge und audit

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:write_json(path, meta, payload)`, `fn:apply_since(plan, run_dirs)`
- Produces: `fn:record(run_dir, packet, tool, payload_path)`, `fn:merge(run_dir)`, `fn:audit(run_dir, report_path)`, `fn:main(argv)`, `token:findings.json`

- [ ] **Step 1: Test schreiben** — `test_record_rejects_unknown_or_duplicate` (unbekanntes
      Paket und zweites Ergebnis → Exit 1, nichts geschrieben; leere Liste angenommen);
      `test_merge_keeps_every_finding` (zwei Funde derselben Datei mit Abstand 2 → einer mit
      beiden Paketen, Abstand 5 → zwei; `findings.json` mit `_meta` und `findings`);
      `test_audit` (fehlendes Ergebnis → `missing`, Ergebnis eines anderen Plans → `stale`,
      Fund fehlt in `findings.json` → `lost_findings`, Bericht mit „vollständig" trotz Lücke
      oder falscher Fundzahl → `report_mismatch`, je `complete: false`; sauberer Lauf →
      `true`; übernommene Funde aus `--since` zählen).
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k "record or merge or audit"`.
- [ ] **Step 3: Implementieren** — `record` liest die JSON-Liste von `/code-review`
      (`file`, `line` als Zahl, Text oder `null`, `summary`, `failure_scenario`) oder die
      Liste aus dem Brief; `merge` mit `MERGE_LINE_GAP`; `audit` liest `report.md` (Kopfzeile,
      Zahl der Funde, Wort „vollständig"); `main(argv)` mit allen Unterbefehlen, Exit 0/1.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 8: fix-task liest findings.json

**Files:**
- Modify: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: `token:findings.json`
- Produces: (nichts Neues)

- [ ] **Step 1: Test schreiben** — `test_fix_task_reads_deep_review_findings`: eine
      `findings.json` mit `_meta` und `findings` (ein Fund mit `packets`, einer mit `line`
      `null`) ergibt eine Task-Datei mit beiden Dateien in der Allowlist; leere `findings` →
      Exit 1; JSON-Liste von `/code-review` und `verdicts.jsonl` bleiben lesbar.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_subagent_dev_plan_to_tasks.py -k deep_review_findings`.
- [ ] **Step 3: Implementieren** — `_read_findings` erkennt ein Objekt mit `findings` und
      behandelt es wie die JSON-Liste; Docstring und `--help` von `fix-task` nennen
      `findings.json` (Spec 26) statt nur `verdicts.jsonl`; `python scripts/sync_skills.py`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 9: references/packets.md und references/counterparts.md

**Files:**
- Create: `skills/deep-review/references/packets.md`
- Create: `skills/deep-review/references/counterparts.md`

**Interfaces:**
- Consumes: `fn:main(argv)`, `token:wirft:`
- Produces: `token:Schnittregel`, `token:Gegenstellen nicht gesammelt`

- [ ] **Step 1: Schreiben** — packets.md: Schwellen aus E7, Schnittregel mit Vorrang, IDs,
      `not_reviewed`, Paket-Bereich über Hilfscommits und was der Reviewer dabei sieht,
      Datei-Schlüssel und `--since`, Fortsetzen mit `--run <lauf>`, `cleanup --stale`.
      counterparts.md: Sammelregel je Sprache, Zeilenformat, was nicht gesammelt wird
      (andere Sprachen: „Gegenstellen nicht gesammelt"), Lesehilfe für den Reviewer
      (eine `wirft:`-Zeile neben einer geänderten `except`-Klausel, ein `Weg:` bis zur
      Bedingung). Beispiele mit eigenen Namen, keiner aus den Fixtures.
- [ ] **Step 2: Prüfen** — jede Konstante aus E7 kommt in packets.md mit dem Wert aus dem
      Skript vor (`grep`), keine Fixture-Bezeichner (`grep -E "grouplib|TQueryTree"` leer).
- [ ] **Step 3: Commit.**

### Task 10: references/review-brief.md und references/delphi.md

**Files:**
- Create: `skills/deep-review/references/review-brief.md`
- Create: `skills/deep-review/references/delphi.md`

**Interfaces:**
- Consumes: `token:Schnittregel`
- Produces: `token:Review ohne /code-review`, `token:Besitz und Freigabe`

- [ ] **Step 1: Schreiben** — review-brief.md: Auftrag je Paket für `/code-review` (Bereich
      `von..bis`, Block jedem Unteragenten unverändert mitgeben, Vertrag der Gegenstelle
      prüfen, JSON-Liste mit `file`, `line`, `summary`, `failure_scenario` zurück), Fassung
      für Fokus `quality` (nur Wartbarkeit, Doppelung, Vereinfachung, je mit Grundlage) und
      die Fassung „Review ohne /code-review" für den Hauptkontext. delphi.md: Prüfliste
      Besitz und Freigabe (`try/finally`, Owner, `Extract` gegen `OwnsObjects`,
      Besitzübergabe an Antwort-Objekte), 1-basierte Strings, Record-Kopien aus
      `TryGetValue`, `TDateTime` in Tagen, UTC gegen Ortszeit, Interface-Referenzzählung
      gemischt mit Objektreferenzen, verschluckte Exceptions — je mit einer Frage und einer
      Eingabe zum Durchspielen.
- [ ] **Step 2: Prüfen** — keine Fixture-Bezeichner (`grep -E "grouplib|TQueryTree|Query\.pas"`
      leer); das Rückgabeformat in review-brief.md nennt dieselben Felder wie `record`.
- [ ] **Step 3: Commit.**

### Task 11: assets/report-template.md

**Files:**
- Create: `skills/deep-review/assets/report-template.md`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:audit(run_dir, report_path)`
- Produces: `token:Nicht geprüft`, `token:unvollständig`

- [ ] **Step 1: Schreiben** — Kopfzeile `<!-- skill: deep-review | schema: 1 | run: … |
      range: … | profile: … | focus: … | tool: … -->`, Tabelle der Pakete (Dateien, Zeilen,
      Gegenstellen, Funde, `reused_from`), je Fund eine Zeile `datei:zeile — Zusammenfassung`,
      Abschnitte „Nicht geprüft" und „Abdeckung" mit dem Satz zum Hauptagenten (Review je
      Paket ist Auskunft, kein Beleg) und der Grenze von `--max-findings all`.
- [ ] **Step 2: Prüfen** — `test_report_template`: das Template ohne Funde hat höchstens
      `REPORT_BASE_LINES` Zeilen, seine Kopfzeile passt auf `ARTIFACT_HEADER_RE`, `audit`
      auf einem Lauf mit diesem Template und sauberen Daten meldet `complete: true`.
- [ ] **Step 3: Commit.**

### Task 12: Evals

**Files:**
- Create: `evals/deep-review/evals.json`
- Create: `evals/fixtures/dr-split/fixture.json`
- Create: `evals/fixtures/dr-split/README.md`
- Create: `evals/fixtures/dr-contract/fixture.json`
- Create: `evals/fixtures/dr-contract/README.md`
- Create: `evals/fixtures/dr-delphi/fixture.json`
- Create: `evals/fixtures/dr-delphi/README.md`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:main(argv)`, `token:Nicht geprüft`
- Produces: `token:anti-ceremony-small-range-one-packet`

- [ ] **Step 1: Fixtures** — je `"git": true`, `README.md`, Tag `base`: `dr-split` rund 450
      geänderte Zeilen in drei Verzeichnissen; `dr-contract` unter 100 Zeilen, `app/groups.py`
      verengt `except (ValueError, TypeError)` vor einem Aufruf in `vendor/grouplib.py`, der
      `TypeError` wirft; `dr-delphi` unter 100 Zeilen, `Tree.pas` mit
      `TQueryTree = class(TObjectList<TNode>)` und `inherited Create(True)`, `Query.pas`
      ersetzt `Remove` durch `Extract` auf einem Parameter dieses Typs.
- [ ] **Step 2: Evals** — `anti-ceremony-small-range-one-packet`,
      `large-range-is-split-and-covered`, `narrowed-except-gets-callee-raises`,
      `delphi-extract-shows-ownership`, `security-focus-is-one-packet`,
      `routing-large-branch-without-skill-name` mit Assertions, Globs und Prompts der Spec,
      Diskriminator-Frage in `notes`; Eval 6 als stochastisch markiert.
- [ ] **Step 3: Test** — `test_evals_and_fixtures`: `evalkit.schema.load_evals` lädt sechs
      Evals; `prepare()` baut jede Fixture; `review_kit.py plan` auf `dr-split` mit
      `--split-at 200` ergibt mindestens `p3`; die Muster aus Eval 3 und 4 treffen
      `packets/p1.md` aus `counterparts` auf `dr-contract` und `dr-delphi`; das Muster aus
      Eval 1 trifft `plan.json` von `dr-seeded`. Commit.

### Task 13: Nachbarn

Plugin-Zuordnung und Projekt-Kopie von deep-review stehen im Task SKILL.md, weil
`test_every_skill_in_exactly_one_plugin` und `test_project_copies_match_originals` eine
vorhandene `SKILL.md` verlangen. Ein **deep-review** in einer Abgrenzung vor dieser Datei
ergibt bei den Nachbarn `unchecked`, keinen Befund.

**Files:**
- Modify: `specs/Spec 00 – skill-foundation.md`
- Modify: `specs/Spec 27 – subagent-dev-checkpoints.md`
- Modify: `README.md`
- Modify: `skills/review-context/SKILL.md`
- Modify: `skills/subagent-dev/SKILL.md`
- Modify: `skills/subagent-dev/references/checkpoints.md`
- Modify: `skills/debug-ledger/SKILL.md`
- Modify: `skills/test-first/SKILL.md`
- Modify: `.claude/skills/review-context/`
- Modify: `.claude/skills/subagent-dev/`
- Modify: `.claude/skills/debug-ledger/`

**Interfaces:**
- Consumes: `token:anti-ceremony-small-range-one-packet`, `token:findings.json`
- Produces: `token:deep-review`

- [ ] **Step 1: Routing** — Spec 00 §5: neue Zeile „großen Bereich oder Prüfpunkt gründlich
      prüfen" mit deep-review unter „zuständig"; Zeile „Diff prüfen" nennt deep-review unter
      „nicht"; Zeile „Sicherheit": deep-review reicht Fokus security an `/security-review`
      durch und ist keine Sicherheits-Skill. README: Routing-Zeile unter „Responsible",
      Skill-Liste von `evaluated-dev`. Plugin-Zuordnung: im Task SKILL.md.
- [ ] **Step 2: Schnittstelle Spec 27** — checkpoints.md „Review am Prüfpunkt" und Fix-Pfad:
      deep-review `--profile checkpoint|standard` statt `--depth`, `findings.json` statt
      `verdicts.jsonl`, `--since` je Datei, keine Grenze von 15 Verifikationen, Ersatz
      `/code-review` für Repos ohne die Skill; subagent-dev/SKILL.md zeilenneutral (145 von
      150); Spec 27 an denselben Stellen (Datei-Tabelle, Prüfpunkt-Abschnitt, Fix-Pfad).
- [ ] **Step 3: Rückverweise** — review-context, debug-ledger, test-first: Abgrenzung nennt
      **deep-review** nach der Spec. `python scripts/sync_skills.py`, dann `--check`;
      `lint_skill.py --base HEAD` je geänderter Skill ohne neuen Befund, `evals_due`
      notieren.
- [ ] **Step 4: Prüfen** — volle Suite grün. Commit.

### Task 14: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `token:deep-review`
- Produces: (nichts Neues)

- [ ] **Step 1: Abschnitt** — `## deep-review`: Review je Paket ist Auskunft des
      Hauptagenten; Schwellen ungemessen zwischen 800 und 2.000 Zeilen; Kontext über viele
      Pakete in einem Hauptkontext ungemessen; Gegenstellen nur Python und Delphi, Delphi
      ungemessen; `--max-findings all` bleibt als Wahl des Nutzers gesetzt, ohne Stufe die
      zuletzt getippte; `/security-review` nimmt vermutlich keinen Bereich, Sicherheit und
      Qualität ungemessen; Hilfscommits unter `refs/deep-review/` bei Abbruch bis
      `cleanup --stale`; Eval-Timeout 600 s bei mehreren `/code-review`-Läufen; Routing-
      Kollision mit `/code-review`. Commit.

### Task 15: SKILL.md

**Files:**
- Create: `skills/deep-review/SKILL.md`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `scripts/sync_skills.py`
- Create: `.claude/skills/deep-review/`

**Interfaces:**
- Consumes: `fn:main(argv)`, `token:Schnittregel`, `token:Review ohne /code-review`, `token:Besitz und Freigabe`, `token:Nicht geprüft`, `token:unvollständig`, `token:deep-review`
- Produces: `token:Eiserne Regel`

- [ ] **Step 1: Frontmatter** — `name`, Description mit Triggern („großen Branch prüfen",
      „gründlich", „Prüfpunkt", „in Paketen", „wurde jedes Stück angeschaut",
      „Sicherheitsreview mit deep-review") und Abgrenzung gegen `/code-review` (kleiner Diff,
      Pfad), `/security-review`, review-context; kein Prozessverb.
- [ ] **Step 2: Rumpf** — Eiserne Regel; Ablauf in sechs Schritten mit den Aufrufen von
      `review_kit.py`, Bootstrap-Satz (`.skills/cache/deep-review/` und `refs/deep-review/`);
      Profile-und-Fokus-Tabelle; Übergabe mit Lauf-ID und „unvollständig" bei Lücke;
      Contract; Anti-Rationalisierung (etwa „das Paket ist klein, den Block lasse ich weg",
      „das Audit meldet nur ein fehlendes Paket, ich nenne es trotzdem fertig"); Abgrenzung
      mit **review-context**, **subagent-dev**, **debug-ledger**, **test-first**.
- [ ] **Step 3: Plugin und Kopie** — `./skills/deep-review` in `evaluated-dev`;
      `deep-review` in `PROJECT_SKILLS`; `python scripts/sync_skills.py`, dann `--check`.
- [ ] **Step 4: Prüfen** — `wc -l` unter 150; `lint_skill.py skills/deep-review` ohne
      Befund (Register bleibt bei 77); volle Suite grün. Commit.

### Task 16: Report

**Files:**
- Modify: `docs/superpowers/reports/deep-review-report.md`

**Interfaces:**
- Consumes: `token:Eiserne Regel`, `token:dr-seeded`, `token:Was nicht gemessen wurde`
- Produces: (nichts Neues)

- [ ] **Step 1: Abnahme** — mit `docs/superpowers/reports/review-bench/` je zwei Läufe
      deep-review im Profil `standard` auf `py-diff` und `dl-diff`, je ein Lauf auf
      `dr-contract` und `dr-delphi`; Treffer, P2/P4, `total_cost_usd` gegen die Basislinie
      (4,5 bzw. 5,0 von 6; 1,06 bzw. 2,33 USD); Abschaltungen ohne Gegenstellen und ohne
      Delphi-Prüfliste je ein Lauf.
- [ ] **Step 2: Evals** — alle sechs mit Skill und einmal ohne (Spec 18); die Evals von
      review-context, subagent-dev, debug-ledger und test-first, wo `evals_due` aus Task 13
      `true` war.
- [ ] **Step 3: Report** — Messmenge, Grenzwerte aus E7, Ergebnis je Stufe, welche Stufe
      rausfliegt, „## Was nicht gemessen wurde" aktualisiert. `lint_skill.py
      skills/deep-review` sauber. Commit.
