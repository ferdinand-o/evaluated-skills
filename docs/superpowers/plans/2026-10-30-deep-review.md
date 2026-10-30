<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# deep-review Implementation Plan

**Goal:** Ein Review in diesem Repo sagt nicht mehr „geprüft", weil das Modell es sagt,
sondern weil `review_kit.py audit` für jede Einheit des Inventars und jede ihr zugewiesene
Linse ein angenommenes Urteil findet und jeder Kandidat einen Status trägt — und die
Trefferquote gegen `/code-review` ist an `dr-seeded` gemessen, bevor die Skill als fertig gilt.

**Architecture:** Tier 1. Der einzige Code ist `skills/deep-review/scripts/review_kit.py`
(Stdlib) mit den Unterbefehlen `inventory`, `packets`, `record`, `merge`, `verdict`,
`audit`, `estimate`, `comments`, `metrics`; er schreibt alles unter
`.skills/cache/deep-review/<lauf>/` und ruft für das Soll
`review-context/scripts/collect_context.py` per Subprozess auf, gefunden relativ zu
`Path(__file__)` (in der Bash-Umgebung ist `${CLAUDE_SKILL_DIR}` nicht gesetzt). Fehlt
review-context (Eval-Workspace), steht „Soll ungeprüft". Suche, Verifikation, Ausführung
zuerst, Prüf-Worktree und Bericht verlangt die SKILL.md (G1); die References tragen die
Aufträge an Such- und Prüfagenten, die Linsen und die Sättigungsregel.

**Reihenfolge wegen des vollen Lint-Registers:** `tests/test_skills_lint.py` lintet jeden
Ordner unter `skills/` mit einer `SKILL.md`, und das Register ist voll (79 von 79). Die
SKILL.md entsteht deshalb erst, wenn Evals, Routing, Rückverweise, known-limits und ein
Report mit „## Was nicht gemessen wurde" schon liegen; im selben Task kommen
Plugin-Zuordnung und Projekt-Kopie dazu, weil `test_every_skill_in_exactly_one_plugin` und
`test_project_copies_match_originals` eine `SKILL.md` verlangen. So ist die Suite nach jedem
Task grün.

**Lesson aus Spec 23 und 24:** Fixture-Werte nie wörtlich als Beispiel in SKILL.md oder
References verwenden — sonst diskriminiert der Eval nicht. Eval-Prompts vor dem ersten
Lauf gegen die eigene `quick`-Regel prüfen.

**Tech Stack:** Python 3.11+ Stdlib für Skript und Tests; pytest in `dr-cross-file` und
`dr-seeded`; Markdown für Skill, References, Evals.

**Spec:** `specs/Spec 26 – deep-review.md`

**Stand 2026-10-30:** Task 1 gebaut, Tasks 2 bis 23 pausiert — siehe Spec 26, Next steps.

## Global Constraints

- **E1 — Tier 1, nur Stdlib.** `review_kit.py` importiert nichts außerhalb der Stdlib, der
  Docstring nennt „Tier 1"; Aufruf in der SKILL.md als
  `python "${CLAUDE_SKILL_DIR}/scripts/review_kit.py"`, nie in References (Regel
  `script-paths`). Ohne Subagenten läuft dieselbe Pipeline sequenziell, der Bericht sagt
  „Suche ohne frischen Kontext".
- **E2 — Gate-Sprache:** Abdeckung, Nonce-Abgleich, Status je Kandidat und
  Berichtskonsistenz meldet `audit` (G2); Suche, Verifikation und Bericht verlangt die
  SKILL.md (G1). Kein Hook, kein „blockiert".
- **E3 — Kopfzeile je Artefakt:** `inventory.json`, `audit.json`, `estimate.json`,
  `comments.json`, `metrics.json` per `_meta`; JSON-Lines mit `_meta` in Zeile 1;
  `packets/*.md` und `report.md` mit `<!-- skill: deep-review | schema: 1 | … -->`.
- **E4 — SKILL.md ≤ 150 Zeilen**, portables Frontmatter, Details in `references/`.
- **E5 — Anti-Zeremonie-Eval** `anti-ceremony-one-line-fix-stays-quick`, gebunden an
  `file_matches` auf `inventory.json`, `artifact_header`, `file_max_lines` und
  `git_head_unchanged`.
