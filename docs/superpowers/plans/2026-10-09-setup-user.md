<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# setup-user Implementation Plan (Abschnitt A)

**Goal:** Ein Config-Verzeichnis von Claude Code lässt sich mit einem gezeigten, gehashten
Plan einrichten und prüfen, und Claude bekommt beim Überschreiten einer Kontext- oder
Limitschwelle einen Hinweis, ohne dass je ein Prompt angehalten wird.

**Architecture:** Tier 1, nur Stdlib, kein Bash-Skript. Fünf Skripte, keines importiert
ein anderes: zwei Laufzeitskripte, die ins Config-Verzeichnis kopiert werden
(`assets/runtime/statusline.py` schreibt Limit-Cache und Kontextzustand,
`assets/runtime/context_hint.py` liest beides und meldet), und drei Werkzeuge
(`scripts/inspect_config.py` schreibt `plan.md` mit kanonischem JSON-Block und Hash,
`scripts/apply_config.py` prüft den Hash und mischt, `scripts/verify_install.py` führt die
Asset-Befehle in einer Sandbox aus). Dazu `lint_skill.py` mit der Liste `CLAUDE_CODE_ONLY`,
drei References, Assets, vier Evals. Abschnitt B (Routing, `route_check.py`, Eval 5) ist
nicht Teil dieses Plans.

**Tech Stack:** Python 3.13 Stdlib für Skripte und Tests; Markdown für Skill,
References, Evals; `bash -c` nur als Ausführer in der Sandbox-Prüfung.

**Spec:** `specs/Spec 21 – setup-user.md`

## Global Constraints

- **E1 — Tier 1, nur Stdlib** (Spec 00 §3). Kein Skript importiert ein anderes; den
  Plan-Hash berechnen `inspect_config.py` und `apply_config.py` je selbst, ein Test hält
  beide gleich. Fehlt `bash`, heißt die Prüfung „ungeprüft — keine bash", nie „geprüft".
- **E2 — Gate-Sprache** (Spec 00 §4): G1 „verlangt" (Plan gezeigt), G2 „meldet" (Hash in
  `apply_config.py`). Der Hook hält nie etwas an; das Fragment liegt unter
  `assets/settings/`, nicht unter `assets/hooks/`.
- **E3 — Kopfzeile je Artefakt** (`docs/artifact-header.md`): `plan.md`, `check.md`,
  `CLAUDE.md.tmpl` und die vier Regeln in Zeile 1; `thresholds.json`, `state/*.json`,
  `known-statusline-hashes.json` und der Limit-Cache per `_meta`.
- **E4 — SKILL.md ≤ 150 Zeilen**, Frontmatter `name`, `description` und
  `disable-model-invocation: true`, das der Lint nur für `CLAUDE_CODE_ONLY` erlaubt.
- **E5 — Anti-Zeremonie-Eval ist Pflicht** (Spec 00 §2):
  `anti-ceremony-check-on-aligned-config-changes-nothing`, gebunden an `check.md`.
- **E6 — Laufzeitskripte enden immer mit 0.** Jede Ausnahme wird gefangen, kein
  `argparse` in `context_hint.py`, stdin als Bytes mit UTF-8-Ersetzung.
- **E7 — Nie ins echte Home.** Tests und Sandbox setzen `CLAUDE_CONFIG_DIR`, `HOME` und
  `USERPROFILE` auf ein Temp-Verzeichnis; kein Test liest oder schreibt `~/.claude`.

## Skill-Struktur

```
skills/setup-user/
├── SKILL.md
├── references/settings-merge.md, plan-format.md, thresholds.md
├── assets/CLAUDE.md.tmpl, assets/rules/{communication,verification,context,git}.md
├── assets/runtime/statusline.py, context_hint.py, known-statusline-hashes.json
├── assets/settings/context-hint.json
└── scripts/inspect_config.py, apply_config.py, verify_install.py

skills/skill-forge/scripts/lint_skill.py, tests/test_skill_forge_lint.py
evals/setup-user/evals.json
evals/fixtures/su-aligned/, su-fresh/, su-planned/, su-own-statusline/
tests/test_setup_user_statusline.py, _hint.py, _apply.py, _verify.py, _fixtures.py
tests/fixtures/setup-user/
```

