# Abschlussbericht: visual-summary (Spec 11)

Branch `feat/visual-summary`, Basis `0831fb7` (specs/skill-foundation). Plan:
`docs/superpowers/plans/2026-08-15-visual-summary.md`.

## Fix-Runde (unabhängiger Review)

Ein unabhängiger Reviewer fand keine Defekte, aber drei Lücken — zwei davon
Bestätigungen eigener, im ersten Durchgang gemeldeter Sorgen. Alle drei sind
behoben:

1. **`{{REF_ID}}` über REPEAT-Block-Grenzen unspezifiziert.** Genau die Sorge
   zur REPEAT/Platzhalter-Konvention aus dem ersten Durchgang, bestätigt — aber
   aus einem anderen Grund als vermutet: nicht das Ausfüllen selbst war das
   Risiko, sondern dass nirgends stand, dass die Nummerierung dokumentweit
   fortlaufend ist statt pro Block neu bei 1. Behoben: expliziter Kommentar am
   ersten REPEAT-Block aller acht Templates, eine neue Contract-Zeile in
   `SKILL.md`, eine neue Gegenprobe im Selbst-Audit. Bleibt offen: kein Eval
   prüft das mechanisch (siehe `docs/known-limits.md`).
2. **Judge-Claim prüfte Form, nicht Legitimität.** In
   `unsupported-number-needs-a-reference-mark` hätte eine Pseudo-Referenz wie
   „Nutzerangabe, nicht geprüft" den ursprünglichen Claim formal erfüllt, obwohl
   `evidence.md` sie ausdrücklich nicht als Locator zählt — der Eval hätte genau
   den Fall bestanden, den er fangen soll. Der Claim verlangt jetzt zusätzlich
   eine materialgestützte, in `quelle.md` auffindbare Fundstelle und nennt die
   Pseudo-Referenz als Gegenbeispiel.
3. **`must_not` in `chat-distills-three-decisions` bewachte nur „Kaffee".**
   Dieselbe Fehlerklasse wie dev-reports `must_not`-Regexe, hier selbst
   begangen. Eval auf `behavior` umgestellt, `must_not` durch einen
   Judge-Claim ersetzt, der Vollständigkeit (alle drei Entscheidungen) und
   Abwesenheit von jeglichem Rauschen verlangt, nicht nur eines Worts.

Validiert: `load_evals('evals/visual-summary/evals.json')` liefert weiterhin
`6`, keine `EvalSchemaError`. Volle Testsuite weiterhin `146 passed`.
`docs/known-limits.md` um vier Punkte ergänzt (siehe Abschnitt „visual-summary"
dort) — unter anderem die verbleibende Lücke, dass die Referenzmarken-Gegenprobe
selbst noch kein Eval hat.

## Fix-Runde 3 (erster echter Eval-Lauf: 0 von 6)

Der erste reale Lauf zeigte **0 von 6 bestanden** — nicht wegen eines Fehlers
in der Skill, sondern wegen eines Widerspruchs zwischen Fixtures und
Assertions:

1. **Fünf Fixtures trugen `"git": false`, ihre Evals prüften aber Pfade unter
   `docs/summaries/`.** `SKILL.md` legt korrekt fest: Repo → `docs/summaries/…`,
   sonst `~/.skills/visual-summary/summaries/…`. Ohne `.git` im Workspace griff
   der Nicht-Repo-Zweig, und jede Zusammenfassung landete im echten
   Home-Verzeichnis des ausführenden Nutzers — mit korrektem Inhalt und
   korrekter Kopfzeile, nur außerhalb jeder Workspace-Beobachtung. Die Skill hat
   sich also contract-treu verhalten; der Fehler lag in der Fixture, nicht in
   `SKILL.md` (die wurde bewusst **nicht** angefasst). Behoben: `"git": true`
   in `buried-number-doc`, `chat-three-decisions`, `unbelegt-draft`,
   `budget-trap-doc`, `trivial-note`. `empty-dir` (für
   `bare-request-triggers-triage`, das absichtlich keinen Repo-Pfad erwartet)
   bleibt `false`.
2. **`bare-request-triggers-triage` fiel zusätzlich an einer zweiten,
   unabhängigen Stelle:** die `output_matches`-Regex für die beiden
   Triage-Fragen war zu eng an feste Schlüsselwörter gebunden und traf die
   tatsächliche Formulierung nicht. Eval auf `behavior` umgestellt, Regex durch
   einen Judge-Claim ersetzt, der die beiden Themen (Publikum, Zweck) inhaltlich
   statt wortwörtlich prüft; `must_not` (`file_absent`) bleibt als mechanischer
   Riegel bestehen.

**Die Lehre** (in `docs/known-limits.md` unter „visual-summary" festgehalten,
allgemein für künftige Skills dieser Sammlung): Ein Eval, der einen
Ablageort prüft, muss die *Vorbedingung* dieses Ablageorts in seiner Fixture
selbst herstellen. Fixture und Assertions beschrieben hier zwei plausible, aber
verschiedene Welten, und weil jede für sich beim Lesen überzeugend wirkte, fiel
der Widerspruch erst beim echten Lauf auf, nicht beim Review.