- **E6 — JSON-Lines-Format** (Spec 26, Constraints): `ensure_ascii=False`, Trennzeichen
  `", "` und `": "`, feste Schlüssel in fester Reihenfolge, `reason` und `evidence` als
  Zeichenketten, repo-relative POSIX-Pfade ohne `./`. Schlüsselfolge in `verdicts.jsonl`:
  `id`, `path`, `lines`, `class`, `status`, `reason`, `evidence`, `related`. Eine Funktion
  schreibt alle Zeilen.
- **E7 — Pfade unter `.skills/` zählen nie** als Einheit, in keinem Modus.
- **E8 — Grenzwerte als Konstanten** am Kopf von `review_kit.py` mit den Namen aus der
  Spec (`QUICK_MAX_LINES = 20`, `PACKET_MAX_CHARS = 8000`, `PATH_PACKET_MAX_CHARS = 16000`,
  `CHAIN_MAX_DEPTH = 4`, `CHUNK_LINES = 150`, `RISK_LENGTH = 80`, `RISK_CHURN = 5`,
  `HIGH_RISK_MIN = 2`, `SATURATION_MAX_RUNS = 6`, `JACKKNIFE_MIN_RUNS = 4`,
  `CHECKPOINT_MAX_VERIFICATIONS = 15`, `REPORT_QUICK_MAX_LINES = 40`); der Report nennt sie.

## Skill-Struktur

```
skills/deep-review/
├── SKILL.md
├── references/lenses.md, finder-prompt.md, verifier-prompt.md, saturation.md
├── assets/report-template.md
└── scripts/review_kit.py

evals/deep-review/evals.json
evals/fixtures/dr-small/, dr-cross-file/, dr-comments/, dr-seeded/, dr-seeded-clean/
tests/test_deep_review_kit.py
docs/superpowers/reports/deep-review-report.md, docs/known-limits.md
skills/review-context/, subagent-dev/, debug-ledger/, test-first/ (Abgrenzung)
specs/Spec 00 – skill-foundation.md, README.md, .claude-plugin/marketplace.json,
scripts/sync_skills.py, .claude/skills/deep-review/ und die Kopien der Nachbarn
```

### Task 1: dr-seeded und Basislinie

Die Spec verlangt die Messfixture als erste Aufgabe, damit die Abnahmeschwelle vor dem
Ausbau steht. Die saubere Fassung liegt als eigene Fixture `dr-seeded-clean` neben
`dr-seeded`, weil beide denselben Bereich `base..HEAD` brauchen und ein Workspace nur einen
HEAD hat. Je Fixture liegt eine `README.md` neben `fixture.json`, weil `evalkit.workspace`
den ersten Commit ohne `--allow-empty` anlegt und eine Fixture nur aus `fixture.json` dort
abbricht.

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

