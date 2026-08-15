# verified-research Implementation Plan

**Ziel:** Eine Recherche-Skill, die Fork/Adaption von samber/deep-research (MIT) ist:
Prozessgerüst, Recherche-Typen, Konfidenz-Tracking und Prose-first-Doktrin bleiben;
neu kommen ein nutzergepflegtes Quellenregister mit Tier-System, eine Truth-Bewertungs-
Rubrik, ein Verifikations-Pass (Stichprobe) und ein Delta-Modus über eine
Themen-Wissensdatei hinzu. Kern: „Das Register vor der Suche, das Tier vor dem Claim,
das Delta vor der Wiederholung."

**Spec:** `specs/Spec 12 – verified-research.md`, gebunden an `specs/Spec 00 – skill-foundation.md`.

**Bindende Entscheidungen aus dem Auftrag (nicht verhandelbar):**

- **R7** Register ist `registry.json` (Tier 1, Stdlib), nicht YAML — PyYAML fehlt in
  dieser Umgebung. Jeder Eintrag trägt ein Pflichtfeld `notiz` mit der
  Bewertungsbegründung. `registry.py` kapselt jeden Zugriff.
- **R9** `spotcheck.py`-Quote: kritische Claims 100 %, vom Rest ein Drittel, mindestens
  aber ein Claim — als benannte Konstante, nicht als verstreute Zahl.
- **R10** Wissensdatei: eine Datei pro Thema, kein Themenbaum. Ab 30 Themen warnt die
  Skill, gliedert aber nicht automatisch um.
- **R8** Evals prüfen den Prozess (Register vor Suche, Tier am Claim, Wissensdatei-Update,
  Delta-Trennung, Registereintrag, Spotcheck-Fang), nie Ergebnisqualität einer echten
  Websuche. Alle Fixtures sind lokal, keine WebSearch/WebFetch-Abhängigkeit.
- **R11** Evals hängen ausschließlich an Artefakten, die nur `verified-research`
  hervorbringt — nicht an Dingen, die die global installierte `deep-research`-Skill
  ebenso hätte erzeugen können (Register-Pfad, `notiz`-Feld, Tier-Tag-Syntax,
  spotcheck-Ausgabe, Wissensdatei-Kopfzeile).

## Eine Abweichung, die dieser Plan gegenüber Spec 00 §1 explizit trifft

Spec 00 §1 sagt für nicht projektgebundene Artefakte: „mit optionalem Projekt-Override,
falls eine **gleichnamige Datei** im Repo liegt". Wörtlich genommen bricht das bei
`research/<thema>.md`: Die erste Recherche zu einem neuen Thema hat naturgemäß noch
keine gleichnamige Datei im Projekt — der Override würde nie greifen, der Schreibzugriff
ginge auf `~/.skills/verified-research/research/<thema>.md` im echten Home-Verzeichnis
des Aufrufers. Das ist exakt die Falle, die `docs/known-limits.md` unter „Isolation" für
den Eval-Harness dokumentiert (HOME wird nicht isoliert) und die laut Auftrag bei
`visual-summary` bereits sechs Evals fälschlich rot gemacht hat.

**Auflösung:** Der Override wird auf Verzeichnis-Ebene geprüft, nicht auf Datei-Ebene:
Existiert `.skills/verified-research/` bereits im Projekt (egal mit welchem Inhalt), gilt
der Override für *alle* Artefakte dieser Skill in diesem Lauf — Register **und** jede
neue Themen-Datei. Existiert das Verzeichnis nicht, geht der erste Lauf nach `~/.skills/`
und kündigt das nach der Bootstrap-Regel an. Fixtures legen deshalb immer
`.skills/verified-research/` im Workspace an (mindestens mit einer `registry.json`),
damit kein Eval verdeckt gegen das echte Home-Verzeichnis des Ausführenden läuft.

## Struktur

