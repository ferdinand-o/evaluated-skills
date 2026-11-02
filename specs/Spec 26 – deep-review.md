# Spec 26: deep-review — `/code-review` in Paketen, mit den Verträgen der Gegenstellen

Skill-Spezifikation · Zyklus 26 · Entscheidung: keine eigene Such-Pipeline — die Skill steuert die mitgelieferten Reviewer und ergänzt nur, was ihnen in der Messung fehlte: große Bereiche schneidet ein Tier-1-Skript in Pakete, und je Paket sammelt es die Gegenstellen der geänderten Aufrufe (Definition, `raise`-Stellen, Besitz, Weg eines Flags), die der Reviewer sonst nicht öffnet · Abgeglichen mit Spec 00 und Spec 27 · Neu gefasst nach der Messung vom 2026-11-01/02 (`docs/superpowers/reports/deep-review-report.md`); ersetzt die Fassung vom 2026-10-30 (Inventar, Nonce, Suchagenten, gestufte Verifikation, Sättigung) · Überarbeitet nach unabhängigem Review (2026-11-02, Opus: Schnittregel mit Paketgröße und IDs festgelegt, je Fixture eine weitere Datei, `--since` je Datei mit Gegenstellen im Schlüssel samt Nachbarn Spec 27, checkpoints.md und `fix-task`, 28 statt 34 Läufe, Sicherheitsfunde berichtigt, Tests standardmäßig nicht reviewt wie in der Messung, Sammelregel wie im Prototyp, Fokus `security` als ein Paket `s1` mit Audit, keine Fixes in der Skill, stochastische Fundprüfungen aus Eval 3 und 4 in die Abnahme, Hilfscommits mit Identität, Message und Aufräumen, `--max-findings all` als bekannte Grenze, test-first ohne Projekt-Kopie, `findings.json` mit Kopf)

## Problem

Der Nutzer will Fehlverhalten, Programmfehler und Sicherheitslücken gefunden sehen und
nicht „gamblen", ob der Reviewer die richtige Stelle findet (2026-10-28). Er prüft
regelmäßig Delphi-Code und reviewt Pläne über subagent-dev an Prüfpunkten (Spec 27).

Die Fassung vom 2026-10-30 baute dafür eine eigene Pipeline mit Inventar und
Abdeckungsnachweis. Die Messung hat ihre Prämisse widerlegt und eine andere Lücke gezeigt
(Report, Abschnitte „Nachmessung auf großen Repos", „Entscheidungsexperiment" und
„Prototyp"; 28 Läufe, 37,71 USD; `/code-review`, engineering:code-review und
superpowers:requesting-code-review auf pip 25.0→25.1 und DelphiMVCFramework rc6→rc7):

- **Pfad-Review bis rund 5k Zeilen ist gelöst.** Auf unbekanntem Delphi-Bestandscode (7 Units
  aus 2026, nach dem Wissensstand des Modells) fanden `/code-review` und engineering in
  sechs von sechs Läufen alle sechs eingebauten Fehler.
- **Große Diffs verlieren Funde.** Bei 4.097 geänderten Zeilen in 151 Dateien verfehlt ein
  Lauf ein bis vier von sechs; bei 1.988 Zeilen null bis zwei.
