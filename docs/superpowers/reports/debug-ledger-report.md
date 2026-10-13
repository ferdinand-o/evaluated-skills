# Bericht: Skill `debug-ledger`

Branch `feat/debug-ledger`, Basis `0831fb7` (Spec 00 §-konform, `specs/skill-foundation`).
Plan: `docs/superpowers/plans/2026-08-16-debug-ledger.md`. Spec: `specs/Spec 01 – systematic-debugging.md`.

Zwei Runden: Erstimplementierung, dann eine Fix-Runde nach unabhängigem Review
(vier Defekte, vier Lücken, eine Harness-Erweiterung). Dieser Bericht beschreibt
den Endstand; die Fix-Runde steht in einem eigenen Abschnitt, weil sie die
wichtigeren Korrekturen enthält.

## Was gebaut wurde (Endstand)

```
skills/debug-ledger/
├── SKILL.md                          (114 Zeilen)
├── references/
│   ├── ledger-schema.md              (Feld-Definitionen, Testevidenz-Kriterien, ausgefülltes Beispiel)
│   ├── tooling-python.md             (debugpy headless, pytest -x --pdb, faulthandler)
│   ├── tooling-node.md               (node --inspect-brk, Vitest-Debugging)
│   └── escalation.md                 (Mini→Voll-Signale, 3-Fehlversuche-Regel, MIT-Attribution)
├── assets/
│   ├── ledger-template.md            (Mini- + Voll-Schema-Vorlage, von new_ledger.py geladen)
│   └── hooks/check-ledger.json       (G3-Vorlage, nie automatisch installiert)
└── scripts/                          (alle Tier 1: Python-Stdlib)
    ├── new_ledger.py                 (anlegen / eskalieren / auflösen)
    ├── check_ledger.py               (Pflichtfeld- und Hypothesen-Contract, plus --staged für den Hook)
    └── bisect_run.py                 (kapselt git bisect run um ein Repro-Kommando, mit Endpunkt-Verifikation)

evals/debug-ledger/evals.json         (4 Evals: 3 contract, 1 behavior)
evals/fixtures/{masking-fix,typo-bug,env-var-layers,archived-cause}/

tests/test_debug_ledger_new_ledger.py        (25 Tests)
tests/test_debug_ledger_check_ledger.py      (32 Testfunktionen, davon mehrere parametrisiert)
tests/test_debug_ledger_bisect_run.py        (15 Tests)
tests/test_debug_ledger_dev_report_wiring.py (2 Tests, Cross-Skill-Verdrahtung)
```

Testlauf: **237 von 237 grün** (146 Baseline + 86 debug-ledger-eigene + 5 aus der
übernommenen Glob-Erweiterung in `evalkit`). Keine Regression.

## Fix-Runde (nach unabhängigem Review)

Der Reviewer hat vier Defekte (drei davon empirisch reproduziert) und vier
Lücken gefunden, plus die Ankündigung, dass die von mir gemeldete
Harness-Grenze (kein Glob-Primitiv) inzwischen behoben ist. Alle vier Defekte
und alle vier Lücken wurden bearbeitet — drei Lücken vollständig behoben, eine
bewusst nur teilweise mit dokumentierter Begründung.

### Defekt 1 (schwerster Fund): Hypothesen-Contract ließ sich mit Füllwörtern umgehen

`check_ledger.py` prüfte nur „nicht leer, nicht der exakte Platzhalter" —
eine Zeile `Vermutlich ein Cache-Problem | - | - | Unklar` plus geratener Root
Cause und Fix bestand die Prüfung (`OK`, Exit 0). Behoben: Eine Zeile zählt
jetzt nur als getestet, wenn Test/Ergebnis echten Inhalt tragen (Mindestlänge 8
Zeichen, Füllwort-Denyliste, mindestens ein Buchstabe) **und** Verdict aus der
geschlossenen Menge `Bestätigt`/`Verworfen` stammt. `references/ledger-schema.md`
dokumentiert dieselbe Anforderung, damit Vorschrift und Prüfung übereinstimmen.
Reviewer-Fall als Regressionstest abgedeckt
(`test_check_flags_fix_backed_only_by_filler_hypothesis`), Gegenrichtung
ebenfalls (`test_full_mode_fix_with_genuinely_tested_hypothesis_is_still_clean`).
Verbleibende, dokumentierte Grenze: Eine Denyliste ist selbst spröde — ein Agent
könnte plausibel klingende, aber erfundene Test/Ergebnis-Sätze schreiben und
`Bestätigt` wählen. Nur ein Judge könnte echte Testevidenz von einer gut
formulierten Erfindung unterscheiden; das ist mit den G2-Mitteln von
`check_ledger.py` nicht erreichbar und war es vor dem Fix noch weniger.