```
skills/verified-research/
├── SKILL.md
├── references/
│   ├── rating-rubric.md
│   ├── research-types.md
│   └── delta-mode.md
├── assets/
│   └── registry.json
└── scripts/
    ├── registry.py
    └── spotcheck.py
evals/verified-research/evals.json
evals/fixtures/vr-*/               (7 Fixtures, siehe Task 5)
tests/test_verified_research_registry.py
tests/test_verified_research_spotcheck.py
```

---

### Task 1 — Register-Kern: `registry.py` + `assets/registry.json`

**Dateien:** `skills/verified-research/scripts/registry.py`,
`skills/verified-research/assets/registry.json`, `tests/test_verified_research_registry.py`

**Inhalt:**
- `resolve_base_dir(repo, home=None) -> (Path, bool)` — Verzeichnis-Override-Logik s. o.
- `ensure_registry(repo, assets_path, home=None) -> Path` — bootstrap, kündigt ersten
  Lauf an (`print`), kopiert `assets/registry.json` als Ausgangsbestand.
- `load_registry(path) -> dict`, `save_registry(path, data)`.
- `lookup(data, needle) -> dict | None` — Substring-Match über alle Domänen +
  `allgemein`, längstes `pattern` gewinnt bei Mehrfachtreffern.
- `RUBRIC_KEYWORDS` (frozenset, an `rating-rubric.md`s Kriterien angelehnt) +
  `add_entry(data, domain, pattern, name, tier, notiz)` — wirft `RegistryError`, wenn
  `tier` nicht in `{1,2,3}`, `notiz` leer/zu kurz, `notiz` kein Rubrik-Stichwort enthält,
  oder `pattern` in dieser Domäne bereits existiert.
- `TOPIC_WARNING_THRESHOLD = 30`, `count_topics(research_dir)`,
  `topic_warning(research_dir) -> str | None`.
- CLI: `lookup`, `add`, `topics` — je mit `--repo`.
- `assets/registry.json`: vier Domänen (`software-tech`, `recht-steuern-de-eu`,
  `wissenschaft`, `wirtschaft-statistik`) plus `allgemein`, ~30 Einträge, jeder mit
  `pattern`/`name`/`tier`/`notiz`. `_meta`-Kopf nach `docs/artifact-header.md`.

**Test:** `resolve_base_dir` (Projekt vorhanden/fehlend), `ensure_registry` (Bootstrap +
Ankündigung), `lookup` (Treffer, längster Match, kein Treffer), `add_entry` (gültig,
alle vier Fehlerfälle), `topic_warning` (unter/über Schwelle).
Lauf: `.../venv/bin/python -m pytest tests/test_verified_research_registry.py -q`

**Commit:** `feat(verified-research): registry.py und Kern-Register (Tier 1, R7)`

---

### Task 2 — Verifikations-Pass: `spotcheck.py`

**Dateien:** `skills/verified-research/scripts/spotcheck.py`,
`tests/test_verified_research_spotcheck.py`

**Inhalt:**
- Claim-Format (auch in SKILL.md dokumentiert): eine Markdown-Liste-Zeile, die auf
  `[Tier <1-3>{, kritisch}?, Quelle: <adresse>]` endet.
- `CLAIM_RE`, `parse_claims(text) -> list[Claim]` (`Claim`: `text, tier, critical,
  source, line_no`).
- Named constants: `SPOTCHECK_REST_QUOTA = 1/3`, `SPOTCHECK_MIN_SAMPLE = 1`,
  `SPOTCHECK_SEED` (fixer Default-Seed für reproduzierbare Stichproben).
- `select_sample(claims, seed=SPOTCHECK_SEED) -> list[Claim]` — alle kritischen +
  `floor(len(rest) * SPOTCHECK_REST_QUOTA)` zufällig (geseedet) aus dem Rest;
  Minimum-Regel fängt den Gleitkomma-Fall `3 * (1/3) == 0.9999999999999999 → floor 0`
  ab, wenn sonst nichts gewählt wurde, aber Claims vorliegen.