- **Die Lücke ist meist keine Lesefrage.** Die Zeile von P2 (eine verengte `except`-Klausel)
  stand in fünf von fünf Läufen im Kontext und wurde nie erkannt; den vendorten Code, der den
  `TypeError` wirft, öffnete keiner von acht Läufen. P4 (ein Resolver-Flag) fand nur der eine
  Lauf, der `factory.py` las. Eine Bitte im Systemprompt („prüfe die Gegenstelle") änderte
  daran nichts.
- **Aufteilen plus mitgegebene Gegenstellen wirkt.** In einem Paket von 591 Zeilen fand
  `/code-review` mit mechanisch gesammeltem Kontext erstmals P2 und P4 (je einmal in zwei
  Läufen). Derselbe Kontext über den ganzen Diff brachte nichts. Aufteilen allein fand so
  viel wie ein ganzer Lauf, kostete für drei Code-Pakete zusammen 1,43 USD (ein ganzer Lauf im
  Mittel 1,06 USD) und fand als einziger Lauf die echte Regression R2.

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
die Lauf-ID `<JJJJ-MM-TT>-<HHMMSS>-<kurz-sha>-<4 Zufallszeichen>`. Dazu schreibt der Lauf
Hilfscommits unter `refs/deep-review/<lauf>/` in das Repo des Nutzers; `cleanup` löscht sie,
und der Bootstrap nennt beide Orte.

| Datei | schreibt | Inhalt |
| --- | --- | --- |
| `plan.json` | `plan` | `_meta`, `range` (aufgelöst, `<base>..<target>`, beim Wurzel-Commit nur `<target>`), `base` (gezählte Basis: Merge-Basis, beim Wurzel-Commit der leere Baum), `target`, `log_base` (aufgelöste BASIS für die Commit-Messages), `profile`, `focus`, `split`, `split_at`, `packet_size`, `changed_lines`, `packets` (je `id`, `files`, `changed_lines`, `range`, `reused_from`), `file_keys` (je Datei ein Schlüssel), `not_reviewed` (Dateien mit Grund) |
| `packets/<id>.md` | `counterparts` | Kopfzeile, Bereich und Dateien des Pakets, Gegenstellen je geänderter Stelle, Zahl der nicht aufgelösten |
| `results/<id>.json` | `record` | `_meta` mit `packet`, `tool`; `findings` als Liste (`file`, `line`, `summary`, `failure_scenario`) |
| `findings.json` | `merge` | `_meta`, `findings` als Liste mit `file`, `line`, `summary`, `failure_scenario`, `packets` — die Felder, die `fix-task` von `/code-review` liest (Spec 27) |
| `audit.json` | `audit` | `_meta`, `complete`, `missing` (Pakete ohne Ergebnis), `stale` (Ergebnis zu einem anderen Plan), `lost_findings`, `report_mismatch` |
| `report.md` | Hauptagent nach `assets/report-template.md` | Bericht mit Kopfzeile |

JSON schreibt das Skript mit `ensure_ascii=False`, festen Schlüsseln in fester Reihenfolge und
repo-relativen POSIX-Pfaden; `_meta` trägt Skill, Schema-Version und Kommando (Kopf-Regel,
Spec 00 §1). Committet wird nur auf Wunsch eine Kopie des Berichts unter `docs/reviews/`.

## Approach

**Eiserne Regel:** *Kein Bericht nennt sich vollständig, solange ein Paket des Plans kein vom
Skript angenommenes Ergebnis hat — und kein Fund eines Pakets fehlt in `findings.json`.*

### Skill-Struktur

```
skills/deep-review/
├── SKILL.md                         Ablauf, Eiserne Regel, Profile und Fokus, Contract, Anti-Rationalisierung, Abgrenzung
├── references/packets.md            Schnittregel, Schwellen, Paket-IDs, Datei-Schlüssel, Paket-Bereiche, --since
├── references/counterparts.md       was je Sprache gesammelt wird und was nicht; Zeilenformat des Paketblocks; Lesehilfe für den Reviewer
├── references/review-brief.md       Auftrag je Paket: Bereich, Gegenstellen-Block weitergeben, JSON-Liste zurück; Fassung ohne /code-review
├── references/delphi.md             Prüfliste Delphi: Besitz und Freigabe, Extract/OwnsObjects, 1-basierte Strings, Record-Kopien, TDateTime in Tagen, UTC gegen Ortszeit, Interface-Referenzzählung
├── assets/report-template.md        Gerüst des Berichts mit Kopfzeile in Zeile 1
└── scripts/review_kit.py            Tier 1 — plan, counterparts, record, merge, audit, cleanup

skills/review-context/SKILL.md       Abgrenzung nennt deep-review (Kontext und Soll für einen Diff vs. Pakete mit Gegenstellen)
skills/subagent-dev/SKILL.md         Merge-und-Prüfpunkt-Schritt ruft deep-review --profile checkpoint; Ersatz /code-review bleibt für Repos ohne die Skill; zeilenneutral (145 von 150 Zeilen)
skills/subagent-dev/references/checkpoints.md   „Review am Prüfpunkt" und Fix-Pfad auf die neue Schnittstelle: --profile checkpoint|standard statt --depth, findings.json statt verdicts.jsonl, --since je Datei, keine Grenze von 15 Verifikationen
skills/subagent-dev/scripts/plan_to_tasks.py   fix-task liest findings.json (Schlüssel findings); Docstring und --help ohne verdicts.jsonl (Spec 26)
specs/Spec 27 – subagent-dev-checkpoints.md   Abschnitte zur Schnittstelle nachgezogen (--depth, verdicts.jsonl, Wiederverwendungsschlüssel, „offen" nach 15 Verifikationen)
skills/debug-ledger/SKILL.md, skills/test-first/SKILL.md   Abgrenzung nennt deep-review
scripts/sync_skills.py               Tier 1, Repo-Werkzeug — deep-review in PROJECT_SKILLS
.claude/skills/deep-review/, .claude/skills/review-context/, .claude/skills/subagent-dev/, .claude/skills/debug-ledger/   Projekt-Kopien über sync_skills.py (test-first hat keine)
.claude-plugin/marketplace.json      deep-review in der skills-Liste von evaluated-dev
specs/Spec 00 – skill-foundation.md  Routing: neue Zeile „großen Bereich oder Prüfpunkt gründlich prüfen" mit deep-review in der Spalte „zuständig"; Zeile „Diff prüfen" nennt deep-review unter „nicht"; Zeile „Sicherheit": deep-review reicht Fokus security an /security-review durch und ist keine Sicherheits-Skill
README.md                            Skill-Liste von evaluated-dev; Routing-Zeile mit deep-review in der Spalte „Responsible"
docs/known-limits.md                 Abschnitt deep-review
docs/superpowers/reports/deep-review-report.md   Report: Messung bis Prototyp (steht), dazu Abnahme
evals/deep-review/evals.json         sechs Evals, siehe unten
evals/fixtures/dr-split/, dr-contract/, dr-delphi/   je fixture.json mit "git": true und README.md (prepare() committet die Basis ohne --allow-empty); dr-seeded besteht
tests/test_deep_review_kit.py        siehe Tests (Repo)
```

### Ablauf

1. **Bereich, Profil, Fokus.** Bereich `BASIS..ZIEL` aus dem Auftrag, Standard der letzte
   Commit. Ein Pfad statt eines Bereichs geht direkt an `/code-review <pfad>` (Pfad-Review
   ist gelöst, siehe Problem) und erzeugt keinen Plan. Profil `standard` (Standard) oder
   `checkpoint` (Aufruf aus subagent-dev, nur Fokus `bugs`). Fokus `bugs` (Standard),
   `security` oder `quality`, aus dem Auftrag oder `--focus`.
2. **Plan:** `review_kit.py plan --range <bereich> [--profile …] [--focus …] [--split-at N]
   [--since <lauf>[,<lauf>…]] [--soll-file <datei>] [--with-tests]`.
   - Gezählt werden hinzugefügte plus gelöschte Zeilen (`git diff --numstat --no-renames`),
     `.skills/` nie; eine Umbenennung ist eine gelöschte und eine neue Datei.
   - Nicht reviewt, mit Grund unter `not_reviewed`: Dateien ohne Quellcode (Markdown, `NEWS`,
     Bilder, `.dproj`, `.res`) und Testdateien (`test_*.py`, `*_test.py`, unter `tests/` oder
     `unittests/` ohne Rücksicht auf Groß/Klein, Delphi-Units mit einem Namenssegment
     `Test` oder `Tests` — getrennt an `.`, `_` und Großbuchstaben, also `App.Tests.Core.pas`
     ja, `Testament.pas` nein), Tests nur mit `--with-tests` — so lief die Messung.
   - Bis `split_at` (Standard 800) geänderte Zeilen, oder wenn der Schnitt nur ein Paket ergibt:
     ein Paket `p1` über den Bereich, `split: false`. Gezählt wird ab der Merge-Basis
     (`git diff <merge-base> ZIEL`), die Commit-Messages kommen aus `git log BASIS..ZIEL`. Darüber `split: true` und `packet_size` = kleiner von 600 und `split_at`.
   - **Schnittregel:** Dateien nach Pfad sortiert und nach ihrem Verzeichnis gruppiert. Gruppen
     werden in dieser Reihenfolge der Reihe nach in Pakete gefüllt, solange das Paket
     `packet_size` nicht überschreitet; ein Paket nimmt mehrere Verzeichnisse auf. Eine Gruppe,
     die allein größer ist, wird an Dateigrenzen geteilt; eine Datei wird nie geteilt, eine
     Datei über `packet_size` ist ein eigenes Paket. Vorrang: Datei ganz vor Verzeichnis
     zusammen vor Paketgröße. IDs `p1`, `p2`, … in dieser Reihenfolge.
   - **Paket-Bereich:** zwei Hilfscommits unter `refs/deep-review/<lauf>/<id>/`, gebaut über
     einen temporären Index (`GIT_INDEX_FILE`, `read-tree ZIEL`, je Paketdatei `update-index`
     auf den Stand von BASIS oder `--force-remove`, `write-tree`, `commit-tree` mit gesetzter
     Identität `deep-review <deep-review@localhost>`, `update-ref`); `von` = ZIEL mit den
     Dateien des Pakets auf dem Stand von BASIS, Message „deep-review <lauf> <id>: Basis";
     `bis` = Baum von ZIEL mit Parent `von`, Message = die Commit-Messages des Bereichs (das
     Soll). Arbeitsbaum, Index und HEAD bleiben unberührt. So sieht der Reviewer den vollen
     Code und als Änderung nur das Paket — wie im Entscheidungsexperiment (`mid..HEAD`). Ist
     ZIEL nicht HEAD oder weicht der Arbeitsbaum in Paketdateien von ZIEL ab, sagt der Bericht
     das, weil der Reviewer den Arbeitsbaum liest.
   - **Datei-Schlüssel:** je reviewte Datei ein Hash über ihren Inhalt am ZIEL und über die
     Gegenstellen-Zeilen ihrer geänderten Stellen (Signatur und `raise`-Zeilen der erreichten
     Definitionen, Schritt 3). Ändert sich eine Gegenstelle in einer späteren Task, ändert sich
     der Schlüssel des Aufrufers.
   - Fokus `security`: ein Paket `s1` über den ganzen Bereich, ohne Hilfscommits.
3. **Gegenstellen:** `review_kit.py counterparts --run <lauf>` schreibt je Paket
   `packets/<id>.md`; Sammelregel wie im Prototyp (`review-bench/counterparts.py`): eine Stelle
   steht im Block, wenn ihre Definition etwas wirft, ein geändertes Schlüsselwort-Argument hat
   oder (Delphi) Besitz oder Default-Werte zeigt. Zeilenformat in `references/counterparts.md`,
   darunter `- Gegenstelle <Name> [<datei>:<zeile>]: <Signatur>` und `  wirft: <Typen>`.
   - Python (`ast`): je Aufruf auf einer geänderten Zeile die erreichte Definition (aufgelöst
     über die Importe der Datei und voll qualifizierte Modulpfade, auch in vendortem Code), ihre
     Signatur, die erste Docstring-Zeile und ihre `raise`-Stellen transitiv im selben Modul
     (Tiefe 2); je geänderter `except`-Klausel die Ausnahmen aller Aufrufe im `try`-Block; je
     geändertem Schlüsselwort-Argument sein Weg durch die Gegenstellen bis zu den Bedingungen,
     die es prüfen (Tiefe 4). Ohne Importbezug und mit mehr als drei gleichnamigen
     Definitionen: nichts statt Raten, aber gezählt.
   - Delphi (Text): je Aufruf `Name(` oder `Obj.Name(` auf einer geänderten Zeile die
     Implementierung `procedure|function|constructor TKlasse.Name` aus der eigenen Unit und den
     Units der `uses`-Listen, ihr Kopf aus dem `interface`-Teil mit Default-Werten der Parameter
     und ihre `raise`-Zeilen. Je geänderter Zeile mit `Extract`, `Remove`, `Free`, `FreeAndNil`
     oder `SetContentStream` der Typ des Empfängers (aus Parameterliste, `var`-Abschnitt der
     Methode oder Feld der Klasse), seine Klassendeklaration mit Basisklasse und der
     `inherited Create(…)` ihres Konstruktors, falls vorhanden; erbt sie von `TObjectList<…>`
     oder `TObjectDictionary<…>`, steht der Besitz-Default der RTL dabei (`OwnsObjects`
     standardmäßig wahr).
   - Je Paket höchstens 30.000 Zeichen; Kappung mit Zahl, nie still.
4. **Review je Paket**, im Hauptkontext, in Plan-Reihenfolge:
   - Fokus `bugs`: `/code-review --max-findings all <von>..<bis>` (bei `split: false` der
     Originalbereich) mit dem Inhalt von `packets/<id>.md` und dem Auftrag aus
     `references/review-brief.md` (den Block jedem Unteragenten unverändert mitgeben); bei
     Delphi dazu `references/delphi.md`. Im Profil `checkpoint` dazu das Soll aus `--soll-file`.
   - Fokus `security`: `/security-review` einmal für `s1`, die Gegenstellen aller Dateien als
     Kontext.
   - Fokus `quality`: `/code-review` je Paket mit dem Auftrag, nur Wartbarkeit, Doppelung und
     Vereinfachung zu melden, je mit Grundlage (Projektregel, Messwert oder konkreter
     Lesefehler); `/simplify` nicht, weil es Änderungen schreibt.

   Das Ergebnis — die JSON-Liste von `/code-review` oder die Liste aus dem Brief — gibt der
   Hauptagent an `review_kit.py record --run <lauf> --packet <id> --tool <werkzeug> <datei>`;
   das Skript nimmt es nur an, wenn das Paket im Plan steht und noch kein Ergebnis hat. Ein
   Paket ohne Funde bekommt eine leere Liste, kein Weglassen.
5. **Vereinigen:** `review_kit.py merge --run <lauf>` legt Funde derselben Datei mit höchstens
   drei Zeilen Abstand zusammen und behält alle Pakete; abgestimmt wird nicht.
6. **Bericht, Audit, Aufräumen:** Bericht nach `assets/report-template.md`: Kopfzeile mit
   Lauf-ID, Bereich, Profil, Fokus und Werkzeug; Tabelle der Pakete (Dateien, Zeilen,
   Gegenstellen, Funde); je Fund eine Zeile `datei:zeile — Zusammenfassung`; „Nicht geprüft" aus
   `not_reviewed`. Dann `review_kit.py audit --run <lauf>` und `review_kit.py cleanup --run
   <lauf>` (löscht die Hilfscommits; `cleanup --stale` löscht die Refs abgebrochener Läufe).
   Übergabe: Lauf-ID, Pfad des Berichts, Zahl der Funde, Abdeckung `<Pakete mit Ergebnis>/<Pakete>`.
   Meldet das Audit eine Lücke, sagt die Übergabe „unvollständig" mit der Liste, nie „fertig".
   deep-review behebt nichts: Im Profil `checkpoint` behebt subagent-dev die Funde über
   `fix-task` (Spec 27); sonst nennt die Übergabe debug-ledger für Funde mit unklarer Ursache
   und test-first für den Regressionstest.

**Folgeläufe** (`--since <lauf>[,<lauf>…]`, Spec 27): je Datei. Hat eine Datei denselben
Datei-Schlüssel wie in einem früheren Lauf, übernimmt sie dessen Funde zu dieser Datei und
steht mit `reused_from` im Plan; steht sie in mehreren Läufen, gilt der jüngste. Die übrigen
Dateien werden nach der Schnittregel neu gepackt und reviewt. Am finalen Prüfpunkt
(`base..HEAD` über alle Läufe aus `runs`) bleiben so die Dateien, die sich seit ihrem Review
geändert haben, und die Aufrufer, deren Gegenstellen sich geändert haben.

**Profile und Fokus:**

| | wann | Werkzeug | Pakete | Gegenstellen |
| --- | --- | --- | --- | --- |
| `standard`, Fokus `bugs` | Normalfall | `/code-review --max-findings all` | ab `split_at` | ja |
| `checkpoint` | Prüfpunkt aus subagent-dev (Spec 27) | wie `standard`, `--soll-file` als Soll | ab `split_at` | ja |
| Fokus `security` | „Sicherheit", „Sicherheitsreview" | `/security-review` | ein Paket `s1` | ja, als Kontext |
| Fokus `quality` | „Wartbarkeit", „Qualität", „Code-Hygiene" | `/code-review` mit Qualitätsauftrag | ab `split_at` | nein |

### Contract

- **Abdeckung gegen den Plan.** `audit` meldet jedes Paket ohne angenommenes Ergebnis und
  jedes Ergebnis, das zu einem anderen Plan gehört (G2). Dass je Paket ein Review lief, bleibt
  Auskunft des Hauptagenten; das steht im Bericht.
- **Kein Fund verschwindet.** Jeder Fund in `results/*.json` steht in `findings.json`; `audit`
  meldet die Differenz als `lost_findings`.
- **Bericht und Daten stimmen überein.** `audit` meldet einen Bericht, der „vollständig" sagt,
  obwohl `audit.json` Lücken trägt, und Zahlen im Bericht, die nicht zu den Dateien passen.
- **Gegenstellen sind mechanisch.** `counterparts` wählt nicht nach Verdacht aus; es schreibt
  jede Stelle, die die Sammelregel trifft, und nennt die Zahl der nicht aufgelösten.
- **Nichts wird ausgeführt, nichts behoben.** Das Skript importiert und startet keinen
  Zielcode; die Hilfscommits liegen nur unter `refs/deep-review/`; die Skill schreibt keine
  Fixes und keine Commits.
- **Anti-Zeremonie-Fall:** Ein Bereich bis `split_at` Zeilen ergibt ein Paket, einen Aufruf
  von `/code-review` über den Originalbereich, keine Hilfscommits und einen Bericht von
  höchstens 20 Zeilen plus einer Zeile je Fund.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| kleinen Diff oder PR prüfen | `/code-review` (mitgeliefert) | deep-review — bringt bis `split_at` nur die Gegenstellen dazu |
| großen Bereich, Branch oder Prüfpunkt eines Plans gründlich prüfen, mit Nachweis je Paket | **deep-review** | `/code-review` über alles — verliert in großen Bereichen Funde |
| Pfad oder Modul ohne Diff prüfen | `/code-review <pfad>` | deep-review — reicht ihn nur durch |
| Kontext und Soll für einen Diff sammeln | **review-context** | deep-review — sammelt Gegenstellen je Paket, nimmt ein Soll nur mit `--soll-file` entgegen |
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
| `test_plan_single_packet_below_threshold` | dito | bis `split_at` ein Paket `p1` mit Originalbereich, `split: false`, keine Refs; `.skills/` zählt nicht |
| `test_plan_cut_rule` | dito | Gruppen in Pfadreihenfolge, mehrere Verzeichnisse je Paket, große Gruppe an Dateigrenzen geteilt, Datei über `packet_size` eigenes Paket, IDs `p1…`; `packet_size` = kleiner von 600 und `split_at` |
| `test_plan_not_reviewed` | dito | Doku und Tests unter `not_reviewed` mit Grund; `--with-tests` nimmt Tests auf; Umbenennung zählt als D und A |
| `test_plan_packet_range_shows_only_the_packet` | dito | `von..bis` ändert genau die Paketdateien (A, D, M), `bis^{tree}` = Baum von ZIEL; HEAD, Index und Arbeitsbaum unverändert; ohne Git-Identität im Repo baubar; `cleanup` und `cleanup --stale` hinterlassen keine Refs |
| `test_counterparts_python_except_and_raises` | dito | geänderte `except`-Klausel → Ausnahmen der Aufrufe im `try` samt `raise`-Zeilen im vendorten Modul, Zeile `wirft:` |
| `test_counterparts_python_flag_flow` | dito | geändertes Schlüsselwort-Argument → Weg über zwei Gegenstellen bis zur Bedingung; voll qualifizierter Modulpfad löst eindeutig auf |
| `test_counterparts_python_no_guessing` | dito | Methode mit gängigem Namen ohne Importbezug → nicht aufgelöst, gezählt |
| `test_counterparts_delphi` | dito | Aufruf → Implementierung aus einer `uses`-Unit, Kopf mit Default-Wert; `Extract` auf einem Parameter vom Typ einer `TObjectList<T>`-Ableitung → Klassendeklaration, `inherited Create(True)`, Besitz-Default; `end` in String und Kommentar ignoriert |
| `test_counterparts_cap` | dito | über 30.000 Zeichen → gekappt mit Zahl |
| `test_record_rejects_unknown_or_duplicate` | dito | unbekanntes Paket oder zweites Ergebnis → abgewiesen, nichts geschrieben |
| `test_merge_keeps_every_finding` | dito | gleiche Datei, Abstand ≤ 3 → ein Fund mit beiden Paketen; sonst zwei; `fix-task` liest `findings.json` |
| `test_since_per_file` | dito | gleicher Datei-Schlüssel → Funde übernommen, `reused_from`; geänderte Gegenstelle → Aufrufer neu; zwei frühere Läufe → der jüngere |
| `test_audit` | dito | fehlendes Ergebnis, Ergebnis zu anderem Plan, Fund fehlt in `findings.json`, Bericht „vollständig" trotz Lücke → je ein Eintrag und `complete: false`; sauber → `true` |
| `test_run_ids_do_not_collide` | dito | zwei Läufe in derselben Sekunde → verschiedene IDs |

### Evals

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-small-range-one-packet` | contract | `dr-seeded` | `file_matches` `.skills/cache/deep-review/*/plan.json` auf `"split":\s*false`; `artifact_header` auf `.skills/cache/deep-review/*/report.md`; `file_max_lines` dort 60; `git_head_unchanged` | `plan.json` schreibt nur `review_kit.py`; 60 = 20 Zeilen plus bis zu 40 Funde |
| 2 | `large-range-is-split-and-covered` | contract | `dr-split` | `file_matches` `.skills/cache/deep-review/*/plan.json` auf `"id":\s*"p3"`; `file_matches` `.skills/cache/deep-review/*/audit.json` auf `"complete":\s*true` und auf `"missing":\s*\[\]` | Prompt nennt „teile ab 200 Zeilen" → `packet_size` 200; rund 450 Zeilen in drei Verzeichnissen ergeben mindestens drei Pakete; ohne Skill weder Plan noch Audit |
| 3 | `narrowed-except-gets-callee-raises` | contract | `dr-contract` | `file_matches` `.skills/cache/deep-review/*/packets/p1.md` auf `wirft:[^\n]*TypeError` und auf `vendor/grouplib\.py` | die Fixture verengt `except (ValueError, TypeError)` vor einem Aufruf in `vendor/grouplib.py`, der `TypeError` wirft; der Paketblock entsteht nur im Skript |
| 4 | `delphi-extract-shows-ownership` | contract | `dr-delphi` | `file_matches` `.skills/cache/deep-review/*/packets/p1.md` auf `inherited Create\(True\)` und auf `TObjectList` | `TQueryTree = class(TObjectList<TNode>)` mit Konstruktor `inherited Create(True)` in `Tree.pas`; der Diff in `Query.pas` ersetzt `Remove` durch `Extract` auf einem Parameter dieses Typs |
| 5 | `security-focus-is-one-packet` | contract | `dr-contract` | `file_matches` `.skills/cache/deep-review/*/plan.json` auf `"focus":\s*"security"` und auf `"id":\s*"s1"`; `file_matches` `.skills/cache/deep-review/*/audit.json` auf `"complete":\s*true` | Plan und Audit schreibt nur das Skript; dass `/security-review` lief, prüft kein Eval (Open questions) |
| 6 | `routing-large-branch-without-skill-name` | contract | `dr-split` | `file_exists` `.skills/cache/deep-review/*/plan.json` | stochastisch: ein roter Lauf zeigt eine Kollision mit `/code-review`; ein grüner beweist nichts |

Prompts: 1 „Review base..HEAD mit deep-review.", 2 „Prüf base..HEAD mit deep-review, teile ab
200 Zeilen.", 3 und 4 „Review den letzten Commit mit deep-review.", 5 „Mach ein
Sicherheitsreview von base..HEAD mit deep-review.", 6 „Prüf base..HEAD gründlich in Paketen auf
Fehler und weise nach, dass jedes Paket angeschaut wurde." Die Fixtures sind Git-Repos mit Tag
`base` und README.md; `dr-split` hat rund 450 geänderte Zeilen in drei Verzeichnissen, `dr-contract`
und `dr-delphi` je unter 100. Die Läufe im Workspace sind ein einziger je Eval; ein
abgebrochener `plan` wird mit `--run <lauf>` fortgesetzt statt neu begonnen, damit der Glob den
richtigen Lauf trifft. Vor der Abnahme läuft jeder Eval einmal ohne Skill (Spec 18).

### Abnahme der Trefferquote

Die Evals prüfen den Vertrag; ob der Reviewer mit dem Paketblock den Fehler meldet, ist
stochastisch und gehört in die Abnahme. Der Report misst mit
`docs/superpowers/reports/review-bench/` auf `py-diff` (pip 25.0→25.1, 6 eingebaute + 2
echte Fehler) und `dl-diff` (DelphiMVCFramework rc6→rc7, 6 eingebaute), je zwei Läufe
deep-review im Profil `standard` gegen die gemessene Basislinie von `/code-review` über den
ganzen Bereich (Mittel 4,5 bzw. 5,0 von 6, Kosten im Mittel 1,06 bzw. 2,33 USD), dazu je ein
Lauf auf `dr-contract` und `dr-delphi`. *Annahme:* Abnahme, wenn deep-review im Mittel
mindestens so viele eingebaute Fehler findet wie die Basislinie, auf `py-diff` P2 oder P4 in
mindestens einem Lauf, und je Lauf höchstens das Doppelte der Basislinie kostet. Jede Stufe,
die gegenüber ihrer Abschaltung (Pakete, Gegenstellen, Delphi-Prüfliste) keinen messbaren
Unterschied bringt, fliegt raus.

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

**Tests als eigene Pakete.** Verworfen für den Standard: die Messung lief ohne sie, und jedes
Paket kostet einen `/code-review`-Lauf. Mit `--with-tests` möglich.

**Zwei Läufe vereinigen.** Bringt `py-diff` auf 5/6 zum doppelten Preis, ohne P2. Bleibt als
Option für Nutzer, die mehr ausgeben wollen; nicht Teil der Skill.

**Eine eigene Review-Skill je Fokus** (Sicherheit, Qualität). Verworfen: dieselben Pakete,
derselbe Plan, dasselbe Audit wären dreifach; die Werkzeuge gibt es mitgeliefert.

## Out of scope

Eigene Such- oder Verifikationsagenten, Abdeckung je Funktion, Sättigung und Schätzung von
Restfehlern (Fassung vom 2026-10-30); Pfad-Review mit eigenem Plan (gelöst durch
`/code-review <pfad>`); Gegenstellen für TypeScript, Java und andere Sprachen; Fixes und
Commits (Hauptagent, subagent-dev); Prüfpunkte planen (subagent-dev); Taint-Analyse; Ausführen
von Zielcode.

## Open questions

*Annahme:* `split_at` 800 und Paketgröße 600 Zeilen. Gemessen ist nur: 591–651 Zeilen je
Paket wirkten, 1.988 Zeilen am Stück verloren null bis zwei Funde, 4.097 Zeilen ein bis
vier. Zwischen 800 und 2.000 ist nichts gemessen.

*Annahme:* 30.000 Zeichen je Paketblock (gemessen: 28,7 KB für das Paket mit 591 Zeilen,
49 KB für den ganzen pip-Diff) und drei Zeilen Abstand beim Vereinigen; beide ungemessen
in ihrer Wirkung.

*Annahme:* Der Gegenstellen-Block erreicht die Unteragenten von `/code-review`, weil der
Hauptagent ihn im Aufruf mitgibt. Im Prototyp ging er über `--append-system-prompt` mit der
Bitte, ihn weiterzugeben, und jedes Paket lief in einem eigenen `claude -p` mit frischem
Kontext. Die Skill reviewt alle Pakete nacheinander in einem Hauptkontext; ob sich der Kontext
dabei so füllt, dass spätere Pakete schlechter werden, ist ungemessen.

*Annahme:* `/code-review` nimmt einen Bereich über Refs unter `refs/deep-review/` so an wie
über Tags (gemessen nur mit Tags) und läuft aus einer Skill heraus wie als getippter Befehl.
`--max-findings all` bleibt danach als Wahl des Nutzers gesetzt, und ohne Stufe nimmt
`/code-review` die zuletzt getippte (Hilfetext der CLI 2.1.316); die Skill sagt das im Bericht
und setzt nichts zurück.

*Annahme:* Der Delphi-Sammler (Text-Scanner) liefert auf DelphiMVCFramework brauchbare
Gegenstellen; gemessen ist nur der Python-Sammler. D1 (Besitz bei `Extract`) fand ein Lauf
mit Prompt-Auftrag, drei von fünf ohne ihn nicht — ein Lauf, kein Beleg.

*Annahme:* Fokus `security` ist ein einziges Paket, weil `/security-review` seinen Bereich
selbst wählt (ausstehende Änderungen des Branches); ob es einen Bereich annimmt, ist nicht
geprüft. Sicherheit und Qualität sind nicht gemessen; von den eingebauten Sicherheitsfehlern
der Diff-Szenarien fand `/code-review` die doppelten Header (D2) und das Secure-Cookie (D5) in
beiden Läufen, die Payload-Grenze (D4) in einem von zwei.

*Annahme:* Name `deep-review` bleibt, weil Spec 27 und subagent-dev ihn schon nennen; die
Skill ist schmaler, als der Name sagt.

Laufzeit und Kosten der Evals sind ungemessen: Jeder Eval ruft `/code-review` auf (auf
`dr-seeded` 0,29–0,45 USD je Lauf), Eval 2 mindestens dreimal; der Runner bricht nach 600
Sekunden ab (`evalkit/dispatch.py`).

Die Streuung bleibt: Mit Gegenstellen fand je Lauf einer von P2 und P4, nicht beide. Zwei
Läufe je Zelle sind kein Mittelwert.

evaluated-dev ist immer an und hat das längste Listing; deep-review kommt mit einer weiteren
Description dazu (Spec 20).

## Next steps

Plan mit `impl-plan` (16) neu; der Plan vom 2026-10-30 (23 Tasks) wird ersetzt, Task 1
(`dr-seeded`, `test_seeded_fixtures`, Basislinie) bleibt gebaut. Reihenfolge: `review_kit.py
plan` mit Schnittregel und Hilfscommits, `counterparts` für Python, dann die Delphi-Hälfte,
dann `record`, `merge`, `audit`, `cleanup`, dann SKILL.md und Nachbarn (subagent-dev mit
checkpoints.md, `fix-task` und Spec 27), zuletzt Evals und Abnahme mit review-bench. Bau nach
`skill-forge` (17) Schritt 3 bis 7.
