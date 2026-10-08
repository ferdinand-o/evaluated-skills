# feature-spec Implementation Plan

**Goal:** Die Skill `feature-spec` bauen — Draft-first statt Interview-first:
Codebase und `docs/decisions.md` scannen, sofort einen vollständigen
Spec-Entwurf mit markierten `Annahme:`-Zeilen vorlegen, und die
Akzeptanzkriterien mechanisch in Test-Stubs exportieren.

**Architecture:** Die Skill selbst ist reine Doktrin (SKILL.md + references +
Template) — kein Skript scannt oder schreibt den Entwurf, das macht Claude im
Gespräch. Der einzige mechanische Teil ist `export_stubs.py` (Tier 1, nur
Stdlib): Es parst `## Non-Goals` und `## Akzeptanzkriterien` aus einer
Spec-Markdown-Datei, verlangt Given/When/Then je Kriterium, und schreibt bei
jedem Verstoß **nichts** — Verweigerung ist atomar, es gibt keinen Teilexport.
Bei Erfolg entsteht pro Kriterium ein pytest-Stub (`@pytest.mark.skip(...)`,
optional zusätzlich ein Vitest-Stub mit `it.todo(...)` hinter `--vitest`).
Re-Exporte überschreiben eine Stub-Datei nur, solange sie noch beide Marker
trägt (Kopfzeile `# spec-stub: <slug>` + Skip-Marker) — das ist ein G2-Gate
nach Spec 00 §4: das Skript urteilt, der Aufruf bleibt freiwillig.

**Tech Stack:** Python 3.13 (Stdlib), pytest als Dev-Abhängigkeit für die
Skript-Tests, der bestehende Eval-Harness (`evalkit/`) für `evals.json` und
Fixtures.

**Spec:** `specs/Spec 03 – feature-spec.md` (und `specs/Spec 00 – skill-foundation.md`
für Artefakt-, Eval-, Tier- und Gate-Vertrag)

## Entscheidungen aus dem Auftrag (übernommen, nicht neu verhandelt)

1. **Marker-Kommentar statt Hash im Dateinamen** für den Re-Export-Schutz:
   `# spec-stub: <slug>` + `@pytest.mark.skip("stub: noch nicht
   implementiert")`. Fehlt einer der beiden Marker beim Re-Export, bleibt die
   Datei unangetastet, gemeldet als „übersprungen (bereits implementiert)".
2. **`docs/decisions.md` bleibt flach.** Ab 30 Einträgen warnt die Skill im
   Output (G1, Selbstauskunft in SKILL.md) — sie gliedert nie automatisch um.
   Kein Skript zählt das mechanisch; das ist Doktrin, keine Gate-Zusage.

## Globale Constraints

- **Tier 1** für `export_stubs.py`: nur Python-Stdlib, kein `pytest`-Import
  zur Laufzeit, kein YAML-Paket.
- **G2-Sprachregelung** (Spec 00 §4): `export_stubs.py` „meldet Verstoß", es
  „blockiert" nicht — SKILL.md und Doku halten sich an diesen Wortlaut.
- **Artefakt-Klassen** (Spec 00 §1): Spec-Entwurf → `docs/specs/wip/`
  (Wissen, committed, wegwerfbar); `docs/decisions.md` → Wissen, committed,
  append-only; Stub-Dateien → `tests/` (Wissen, committed — sie sind der
  dauerhafte Drift-Schutz, kein Ephemera).
- **Kopfzeile** (Spec 00 §1) auf Spec-Entwurf und `docs/decisions.md`:
  `<!-- skill: feature-spec | schema: 1 | generated: … -->`. Stub-Dateien
  bekommen **keine** generische Kopfzeile, sondern den spezifischen
  `# spec-stub: <slug>`-Marker aus Entscheidung 1 — eine dokumentierte
  Ausnahme nach dem `handoff.md`-Muster in `docs/artifact-header.md`, weil der
  Marker hier eine andere Aufgabe hat (Überschreibschutz, nicht
  Schema-Erkennung durch einen Konsumenten).
- **Eval-Contract** (Spec 00 §2): `evals/feature-spec/evals.json`, Klassen
  `contract`/`behavior`, Schema in `evalkit/schema.py`. Fixtures liegen
  gemeinsam unter `evals/fixtures/`. Ein Pflicht-Anti-Zeremonie-Eval ist bei
  dieser Skill nicht explizit gefordert (Spec 03 nennt vier feste Evals) —
  wird im Bericht als Lücke vermerkt, nicht stillschweigend übergangen.
