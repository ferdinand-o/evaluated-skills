# Abschlussbericht: visual-summary (Spec 11)

Branch `feat/visual-summary`, Basis `0831fb7` (specs/skill-foundation). Plan:
`docs/superpowers/plans/2026-08-15-visual-summary.md`.

## Was gebaut wurde

```
skills/visual-summary/
├── SKILL.md                     (106 Zeilen, ≤150-Budget eingehalten)
├── references/
│   ├── formats.md                (vier Formate: wann, Aufbau, Zeilenbudget, Leerfälle)
│   ├── evidence.md                (Referenzmarken-Konvention, Locator je Input-Art, Konfidenz)
│   └── charts.md                  (Chart-Typen, Inline-SVG-Doktrin, verweist auf enterprise-ui)
└── assets/
    ├── tokens.css                 (editoriales Token-Set, hell/dunkel, @media print)
    ├── one-pager.html, decision-memo.html, timeline-brief.html, learn-card.html
    └── md/one-pager.md, decision-memo.md, timeline-brief.md, learn-card.md

evals/visual-summary/evals.json    (6 Evals: 5 aus Spec 11 + 1 Pflicht-Anti-Zeremonie-Eval)
evals/fixtures/{buried-number-doc,budget-trap-doc,chat-three-decisions,unbelegt-draft,trivial-note}/
```

Tier 0 bestätigt: kein Python-Skript. Das Inhaltsmodell entsteht direkt im
Kontext von Claude (Kernthese, Belege+Referenz+Konfidenz, Datenpunkte+Referenz,
offene Punkte) und wird beim Rendern über die Referenzmarken-Konvention im
Output selbst sichtbar — das war die zentrale Design-Entscheidung, um den
Contract auch ohne Sammel-Skript mechanisch/judge-prüfbar zu machen (siehe
unten).

## Die vier Entscheidungen aus dem Auftrag — wie sie umgesetzt sind

1. **Ablageort:** `docs/summaries/<format>-<slug>.md|html` im Repo-Fall
   (`.git` im cwd oder Elternverzeichnis), sonst
   `~/.skills/visual-summary/summaries/<format>-<slug>.*`. Bootstrap-Regel aus
   Spec 00 §1 in SKILL.md übernommen (erster Lauf kündigt `docs/summaries/` an).
2. **Token-Set:** `assets/tokens.css` mit gutem editorialen Default (Serif-Headlines,
   Sans-Fließtext, warmer Terrakotta-Akzent statt eines weiteren Blaus), kein
   Setup-Interview.
3. **Chat-Verlauf:** SKILL.md verlangt explizit Pfad oder eingefügten Text, nie
   Rekonstruktion aus der laufenden Session; als eigener Abschnitt in
   `references/evidence.md` verankert.
4. **Charts:** handgebautes Inline-SVG aus `references/charts.md`, keine
   Bibliothek, Token-Farben, versteckte Datentabelle als A11y-Fallback,
   Markdown bekommt nie ein Bild, immer eine Tabelle.

## Zusätzliche Entscheidungen, die ich treffen musste

- **Referenzmarken-Konvention als Contract-Mechanik.** Die Spec sagt „keine Zahl
  ohne Quellenreferenz im Modell", nennt aber keine konkrete Syntax. Ich habe
  festgelegt: Markdown nutzt native Fußnoten (`[^n]` / `[^n]: Locator — Auszug`),
  HTML einen verlinkten Anker (`[<a href="#ref-n">n</a>]`) zu einem `<li
  id="ref-n">` in der Quellenliste — dieselbe visuelle Grammatik (Zahl in
  Klammern), zwei Mechaniken. Das war nötig, damit der Contract ohne Skript
  überhaupt prüfbar ist: Die Quellenliste im Output *ist* das freigelegte
  Inhaltsmodell.
- **Slug-Vorrang.** Ohne Sammel-Skript gibt es keine deterministische
  Pfadberechnung wie `collect.py`s `report_path` bei dev-report. Ich habe
  festgelegt: Nennt der Nutzer einen Slug, gilt er; sonst leitet die Skill einen
  kebab-case-Slug aus der Kernthese ab. Alle sechs Eval-Prompts nennen Format,
  Medium und Slug explizit, damit der Ausgabepfad für die Assertions
  vorhersagbar ist — ohne das wäre `file_exists` gegen einen selbstgewählten
  Dateinamen nicht schreibbar gewesen. Das ist in `docs/known-limits.md`
  dokumentiert: ein Prompt ohne Slug-Vorgabe ist eval-seitig ungetestet.
- **Konkrete Zeilenbudgets je Format** (one-pager 60, decision-memo 80,
  timeline-brief 70, learn-card 40 Zeilen Markdown) — die Spec sagt „das
  Budget ist hart", nennt aber keine Zahl. Ich habe mich an dev-reports
  `quiet-week-stays-short` orientiert (40 Zeilen für fünf Sektionen) und die
  Zahlen pro Format proportional zur Komplexität der Struktur skaliert
  (Optionen-Matrix braucht mehr Platz als eine Lernkarte).
