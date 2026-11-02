# Spec 26: deep-review — `/code-review` in Paketen, mit den Verträgen der Gegenstellen

Skill-Spezifikation · Zyklus 26 · Entscheidung: keine eigene Such-Pipeline — die Skill steuert die mitgelieferten Reviewer und ergänzt nur, was ihnen in der Messung fehlte: große Bereiche schneidet ein Tier-1-Skript in Pakete, und je Paket sammelt es die Gegenstellen der geänderten Aufrufe (Definition, `raise`-Stellen, Besitz, Weg eines Flags), die der Reviewer sonst nicht öffnet · Abgeglichen mit Spec 00 und Spec 27 · Neu gefasst nach der Messung vom 2026-11-01/02 (`docs/superpowers/reports/deep-review-report.md`); ersetzt die Fassung vom 2026-10-30 (Inventar, Nonce, Suchagenten, gestufte Verifikation, Sättigung)

## Problem

Der Nutzer will Fehlverhalten, Programmfehler und Sicherheitslücken gefunden sehen und
nicht „gamblen", ob der Reviewer die richtige Stelle findet (2026-10-28). Er prüft
regelmäßig Delphi-Code und reviewt Pläne über subagent-dev an Prüfpunkten (Spec 27).

Die Fassung vom 2026-10-30 baute dafür eine eigene Pipeline mit Inventar und
Abdeckungsnachweis. Die Messung hat ihre Prämisse widerlegt und eine andere Lücke gezeigt
(Report, Abschnitte „Nachmessung auf großen Repos", „Entscheidungsexperiment" und
„Prototyp"; 34 Läufe, 37,71 USD; `/code-review`, engineering:code-review und
superpowers:requesting-code-review auf pip 25.0→25.1 und DelphiMVCFramework rc6→rc7):

- **Pfad-Review bis rund 5k Zeilen ist gelöst.** Auf unbekanntem Delphi-Bestandscode (7 Units
  aus 2026, nach dem Wissensstand des Modells) fanden `/code-review` und engineering in
  sechs von sechs Läufen alle sechs eingebauten Fehler.
- **Große Diffs verlieren Funde.** Bei 4.100 geänderten Zeilen in 151 Dateien verfehlt ein
  Lauf ein bis vier von sechs; bei 2.000 Zeilen null bis zwei.