- **Deutsch** in Kommentaren, Commit-Messages, Doku, Skill-Texten. Englische
  Bezeichner in Code/Schema.
- **146 bestehende Tests bleiben grün.** Testlauf über den Venv-Python aus
  dem Auftrag.

---

## Task 1: Spec-Schema, Template, Entscheidungsgedächtnis-Doku

**Files:**
- Create: `skills/feature-spec/references/spec-schema.md`
- Create: `skills/feature-spec/references/decisions-guide.md`
- Create: `skills/feature-spec/assets/spec-template.md`

**Inhalt:**
- `spec-schema.md`: Pflichtfelder aus Spec 03 (Problem, Non-Goals, Annahmen,
  Ansatz, Akzeptanzkriterien nur als Given/When/Then, Offene Fragen mit
  Entscheider), das exakte Markdown-Format, das `export_stubs.py` parst
  (`## Non-Goals`, `## Akzeptanzkriterien` mit `### <Titel>`-Blöcken,
  `- Given/When/Then/And …`-Zeilen), und ein vollständig ausgefülltes
  Beispiel.
- `decisions-guide.md`: Kriterien für „erntbar" (Grundsatzentscheidung,
  wiederverwendbar über das Feature hinaus) vs. „nicht erntbar"
  (Feature-Detail), Zeilenformat für `docs/decisions.md`, die 30-Einträge-
  Warnregel.
- `spec-template.md`: leeres Gerüst mit Platzhaltern, inklusive
  Artefakt-Kopfzeile.

**Test:** keiner (reine Doku) — Prüfung ist die Konsistenz mit dem Parser aus
Task 2, die Task 3 durch Unit-Tests erzwingt.

**Commit:** `docs(feature-spec): Spec-Schema, Template und Entscheidungsgedächtnis-Guide`

---

## Task 2: `export_stubs.py` — Parser, Contract, pytest- und Vitest-Export

**Files:**
- Create: `skills/feature-spec/scripts/export_stubs.py`

**Umfang:**
- `slugify()` (inkl. deutscher Umlaute), `derive_feature()`.
- `find_section()`, `extract_top_bullets()`, `parse_spec()`: sammelt **alle**
  Contract-Verstöße (fehlende/leere Non-Goals, fehlende/leere
  Akzeptanzkriterien-Sektion, Prosa-Kriterien mit Zeilennummer,
  Slug-Kollisionen) in einer Liste und wirft `SpecParseError` erst am Ende —
  kein Verstoß bleibt unentdeckt, weil ein früherer schon abgebrochen hätte.
- `should_write_pytest()` / `write_pytest_stubs()`: Überschreibschutz nach
  Entscheidung 1, `mkdir` und Dateizugriffe ausschließlich nach erfolgreicher
  Validierung (Atomaritäts-Garantie).
- `should_write_vitest()` / `write_vitest_stubs()`: dieselbe Überschreib-Logik,
  gespiegelt auf `// spec-stub: <slug>` + `it.todo(` — hinter `--vitest`,
  Vitest ist sekundär, entsteht aber im selben Lauf wie pytest (Auftrag).
- `main()`: CLI (`spec`-Pfad, `--feature`, `--out-dir`, `--vitest`,
  `--vitest-out-dir`), Exit-Code 0 bei Erfolg, 1 bei Verstoß oder fehlender
  Datei; Refusal-Meldung nennt jede Zeile einzeln, endet mit „Keine
  Stub-Datei wurde geschrieben."

**Test:** noch keiner in diesem Task (Task 3 deckt es vollständig ab) —
stattdessen manueller Smoke-Lauf gegen eine Ad-hoc-Datei, bevor committet
wird, damit Task 3 nicht gegen kaputten Code schreibt.

**Commit:** `feat(feature-spec): export_stubs.py parst Given/When/Then und exportiert pytest-/Vitest-Stubs`

---

## Task 3: Unit-Tests für `export_stubs.py`

**Files:**
- Create: `tests/test_feature_spec_export.py`

**Testfälle (Muster: `tests/test_dev_report_collect.py`, `conftest.load_script`):**
- `slugify`: Normalfall, Umlaute, leerer String.
- `derive_feature`: aus `# Feature: …`, Fallback auf `# <Titel>`, Fallback
  auf Dateinamen.
