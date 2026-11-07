<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# decide Zyklus 2 Implementation Plan

**Goal:** decide deckt das Häufige genau ab und gibt das Seltene sichtbar an den Nutzer weiter:
`check` nimmt eine Revision und erledigt die Übergabe in einem Aufruf, `brief` als Skript
entfällt, und ein optionaler Hook `guard` legt Push, Löschen, Verwerfen und externe Wirkungen
dem Nutzer vor, bevor sie geschehen.

**Architecture:** Tier 1, weiter ein Skript `skills/decide/scripts/decide_log.py` (Stdlib). Es
verliert die Bereichslogik von `check` (`<a>..<b>`, `<a>...<b>`, `^!`, Merge-Basen, Ablage aus
einer Revision, Bare-Repo), die Richtung des Schlüsseltexts (`#-`, `#+`) und den Unterbefehl
`brief` samt Wortlisten-Prüfung; `check` hängt Zusammenfassung und offene Fragen an. Neu ist der
Unterbefehl `guard` (PreToolUse-Hook, liest JSON von stdin, Befehlsliste als Konstante, weil die
Hook-Kopie ohne `references/` läuft) mit dem Snippet `assets/hooks/decide-guard.json`. SKILL.md
schrumpft auf höchstens 110 Zeilen; `references/brief.md` wird reine Vorlage.

**Lesson aus Zyklus 1:** Die meisten Fix-Runden kamen aus Randfällen von `check`. Jeder Randfall,
den dieser Plan streicht, endet in einer Zeile „ungeprüft — …“ mit Exit 2 oder in einer Rückfrage,
nie in einem stillen „sauber“ — das ist die Abnahmebedingung jeder Code-Task.

**Tech Stack:** Python 3.11+ Stdlib für Skript und Tests; pytest und `git` in den Tests;
Markdown für Skill und References; JSON für das Hook-Snippet.

**Spec:** `specs/Spec 28 – decide.md`

## Global Constraints

- **E1 — Tier 1, nur Stdlib.** `decide_log.py` importiert nichts außerhalb der Stdlib; `guard`
  läuft auch als Kopie unter `.claude/hooks/` ohne `references/` und ohne `assets/`.
- **E2 — Gate-Sprache** (Spec 00 §4): „blockiert“ nur für `guard` mit installiertem Hook (G3);
  ohne Hook verlangt die SKILL.md (G1); `check` meldet (G2). Die Skill installiert den Hook nie.
- **E3 — Kopfzeile je Artefakt** unverändert für `log.md` und `docs/big-decisions.md`.
- **E4 — SKILL.md ≤ 110 Zeilen**, portables Frontmatter, Description unverändert.
- **E5 — Anti-Zeremonie-Eval** `anti-ceremony-order-in-file-needs-no-decision` und alle fünf
  Evals bleiben unverändert; die Schlusszeile von `check` bleibt wörtlich
  „ungeprüft: data-delete, unsaved-work, push, external, cost; teilweise: api, migration,
  dependency, permissions“.
- **E6 — Seltenes an den Nutzer:** Ein gestrichener Fall endet mit Exit 2 und „ungeprüft — …“
  (`check`) oder mit `ask` (`guard`), nie mit Exit 0 ohne Hinweis.
- **E7 — Signaturen** aus dem Plan `2026-11-02-decide.md` bleiben, außer `check` (bekommt
  `session` und `home`); `write_brief`, `check_brief` und `load_wordlist` entfallen ersatzlos.

## Skill-Struktur

```
skills/decide/
├── SKILL.md                        ≤ 110 Zeilen
├── references/reversibility.md     + Tabelle der Befehle von guard
├── references/option-memo.md       ohne #- und #+
├── references/brief.md             Vorlage statt Parser-Quelle
├── assets/big-decisions.md
├── assets/hooks/decide-guard.json  neu
└── scripts/decide_log.py           ohne brief, check schlanker, + guard

tests/test_decide_log.py, tests/test_decide_guard.py (neu), 17 Akzeptanztests tests/test_decide_*.py
```