### Task 1: Statusline-Vorlagen des Nutzers

Die Spec baut Asset und zwei Tests auf der Statusline des Nutzers in der Fassung vom
2026-10-07 und ihrer korrigierten Fassung aus dem Review. Keine von beiden liegt im Repo.
Diese Task braucht den Nutzer und läuft im Hauptkontext.

**Files:**
- Create: `tests/fixtures/setup-user/statusline-original.py`
- Create: `tests/fixtures/setup-user/statusline-corrected.py`
- Create: `tests/fixtures/setup-user/README.md`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `token:statusline-original.py`

- [ ] **Step 1: Dateien vom Nutzer** — die Statusline, die heute in seiner
      `settings.json` steht, und, falls vorhanden, die korrigierte Fassung aus dem
      Review; fehlt die korrigierte, entsteht sie in Task 5 aus dem Original.
- [ ] **Step 2: Ablegen** — unverändert unter `tests/fixtures/setup-user/`; `README.md`
      mit Kopfzeile nennt Herkunft, Datum und den SHA-256 beider Dateien mit
      LF-normalisierten Zeilenenden.
- [ ] **Step 3: Prüfen** — beide Dateien laufen mit einer vollen Beispiel-Eingabe aus der
      statusline-Doku und geben eine Zeile aus; ein Lauf schreibt nur in ein
      Temp-`HOME`. Commit.

### Task 2: CLAUDE_CODE_ONLY im Lint

