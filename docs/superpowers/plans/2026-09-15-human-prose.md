<!-- skill: impl-plan | schema: 1 | generated: von Hand nach skills/impl-plan/assets/plan-template.md -->

# human-prose Implementation Plan

**Goal:** Wer eine Mail, einen Abschnitt oder einen Artikel bestellt oder einen Text
überarbeiten lässt, bekommt Prosa ohne Modellmarker — und eine Messung dazu, statt
der Behauptung, sie sei menschlich.

**Architecture:** Tier 1. Der einzige Code ist `skills/human-prose/scripts/measure.py`
(Stdlib: `re`, `statistics`, `json`, `argparse`): ein Textmodell (Absätze, Sätze,
Wörter, Code und Zitate ausgenommen), vierzehn Prüfpunkte mit `pass | finding |
unchecked`, fünf Urteile unter `judgement`, `measure.json` mit `_meta` und `method`,
Vorher/Nachher per `--after`. Dazu zwei References (die Regeln des Entwurfs mit
Phrasen als Muster; der Überarbeitungsablauf), eine SKILL.md mit zwei Modi, fünf Evals
mit drei Fixtures, Tests an den sechs Beispieltexten des Entwurfs.

**Tech Stack:** Python 3.13 Stdlib für Skript und Tests; Markdown für Skill,
References, Evals.

**Spec:** `specs/Spec 19 – human-prose.md`

## Global Constraints

- **E1 — Tier 1, nur Stdlib** (Spec 00 §3). Fehlt das Skript, lautet die Übergabe
  „ungeprüft: measure.py nicht verfügbar", nie „nachgemessen". Kein Geviertstrich in
  einem Wortlaut, den die Skill vorschreibt.
- **E2 — Gate-Sprache** (Spec 00 §4): SKILL.md „verlangt" (G1), `measure.py` „meldet"
  (G2, Exit 1 bei Befund, Exit 2 bei unlesbarem Text). Nichts blockiert.
- **E3 — Kopfzeile je Artefakt** (`docs/artifact-header.md`): `measure.json` per
  `_meta` mit `skill`, `schema`, `generated`; Bootstrap-Ankündigung beim ersten Anlegen
  von `.skills/cache/human-prose/`.
- **E4 — SKILL.md ≤ 150 Zeilen**, Frontmatter nur `name` und `description`,
  Description mit Trigger und Abgrenzung, ohne Prozessverb.
- **E5 — Anti-Zeremonie-Eval ist Pflicht** (Spec 00 §2), gebunden an die
  Register-Zeile und das fehlende Artefakt unter 120 Wörtern.
- **E6 — `unchecked` und `judgement` zählen nie als `pass`.** Jede Zeile in
  `measure.json` sagt, was sie gemessen hat und mit welcher Methode; Schwellen tragen
  den Vermerk `geschätzt`.
- **E7 — Erwartungswerte an den sechs Beispieltexten stehen in den Tests**, auch dort,
  wo eine Heuristik einen Nachher-Text rot zählt (Beispiel 2 Nachher ohne konkretes
  Element, Beispiel 3 Nachher ohne Satz mit zwanzig Wörtern). Ein Test hält den
  gemessenen Wert fest und kommentiert, warum er falsch zählt; der Report nennt ihn.
- **E8 — Keine erfundene Konkretion** (Eiserne Regel): Zahlen nur aus Original,
  Auftrag oder Antwort auf eine `Rückfrage:`.

## Skill-Struktur

```
skills/human-prose/
├── SKILL.md
├── references/rules.md, revise.md
└── scripts/measure.py

evals/human-prose/evals.json, evals/fixtures/hp-empty, hp-cache, hp-vague
tests/test_human_prose_measure.py, tests/test_human_prose_evals_schema.py
```

### Task 1: Textmodell und Satzteiler

