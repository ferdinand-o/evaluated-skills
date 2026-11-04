<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# deep-review B Implementation Plan

**Goal:** deep-review findet auf jeder Eingabe, die es annimmt (großer und kleiner Diff, Pfad,
Python, Delphi, TypeScript und weitere Sprachen), im Mittel mindestens so viel wie
`/code-review`, mehr, wo der Vertrag außerhalb des Diffs liegt, kostet auf großen Diffs
höchstens das Doppelte und belegt je Paket, dass der Reviewer den Gegenstellen-Block bekam.

**Architecture:** Tier 1 wie in Spec 26. Der Code bleibt in
`skills/deep-review/scripts/review_kit.py` (Stdlib): neue Unterbefehle `report`, `verify`,
`verdict`; Paket-Auftrag mit Marke; Spannen innerhalb einer Datei; Pfad-Modus; Sammler für
TypeScript/JavaScript und ein Namens-Rückfall; Gegenstellen einmal gesammelt. Dazu eine
kleine Änderung an `fix-task` in subagent-dev und ein Werkzeug `crb` im Review-Bench. Vor dem
Bau misst eine Sonde, welche Stufe von `/code-review` je Paket reicht, ob der Block die Treffer
trägt und wie der Block den Reviewer erreicht; ihr Ergebnis legt Task 12 fest.

**Gemessen vor dem Plan** (2026-11-04, ohne bezahlte Läufe): `match.py` gleicht die
gespeicherten Läufe `py-diff-dr-1` (7/8: P1–P6, R1) und `dl-diff-dr-1` (6/6) schon über
`.kit/<lauf>/findings.json` ab; der Eintrag dazu in `docs/known-limits.md` ist veraltet und
wird in Task 13 berichtigt, nicht repariert. `run.sh` gibt `dr` nur `Edit` im Laufordner;
seit `review_kit.py report` den Bericht schreibt (Task 5), braucht `dr` kein `Write`.

**Lesson aus Spec 23, 24 und 26:** Fixture-Werte nie als Beispiel in SKILL.md oder References;
`verify` vor jedem Merge mit `rc=$?` auswerten, nie hinter `tail`.

**Tech Stack:** Python 3.11+ Stdlib für Skript und Tests; Git-Plumbing (`read-tree`,
`apply --cached`, `write-tree`, `commit-tree`, `update-ref`); Bash für den Bench; Markdown
für Skill, References, Evals.

**Spec:** `specs/Spec 28 – deep-review-b.md`

## Global Constraints

- **E1 — Tier 1, nur Stdlib.** Aufruf in der SKILL.md als
  `python "${CLAUDE_SKILL_DIR}/scripts/review_kit.py"`, in References ohne Pfad. Ohne
  `/code-review` läuft dieselbe Paketfolge nach `references/review-brief.md`.
- **E2 — Gate-Sprache:** Abdeckung, Marke, Bericht und Urteile meldet `audit` bzw. `record`
  und `verdict` (G2); dass je Paket ein Review lief, verlangt die SKILL.md (G1). Kein Hook.
- **E3 — Kopfzeile je Artefakt:** neue Dateien (`packets/<id>.prompt.md`, `verify/<n>.md`,
  `verdicts/<n>.json`, der Gegenstellen-Speicher) tragen `_meta` bzw. die HTML-Kopfzeile;
  `report.md` schreibt nur `review_kit.py report`.
- **E4 — SKILL.md ≤ 150 Zeilen**, portables Frontmatter.
- **E5 — Anti-Zeremonie-Eval** `anti-ceremony-small-diff-script-report`.
- **E6 — Nichts im Arbeitsbaum des Nutzers.** Auch Teil-Hilfscommits (Spannen) und der
  Pfad-Modus laufen über einen temporären Index; HEAD, Index und Arbeitsbaum bleiben
  unverändert.
- **E7 — Grenzwerte als Konstanten** am Kopf von `review_kit.py`: neu `PATH_SPLIT_AT = 5000`,
  `PATH_PACKET_SIZE = 2500`, `LEVELS = ("low", "medium", "high", "xhigh", "max")`,
  `PROFILE_LEVELS` (Werte aus der Sonde, Task 2).