**Files:**
- Modify: `skills/skill-forge/scripts/lint_skill.py`
- Modify: `.claude/skills/skill-forge/`
- Test: `tests/test_skill_forge_lint.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `token:CLAUDE_CODE_ONLY`

- [x] **Step 1: Test schreiben** — `test_disable_model_invocation_only_for_claude_code_only`:
      `make_repo` mit `name: setup-user` und `disable-model-invocation: true` →
      `frontmatter` `pass`; dieselbe Zeile in `note-tag` → `finding` mit dem Schlüssel im
      Grund.
- [x] **Step 2: Rot sehen** — `pytest tests/test_skill_forge_lint.py -k claude_code_only`.
- [x] **Step 3: Implementieren** — `CLAUDE_CODE_ONLY = frozenset({"setup-user", "setup-repo"})`;
      `rule_frontmatter` erlaubt `disable-model-invocation` nur, wenn der Ordnername in
      der Liste steht.
- [x] **Step 4: Grün sehen**, volle Suite; `python scripts/sync_skills.py` und `--check`.
- [x] **Step 5: Commit.**

### Task 3: References

**Files:**
- Create: `skills/setup-user/references/plan-format.md`
- Create: `skills/setup-user/references/settings-merge.md`
- Create: `skills/setup-user/references/thresholds.md`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `token:setup-user-plan`, `token:hookEventName`, `token:limit-hints.json`

- [x] **Step 1: plan-format.md** — Aufbau von `plan.md` (Kopfzeile, Ansicht, Codeblock mit
      Info-String `json setup-user-plan`); Felder des Blocks: `schema`, `python`,
      `answers`, `operations` (je `path` relativ zu `<config-dir>`, `action` aus
      `create`, `merge`, `copy`, `content` oder `patch`), `base` (je Pfad SHA-256 des
      LF-normalisierten Bestands mit `<config-dir>` statt absolutem Pfad, `null` wenn
      fehlend), `hash`; Hash = SHA-256 über `json.dumps(block ohne hash, sort_keys=True,
      ensure_ascii=False, separators=(",", ":"))`.
- [x] **Step 2: settings-merge.md** — welche Schlüssel `apply` mischt (`statusLine.command`,
      `hooks.UserPromptSubmit`, auf Bestätigung `permissions.deny`), welche es nie
      anfasst (alle anderen, in Abschnitt A auch `enabledPlugins`); Identität eigener
      Einträge über die Suffixe `setup-user/runtime/context_hint.py` und
      `setup-user/runtime/statusline.py`; Schreibformat (Einrückung 2, ohne
      ASCII-Escapes, Schlüsselreihenfolge des Bestands, LF, Zeilenumbruch am Ende);
      Backup-Namen `JJJJMMTT-hhmmss` mit `-2` bei Kollision; Reihenfolge `runtime/`,
      `thresholds.json`, CLAUDE.md und Regeln, zuletzt `settings.json`.
- [x] **Step 3: thresholds.md** — Schwellen 60 und 80 % Kontext, 80 % fünf Stunden, 85 %
      sieben Tage; Gültigkeit (Kontext je `session_id`, Limit solange `resets_at_epoch`
      in der Zukunft); Merker in `state/hints-<session_id>.json` und
      `state/limit-hints.json` mit Schlüssel aus Fenster, Schwelle und
      `resets_at_epoch`; höchstens ein Hinweistext je Prompt, je Art die höchste neu
      überschrittene Schwelle; Ausgabeform mit `hookEventName` `UserPromptSubmit` und
      `additionalContext`; Wortlaut als Feststellung mit `[setup-user]` am Anfang;
      Aufräumen nach 24 Stunden Änderungszeit.
- [x] **Step 4: Prüfen** — References tragen wie im ganzen Repo keine Kopfzeile, sie
      sind Doktrin, kein erzeugtes Artefakt; jede Datei unter 200 Zeilen, die drei
      Tokens wörtlich vorhanden. Commit.

### Task 4: context_hint.py

**Files:**
- Create: `skills/setup-user/assets/runtime/context_hint.py`
- Test: `tests/test_setup_user_hint.py`

**Interfaces:**
- Consumes: `token:limit-hints.json`, `token:hookEventName`
- Produces: `fn:hint_for(payload, config_dir, now)`, `fn:main()`

- [x] **Step 1: Tests schreiben** — Zustand und Cache werden im Test von Hand in ein
      Temp-Config-Verzeichnis geschrieben: `test_hint_once_and_rearms` (zweiter Prompt
      über derselben Schwelle schweigt, nach Absinken und erneutem Überschreiten wieder
      ein Hinweis, neues Limitfenster wieder scharf), `test_hint_one_text_per_prompt_highest_threshold`
      (50 → 85 % ergibt einen Hinweis mit 80, 60 gilt als gemeldet),
      `test_hint_silent_on_foreign_session_null_or_expired_limits`,
      `test_hint_limits_without_statusline_state`, `test_hint_exit_zero_on_any_error`
      (kaputtes JSON, unlesbarer Zustand, erzwungene Ausnahme → Exit 0, leeres stdout),
      `test_hint_output_shape` (stdout genau ein JSON-Objekt mit `hookEventName` und
      `additionalContext`, Text beginnt mit `[setup-user]`); Aufruf als Unterprozess mit
      `CLAUDE_CONFIG_DIR` auf `tmp_path`.
- [x] **Step 2: Rot sehen** — `pytest tests/test_setup_user_hint.py`.
- [x] **Step 3: Implementieren** — `hint_for` ist rein bis auf das Lesen und Schreiben
      der Merker; `main` liest `sys.stdin.buffer`, dekodiert UTF-8 mit Ersetzung, ruft
      `hint_for` in `try/except BaseException`, gibt bei Text genau ein JSON-Objekt aus
      und endet immer mit 0; Config-Verzeichnis aus `CLAUDE_CONFIG_DIR`, sonst drei
      Ebenen über der Datei, sonst `~/.claude`; Merker atomar über Temp-Datei und
      `os.replace` mit drei Versuchen.
- [x] **Step 4: Grün sehen**, volle Suite.
- [x] **Step 5: Commit.**

### Task 5: Statusline-Asset

**Files:**
- Create: `skills/setup-user/assets/runtime/statusline.py`
- Modify: `skills/setup-user/assets/runtime/known-statusline-hashes.json`
- Test: `tests/test_setup_user_statusline.py`

**Interfaces:**
- Consumes: `token:statusline-original.py`, `token:limit-hints.json`
- Produces: `token:setup-user: statusline`

- [ ] **Step 1: Tests schreiben** — `test_statusline_keeps_cache_on_session_start`,
      `test_statusline_keeps_window_on_explicit_null`, `test_statusline_respects_config_dir`,
      `test_statusline_partial_window_keeps_other_window`,
      `test_statusline_survives_null_empty_and_non_ascii_input`,
      `test_statusline_display_unchanged` (Ausgabe gleich der von
      `tests/fixtures/setup-user/statusline-original.py` bei voller Eingabe),
      `test_statusline_state_prunes_and_sanitizes`; alle als Unterprozess mit
      `CLAUDE_CONFIG_DIR` und `HOME` auf `tmp_path`.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_setup_user_statusline.py`.