- [ ] **Step 1: Test schreiben** — `test_seeded_fixtures`: beide `fixture.json` mit
      `"git": true` und `commits` (erster Eintrag Gerüst mit Tag `base`, zweiter der Code);
      in `dr-seeded` laufen die mitgelieferten Tests grün und treffen keinen der fünf
      Fehler; `dr-seeded-clean` unterscheidet sich nur an den fünf Stellen.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k seeded_fixtures`.
- [ ] **Step 3: Fixtures bauen** — fünf Fehler verschiedener Klassen: `None` über zwei
      Dateien, Grenzwert um eins daneben, Ressourcenleck nur im Fehlerpfad, verschluckte
      Exception, Kommentar widerspricht Code; Lage und Klasse je Fehler in
      `fixture.json` unter `description`, nicht im Code.
- [ ] **Step 4: Basislinie messen** — je drei Läufe `/code-review` und ein einzelner
      Sonnet-Lauf ohne Inventar über `base..HEAD` beider Fixtures mit `claude -p`; je Lauf
      gefundene der fünf, Fehlalarme auf `dr-seeded-clean`, `total_cost_usd`. Report
      anlegen mit Kopfzeile, Abschnitt „Basislinie" und „## Was nicht gemessen wurde"
      (deep-review selbst noch nicht).
- [ ] **Step 5: Grün sehen**, volle Suite; Commit.

### Task 2: Lauf-ID, JSON-Lines und Python-Inventar

**Files:**
- Create: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `fn:main(argv)`, `fn:new_run_id(repo)`, `fn:dump_line(obj)`, `fn:python_units(path, text)`, `fn:build_inventory(repo, args)`

- [ ] **Step 1: Tests schreiben** — `test_run_ids_do_not_collide` (zwei IDs in derselben
      Sekunde am selben Commit verschieden, Form `<JJJJ-MM-TT>-<HHMMSS>-<kurz-sha>-<4
      Zeichen>`); `test_jsonl_format` (`_meta` in Zeile 1, Schlüsselreihenfolge,
      `ensure_ascii=False`, Trennzeichen, `reason`/`evidence` als Zeichenketten, Pfade ohne
      `./`); `test_inventory_python` (Funktionen, Methoden, verschachtelte Funktionen; Hash
      ändert sich nur mit dem Inhalt; Modus `diff`: geänderte Einheiten, direkte Aufrufer
      mit Linse Vertrag, gelöschte Funktion als Vorher-Einheit; `.skills/` zählt nicht).
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k "run_ids or jsonl or inventory_python"`.
- [ ] **Step 3: Implementieren** — Konstanten nach E8; `inventory --mode diff|path|repo`
      mit `--range`, `--entry`, `--dir`; Einheiten per `ast` mit Datei, Zeilen, Hash,
      Risikomerkmalen (Auth, SQL, Dateisystem, Netz, Shell, Geld, Parsing als Wortlisten
      über Code und Importe; Länge ab `RISK_LENGTH`; Änderungshäufigkeit aus
      `git log --since=1.year` ab `RISK_CHURN`), Linsen; Bootstrap-Zeile beim ersten
      Anlegen von `.skills/cache/deep-review/` auf stderr.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 3: Aufrufkette, Tiefen und Profile

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:python_units(path, text)`, `fn:build_inventory(repo, args)`
- Produces: `fn:call_chain(repo, entry, max_depth)`, `fn:choose_depth(units, mode, depth, profile)`

- [ ] **Step 1: Tests schreiben** — `test_inventory_path_chain` (Kette ab
      `datei:funktion` transitiv bis `CHAIN_MAX_DEPTH`, Pfad-Einheit nennt jedes Glied);
      `test_depth_and_profiles` (quick zählt keine Aufrufer; Risikomerkmal → standard;
      `path` und `repo` → standard; `deep` nur mit `--depth deep`; `--depth` überschreibt;
      `--profile checkpoint` setzt Korrektheit und Vertrag und die Grenze 15; `quality`
      unabhängig von der Tiefe; `inventory.json` trägt `depth` und `profile`).
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k "path_chain or depth_and_profiles"`.
- [ ] **Step 3: Implementieren** — Kette über aufgelöste Namen im selben Repo
      (Modulimporte und lokale Aufrufe), Zyklen einmal; Tiefenregel aus der Tabelle der
      Spec; `--ablate callers|path-packet` nur für die Messung im Report, im
      `_meta` vermerkt.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 4: TS/JS-Inventar und Chunks

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:build_inventory(repo, args)`
- Produces: `fn:ts_units(path, text)`, `fn:chunk_units(path, text, reason)`

- [ ] **Step 1: Test schreiben** — `test_inventory_ts`: Funktionsdeklaration,
      Pfeilfunktion an `const`, Klassenmethode; Änderung im Rumpf erkannt; eine
      `.go`-Datei wird zu Blöcken von höchstens `CHUNK_LINES` mit `unit_kind: "chunk"` und
      Grund.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k inventory_ts`.
