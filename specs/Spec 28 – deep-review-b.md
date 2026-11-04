# Spec 28: deep-review B — auf jeder gemessenen Eingabe mindestens so gut wie `/code-review`, besser, wo der Bereich groß ist oder der Vertrag außerhalb liegt

Skill-Spezifikation · Zyklus 28 · Entscheidung: deep-review bleibt `/code-review` je Paket mit Gegenstellen-Block und Audit (Spec 26); Abschnitt B schließt die Lücken aus der Abnahme vom 2026-11-03 — Kosten der Hauptschleife, Block und Auftrag untrennbar, Spannen in großen Dateien, Pfade, Sprachen ohne Sammler, Präzision — und misst vor dem Bau, welche Stufe und welche Übergabe die Treffer tragen · Abgeglichen mit Spec 00, Spec 26 und Spec 27 · Überarbeitet nach unabhängigem Review (2026-11-04, Opus: Pfad von Eval 10 auf die Units der Fixture, Marke als Auskunft statt Beleg und Auftrag mit Block in einer Datei, Basis `dr-seeded` 0,37 USD, Spannen als Zeilenbereiche des Ziels mit festem Rückfall und drei Paketen für 1.300 Zeilen, `PATH_SPLIT_AT` über dem Messpunkt 5.308, Kosten der Hauptschleife aus den Läufen zerlegt, Routing-Regel ohne Widerspruch zur Abgrenzung, „mehr" nur auf großen Diffs, Stufenregel für den Fall ohne Treffer, Budget mit bedingtem Lauf, Präzision nur auf Python ausgeführt, Urteile mit `bestätigt`/`widerlegt`/`unklar` und Feld `evidence`, Vermerk „laut fix-task" unter `## Einordnung`, `match.py`-Fix gestrichen, Eval 7 in Eval 1 aufgegangen, Muster geschärft, stille Entscheidungen als Annahmen, Umbau der bestehenden Tests genannt)

## Problem

Der Nutzer will deep-review „für alles gut (besser als code-review)" (2026-11-04). Gemessen
ist (`docs/superpowers/reports/deep-review-report.md`, Abschnitte „Nachmessung auf großen
Repos", „Abnahme (Task 16)" und die Basislinie auf `dr-seeded`):

| Eingabe | `/code-review` | deep-review | Lücke |
| --- | --- | --- | --- |
| großer Diff Python (`py-diff`, 4.097 Zeilen) | 4,5/6 im Mittel, P2 in keinem Lauf, 1,06 USD | 6/6 mit P2 und P4, ein Lauf, 5,87 USD | Kosten 5,5×, ein Lauf |
| großer Diff Delphi (`dl-diff`, 1.988 Zeilen) | 5,0/6, 2,33 USD | 6/6, ein Lauf, 7,43 USD | Kosten 3,2×; Block nicht ausdrücklich übergeben |
| kleiner Diff (`dr-seeded`, rund 400 Zeilen) | 5/5 in drei Läufen, 0,29–0,45 USD, im Mittel 0,37 | nicht gemessen | `/code-review` am Anschlag |
| kleiner Diff mit Vertrag in einer Nachbardatei (`dr-contract`, `dr-delphi`) | nicht gemessen | Fund gemeldet, 0,67 und 0,54 USD | Basislinie fehlt |
| Pfad ohne Diff (`dl-path`, 5.308 Zeilen) | 6/6 in drei Läufen, 1,29 USD | nimmt keinen Pfad | Eingabe fehlt |
| andere Sprachen als Python und Delphi | ungemessen | teilt, sammelt keine Gegenstellen | Block fehlt |

Die Kosten von deep-review liegen nicht nur in den Reviews. Eine Zerlegung der beiden
Abnahme-Läufe (Spec-Review vom 2026-11-04, Preismodell an `py-diff-cr-1` angepasst, trifft
die Gesamtkosten auf ±5 %; eine Schätzung, keine Abrechnung) ergibt für die Hauptschleife
rund 2,17 USD auf `py-diff` und 1,70 USD auf `dl-diff`, für die Pakete rund 3,70 und
5,74 USD. Die Hauptschleife allein liegt auf `py-diff` schon über dem Doppelten der
Basislinie. Ob `total_cost_usd` eines `cr`-Laufs die Unteragenten von `/code-review` enthält,
ist ungeprüft; die Faktoren 5,5× und 3,2× stehen unter diesem Vorbehalt.