- [ ] **Step 3: Implementieren** — Ausgangspunkt ist die korrigierte Fassung aus Task 1;
      dazu Kennzeile `# setup-user: statusline` in Zeile 2, Zeile zuerst ausgeben, dann
      schreiben; Limit-Cache je Fenster nur bei gültigem Wert überschreiben, bisherige
      Schlüssel des Caches behalten und `_meta` ergänzen; `state/context-<session_id>.json`
      mit `used_percentage` oder `null`; `session_id` auf `[A-Za-z0-9_-]` prüfen;
      Aufräumen nach 24 Stunden Änderungszeit und alter `*.tmp`; immer Exit 0.
      `known-statusline-hashes.json` bekommt die LF-normalisierten Hashes von Original
      und korrigierter Fassung.
- [ ] **Step 4: Grün sehen**, volle Suite.
- [ ] **Step 5: Commit.**

### Task 6: inspect_config.py

**Files:**
- Create: `skills/setup-user/scripts/inspect_config.py`
- Test: `tests/test_setup_user_apply.py`

**Interfaces:**
- Consumes: `token:setup-user-plan`
- Produces: `fn:build_plan(config_dir, answers, python)`, `fn:plan_hash(block)`, `fn:render_plan(block, config_dir)`

- [x] **Step 1: Tests schreiben** — `test_plan_is_path_and_eol_neutral` (dasselbe
      Verzeichnis an zwei Orten, einmal mit CRLF-Bestand → gleicher Hash; andere
      Kopfzeile → gleicher Hash), `test_plan_classifies_statusline` (Kennzeile oder
      bekannter Hash → umstellen, keine → Asset, fremde → bleibt mit Satz
      „Kontext-Hinweise nicht verfügbar"), `test_plan_writes_only_plan_md`
      (Snapshot des Config-Verzeichnisses vorher und nachher; nur `setup-user/plan.md`
      ist neu), `test_plan_resolves_python` (aus vorhandenem `statusLine`-Kommando, sonst
      `--python`, sonst `python3`; steht im Block).
- [x] **Step 2: Rot sehen** — `pytest tests/test_setup_user_apply.py -k plan`.
- [x] **Step 3: Implementieren** — Bestandsaufnahme, Interview-Antworten aus
      `--answers <json>` in CLAUDE.md und Regeln einsetzen, Operationen nach
      `references/settings-merge.md`, Block und Hash nach `references/plan-format.md`,
      Ansicht mit Diff; erste Ausgabezeile nennt das aufgelöste Verzeichnis.
- [x] **Step 4: Grün sehen**, volle Suite.
- [x] **Step 5: Commit.**

### Task 7: apply_config.py

**Files:**
- Create: `skills/setup-user/scripts/apply_config.py`
- Modify: `tests/test_setup_user_apply.py`

**Interfaces:**
- Consumes: `fn:build_plan(config_dir, answers, python)`, `fn:plan_hash(block)`
- Produces: `fn:apply_plan(plan_path, config_dir)`, `fn:canonical_hash(block)`

- [x] **Step 1: Tests schreiben** — `test_hash_functions_agree` (`canonical_hash` gleich
      `plan_hash` für drei Blöcke), `test_apply_is_idempotent`,
      `test_apply_refuses_changed_plan_or_state`,
      `test_apply_requires_explicit_existing_config_dir`,
      `test_apply_writes_settings_last` (Fehler beim Kopieren von `runtime/` →
      `settings.json` unverändert), `test_apply_keeps_foreign_keys_and_statusline_options`
      (fremder Schlüssel, `padding`, `refreshInterval` bleiben; kein zweiter Hook-Eintrag;
      Backup enthält den alten Inhalt).
- [x] **Step 2: Rot sehen** — `pytest tests/test_setup_user_apply.py -k apply`.
- [x] **Step 3: Implementieren** — Block aus `plan.md` lesen, Hash und Basis-Hashes prüfen,
      `<config-dir>` mit Schrägstrichen einsetzen, Backups, Reihenfolge nach
      `references/settings-merge.md`, atomares Schreiben; Abbruch ohne berührte Datei.
- [x] **Step 4: Grün sehen**, volle Suite.
- [x] **Step 5: Commit.**

### Task 8: verify_install.py

**Files:**
- Create: `skills/setup-user/scripts/verify_install.py`
- Test: `tests/test_setup_user_verify.py`

**Interfaces:**
- Consumes: `fn:hint_for(payload, config_dir, now)`, `token:setup-user: statusline`
- Produces: `fn:verify(config_dir)`

- [x] **Step 1: Tests schreiben** — `test_verify_runs_in_sandbox_only` (keine neue oder
      geänderte Datei außerhalb des Temp-Verzeichnisses, auch nicht unter `HOME`),
      `test_verify_skips_foreign_commands` („ungeprüft (fremd, nicht ausgeführt)"),
      `test_verify_flags_silent_hook_nonzero_exit_and_empty_statusline`,
      `test_verify_without_bash_is_unchecked`.
- [x] **Step 2: Rot sehen** — `pytest tests/test_setup_user_verify.py`.
- [x] **Step 3: Implementieren** — Befehle aus `settings.json` lesen, Skriptpfad
      auflösen, nur Dateien mit Asset-Hash ausführen, über `bash -c` mit
      `CLAUDE_CONFIG_DIR`, `HOME`, `USERPROFILE` auf ein Temp-Verzeichnis und 10 Sekunden
      Timeout; Beispielzustand oberhalb einer Schwelle einspielen; Befunde als Liste.
- [x] **Step 4: Grün sehen**, volle Suite.
- [x] **Step 5: Commit.**

### Task 9: Assets

**Files:**
- Create: `skills/setup-user/assets/CLAUDE.md.tmpl`
- Create: `skills/setup-user/assets/rules/communication.md`
- Create: `skills/setup-user/assets/rules/verification.md`
- Create: `skills/setup-user/assets/rules/context.md`
- Create: `skills/setup-user/assets/rules/git.md`
- Create: `skills/setup-user/assets/settings/context-hint.json`
- Create: `skills/setup-user/assets/runtime/known-statusline-hashes.json`

**Interfaces:**
- Consumes: `token:setup-user-plan`
- Produces: `token:UserPromptSubmit`

- [x] **Step 1: Schreiben** — CLAUDE.md-Gerüst ≤ 40 Zeilen, je Regel ≤ 20 Zeilen,
      zusammen ≤ 120, jede mit Kopfzeile in Zeile 1; `verification.md` mit „keine
      Erfolgsmeldung ohne Beleg" und „Review-Befunde vor dem Umsetzen nachmessen";
      `context.md` sagt, was `[setup-user]`-Hinweise bedeuten; das Fragment trägt den
      Hook mit `<python> "<config-dir>/setup-user/runtime/context_hint.py" || true`;
      `known-statusline-hashes.json` mit `_meta` und leerer Liste, Task 5 füllt sie.
- [x] **Step 2: Prüfen** — `wc -l` je Datei; ein Test in `tests/test_setup_user_fixtures.py`
      ist erst Task 11; hier `lint_skill.py skills/setup-user` ohne Befund für
      `asset-headers`. Commit.

### Task 10: SKILL.md

**Files:**
- Create: `skills/setup-user/SKILL.md`

**Interfaces:**
- Consumes: `fn:build_plan(config_dir, answers, python)`, `fn:apply_plan(plan_path, config_dir)`, `fn:verify(config_dir)`, `token:CLAUDE_CODE_ONLY`
- Produces: `token:angewendet und geprüft`

- [ ] **Step 1: Frontmatter** — `name`, Description mit Triggern und Abgrenzung gegen
      `/statusline` und setup-repo, ohne `<…>`, `disable-model-invocation: true`.
- [ ] **Step 2: Rumpf** — Eiserne Regel, Modi plan, apply, check, Interview mit höchstens
      drei Fragen, Übergabesätze „angewendet und geprüft, wirkt ab der nächsten Session"
      und „angewendet, ungeprüft — Grund", Contract, Abgrenzung mit **handoff** fett und
      skill-forge unfett, Skripte über `${CLAUDE_SKILL_DIR}`.
- [ ] **Step 3: Prüfen** — `wc -l` unter 150; `lint_skill.py skills/setup-user` ohne
      Befund außer `report-section`, `routing`, `neighbors` und `plugin-membership`, die
      Task 12 bis 14 schließen. Commit.

### Task 11: Evals

**Files:**
- Create: `evals/setup-user/evals.json`
- Create: `evals/fixtures/su-aligned/`
- Create: `evals/fixtures/su-fresh/`
- Create: `evals/fixtures/su-planned/`
- Create: `evals/fixtures/su-own-statusline/`
- Create: `tests/test_setup_user_fixtures.py`

**Interfaces:**
- Consumes: `token:angewendet und geprüft`, `token:setup-user: statusline`
- Produces: `token:anti-ceremony-check-on-aligned-config-changes-nothing`

- [ ] **Step 1: Fixtures** — je `fixture.json` und `cfg/`; `su-aligned` mit Laufzeitdateien
      gleich den Assets und relativen Skriptpfaden; `su-planned` und `su-own-statusline`
      mit einem `plan.md`, den `inspect_config.py --python python3` erzeugt hat;
      `su-fresh` und `su-planned` mit `"spinnerTipsEnabled": false`.
- [ ] **Step 2: Evals** — `anti-ceremony-check-on-aligned-config-changes-nothing`,
      `plan-is-default-and-writes-only-plan`, `apply-merges-existing-plan-and-backs-up`,
      `foreign-statusline-is-kept-while-hook-is-merged` mit den Assertions der Spec und je
      der Diskriminator-Frage in `notes`; `superpowers-sessionstart-is-reported` kommt mit
      Abschnitt B und steht hier nicht.
- [ ] **Step 3: Schema-Test** — `load_evals` lädt vier Evals; `test_fixture_plans_are_current`
      vergleicht die Blöcke der Fixture-Pläne mit neu erzeugten und die Laufzeitdateien
      in `su-aligned` mit den Assets. Commit.

### Task 12: Nachbarn

**Files:**
- Modify: `skills/handoff/SKILL.md`
- Modify: `.claude/skills/handoff/`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `specs/Spec 00 – skill-foundation.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `token:angewendet und geprüft`
- Produces: `token:[setup-user]`

- [ ] **Step 1: handoff** — Abgrenzung: `[setup-user]`-Hinweise raten zu handoff, mit dem
      Wort setup-user; `python scripts/sync_skills.py` und `--check`; `lint_skill.py
      --base HEAD skills/handoff` ohne neuen Befund.
- [ ] **Step 2: Manifest** — `./skills/setup-user` in die `skills`-Liste von `cc-dev`;
      `pytest tests/test_marketplace.py`.
- [ ] **Step 3: Matrix** — Spec 00 §5: Satz zur Ausnahme für Claude-Code-spezifische
      Skills und Zeile setup-user; README dieselbe Zeile und setup-user in der Liste von
      `cc-dev`. `lint_skill.py skills/setup-user` meldet `routing` und `neighbors` grün.
      Commit.

### Task 13: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `token:anti-ceremony-check-on-aligned-config-changes-nothing`
- Produces: (nichts Neues)

- [ ] **Step 1: Abschnitt** — `## setup-user`: was auf Windows ungemessen ist (`|| true`,
      Interpreter, Vererbung von `CLAUDE_CONFIG_DIR`, `os.replace` bei offenem Leser),
      dass die Statusline bei `claude -p` nicht läuft, dass Hinweise nur entstehen und
      schweigen, ihre Wirkung aber ungemessen ist, dass Abschnitt B fehlt. Commit.

### Task 14: Report

**Files:**
- Create: `docs/superpowers/reports/setup-user-report.md`

**Interfaces:**
- Consumes: `token:anti-ceremony-check-on-aligned-config-changes-nothing`
- Produces: (nichts Neues)

- [ ] **Step 1: Report** — was entstanden ist, Testzahl, Eval-Läufe außerhalb des Harness
      oder „ungefahren" mit Grund, und die Sektion „Was nicht gemessen wurde": erster
      echter Lauf auf dem Windows-PC und der Devbox, Baseline ohne Skill, Abschnitt B.
      `lint_skill.py skills/setup-user` ganz sauber. Commit.
