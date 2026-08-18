# review-context Implementation Plan

**Goal:** Kontextpaket-Zulieferer für `/code-review` (Spec 04, Zuschnitt (a) aus Spec 00 §5,
R12 des Auftrags). Baut **nicht** die Linsen-Engine — die liefert Claude Code bereits als
`/code-review`. Additiv ist ausschließlich `collect_context.py`: ein deterministisches,
Tier-1-Skript, das aus einem Git-Diff drei gewichtete Kontextpakete (Spec-Compliance,
Korrektheit, Vereinfachung) baut und als `.skills/cache/review-context.json` ablegt.

**Architecture:** Ein Skript, vier Phasen in einer Datei: (1) Diff einsammeln (Range oder
Uncommitted, Ist-Stand vor/nach je Datei, Patch-Text, alles mit benannten Kappungen), (2)
Soll auflösen (Feature-Spec → PR-Beschreibung → Commit-Messages, mit Tautologie-Vermeidung
bei Single-Commit-Ranges — siehe Entscheidung unten), (3) berührte Symbole samt Aufrufer-
Signaturen (Python: `ast`; TS/JS: `grep`-Regex, benannte Grenze), (4) alles zu drei Paketen
zusammensetzen und schreiben. Kein Subagent, keine Linsen-Prompts, keine Renderer — die
SKILL.md beschreibt nur, wie das Paket an `/code-review` übergeben wird.

**Tech Stack:** Python 3.13 (Stdlib: `ast`, `re`, `subprocess`, `json`, `argparse`), git CLI.
Tier 1, keine PyPI-Pakete (R16).

