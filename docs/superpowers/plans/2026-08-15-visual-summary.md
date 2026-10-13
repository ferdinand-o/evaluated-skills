# visual-summary Implementation Plan

**Goal:** Eine Tier-0-Skill (keine Skripte, reine Doktrin) für das Ad-hoc-„fass das
zusammen" — vier Formate (one-pager, decision-memo, timeline-brief, learn-card),
zwei Renderer (HTML mit eigenem Token-Set, strukturgleiches Markdown) aus einem
gemeinsamen, medienneutralen Inhaltsmodell. Der harte Contract: keine Zahl und
kein Chart ohne Quellenreferenz im Modell.

**Architecture:** Kein Skript sammelt Fakten — Claude baut das Inhaltsmodell direkt
im Kontext (Kernthese, Belege mit Referenz+Konfidenz, Datenpunkte mit Referenz,
offene Punkte) und füllt dann Slots in einem von acht fertigen Templates (vier
HTML, vier Markdown). Die Quellenbindung ist nicht optional-dokumentiert, sondern
im Rendering selbst sichtbar: jede Zahl trägt unmittelbar eine Referenzmarke
(Markdown: native Fußnote `[^n]`; HTML: verlinkter Anker `[n]`), jede Marke hat
einen Eintrag in der Quellenliste am Dokumentende. Das macht den Contract auch
ohne Skript mechanisch/judge-prüfbar — die Referenzliste *ist* das freigelegte
Modell.

**Spec:** `specs/Spec 11 – visual-summary.md`, gebunden an `specs/Spec 00 – skill-foundation.md`.
**Vorbild:** `skills/dev-report/` (Aufbau, Tonfall, Leerfall-Disziplin).

## Entscheidungen aus dem Auftrag (übernommen, nicht verhandelt)

1. Ablageort: `docs/summaries/<format>-<slug>.md|html` im Repo-Fall (Erkennung:
   `.git` im cwd oder einem Elternverzeichnis), sonst
   `~/.skills/visual-summary/summaries/<format>-<slug>.*`.
2. Token-Set: guter Default in `tokens.css`, kein Setup-Interview.
3. Chat-Verlauf wird übergeben (Pfad oder eingefügter Text), nie erraten.
4. Charts: selbst generiertes Inline-SVG, keine Bibliothek.

## Zusätzliche Entscheidungen für dieses Plan (Begründung im Abschlussbericht)

- **Slug-Vorrang:** Nennt der Nutzer einen Slug, gilt er. Ohne Vorgabe leitet die
  Skill einen kebab-case-Slug (≤ 4 Wörter) aus der Kernthese ab. Grund: Ohne
  Skript gibt es keine deterministische Pfadberechnung wie bei dev-reports
  `report_path` — ein nutzerseitig vorgegebener Slug macht den Ausgabepfad
  vorhersagbar, was sowohl echte Nutzung als auch Evals verlangen.
- **Referenzmarken-Konvention:** Jede Zahl/jeder Chart trägt direkt im Anschluss
  eine Zahl in eckigen Klammern; Markdown nutzt dafür native Fußnoten (`[^n]` /
  `[^n]: Locator — Auszug`), HTML einen verlinkten Anker (`[<a href="#ref-n">n</a>]`)
  zu einem `<li id="ref-n">` in der Quellenliste. Gleiche visuelle Grammatik, zwei
  Mechaniken — das ist die mechanisch/judge-prüfbare Oberfläche des Contracts.
- **Längenbudgets sind Zeilenzahlen für Markdown** (mechanisch prüfbar über
  `file_max_lines`); für HTML bleibt das Budget eine Sichtprüfung im Selbst-Audit
  (Druckseite/Bildschirmhöhe) — dokumentiert als bekannte Grenze, nicht stillschweigend
  ignoriert.
- **CSS-Duplikation statt Build-Schritt:** Jedes der vier HTML-Templates bettet
  `tokens.css` vollständig in ein `<style>`-Tag ein (kein `<link>`, kein Build).
  Das hält jede Ausgabedatei einzeln selbstenthalten (Kern von Entscheidung 4),
  kostet aber Konsistenzpflege von Hand bei Token-Änderungen — im Bericht als
  Kompromiss benannt.

## Struktur

```
skills/visual-summary/
├── SKILL.md
├── references/{formats,evidence,charts}.md
└── assets/
    ├── tokens.css
    ├── {one-pager,decision-memo,timeline-brief,learn-card}.html
    └── md/{one-pager,decision-memo,timeline-brief,learn-card}.md
evals/visual-summary/evals.json
evals/fixtures/{buried-number-doc,chat-three-decisions,unbelegt-draft,budget-trap-doc,trivial-note}/
```

---

### Task 1: SKILL.md

**Files:** Create `skills/visual-summary/SKILL.md`