Die Grundlage aller Prüfpunkte: Aus Markdown werden Absätze, Sätze und Wörter, ohne
Codezäune, Inline-Code und Zitatblöcke. Listenpunkte sind je ein Satz. Der Satzteiler
kennt Abkürzungen (`z. B.`, `bzw.`, `Nr.`, `ca.`, `d. h.`, `u. a.`, `e.g.`, `i.e.`) und
Zahlen mit Punkt (`3.5`, `21:40` bleibt ein Token).

**Files:**
- Create: `skills/human-prose/scripts/measure.py`
- Test: `tests/test_human_prose_measure.py`

**Interfaces:**
- Consumes: `file:docs/superpowers/specs/2026-09-15-menschlich-schreiben-v0.1.md`
- Produces: `fn:strip_markup(text)`, `fn:paragraphs(text)`, `fn:sentences(text)`, `fn:words(text)`

- [x] **Step 1: Tests schreiben** — die sechs Beispieltexte aus Abschnitt 9 des
      Entwurfs als Fixture-Strings im Test; Satzzahlen 4, 1, 5 (Vorher 1 bis 3) und
      5, 3, 4 (Nachher 1 bis 3); Absätze 1, 1, 1 und 2, 1, 2; Wörter per `str.split`
      63, 36, 52 und 50, 44, 35; „z. B." teilt keinen Satz; ein Codezaun und ein
      Zitatblock verschwinden; drei Listenpunkte sind drei Sätze.
- [x] **Step 2: Rot sehen** — `pytest tests/test_human_prose_measure.py -k "sentences or paragraphs or words"`.
- [x] **Step 3: Implementieren** — Modul-Docstring „Tier 1: nur Stdlib";
      `strip_markup` entfernt Zäune, Inline-Code, Zitatzeilen und Überschriftenmarken
      und merkt sich die Zahl der entfernten Zitatzeilen für `method`; `sentences`
      teilt an `. ! ?` plus Leerraum, außer nach Abkürzung oder Ziffer.
- [x] **Step 4: Grün sehen**, volle Suite.
- [x] **Step 5: Commit.**

### Task 2: Vierzehn Prüfpunkte

Jede Regel ist eine Funktion `(model, register) -> Check(id, status, value, limit,
reason)`, gesammelt in `CHECKS` in der Reihenfolge der Spec-Tabelle. Register-Grenzen
aus Abschnitt 6 des Entwurfs als Konstanten mit Vermerk `geschätzt`.

**Files:**
- Modify: `skills/human-prose/scripts/measure.py`
- Modify: `tests/test_human_prose_measure.py`

**Interfaces:**
- Consumes: `fn:paragraphs(text)`, `fn:sentences(text)`, `fn:words(text)`
- Produces: `fn:check_all(text, register)`, `CHECKS`, `PHRASES_DE`, `PHRASES_EN`, `token:unchecked`, `token:judgement`