- `write_sample(sample, out_path)` — JSON nach `.skills/cache/verified-research-spotcheck.json`
  (Ephemera, `_meta`-Kopf), pro Claim ein Verifikationsauftrag-Text.
- CLI: `--report <pfad> --repo . --seed N`; exit 2 wenn Report fehlt, exit 3 (mit
  Warnung auf stderr) wenn null Claims im erwarteten Format gefunden wurden — G2:
  das Skript meldet den Verstoß, statt still 0 zu melden.

**Test:** `parse_claims` (kritisch/unkritisch, mehrere Claims, kein Treffer),
`select_sample` (100 % kritisch, Drittel-Quote, Minimum-Regel exakt bei 3 unkritischen
Claims — der in R9 benannte Grenzfall), Determinismus bei festem Seed.
Lauf: `.../venv/bin/python -m pytest tests/test_verified_research_spotcheck.py -q`

**Commit:** `feat(verified-research): spotcheck.py mit benannter Stichproben-Quote (R9)`

---

### Task 3 — Doktrin: `SKILL.md` + `references/`

**Dateien:** `skills/verified-research/SKILL.md`,
`skills/verified-research/references/rating-rubric.md`,
`skills/verified-research/references/research-types.md`,
`skills/verified-research/references/delta-mode.md`

**Inhalt SKILL.md** (≤150 Zeilen, Frontmatter nur `name`/`description`):
- Kern-Satz, Ablauf (Scope → Register-Phase zuerst und verpflichtend → freie Suche →
  Tier-Synthese → spotcheck → Wissensdatei-Update), Tier-Definitionen, Contract
  (kritische Claims brauchen Tier-1/2; nur Tier-3 → wörtlich „Nur Sekundärquellen
  gefunden"; jeder Lauf endet mit Wissensdatei-Update; Aggregator-Zitate werden zur
  Primärquelle zurückverfolgt), das exakte Claim-Tag-Format, Anti-Rationalisierungs-
  Tabelle (die vier aus Spec 12 plus eine zur Register-Pflicht), Abgrenzung gegen
  `deep-research` (global installiert, gleiche Anfragen) und `visual-summary`,
  Attribution an samber/deep-research (MIT).
- Description muss `deep-research` inhaltlich schlagen: Betonung auf Quellenregister,
  Tier-Nachvollziehbarkeit, Gedächtnis über frühere Recherchen — Dinge, die
  `deep-research` nicht hat.

**Inhalt references:**
- `rating-rubric.md`: Kriterien (Primär-/Sekundärstatus, redaktionelle Standards,
  Anreizlage/Interessenkonflikte, Track Record, Aktualität), Einstufungs-Leitfaden
  Tier 1/2/3, Verweis auf `RUBRIC_KEYWORDS` in `registry.py`.
- `research-types.md`: adaptiert (nicht wörtlich kopiert) aus deep-research, gekürzt,
  mit Attributionszeile.
- `delta-mode.md`: Wissensdatei-Schema (Kopfzeile, `## Bekannt`, `## Neu seit <Datum>`,
  `## Offene Fragen`), Differenz-Recherche-Ablauf, 30-Themen-Warnung (R10).

**Test:** keiner (Dokumentation) — mechanische Validierung über
`python3 -c "assert len(open('skills/verified-research/SKILL.md').read().splitlines()) <= 150"`.

**Commit:** `docs(verified-research): SKILL.md, Rubrik, Research-Types, Delta-Mode`

---

### Task 4 — Evals: `evals.json`

**Datei:** `evals/verified-research/evals.json`

7 Evals, alle Klasse `contract` (keine Ergebnisqualitäts-Judge-Assertion, R8/R11):

1. `anti-ceremony-delta-no-news` — Pflicht-Anti-Zeremonie-Eval (Spec 00 §2): Thema
   vollständig bekannt, Wissensdatei aktuell, Skill bleibt kurz und sagt „keine
   Neuigkeiten" statt neu zu recherchieren.