### Defekt 2: `bisect_run.py` meldete einen falschen Culprit mit voller Zuversicht

Kein Check, ob das Repro-Kommando am bekannt guten Commit wirklich besteht.
`git bisect run false` fand „erfolgreich" einen Commit, obwohl das Kommando nie
zwischen gut und schlecht unterschied. Behoben: `verify_endpoints()` prüft vor
der eigentlichen Bisektion beide Enden (Kommando muss am guten Commit Exit 0,
am schlechten Exit ≠ 0 liefern) und bricht mit benannter Ursache ab, sonst.
Reviewer-Fall reproduziert und als Regressionstest abgedeckt
(`test_run_bisect_raises_instead_of_reporting_a_fake_culprit`, mit `false` als
Kommando — exakt der Reviewer-Repro), Gegenrichtung ebenfalls (ein echt
unterscheidendes Kommando darf nicht scheitern).

### Defekt 3: `bisect_run.py` verwarf eine laufende Bisektion kommentarlos

`_reset_quietly()` lief unbedingt vor jedem Start und hätte den Fortschritt
eines Nutzers, der selbst mitten in einer Bisektion steckt, stillschweigend
verworfen. Behoben: `bisect_in_progress()` erkennt eine aktive Sitzung über
`git bisect log` (Exit 0 = aktiv, empirisch geprüft, nicht angenommen) und
`main()` bricht sichtbar ab (Exit 3, Meldung auf stderr), ohne die fremde
Sitzung anzutasten. Getestet inklusive der entscheidenden Prüfung: Nach dem
Abbruch existiert die Nutzer-Sitzung noch (`test_main_aborts_visibly_when_bisect_already_in_progress`).

### Defekt 4: Description widersprach dem eigenen „ausnahmslos"-Contract

„…and a plausible-sounding fix is not enough" schloss den Pflichtfall (jeder
Bug bekommt ein Mini-Ledger, auch ein Tippfehler) implizit aus der eigenen
Trigger-Bedingung aus — während `superpowers:systematic-debugging`s
„any bug… before proposing fixes" diesen Fall uneingeschränkt trifft. Behoben:
Description trennt jetzt ausschließlich über das Artefakt (persistiertes,
archiviertes, mechanisch geprüftes Ledger), schließt „any bug… including a
one-line typo fix" explizit ein. Nicht mechanisch nachprüfbar, siehe unten.

### Lücke 1: `must_not`-Regex in Eval 2 konnte korrektes Verhalten fälschlich rot machen

„root cause" im `output_matches`-Muster war generisches Vokabular, das auch bei
einem korrekt im Mini-Modus belassenen Fix beiläufig fällt. Behoben, nicht nur
gepatcht: `output_matches` (prüft die Chat-Antwort) ersetzt durch `file_matches`
direkt am Ledger-Artefakt (`## Hypothesen` darf im File nie auftauchen) — robuster
gegen Wortwahl-Varianz und näher an dem, was die Skill tatsächlich tut.

### Lücke 2: Eval 4 hatte keinen mechanischen Beweis, dass die Skill aktiv wurde

Mit der jetzt verfügbaren Glob-Unterstützung (siehe unten) wurde das für Eval 1
und 3 vollständig gelöst. Für Eval 4 (Fixture bringt bereits eine datierte
Archiv-Datei mit) bleibt es strukturell ungelöst — Begründung im
Evals-Abschnitt unten, dort auch als neue Grenze in `docs/known-limits.md`
festgehalten. Teilweise kompensiert durch eine neue `file_unchanged`-Assertion
auf dem bekannten Archiv-Pfad (gegenprobenverifiziert: Korruption des Archivs
wird erkannt).

### Lücke 3: `artifact_header` prüfte nicht den Skill-Namen im Header