- `parse_spec` positiv: zwei valide Kriterien, Given/When/Then korrekt
  gebündelt, `And`-Fortsetzung wird der letzten Kategorie zugeschlagen.
- `parse_spec` negativ, je ein Test:
  - `## Non-Goals` fehlt ganz.
  - `## Non-Goals` vorhanden, aber leer.
  - `## Akzeptanzkriterien` fehlt ganz.
  - Sektion vorhanden, aber ohne `### `-Kriterien.
  - Ein Kriterium ist Prosa (keine `- `-Liste) — Fehlermeldung trägt die
    korrekte Zeilennummer der Überschrift.
  - Ein Kriterium hat Bullets, aber keine mit Given/When/Then/And-Präfix —
    Fehlermeldung trägt die Zeilennummer des ersten unparsbaren Bullets.
  - `And` als erstes Bullet ohne vorausgehendes Given/When/Then.
  - Kriterium fehlt eine Kategorie (z. B. kein `Then`).
  - Zwei Kriterien kollidieren im Slug — beide referenzierten Zeilen stehen
    in der Meldung.
  - **Kombinierter Fall:** Non-Goals fehlt UND ein Kriterium ist Prosa —
    beide Meldungen erscheinen zusammen (Beweis, dass gesammelt statt beim
    ersten Fehler abgebrochen wird).
- `should_write_pytest` / Overwrite-Schutz:
  - Datei existiert nicht → schreiben.
  - Datei existiert mit beiden Markern → überschreiben (Inhalt ändert sich).
  - Datei existiert, Skip-Marker entfernt (simuliert „implementiert") →
    unangetastet, im Rückgabewert als „übersprungen" markiert.
  - Datei existiert ganz ohne `# spec-stub:`-Kopfzeile (fremde Datei am
    selben Pfad) → unangetastet.
- Vitest-Pendant derselben vier Overwrite-Fälle (`should_write_vitest`).
- `main()`-Integrationstests über `capsys`/`tmp_path`:
  - Erfolgsfall: Exit 0, Stub-Dateien entstehen, Stdout nennt Pfade.
  - **Der wichtigste Testfall:** eine Spec mit einem validen und einem
    Prosa-Kriterium → Exit ungleich 0, **keine** der beiden Stub-Dateien
    entsteht (auch nicht die des validen Kriteriums), Stderr nennt die
    Zeilennummer und das Wort „Given/When/Then".
  - Spec-Datei existiert nicht → Exit 1, klare Fehlermeldung.
  - Re-Export-Lauf über `main()` zweimal hintereinander: zweiter Lauf nach
    manuellem Entfernen des Skip-Markers verändert die Datei nicht.
  - `--vitest`-Lauf erzeugt zusätzlich `it.todo(...)`-Dateien im
    `--vitest-out-dir`.

**Verifikation:** `.../scratchpad/venv/bin/python -m pytest -q` — alle neuen
Tests grün, die 146 bestehenden weiterhin grün.

**Commit:** `test(feature-spec): export_stubs.py — Contract-Verweigerung, Overwrite-Schutz, Re-Export`

---

## Task 4: SKILL.md

**Files:**
- Create: `skills/feature-spec/SKILL.md`

**Umfang:** Frontmatter (`name`, `description` mit Abgrenzung gegen
systematic-debugging und superpowers:writing-plans), eiserne Regel
(Scannen vor Fragen), Ablauf in sieben Schritten (Scannen → Fallback-Prüfung
→ Entwurf → Vorlegen → Export → Ernten → Spec ist wegwerfbar), Contract-
Abschnitt mit der G2-Sprachregelung für `export_stubs.py`, Marker-basiertem
Re-Export-Schutz, 30-Einträge-Warnregel; Anti-Rationalisierungs-Tabelle;
Abgrenzung. ≤150 Zeilen (Spec 00 §5).

**Test:** `wc -l` gegen die 150-Zeilen-Grenze; kein automatisierter Test
sonst — Doktrin wird über die Evals geprüft, nicht über Unit-Tests.

**Commit:** `feat(feature-spec): SKILL.md — Draft-first-Doktrin, Contract, Abgrenzung`

---

## Task 5: Fixtures

**Files:**
- Create: `evals/fixtures/prose-criteria/` (fixture.json, README.md,
  `docs/specs/wip/notifications.md` mit einem validen + einem
  Prosa-Kriterium, gültigen Non-Goals)
- Create: `evals/fixtures/vague-feature/` (fixture.json, README.md,
  kleine Task-Manager-Codebase mit `src/email.py`, `src/events.py`, damit
  die vage Anfrage „bau mir Notifications" plausible Annahmen über
  bestehende Muster erlaubt)
- Create: `evals/fixtures/decisions-conflict/` (fixture.json, README.md,
  `docs/decisions.md` mit Kopfzeile und einer Fehlerformat-Entscheidung,
  kleine API-Codebase)
- Create: `evals/fixtures/scope-risk-tenant/` (fixture.json, README.md,
  Multi-Tenant-Codebase mit durchgängigem `tenant_id`-Scoping, damit ein
  CSV-Export-Wunsch das versteckte Mandanten-Risiko trägt)

**Test:** mechanischer Ladetest über `evalkit.workspace.prepare()` wird nicht
separat automatisiert (kein bestehendes Muster dafür in dev-report), aber
jede `fixture.json` wird nach dem Schreiben mit `json.load` auf Syntax
geprüft (Bash-Einzeiler, kein Testfile).

**Commit:** `feat(feature-spec): vier Eval-Fixtures — Prosa-Falle, vage Anfrage, Entscheidungs-Konflikt, Mandanten-Scope`

---

## Task 6: `evals/feature-spec/evals.json`

**Files:**
- Create: `evals/feature-spec/evals.json`

**Vier Evals aus Spec 03, wie im Auftrag zugeteilt:**
1. `prose-criteria-refuses-export` — **contract**, trägt den Contract, zuerst
   gebaut. Mechanisch: `file_absent` auf beide möglichen Stub-Pfade,
   `output_matches` für Zeilennummer-Hinweis und die Begriffe
   „Given"/„When"/„Then" einzeln (falsifizierbar statt eines
   umgehbaren Kombi-Patterns), `git_head_unchanged`.