**Auftrag:** `brief-review-context.md` (im Dispatch), R12–R16. **Specs:** `specs/Spec 04 –
code-review.md` (Abschnitt „Status" + R12 lesen, bevor der Rest gilt), `specs/Spec 00 –
skill-foundation.md` (Artefakt-, Eval-, Tier-, Gate-Vertrag).

## Globale Entscheidungen (zusätzlich zu R12–R16, im Bericht vermerkt)

- **Diff-Auswahl:** `--range BASIS..ZIEL` (Zwei-Punkt, git-Range) oder ohne Flag = Uncommitted
  (`git diff HEAD`, Arbeitsverzeichnis gegen HEAD). Drei-Punkt-Syntax (`...`) wird abgelehnt —
  Merge-Base-Auflösung wäre zusätzliche Komplexität ohne Tier-1-Nutzen hier.
- **Commit-Messages als Soll-Quelle nur ab zwei Commits im Range.** Ein Range mit genau einem
  Commit reviewt gerade diesen Commit — seine eigene Subject-Zeile beschreibt den Diff, nicht
  das Ziel dahinter (Tautologie). Uncommitted-Diffs haben nie eine Commit-Message. Das macht
  „Diff ohne jedes Soll" (R13, Eval 1) deterministisch erzeugbar, ohne dass der Eval-Harness
  echte uncommittete Zustände bauen müsste (er kann das nicht, siehe `docs/known-limits.md`,
  Abschnitt Fixtures — `dirty-worktree` ist nach `prepare()` sauber).
- **`docs/decisions.md` folgt derselben Konsumenten-Regel wie `dev-report`s Harvest:** Header
  fehlt oder Schema passt nicht → sichtbar übersprungen, nie geraten. Die Skill, die diese
  Datei erzeugt (feature-spec, Spec 03), ist noch nicht gebaut — der Regelfall ist also
  aktuell `missing` oder `no_header`, ehrlich gemeldet.
- **Aufrufer-Suche ist grep-basiert für beide Sprachen** (R16 erlaubt das explizit für TS,
  hier auf Python-Aufrufer-*Fundstellen* ausgedehnt — nur die Python-*Signaturen* selbst
  kommen aus `ast`). Deckelung: 20 Aufrufer, Rest als Zahl benannt.
- **Symbol-/Aufrufer-Erkennung entfällt für gelöschte Dateien.** Wer eine Datei löscht, hat
  keinen „Nachher"-Zustand, aus dem sich Symbolgrenzen ableiten ließen. Als bekannte Grenze
  vermerkt, nicht stillschweigend.

## Was gebaut wird

```
skills/review-context/
├── SKILL.md
├── references/
│   └── context-packets.md
└── scripts/
    └── collect_context.py
evals/review-context/evals.json
evals/fixtures/review-context-no-soll/
evals/fixtures/review-context-with-spec/
evals/fixtures/review-context-mini-diff/
evals/fixtures/review-context-caller/
tests/test_review_context_collect.py
docs/known-limits.md          (Ergänzung: Abschnitt review-context)
docs/superpowers/reports/review-context-report.md
```

---

### Task 1: Grundgerüst — Range, Diff-Dateien, Ist-Ränder

**Files:** Create `skills/review-context/scripts/collect_context.py`, `tests/test_review_context_collect.py`

**Interfaces:**
- `resolve_range(range_arg: str | None) -> tuple[str, str, str | None, str | None]` → `(mode, base, head, raw)`, `mode` ∈ `{"range", "uncommitted"}`
- `_diff_args(mode, base, head) -> list[str]`
- `list_changed_files(repo, mode, base, head) -> list[dict]` — je Datei `path`, `old_path`, `status` (`added`/`modified`/`deleted`/`renamed`/`binary`), `insertions`, `deletions`, `before`, `before_truncated`, `before_note`, `after`, `after_truncated`, `after_note`, `patch`, `patch_truncated`, `changed_ranges_after`
- `CollectError`

**Tests (u. a.):** leerer Diff → `[]`; neue Datei → `before is None`, `before_note` gesetzt; gelöschte Datei → `after is None`; Binärdatei (git erkennt sie über `-`/`-` im numstat) → `status == "binary"`, kein Patch; Umbenennung → `old_path` gesetzt; Range mit `...` wirft `CollectError`; kein Git-Repo wirft `CollectError`.

**Commit:** `feat(review-context): Diff-Sammlung mit Range/Uncommitted und benannten Rändern`

---

### Task 2: Soll-Auflösung

**Files:** Modify `collect_context.py`, `tests/test_review_context_collect.py`

**Interfaces:**
- `parse_given_when_then(text: str) -> list[dict]` — je Kriterium `title`, `given`, `when`, `then`, `and_` (Liste)
- `find_feature_spec(repo) -> list[dict] | None` — liest `docs/specs/wip/*.md`
- `find_pr_description(pr_description, pr_description_file) -> dict | None`
- `find_commit_message_soll(repo, mode, base, head) -> dict | None` — `None` bei `mode == "uncommitted"` oder < 2 Commits im Range
- `resolve_soll(repo, mode, base, head, pr_description, pr_description_file) -> dict` mit `source` ∈ `{"feature_spec", "pr_description", "commit_messages", "none"}`, `weak: bool`
- `NO_SOLL_MESSAGE`, `EMPTY_DIFF_MESSAGE` als Konstanten mit dem exakten Wortlaut aus R13

**Tests:** GWT-Block wird korrekt geparst (Given/When/Then, optional And); Spec ohne GWT-Block liefert trotzdem `criteria == []` plus Excerpt, aber `source == "feature_spec"` bleibt (R13: das zählt noch als Soll, nur schwächer strukturiert); PR-Beschreibung nur genutzt, wenn keine Spec da ist; Single-Commit-Range liefert `find_commit_message_soll() is None`; Zwei-Commit-Range liefert die Messages; nichts von allem → `source == "none"`.

**Commit:** `feat(review-context): Soll-Auflösung — Feature-Spec, PR-Beschreibung, Commit-Messages`

---

### Task 3: Ist-Vertiefung — decisions.md, Symbole, Aufrufer

**Files:** Modify `collect_context.py`, `tests/test_review_context_collect.py`

**Interfaces:**
- `read_decisions(repo) -> dict` — Konsumenten-Regel wie `dev-report`s Harvest (`status`: `read`/`missing`/`no_header`/`schema_mismatch`)
- `detect_python_symbols(after_text, changed_ranges) -> list[dict]` — `ast`-basiert, je Symbol `name`, `kind`, `signature`, `lineno`
- `detect_ts_symbols(after_text, changed_ranges) -> list[dict]` — regex-basiert (`function`, `const … = (`, `class`)
- `find_callers(repo, symbol_name, definition_path, cap=20) -> dict` — `shown` (je `file`, `line`, `text`, `caller_signature`), `total`, `note` bei Deckelung

**Tests:** Python-Funktion, deren Body sich ändert (Signatur bleibt gleich) wird als berührt erkannt; Signatur wird korrekt extrahiert (auch mehrzeilig); Aufrufer in anderer Datei wird gefunden, seine umschließende Funktion als `caller_signature`; > 20 Aufrufer → `note` benennt die Zahl, `shown` hat genau 20 Einträge; TS-`function`/`const`-Deklaration wird erkannt; `docs/decisions.md` fehlt → `status == "missing"`; Header falsch/fehlt → `status == "no_header"`.

**Commit:** `feat(review-context): Symbol- und Aufrufer-Erkennung, decisions.md-Konsum`

---

### Task 4: Paket-Zusammenbau, CLI, JSON-Ausgabe

**Files:** Modify `collect_context.py`, `tests/test_review_context_collect.py`

**Interfaces:**
- `gather_conventions(repo, changed_paths) -> dict` — Geschwisterdateien je Verzeichnis (gekappt), vorhandene Konventions-Marker (`pyproject.toml`, `ruff.toml`, `tsconfig.json`, `.eslintrc*`)
- `build_context(repo, args) -> dict` — Top-Level-Objekt mit `_meta`, `range`, `diff`, `findings`, `packages.{spec_compliance,correctness,simplification}`
- `main(argv=None) -> int`
- `SCHEMA_VERSION = 1`, `CACHE_PATH = .skills/cache/review-context.json`

**Contract, mechanisch geprüft in Tests:** leerer Diff → genau ein Finding (`empty_diff`), kein `no_soll` zusätzlich; kein Soll bei nicht-leerem Diff → `no_soll`-Finding mit exaktem Wortlaut; `_meta.skill == "review-context"`; `main()` schreibt nach `.skills/cache/review-context.json`, gibt `0` zurück außer bei `CollectError` (dann `1` + Meldung auf stderr).

**Commit:** `feat(review-context): Paket-Zusammenbau, CLI und JSON-Ausgabe`

---

### Task 5: SKILL.md und references/context-packets.md

**Files:** Create `skills/review-context/SKILL.md`, `skills/review-context/references/context-packets.md`

**Inhalt SKILL.md (≤ 150 Zeilen):** Zweck (Zulieferer, kein Review), Ablauf (Skript aufrufen →
Paket an `/code-review` übergeben), Contract (keine Erfindung von Soll, Befund statt Rateversuch,
Grenzen benennen), Abgrenzung zu `/code-review`/`/security-review`, Anti-Rationalisierungs-Tabelle.
Description routet explizit weg von „review mal meinen Diff" (das ist `/code-review`) hin zu „vor
einem Review, damit der Reviewer nicht rät".

**Commit:** `docs(review-context): SKILL.md und Kontextpaket-Referenz`

---

### Task 6: Evals — vier Fixtures + evals.json

**Files:** Create `evals/fixtures/review-context-no-soll/`, `evals/fixtures/review-context-with-spec/`,
`evals/fixtures/review-context-mini-diff/`, `evals/fixtures/review-context-caller/`,
`evals/review-context/evals.json`

Jede Fixture `"git": true` (Zwei-Fallen-Warnung aus dem Auftrag). Jede Assertion zielt auf
`.skills/cache/review-context.json`-Inhalt, nie auf etwas, das `/code-review` selbst liefern
könnte. Vier Evals wie in R13–R16 skizziert, alle `class: "contract"`.

**Validierung (mechanisch, kein echter Agent-Lauf):**
```
python3 -c "from evalkit.schema import load_evals; print(len(load_evals('evals/review-context/evals.json')))"
```

**Commit:** `test(review-context): vier Contract-Evals mit Fixtures`

---

### Task 7: known-limits.md, Bericht

**Files:** Modify `docs/known-limits.md` (Abschnitt `review-context` im Stil des `dev-report`-Abschnitts),
Create `docs/superpowers/reports/review-context-report.md`

**Commit:** `docs: bekannte Grenzen und Abschlussbericht für review-context`

---

## Verifikation vor Abschluss

```bash
.venv/bin/python -m pytest -q   # 146 bestehende + neue müssen grün sein
python3 -c "from evalkit.schema import load_evals; print(len(load_evals('evals/review-context/evals.json')))"
wc -l skills/review-context/SKILL.md   # ≤ 150
```