- **E8 — Läufe aus Spec 26 bleiben lesbar.** Neue Felder in `plan.json`, Ergebnissen und
  `findings.json` sind optional mit Standard; Schema bleibt 1. Ein Plan ohne `mode` ist
  `range`, ein Paket ohne `spans` umfasst ganze Dateien, ein Ergebnis ohne `marke` gilt als
  `no_block`.

## Skill-Struktur

```
skills/deep-review/
├── SKILL.md
├── references/packets.md, counterparts.md, review-brief.md, delphi.md
├── assets/report-template.md   (entfällt in Task 5)
└── scripts/review_kit.py

evals/deep-review/evals.json, evals/fixtures/dr-bigfile/, evals/fixtures/dr-ts/
tests/test_deep_review_kit.py, tests/test_subagent_dev_plan_to_tasks.py
docs/superpowers/reports/review-bench/run.sh, README.md
skills/subagent-dev/scripts/plan_to_tasks.py, skills/subagent-dev/references/checkpoints.md
docs/superpowers/reports/deep-review-report.md, docs/known-limits.md
specs/Spec 00 – skill-foundation.md, README.md, .claude/skills/ (Kopien)
```

### Task 1: Review-Bench: Werkzeug crb und dr auf Pfaden

`crb` ist das Messwerkzeug der Sonde: ein einzelnes `/code-review <stufe>` über einen Bereich,
dem `review_kit.py` aus diesem Repo den Gegenstellen-Block mitgibt. `dr` auf Pfaden braucht
den Pfad-Modus (Task 7) und wird erst in der Abnahme gefahren; die Sperre in `run.sh` fällt
schon hier, weil sie dieselbe Datei betrifft.

**Files:**
- Modify: `docs/superpowers/reports/review-bench/run.sh`
- Modify: `docs/superpowers/reports/review-bench/README.md`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `token:crb`

- [ ] **Step 1: crb** — in `run.sh` ein Fall `crb`: Stufe aus `LEVEL` (Standard `medium`,
      erlaubt `low|medium|high`), vor dem Lauf `review_kit.py plan --range <bereich>
      --split-at 100000` und `counterparts --run <lauf>` im Workspace, dann
      `/code-review $LEVEL --max-findings all <bereich>` mit dem Inhalt von `packets/p1.md`
      über `--append-system-prompt` (Wortlaut wie bei `crx`). Ausgabename
      `<repo>-crb-<stufe>-<nr>`.
- [ ] **Step 2: dr auf Pfaden** — die Abweisung von `dr`/`drnc` auf `*-path` entfernen; der
      Prompt lautet dort `Prüf die Pfade <liste> mit deep-review.`
- [ ] **Step 3: Prüfen** — `bash -n run.sh`; `run.sh` ohne `BENCH` endet mit Exit 2 ohne
      etwas anzulegen; README-Tabelle der Werkzeuge nennt `crb` mit Timeout.
- [ ] **Step 4: Commit.**

### Task 2: Sonde B

Messung vor dem Bau, rund 9 USD. Ohne Freigabe des Nutzers läuft kein bezahlter Lauf; dann
bleiben die Annahmen der Spec stehen, und der Report sagt das.

**Files:**
- Modify: `docs/superpowers/reports/deep-review-report.md`
- Modify: `specs/Spec 28 – deep-review-b.md`

**Interfaces:**
- Consumes: `token:crb`
- Produces: `token:Sonde B`

- [ ] **Step 1: Freigabe** — Budget der Sonde (rund 9 USD) vom Nutzer bestätigen lassen;
      Bench nach README neu bauen, falls `$BENCH/repos` fehlt.
- [ ] **Step 2: Läufe** — `run.sh py-diff drnc 1`; `run.sh dr-contract cr 1..2` und
      `run.sh dr-delphi cr 1..2` (die Fixtures als Bench-Repos über `build.sh`, Treffer aus
      dem README der Fixture); `LEVEL=low|medium|high run.sh py-c1 crb 1`.
- [ ] **Step 3: Übergabe des Blocks** — ein headless-Lauf `/code-review medium` über `py-c1`
      mit einer Marke `sonde-<zufall>` im Aufruf; in den Transkripten seiner Unteragenten
      (`<projektordner>/<sitzung>/subagents/`) nach der Marke suchen. Ein zweiter Lauf, in dem
      ein Unteragent (Agent-Werkzeug) `/code-review low` über `py-c1` startet: läuft es,
      startet es eigene Unteragenten, kommt ein Ergebnis zurück?