2. `vague-request-drafts-with-marked-assumptions` — **behavior**, Judge-
   Claims für: sofortiger vollständiger Entwurf ohne Fragenlawine,
   `Annahme:`-Zeilen einzeln markiert, kein ungeerdeter
   Vollständigkeits-Anspruch. Plus mechanisches `output_matches` auf
   `(?i)annahme:` als billiges Zusatzsignal.
3. `decisions-conflict-is-surfaced` — **contract**: `output_matches` auf den
   konkreten entschiedenen Begriff aus der Fixture (nicht nur „ich prüfe
   decisions.md") plus auf den Dateinamen `decisions.md`.
4. `hidden-scope-risk-lands-in-non-goals` — **behavior**: Judge-Claim, dass
   Non-Goals das Mandanten-Risiko konkret benennt, `must_not`-Judge-Claim
   gegen generische Nicht-Ziele ohne Codebase-Bezug.

**Test:** mechanische Validierung, keine echten Agent-Läufe (verboten laut
Auftrag):
```bash
python3 -c "from evalkit.schema import load_evals; print(len(load_evals('evals/feature-spec/evals.json')))"
```

**Commit:** `feat(feature-spec): vier Evals — Prosa-Falle als Contract zuerst`

---

## Task 7: Repo-weite Anschlüsse

**Files:**
- Modify: `docs/artifact-header.md` (Ausnahme für `# spec-stub:`-Marker nach
  dem `handoff.md`-Muster dokumentieren)
- Modify: `README.md` (Routing-Zeile `feature-spec` von „geplant" auf gebaut
  setzen)

**Test:** keiner (Doku-Änderungen); Sichtprüfung der Konsumenten-Regel-Logik
bleibt konsistent mit Task 1.

**Commit:** `docs: feature-spec-Ausnahme in artifact-header.md, README-Routing aktualisiert`

---

## Task 8: Abschlussbericht

**Files:**
- Create: `docs/superpowers/reports/feature-spec-report.md`

**Inhalt:** was gebaut wurde, zusätzlich getroffene Entscheidungen (z. B.
exaktes Markdown-Parsformat, Vitest-Umfang), was nicht verifiziert werden
konnte (keine echten Agent-Läufe, keine Judge-Kalibrierung), was davon nach
`docs/known-limits.md` gehört.

**Commit:** `docs: Abschlussbericht feature-spec`

---

## Verifikationsschritt vor Abschluss

```bash
.../scratchpad/venv/bin/python -m pytest -q
python3 -c "from evalkit.schema import load_evals; print(len(load_evals('evals/feature-spec/evals.json')))"
```
Beide müssen grün bzw. `4` zurückgeben, bevor der Bericht geschrieben wird.