Dazu aus dem Bau (`docs/known-limits.md`, Abschnitt deep-review): Eine Datei wird nie geteilt
(ein neues Modul mit 5.000 Zeilen ist ein Paket); dass der Block den Reviewer erreicht, ist
Auskunft des Hauptagenten, und Auftrag und Block sind zwei Dinge, von denen der Hauptagent
eines weglassen kann; den Bericht schreibt der Hauptagent, und `audit` liest ihn mit
regulären Ausdrücken; die Gegenstellen werden zweimal gesammelt. Ob die Treffer vom Block oder
vom Schneiden kommen, ist auf den großen Repos nicht getrennt (`drnc` entfiel), und die
Präzision ist ungemessen.

Was „besser" heißen kann, setzt die Messung: Wo `/code-review` alle eingebauten Fehler findet
(`dr-seeded`, `dl-path`), kann deep-review bei den Treffern nur gleichziehen; dort heißt besser:
gleiche Treffer, Abdeckungsnachweis, wenig Mehrkosten. Mehrtreffer sind nur auf den großen
Diffs belegt (`py-diff`, `dl-diff`). `dr-contract` und `dr-delphi` haben je einen Einbau in 61
bzw. 114 Zeilen Basis; der Report sagt selbst, dass Fixtures dieser Größe „außerhalb des
Gelesenen" nicht erzeugen. Fokus `quality`, Fokus `security` und Sprachen ohne Fixture misst
auch dieser Abschnitt nicht; „für alles" gilt nur für die Eingaben der Abnahme B.

## Constraints

Wie Spec 26: portables Frontmatter, Tier 1 mit `scripts/review_kit.py` (nur Stdlib, nie Import
des Zielcodes), Ablage unter `.skills/cache/deep-review/<lauf>/`, Hilfscommits unter
`refs/deep-review/<lauf>/`, Gate-Grade G1 (SKILL.md verlangt) und G2 (`audit` meldet), kein
Hook. Neu gesammelt wird für TypeScript/JavaScript mit einem Text-Scanner wie bei Delphi; für
weitere Sprachen nur Definitionen mit eindeutigem Namen, gekennzeichnet.

Die Reviews führt weiter `/code-review` aus. Es nimmt eine Stufe vor dem Ziel
(`low|medium|high|xhigh|max`); ohne Stufe nimmt es die zuletzt getippte. deep-review nennt
die Stufe künftig in jedem Aufruf ausdrücklich, `max` nur auf ausdrücklichen Wunsch des
Nutzers (Beschreibung von `/code-review`). Welche Stufe die Basislinie `cr` hatte, ist
unbekannt (headless, ohne Stufe).

`SKILL.md` hat 148 von 150 Zeilen. Was neu hineinkommt (Pfad, Paket-Auftrag, `report`,
`verify`), verdrängt Einzelheiten, die nach `references/packets.md` wandern: der Hinweis zu
Git Bash und dem Werkzeugnamen, die Wirkung von `cleanup --stale`, die Lage der Cache-Dateien.

Messbudget (*Annahme*, aus den Kosten der Abnahme vom 2026-11-03 hochgerechnet): Sonde rund
9 USD, dazu bedingt ein zweiter `drnc`-Lauf (rund 6 USD); Abnahme rund 30 USD, wenn das
Kostenziel erreicht ist, bis rund 45 USD, wenn nicht (vier große Läufe zu heutigen Preisen:
26,6 USD). Der Nutzer gibt beide Budgets vor dem jeweiligen Schritt frei.

## Approach

**Eiserne Regel** (unverändert aus Spec 26): *Kein Bericht nennt sich vollständig, solange ein
Paket des Plans kein vom Skript angenommenes Ergebnis hat — und kein Fund eines Pakets fehlt in
`findings.json`.*

**Ziel je Eingabe** (Abnahme B unten): Treffer im Mittel nie unter `/code-review`; auf den
großen Diffs mehr. Kosten: auf großen Diffs höchstens 2× der Basislinie, auf kleinen Diffs und
Pfaden höchstens 1,5× (*Annahme:* gesetzt, nicht gemessen; 1,5× ist der Aufschlag, bei dem ein
Nachweis ohne Mehrtreffer noch lohnt). Präzision: der Anteil `widerlegt` nicht höher als bei
`/code-review`.