- [ ] **Step 4: Report** — Abschnitt „Sonde B" mit Tabelle (Lauf, Treffer am Text, Kosten)
      und den drei Entscheidungen: Stufe je Profil (billigste mit P2 und P4 für `standard`,
      eine höher für `checkpoint`), Block bleibt oder fliegt (Regel aus Spec 28, Open
      questions), Schritt 4 im Hauptkontext oder je Paket ein Unteragent. Dieselben drei als
      Ergebnis in die Open questions von Spec 28.
- [ ] **Step 5: Commit.**

### Task 3: review_kit: Gegenstellen einmal sammeln, Stufe im Plan

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `token:Sonde B`
- Produces: `fn:store_collected(run_path, collected)`, `fn:load_collected(run_path)`, `PROFILE_LEVELS`

- [ ] **Step 1: Test schreiben** — `test_b_counterparts_collected_once`: nach `plan` liegt
      der Speicher im Laufordner, `counterparts` ruft `collect_python` und `collect_delphi`
      nicht erneut (Monkeypatch zählt Aufrufe); `plan.json` trägt `level` nach
      `PROFILE_LEVELS[profile]`, `--level` überschreibt, `max` nur mit `--level max`; die
      erste Ausgabe nennt `Reviews: <n> × /code-review <stufe>`; ein Plan ohne `level`
      (Spec 26) liest sich mit dem Standard des Profils.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k test_b_counterparts_collected_once`.
- [ ] **Step 3: Implementieren** — `build_plan` legt die gesammelten Einträge mit
      `store_collected` ab (JSON mit `_meta`, je Datei Einträge und nicht aufgelöste);
      `write_counterparts` nimmt `load_collected` und sammelt nur, wenn der Speicher fehlt
      oder nicht zum Plan passt; `LEVELS`, `PROFILE_LEVELS` mit den Werten aus der Sonde.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 4: review_kit: Paket-Auftrag mit Marke

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:load_collected(run_path)`, `PROFILE_LEVELS`
- Produces: `fn:packet_marker(run_id, packet_id)`, `fn:write_prompt(run_path, packet, block, level)`, `fn:record(run_path, packet, tool, payload_path, no_block)`

- [ ] **Step 1: Test schreiben** — `test_b_record_needs_packet_marker`: `counterparts`
      schreibt `packets/<id>.prompt.md` mit Auftrag, Bereich, Stufe, Block und letzter Zeile
      `Paket-Marke: dr-…`; `record` mit Objekt `{"marke", "findings"}` und passender Marke →
      angenommen; ohne Marke, mit Marke eines anderen Pakets oder als bloße Liste → Exit 1,
      nichts geschrieben; `--no-block` → angenommen mit `no_block: true`; `audit` listet
      solche Pakete unter `no_block`; ein Ergebnis aus Spec 26 ohne Marke gilt als
      `no_block`.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k test_b_record_needs_packet_marker`.
- [ ] **Step 3: Implementieren** — Marke aus Lauf, Paket und `secrets.token_hex(3)`, im Plan
      je Paket gespeichert; Auftragstext aus `references/review-brief.md` gelesen (Fassung nach
      Profil und Fokus), nicht im Skript dupliziert; `record` und CLI um `--no-block`;
      `audit.json` um `no_block`.
- [ ] **Step 4: Grün sehen**, volle Suite; bestehende `record`-Tests auf das Objekt umstellen
      oder `--no-block` setzen.
- [ ] **Step 5: Commit.**

### Task 5: review_kit: Bericht vom Skript

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`
- Delete: `skills/deep-review/assets/report-template.md`

**Interfaces:**
- Consumes: `fn:record(run_path, packet, tool, payload_path, no_block)`
- Produces: `fn:render_report(run_path)`, `fn:write_report(run_path)`