- [ ] **Step 3: Implementieren** — Textmuster mit Klammerzählung, die Strings, Template-
      Literale und Kommentare überspringt; alles ohne Scanner geht an `chunk_units`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 5: Delphi-Scanner

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:chunk_units(path, text, reason)`
- Produces: `fn:delphi_units(path, text)`

- [ ] **Step 1: Test schreiben** — `test_inventory_delphi_and_chunks` mit allen Fällen der
      Spec: lokale Prozedur endet am eigenen `end;` und gehört zur umgebenden Methode;
      `case`, `try`, `record`, `asm` gezählt; varianter `record … case X of … end` schließt
      mit einem `end`; `forward;`/`external` ohne Rumpf keine Einheit; `end` in String und
      `{…}`, `(*…*)`, `//` ignoriert; `interface`-Teil keine Einheit; unvollständiger
      `{$IFDEF}` → `chunk` mit Grund.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k delphi`.
- [ ] **Step 3: Implementieren** — Tokenizer ohne Strings und Kommentare, Methodenköpfe
      nur nach `implementation`, Blockzähler; `{$IFDEF}` ohne passendes `{$ENDIF}` oder
      `{$I …}` im Rumpf → ganze Datei an `chunk_units`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 6: Pakete, Nonce und Soll

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:build_inventory(repo, args)`, `fn:call_chain(repo, entry, max_depth)`
- Produces: `fn:build_packets(run_dir, repo)`, `fn:load_soll(repo, range_raw, soll_file)`, `fn:packet_hash(code, signatures, soll)`, `fn:reuse_key(code, signatures)`

- [ ] **Step 1: Test schreiben** — `test_packets_and_nonce`: Einheiten-Paket über
      `PACKET_MAX_CHARS` wird geteilt; Pfad-Paket bis `PATH_PACKET_MAX_CHARS`; Paket-Hash
      ändert sich mit Signatur eines Aufgerufenen und mit dem Soll, `reuse_key` nur mit
      der Signatur; `review-context.json` mit fremdem `range.raw` wird nicht gelesen;
      fehlendes `collect_context.py` → „Soll ungeprüft"; Code im Paket als abgegrenzter
      Datenblock mit Kopfzeile.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k packets_and_nonce`.
- [ ] **Step 3: Implementieren** — `packets <lauf>`; Nonce per `secrets.token_hex`;
      Soll im Modus `diff` per Subprozess `collect_context.py --range <bereich>` (mit
      `--soll-file` zusätzlich `--pr-description-file`), Pfad relativ zu
      `Path(__file__)`; Pfad-Paket mit Signatur und wertweiterreichenden Zeilen je Glied.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 7: record

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:build_packets(run_dir, repo)`, `fn:dump_line(obj)`
- Produces: `fn:record_result(run_dir, payload)`

- [ ] **Step 1: Test schreiben** — `test_record_rejects_wrong_nonce`: falsche Nonce,
      alter Paket-Hash oder unbekannte Linse → Exit ≠ 0, nichts in `results.jsonl`;
      passendes Urteil → eine Zeile mit Verdachtsliste (Zeile, Auslösebedingung, Klasse).
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k record_rejects`.
- [ ] **Step 3: Implementieren** — `record <lauf> --packet <id> --lens <linse>` liest
      die Antwort des Suchagenten als JSON von stdin oder `--file`; Quelle `tool` für
      Meldungen aus Schritt 3 der SKILL.md ohne Nonce, aber mit Werkzeugname.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 8: merge und verdict

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:record_result(run_dir, payload)`, `fn:dump_line(obj)`
- Produces: `fn:merge_candidates(run_dir)`, `fn:record_verdict(run_dir, payload)`, `CLASSES`, `STATUSES`

- [ ] **Step 1: Tests schreiben** — `test_merge_without_voting` (gleiche Datei,
      überlappende Zeilen, gleiche Klasse → ein Kandidat mit allen Quellen; andere Klasse
      → zwei; kein Kandidat fällt weg); `test_verdict_statuses_and_checkpoint_limit` (nur
      `bestätigt`, `plausibel`, `widerlegt`, `offen`; `widerlegt` ohne Grund abgewiesen;
      im Profil `checkpoint` wird ein 16. Urteil außer `offen` abgewiesen; Zeile trifft das
      Muster aus Eval 3).
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k "merge_without or verdict_statuses"`.
- [ ] **Step 3: Implementieren** — geschlossene Klassenliste `CLASSES` (darunter
      Datenverlust und Nebenläufigkeit, die die Opus-Stufe auslösen), `STATUSES`;
      `verdict <lauf> --candidate <id>` schreibt in der Schlüsselfolge aus E6.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 9: audit

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:merge_candidates(run_dir)`, `fn:record_verdict(run_dir, payload)`
- Produces: `fn:audit_run(run_dir)`