Jede der vier Evals hat jetzt zusätzlich `file_matches` mit dem Muster
`skill:\s*debug-ledger` auf demselben Pfad wie die `artifact_header`-Assertion
— schließt aus, dass ein formkorrekter Header einer fremden Skill den Eval
fälschlich bestehen lässt.

### Lücke 4: `INDEX.md`-Kopfzeile log über ihre Herkunft beim `--symptom`-Bootstrap

`bootstrap_index()` trug fest ein `--resolve`-Template mit literalen
Platzhaltern (`<ledger>`, `<ursache>`), auch wenn der Bootstrap durch einen
`--symptom`-Aufruf ausgelöst wurde — nicht re-eintippbar, verstößt gegen die
eigene Kopf-Regel. Behoben: `generated` wird jetzt vom jeweiligen Aufrufer
(`action_new`/`action_resolve`) aus den echten Argumenten gebaut und
durchgereicht. Beide Richtungen getestet.

### Harness-Erweiterung: Glob-Unterstützung übernommen

`evalkit/assertions.py` und `evalkit/schema.py` (samt zugehöriger Tests) von
`feat/dev-report` (Commit `a1417b3`) übernommen — geprüft per Diff, dass nur
die Glob-Änderung mitkam, keine unabhängigen Änderungen aus dieser Schwester-Skill.
Damit heben Eval 1 (`masking-fix-finds-real-root-cause`) und Eval 3
(`env-var-layers-instruments-boundaries`) von `class: behavior` auf
`class: contract` — beide Fixtures haben kein vorab vorhandenes
`docs/debugging/`, der Glob `docs/debugging/[0-9]*.md` löst also eindeutig auf
die eine neu angelegte Datei auf. Für jede der beiden Evals per Gegenprobe
verifiziert: ein simuliertes „gutes" Ledger (escalated, echte Testevidenz,
richtige Ursache benannt) besteht alle `must`-Assertions; ein simuliertes
„schlechtes" Ledger (Mini-Modus, keine Untersuchung) lässt exakt die
inhaltlichen `must`-Assertions durchfallen, nicht die strukturellen.
`docs/known-limits.md`s Eintrag zum fehlenden Glob-Primitiv wurde als behoben
markiert; eine neue, präzisere Restlücke ergänzt (siehe nächster Abschnitt).

## Die vier Evals: Endstand nach der Fix-Runde

**3 von 4 Evals sind jetzt `class: contract`** (`masking-fix-finds-real-root-cause`,
`typo-bug-stays-mini`, `env-var-layers-instruments-boundaries`) — mechanisch,
ohne Judge, günstig genug fürs Routine-Gate. Alle mechanischen Assertions per
Gegenprobe verifiziert: Fixture real vorbereitet (`evalkit.workspace.prepare()`),
`new_ledger.py`/`--escalate` real aufgerufen, Ledger-Inhalt einmal „gut" (echte
Untersuchung) und einmal „schlecht" (nur Mini-Modus bzw. geratener Inhalt)
simuliert, `evalkit.assertions.check()` direkt gegen beide Zustände geprüft.
Ergebnis kippt in allen drei Fällen korrekt.

**Eval 4 (`archive-hit-tested-first`) bleibt bewusst `class: behavior`.**
Grund, den ich erst bei der Umsetzung der Glob-Unterstützung entdeckt habe:
`evalkit.assertions.resolve_target()` wählt bei mehreren Glob-Treffern den
*alphabetisch ersten*, nicht den neuesten. Die `archived-cause`-Fixture bringt
mit `docs/debugging/2026-07-01-login-haengt.md` bereits eine datierte
Ledger-Datei mit; ein vom Agenten neu angelegtes Ledger trägt zwangsläufig ein
späteres Datum und sortiert danach. `file_matches`/`artifact_header` auf
`docs/debugging/[0-9]*.md` würden deshalb strukturell **immer** die alte
Archiv-Datei lesen, nie die neue — eine mechanische Content-Prüfung der neuen
Datei ist mit diesem Fixture-Design nicht möglich, ohne entweder das
Fixture-Layout zu verbiegen (Archiv in einen Unterordner, den es sonst nicht
gibt) oder ein Datum hart zu codieren (bricht, sobald `run_evals.py` an einem
anderen Tag läuft als angenommen). Das ist als neue Grenze in
`docs/known-limits.md` festgehalten. Kompensiert, aber nicht ersetzt, durch:
`file_unchanged` auf dem bekannten Archiv-Pfad (neu, gegenprobenverifiziert)
und die um die Skill-Namen-Prüfung erweiterten `INDEX.md`-Checks. Der
eigentliche Phase-0-Treffer (wurde der archivierte Fall zuerst getestet)
bleibt ein `judge`-Claim.