- [ ] **Step 1: Test schreiben** — `test_b_report_is_written_by_the_script`: `report --run`
      schreibt Kopfzeile (mit `generated: python scripts/review_kit.py report …`, Stufe und
      Werkzeug), `Funde:`, `- Hinweise:`, `- Übernommen (--since):`, `- Nicht geprüft:`,
      `- Abdeckung:`, Pakettabelle, Fundzeilen; `audit` danach `complete: true`; eine
      geänderte Fundzeile → `report_mismatch`; angefügtes `## Einordnung` → keine Abweichung;
      Längengrenze bei `split: false` hält. Tests, die die Vorlage lesen
      (`test_report_template`, `test_cp8_f1_…`), auf `render_report` umstellen.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k test_b_report_is_written_by_the_script`.
- [ ] **Step 3: Implementieren** — `render_report` erzeugt den Text aus `plan.json`,
      `findings.json` und einer vorläufigen Abdeckung; `audit` vergleicht alle Zeilen bis
      `## Einordnung` mit `render_report` statt der regulären Ausdrücke; Vorlage löschen.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 6: review_kit: Spannen in großen Dateien

**Modell:** opus

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:write_report(run_path)`
- Produces: `fn:split_file_spans(repo, rng, path, packet_size)`

- [ ] **Step 1: Test schreiben** — `test_b_big_file_split_at_definitions`: eine Python-Datei
      mit 1.300 geänderten Zeilen → mindestens zwei Pakete mit `spans`, jede Grenze auf einer
      Zeile mit `def` oder `class` der obersten Ebene; Delphi an einer Routinengrenze; eine
      Datei ohne Sammler an der größten Hunk-Lücke; `von..bis` je Paket zeigt nur die Hunks
      seiner Spanne, `bis^{tree}` = Baum des Ziels; HEAD, Index, Arbeitsbaum unverändert;
      `merge` ordnet Funde nach Spanne; `--since` behandelt die Datei weiter als ein
      Schlüssel und übernimmt nur, wenn alle ihre Spannen ein Ergebnis haben.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k test_b_big_file_split_at_definitions`.
- [ ] **Step 3: Implementieren** — `cut_packets` ruft `split_file_spans` für Dateien über
      `packet_size`; `make_packet_range` baut `von` als Ziel-Baum, in dem die Hunks der
      Spanne per `git apply -R --cached --unidiff-zero` auf einem temporären Index
      zurückgenommen sind; `render_block` nimmt nur Einträge der Spanne.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 7: review_kit: Pfad-Modus

**Modell:** opus

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:split_file_spans(repo, rng, path, packet_size)`
- Produces: `fn:build_path_plan(repo, paths, profile, focus, with_tests)`

- [ ] **Step 1: Test schreiben** — `test_b_path_mode`: `plan --path src` → `mode: path`,
      `range` vom leeren Stand zum Ziel nur mit den Dateien des Pfads; bis
      `PATH_SPLIT_AT` ein Paket, darüber Pakete bis `PATH_PACKET_SIZE`; Gegenstellen nur für
      Aufrufe in Dateien außerhalb des Pfads; `--path` und `--range` zusammen → Exit 2;
      `--since` im Pfad-Modus → Exit 1 mit Meldung; `report` nennt den Pfad statt des
      Bereichs.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k test_b_path_mode`.
- [ ] **Step 3: Implementieren** — `build_path_plan` zählt die Zeilen des Pfads am Ziel,
      schneidet mit den Pfad-Grenzwerten und schreibt dieselben Dateien wie `build_plan`;
      Hilfscommits: `von` = Ziel-Baum ohne die Pfad-Dateien, `bis` = Ziel-Baum.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 8: review_kit: Sammler TypeScript und Namens-Rückfall

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:load_collected(run_path)`
- Produces: `fn:collect_typescript(repo, rng, files)`, `fn:collect_by_name(repo, rng, files)`

- [ ] **Step 1: Test schreiben** — `test_b_typescript_collector`: relativer `import` und
      `require` → Definition und `throw`-Zeilen bis `RAISE_DEPTH`; Aufruf einer
      `async`-Funktion ohne `await` → Eintrag; Strings, Template-Literale und Kommentare
      ignoriert; `node_modules` und Pfad-Aliase → nicht aufgelöst, gezählt.
      `test_b_name_fallback_marks_unique_names`: Go-Datei, eindeutiger Name → Definition mit
      „(Name eindeutig, ohne Sammler)" und `panic`-Zeile; zwei gleichnamige → nicht
      aufgelöst; Datei in einer Sprache ohne Eintrag → „Gegenstellen nicht gesammelt
      (Sprache)".
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k "test_b_typescript_collector or test_b_name_fallback_marks_unique_names"`.
- [ ] **Step 3: Implementieren** — Text-Scanner mit Maskierung wie `mask_pascal`; Endungen
      und Sprachen nach der Sammler-Tabelle in Spec 28; beide in `COLLECTORS`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 9: review_kit: verify und verdict, fix-task ohne widerlegte Funde

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`
- Modify: `skills/subagent-dev/scripts/plan_to_tasks.py`
- Modify: `tests/test_subagent_dev_plan_to_tasks.py`

**Interfaces:**
- Consumes: `fn:render_report(run_path)`
- Produces: `fn:write_verify(run_path)`, `fn:verdict(run_path, number, payload_path)`, `token:widerlegt`

- [ ] **Step 1: Test schreiben** — `test_b_verdict_needs_evidence`: `verify --run` schreibt
      je Fund ohne Beleg `verify/<n>.md` mit Datei, Zeile, Szenario, Commit und ohne
      `summary`-Begründung; `verdict` mit `widerlegt` ohne `beleg` → Exit 1; mit Beleg →
      `findings.json` trägt `verdict`, der Bericht zählt `Urteile:`; `plan --verify` und
      Profil `checkpoint` setzen `verify: true`, `audit` meldet fehlende Urteile dann als
      Lücke. `test_b_fix_task_skips_refuted`: `fix-task` lässt `widerlegt` weg und nennt
      die Zahl in der Task-Datei.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py tests/test_subagent_dev_plan_to_tasks.py -k "verdict or refuted"`.