- [ ] **Step 1: Test schreiben** — `test_audit`: fehlendes Urteil (`missing` mit Einheit
      und Linse), Nonce-Abweichung (`nonce_mismatch`), Kandidat ohne Status
      (`unverdicted`), Bericht „vollständig" trotz Lücke oder Zahl im Bericht, die nicht zu
      den Dateien passt (`report_mismatch`) → je ein Eintrag und `complete: false`;
      sauberer Lauf → `complete: true`, alle Listen leer.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k test_audit`.
- [ ] **Step 3: Implementieren** — `audit <lauf>` schreibt `audit.json` mit `_meta`,
      `complete`, `missing`, `nonce_mismatch`, `unverdicted`, `report_mismatch`; Zahlen
      im Bericht aus festen Zeilen der Vorlage (Abdeckung `<angenommen>/<zugewiesen>`, Funde
      je Status). Exit 1 bei `complete: false`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 10: estimate

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:merge_candidates(run_dir)`
- Produces: `fn:jackknife(found_per_run)`, `fn:write_estimate(run_dir)`

- [ ] **Step 1: Test schreiben** — `test_estimate`: Jackknife erster Ordnung an bekannten
      Zahlen; unter `JACKKNIFE_MIN_RUNS` steht `ungeprüft`; `estimate.json` nennt Zahl der
      Läufe und das Wort „unkalibriert".
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k test_estimate`.
- [ ] **Step 3: Implementieren** — Zählung nur über `bestätigt` und `plausibel` je
      Sättigungslauf.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 11: Folgeläufe mit --since

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:reuse_key(code, signatures)`, `fn:build_inventory(repo, args)`, `fn:record_verdict(run_dir, payload)`
- Produces: `fn:reuse_from(repo, run_dirs, inventory)`

- [ ] **Step 1: Test schreiben** — `test_since_reuses_unchanged_verdicts`: gleicher
      Schlüssel → Urteile und Kandidaten übernommen, auch bei anderem Soll; geänderte
      Signatur eines Aufgerufenen → neu geprüft samt direkten Aufrufern; neue Linse → auf
      allen Einheiten; zwei Läufe mit disjunkten Bereichen → Urteile aus beiden, bei
      derselben Einheit der jüngere; übernommener `offen`-Kandidat in Tiefe `standard`
      erneut zur Verifikation, im Profil `checkpoint` unverändert.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k since_reuses`.
- [ ] **Step 3: Implementieren** — `inventory --since <lauf>[,<lauf>…]`; übernommene
      Urteile und Kandidaten stehen im neuen Lauf mit Quelle `since:<lauf>`, damit `audit`
      sie zählt.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 12: comments

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:build_inventory(repo, args)`
- Produces: `fn:scan_comments(repo, files, diff_only)`

- [ ] **Step 1: Test schreiben** — `test_comment_rules`: `change-narration`,
      `ticket-ref`, `docstring-oversize`, `commented-out-code` (Python per `ast`, andere
      Sprachen `;`/`)` plus Bezeichner des Moduls), `comment-ratio` treffen je ihr
      Beispiel und nicht einen Warum-Kommentar; jeder neue Kommentar steht mit seiner
      Folgezeile als Kandidat `restates-code` für das Modell; im Modus `diff` nur neue und
      geänderte. Beispiele nicht aus `dr-comments` übernehmen.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k comment_rules`.
- [ ] **Step 3: Implementieren** — `comments <lauf>` schreibt `comments.json` mit `_meta`
      und je Fund `rule`, `path`, `line`, `text`.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 13: metrics

**Files:**
- Modify: `skills/deep-review/scripts/review_kit.py`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:python_units(path, text)`
- Produces: `fn:function_metrics(path, text)`, `fn:repo_medians(repo)`