- **Die Lücke ist meist keine Lesefrage.** Die Zeile von P2 (eine verengte `except`-Klausel)
  stand in fünf von fünf Läufen im Kontext und wurde nie erkannt; den vendorten Code, der den
  `TypeError` wirft, öffnete keiner von acht Läufen. P4 (ein Resolver-Flag) fand nur der eine
  Lauf, der `factory.py` las. Eine Bitte im Systemprompt („prüfe die Gegenstelle") änderte
  daran nichts.
- **Aufteilen plus mitgegebene Gegenstellen wirkt.** In einem Paket von 591 Zeilen fand
  `/code-review` mit mechanisch gesammeltem Kontext erstmals P2 und P4 (je einmal in zwei
  Läufen). Derselbe Kontext über den ganzen Diff brachte nichts. Aufteilen allein fand so
  viel wie ein ganzer Lauf, kostete für drei Pakete zusammen 1,43 USD (ein ganzer Lauf rund
  1,05 USD) und fand als einziger Lauf die echte Regression R2.

Am Prüfpunkt von subagent-dev läuft heute `/code-review` über den ganzen Bereich, und die
Übergabe sagt „Review ohne Abdeckungsnachweis" (Spec 27). Der finale Prüfpunkt reviewt
`base..HEAD` — genau der große Bereich, in dem Funde verloren gehen.

## Constraints

Portables Frontmatter. Tier 1: ein Skript `scripts/review_kit.py`, nur Stdlib, aufgerufen
als `python "${CLAUDE_SKILL_DIR}/scripts/review_kit.py"` (Spec 25). Python über `ast`, nie
Import des Zielcodes; Delphi/Object Pascal über einen Text-Scanner, der Strings und
Kommentare ausblendet. Andere Sprachen: Aufteilen ja, Gegenstellen nein — der Bericht sagt
„Gegenstellen nicht gesammelt (Sprache)".

Die Reviews selbst führen die mitgelieferten Befehle aus, im Hauptkontext, weil `/code-review`
eigene Unteragenten startet: `/code-review --max-findings all <bereich>` je Paket, für
Sicherheit `/security-review`. Ohne diese Befehle (claude.ai, andere Agenten) läuft dieselbe
Paketfolge als Review im Hauptkontext nach `references/review-brief.md`; der Bericht sagt dann
„Review ohne /code-review".

Gate-Grade: Paketplan, Gegenstellen, Abdeckung aller Pakete und Konsistenz des Berichts
meldet `review_kit.py audit` (G2); dass je Paket wirklich ein Review lief, verlangt die
SKILL.md (G1). Kein Hook. Plugin `evaluated-dev`; dazu Projekt-Kopie unter `.claude/skills/`,
weil dieses Repo das Plugin abschaltet und Cloud-Sitzungen nur Projekt-Kopien laden
(`scripts/sync_skills.py`).

Ablage (Spec 00 §1), alles Ephemera unter `.skills/cache/deep-review/<lauf>/`. `<lauf>` ist
die Lauf-ID `<JJJJ-MM-TT>-<HHMMSS>-<kurz-sha>-<4 Zufallszeichen>`.

| Datei | schreibt | Inhalt |
| --- | --- | --- |
| `plan.json` | `plan` | `_meta`, `range`, `profile`, `focus`, `split`, `split_at`, `changed_lines`, `packets` (je `id`, `files`, `changed_lines`, `key`, `range`, `reused_from`), `not_reviewed` (Dateien ohne Quellcode mit Grund) |
| `packets/<id>.md` | `counterparts` | Kopfzeile, Bereich und Dateien des Pakets, Gegenstellen je geänderter Stelle |
| `results/<id>.json` | `record` | `_meta` mit `packet`, `key`, `tool`; `findings` als Liste (`file`, `line`, `summary`, `failure_scenario`) |
| `findings.json` | `merge` | vereinigte Funde als JSON-Liste mit `file`, `line`, `summary`, `failure_scenario`, `packets` — das Format, das `fix-task` von `/code-review` liest (Spec 27) |
| `audit.json` | `audit` | `_meta`, `complete`, `missing` (Pakete ohne Ergebnis), `key_mismatch`, `lost_findings`, `report_mismatch` |
| `report.md` | Hauptagent nach `assets/report-template.md` | Bericht mit Kopfzeile |

JSON schreibt das Skript mit `ensure_ascii=False`, festen Schlüsseln in fester Reihenfolge und
repo-relativen POSIX-Pfaden. Committet wird nur auf Wunsch eine Kopie des Berichts unter
`docs/reviews/`. Bootstrap: Der erste Lauf nennt `.skills/cache/deep-review/`, bevor er
schreibt.

## Approach

**Eiserne Regel:** *Kein Bericht nennt sich vollständig, solange ein Paket des Plans kein vom
Skript angenommenes Ergebnis hat — und kein Fund eines Pakets fehlt in `findings.json`.*

### Skill-Struktur

```
skills/deep-review/
├── SKILL.md                         Ablauf, Eiserne Regel, Profile und Fokus, Contract, Anti-Rationalisierung, Abgrenzung
├── references/packets.md            Schnittregel, Schwellen, Schlüssel, Paket-Bereiche, --since
├── references/counterparts.md       was je Sprache gesammelt wird und was nicht; Lesehilfe für den Reviewer
├── references/review-brief.md       Auftrag je Paket: Bereich, Gegenstellen-Block weitergeben, JSON-Liste zurück; Fassung ohne /code-review
├── references/delphi.md             Prüfliste Delphi: Besitz und Freigabe, Extract/OwnsObjects, 1-basierte Strings, Record-Kopien, TDateTime in Tagen, UTC gegen Ortszeit, Interface-Referenzzählung
├── assets/report-template.md        Gerüst des Berichts mit Kopfzeile in Zeile 1
└── scripts/review_kit.py            Tier 1 — plan, counterparts, record, merge, audit, cleanup

skills/review-context/SKILL.md       Abgrenzung nennt deep-review (Kontext für einen Diff vs. Pakete mit Gegenstellen)
skills/subagent-dev/SKILL.md, skills/subagent-dev/references/checkpoints.md   Review am Prüfpunkt über deep-review; Ersatz /code-review bleibt für Repos ohne die Skill
skills/debug-ledger/SKILL.md, skills/test-first/SKILL.md   Abgrenzung nennt deep-review
scripts/sync_skills.py               Tier 1, Repo-Werkzeug — deep-review in PROJECT_SKILLS
.claude/skills/deep-review/, .claude/skills/review-context/, .claude/skills/subagent-dev/, .claude/skills/debug-ledger/, .claude/skills/test-first/   Projekt-Kopien über sync_skills.py
.claude-plugin/marketplace.json      deep-review in der skills-Liste von evaluated-dev
specs/Spec 00 – skill-foundation.md  Routing: neue Zeile „großen Bereich oder Prüfpunkt gründlich prüfen" mit deep-review in der Spalte „zuständig"; Zeile „Diff prüfen" nennt deep-review unter „nicht"
README.md                            Skill-Liste von evaluated-dev; Routing-Zeile mit deep-review in der Spalte „Responsible"
docs/known-limits.md                 Abschnitt deep-review
docs/superpowers/reports/deep-review-report.md   Report: Messung bis Prototyp (steht), dazu Abnahme
evals/deep-review/evals.json         sechs Evals, siehe unten
evals/fixtures/dr-split/, dr-contract/, dr-delphi/   je fixture.json mit "git": true (dr-seeded besteht)
tests/test_deep_review_kit.py        siehe Tests (Repo)
```

### Ablauf

1. **Bereich, Profil, Fokus.** Bereich `BASIS..ZIEL` aus dem Auftrag, Standard der letzte
   Commit. Ein Pfad statt eines Bereichs geht direkt an `/code-review <pfad>` (Pfad-Review
   ist gelöst, siehe Problem) und erzeugt keinen Plan. Profil `standard` (Standard) oder
   `checkpoint` (Aufruf aus subagent-dev, nur Fokus `bugs`). Fokus `bugs` (Standard),
   `security` oder `quality`, aus dem Auftrag oder `--focus`.
2. **Plan:** `review_kit.py plan --range <bereich> [--profile …] [--focus …] [--split-at N]
   [--since <lauf>[,<lauf>…]] [--soll-file <datei>]`. Gezählt werden hinzugefügte plus gelöschte
   Zeilen (`git diff --numstat`), `.skills/` nie. Bis `split_at` (Standard 800) ein Paket über
   den Originalbereich, `split: false`. Darüber schneidet das Skript nach Verzeichnis: Dateien
   desselben Verzeichnisses bleiben zusammen, Pakete füllen bis 600 Zeilen, eine Datei über
   600 Zeilen ist ein eigenes Paket, eine Datei wird nie geteilt. Testdateien (`test_*.py`,
   `*_test.py`, `tests/`, `*Test*.pas`) bilden eigene Pakete nach dem Code. Dateien ohne
   Quellcode (Markdown, `NEWS`, Bilder, `.dproj`, `.res`) stehen unter `not_reviewed` mit
   Grund. Je Paket ein Schlüssel (Hash über die Inhalte seiner Dateien am Ziel) und ein
   Paket-Bereich: zwei Hilfscommits unter `refs/deep-review/<lauf>/<id>/`, `von` = Zielstand
   mit den Dateien des Pakets auf dem Basisstand, `bis` = Zielstand. So sieht der Reviewer den
   vollen Code und als Änderung nur das Paket — wie im Entscheidungsexperiment (`mid..HEAD`).
3. **Gegenstellen:** `review_kit.py counterparts --run <lauf>` schreibt je Paket
   `packets/<id>.md`. Python (`ast`): je Aufruf auf einer geänderten Zeile die erreichte
   Definition (aufgelöst über die Importe der Datei und voll qualifizierte Modulpfade, auch in
   vendortem Code), ihre Signatur, die erste Docstring-Zeile und ihre `raise`-Stellen transitiv
   im selben Modul (Tiefe 2); je geänderter `except`-Klausel die Ausnahmen aller Aufrufe im
   `try`-Block; je geändertem Schlüsselwort-Argument sein Weg durch die Gegenstellen bis zu den
   Bedingungen, die es prüfen (Tiefe 4). Ohne Importbezug und mit mehr als drei gleichnamigen
   Definitionen: nichts statt Raten, aber gezählt. Delphi (Text): je Aufruf `Name(` oder
   `Obj.Name(` auf einer geänderten Zeile die Implementierung `procedure|function|constructor
   TKlasse.Name` aus den Units der `uses`-Listen, ihr Kopf aus dem `interface`-Teil mit
   Default-Werten der Parameter und ihre `raise`-Zeilen; je geänderter Zeile mit `Extract`,
   `Remove`, `Free`, `FreeAndNil` oder `SetContentStream` die Klassendeklaration des Empfängers
   mit Basisklasse und dem `inherited Create(…)` ihres Konstruktors (Besitz über
   `OwnsObjects`, `doOwnsValues`, `Create(True)`). Je Paket höchstens 30.000 Zeichen; Kappung
   mit Zahl, nie still.
4. **Review je Paket**, im Hauptkontext, in Plan-Reihenfolge:
   - Fokus `bugs`: `/code-review --max-findings all <von>..<bis>` über den Paket-Bereich, mit
     dem Inhalt von `packets/<id>.md` und dem Auftrag aus `references/review-brief.md`
     (den Block jedem Unteragenten unverändert mitgeben); bei Delphi dazu
     `references/delphi.md`. Im Profil `checkpoint` dazu das Soll aus `--soll-file`.
   - Fokus `security`: `/security-review` einmal über den ganzen Bereich, die Gegenstellen
     aller Pakete als Kontext; nicht aufgeteilt (siehe Open questions).
   - Fokus `quality`: `/code-review` je Paket mit dem Auftrag, nur Wartbarkeit, Doppelung und
     Vereinfachung zu melden, je mit Grundlage (Projektregel, Messwert oder konkreter
     Lesefehler); `/simplify` nicht, weil es Änderungen schreibt.

   Das Ergebnis — die JSON-Liste von `/code-review` oder die Liste aus dem Brief — gibt der
   Hauptagent an `review_kit.py record --run <lauf> --packet <id> --key <schlüssel> <datei>`;
   das Skript nimmt es nur an, wenn Schlüssel und Paket zum Plan passen. Ein Paket ohne Funde
   bekommt eine leere Liste, kein Weglassen.
5. **Vereinigen:** `review_kit.py merge --run <lauf>` legt Funde derselben Datei mit höchstens
   drei Zeilen Abstand zusammen und behält alle Pakete; abgestimmt wird nicht.
6. **Bericht und Audit:** Bericht nach `assets/report-template.md` (Kopfzeile mit Lauf-ID,
   Bereich, Profil, Fokus, Werkzeug), Tabelle der Pakete mit Dateien, Zeilen, Zahl der
   Gegenstellen und Funde, „Nicht geprüft" aus `not_reviewed`; dann `review_kit.py audit
   --run <lauf>` und `review_kit.py cleanup --run <lauf>` (löscht die Hilfscommits). Übergabe:
   Lauf-ID, Pfad des Berichts, Zahl der Funde, Abdeckung `<Pakete mit Ergebnis>/<Pakete>`.
   Meldet das Audit eine Lücke, sagt die Übergabe „unvollständig" mit der Liste, nie „fertig".
   Im Profil `checkpoint` endet deep-review hier; subagent-dev behebt die Funde aus
   `findings.json` über `fix-task` (Spec 27). Sonst gehen Funde mit unklarer Ursache an
   debug-ledger, die übrigen behebt der Hauptagent mit Regressionstest über test-first.

**Folgeläufe** (`--since <lauf>[,<lauf>…]`, Spec 27): Ein Paket, dessen Dateien am Ziel
dieselben Inhalte haben wie in einem Paket eines früheren Laufs (gleicher Hash je Datei),
übernimmt dessen Ergebnis mit `reused_from`; steht eine Datei in mehreren Läufen, gilt der
jüngste. Geänderte Dateien werden neu geschnitten und reviewt. Am finalen Prüfpunkt
(`base..HEAD` über alle Läufe aus `runs`) bleiben so nur die Dateien, die sich seit ihrem
Review geändert haben.

**Profile und Fokus:**

| | wann | Werkzeug | Pakete | Gegenstellen |
| --- | --- | --- | --- | --- |
| `standard`, Fokus `bugs` | Normalfall | `/code-review --max-findings all` | ab `split_at` | ja |
| `checkpoint` | Prüfpunkt aus subagent-dev (Spec 27) | wie `standard`, `--soll-file` als Soll | ab `split_at` | ja |
| Fokus `security` | „Sicherheit", „Sicherheitsreview" | `/security-review` | nein | ja, als Kontext |
| Fokus `quality` | „Wartbarkeit", „Qualität", „Code-Hygiene" | `/code-review` mit Qualitätsauftrag | ab `split_at` | nein |

### Contract

- **Abdeckung gegen den Plan.** `audit` meldet jedes Paket ohne angenommenes Ergebnis und
  jedes Ergebnis, dessen Schlüssel nicht zum Plan passt (G2). Der Schlüssel verhindert ein
  Ergebnis für einen veralteten Stand, nicht ein erfundenes: Dass je Paket ein Review lief,
  bleibt Auskunft des Hauptagenten. Das steht im Bericht.
- **Kein Fund verschwindet.** Jeder Fund in `results/*.json` steht in `findings.json`; `audit`
  meldet die Differenz als `lost_findings`.
- **Bericht und Daten stimmen überein.** `audit` meldet einen Bericht, der „vollständig" sagt,
  obwohl `audit.json` Lücken trägt, und Zahlen im Bericht, die nicht zu den Dateien passen.
- **Gegenstellen sind mechanisch.** `counterparts` wählt nicht nach Verdacht aus; es schreibt
  jede geänderte Stelle, die es auflösen kann, und nennt die Zahl der nicht aufgelösten.
- **Nichts wird ausgeführt.** Das Skript importiert und startet keinen Zielcode; die
  Hilfscommits liegen nur unter `refs/deep-review/` und `cleanup` löscht sie.
- **Anti-Zeremonie-Fall:** Ein Bereich bis `split_at` Zeilen ergibt ein Paket, einen Aufruf
  von `/code-review` über den Originalbereich, keine Hilfscommits und einen Bericht von
  höchstens 40 Zeilen.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| kleinen Diff oder PR prüfen | `/code-review` (mitgeliefert) | deep-review — bringt bis `split_at` nur die Gegenstellen dazu |
| großen Bereich, Branch oder Prüfpunkt eines Plans gründlich prüfen, mit Nachweis je Paket | **deep-review** | `/code-review` über alles — verliert in großen Bereichen Funde |
| Pfad oder Modul ohne Diff prüfen | `/code-review <pfad>` | deep-review — reicht ihn nur durch |
| Kontext und Soll für einen Diff sammeln | **review-context** | deep-review — sammelt Gegenstellen je Paket, kein Soll |
| wann zwischen Tasks reviewt wird | **subagent-dev** (Spec 27) | deep-review prüft, plant keine Prüfpunkte |
| Sicherheitsaudit eines ganzen Systems | `/security-review`, trailofbits | deep-review — reicht Fokus `security` an `/security-review` durch |
| bestätigter Fund mit unklarer Ursache | **debug-ledger** | deep-review meldet, diagnostiziert nicht |
| Regressionstest zu einem Fund | **test-first** | deep-review schreibt keine Tests |

Rückverweise beim Bau, je mit dem Wort deep-review: review-context, subagent-dev,
debug-ledger, test-first (alle im Strukturblock oben).

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_seeded_fixtures` | `tests/test_deep_review_kit.py` | besteht (Task 1 des Plans vom 2026-10-30) |
| `test_plan_single_packet_below_threshold` | dito | bis `split_at` ein Paket mit Originalbereich, `split: false`, keine Refs; `.skills/` zählt nicht |
| `test_plan_splits_by_directory` | dito | Verzeichnis bleibt zusammen, Pakete bis 600 Zeilen, große Datei eigenes Paket, Tests nach dem Code, Doku unter `not_reviewed` mit Grund |
| `test_plan_packet_range_shows_only_the_packet` | dito | `von..bis` eines Pakets ändert genau seine Dateien, `bis` hat den Baum des Ziels; `cleanup` löscht alle Refs des Laufs |
| `test_counterparts_python_except_and_raises` | dito | geänderte `except`-Klausel → Ausnahmen der Aufrufe im `try` samt `raise`-Zeilen im vendorten Modul |
| `test_counterparts_python_flag_flow` | dito | geändertes Schlüsselwort-Argument → Weg über zwei Gegenstellen bis zur Bedingung; voll qualifizierter Modulpfad löst eindeutig auf |
| `test_counterparts_python_no_guessing` | dito | Methode mit gängigem Namen ohne Importbezug → nicht aufgelöst, gezählt |
| `test_counterparts_delphi` | dito | Aufruf → Implementierung aus einer `uses`-Unit, Kopf mit Default-Wert; `Extract` → Klassendeklaration mit `inherited Create(True)`; `end` in String und Kommentar ignoriert |
| `test_counterparts_cap` | dito | über 30.000 Zeichen → gekappt mit Zahl |
| `test_record_rejects_wrong_key` | dito | falscher Schlüssel oder unbekanntes Paket → abgewiesen, nichts geschrieben |
| `test_merge_keeps_every_finding` | dito | gleiche Datei, Abstand ≤ 3 → ein Fund mit beiden Paketen; sonst zwei; `fix-task` liest `findings.json` |
| `test_since_reuses_unchanged_packets` | dito | gleiche Dateiinhalte → `reused_from`; eine geänderte Datei → ihr Paket neu; zwei frühere Läufe → der jüngere |
| `test_audit` | dito | fehlendes Ergebnis, falscher Schlüssel, Fund fehlt in `findings.json`, Bericht „vollständig" trotz Lücke → je ein Eintrag und `complete: false`; sauber → `true` |
| `test_run_ids_do_not_collide` | dito | zwei Läufe in derselben Sekunde → verschiedene IDs |

### Evals

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-small-range-one-packet` | contract | `dr-seeded` | `file_matches` `.skills/cache/deep-review/*/plan.json` auf `"split":\s*false`; `artifact_header` auf `.skills/cache/deep-review/*/report.md`; `file_max_lines` dort 40; `git_head_unchanged` | `plan.json` schreibt nur `review_kit.py` |
| 2 | `large-range-is-split-and-covered` | contract | `dr-split` | `file_matches` `.skills/cache/deep-review/*/plan.json` auf `"id":\s*"p2"`; `file_matches` `.skills/cache/deep-review/*/audit.json` auf `"complete":\s*true` und auf `"missing":\s*\[\]` | Prompt nennt „teile ab 200 Zeilen"; ohne Skill gibt es weder Plan noch Audit |
| 3 | `narrowed-except-gets-callee-raises` | contract | `dr-contract` | `file_matches` `.skills/cache/deep-review/*/packets/*.md` auf `wirft[^\n]*TypeError`; `file_matches` `.skills/cache/deep-review/*/findings.json` auf `app/groups\.py` | die Fixture verengt `except (ValueError, TypeError)` vor einem Aufruf in `vendor/grouplib.py`, der `TypeError` wirft; der Paketblock entsteht nur im Skript |
| 4 | `delphi-extract-shows-ownership` | contract | `dr-delphi` | `file_matches` `.skills/cache/deep-review/*/packets/*.md` auf `inherited Create\(True\)`; `file_matches` `.skills/cache/deep-review/*/findings.json` auf `Query\.pas` | `TQueryTree = class(TObjectList<TNode>)` besitzt seine Knoten, der Diff ersetzt `Remove` durch `Extract` |
| 5 | `security-focus-routes-to-security-review` | contract | `dr-contract` | `artifact_header` auf `.skills/cache/deep-review/*/report.md`; `file_matches` dort auf `^<!--[^\n]*focus: security` und auf `/security-review` | Kopfzeile schreibt nur die Skill nach ihrem Template |
| 6 | `routing-large-branch-without-skill-name` | contract | `dr-split` | `file_exists` `.skills/cache/deep-review/*/plan.json` | stochastisch: ein roter Lauf zeigt eine Kollision mit `/code-review`; ein grüner beweist nichts |

Prompts: 1 „Review base..HEAD mit deep-review.", 2 „Prüf base..HEAD mit deep-review, teile ab
200 Zeilen.", 3 und 4 „Review den letzten Commit mit deep-review.", 5 „Mach ein
Sicherheitsreview von base..HEAD mit deep-review.", 6 „Der Branch ist groß, prüf base..HEAD
gründlich auf Fehler und sag mir, ob jedes Stück angeschaut wurde." Die Fixtures sind
Git-Repos mit Tag `base`; `dr-split` hat rund 450 geänderte Zeilen in zwei Verzeichnissen.
Vor der Abnahme läuft jeder Eval einmal ohne Skill (Spec 18).

### Abnahme der Trefferquote

Die Evals prüfen den Vertrag. Die Trefferquote misst der Report mit
`docs/superpowers/reports/review-bench/` auf `py-diff` (pip 25.0→25.1, 6 eingebaute + 2
echte Fehler) und `dl-diff` (DelphiMVCFramework rc6→rc7, 6 eingebaute), je zwei Läufe
deep-review im Profil `standard` gegen die gemessene Basislinie von `/code-review` über den
ganzen Bereich (Mittel 4,5 bzw. 5,0 von 6). *Annahme:* Abnahme, wenn deep-review im Mittel
mindestens so viele eingebaute Fehler findet wie die Basislinie, auf `py-diff` P2 oder P4 in
mindestens einem Lauf, und je Lauf höchstens das Doppelte der Basislinie kostet (pip rund
1,05 USD, Delphi rund 2,30 USD). Jede Stufe, die gegenüber ihrer Abschaltung (Pakete,
Gegenstellen, Delphi-Prüfliste) keinen messbaren Unterschied bringt, fliegt raus.

## Alternatives considered

**Die Fassung vom 2026-10-30** (Inventar je Funktion, Nonce, lesende Suchagenten je Linse,
gestufte Verifikation, Sättigung). Verworfen nach der Messung: Sie erzwingt Abdeckung, und
Abdeckung war nicht das Problem — die übersehenen Zeilen standen im Kontext. Gewinnt, wenn
das runlog aus Spec 27 Funde zeigt, die `/code-review` in kleinen Paketen mit Gegenstellen
übersieht, obwohl ihre Gegenstelle im Paketblock stand.

**Bei `/code-review` über den ganzen Bereich bleiben.** Verworfen: verliert in großen
Bereichen ein bis vier von sechs Fehlern, und P2 in keinem von sieben Läufen.

**Nur aufteilen, ohne Gegenstellen.** Billiger und einfacher. Verworfen als alleiniger Weg:
fand P2 und P4 nicht; mit Gegenstellen je einmal in zwei Läufen.

**Nur ein Auftrag im Prompt („prüfe die Gegenstelle").** Verworfen: auf pip ohne Wirkung,
kein Lauf öffnete den vendorten Code.

**Pfadfilter statt Hilfscommits** (`/code-review <bereich> -- <dateien>`). Einfacher, aber
nicht geprüft, ob `/code-review` ihn annimmt; die Hilfscommits sind die gemessene Form.

**Zwei Läufe vereinigen.** Bringt `py-diff` auf 5/6 zum doppelten Preis, ohne P2. Bleibt als
Option für Nutzer, die mehr ausgeben wollen; nicht Teil der Skill.

**Eine eigene Review-Skill je Fokus** (Sicherheit, Qualität). Verworfen: dieselben Pakete,
derselbe Plan, dasselbe Audit wären dreifach; die Werkzeuge gibt es mitgeliefert.

## Out of scope

Eigene Such- oder Verifikationsagenten, Abdeckung je Funktion, Sättigung und Schätzung von
Restfehlern (Fassung vom 2026-10-30); Pfad-Review mit eigenem Plan (gelöst durch
`/code-review <pfad>`); Gegenstellen für TypeScript, Java und andere Sprachen; Fixes
schreiben (Hauptagent); Prüfpunkte planen (subagent-dev); Taint-Analyse; Ausführen von
Zielcode.

## Open questions

*Annahme:* `split_at` 800 und Paketgröße 600 Zeilen. Gemessen ist nur: 591–651 Zeilen je
Paket wirkten, 2.000 Zeilen am Stück verloren null bis zwei Funde, 4.100 Zeilen ein bis
vier. Zwischen 800 und 2.000 ist nichts gemessen.

*Annahme:* Der Gegenstellen-Block erreicht die Unteragenten von `/code-review`, weil der
Hauptagent ihn im Aufruf mitgibt. Im Prototyp ging er über `--append-system-prompt` mit der
Bitte, ihn weiterzugeben; ob er im interaktiven Aufruf genauso ankommt, ist ungemessen.

*Annahme:* Der Delphi-Sammler (Text-Scanner) liefert auf DelphiMVCFramework brauchbare
Gegenstellen; gemessen ist nur der Python-Sammler. D1 (Besitz bei `Extract`) fand ein Lauf
mit Prompt-Auftrag, drei von fünf ohne ihn nicht — ein Lauf, kein Beleg.

*Annahme:* Fokus `security` wird nicht aufgeteilt, weil `/security-review` seinen Bereich
selbst wählt (ausstehende Änderungen des Branches); ob es einen Bereich annimmt, ist nicht
geprüft. Sicherheit und Qualität sind nicht gemessen — die eingebauten Sicherheitsfehler
(doppelte Header, Payload-Grenze, Secure-Cookie, Refresh-Token, Zip-Slip) fand `/code-review`.

*Annahme:* Name `deep-review` bleibt, weil Spec 27 und subagent-dev ihn schon nennen; die
Skill ist schmaler, als der Name sagt.

Die Streuung bleibt: Mit Gegenstellen fand je Lauf einer von P2 und P4, nicht beide. Zwei
Läufe je Zelle sind kein Mittelwert.

evaluated-dev ist immer an und hat das längste Listing; deep-review kommt mit einer weiteren
Description dazu (Spec 20).

## Next steps

Plan mit `impl-plan` (16) neu; der Plan vom 2026-10-30 (23 Tasks) wird ersetzt, Task 1
(`dr-seeded`, `test_seeded_fixtures`, Basislinie) bleibt gebaut. Reihenfolge: `review_kit.py
plan` und `counterparts` für Python mit Tests, dann die Delphi-Hälfte, dann `record`, `merge`,
`audit`, dann SKILL.md und Nachbarn (subagent-dev ruft am Prüfpunkt deep-review), zuletzt
Evals und Abnahme mit review-bench. Bau nach `skill-forge` (17) Schritt 3 bis 7.