**Jede Assertion wurde gegen die Frage geprüft:** „Könnte eine generische
Debugging-Skill ohne Ledger-Artefakt das auch erfüllen?" Alle mechanischen
Checks beziehen sich auf Struktur oder Inhalt einer Ledger-Datei unter
`docs/debugging/` mit ihrer spezifischen Kopfzeile (`skill: debug-ledger`) —
nichts prüft nur „wurde der Bug gefunden" als Chat-Aussage.

**Bekannte, dokumentierte Restgrenze der jetzt mechanischen Content-Checks
(Eval 1 und 3):** Sie sind Keyword-Regex, keine Judge-Bewertung — derselbe
Kompromiss wie bei `dev-report`s `release-notes-filter-internals`. Ein Agent,
der die richtige Ursache mit stark abweichendem Vokabular beschreibt (z. B.
„der Zustand wird zweifach angewendet" statt „zweimal verarbeitet"), könnte den
Eval fälschlich verfehlen; ein Agent, der zufällig genug Schlüsselwörter trifft,
ohne die Ursache wirklich verstanden zu haben, könnte ihn fälschlich bestehen.
Beide Richtungen sind eine inhärente Grenze des Ansatzes (`docs/known-limits.md`
nennt dieselbe Klasse von Grenze bereits für `output_matches`), kein
Implementierungsfehler dieser Skill — aber deutlich enger als vorher, weil jede
Eval mehrere unabhängige Muster gleichzeitig verlangt (Kombination aus
Eskalation + getesteter Hypothese + Nennung des richtigen Dateinamens/der
richtigen Variable + Nennung des richtigen Mechanismus).

**Gegenproben durchgeführt** (mechanisch, ohne `run_evals.py` oder LLM-Aufruf):
Für alle vier Fixtures `evalkit.workspace.prepare()` real ausgeführt. Für Eval
1, 2, 3 je ein „gutes" und ein „schlechtes" Ledger real erzeugt/manipuliert und
gegen alle `must`/`must_not`-Assertions geprüft — Ergebnis kippt in jedem Fall
korrekt. Für Eval 4 die mechanischen Assertions gegen die unberührte Fixture
und gegen eine simulierte Archiv-Korruption geprüft. Schema-Validierung über
`python3 -c "from evalkit.schema import load_evals; print(len(load_evals(...)))"`
→ 4 Evals, keine `EvalSchemaError`.
**Nicht verifiziert:** die verbliebenen `judge`-Claims in Eval 4 selbst — das
erfordert einen echten LLM-Judge-Lauf, den ich laut Auftrag nicht starte
(`run_evals.py` bleibt unausgeführt).

## R1–R3 aus dem Auftrag: Status

- **R1 (Verzeichnisname):** `skills/debug-ledger/`, `evals/debug-ledger/` — umgesetzt, vom Reviewer bestätigt.
- **R2 (INDEX.md flach, Warnung ab 50):** `new_ledger.py --resolve` zählt Einträge
  nach jedem Append und warnt sichtbar ab 50, ohne umzugliedern oder zu prunen.
  Vom Reviewer bestätigt.
- **R3 (Hook nie automatisch installiert):** `assets/hooks/check-ledger.json`
  wird von keinem Skript referenziert oder ausgeführt. Vom Reviewer bestätigt,
  inklusive der G2-Sprachregelung.

## Zusätzliche Entscheidungen (nicht im Auftrag vorgegeben)

1. **`new_ledger.py` hat drei Aktionen über Flags, keine Subcommands**
   (`--symptom`/`--escalate`/`--resolve`), näher am Beispiel aus
   `docs/artifact-header.md`. Die tatsächliche Kopfzeile nutzt den vollen Pfad
   `skills/debug-ledger/scripts/new_ledger.py`, konsistent mit `dev-report`s
   Konvention — das verkürzte Beispiel in `docs/artifact-header.md` als
   illustrativ behandelt, nicht als Pfadvorschrift.