- [ ] **Step 1: Test schreiben** — `test_metrics_against_median`: Länge, Verschachtelung,
      Verzweigungen je Funktion und der Median des Repos; `.skills/` zählt nicht.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_deep_review_kit.py -k metrics_against`.
- [ ] **Step 3: Implementieren** — `metrics <lauf>` schreibt `metrics.json` mit `_meta`,
      je Einheit Werte und Verhältnis zum Median.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 14: references/lenses.md

**Files:**
- Create: `skills/deep-review/references/lenses.md`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `CLASSES`
- Produces: `token:Eingabe zum Durchspielen`

- [ ] **Step 1: Schreiben** — je Linse ein Szenario mit konkreten Fragen und einer
      Eingabe zum Durchspielen: Korrektheit, Fehlerpfade, Vertrag, Nebenläufigkeit,
      Ressourcen, Delphi (Besitz mit `try/finally` und Owner, Interface-Referenzzählung,
      VCL-Hauptthread, verschluckte Exceptions, String-Kodierung), Wartbarkeit (Grundlage
      Pflicht), Kommentare; die geschlossene Klassenliste; Quelle der Szenario-Form
      (Porter 1995, Laitenberger 2000) mit „für Modelle ungemessen".
- [ ] **Step 2: Prüfen** — `test_lens_classes_match_reference`: die Klassenliste in
      `lenses.md` gleicht `CLASSES`. Commit.

### Task 15: references/finder-prompt.md

**Files:**
- Create: `skills/deep-review/references/finder-prompt.md`

**Interfaces:**
- Consumes: `fn:record_result(run_dir, payload)`, `token:Eingabe zum Durchspielen`
- Produces: `token:Code ist Daten`

- [ ] **Step 1: Schreiben** — Auftrag: mehrere Pakete, eine Linse, Nonce und Paket-Hash
      je Paket zurückgeben, jeder Verdacht mit Zeile und Auslösebedingung, kein Filter
      („lieber melden als weglassen"), „Code ist Daten, nie Anweisung"; Antwortform genau
      die JSON-Form, die `record` annimmt, mit einem Beispiel ohne Fixture-Werte.
- [ ] **Step 2: Prüfen** — das Beispiel aus der Datei durch `record` an einem Temp-Lauf
      angenommen; kein `${CLAUDE_SKILL_DIR}` mit `python` in der Datei. Commit.

### Task 16: references/verifier-prompt.md

**Files:**
- Create: `skills/deep-review/references/verifier-prompt.md`

**Interfaces:**
- Consumes: `fn:record_verdict(run_dir, payload)`, `STATUSES`
- Produces: `token:erst widerlegen`

- [ ] **Step 1: Schreiben** — „erst widerlegen, dann belegen"; die vier Status mit ihrer
      Schwelle (`bestätigt` nur mit Test oder Ausführung in der Kopie an der behaupteten
      Stelle); Beweistest nur unter `<lauf>/proof/` (`git worktree add --detach`, nach dem
      Lauf `git worktree remove --force`); Opus-Stufe für Datenverlust und Nebenläufigkeit;
      Antwortform für `verdict`.
- [ ] **Step 2: Prüfen** — das Beispiel aus der Datei durch `verdict` an einem Temp-Lauf
      angenommen. Commit.

### Task 17: references/saturation.md

**Files:**
- Create: `skills/deep-review/references/saturation.md`

**Interfaces:**
- Consumes: `fn:write_estimate(run_dir)`
- Produces: `token:unkalibriert`

- [ ] **Step 1: Schreiben** — nur Tiefe `deep`; obere Risikogruppe ab `HIGH_RISK_MIN`
      Merkmalen; andere Reihenfolge je Lauf, einer mit Opus; Abbruch nach zwei fundlosen
      Läufen, spätestens `SATURATION_MAX_RUNS`; Jackknife ab `JACKKNIFE_MIN_RUNS` als
      unkalibrierte Untergrenze und warum (korrelierte Läufe, Fehlalarme).
- [ ] **Step 2: Prüfen** — jede Zahl in der Datei gleicht der Konstante in
      `review_kit.py` (grep). Commit.

### Task 18: assets/report-template.md

**Files:**
- Create: `skills/deep-review/assets/report-template.md`

**Interfaces:**
- Consumes: `fn:audit_run(run_dir)`
- Produces: `token:Nicht geprüft`, `token:Suche ohne frischen Kontext`

- [ ] **Step 1: Schreiben** — Kopfzeile in Zeile 1; feste Zeilen für Lauf-ID, Abdeckung
      `<angenommen>/<zugewiesen>` und Funde je Status, die `audit` liest; Abschnitte Funde,
      Wartbarkeit (nur mit `quality`), „Nicht geprüft", Anhang `widerlegt` mit Grund,
      Vorbehalt zur Nonce; Variante `quick` passt in `REPORT_QUICK_MAX_LINES`.
- [ ] **Step 2: Prüfen** — eine aus der Vorlage gefüllte Datei besteht `audit` an einem
      sauberen Temp-Lauf; Regel `asset-headers` sauber. Commit.

### Task 19: Evals

**Files:**
- Create: `evals/deep-review/evals.json`
- Create: `evals/fixtures/dr-small/fixture.json`
- Create: `evals/fixtures/dr-small/README.md`
- Create: `evals/fixtures/dr-cross-file/fixture.json`
- Create: `evals/fixtures/dr-cross-file/README.md`
- Create: `evals/fixtures/dr-comments/fixture.json`
- Create: `evals/fixtures/dr-comments/README.md`
- Modify: `tests/test_deep_review_kit.py`

**Interfaces:**
- Consumes: `fn:record_verdict(run_dir, payload)`, `fn:scan_comments(repo, files, diff_only)`, `token:Nicht geprüft`
- Produces: `token:anti-ceremony-one-line-fix-stays-quick`

- [ ] **Step 1: Fixtures** — je `"git": true` mit einem Commit für den Diff; `dr-small`
      ein Einzeiler ohne Risikomerkmal; `dr-cross-file` mit `app/cli.py:main`,
      `app/orders.py:parse_order` (gibt bei leerer Zeile `None`), `app/report.py:summarize`
      (greift ungeprüft auf `.total` zu), pytest und einem grünen Test ohne den leeren
      Fall; `dr-comments` fügt `# jetzt mit Cache` und `# old_total = sum(values)` in
      `app/stats.py` hinzu.