- [ ] **Step 3: Implementieren** — `write_verify`, `verdict`, Feld `verdict` in `merge`,
      `render_report` und `audit`; in `plan_to_tasks.py` filtert `_deep_review_findings`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 10: References

**Files:**
- Modify: `skills/deep-review/references/packets.md`
- Modify: `skills/deep-review/references/counterparts.md`
- Modify: `skills/deep-review/references/review-brief.md`

**Interfaces:**
- Consumes: `fn:build_path_plan(repo, paths, profile, focus, with_tests)`, `fn:collect_typescript(repo, rng, files)`, `fn:write_verify(run_path)`
- Produces: `token:Paket-Marke:`, `token:Pfad-Modus`, `token:Name eindeutig, ohne Sammler`

- [ ] **Step 1: packets.md** — Spannen, Pfad-Modus mit `PATH_SPLIT_AT`/`PATH_PACKET_SIZE`,
      Stufe je Profil, Zeile `Reviews:`.
- [ ] **Step 2: counterparts.md** — TypeScript/JavaScript und Namens-Rückfall nach der
      Sammler-Tabelle der Spec, mit einem Beispiel, das keiner Fixture gleicht.
- [ ] **Step 3: review-brief.md** — Paket-Auftrag als Datei, Rückgabe als Objekt mit
      `Paket-Marke:`, `--no-block`, Prüfer-Auftrag für `verify` (nur Datei, Zeile, Szenario,
      Commit; Urteil mit Beleg).
- [ ] **Step 4: Prüfen** — `python skills/skill-forge/scripts/lint_skill.py skills/deep-review` ohne Befund in den
      References, `pytest tests/test_deep_review_kit.py`; Commit.

### Task 11: Evals

**Files:**
- Modify: `evals/deep-review/evals.json`
- Create: `evals/fixtures/dr-bigfile/fixture.json`
- Create: `evals/fixtures/dr-bigfile/README.md`
- Create: `evals/fixtures/dr-ts/fixture.json`
- Create: `evals/fixtures/dr-ts/README.md`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `token:Paket-Marke:`, `fn:write_report(run_path)`
- Produces: `evals_json`

- [ ] **Step 1: Fixtures** — `dr-bigfile`: neues Python-Modul mit rund 1.300 Zeilen über
      mehrere Klassen; `dr-ts`: `src/` fängt einen Fehler nicht mehr, den eine Funktion unter
      `lib/` wirft. Je Tag `base` und README mit dem Einbau.
- [ ] **Step 2: Evals** — `anti-ceremony-small-diff-script-report`,
      `packet-result-carries-marker`, `big-file-split-at-definitions`,
      `path-review-has-plan-and-audit`, `typescript-throw-gets-counterpart` mit Prompts und
      Assertions aus Spec 28; je Eval in `notes` die Diskriminator-Frage.