### Task 1: decide_log.py check — eine Revision, Text nur für hinzugefügte Zeilen, Übergabe in einem Aufruf

Streicht die Bereichslogik und die Richtung des Schlüsseltexts und hängt Zusammenfassung und
offene Fragen an `check` an. Vorher `wc -l skills/decide/scripts/decide_log.py` notieren, für
den Report.

**Modell:** opus

**Files:**
- Modify: `skills/decide/scripts/decide_log.py`
- Modify: `skills/decide/references/reversibility.md`
- Modify: `skills/decide/references/option-memo.md`
- Modify: `tests/test_decide_log.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_decide_teure_aenderung_ohne_freigabe_wird_gemeldet.py`
- Modify: `tests/test_decide_freigegebene_teure_aenderung_wird_nicht_gemeldet.py`
- Modify: `tests/test_decide_fixtures.py`

**Interfaces:**
- Consumes: `fn:summary(root, session, home)`, `fn:open_questions(root)`, `fn:read_ledger(root)`
- Produces: `fn:check(root, rev, session, home)`, `fn:parse_key(key)`, `token:ungeprüft — check nimmt eine Revision`, `token:ungeprüft — kein Arbeitsbaum`

- [ ] **Step 1: Tests schreiben** — in `tests/test_decide_log.py`: `test_check_one_revision`
      (`HEAD~1..HEAD`, `HEAD~1...HEAD`, `HEAD^!`, `HEAD^@`, eine unbekannte Revision → Exit 2 mit
      „ungeprüft — check nimmt eine Revision, nicht „<angabe>“; den Bereich selbst prüfen“;
      Bare-Repo → Exit 2 mit „ungeprüft — kein Arbeitsbaum“; ein Merge-Commit als `<rev>` wird
      gegen den Arbeitsbaum verglichen), `test_check_includes_summary_and_open` (Sitzung mit
      kleinem Eintrag und ein offener Block erscheinen vor der Schlusszeile; ohne beides nur
      Ergebniszeile und Schlusszeile; ohne Sitzung kein Teil Zusammenfassung, kein Fehler; die
      Schlusszeile ist immer die letzte Zeile; auch bei Exit 2 — Bereich statt Revision —
      stehen Zusammenfassung und offener Block vor der Schlusszeile),
      `test_check_untracked_and_hash_key` erweitert
      (nur entfernte Zeilen mit `#python-dateutil` → gemeldet; `add --key dependency:pyproject.toml#-x`
      und `#+x` → Exit 1; ein Block mit `#-x` in der Ablage gibt nichts frei, Hinweis in der
      Ausgabe), `test_check_unreadable_file` (Datei mit ungültigem UTF-8 unter `migrations/`
      → Stelle „unlesbar — selbst prüfen“, Exit 1). Tests für gestrichene Bereiche,
      Merge-Basen, Root-Commit, Ablage aus einer Revision und `#-`/`#+` löschen; die zwei
      Akzeptanztests oben und `test_eval_patterns` auf die neue Ausgabe von `check` prüfen.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_decide_log.py tests/test_decide_teure_aenderung_ohne_freigabe_wird_gemeldet.py tests/test_decide_freigegebene_teure_aenderung_wird_nicht_gemeldet.py tests/test_decide_fixtures.py -q`.
- [ ] **Step 3: Implementieren** — `check` löst `<rev>` mit
      `git rev-parse --verify --end-of-options <rev>^{commit}` auf; eine Angabe mit `..`, `^!`,
      `^@`, `^-` oder ohne Auflösung → Exit 2 mit dem Token; kein Arbeitsbaum → Exit 2;
      `_revision_ends`, `_ledger_at`, `MERGE_NOTE` und die Ablage aus einer Revision entfernen,
      die Ablage immer aus der Arbeitskopie; `parse_key` kennt nur `#<text>` (hinzugefügte
      Zeilen), ein Text mit führendem `-` oder `+` ist ein Formfehler; je Datei, deren Diff
      nicht lesbar ist, eine Stelle „unlesbar — selbst prüfen“; nach den Stellen die Abschnitte
      wie `summary` (nur mit Sitzung und Einträgen) und wie `open` (nur mit offenen Blöcken),
      dann die Schlusszeile — auch auf jedem Weg mit Exit 2; `main` gibt `check` ein optionales `--session`.
      `references/reversibility.md` (Abschnitt Schlüssel) und `references/option-memo.md` ohne
      `#-` und `#+`, mit dem Satz aus Spec 28: nur entfernte Zeilen gibt nur ein Schlüssel ohne
      Text frei.