- [ ] **Step 2: Evals** — `anti-ceremony-one-line-fix-stays-quick`,
      `every-unit-gets-a-verdict`, `cross-file-none-bug-is-found`,
      `comment-ballast-is-flagged`, `routing-thorough-check-without-skill-name` mit
      Assertions, Globs und Prompts der Spec (`|` statt `\|`), Diskriminator-Frage in
      `notes`; Eval 5 als stochastisch markiert.
- [ ] **Step 3: Test** — `test_evals_and_fixtures`: `evalkit.schema.load_evals` lädt
      fünf Evals; der grüne Test in `dr-cross-file` läuft grün; das Muster aus Eval 3
      trifft eine Zeile aus `record_verdict` mit `plausibel` und nicht eine mit
      `widerlegt`; das Muster aus Eval 1 trifft ein echtes `inventory.json` von `dr-small`.
      Commit.

### Task 20: Nachbarn

Plugin-Zuordnung und Projekt-Kopie von deep-review stehen im Task SKILL.md, weil
`test_every_skill_in_exactly_one_plugin` und `test_project_copies_match_originals` eine
vorhandene `SKILL.md` verlangen. Ein **deep-review** in einer Abgrenzung vor dieser Datei
ergibt bei den Nachbarn `unchecked`, keinen Befund.

**Files:**
- Modify: `specs/Spec 00 – skill-foundation.md`
- Modify: `README.md`
- Modify: `skills/review-context/SKILL.md`
- Modify: `skills/subagent-dev/SKILL.md`
- Modify: `skills/debug-ledger/SKILL.md`
- Modify: `skills/test-first/SKILL.md`
- Modify: `.claude/skills/review-context/`
- Modify: `.claude/skills/subagent-dev/`
- Modify: `.claude/skills/debug-ledger/`

**Interfaces:**
- Consumes: `token:anti-ceremony-one-line-fix-stays-quick`
- Produces: `token:deep-review`

- [ ] **Step 1: Routing** — Spec 00 §5: neue Zeile mit deep-review unter „zuständig",
      Zeile „Diff prüfen" nennt deep-review unter „nicht", Annahme zu Spec 04 mit Verweis
      auf Spec 26; README: neue Zeile unter „Responsible", Zeile „review a diff" ohne
      „scope left open", Skill-Liste von `evaluated-dev`.