- [x] **Step 1: Tests schreiben** — je Prüfpunkt ein reißender und ein bestehender
      Text, dazu die Erwartungswerte an den Beispielen: R1.1 Beispiel 2 Vorher
      `finding` (ein Geviertstrich), alle Nachher `pass`; R4.1/R4.2 Beispiel 1 Vorher
      drei Treffer (Muster mit Lücke: „spielt (\w+ ){0,2}eine entscheidende Rolle",
      „nicht nur .{1,80}, sondern auch", wörtlich „es ist wichtig zu beachten"),
      Beispiel 2 Vorher vier („when it comes to", „it is important to note",
      „pivotal", „robust"), alle Nachher null; R4.3 Beispiel 1 Vorher eins
      (`, wodurch`), Beispiel 2 Vorher eins (`— ensuring`: das Muster erlaubt Komma
      oder Strich vor dem Partizip); R2.1 Beispiel 1 Vorher `finding` (kein Satz ≤ 6),
      Beispiel 3 Vorher `pass`, Beispiel 2 Vorher und Nachher `unchecked` (unter vier
      Sätzen), Beispiel 1 Nachher `pass`, Beispiel 3 Nachher `finding` (kein Satz ≥ 20,
      Kommentar: Regel ist für Register `kurz` zu streng, Report nennt es); R2.2 alle
      sechs `pass` („Darüber hinaus" steht in Beispiel 1 Vorher im Absatzinneren);
      R3.5 Beispiel 1 Vorher `finding` (Schluss), Beispiel 3 Vorher `pass` (die
      Schlussformel „Ich hoffe, das hilft" ist R6, kein R3.5-Muster); R5.1 Beispiel 1
      Vorher `finding`, Beispiel 1 Nachher `pass` (Ziffern, `TTL`), Beispiel 3 Nachher
      `unchecked` (zwei Absätze mit je zwei Sätzen: kein Behauptungsabsatz ab drei
      Sätzen), Beispiel 2 Nachher `finding` mit Kommentar (Heuristik: Ziffer,
      Pfad, Backtick, Datum, Token in Großbuchstaben oder gemischter Schreibung wie
      `PostgreSQL` — deutsche Substantive zählen nicht); R5.2 immer `unchecked`; R3.3
      ein Text mit drei Dreier-Aufzählungen von vier `finding`; R4.4 ein Text mit 20
      -ung-Wörtern auf 1000 `finding`, Beispiel 1 Vorher `pass` (1 auf 63); R1.4, R4.5,
      R4.6, R2.4 je ein Paar; `judgement` enthält genau R3.1, R5.3, R5.4, R2.3-2, R5.2.
- [x] **Step 2: Rot sehen** — `pytest tests/test_human_prose_measure.py -k check`.
- [x] **Step 3: Implementieren** — `Check` als Dataclass; Fenster für R2.1 nach Spec
      (ganzer Text unter zehn Sätzen); Passiv-Heuristik `werden`-Form plus Partizip II
      im selben Satz; Fragment-Heuristik Satz ohne finites Verb aus einer kleinen
      Liste; Hedges aus R4.6; Konkretion wie im Test beschrieben.
- [x] **Step 4: Grün sehen**, volle Suite; die Tabelle der sechs Beispieltexte
      (Prüfpunkt × Text) einmal ausdrucken und gegen die Spec-Tabelle lesen.
- [x] **Step 5: Commit.**

### Task 3: CLI, measure.json, Vorher/Nachher

**Files:**
- Modify: `skills/human-prose/scripts/measure.py`
- Modify: `tests/test_human_prose_measure.py`

**Interfaces:**
- Consumes: `fn:check_all(text, register)`, `CHECKS`
- Produces: `fn:main(argv)`, `fn:render_measure_json(results, meta)`, `measure_json`

- [x] **Step 1: Tests schreiben** — `main([datei, "--out", pfad])` schreibt JSON mit
      `_meta` (`skill: human-prose`, `schema: 1`, `generated` als Aufrufzeile),
      `method` (Satzteiler, Wortzählung, ausgelassene Zitatzeilen), Schlüssel `text`
      mit vierzehn Zeilen in fester Reihenfolge und `judgement` mit fünf Einträgen;
      mit `--after` Schlüssel `before` und `after` statt `text`; `--register kurz`
      ändert die Grenzen; Exit 0 ohne Befund, 1 mit Befund, 2 bei fehlender oder
      nicht dekodierbarer Datei; stdout zeigt bei `--after` Vorher und Nachher
      nebeneinander; erster Lauf in einem Verzeichnis ohne `.skills/cache/human-prose/`
      druckt die Bootstrap-Ankündigung mit Pfad.
- [x] **Step 2: Rot sehen** — `pytest tests/test_human_prose_measure.py -k "main or json"`.
- [x] **Step 3: Implementieren** — `argparse` mit `datei`, `--after`, `--register`,
      `--out`; `_meta` nach `docs/artifact-header.md`; Grenzen im JSON mit
      `"estimated": true`.
- [x] **Step 4: Grün sehen**, volle Suite; einmal
      `python skills/human-prose/scripts/measure.py --help` lesen und das Skript über
      `docs/superpowers/specs/2026-09-15-menschlich-schreiben-v0.1.md` fahren (Exit 1
      erwartet, die Zahlen aus Spec 19 „Problem" im Rahmen der dort genannten Spanne).
- [x] **Step 5: Commit.**

### Task 4: references/rules.md und revise.md

Doktrin-Task. `rules.md` ist der Entwurf, Abschnitte 0 bis 6 und 9, mit den Listen aus
R4.1 und R4.2 zusätzlich als Muster (dieselben, die `PHRASES_DE`/`PHRASES_EN` tragen);
`revise.md` ist Abschnitt 7 mit dem Ein-Zug-Verhalten aus der Spec (nie warten,
`Rückfrage:` am Ende), der Eingriffstiefe und dem Format des Berichts.

**Files:**
- Create: `skills/human-prose/references/rules.md`
- Create: `skills/human-prose/references/revise.md`

**Interfaces:**
- Consumes: `PHRASES_DE`, `PHRASES_EN`, `file:docs/superpowers/specs/2026-09-15-menschlich-schreiben-v0.1.md`
- Produces: `rules_md`, `revise_md`, `token:Rückfrage:`

- [x] **Step 1: rules.md** — Entwurf übernehmen, Kopfzeile mit Herkunft und Version;
      je Phrasenliste ein Absatz „als Muster", Wortlaut identisch mit dem Skript.
- [x] **Step 2: revise.md** — sieben Schritte, Eingriffstiefe leicht/mittel/stark,
      Bericht drei bis fünf Zeilen, `Rückfrage:` als Liste der Stellen, `Offen` gibt
      es nicht mehr; Faktenabgleich als Tabelle Aussage → Stelle im Ergebnis.
- [x] **Step 3: Prüfen** — ein Test vergleicht die Muster in `rules.md` mit
      `PHRASES_DE`/`PHRASES_EN` (Zeile für Zeile gleich); Commit.

### Task 5: SKILL.md

**Files:**
- Create: `skills/human-prose/SKILL.md`

**Interfaces:**
- Consumes: `token:Rückfrage:`, `measure_json`, `rules_md`, `revise_md`
- Produces: `token:Register:`, `token:Nachgemessen:`

- [x] **Step 1: Frontmatter** — `name: human-prose`; Description mit Triggern
      („schreib mir eine Mail", „das klingt nach KI", „überarbeite den Text",
      „menschlicher") und Abgrenzung gegen `setup-writing-style` und `visual-summary`,
      ohne Prozessverb.
- [x] **Step 2: Body** — Eiserne Regel; Ablauf mit Register-Zeile, Modus A (120
      Wörter, `draft.md`, `Nachgemessen: <p> pass, <f> Befunde, <u> ungeprüft`), Modus B
      (Verweis auf `revise.md`, beide Aufrufe mit Repo- und Installationspfad),
      Stilprofil; Contract aus der Spec; Anti-Rationalisierung („eine kleine Zahl macht
      es konkreter", „der Leser merkt den Gedankenstrich nicht", „ich frage kurz
      nach und warte"); Abgrenzung mit `setup-writing-style`, `visual-summary`,
      `explain`, `dev-report`, `handoff`.
- [x] **Step 3: Prüfen** — `wc -l` unter 150; Sprachprüfung nach Spec 00 §4;
      `python skills/skill-forge/scripts/lint_skill.py skills/human-prose` (ohne
      `--base`, neue Skill) — `unchecked` nur, wo `evals/` noch fehlt; Commit.

### Task 6: Evals

**Files:**
- Create: `evals/human-prose/evals.json`
- Create: `evals/fixtures/hp-empty/fixture.json`
- Create: `evals/fixtures/hp-empty/README.md`
- Create: `evals/fixtures/hp-cache/fixture.json`
- Create: `evals/fixtures/hp-cache/text.md`
- Create: `evals/fixtures/hp-vague/fixture.json`
- Create: `evals/fixtures/hp-vague/text.md`
- Create: `tests/test_human_prose_evals_schema.py`

**Interfaces:**
- Consumes: `token:Register:`, `token:Nachgemessen:`, `token:Rückfrage:`, `measure_json`
- Produces: `evals_json`

- [x] **Step 1: Fixtures** — alle drei mit `"git": true`; `hp-empty` mit einer
      README-Zeile (eine Git-Fixture ohne Datei scheitert am leeren Commit);
      `hp-cache/text.md` der Vorher-Text aus Beispiel 1; `hp-vague/text.md` der Satz
      aus der Spec.
- [x] **Step 2: Evals** — die fünf IDs aus der Spec-Tabelle mit den dort genannten
      Assertions: `anti-ceremony-short-mail-no-measurement`,
      `revise-writes-before-and-after`, `vague-text-asks-instead-of-inventing`,
      `long-draft-ends-with-measurement-line`,
      `routing-sounds-like-ai-without-skill-name`; `notes` je Eval mit der
      Diskriminator-Antwort; Muster escaped wie in `evals/skill-forge/evals.json`.
- [x] **Step 3: Schema-Test** — `evalkit.schema.load_evals` lädt sie; die Regexe
      treffen die Fixture-Texte so, wie die Spec sagt (Eval 2: drei Muster auf
      `text.md` vorher wahr; Eval 3: die vagen Formeln vorher wahr, kein Zahl-Muster);
      `lint_skill.py skills/human-prose` meldet `anti-ceremony-eval` `pass`; Commit.

### Task 7: Nachbarn

**Files:**
- Modify: `specs/Spec 00 – skill-foundation.md`
- Modify: `README.md`
- Modify: `skills/explain/SKILL.md`
- Modify: `skills/visual-summary/SKILL.md`

**Interfaces:**
- Consumes: `token:Register:`
- Produces: (nichts Neues)

- [x] **Step 1: Routing-Matrix** — Zeile „Text schreiben oder überarbeiten, der nicht
      nach Modell klingen soll | human-prose (19) | setup-writing-style (Profil),
      visual-summary (verdichtet), explain (erklärt)" in Spec 00 §5 und README.
- [x] **Step 2: Abgrenzungssätze** — je ein Satz in `explain` (Tokens bleiben, wenn
      human-prose den Text formt) und `visual-summary` (ändert Format, nicht Stil);
      vorher `lint_skill.py <nachbar> --base main` und die `evals_due`-Folge tragen.
      `setup-writing-style` liegt im Profil und bleibt unverändert. Commit.

### Task 8: known-limits

**Files:**
- Modify: `docs/known-limits.md`

**Interfaces:**
- Consumes: `evals_json`
- Produces: (nichts Neues)

- [x] **Step 1: Abschnitt `## human-prose`** — Heuristiken (Passiv, Fragment,
      Konkretion, Satzgrenze) und wo sie an den Beispielen falsch zählen; Schwellen
      geschätzt, kein Korpus; R2.1 in Register `kurz` zu streng (Beispiel 3 Nachher);
      Rückfrage im `-p`-Modus ohne Antwort; Profil ungetestet, weil nicht installiert;
      Evals ungefahren. Commit.

### Task 9: Report

**Files:**
- Create: `docs/superpowers/reports/human-prose-report.md`

**Interfaces:**
- Consumes: `evals_json`
- Produces: (nichts Neues)

- [ ] **Step 1: Report** nach `skills/skill-forge/assets/skill-template/report.md`:
      Entscheidungen (nie warten, Phrasen als Muster, vierzehn statt zehn Zeilen),
      „Was gemessen wurde" mit der Tabelle Prüfpunkt × Beispieltext und dem Lauf über
      den Entwurf, „Was nicht gemessen wurde" (Evals, Trigger, Baseline, Profil),
      Lint-Ergebnis. Commit.