2. **`docs/debugging/INDEX.md` trägt selbst die Artefakt-Kopfzeile**, exakt wie
   `dev-report/scripts/collect.py`s `HARVEST_SOURCES` es erwartet. Per
   Integrationstest verifiziert.
3. **`check_ledger.py --staged`** statt einer vierten Skriptdatei für den Hook
   — bleibt bei den drei in Spec 01 genannten Skripten.
4. **Der Hook-Befehl in `assets/hooks/check-ledger.json` wurde funktional
   gegengeprüft** (simulierter `PreToolUse`-Stdin-Payload gegen einen echten
   Workspace mit Contract-Verstoß: Exit 2, Meldung auf stderr; ohne Verstoß:
   Exit 0). Nicht verifiziert: ob Claude Code den Tool-Aufruf wirklich in genau
   diesem JSON-auf-stdin-Format an `PreToolUse`-Hooks reicht — G3, nutzerinstalliert,
   ein falsches Format würde beim ersten `git commit` sichtbar auffallen.
5. **`bisect_run.py` verifiziert jetzt beide Endpunkte vor der Bisektion** und
   erkennt eine bereits laufende fremde Sitzung, statt sie zu verwerfen (siehe
   Fix-Runde, Defekte 2 und 3).
6. **Platzhalter-Konvention `_(noch offen)_`** plus, seit der Fix-Runde,
   Mindestlänge/Füllwort-Denyliste/geschlossene Verdict-Menge — die Grundlage,
   auf der `check_ledger.py` echte Testevidenz von Füllwörtern unterscheidet.

## Description-Schärfung gegen `superpowers:systematic-debugging`

Nach dem Fix an Defekt 4 trennt die Description ausschließlich über das
Artefakt, nicht mehr über eine engere (und mit dem eigenen Contract
kollidierende) Trigger-Bedingung.

**Wie sicher ich mir bin, dass sie gewinnt: mittel, nicht verifiziert — und der
Reviewer hat die vorherige Einschätzung zu Recht als "eher zu optimistisch"
korrigiert.** Ich habe weiterhin keinen Zugriff auf den tatsächlichen
Trigger-/Routing-Mechanismus des Eval-Agenten. Der behobene Defekt 4 war aber
ein selbst verursachtes, klar behebbares Risiko (die Description widersprach
dem eigenen Contract) — nach dem Fix bleibt nur noch die generische,
unvermeidliche Unsicherheit über Routing-Verhalten, nicht mehr ein zusätzlicher,
selbstgemachter Nachteil gegenüber der Konkurrenz-Description.

## Was ich nicht verifizieren konnte (Zusammenfassung)

1. Ob die verbliebenen `judge`-Claims in Eval 4 bei einem echten LLM-Lauf so
   urteilen wie beabsichtigt.
2. Ob die Description tatsächlich gegen `superpowers:systematic-debugging`
   gewinnt — offene, bewusst unsichere Einschätzung, s. o.
3. Ob Claude Code `PreToolUse`-Hooks exakt im angenommenen JSON-auf-stdin-Format
   aufruft (G3, nutzerinstalliert, dokumentiert als Annahme).
4. Ob ein echter Agent bei Eval 1/3 tatsächlich genug der jetzt verlangten
   Schlüsselwort-Kombination trifft, um korrektes Verhalten nicht fälschlich
   als Fehlschlag zu werten (Restrisiko der neuen Keyword-Regex-Checks, s. o.).

## Ergänzungen in `docs/known-limits.md`

1. Ursprünglicher Eintrag zum fehlenden Glob-Primitiv als **behoben** markiert
   (Commit `a1417b3`, übernommen in `e124236`).
2. Neue, präzisere Restlücke ergänzt: `resolve_target()` wählt bei mehreren
   Glob-Treffern den alphabetisch ersten, nicht den neuesten — trifft Fixtures,
   die bereits eine Datei mitbringen, deren Name vor jedem neu erzeugten Namen
   sortiert (konkreter Fall: `archive-hit-tested-first`). Commit `2e8f9ca`.