Frontmatter mit `name`/`description`; Description trägt die Abgrenzungsklausel
gegen dev-report (periodisch) und handoff (Sitzungsende) — Pflicht laut Auftrag,
sonst greifen beide Skills nach derselben Anfrage.

Inhalt: Doktrin „Inhalt vor Medium", Triage (zwei Fragen → Format, Medium),
Pflicht zur begründeten Format-Ausgabe, Inhaltsmodell knapp (Verweis auf
references/), Contract-Absatz (Referenzmarken-Konvention, hartes Budget, ein
Format pro Output), Ablauf inkl. Bootstrap-Regel und Kopfzeile, Selbst-Audit
(vier Fragen aus der Spec), Anti-Rationalisierungs-Tabelle, Leerfall-Zeilen
(weniger als drei Belege → weniger, nicht erfunden; keine offenen Punkte →
„Keine."), Abgrenzung. Ziel ≤ 150 Zeilen (dev-report liegt bei ~95).

**Validate:** `wc -l skills/visual-summary/SKILL.md` (≤ 150), Frontmatter-Check
per `head -5`.

**Commit:** `feat(visual-summary): SKILL.md mit Triage, Contract und Anti-Rationalisierung`

---

### Task 2: references/

**Files:** Create `references/formats.md`, `references/evidence.md`, `references/charts.md`

- `formats.md`: pro Format — wann, Aufbau (Sektionen), Längenbudget (Markdown-Zeilen:
  one-pager 60, decision-memo 80, timeline-brief 70, learn-card 40), Leerfälle.
- `evidence.md`: Referenzmarken-Konvention formal, Locator-Regeln je Input-Art
  (Dokument: „S. n"/„§n"; Chat: „Nachricht n"; Code/Projekt: Commit-Hash oder
  `Pfad:Zeile`; Recherche: Quelle/Link/Notiz-ID), Konfidenz-Stufen (gesichert/
  abgeleitet/unsicher).
- `charts.md`: schlank, verweist auf enterprise-ui-Prinzipien (Frage bestimmt
  Chart-Typ, Farbe nie allein bedeutungstragend, kein Chartjunk) plus visual-summary-
  Spezifisches: Inline-SVG-Erzeugung ohne Bibliothek, a11y-Fallback (versteckte
  Datentabelle), „kein Chart ohne Frage, die er beantwortet".

**Validate:** manuelles Gegenlesen gegen SKILL.md-Verweise (keine toten Links).

**Commit:** `feat(visual-summary): Format-, Quellen- und Chart-Referenzen`

---

### Task 3: assets/tokens.css

**Files:** Create `assets/tokens.css`

Primitives + semantische Schicht, hell/dunkel über `prefers-color-scheme` und
`[data-theme]`-Override (wie enterprise-ui), aber eigene, editoriale Identität
(Systemschrift-Serife für Headlines, Sans für Fließtext, distinkter Akzentton),
`--up`/`--down` fürs Chart-Farbpaar, `@media print`-Regeln fürs Ein-Seiten-Budget.

**Validate:** Datei öffnet ohne Syntaxfehler (`python3 -c` grep-basierte Klammer-
Balance ist ausreichend für Tier 0; kein Linter vorhanden).

**Commit:** `feat(visual-summary): persönliches Token-Set (hell/dunkel, editorial)`

---

### Task 4: assets/*.html — vier Formate

**Files:** Create `one-pager.html`, `decision-memo.html`, `timeline-brief.html`, `learn-card.html`

Jede Datei: `tokens.css`-Inhalt komplett in `<style>` eingebettet (Task 3 als
Quelle kopieren), Artefakt-Kopfzeile als allererste Zeile (`<!-- skill:
visual-summary | schema: 1 | generated: ... -->`, gültig vor `<!doctype html>`),
Slots als `{{PLATZHALTER}}`, Wiederholblöcke als `<!-- REPEAT: x --> … <!-- /REPEAT -->`.
Struktur je Format wie in `references/formats.md` festgelegt; Chart-Slot nur in
one-pager/timeline-brief, mit `<figure>` + `aria-label` + versteckter Datentabelle.

**Validate:** Jede Datei enthält `<!doctype html>`, schließendes `</html>`, die
Kopfzeile matcht `ARTIFACT_HEADER_RE` aus `evalkit/assertions.py` (Stichprobe
manuell gegen die Regex geprüft).

**Commit:** `feat(visual-summary): vier HTML-Formate als selbstenthaltene Templates`

---

### Task 5: assets/md/*.md — vier Skelette

**Files:** Create `md/one-pager.md`, `md/decision-memo.md`, `md/timeline-brief.md`, `md/learn-card.md`

Strukturgleich zu Task 4 (dieselben Sektionsnamen, dieselbe Reihenfolge), aber
schmucklos: Überschriften, Tabellen, native Fußnoten für Referenzen. Erste Zeile
Artefakt-Kopfzeile (`<!-- skill: ... -->`). Chart-Datenpunkte als Tabelle, nie
als Bild — explizite Zeile im Skelett, die daran erinnert.

**Validate:** Jede Datei beginnt mit der Kopfzeile; Sektionsüberschriften decken
sich 1:1 mit dem passenden HTML-Template (diff der `##`/`<h2>`-Titel von Hand).

**Commit:** `feat(visual-summary): Markdown-Skelette strukturgleich zu den HTML-Formaten`

---

### Task 6: Evals und Fixtures

**Files:**
- Create `evals/visual-summary/evals.json`
- Create `evals/fixtures/buried-number-doc/{fixture.json,bericht.md}`
- Create `evals/fixtures/chat-three-decisions/{fixture.json,chat.md}`
- Create `evals/fixtures/unbelegt-draft/{fixture.json,quelle.md}`
- Create `evals/fixtures/budget-trap-doc/{fixture.json,material.md}`
- Create `evals/fixtures/trivial-note/{fixture.json,notiz.md}`
- Reuse `evals/fixtures/empty-dir` für den Triage-Eval

Sechs Evals (fünf aus Spec 11 + der nach Spec 00 §2 verpflichtende Anti-Zeremonie-Fall):

1. `buried-number-gets-page-ref` (contract) — 40-„Seiten"-Dokument mit
   Seitenmarken, vergrabene Zahl auf Seite 23. Prüft Zahl **und** Seitenreferenz
   getrennt, plus `artifact_header`, plus Budget.
2. `chat-distills-three-decisions` (contract) — Chat mit drei klaren Entscheidungen
   in viel Rauschen. Prüft alle drei Entscheidungs-Stichworte, `must_not` auf eine
   markante Rausch-Phrase, `file_max_lines` als Distillations-Beleg.
3. `unsupported-number-needs-a-reference-mark` (behavior, judge) — der Contract
   unter Druck: Nutzer verlangt ausdrücklich eine unbelegte Zahl. Judge-Claim
   prüft **Struktur** (Zahl unmittelbar neben Referenzmarke mit Quellenlisten-
   Eintrag, oder die Zahl fehlt ganz) und schließt Umformulierung explizit als
   denselben Verstoß ein — genau die Lücke, die dev-reports `must_not`-Regexe
   nicht schließen konnten.
4. `bare-request-triggers-triage` (contract) — „Fass das zusammen." ohne Material.
   `output_matches` mit zwei unabhängigen Lookaheads (Zielgruppen-Frage UND
   Zweck/Entscheidungs-Frage) plus Fragezeichen, dazu `file_absent` auf einen
   naheliegenden Rate-Dateinamen.
5. `budget-trap-distills-not-truncates` (contract) — Material für drei Seiten,
   Slug erzwingt einen One-Pager. Schlüsselfakt sitzt am Dokumentende — eine
   Top-N-Kürzung würde ihn verfehlen. Prüft `file_max_lines` **und** das
   Vorhandensein des späten Fakts.
6. `trivial-input-stays-minimal` (contract, Anti-Zeremonie-Pflicht-Eval nach
   Spec 00 §2) — Drei-Satz-Notiz, Lernkarte angefordert. `file_max_lines` deutlich
   unter dem Format-Budget, mirrored nach dem Muster
   `quiet-week-stays-short` aus `evals/dev-report/evals.json`.

Jeder Eval-Prompt nennt Format, Medium und Slug explizit, damit der Ausgabepfad
deterministisch ist (siehe Entscheidung oben) — ohne das wäre `file_exists` gegen
einen selbstgewählten Dateinamen nicht prüfbar.

**Validate:**
```bash
python3 -c "from evalkit.schema import load_evals; print(len(load_evals('evals/visual-summary/evals.json')))"
```
Erwartet: `6`, keine `EvalSchemaError`.

**Commit:** `test(visual-summary): sechs Evals inkl. Anti-Zeremonie-Fall und Fixtures`

---

### Task 7: README, known-limits, Abschluss

**Files:**
- Modify `README.md` (visual-summary-Zeile: `*(geplant)*` entfernen)
- Modify `docs/known-limits.md` (Abschnitt „visual-summary" ergänzen: HTML-Budget
  nur sichtprüfbar, CSS-Duplikation, Slug-Vorrang-Konvention als Testbarkeits-
  Voraussetzung)
- Create `docs/superpowers/reports/visual-summary-report.md`

**Validate:**
```bash
<scratchpad>/venv/bin/python -m pytest -q
```
Erwartet: 146 passed (unverändert — diese Skill fasst keinen bestehenden Code an).

**Commit:** `docs: visual-summary als gebaut markiert, bekannte Grenzen ergänzt, Abschlussbericht`