2. `registry-consulted-before-free-search` — fixture-eigener Registereintrag mit
   frei erfundenem Namen/`notiz`; nur konsultierbar, nicht erratbar.
3. `critical-claim-tier3-only-flagged` — kritischer Claim, nur lokale Tier-3-Quelle,
   wörtliche Phrase „Nur Sekundärquellen gefunden" Pflicht, kein Tier-1/2-Tag erlaubt.
4. `unknown-source-gets-registry-entry` — unbekannte lokale Quelle mit rubrik-relevanten
   Fakten im Fixture-Text; neuer Registereintrag mit begründeter `notiz` erwartet.
5. `fresh-topic-updates-knowledge-file` — einfache Anfrage, keine Wissensdatei vorher;
   danach Datei mit Kopfzeile und mindestens einem Tier-Tag Pflicht.
6. `delta-mode-separates-known-and-new` — vorbereitete Wissensdatei + neue lokale
   Quelle; `## Bekannt` und `## Neu` Pflicht, alter Fakt bleibt erhalten.
7. `spotcheck-catches-numeric-trap` — vorbereiteter Bericht mit einem kritischen Claim,
   dessen Zahl der lokalen Quelle widerspricht; `spotcheck.py`-Lauf Pflicht, degradierte
   Markierung „VERWORFEN nach Spotcheck" im aktualisierten Bericht Pflicht.

Jeder Eval trägt in `notes` einen Satz, warum die Assertion nicht auch von
`deep-research` erfüllbar wäre (R11-Selbstprüfung).

**Test/Validierung (nicht ausführen, nur Schema):**
`python3 -c "from evalkit.schema import load_evals; print(len(load_evals('evals/verified-research/evals.json')))"`

**Commit:** `test(verified-research): evals.json — Prozess-Contract, keine Websuche (R8)`

---

### Task 5 — Fixtures

**Dateien:** `evals/fixtures/vr-anti-ceremony/`, `evals/fixtures/vr-registry-hit/`,
`evals/fixtures/vr-critical-tier3-only/`, `evals/fixtures/vr-unknown-source/`,
`evals/fixtures/vr-fresh-topic/`, `evals/fixtures/vr-delta-known-topic/`,
`evals/fixtures/vr-spotcheck-trap/` — je `fixture.json` (`"git": true`) plus
`.skills/verified-research/registry.json`, ggf. `.skills/verified-research/research/<thema>.md`,
und `sources/*.md` als lokale Ersatz-Quellen (nie Web).

**Test:** Kein eigener automatischer Test (Fixtures sind Daten); manuelle Prüfung durch
`evalkit.workspace.prepare()` — nicht ausgeführt, da `run_evals.py` laut Auftrag nicht
läuft. Stattdessen: `python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('evals/fixtures/vr-*/fixture.json')]"`
als reine JSON-Syntaxprüfung.

**Commit:** `test(verified-research): sieben lokale Fixtures für die Prozess-Evals`

---

### Task 6 — known-limits.md ergänzen + Bericht

**Dateien:** `docs/known-limits.md`, `docs/superpowers/reports/verified-research-report.md`

Ergänzt: Quellenauswahl im echten Web bleibt ungeprüft (R8-Grenze), die
Verzeichnis-Override-Interpretation (Abweichung von Spec 00 §1s Wortlaut),
Unsicherheit der Description-basierten Routing-Priorität gegenüber `deep-research`.

**Commit:** `docs: bekannte Grenzen von verified-research, Abschlussbericht`

---

## Reihenfolge und Testlauf

Nach jedem Task: `.../venv/bin/python -m pytest -q` — die 146 bestehenden Tests bleiben
grün, neue Tests kommen hinzu. Häufige, kleine Commits pro Task (teils mehrere Commits
innerhalb eines Tasks, falls sinnvoll).