**Hebel für die Kosten.** Die Hauptschleife liest keinen Paketblock und keine Ausgabe eines
Reviews mehr: Auftrag und Block liegen in einer Datei, die der Reviewer selbst liest; den
Bericht schreibt das Skript. Die Stufe je Paket setzt die Sonde.

### Skill-Struktur

```
skills/deep-review/
├── SKILL.md                         Ablauf mit Paket-Auftrag, Stufe je Profil, Pfad-Modus, `report`, `verify`; Description nach der Abnahme
├── references/packets.md            Spannen, Pfad-Modus mit eigenen Grenzwerten, Zeile `Reviews:`; dazu aus SKILL.md verdrängte Einzelheiten
├── references/counterparts.md       TypeScript/JavaScript-Sammler, Namens-Rückfall für weitere Sprachen
├── references/review-brief.md       Paket-Auftrag als Datei mit Marke, Rückgabe mit `evidence`, Stufe je Profil, Prüfer-Auftrag für `verify`
├── references/delphi.md             unverändert
├── assets/report-template.md        entfällt; den Bericht schreibt `review_kit.py report`
└── scripts/review_kit.py            Tier 1 — dazu `report`, `verify`, `verdict`; Spannen, Pfad-Modus, Sammler TS/JS und Namens-Rückfall, Gegenstellen einmal gesammelt

docs/superpowers/reports/review-bench/run.sh, README.md   Werkzeug `crb` (ein Review mit Block, Stufe wählbar), `dr` auf Pfaden
skills/subagent-dev/scripts/plan_to_tasks.py   `fix-task` lässt Funde mit Urteil `widerlegt` weg und nennt ihre Zahl
skills/subagent-dev/references/checkpoints.md  `verify` am finalen Prüfpunkt; Vermerk „laut fix-task-… behoben" unter `## Einordnung`
specs/Spec 00 – skill-foundation.md, README.md   Routing nach der Abnahme
docs/known-limits.md, docs/superpowers/reports/deep-review-report.md
evals/deep-review/evals.json         Eval 1 nachgezogen, Evals 7–10 neu
evals/fixtures/dr-bigfile/, dr-ts/   neu
tests/test_deep_review_kit.py, tests/test_subagent_dev_plan_to_tasks.py
.claude/skills/deep-review/, .claude/skills/subagent-dev/   Projekt-Kopien über scripts/sync_skills.py
```

### Ablauf

0. **Sonde vor dem Bau** (einmalig, Report Abschnitt „Sonde B"):
   - Zerlegung der Kosten aus den gespeicherten Läufen (`$BENCH/out/*.json`, kostenlos):
     Hauptschleife gegen Unteragenten, und ob `cr` die Unteragenten mitzählt.
   - `drnc` auf `py-diff`, ein Lauf. Findet er P2 und P4 wie `dr`, läuft ein zweiter `drnc`;
     findet auch der beide, fliegt der Block raus (Spec 26: jede Stufe ohne messbaren
     Unterschied fliegt). Sonst bleibt er.
   - `/code-review` auf `dr-contract` und `dr-delphi`, je zwei Läufe: die fehlende Basislinie.
   - Stufe je Paket: `crb` auf `py-c1` (trägt P2, P4, P5) mit `low`, `medium` und `high`, je
     ein Lauf. Regel: Die billigste Stufe, die P5 und mindestens einen von P2 und P4 findet,
     wird die des Profils `standard`, eine höher die von `checkpoint`. Findet keine Stufe
     einen von P2 und P4, gilt `high` für beide Profile.
   - Übergabe: ein Lauf `/code-review medium` mit einer Marke im Aufruf, Suche nach der Marke
     in den Transkripten seiner Unteragenten; ein Lauf, in dem ein Unteragent (Agent-Werkzeug)
     `/code-review low` startet. Das Ergebnis legt fest, ob Schritt 4 im Hauptkontext bleibt
     oder je Paket einen Unteragenten startet.
1. **Bereich oder Pfad.** Neu: `plan --path <pfad>[,<pfad>…]` statt `--range`. Ein Pfad wird
   wie ein Bereich vom leeren Stand bis zum Ziel behandelt: Hilfscommits mit den Dateien des
   Pfads als neu, analog zum Wurzel-Commit (`packets.md`). Grenzwerte: `PATH_SPLIT_AT = 6000`,
   `PATH_PACKET_SIZE = 3000` Zeilen (*Annahme:* gemessen ist nur `dl-path` mit 5.308 Zeilen in
   einem Review ohne Verlust; die Grenze liegt darüber, damit `dl-path` ein Paket bleibt).
   Gegenstellen sammelt der Pfad-Modus nur für Aufrufe, die den Pfad verlassen. *Annahme:* Der
   Pfad-Modus prüft den Stand am Ziel (Standard `HEAD`), nicht den Arbeitsbaum wie
   `/code-review <pfad>`; weicht der Arbeitsbaum ab, steht der Hinweis `worktree_differs`.
2. **Plan** wie bisher, dazu:
   - Eine Datei mit mehr als `PACKET_SIZE` geänderten Zeilen wird geteilt. Eine Spanne ist ein
     Zeilenbereich der Datei am Ziel. Grenzen an Definitionen der obersten Ebene (Python über
     `ast`, Delphi und TS/JS über den Scanner); fehlt eine Grenze, eine Leerzeile, sonst nach
     genau `PACKET_SIZE` Zeilen. Eine Datei mit 1.300 geänderten Zeilen ergibt so mindestens
     drei Spannen.
   - Ein Paket mit Spanne trägt `spans` (`[{file, lines}]`). Sein `von` ist der Baum des Ziels,
     in dem die Datei außerhalb der Spanne Ziel-Stand und innerhalb Basis-Stand hat (bei einer
     neuen Datei: die Zeilen der Spanne fehlen); `bis` bleibt der Baum des Ziels. Datei-Schlüssel
     für `--since` bleiben je Datei, übernommen wird nur, wenn jede Spanne ein Ergebnis hatte;
     `outside` und `packet_files` zählen die Datei bei jedem ihrer Pakete.
   - `plan` nennt `Reviews: <n> × /code-review <stufe>`, damit der Nutzer die Kosten vor dem
     Lauf sieht. Die Gegenstellen sammelt `plan` einmal und legt sie im Laufordner ab.
3. **Paket-Auftrag.** `counterparts` schreibt je Paket `packets/<id>.prompt.md`: Auftrag aus
   `review-brief.md` (Fassung nach Profil und Fokus), Bereich, Stufe, Block und als letzte Zeile
   `Paket-Marke: dr-<paket>-<6 hex>`; die Marke steht auch in `plan.json` beim Paket. Auftrag
   und Block sind damit eine Datei: Wer den Auftrag weitergibt, gibt den Block mit.
4. **Review je Paket** mit `/code-review <stufe> --max-findings all <von>..<bis>`; der Auftrag
   ist `packets/<id>.prompt.md`, im Hauptkontext als Pfad, den der Reviewer liest, oder als
   ganzer Auftrag eines Unteragenten (Entscheidung der Sonde). Das Ergebnis ist ein Objekt
   `{"marke": …, "findings": […]}`, je Fund optional `evidence` (Befehl und Ausgabe oder
   zitierte Zeilen mit Datei:Zeile). `record` weist ein Ergebnis ohne passende Marke mit Exit 1
   ab; `record --no-block` nimmt es an und vermerkt „ohne Gegenstellen-Block". Die Marke ist
   eine Auskunft, kein Beleg: Sie zeigt nur, dass der Schreiber des Ergebnisses die Datei
   kennt (*Annahme* in den Open questions).
5. **Vereinigen** wie bisher; `merge` liest dazu die Urteile aus `verdicts/`, ein erneutes
   `merge` verliert sie also nicht.
6. **Prüfen** (`plan --verify`; im Profil `checkpoint` Standard). `verify` schreibt je Fund
   ohne `evidence` einen Prüfauftrag `verify/<n>.md` mit Datei, Zeile, Szenario und Commit,
   ohne `summary`. Je Auftrag ein Unteragent (Modell Sonnet), der nur unter
   `verify/<n>/work/` schreibt und Python nur mit `-I` startet. Urteil `bestätigt`,
   `widerlegt` oder `unklar`; `verdict` nimmt es an und weist `widerlegt` ohne Beleg ab (Beleg
   wie `evidence`). `fix-task` lässt `widerlegt` weg und nimmt `bestätigt`, `unklar` und Funde
   ohne Urteil; in `findings.json` und im Bericht bleibt jeder Fund mit Urteil stehen.
7. **Bericht, Audit, Aufräumen.** `report --run <lauf>` schreibt `report.md` mit allen
   datentragenden Zeilen (Kopfzeile, Funde, Abdeckung, Hinweise, Übernommen, Nicht geprüft,
   Ohne Block, Urteile, Stufe, Reviews, Fundzeilen). Der Hauptagent fügt nur einen Abschnitt
   `## Einordnung` an; dort steht auch der Vermerk „laut fix-task-… behoben" (Spec 27). `audit`
   vergleicht alles vor `## Einordnung` mit einer neu erzeugten Fassung statt mit regulären
   Ausdrücken; jede Abweichung ist `report_mismatch`. *Annahme:* `no_block` macht einen Lauf
   nicht unvollständig (alte Läufe haben keine Marke, und der Nutzer darf den Block abwählen);
   `audit` listet die Pakete, der Bericht nennt sie.

Begründung für den Bericht aus dem Skript: Die Hauptschleife spart das Schreiben, und `audit`
vergleicht Text mit Text statt Mustern auf freiem Markdown. Der fehlende Bericht im
`py-diff`-Lauf war ein Fehler im Bench, kein Grund.

### Sammler

| Sprache | sammelt | nicht |
| --- | --- | --- |
| Python, Delphi | wie Spec 26 | — |
| TypeScript, JavaScript (`.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs`) | Definition über `import`/`require` mit relativem Pfad, `throw`-Stellen der Gegenstelle bis `RAISE_DEPTH`, `async`-Gegenstelle bei einem Aufruf ohne `await` | Typinferenz, `node_modules`, Pfad-Aliase aus `tsconfig.json` |
| Java, C#, Go, Rust, C, C++, Kotlin, Swift | Definition mit eindeutigem Namen im Repo, markiert „(Name eindeutig, ohne Sammler)", `throw`/`panic`-Zeilen ihres Rumpfs | Importe, Überladungen, Besitz |
| andere | nichts, „Gegenstellen nicht gesammelt (Sprache)" | — |

### Contract

- `record` meldet ein Ergebnis ohne die Marke seines Pakets mit Exit 1 (G2 auf die Form), außer
  mit `--no-block`; `audit` listet solche Pakete unter `no_block`. Dass der Reviewer den Auftrag
  gelesen hat, verlangt die SKILL.md (G1).
- `report.md` schreibt das Skript; `audit` meldet jede Abweichung vor `## Einordnung`.
- `verdict` weist `widerlegt` ohne Beleg ab; ein Lauf mit `verify: true` ist erst vollständig,
  wenn jeder Prüfauftrag ein Urteil hat.
- Die Stufe je Paket steht im Plan (`level`) und in der Kopfzeile des Berichts.
- Pfad- und Bereichsmodus schreiben dieselben Dateien; `plan.json` trägt `mode` (`range` oder
  `path`). Läufe aus Spec 26 bleiben lesbar: ohne `mode` gilt `range`, ohne `spans` ganze
  Dateien, ohne `marke` `no_block`.

### Abgrenzung

Welche Eingaben deep-review übernimmt, entscheidet die Abnahme B (Regel dort). Die Tabelle
zeigt den Stand vor ihr; die Zeilen mit „nach Abnahme B" ändern sich nur, wenn die Regel es
sagt.

| Anlass | zuständig | nicht |
| --- | --- | --- |
| großen Bereich, Branch oder Prüfpunkt gründlich prüfen | **deep-review** | `/code-review` über alles |
| kleinen Diff oder Pfad mit Nachweis je Paket prüfen | `/code-review`; nach Abnahme B **deep-review** für jede Eingabe, die ihre Schwelle erfüllt | — |
| schneller Blick auf einen kleinen Diff ohne Nachweis | `/code-review` | deep-review |
| Kontext und Soll für einen Diff | **review-context** | deep-review |
| Prüfpunkte planen, Fixes dispatchen | **subagent-dev** | deep-review |
| bestätigter Fund mit unklarer Ursache | **debug-ledger** | deep-review |
| Sicherheitsaudit eines Systems | `/security-review` | deep-review |

### Tests (Repo)

Neue Tests; dazu müssen die bestehenden Aufrufe von `record` (in
`tests/test_deep_review_kit.py` rund 90) und die Bericht-Helfer (rund 50) auf das Objekt mit
Marke bzw. auf `render_report` umgestellt werden, zentral über die Helfer der Testdatei.

| Test | Datei | prüft |
| --- | --- | --- |
| `test_b_counterparts_collected_once` | `tests/test_deep_review_kit.py` | `counterparts` ruft den Sammler nicht erneut, wenn `plan` ihn abgelegt hat; `level` und Zeile `Reviews:` |
| `test_b_record_needs_packet_marker` | dito | Ergebnis ohne oder mit fremder Marke → Exit 1, nichts geschrieben; `--no-block` → angenommen, `audit` nennt `no_block`, `complete` bleibt `true` |
| `test_b_report_is_written_by_the_script` | dito | `report` schreibt alle Pflichtzeilen; geänderte Fundzeile → `report_mismatch`; angefügtes `## Einordnung` → keine Abweichung |
| `test_b_big_file_split_at_definitions` | dito | neue Python-Datei mit 1.300 Zeilen → drei Pakete mit `spans` an `def`/`class`-Grenzen; geänderte Datei mit Hunks in zwei Spannen; Datei ohne Scanner nach fester Zeilenzahl; `von..bis` zeigt nur die Spanne; `bis^{tree}` = Ziel |
| `test_b_path_mode` | dito | `plan --path` → `mode: path`, Hilfscommits mit den Dateien als neu; über `PATH_SPLIT_AT` geteilt; Gegenstellen nur für Aufrufe außerhalb des Pfads |
| `test_b_typescript_collector` | dito | relativer Import → Definition und `throw`-Zeile; Aufruf einer `async`-Funktion ohne `await` → Eintrag |
| `test_b_name_fallback_marks_unique_names` | dito | Go-Datei: eindeutiger Name → Definition mit Kennzeichnung; doppelter Name → nicht aufgelöst |
| `test_b_verdict_needs_evidence` | dito | `widerlegt` ohne Beleg → abgewiesen; mit Beleg → Urteil in `findings.json`, auch nach erneutem `merge` |
| `test_b_fix_task_skips_refuted` | `tests/test_subagent_dev_plan_to_tasks.py` | Fund mit `widerlegt` fehlt in der Task-Datei, die Zahl steht dort; `unklar` bleibt |

### Evals

Fortgeführt in `evals/deep-review/evals.json`. Evals 1–6 aus Spec 26 bleiben; Eval 1 bekommt
eine Assertion auf den Bericht aus dem Skript, und seine Notes verlieren den Verweis auf
`assets/report-template.md`.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-small-range-one-packet` | contract | `dr-seeded` | wie Spec 26, dazu `file_matches` `.skills/cache/deep-review/*/report.md` auf `generated: python scripts/review_kit\.py report` | den Bericht mit dieser Kopfzeile schreibt nur `review_kit.py report` |
| 2 | `large-range-is-split-and-covered` | contract | `dr-split` | wie Spec 26 | wie Spec 26 |
| 3 | `narrowed-except-gets-callee-raises` | contract | `dr-contract` | wie Spec 26 | wie Spec 26 |
| 4 | `delphi-extract-shows-ownership` | contract | `dr-delphi` | wie Spec 26 | wie Spec 26 |
| 5 | `security-focus-is-one-packet` | contract | `dr-contract` | wie Spec 26 | wie Spec 26 |
| 6 | `routing-large-branch-without-skill-name` | contract | `dr-split` | wie Spec 26 | wie Spec 26 |
| 7 | `packet-result-carries-marker` | contract | `dr-contract` | `file_matches` `.skills/cache/deep-review/*/results/p1.json` auf `"marke":\s*"dr-p1-[0-9a-f]{6}"`; `file_matches` `.skills/cache/deep-review/*/audit.json` auf `"no_block":\s*\[\]` | die Marke erzeugt nur `counterparts`; das Basismodell kennt weder Datei noch Format |
| 8 | `big-file-split-at-definitions` | contract | `dr-bigfile` | `file_matches` `.skills/cache/deep-review/*/plan.json` auf `"spans":\s*\[\s*\{` und auf `"id":\s*"p3"` | ein neues Python-Modul mit rund 1.300 Zeilen; nach Spec 26 wäre es ein Paket |
| 9 | `path-review-has-plan-and-audit` | contract | `dr-delphi` | `file_matches` `.skills/cache/deep-review/*/plan.json` auf `"mode":\s*"path"`; `file_matches` `.skills/cache/deep-review/*/audit.json` auf `"complete":\s*true` | ohne Skill entsteht weder Plan noch Audit; nach Spec 26 ginge der Pfad ohne Plan an `/code-review` |
| 10 | `typescript-throw-gets-counterpart` | contract | `dr-ts` | `file_matches` `.skills/cache/deep-review/*/packets/p1.md` auf `wirft:[^\n]*[A-Za-z]+Error` und auf `lib/` | der Diff fängt in `src/` einen Fehler nicht mehr, den eine Funktion unter `lib/` wirft; den Block erzeugt nur das Skript |

Prompts: 7 „Review den letzten Commit mit deep-review.", 8 „Prüf base..HEAD mit
deep-review.", 9 „Prüf die Units Query.pas und Tree.pas mit deep-review.", 10 „Review den
letzten Commit mit deep-review." `dr-bigfile` und `dr-ts` sind Git-Repos mit Tag `base` und
README.md wie die Fixtures aus Spec 26; `dr-delphi` hat seine Units im Wurzelordner.

### Abnahme B

Gemessen mit `docs/superpowers/reports/review-bench/`, Treffer am Text geprüft:

| Eingabe | Läufe deep-review | Vergleich | Treffer-Schwelle | Kosten-Schwelle |
| --- | --- | --- | --- | --- |
| `py-diff` | 2 | `cr` 4,5/6, 1,06 USD | ≥ 5,5 im Mittel, P2 in mindestens einem Lauf | ≤ 2,12 USD je Lauf |
| `dl-diff` | 2 | `cr` 5,0/6, 2,33 USD | ≥ 5,5 im Mittel | ≤ 4,66 USD |
| `dl-path` | 1 | `cr` 6/6, 1,29 USD | 6/6 | ≤ 1,94 USD |
| `dr-seeded` | 1 | `cr` 5/5, 0,37 USD | 5/5 | ≤ 0,56 USD |
| `dr-contract`, `dr-delphi`, `dr-ts` | je 1 | `cr` je 2 Läufe (Sonde bzw. Abnahme) | ≥ `cr` | ≤ 1,5× `cr` |

*Annahme:* 5,5 im Mittel heißt höchstens ein Fehlschlag in zwei Läufen; gesetzt über der
Vereinigung aller Basisläufe auf `py-diff` (5/6).

Präzision: aus je einem Lauf `cr` und deep-review auf `py-diff` je zehn zufällig gezogene
Funde, isoliert geprüft wie in Ablauf Schritt 6 (Python lässt sich dort ausführen; auf
`dl-diff` kein Delphi-Compiler, daher nicht dort). Schwelle: Anteil `widerlegt` bei deep-review
nicht höher als bei `cr`; bei zehn Funden entscheidet ein einziger, das Ergebnis ist ein
Hinweis, kein Beleg.

**Regel für Routing und Description:**
- Großer Diff: deep-review bleibt zuständig, wenn die Treffer-Schwelle erfüllt ist. Wird nur
  die Kosten-Schwelle verfehlt, sagt der Bericht den Faktor; die Zeile `Reviews:` nennt die
  Zahl der Reviews vorab.
- Kleiner Diff und Pfad: ohne Mehrtreffer zählt nur der Nachweis. deep-review übernimmt eine
  solche Eingabe nur, wenn beide Schwellen erfüllt sind; sonst bleibt sie bei `/code-review`,
  und die Description nennt sie unter „Not for".

## Alternatives considered

**Eigener Reviewer statt `/code-review` je Paket** (ein Sonnet-Unteragent mit dem
Paket-Auftrag). Billiger, aber auf `dr-seeded` fand Sonnet im Mittel 4,33 von 5, `/code-review`
5 von 5. Gewinnt, wenn die Sonde zeigt, dass `/code-review low` keinen von P2 und P4 findet und
ein einzelner Reviewer mit Block schon.

**Kostenschwelle an die Paketzahl knüpfen** (Vorschlag aus dem Report der Abnahme). Verworfen
als Ziel: Der Nutzer vergleicht mit einem `/code-review`-Lauf, nicht mit n. Die Zahl der
Reviews nennt `plan` trotzdem vorab.

**Größere Pakete statt Stufe** (`PACKET_SIZE` 1.000). Senkt die Zahl der Reviews, aber
zwischen 800 und 2.000 Zeilen ist nichts gemessen, und 1.988 Zeilen am Stück verloren Funde.
Bleibt bei 600, bis eine Messung mehr zeigt.

**Den Bericht weiter vom Hauptagenten schreiben lassen.** Verworfen: Die Hauptschleife kostet
auf `py-diff` schon mehr als das Doppelte der Basislinie, und `audit` liest freies Markdown nur
mit Mustern.

**Marke als Beleg der Block-Übergabe.** Verworfen: Das Ergebnisobjekt baut, wer `record`
aufruft; die Marke steht in der letzten Zeile der Datei. Bleibt als Auskunft, die den Weg mit
Auftrag und Block in einer Datei sichtbar macht; belegen kann die Übergabe nur ein Transkript.

**Präzision über eine saubere Fassung messen.** Verworfen: `dr-seeded-clean` enthält
mindestens fünf echte, unabsichtliche Fehler; die Zahl der Funde auf einer sauberen Fassung
misst keine Fehlalarme. Gezählt wird `widerlegt` in einer Stichprobe.

## Out of scope

Typinferenz für TypeScript, Pfad-Aliase und `node_modules`; Sammler mit Importen für die
Sprachen des Namens-Rückfalls; eigene Such- oder Verifikationsagenten außer `verify`; Fixes
und Commits; Messung von Fokus `security` und `quality`; ein großes TypeScript-Szenario im
Bench; Präzision auf Delphi.

## Open questions

*Annahme:* Die Sonde trennt die Wirkung des Blocks mit ein oder zwei Läufen nur grob; die
Streuung von `dr` ist mit einem Lauf je Szenario unbekannt.

*Annahme:* `PATH_SPLIT_AT = 6000` und `PATH_PACKET_SIZE = 3000`. Gemessen ist nur `dl-path`
mit 5.308 Zeilen in einem Review ohne Verlust.

*Annahme:* Die Marke zeigt nur, dass der Schreiber des Ergebnisses `packets/<id>.prompt.md`
kennt. Dass die Unteragenten von `/code-review` den Auftrag sehen, misst die Sonde einmal an den
Transkripten; das gilt dann für diese CLI-Version.

*Annahme:* Ein Unteragent kann `/code-review` starten und einen Auftrag von mehreren KB lesen.
Wenn nicht, bleibt Schritt 4 im Hauptkontext, und der Kontext über viele Pakete bleibt
ungemessen.

*Annahme:* `verify` kostet rund 61.000 Tokens je Fund (finaler Prüfpunkt von Spec 26: 9 Funde,
rund 550.000 Tokens, 1 widerlegt). Deshalb nur im Profil `checkpoint` als Standard. Ein Prüfer
ohne Schreibgrenze legte damals `/out` und `/work` im Container an; die Grenze
`verify/<n>/work/` verlangt der Auftrag (G1), kein Mechanismus.

*Annahme:* Die Kostenzerlegung aus dem Spec-Review ist eine Schätzung; die Sonde misst sie
nach. Ob das Kostenziel mit Stufe und schlanker Hauptschleife erreichbar ist, ist offen.

Ob die Description mit „kleinen Diff" gegen `/code-review` gewinnt, ist stochastisch wie
Eval 6 aus Spec 26.

## Next steps

Plan `docs/superpowers/plans/2026-11-04-deep-review-b.md` (impl-plan), Bau mit subagent-dev.
Vor der Sonde und vor der Abnahme gibt der Nutzer das jeweilige Messbudget frei.