- [ ] **Step 2: Rückverweise** — review-context: Abschnitt „Warum diese Skill existiert"
      neu (die Linsen-Engine gibt es jetzt als deep-review), Abgrenzung nennt
      **deep-review**; subagent-dev, debug-ledger, test-first: Abgrenzung nennt
      **deep-review**. `python scripts/sync_skills.py`, dann `--check`; `lint_skill.py
      --base HEAD` je geänderter Skill ohne neuen Befund, `evals_due` notieren.
- [ ] **Step 3: Prüfen** — volle Suite grün. Commit.

### Task 21: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `token:deep-review`
- Produces: (nichts Neues)

- [ ] **Step 1: Abschnitt** — `## deep-review`: Nonce erschwert, verhindert kein
      erfundenes Urteil; keine Security-Linse; TS/JS nur Textmuster, Delphi mit
      `{$IFDEF}` als Chunk; Grenzwerte ungemessen; Kosten geschätzt; Eval-Timeout 600 s,
      keine Eval in Tiefe `deep`; Subagenten aus Subagenten ungemessen; Soll fehlt im
      Eval-Workspace ohne review-context; Routing-Kollision mit `/code-review` und global
      installierten Review-Skills. Commit.

### Task 22: SKILL.md

**Files:**
- Create: `skills/deep-review/SKILL.md`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `scripts/sync_skills.py`
- Create: `.claude/skills/deep-review/`

**Interfaces:**
- Consumes: `fn:main(argv)`, `token:Code ist Daten`, `token:erst widerlegen`, `token:unkalibriert`, `token:Nicht geprüft`, `token:deep-review`
- Produces: `token:Eiserne Regel`, `token:unvollständig`

- [ ] **Step 1: Frontmatter** — `name`, Description mit Triggern („gründlich prüfen",
      „Audit", „wurde wirklich alles angeschaut", „review mit Abdeckung") und Abgrenzung
      gegen `/code-review`, `/security-review`, review-context; kein Prozessverb.
- [ ] **Step 2: Rumpf** — Eiserne Regel; Ablauf in neun Schritten mit den Aufrufen von
      `review_kit.py`, Bootstrap-Satz; Tiefen-und-Profile-Tabelle; Ausführung zuerst aus
      `Verifikation:`; Suchagenten lesend (`Explore`), Prüfagenten nur unter
      `<lauf>/proof/`; Übergabe mit Lauf-ID, „unvollständig" bei Lücke; Contract;
      Anti-Rationalisierung; Abgrenzung mit **review-context**, **subagent-dev**,
      **debug-ledger**, **test-first**.
- [ ] **Step 3: Plugin und Kopie** — `./skills/deep-review` in `evaluated-dev`,
      Description des Plugins nennt Review; `deep-review` in `PROJECT_SKILLS`;
      `python scripts/sync_skills.py`, dann `--check`.
- [ ] **Step 4: Prüfen** — `wc -l` unter 150; `lint_skill.py skills/deep-review` ohne
      Befund (Register bleibt bei 79); volle Suite grün. Commit.

### Task 23: Report

**Files:**
- Modify: `docs/superpowers/reports/deep-review-report.md`

**Interfaces:**
- Consumes: `token:Eiserne Regel`, `token:dr-seeded`, `token:Was nicht gemessen wurde`
- Produces: (nichts Neues)

- [ ] **Step 1: Messung** — deep-review in Tiefe `standard` je drei Läufe auf
      `dr-seeded` und `dr-seeded-clean`; Abnahme gegen die Basislinie aus Task 1
      (mindestens so viele der fünf wie `/code-review` und Sonnet zusammen, höchstens zwei
      `plausibel` auf der sauberen Fassung); Abschaltungen über `--ablate callers`,
      `--ablate path-packet` und ohne Verifikation; `total_cost_usd` je Lauf.
- [ ] **Step 2: Evals** — alle fünf mit Skill und einmal ohne (Spec 18); die Evals von
      review-context, subagent-dev, debug-ledger und test-first, wo `evals_due` aus Task 20
      `true` war.
- [ ] **Step 3: Report** — Messmenge, Grenzwerte aus E8, Ergebnis je Stufe, welche Stufe
      vor dem nächsten Zyklus rausfliegt, „## Was nicht gemessen wurde" aktualisiert.
      `lint_skill.py skills/deep-review` sauber. Commit.