- [ ] **Step 3: Prüfen** — `test_evals_and_fixtures` spielt die neuen Evals mechanisch durch
      (plan, counterparts, record mit Marke, merge, report, audit, cleanup) und prüft die
      Assertions gegen die echte Ausgabe; `evalkit.schema.load_evals` lädt; Commit.

### Task 12: SKILL.md

**Files:**
- Modify: `skills/deep-review/SKILL.md`
- Modify: `.claude/skills/deep-review/SKILL.md`

**Interfaces:**
- Consumes: `evals_json`, `token:Sonde B`
- Produces: `token:Paket-Auftrag`

- [ ] **Step 1: Ablauf** — Schritt 1 nimmt Pfade (`plan --path`); Schritt 4 ruft
      `/code-review <stufe> --max-findings all <von>..<bis>` mit dem Inhalt von
      `packets/<id>.prompt.md` als Paket-Auftrag, im Hauptkontext oder je Paket in einem
      Unteragenten, wie die Sonde B entschieden hat; `record` mit Marke; Schritt 6 `report`
      statt Vorlage; `verify` im Profil `checkpoint`; Anti-Rationalisierung „den Block lasse
      ich weg" zeigt auf `record`, das ohne Marke abweist.
- [ ] **Step 2: Prüfen** — `wc -l` ≤ 150, `python skills/skill-forge/scripts/lint_skill.py skills/deep-review`,
      `python scripts/sync_skills.py` und `--check`, volle Suite.
- [ ] **Step 3: Commit.**

### Task 13: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `evals_json`
- Produces: (nichts Neues)

- [ ] **Step 1: Abschnitt deep-review** — behobene Grenzen streichen (zweimal gesammelt, Datei
      nie geteilt, Bericht per Regex, `dr` ohne `Write`, Block im Fork); den veralteten Eintrag
      zu `match.py` berichtigen; neue Grenzen: was die Marke belegt und was nicht, TS ohne
      Typinferenz und Aliase, Namens-Rückfall rät nur bei eindeutigen Namen, Pfad-Grenzwerte
      ungemessen, `verify`-Kosten. Commit.

### Task 14: Report

**Files:**
- Modify: `docs/superpowers/reports/deep-review-report.md`

**Interfaces:**
- Consumes: `evals_json`, `token:Paket-Auftrag`
- Produces: `token:Abnahme B`

- [ ] **Step 1: Freigabe** — Budget der Abnahme (rund 31 USD) vom Nutzer bestätigen lassen.
- [ ] **Step 2: Läufe** — nach der Tabelle „Abnahme B" der Spec: `dr` auf `py-diff` und
      `dl-diff` je zweimal, `dl-path` einmal, `dr-seeded`, `dr-contract`, `dr-delphi`,
      `dr-ts` je einmal, `cr` auf `dr-ts` zweimal; Evals 7–11 mit Skill; Präzision mit je
      zehn gezogenen Funden aus `cr` und `dr` auf `py-diff` und `dl-diff`, isoliert geprüft.
- [ ] **Step 3: Report** — Abschnitt „Abnahme B" mit Treffern am Text, Kosten, Schwellen je
      Eingabe, Präzision; „Was nicht gemessen wurde" nachziehen. Commit.

### Task 15: Nachbarn

**Files:**
- Modify: `specs/Spec 00 – skill-foundation.md`
- Modify: `README.md`
- Modify: `skills/deep-review/SKILL.md`
- Modify: `skills/subagent-dev/references/checkpoints.md`
- Modify: `skills/review-context/SKILL.md`

**Interfaces:**
- Consumes: `token:Abnahme B`
- Produces: (nichts Neues)

- [ ] **Step 1: Routing nach der Abnahme** — nur die Eingaben, deren Schwelle in „Abnahme B"
      erfüllt ist, wandern in Spec 00 §5, README und die Description von deep-review; die
      übrigen bleiben bei `/code-review`, und die Description nennt sie unter „Not for".
- [ ] **Step 2: Abgrenzungen** — `checkpoints.md`: `verify` am finalen Prüfpunkt und
      widerlegte Funde in `fix-task`; review-context nennt den Pfad-Modus. Plugin-Zuordnung
      unverändert (evaluated-dev).
- [ ] **Step 3: Prüfen** — `python scripts/sync_skills.py` und `--check`,
      `python skills/skill-forge/scripts/lint_skill.py skills/deep-review`, volle Suite; Commit.