- **CSS-Duplikation statt Build-Schritt.** `tokens.css` wird komplett in jedes
  der vier HTML-Templates eingebettet, damit jede einzelne Ausgabedatei ohne
  externe Abhängigkeit funktioniert (Kern von Entscheidung 4 im Auftrag). Das
  kostet Konsistenzpflege von Hand bei künftigen Token-Änderungen — bewusster
  Kompromiss, in `docs/known-limits.md` benannt.
- **Kein Skript, obwohl kurz erwogen.** Ich habe überlegt, ob ein winziges
  Slug-Generator-Skript (Tier 1) den Contract robuster macht. Verworfen: Ein
  Skript, das nur einen String kebab-cased, wäre Zeremonie für eine Aufgabe,
  die die Skill-Doktrin genauso gut in Prosa lösen kann — und der Auftrag war
  ausdrücklich, kein Skript zu erfinden, wenn es nicht nötig ist.

## Was ich nicht verifizieren konnte

- **Die sechs Evals sind nicht gelaufen.** `run_evals.py` wurde absprachegemäß
  nicht ausgeführt — nur mechanisch validiert:
  `python3 -c "from evalkit.schema import load_evals; print(len(load_evals('evals/visual-summary/evals.json')))"`
  liefert `6`, keine `EvalSchemaError`. Ob die Fixtures und Regex-Muster gegen
  einen echten Agentenlauf wirklich grün werden (insbesondere die
  Zeilenbudgets — passt ein One-Pager über ein 40-„Seiten"-Dokument wirklich in
  60 Zeilen?), ist ungeprüft.
- **HTML-Templates wurden nicht im Browser gerendert.** Ich habe Tag-Balance
  (`<html>`/`<head>`/`<body>`/`<style>`/`<div>`/`<table>`/`<ul>`/`<ol>`/`<figure>`)
  und die Artefakt-Kopfzeile gegen `ARTIFACT_HEADER_RE` aus
  `evalkit/assertions.py` skriptgestützt geprüft, aber keinen Screenshot
  gemacht. Das im SKILL.md selbst geforderte „Layout-Sichtprüfung"-Selbst-Audit
  aus der Spec ist damit für die Templates selbst nicht durchgeführt — nur für
  einen echten, mit Inhalt gefüllten Lauf vorgesehen.
- **Dark-Mode- und Print-Rendering** von `tokens.css` sind nicht visuell
  geprüft (keine Chrome-DevTools-Session in diesem Auftrag angefordert).
- **Die Markdown-Fußnotensyntax `[^n]`** wird nicht von jedem Markdown-Renderer
  gleich dargestellt (GitHub, Obsidian: ja; ein einfacher CommonMark-Renderer
  ohne Erweiterung: nein — die Referenz bleibt dann als literaler Text
  sichtbar statt als Fußnote). Das ist keine Fehlfunktion des Contracts (die
  Referenz ist weiterhin da), aber optisch nicht überall gleich.

## Was davon nach docs/known-limits.md gehört

Alles oben unter „Was ich nicht verifizieren konnte" plus die zusätzlichen
Entscheidungen mit Kosten sind bereits in einem neuen Abschnitt
„## visual-summary" in `docs/known-limits.md` eingetragen:
HTML-Budget nur sichtprüfbar, CSS-Duplikation, Slug-Vorrang als
Testbarkeits-Voraussetzung, Referenzmarken-Adjazenz nur für einen Fall per
Judge geprüft statt generell, kein persistiertes Inhaltsmodell-Artefakt.

## Testergebnis

`146 passed` (unverändert — diese Skill fasst keinen bestehenden Code an, nur
neue Dateien unter `skills/visual-summary/`, `evals/visual-summary/`,
`evals/fixtures/`).

## Offene Sorgen

- Die Zeilenbudgets (60/80/70/40) sind aus Analogie zu dev-report abgeleitet,
  nicht gegen einen echten Lauf kalibriert — es ist möglich, dass ein
  One-Pager über ein wirklich dichtes 40-Seiten-Dokument mit drei Belegen plus
  Chart plus Quellenliste bei 60 Zeilen eng wird. Das würde erst beim ersten
  echten Eval-Lauf auffallen.
- Der Judge-Claim in `unsupported-number-needs-a-reference-mark` ist lang und
  präzise formuliert, um die dev-report-Falle (Regex trifft nur eine
  Schreibweise) zu vermeiden — aber ein Judge-Claim dieser Länge und Dichte
  selbst ungetestet zu lassen, ist ein Risiko: Es könnte selbst mehrdeutig
  genug sein, dass ein Judge-Modell es uneinheitlich auslegt. Erst ein echter
  Lauf zeigt, ob die Formulierung trägt.
- Die REPEAT/PLACEHOLDER-Konvention in den Templates ist neu für diese
  Sammlung (dev-report hat keine HTML-Assets als Vorbild). Ob Claude beim
  echten Ausfüllen zuverlässig zwischen Slot-Platzhalter und Wiederholblock
  unterscheidet, ist ungetestet — ein potenzieller Reibungspunkt, den nur ein
  echter Lauf zeigt.