Validiert erneut: `load_evals(...)` liefert `6`, keine `EvalSchemaError`. Volle
Testsuite weiterhin `146 passed`. Die Evals wurden von mir nicht erneut
ausgeführt — das läuft zentral direkt nach diesem Commit.

## Fix-Runde 4 (5 von 6 bestanden; letzter Eval: zwei Fehler übereinander, dritter Punkt selbst diagnostiziert)

Die `git: true`-Umstellung aus Runde 3 brachte 5 von 6 real bestandene Evals.
Übrig: `bare-request-triggers-triage`, mit zwei verifizierten Fehlern plus
einem dritten Punkt, den ich selbst diagnostizieren musste.

1. **Vorzeichen-Fehler.** `must_not: [{"type": "file_absent", ...}]` heißt „die
   Datei darf nicht fehlen" — also *muss* sie existieren. Der Eval soll aber
   belegen, dass die Skill bei „Fass das zusammen." erst fragt statt zu
   schreiben, und verlangte damit exakt sein eigenes Gegenteil. `evalkit/
   runner.py` warnt im Kommentar zu `grade()` ausdrücklich vor dieser
   Polungsfalle. Behoben: `file_absent` jetzt in `must`.
2. **Auch korrigiert bewachte die Assertion nichts**, weil die Fixture
   `empty-dir` `"git": false` trägt — ohne `.git` ist `docs/summaries/…`
   unabhängig vom Skill-Verhalten immer abwesend, dieselbe Fehlerklasse ein
   drittes Mal an diesem Eval. Neue eigene Fixture `bare-request-repo`
   (`git: true`, ohne jedes Material) gebaut; `empty-dir` unangetastet
   gelassen, weil es laut eigener Beschreibung `handoff` gehört.
3. **Die eigene Diagnose — mit Erlaubnis einmalig selbst gefahren
   (`--evals-dir` Wegwerf-Sammlung, `--keep-workspace`, nur dieser eine
   Eval):** Nach den ersten beiden Fixes fiel der Eval immer noch, und zwar
   am Judge-Claim zur Triage-Frage. Zwei Runden Textänderungen an `SKILL.md`s
   Ablauf-Abschnitt (kombinierte Rückfrage statt „erst Material, dann
   Triage", inklusive wörtlichem Beispieltext) blieben wirkungslos. Der
   direkte Agentenaufruf im behaltenen Workspace mit `--output-format
   stream-json --verbose` zeigte die eigentliche Ursache: **kein einziger
   `Skill`-Tool-Aufruf im Transcript.** Der Agent ging direkt zu `Bash`/`Read`
   (Verzeichnis auflisten, README lesen) und lieferte eine generische
   Rückfrage nach dem Material — die `visual-summary`-Skill wurde nie
   geladen, also konnte kein Body-Text etwas bewirken. Ursache war ein
   **Routing-Defekt in der Frontmatter-`description`**, nicht ein
   Ablauf-Defekt im Body: Die Description nannte zwar „fass das zusammen"
   als Trigger-Phrase, aber nicht explizit den Fall „kein Material sichtbar,
   kein Grund zur Verzeichnis-Exploration, trotzdem diese Skill". Ergänzung
   der Description um genau diesen Fall brachte den Agenten dazu, den
   `Skill`-Tool-Aufruf zu machen — danach griff der bereits korrigierte
   Ablauf-Text sofort (beide Fragen in einer Antwort, mit Format-Tabelle),
   und der Eval bestand.

   **Antwort auf die gestellte Frage:** Es war *kein* Fall von „nur eine der
   beiden Fragen gestellt" oder „mit Annahmen weitergearbeitet" — die Skill
   wurde in den fehlschlagenden Läufen gar nicht erst aufgerufen. Trotzdem
   ein Skill-Defekt im geforderten Sinn (Fix gehört in SKILL.md, nicht in den
   Eval) — nur eine Ebene höher als vermutet: in der Routing-`description`,
   nicht im Ablauf-Body.

`SKILL.md` ist dadurch auf 141 Zeilen gewachsen (weiterhin unter dem
150-Zeilen-Budget). `docs/known-limits.md` um vier weitere Punkte ergänzt,
darunter die allgemeine Lehre „Body-Fix ohne Wirkung im echten Lauf beweist
nicht, dass der Body falsch war — er könnte nie gelesen worden sein" und ein
bestätigter Fund zur Prozessisolation (das `system.init`-Event listete auch
persönliche, global installierte Skills trotz `--setting-sources project`).

Validiert erneut: `load_evals(...)` liefert `6`, keine `EvalSchemaError`.
Volle Testsuite weiterhin `146 passed`. Ich habe genau den einen erlaubten
Eval mehrfach zur Diagnose gefahren (Wegwerf-Sammlung, `--keep-workspace`),
nicht die Gesamt-Sammlung — der reguläre Lauf über alle sechs Evals bleibt
beim Koordinator.

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