- [ ] **Step 4: Grün sehen**, dann die ganze Suite (`pytest -q`); einziger erlaubter roter Test
      ist `test_rest_api_architect_gate.py::test_main_exit_zero_when_degraded_but_checklist_clean`.
- [ ] **Step 5: Commit.**

### Task 2: decide_log.py ohne brief, references/brief.md als Vorlage

**Modell:** sonnet

**Files:**
- Modify: `skills/decide/scripts/decide_log.py`
- Modify: `skills/decide/references/brief.md`
- Modify: `skills/decide/references/option-memo.md`
- Modify: `tests/test_decide_log.py`
- Modify: `tests/test_decide_evals_schema.py`
- Delete: `tests/test_decide_auftrag_uebernimmt_passende_eintraege_und_regeln.py`
- Delete: `tests/test_decide_zu_langer_oder_wertender_auftrag_wird_gemeldet.py`

**Interfaces:**
- Consumes: `fn:main(argv)`
- Produces: `token:Du arbeitest als Subagent.`

- [ ] **Step 1: Test schreiben** — `test_brief_reference_sentence` in `tests/test_decide_log.py`:
      `references/brief.md` und `skills/decide/SKILL.md` enthalten den Satz aus Spec 28 Ablauf 5
      wörtlich (als Konstante im Test, nicht aus dem Skript gelesen); `main(["brief", "--topic", "x"])`
      endet mit argparse-Fehler Exit 2.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_decide_log.py -k brief_reference_sentence -q`.
- [ ] **Step 3: Implementieren** — Unterbefehl `brief` und alles, was nur er braucht, entfernen
      (`write_brief`, `check_brief`, `_check_brief`, `load_wordlist`, `load_subagent_sentence`,
      `_section_lines`, `_fence_step`, `_entry_lines`, `_block_line`, `_decided_line`,
      `_comment_safe`, `_write_new`, `_word_re`, `_resolve_brief`, `BRIEF_REFERENCE` und ihre
      Konstanten), jede Funktion vorher mit `grep -n "<name>(" skills/decide/scripts/decide_log.py`
      auf andere Aufrufer prüfen; die zwei Akzeptanztests und alle `brief`-Tests in
      `tests/test_decide_log.py` löschen; in `tests/test_decide_evals_schema.py` `brief` aus
      `INLINE_CALL_RE` nehmen; den Verweis auf `brief` in `references/option-memo.md` auf die
      Vorlage `references/brief.md` umstellen. Die Zahl der gelöschten Tests notieren (Report).
      `references/brief.md` neu: sechs Felder (Frage, Anlass, Wo
      nachsehen, Schon entschieden, Feste Vorgaben, Rückgabe) mit je einer Zeile, was hinein
      gehört; der feste Satz als Zitat unter Rückgabe; die Wortliste als Hinweis für den
      Hauptagenten (G1, kein Skript liest sie); keine Erwähnung von `brief --topic`,
      `brief --check` oder `brief-<n>.md`.
- [ ] **Step 4: Grün sehen**, dann die ganze Suite; `grep -rn "brief --\|brief-<n>" skills/decide tests`
      ohne Treffer.
- [ ] **Step 5: Commit.**

### Task 3: decide_log.py guard und Hook-Snippet

**Modell:** opus

**Files:**
- Modify: `skills/decide/scripts/decide_log.py`
- Create: `skills/decide/assets/hooks/decide-guard.json`
- Modify: `skills/decide/references/reversibility.md`
- Create: `tests/test_decide_guard.py`

**Interfaces:**
- Consumes: `fn:read_ledger(root)`, `fn:parse_key(key)`, `fn:glob_to_regex(pattern)`
- Produces: `fn:guard(text)`, `fn:guard_decision(command, root)`, `token:Hook ungeprüft`, `token:immer Rückfrage`

- [ ] **Step 1: Tests schreiben** — `tests/test_decide_guard.py` nach Spec 28 „Tests (Repo)“:
      `test_guard_push` (mit Git-Repo und lokalem Bare-Repo als `origin`; ohne Block `ask` mit
      „keine Freigabe mit Schlüssel push:origin/x“; freigegebener Block `push:origin/**` →
      leere Ausgabe; `--force`, `+x`, zwei Refspecs, `--tags` trotz Block → `ask`; ohne Upstream
      und ohne Argumente → `ask`; jüngerer offener Block gleicher Frage und gleichen Schlüssels →
      `ask`; `git push -u origin HEAD` → Ziel `origin/<aktueller zweig>`), `test_guard_commands`
      (je Tabellenzeile ein erkannter und ein ähnlicher nicht erkannter Befehl, wie in der Spec
      aufgezählt; `cd x && git reset --hard` → `ask`; `FOO=1 sudo rm -rf data` → `ask`),
      `test_guard_errors` (kein JSON, leere Eingabe, fehlendes `tool_input` → `systemMessage` mit
      „[decide] Hook ungeprüft“, Exit 0; unbalancierte Anführungszeichen → Teil nicht erkannt),
      `test_guard_table_matches_reference`, `test_hook_snippet`. Jede `ask`-Ausgabe ist gültiges
      JSON mit `hookSpecificOutput.hookEventName` `PreToolUse` und `permissionDecision` `ask`.
- [ ] **Step 2: Rot sehen** — `pytest tests/test_decide_guard.py -q`.
- [ ] **Step 3: Implementieren** — `guard(text)` liest das Hook-JSON, ruft
      `guard_decision(command, root)` (`None` oder `(kategorie, grund)`, erste Rückfrage zählt)
      und gibt `""`, die `ask`-Zeile oder die `systemMessage` zurück; `main(["guard"])` liest
      stdin, schreibt das Ergebnis, endet immer mit 0. Zerlegen mit
      `shlex.shlex(befehl, posix=True, punctuation_chars=";&|\n")` und `whitespace = " \t\r"`, `whitespace_split = True`,
      Trenner nur außerhalb von Anführungszeichen; bei `ValueError` `ask` mit „Befehl nicht
      zerlegbar“, wenn ein Programmname der Tabelle im Text steht, sonst nichts. Zuweisungen
      und `sudo` am Anfang, bei `git` die globalen Optionen (`-C` setzt das Verzeichnis)
      überspringen; Kurzoptions-Bündel auflösen; Befehlsliste als Konstante `GUARD_COMMANDS`,
      Ausnahmeliste für `rm` als Konstante; Push-Ziel genau nach Spec 28 „Push-Ziel“ (bekannte
      Optionen überspringen, jede andere → `ask`; `HEAD` und `refs/heads/` auflösen; `:dst`,
      `+`, andere `refs/`, mehrere Refspecs, abgelöster `HEAD` → `ask`), Upstream über
      `git rev-parse --abbrev-ref --symbolic-full-name @{u}`; Freigabe über den jüngsten Block
      je Frage und Schlüssel mit `push:<muster>` und Status `freigegeben`. Befehl in der
      Begründung auf 80 Zeichen gekürzt. Den Satz „eine zweite Liste im Skript gibt es nicht“
      im Kopf von `decide_log.py` und in `reversibility.md` auf Kategorien und Pfadmuster
      einschränken. `assets/hooks/decide-guard.json` nach dem Vorbild
      `skills/sql-schema-architect/assets/hooks/migration-gate.json` (`_comment` mit
      Installationsweg, Fallback mit „[decide] Hook ungeprüft — .claude/hooks/decide_log.py
      fehlt“). `reversibility.md` bekommt den Abschnitt „Befehle, die guard erkennt“ mit derselben
      Liste.
- [ ] **Step 4: Grün sehen**, dann die ganze Suite.
- [ ] **Step 5: Commit.**

### Task 4: SKILL.md

Schreibt die SKILL.md auf den Stand von Zyklus 2 und kürzt sie. Contract und
Anti-Rationalisierung wiederholen keine Zeile des Ablaufs.

**Files:**
- Modify: `skills/decide/SKILL.md`

**Interfaces:**
- Consumes: `fn:check(root, rev, session, home)`, `fn:guard(text)`, `token:Du arbeitest als Subagent.`, `token:Hook ungeprüft`, `token:ungeprüft — check nimmt eine Revision`
- Produces: `token:Optionaler Hook (G3)`

- [ ] **Step 1: Schreiben** — Ablauf 6 ohne Skript-Aufruf: Auftrag nach `references/brief.md`
      direkt in den Prompt, der feste Satz bleibt wörtlich in Schritt 5; Ablauf 7 mit genau einem
      Aufruf `check --range "<rev>"` als letztem Aufruf vor der Antwort, ohne die Bereichsformen,
      mit dem Satz „Ohne Aufruf kein Satz über das Ergebnis von `check`“ und dem wörtlichen Zitat
      der Schlusszeile; Abschnitt „Optionaler Hook (G3)“ mit Installationsweg (Kopie nach
      `.claude/hooks/`, Snippet mischen, nie selbst installieren) und dem Satz, dass ein
      beauftragter Push einmal mit `--key push:<remote>/<branch>` abgelegt wird; Contract-Punkt
      „Seltenes an den Nutzer“; Anti-Rationalisierung um die Zeile zum Hook aus Spec 28
      ergänzt, dazu die Zeile „Der Hook hat abgelehnt, dann eben über `bash -c`“ und der
      Contract-Punkt „Kein Ausweichen“; ohne geänderte Datei ist der eine Aufruf `open`; der
      Satz „einen Hook gibt es nicht“ in der Eisernen Regel entfällt; Description unverändert.
- [ ] **Step 2: Prüfen** — `wc -l skills/decide/SKILL.md` ≤ 110;
      `pytest tests/test_decide_evals_schema.py tests/test_decide_log.py -q` grün (Tokens der
      Evals stehen wörtlich in der SKILL.md, Satz für Subagenten wörtlich);
      `python skills/skill-forge/scripts/lint_skill.py skills/decide` ohne neuen Befund.
- [ ] **Step 3: Commit.**

### Task 5: Evals

Keine Änderung an `evals/decide/evals.json` und den Fixtures (Spec 28, Zyklus 2): Gemessen wird,
ob die verschlankte Skill dieselben Evals hält.

**Files:**
- Modify: `docs/superpowers/reports/decide-report.md`

**Interfaces:**
- Consumes: `token:Optionaler Hook (G3)`, `token:anti-ceremony-order-in-file-needs-no-decision`
- Produces: `token:Zyklus 2`

- [ ] **Step 1: Schema** — `pytest tests/test_decide_evals_schema.py tests/test_decide_fixtures.py -q`
      grün; `git diff 94526fe -- evals/` leer.
- [ ] **Step 2: Läufe mit Skill** — `python run_evals.py --skill decide` einmal über alle fünf
      IDs: `anti-ceremony-order-in-file-needs-no-decision`, `small-decision-cites-repo-source`,
      `side-decision-expensive-stays-open`, `user-order-is-approval`,
      `always-ask-rule-upgrades-small`; je Eval grün oder rot mit Grund in den Report unter
      `## Zyklus 2`. Abnahme bei mindestens 4 von 5;
      Eval 2 rot gilt als bekannte Routing-Lücke. Ohne Skill kein neuer Lauf (Spec 28).
- [ ] **Step 3: Stichprobe Hook** — in einem Ordner im Scratchpad: Git-Repo mit lokalem Bare-Repo
      als `origin`, `decide_log.py` nach `.claude/hooks/`, Snippet nach `.claude/settings.json`;
      `claude -p "Führe git push -u origin HEAD aus."` je einmal mit
      `--permission-mode default` und `--permission-mode bypassPermissions`, vor dem zweiten Lauf
      den Remote zurücksetzen; nach jedem Lauf zeigt `git ls-remote origin`, ob gepusht wurde.
      Beide Ergebnisse (abgelehnt oder ausgeführt) in den Report; trifft die Annahme aus
      Spec 28 nicht zu, steht das in Task 7 in known-limits. Commit.

### Task 6: Nachbarn

**Files:**
- Modify: `specs/Spec 00 – skill-foundation.md`
- Modify: `.claude/skills/decide/**`

**Interfaces:**
- Consumes: `token:Optionaler Hook (G3)`
- Produces: (nichts Neues)

- [ ] **Step 1: Routing-Matrix** — Spec 00 §5 und README unverändert (Trigger und Abgrenzung
      gleich); `grep -n "decide" README.md "specs/Spec 00 – skill-foundation.md"` zeigt keine
      Erwähnung von `brief` oder Bereichen.
- [ ] **Step 2: Abgrenzungssätze und Spec 00 §4** — in Spec 00 §4 den Satz, der
      `migration_gate.py` (08) und `check_ledger.py` (01) als Skills mit Hook-Snippet nennt, um
      `decide_log.py guard` (28) ergänzen; feature-spec, work-plan, subagent-dev unverändert; der Satz
      für Tasks in `plan_to_tasks.py` bleibt. Plugin-Zuordnung unverändert (`evaluated-dev`,
      `PROJECT_SKILLS`).
- [ ] **Step 3: Projekt-Kopie** — `python scripts/sync_skills.py`, dann
      `python scripts/sync_skills.py --check` sauber; `lint_skill.py skills/decide` ohne Befund
      außer `neighbors` (brainstorming ohne Ordner, wie in Zyklus 1). Commit.

### Task 7: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `token:Zyklus 2`
- Produces: (nichts Neues)

- [ ] **Step 1: Abschnitt** `## decide` — Punkte streichen, die Zyklus 2 gegenstandslos macht
      (Bereiche, Merge-Basen, Ablage aus einer Revision, `#-`/`#+`, alles zu `brief`), neu:
      `check` nimmt nur eine Revision, ein PR-Diff ist Sache des Nutzers; `guard` sieht nur Bash
      und nur die gelisteten Befehle, nicht `$(…)` außerhalb von Anführungszeichen, `bash -c`,
      `eval`, Aliase, Skripte, Heredocs ohne Anführungszeichen, MCP; Ausnahmeliste für `rm` ist
      eine Annahme;
      `guard` fragt auch bei beauftragtem Löschen (nur Push hat eine Freigabe über die Ablage);
      Ergebnis der Stichprobe aus Task 5; der Auftrag an Subagenten ist ganz G1. Anzahl der
      Punkte vorher und nachher zählen (`awk` über den Abschnitt, Zeilen mit `- `). Commit.

### Task 8: Report

**Files:**
- Modify: `docs/superpowers/reports/decide-report.md`
- Modify: `specs/Spec 28 – decide.md`

**Interfaces:**
- Consumes: `token:Zyklus 2`
- Produces: (nichts Neues)

- [ ] **Step 1: Report** — unter `## Zyklus 2`: Zeilen `decide_log.py` und SKILL.md vorher
      (2245, 143) und nachher, Punkte in known-limits vorher (42) und nachher, Aufrufe bei der
      Übergabe (3 → 1), Testzahl, Eval-Ergebnis und Stichprobe aus Task 5, „Was nicht gemessen
      wurde“ (Routing mit CLAUDE.md-Zeile, Hook im Alltag, `ask` beaufsichtigt).
      Spec 28 Next steps: Stand von Zyklus 2 in einem Satz.
      `python skills/skill-forge/scripts/lint_skill.py skills/decide --out .skills/cache/skill-forge/lint.json`.
      Commit.
