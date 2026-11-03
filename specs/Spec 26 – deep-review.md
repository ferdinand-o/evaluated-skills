# Spec 26: deep-review — `/code-review` in Paketen, mit den Verträgen der Gegenstellen

Skill-Spezifikation · Zyklus 26 · Entscheidung: keine eigene Such-Pipeline — die Skill steuert die mitgelieferten Reviewer und ergänzt nur, was ihnen in der Messung fehlte: große Bereiche schneidet ein Tier-1-Skript in Pakete, und je Paket sammelt es die Gegenstellen der geänderten Aufrufe (Definition, `raise`-Stellen, Besitz, Weg eines Flags), die der Reviewer sonst nicht öffnet · Abgeglichen mit Spec 00 und Spec 27 · Neu gefasst nach der Messung vom 2026-11-01/02 (`docs/superpowers/reports/deep-review-report.md`); ersetzt die Fassung vom 2026-10-30 (Inventar, Nonce, Suchagenten, gestufte Verifikation, Sättigung) · Überarbeitet nach unabhängigem Review (2026-11-02, Opus: Schnittregel mit Paketgröße und IDs festgelegt, je Fixture eine weitere Datei, `--since` je Datei mit Gegenstellen im Schlüssel samt Nachbarn Spec 27, checkpoints.md und `fix-task`, 28 statt 34 Läufe, Sicherheitsfunde berichtigt, Tests standardmäßig nicht reviewt wie in der Messung, Sammelregel wie im Prototyp, Fokus `security` als ein Paket `s1` mit Audit, keine Fixes in der Skill, stochastische Fundprüfungen aus Eval 3 und 4 in die Abnahme, Hilfscommits mit Identität, Message und Aufräumen, `--max-findings all` als bekannte Grenze, test-first ohne Projekt-Kopie, `findings.json` mit Kopf) · Nachgezogen an den Bau (2026-11-03): kein `plan --run`, fortgesetzt wird mit `counterparts`, `record`, `merge` und `audit` über `--run`; die Paket-Bereiche baut `counterparts`, und `s1` bekommt beim Wurzel-Commit und nach `--since` Hilfscommits; `--since` nur beim Anlegen, mit Abdeckungskette (`base_blob`/`target_blob` als `<mode>:<sha>`), `reused_chain`, `outside`, `run` je Fund, Gleichstand über die mtime der Ergebnisse und Profilen nach `SINCE_PROFILES`; `checkpoint` nur mit `--soll-file`; Datei-Schlüssel mit Zeilennummern der Gegenstellen und Ziel eines Symlinks, bei `quality` nur Inhalt; `record` normalisiert Zeilen, `merge` nicht transitiv; `audit.json` mit `coverage`; Bericht mit fünf Kopffeldern, Pflichtzeilen, Längengrenze ohne Kopf- und Kommentarzeilen und der Regel für „vollständig"; Delphi-Sammler und `DELPHI_RELEASES` wie gebaut; `not_reviewed` mit den Gründen für Nicht-UTF-8-Pfade; `/security-review` nur bei passendem Umfang, sonst „Review ohne /security-review"; `fix-task` liest weiter `verdicts.jsonl`; Tests und Evals wie gebaut

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
Sicherheit `/security-review`, wenn sein Umfang dem Plan entspricht (Ablauf Schritt 4). Ohne
diese Befehle (claude.ai, andere Agenten) läuft dieselbe Paketfolge als Review im
Hauptkontext nach `references/review-brief.md`; der Bericht sagt dann „Review ohne
/code-review", beim Fokus `security` „Review ohne /security-review".

Gate-Grade: Paketplan, Gegenstellen, Abdeckung aller Pakete und Konsistenz des Berichts
meldet `review_kit.py audit` (G2, Exit 1 bei Lücke); dass je Paket wirklich ein Review lief,
verlangt die SKILL.md (G1). Kein Hook. Plugin `evaluated-dev`; dazu Projekt-Kopie unter
`.claude/skills/`, weil dieses Repo das Plugin abschaltet und Cloud-Sitzungen nur
Projekt-Kopien laden (`scripts/sync_skills.py`).

Ablage (Spec 00 §1), alles Ephemera unter `.skills/cache/deep-review/<lauf>/`. `<lauf>` ist
die Lauf-ID `<JJJJ-MM-TT>-<HHMMSS>-<kurz-sha>-<4 Zufallszeichen>` (UTC). Dazu schreibt
`counterparts` Hilfscommits unter `refs/deep-review/<lauf>/` in das Repo des Nutzers;
`cleanup` löscht sie, und der Bootstrap nennt beide Orte.

| Datei | schreibt | Inhalt |
| --- | --- | --- |
| `plan.json` | `plan`; `counterparts` trägt `range` der Pakete und `notes` nach, `cleanup` setzt `range` auf `null` zurück | `_meta` (dazu `run`, im Profil `checkpoint` `soll_file`), `range` (aufgelöst, `<base>..<target>`, beim Wurzel-Commit nur `<target>`), `base` (gezählte Basis: Merge-Basis, beim Wurzel-Commit der leere Baum), `target`, `log_base` (aufgelöste BASIS für die Commit-Messages, beim Wurzel-Commit `null`), `root` (Wurzel-Commit: jedes Paket hat `range: null` und bekommt Hilfscommits mit leerer Basis), `profile`, `focus`, `split`, `split_at`, `packet_size`, `changed_lines`, `packets` (je `id`, `files`, `changed_lines`, `range`, `reused_from` — immer `null`, übernommen wird je Datei), `file_keys` (je reviewte Datei `key`, `changed_lines`, `base_blob`, `target_blob`, `reused_from`; übernommen dazu `reused_chain`, `findings` und, wenn vorhanden, `outside`), `not_reviewed` (Dateien mit Grund), `notes` (erst nach `counterparts`: je Paket `target_not_head`, `worktree_differs` oder `worktree_unknown`, je `{packet, kind, files, text}`) |
| `packets/<id>.md` | `counterparts` | Kopfzeile, Bereich und Dateien des Pakets, Gegenstellen je geänderter Stelle, Zahl der nicht aufgelösten |
| `results/<id>.json` | `record` | `_meta` mit `run`, `packet`, `tool` und `plan` (Fingerabdruck aus Lauf, Bereich, Profil, Fokus und Paketen mit Dateien); `findings` als Liste (`file`, `line`, `summary`, `failure_scenario`) |
| `findings.json` | `merge` | `_meta` mit `run` und `plan`, `findings` als Liste mit `file`, `line`, `summary`, `failure_scenario` — die Felder, die `fix-task` von subagent-dev liest (Spec 27) —, dazu `packets`, `reused_from` (der Lauf, der einen übernommenen Fund gemeldet hat) und `sources` (jeder ursprüngliche Fund) |
| `audit.json` | `audit` | `_meta` mit `run`, `plan` und `report`, `complete`, `coverage` (`covered`: Pakete mit angenommenem Ergebnis, `total`: Pakete), `missing` (Pakete ohne Ergebnis), `stale` (Ergebnis, das nicht angenommen ist, etwa zu einem anderen Plan, je `{packet, reason}`), `lost_findings`, `report_mismatch` |
| `report.md` | Hauptagent nach `assets/report-template.md` | Bericht mit Kopfzeile und Pflichtzeilen (Ablauf Schritt 6) |

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
├── references/packets.md            Grenzwerte, Bereich und Zählung, Nicht reviewt, Schnittregel, Paket-Bereiche, Datei-Schlüssel, --since, Vereinigen, Fortsetzen, cleanup
├── references/counterparts.md       was je Sprache gesammelt wird und was nicht; Zeilenformat des Paketblocks; Lesehilfe für den Reviewer
├── references/review-brief.md       Auftrag je Paket: Bereich, Gegenstellen-Block weitergeben, JSON-Liste zurück; Fokus security mit Umfangsprüfung; Fassung ohne /code-review; Rückgabeformat
├── references/delphi.md             Prüfliste Delphi: Besitz und Freigabe, Extract/OwnsObjects, 1-basierte Strings, Record-Kopien, TDateTime in Tagen, UTC gegen Ortszeit, Interface-Referenzzählung, verschluckte Exceptions
├── assets/report-template.md        Gerüst des Berichts mit Kopfzeile in Zeile 1 und den Pflichtzeilen
└── scripts/review_kit.py            Tier 1 — plan, counterparts, record, merge, audit, cleanup

skills/review-context/SKILL.md       Abgrenzung nennt deep-review (Kontext und Soll für einen Diff vs. Pakete mit Gegenstellen)
skills/subagent-dev/SKILL.md         Merge-und-Prüfpunkt-Schritt ruft deep-review --profile checkpoint; Ersatz /code-review bleibt für Repos ohne die Skill; zeilenneutral (145 von 150 Zeilen)
skills/subagent-dev/references/checkpoints.md   „Review am Prüfpunkt" und Fix-Pfad auf die neue Schnittstelle: --profile checkpoint|standard statt --depth, --soll-file im Profil checkpoint, findings.json als Eingabe von fix-task (verdicts.jsonl bleibt lesbar), --since je Datei nach SINCE_PROFILES, Nachprüfung eines Fixes über <prüfpunkt-basis>..HEAD mit --since, keine Grenze von 15 Verifikationen
skills/subagent-dev/scripts/plan_to_tasks.py   fix-task liest findings.json (Schlüssel findings) und weiter verdicts.jsonl und die /code-review-Liste (Kompatibilität); Docstring und --help nennen alle drei
specs/Spec 27 – subagent-dev-checkpoints.md   Abschnitte zur Schnittstelle nachgezogen (--depth, verdicts.jsonl, Wiederverwendungsschlüssel, „offen" nach 15 Verifikationen)
skills/debug-ledger/SKILL.md, skills/test-first/SKILL.md   Abgrenzung nennt deep-review
scripts/sync_skills.py               Tier 1, Repo-Werkzeug — deep-review in PROJECT_SKILLS
.claude/skills/deep-review/, .claude/skills/review-context/, .claude/skills/subagent-dev/, .claude/skills/debug-ledger/   Projekt-Kopien über sync_skills.py (test-first hat keine)
.claude-plugin/marketplace.json      deep-review in der skills-Liste von evaluated-dev
specs/Spec 00 – skill-foundation.md  Routing: neue Zeile „großen Bereich oder Prüfpunkt gründlich prüfen" mit deep-review in der Spalte „zuständig"; Zeile „Diff prüfen" nennt deep-review unter „nicht"; Zeile „Sicherheit": deep-review reicht Fokus security an /security-review durch und ist keine Sicherheits-Skill
README.md                            Skill-Liste von evaluated-dev; Routing-Zeile mit deep-review in der Spalte „Responsible"
docs/known-limits.md                 Abschnitt deep-review
docs/superpowers/reports/deep-review-report.md   Report: Messung bis Prototyp (steht), Bau mit Prüfpunkten (steht), dazu Abnahme
evals/deep-review/evals.json         sechs Evals, siehe unten
evals/fixtures/dr-split/, dr-contract/, dr-delphi/   je fixture.json mit "git": true und README.md (prepare() committet die Basis ohne --allow-empty); dr-seeded besteht
tests/test_deep_review_kit.py        siehe Tests (Repo)
```

### Ablauf

1. **Bereich, Profil, Fokus.** Bereich `BASIS..ZIEL` aus dem Auftrag, Standard der letzte
   Commit (`HEAD`). Eine Revision `X` gilt als `X^..X`, beim Wurzel-Commit als leerer
   Baum..`X`; `A...B` lehnt das Skript ab. Ein Pfad statt eines Bereichs geht direkt an
   `/code-review <pfad>` (Pfad-Review ist gelöst, siehe Problem) und erzeugt keinen Plan.
   Profil `standard` (Standard) oder `checkpoint` (Aufruf aus subagent-dev, nur Fokus `bugs`
   und nur mit `--soll-file`). Fokus `bugs` (Standard), `security` oder `quality`, aus dem
   Auftrag oder `--focus`.
2. **Plan:** `review_kit.py plan --range <bereich> [--profile …] [--focus …] [--split-at N]
   [--since <lauf>[,<lauf>…]] [--soll-file <datei>] [--with-tests]`.
   - `plan` legt immer einen neuen Lauf an und hat kein `--run`. Die erste Ausgabezeile ist
     `Lauf: <lauf>`. Ein gescheitertes `plan` hinterlässt keinen Laufordner: ohne reviewte
     Datei („nichts zu reviewen"), Profil `checkpoint` ohne `--soll-file` oder mit einem
     anderen Fokus als `bugs`, ein `--since` auf einen fehlenden oder unlesbaren Lauf — je
     Exit 1. `--soll-file` steht danach in `_meta.soll_file`.
   - Gezählt werden hinzugefügte plus gelöschte Zeilen (`git diff --numstat --no-renames`),
     `.skills/` nie, Binärdateien mit 0; eine Umbenennung ist eine gelöschte und eine neue Datei.
   - Nicht reviewt, mit Grund unter `not_reviewed`: Dateien ohne Quellcode (Doku: `.md`,
     `.markdown`, `.rst` und ohne Endung `NEWS`, `CHANGES`, `CHANGELOG`, `AUTHORS`, `LICENSE`,
     `COPYING`; Bilder; `.dproj`, `.res`) und Testdateien (`test_*.py`, `*_test.py`, unter
     `tests/` oder `unittests/` ohne Rücksicht auf Groß/Klein, Delphi-Units mit einem
     Namenssegment `Test` oder `Tests` — getrennt an `.`, `_`, Wortgrenzen und Ziffern, also
     `App.Tests.Core.pas` und `HTMLTest.pas` ja, `Testament.pas` nein), Tests nur mit `--with-tests` — so lief die Messung.
     Ein Pfad, der kein UTF-8 ist, steht in escapter Form da: als Quelldatei mit dem Grund
     „Quelldatei mit Nicht-UTF-8-Pfad — nicht reviewt", sonst mit „Pfad ist kein UTF-8".
   - Bis `split_at` (Standard 800) geänderte Zeilen, oder wenn der Schnitt nur ein Paket ergibt:
     ein Paket `p1` über den Bereich, `split: false`. Gezählt wird ab der Merge-Basis
     (`git diff <merge-base> ZIEL`), die Commit-Messages kommen aus `git log BASIS..ZIEL`. Darüber `split: true` und `packet_size` = kleiner von 600 und `split_at`.
   - **Schnittregel:** Dateien nach Pfad sortiert und nach ihrem Verzeichnis gruppiert. Gruppen
     werden in der Reihenfolge ihres ersten Auftretens der Reihe nach in Pakete gefüllt, solange
     das Paket `packet_size` nicht überschreitet; ein Paket nimmt mehrere Verzeichnisse auf. Eine
     Gruppe, die allein größer ist, wird an Dateigrenzen geteilt, ihre letzte Teilmenge kann
     sich das Paket mit der nächsten Gruppe teilen; eine Datei wird nie geteilt, eine Datei über
     `packet_size` ist ein eigenes Paket. Vorrang: Datei ganz vor Verzeichnis zusammen vor
     Paketgröße. IDs `p1`, `p2`, … in dieser Reihenfolge.
   - **Paket-Bereich:** baut `counterparts` (Schritt 3), nicht `plan`. Im Plan steht der
     Originalbereich als `range` des Pakets nur bei `split: false` ohne Wurzel-Commit (auch für
     `s1`); dann gibt es keine Hilfscommits. Bei `split: true`, beim Wurzel-Commit (auch `p1`
     und `s1`) und nach einem `--since`, das etwas übernommen hat (auch ein einzelnes Paket und
     `s1`), ist `range` bis dahin `null`, und `counterparts` baut zwei Hilfscommits unter
     `refs/deep-review/<lauf>/<id>/`, über einen temporären Index (`GIT_INDEX_FILE`, `read-tree
     ZIEL`, je Paketdatei Modus und Blob der gezählten Basis oder entfernt, `write-tree`,
     `commit-tree` mit gesetzter Identität `deep-review <deep-review@localhost>`,
     `update-ref`); `von` = ZIEL mit den Dateien des Pakets auf dem Stand der Basis (beim
     Wurzel-Commit leer), Parent ZIEL, Message „deep-review <lauf> <id>: Basis"; `bis` = Baum
     von ZIEL mit Parent `von`, Message = die Commit-Messages des Bereichs (das Soll).
     Arbeitsbaum, Index und HEAD bleiben unberührt. So sieht der Reviewer den vollen Code und
     als Änderung nur das Paket — wie im Entscheidungsexperiment (`mid..HEAD`). Ausnahme:
     Kollidiert eine Paketdatei auf dem Stand der Basis als Datei/Ordner mit einem Pfad
     außerhalb des Pakets, fehlt dieser fremde Pfad in `von` und `bis`. Vorhandene Bereiche
     bleiben, solange ihre Refs stehen; fehlen sie (`cleanup`, anderer Worktree), baut
     `counterparts` neu. Weil der Reviewer den Arbeitsbaum liest, schreibt jedes
     `counterparts` je Paket `notes`: `target_not_head` (ZIEL ist nicht HEAD),
     `worktree_differs` (Paketdateien im Arbeitsbaum weichen von ZIEL ab) oder
     `worktree_unknown` (Index fehlt, Arbeitsbaum nicht geprüft); der Bericht nennt sie.
   - **Datei-Schlüssel:** je reviewte Datei ein SHA-256 über ihren Inhalt am ZIEL (aus Git, nie
     aus dem Arbeitsbaum) und über die Zeilen der Gegenstellen-Einträge ihrer geänderten
     Stellen (Schritt 3): Überschrift, Signatur, `wirft:` und `raise … at <datei>:<zeile>`. Die
     Zeilennummern gehören dazu: Ändert sich eine Gegenstelle in einer späteren Task, auch nur
     ihre Zeile, ändert sich der Schlüssel des Aufrufers. Ein Symlink zählt mit seinem Link und
     dem Inhalt seines Ziels im Repo, Teil für Teil aufgelöst, auch über Ordner-Symlinks
     (höchstens 40 Sprünge; ein Ziel außerhalb, ein Ordner oder ein Kreis gibt eine eigene
     Marke); ein Submodul zählt mit seinem Commit, eine gelöschte Datei mit eigener Marke. Bei
     Fokus `quality`, der keine Gegenstellen sammelt, zählt nur der Inhalt. Dazu stehen je Datei
     `base_blob` und `target_blob`, der Stand an der gezählten Basis und am ZIEL als
     `<mode>:<sha>`, `absent` oder `gitlink:<commit>`, für die Abdeckungskette von `--since`.
     `plan` sammelt dafür die Gegenstellen über den ganzen Bereich.
   - Fokus `security`: ein Paket `s1` über den ganzen Bereich, nie geteilt; Hilfscommits nur
     beim Wurzel-Commit und nach `--since` (Paket-Bereich).
3. **Gegenstellen:** `review_kit.py counterparts --run <lauf>` baut zuerst je Paket den
   Paket-Bereich, dann schreibt es `packets/<id>.md` und gibt je Paket
   `<id>: <bereich> · <pfad> · <k> Gegenstellen, <gezeigt> gezeigt, <u> nicht aufgelöst` aus;
   diesen Bereich bekommt das Review. Der Code kommt aus Git am ZIEL, gesucht wird im ganzen
   Repo ohne `.skills/`. Sammelregel wie im Prototyp (`review-bench/counterparts.py`): eine
   Stelle steht im Block, wenn ihre Definition etwas wirft, ein geändertes
   Schlüsselwort-Argument hat oder (Delphi) Besitz oder Default-Werte zeigt. Zeilenformat in
   `references/counterparts.md`, darunter `- Gegenstelle <Name> [<datei>:<zeile>]: <Signatur>`
   und `  wirft: <Typen>`. Fokus `quality` sammelt nicht; der Block sagt „Gegenstellen nicht
   gesammelt (Fokus quality)."
   - Python (`ast`): je Aufruf auf einer geänderten Zeile die erreichte Definition (aufgelöst
     über die Importe der Datei und voll qualifizierte Modulpfade, auch in vendortem Code;
     höchstens zwei Definitionen je Aufruf, ein Klassenaufruf erreicht `__init__`), ihre
     Signatur, die erste Docstring-Zeile und ihre `raise`-Stellen transitiv im selben Modul
     (Tiefe 2, bis zu acht Zeilen); je geänderter `except`-Klausel die Ausnahmen aller Aufrufe
     im `try`-Block; je geändertem Schlüsselwort-Argument sein Weg durch die Gegenstellen bis
     zu den Bedingungen, die es prüfen (Tiefe 4, höchstens zwölf Zeilen; endet er an einer
     mehrdeutigen Gegenstelle, wird das gezählt). Ohne Importbezug und mit mehr als drei
     gleichnamigen Definitionen: nichts statt Raten, aber gezählt.
   - Delphi (Text): je Aufruf `Name(`, `Obj.Name(` oder `Name<T>(` auf einer geänderten Zeile,
     im Rumpf einer Routine auch ohne Klammer (`Flush;`, `Queue.Drain;`; ohne Empfänger nicht,
     wenn der Name dort einen Wert benennt), die Implementierung
     `procedure|function|constructor|destructor [TKlasse.]Name`. Gesucht wird zuerst in den
     geschachtelten Routinen, die an der Stelle sichtbar sind, dann in der eigenen Klasse, der
     eigenen Unit und den Units der `uses`-Listen (die zuletzt genannte verdeckt frühere); bei
     einem Empfänger mit bekanntem Typ nur in dessen Klassenkette. Gezeigt werden ihr Kopf aus
     der Deklaration (`interface`-Teil oder Klassenrumpf, Überladungen nach Namen und Typen der
     Parameter) mit Default-Werten, `deklariert:` mit deren Zeile und ihre `raise`-Zeilen
     (Tiefe 2, in derselben Unit). Ein Aufruf auf einer Unit außerhalb des Repos
     (`System.SysUtils.Format(`) oder auf einer Unit, deren Blöcke nicht aufgehen, ergibt
     nichts und wird gezählt; ebenso ein unbekannter Empfänger mit mehr als drei gleichnamigen
     Methoden, ohne Klammer schon mit einer.
   - Delphi, Besitz: je geänderter Zeile mit einem Aufruf aus `DELPHI_RELEASES` (`Extract`,
     `ExtractPair`, `ExtractItem`, `Remove`, `Delete`, `Clear`, `Dequeue`, `Pop`, `Free`,
     `FreeAndNil`, `SetContentStream`) der Typ des Empfängers (aus Parameterliste,
     `var`-Abschnitt, Inline-`var`, Feld oder Property der Klasse, Unit-Variable oder `Self`),
     seine Klassendeklaration mit Basisklasse und die `inherited Create(…)` ihrer Konstruktoren,
     über bis zu vier Klassen der Kette; erbt sie von `TObjectList<…>`, `TObjectDictionary<…>`,
     `TObjectQueue<…>`, `TObjectStack<…>` oder `TObjectList` (Contnrs), steht der
     Besitz-Default der RTL dabei (`TObjectList`, `TObjectQueue`, `TObjectStack`:
     `OwnsObjects` standardmäßig wahr; `TObjectDictionary`: Besitz nur über `Ownerships`).
     Ein geändertes `inherited Create(…)` im Konstruktor einer solchen Klasse ist eine eigene
     Stelle (`inherited Create auf Self: <Klasse>`). Gelesen wird nur der erste Zweig von
     `{$IFDEF}` …, `{$I}`-Dateien nicht; geänderte Zeilen in anderen Zweigen stehen mit Zahl
     in der Dateiliste.
   - Je Paket höchstens 30.000 Zeichen, Kopfzeile eingeschlossen; die Dateiliste bekommt
     höchstens die Hälfte, außer die Stellen brauchen weniger. Kappung mit Zahl, nie still.
4. **Review je Paket**, im Hauptkontext, in Plan-Reihenfolge:
   - Fokus `bugs`: `/code-review --max-findings all <bereich>`, `<bereich>` wie ihn
     `counterparts` für das Paket ausgibt (bei `split: false` ohne Wurzel-Commit und ohne
     übernommene Datei der Originalbereich, sonst `<von>..<bis>`), mit dem Inhalt von
     `packets/<id>.md` und dem Auftrag aus `references/review-brief.md` (den Block jedem
     Unteragenten unverändert mitgeben); bei Delphi dazu `references/delphi.md`. Im Profil
     `checkpoint` dazu das Soll aus `--soll-file`.
   - Fokus `security`: `/security-review` prüft HEAD gegen die Merge-Basis mit `origin/HEAD`
     und nimmt keinen Bereich. Es läuft deshalb einmal für `s1`, die Gegenstellen aller
     Dateien als Kontext, nur wenn sein Umfang dem Plan entspricht: ZIEL ist HEAD (unter
     `notes` kein `target_not_head`), `origin/HEAD` ist vorhanden, `base` ist gleich
     `git merge-base HEAD origin/HEAD`, und unter `notes` steht kein `worktree_differs` und
     kein `worktree_unknown`. Sonst prüft der Hauptagent `s1` selbst über den Bereich aus
     `counterparts` nach `references/review-brief.md` (Eingaben von außen, Rechte, Geheimnisse,
     Injektion); das Werkzeug heißt dann „Review ohne /security-review".
   - Fokus `quality`: `/code-review` je Paket mit dem Auftrag, nur Wartbarkeit, Doppelung und
     Vereinfachung zu melden, je mit Grundlage (Projektregel, Messwert oder konkreter
     Lesefehler); `/simplify` nicht, weil es Änderungen schreibt.

   Das Ergebnis — die JSON-Liste von `/code-review` oder die Liste aus dem Brief — gibt der
   Hauptagent an `review_kit.py record --run <lauf> --packet <id> --tool <werkzeug> <datei|->`
   (`-` liest stdin; Datei und stdin als UTF-8, ein BOM zählt nicht). `<werkzeug>` ist, was
   lief: `/code-review`, `/security-review`, „Review ohne /code-review" oder „Review ohne
   /security-review". Das Skript nimmt das Ergebnis nur an, wenn das Paket im Plan steht und
   noch kein Ergebnis hat, und nur als ganze gültige Liste; sonst schreibt es nichts. Dabei
   wird `file` repo-relativ (`\` wird `/`, `./` fällt weg, `..` und Pfade außerhalb des Repos
   sind ungültig) und `line` eine Zahl, ein Bereich `"a-b"` oder `null` (`12`, `L12`, `12-14`,
   `12 - 14`, `12–14`, `L12-L14`, `12 bis 14`; vertauschte Enden sortiert, `12-12` wird 12;
   `"near 40"` oder `"12, 15"` machen die Liste ungültig). Ein Paket ohne Funde bekommt eine
   leere Liste, kein Weglassen.
5. **Vereinigen:** `review_kit.py merge --run <lauf>` legt Funde derselben Datei zusammen,
   nicht transitiv: In Zeilenfolge eröffnet ein Fund eine Gruppe, sein Ende ist der Anker; ein
   späterer Fund kommt hinein, wenn sein Anfang höchstens drei Zeilen nach dem Anker liegt
   oder seine Spanne die eines Glieds überschneidet. 10 und 12 werden ein Fund, aus 10, 13 und
   16 werden zwei, `20-22` und 25 einer; Funde ohne Zeile bleiben für sich. Übernommene Funde
   (`--since`) zählen wie eigene. Alle Pakete bleiben in `packets`, alle ursprünglichen Funde in
   `sources`; abgestimmt wird nicht.
6. **Bericht, Audit, Aufräumen:** Bericht `report.md` im Laufordner nach
   `assets/report-template.md`:
   - Zeile 1 die Kopfzeile `<!-- skill: deep-review | schema: 1 | generated: … | run: <lauf> |
     range: <range aus plan.json> | profile: <profil> | focus: <fokus> | tool: <werkzeug> -->`,
     also nach den festen Feldern die fünf Felder Lauf-ID, Bereich, Profil, Fokus und Werkzeug
     (wie bei `record`).
   - Pflichtzeilen, je genau einmal: `Funde: <N>` (Einträge in `findings.json`), je Fund eine
     Zeile `` - `datei:zeile` — Zusammenfassung `` (ohne Zeile `` - `datei` — … ``), die
     Tabelle der Pakete (Dateien, Zeilen, Gegenstellen, Funde), `- Hinweise: <paket> <kind>
     (<dateien>); …`, `- Übernommen (--since): <n> Dateien aus <Läufe>, <m> Funde`,
     `- Nicht geprüft: …` aus `not_reviewed` (Gründe zu Quelldateien mit ihren Dateien, die
     übrigen mit ihrer Zahl) und `- Abdeckung: <a>/<b> — vollständig|unvollständig`. Hinweise,
     Übernommen und Nicht geprüft sagen ohne Inhalt `keine`.

   Dann `review_kit.py audit --run <lauf> [--report <datei>]`. Es schreibt `audit.json` immer
   und endet mit Exit 1, wenn `complete` falsch ist; `complete` ist wahr nur, wenn `missing`,
   `stale`, `lost_findings` und `report_mismatch` leer sind. Am Bericht prüft es die
   Kopfzeile; `Funde:` gegen `findings.json`; `Abdeckung:` gegen `coverage`, „unvollständig"
   dort nur mit Lücke; je Fund seine Fundzeile; dass `- Hinweise:` jedes Paar `<paket> <kind>`
   aus `notes` nennt; dass `- Übernommen (--since):` n (Dateien mit `reused_from` in
   `file_keys`) und m (deren `findings` plus `outside`) nennt; bei `split: false` höchstens 20
   Zeilen plus eine je Fund, wobei die Kopfzeile und Zeilen nur aus HTML-Kommentaren nicht
   zählen. `- Nicht geprüft:` und die Zahlen der Pakettabelle prüft `audit` nicht.

   **„vollständig":** Bei einer Lücke (`missing`, `stale` oder `lost_findings`) darf der
   Bericht außerhalb von HTML-Kommentaren und Fundzeilen nicht „vollständig" behaupten. Als
   Behauptung zählt das ganze Wort und seine Adjektivformen (`vollständige`, `vollständigen`,
   `vollständiger`, `vollständiges`, `vollständigem`; groß oder klein, nicht
   „Vollständigkeit"). Als Verneinung zählt „nicht", „kein…" (auch „keineswegs") oder „un"
   davor, mit höchstens zwei Wörtern dazwischen („nicht mehr vollständig", „noch nicht ganz
   vollständig", „unvollständig"); Hervorhebung mit `*`, `_` oder `` ` `` zählt nicht. Eine
   Fundzeile ist nur eine Zeile, deren `datei:zeile` ein Fund aus `findings.json` ist.

   Zuletzt `review_kit.py cleanup --run <lauf>` (löscht die Hilfscommits des Laufs;
   `cleanup --stale` löscht alle Refs unter `refs/deep-review/`, `cleanup --stale --run <lauf>`
   die aller anderen Läufe; danach steht `range` der betroffenen Pakete wieder auf `null`).
   Übergabe: Lauf-ID, Pfad des Berichts, Zahl der Funde, Abdeckung `<covered>/<total>` aus
   `coverage` in `audit.json`, bei einem Review im Hauptkontext das Werkzeug wörtlich.
   Meldet das Audit eine Lücke, sagt die Übergabe „unvollständig" mit der Liste, nie „fertig".
   deep-review behebt nichts: Im Profil `checkpoint` behebt subagent-dev die Funde über
   `fix-task` (Spec 27); sonst nennt die Übergabe debug-ledger für Funde mit unklarer Ursache
   und test-first für den Regressionstest.

**Fortsetzen eines Laufs:** nie mit einem zweiten `plan` über denselben Bereich, das gäbe einen
zweiten Lauf, sondern mit `--run <lauf>`: `counterparts` ist wiederholbar (vorhandene Bereiche
bleiben, solange ihre Refs stehen, `packets/*.md` wird überschrieben); `record` nimmt je Paket
genau ein Ergebnis an; `merge` und `audit` sind wiederholbar. Welche Pakete fehlen, nennt
`audit` unter `missing`.

**Folgeläufe** (`--since <lauf>[,<lauf>…]`, Spec 27): je Datei und nur beim Anlegen eines
Laufs. `--since` wirkt auf den Lauf, den dieses `plan` gerade anlegt, und nur, solange er
frisch ist (keine übernommenen Dateien, ohne `results/`, `packets/` und Refs); einem
bestehenden Lauf lässt es sich nicht nachträglich geben. Eine Datei übernimmt die Funde
früherer Läufe, wenn alles zutrifft:

- Der frühere Lauf hat denselben Fokus und ein Profil nach `SINCE_PROFILES`: Ein
  `standard`-Plan übernimmt aus `standard`- und `checkpoint`-Läufen, ein `checkpoint`-Plan nur
  aus `checkpoint`-Läufen, denn ein `standard`-Lauf hatte nur die Commit-Messages als Soll.
  Andere Läufe werden still übergangen; eine Kette darf beide erlaubten Profile mischen.
- Er hat die Datei mit demselben Datei-Schlüssel reviewt: Ihr Paket hat ein angenommenes
  Ergebnis, oder er hat sie selbst übernommen. Ohne Ergebnis wird nichts übernommen.
- Die **Abdeckungskette** schließt sich: Der `base_blob` des passenden Laufs gleicht dem
  `base_blob` des neuen Plans, oder dem `target_blob` eines anderen angegebenen Laufs, der die
  Datei reviewt hat, und so weiter bis zur neuen Basis (neuer Lauf `t0..t2`, Lauf A über
  `t1..t2` reicht allein nicht; mit A0 über `t0..t1` schließt sich `t0→t1→t2`). Die Stände
  sind `<mode>:<sha>`, `absent` oder `gitlink:<commit>`; ein Symlink und eine Datei mit
  denselben Bytes sind verschiedene Stände.

Passen mehrere Läufe, gilt der jüngste: zuerst der Zeitteil der Lauf-ID, bei Gleichstand die
jüngste mtime seiner `results/*.json`, zuletzt die ID selbst. Die Kette ist die kürzeste, bei
gleicher Länge die über jüngere Läufe. Die Datei steht dann in `file_keys` mit `reused_from`
(der passende Lauf), `reused_chain` (die Läufe der Kette, der jüngste zuerst) und `findings`:
den Funden aller Kettenglieder zu ihr, gleiche `file`, `line` und `summary` nur einmal, je Fund
mit `run`, dem Lauf, der ihn gemeldet hat, über weitere Folgeläufe unverändert weitergegeben.
Funde eines früheren Pakets zu Dateien außerhalb des Pakets (etwa zur Definition einer
Gegenstelle) stehen getrennt unter `outside`, je `{finding, packet_files, file_blob}`, und
werden bei jedem Folgelauf neu geprüft: übernommen nur, wenn alle `packet_files` übernommen
werden, der tragende Lauf in ihrer `reused_chain` steht und die Fund-Datei am neuen ZIEL
denselben `file_blob` hat; sonst sieht das neue Review die Stelle wieder. Die übrigen Dateien
werden nach der Schnittregel neu gepackt; alle Pakete bekommen `range: null` und über
`counterparts` Hilfscommits, `split` ist `true`, `notes` entfallen, `changed_lines` bleibt die
Zahl des ganzen Bereichs. Bleibt keine Datei übrig, ist `packets` leer, und `plan` sagt
„Pakete: keine — alle Dateien übernommen". Ein fehlender oder unlesbarer früherer Plan bricht
den Folgelauf ab, auch wenn er wegen Fokus oder Profil übergangen würde. Am finalen Prüfpunkt
(`base..HEAD` über alle Läufe aus `runs`) bleiben so die Dateien, die sich seit ihrem Review
geändert haben, und die Aufrufer, deren Gegenstellen sich geändert haben. Die Nachprüfung
eines Fixes läuft über `<prüfpunkt-basis>..HEAD` mit `--since` auf den Lauf des Prüfpunkts
(Spec 27, Fix-Pfad in `checkpoints.md`).

**Profile und Fokus:**

| | wann | Werkzeug | Pakete | Gegenstellen |
| --- | --- | --- | --- | --- |
| `standard`, Fokus `bugs` | Normalfall | `/code-review --max-findings all` | ab `split_at` | ja |
| `checkpoint` | Prüfpunkt aus subagent-dev (Spec 27) | wie `standard`, `--soll-file` (Pflicht) als Soll | ab `split_at` | ja |
| Fokus `security` | „Sicherheit", „Sicherheitsreview" | `/security-review`, wenn sein Umfang dem Plan entspricht; sonst „Review ohne /security-review" im Hauptkontext | ein Paket `s1`, nie geteilt | ja, als Kontext |
| Fokus `quality` | „Wartbarkeit", „Qualität", „Code-Hygiene" | `/code-review` mit Qualitätsauftrag | ab `split_at` | nein |

### Contract

- **Abdeckung gegen den Plan.** `audit` meldet jedes Paket ohne angenommenes Ergebnis und
  jedes Ergebnis, das zu einem anderen Plan gehört (G2); `coverage` zählt die Pakete mit
  angenommenem Ergebnis gegen alle. Angenommen ist ein Ergebnis, wenn `_meta` Lauf, Paket,
  Fingerabdruck des Plans und ein Werkzeug trägt und jeder Fund gültig ist — dieselbe Regel
  für `audit`, `merge` und `--since`. Dass je Paket ein Review lief, bleibt Auskunft des
  Hauptagenten; das steht im Bericht.
- **Kein Fund verschwindet.** Jeder Fund in `results/*.json` und jeder übernommene Fund
  (`findings` und `outside` in `file_keys`) steht in `findings.json`; `audit` meldet die
  Differenz als `lost_findings`.
- **Bericht und Daten stimmen überein.** `audit` meldet einen Bericht, der „vollständig" sagt,
  obwohl `audit.json` Lücken trägt, eine Kopfzeile, die nicht zum Plan passt, und Zahlen,
  Fundzeilen, Hinweise und übernommene Dateien im Bericht, die nicht zu den Dateien passen
  (Ablauf Schritt 6).
- **Gegenstellen sind mechanisch.** `counterparts` wählt nicht nach Verdacht aus; es schreibt
  jede Stelle, die die Sammelregel trifft, und nennt die Zahl der nicht aufgelösten.
- **Nichts wird ausgeführt, nichts behoben.** Das Skript importiert und startet keinen
  Zielcode; die Hilfscommits liegen nur unter `refs/deep-review/`; die Skill schreibt keine
  Fixes und keine Commits.
- **Anti-Zeremonie-Fall:** Ein Bereich bis `split_at` Zeilen ohne Wurzel-Commit ergibt ein
  Paket, einen Aufruf von `/code-review` über den Originalbereich, keine Hilfscommits und einen
  Bericht von höchstens 20 Zeilen (`REPORT_BASE_LINES`) plus einer Zeile je Fund; die
  Kopfzeile und Zeilen nur aus HTML-Kommentaren zählen nicht. Mit HEAD als ZIEL und sauberem
  Arbeitsbaum gibt es auch keine `notes`.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| kleinen Diff oder PR prüfen | `/code-review` (mitgeliefert) | deep-review — bringt bis `split_at` nur die Gegenstellen dazu |
| großen Bereich, Branch oder Prüfpunkt eines Plans gründlich prüfen, mit Nachweis je Paket | **deep-review** | `/code-review` über alles — verliert in großen Bereichen Funde |
| Pfad oder Modul ohne Diff prüfen | `/code-review <pfad>` | deep-review — reicht ihn nur durch |
| Kontext und Soll für einen Diff sammeln | **review-context** | deep-review — sammelt Gegenstellen je Paket, nimmt ein Soll nur mit `--soll-file` entgegen |
| wann zwischen Tasks reviewt wird | **subagent-dev** (Spec 27) | deep-review prüft, plant keine Prüfpunkte |
| Sicherheitsaudit eines ganzen Systems | `/security-review`, trailofbits | deep-review — reicht Fokus `security` an `/security-review` durch, wenn dessen Umfang dem Plan entspricht |
| bestätigter Fund mit unklarer Ursache | **debug-ledger** | deep-review meldet, diagnostiziert nicht |
| Regressionstest zu einem Fund | **test-first** | deep-review schreibt keine Tests |

Rückverweise beim Bau, je mit dem Wort deep-review: review-context, subagent-dev,
debug-ledger, test-first (alle im Strukturblock oben).

### Tests (Repo)

Die Tabelle nennt die Tests, die den Vertrag tragen; `tests/test_deep_review_kit.py` hat
weitere zu den Randfällen aus den Prüfpunkten.

| Test | Datei | prüft |
| --- | --- | --- |
| `test_seeded_fixtures` | `tests/test_deep_review_kit.py` | besteht (Task 1 des Plans vom 2026-10-30) |
| `test_run_ids_do_not_collide` | dito | zwei Läufe in derselben Sekunde → verschiedene IDs |
| `test_plan_single_packet_below_threshold` | dito | bis `split_at` ein Paket `p1` mit Originalbereich, `split: false`, keine Refs; `.skills/` zählt nicht |
| `test_plan_cut_rule` | dito | Gruppen in Pfadreihenfolge, mehrere Verzeichnisse je Paket, große Gruppe an Dateigrenzen geteilt, Datei über `packet_size` eigenes Paket, IDs `p1…`; `packet_size` = kleiner von 600 und `split_at` |
| `test_plan_not_reviewed` | dito | Doku und Tests unter `not_reviewed` mit Grund; `--with-tests` nimmt Tests auf; Umbenennung zählt als D und A |
| `test_h03_non_utf8_source_file_has_its_own_reason` | dito | Quelldatei mit Nicht-UTF-8-Pfad hat ihren eigenen Grund |
| `test_h02_root_commit_plan_needs_helper_commits` | dito | Wurzel-Commit: `root: true`, `range` nur `<ziel>`, Pakete mit `range: null`, auch `s1` |
| `test_plan_packet_range_shows_only_the_packet` | dito | `von..bis` ändert genau die Paketdateien (A, D, M), `bis^{tree}` = Baum von ZIEL; HEAD, Index und Arbeitsbaum unverändert; ohne Git-Identität im Repo baubar; `cleanup` und `cleanup --stale` hinterlassen keine Refs |
| `test_plan_packet_range_root_split_false_and_target_not_head` | dito | bis `split_at` ohne Wurzel-Commit der Originalbereich ohne Hilfscommits; Wurzel-Commit mit Hilfscommits; ZIEL nicht HEAD → `target_not_head` |
| `test_k5_missing_index_is_one_unknown_note` | dito | Index fehlt → ein Hinweis `worktree_unknown` |
| `test_counterparts_python_except_and_raises` | dito | geänderte `except`-Klausel → Ausnahmen der Aufrufe im `try` samt `raise`-Zeilen im vendorten Modul, Zeile `wirft:` |
| `test_counterparts_python_flag_flow` | dito | geändertes Schlüsselwort-Argument → Weg über zwei Gegenstellen bis zur Bedingung; voll qualifizierter Modulpfad löst eindeutig auf |
| `test_counterparts_python_no_guessing` | dito | Methode mit gängigem Namen ohne Importbezug → nicht aufgelöst, gezählt |
| `test_counterparts_delphi` | dito | Aufruf → Implementierung aus einer `uses`-Unit, Kopf mit Default-Wert; `Extract` auf einem Parameter vom Typ einer `TObjectList<T>`-Ableitung → Klassendeklaration, `inherited Create(True)`, Besitz-Default; `end` in String und Kommentar ignoriert |
| `test_n03_calls_without_parentheses_and_generic_calls` | dito | Delphi: Aufrufe ohne Klammer und `Name<T>(` |
| `test_n04_nested_routines_visible_only_inside_their_routine` | dito | Delphi: geschachtelte Routinen nur in ihrer Routine sichtbar |
| `test_n11_changed_inherited_create_of_an_owning_list` | dito | geändertes `inherited Create(…)` einer besitzenden Liste → eigene Stelle mit Besitz-Default |
| `test_n13_object_stack_queue_and_contnrs_list` | dito | `TObjectStack<…>`, `TObjectQueue<…>` und `TObjectList` aus Contnrs mit Besitz-Default |
| `test_cp8b_f2_extract_pair_on_owning_dictionary_gets_owner_entry` | dito | `ExtractPair` auf einem besitzenden `TObjectDictionary`; eigene `ExtractKey`/`ExtractValue` ohne Besitz-Hinweis |
| `test_cp9b_f5_delete_clear_extractitem_dequeue_pop_get_owner_entries` | dito | `Delete`, `Clear`, `ExtractItem`, `Dequeue`, `Pop` bekommen Besitz-Einträge |
| `test_counterparts_cap` | dito | über 30.000 Zeichen → gekappt mit Zahl |
| `test_file_keys_content_and_counterparts` | dito | Schlüssel aus Inhalt am ZIEL (nicht Arbeitsbaum) und den Gegenstellen-Zeilen der eigenen Datei; geänderte Gegenstelle → anderer Schlüssel; gelöschte Datei mit eigenem Schlüssel |
| `test_f5_symlink_key_follows_the_real_file` | dito | Schlüssel eines Symlinks folgt der echten Datei |
| `test_cp5b_f2_symlink_key_follows_through_directory_links` | dito | dasselbe über Ordner-Symlinks; ein Link auf einen Ordner ergibt eine Marke |
| `test_record_rejects_unknown_or_duplicate` | dito | unbekanntes Paket oder zweites Ergebnis → abgewiesen, nichts geschrieben |
| `test_cp6_f01_line_normalised_and_paths_with_spaces` | dito | `line` normalisiert zu Zahl, `"a-b"` oder `null`; Pfade mit Leerzeichen im Bericht |
| `test_merge_keeps_every_finding` | dito | gleiche Datei, Abstand ≤ 3 → ein Fund mit beiden Paketen; sonst zwei; `20-22` und 25 ein Fund; jeder Fund unter `sources`; die Felder, die `fix-task` liest |
| `test_cp6_f07_merge_groups_do_not_chain` | dito | `merge` nicht transitiv: 10, 13, 16 sind zwei Funde |
| `test_cp6b_f6_merge_joins_findings_inside_a_members_span` | dito | ein Fund in der Spanne eines Glieds gehört zur Gruppe |
| `test_since_per_file` | dito | gleicher Datei-Schlüssel → Funde übernommen, `reused_from`; geänderte Gegenstelle → Aufrufer neu; zwei frühere Läufe → der jüngere; ein jüngerer ohne Ergebnis verdeckt den älteren nicht |
| `test_f1_since_reuses_only_when_coverage_chain_closes` | dito | Übernahme nur, wenn sich die Abdeckungskette schließt; Funde aller Kettenglieder; gelöschte Datei mit anderer Basis nicht |
| `test_cp5b_f3_mode_counts_in_the_coverage_chain` | dito | Symlink und Datei mit denselben Bytes sind verschiedene Stände |
| `test_cp9_f1_since_standard_reuses_checkpoint_runs` | dito | `SINCE_PROFILES`: `standard` übernimmt aus `standard` und `checkpoint`, `checkpoint` nur aus `checkpoint`; Fokus gleich |
| `test_f3_plan_since_only_on_a_fresh_run` | dito | `--since` nur auf einem frischen Lauf |
| `test_f4_youngest_run_by_time_then_results_mtime` | dito | Gleichstand der Lauf-IDs → mtime der Ergebnisse |
| `test_cp6b_f4_outside_findings_are_rechecked_on_every_hop` | dito | `outside` wird bei jedem Folgelauf neu geprüft |
| `test_cp9b_f2_reused_findings_name_the_run_that_found_them` | dito | übernommene Funde tragen `run`, `findings.json` nennt ihn in `sources[].reused_from` |
| `test_cp9b_f3_checkpoint_profile_needs_a_soll_file` | dito | `plan --profile checkpoint` ohne `--soll-file` → Exit 1, kein Lauf |
| `test_audit` | dito | fehlendes Ergebnis, Ergebnis zu anderem Plan, Fund fehlt in `findings.json`, Bericht „vollständig" trotz Lücke → je ein Eintrag und `complete: false`; sauber → `true` |
| `test_cp6_f09_header_names_range_profile_focus_and_tool` | dito | Kopfzeile mit Lauf, Bereich, Profil, Fokus und Werkzeug |
| `test_cp6_f08_claim_is_the_whole_word_and_not_negated` | dito | „vollständig" nur als ganzes Wort und nicht verneint |
| `test_cp6b_f2_inflected_claims_count` | dito | gebeugte Formen zählen als Behauptung |
| `test_cp6b_f3_negation_with_emphasis_and_words_between` | dito | Verneinung mit Hervorhebung und Wörtern dazwischen |
| `test_cp8b_f3_audit_checks_notes_reused_and_comment_lines` | dito | `audit` prüft Hinweise und Übernommen; Kommentarzeilen zählen nicht zur Längengrenze |
| `test_report_template` | dito | Vorlage: Kopfzeile in Zeile 1 mit allen Pflichtfeldern, Pflichtzeilen, Spalten der Pakettabelle |
| `test_cp8_f1_filled_single_packet_report_stays_within_line_limit` | dito | eine ausgefüllte Vorlage bei `split: false` bleibt in der Längengrenze |
| `test_main_subcommands_exit_codes` | dito | Unterbefehle und Exit-Codes; `--since` auf einen fehlenden oder kaputten Lauf hinterlässt keinen Lauf |
| `test_evals_and_fixtures` | dito | jeder Eval mechanisch durchgespielt (plan, counterparts, record mit `[]`, merge, Bericht, audit, cleanup), Assertions gegen die echte Ausgabe; Fixtures mit Tag `base`, Größe und Verzeichnissen |
| `test_fix_task_reads_deep_review_findings` | `tests/test_subagent_dev_plan_to_tasks.py` | `fix-task` liest `findings.json` von deep-review |
| `test_fix_task_old_forms_stay_readable_next_to_deep_review_findings` | dito | `verdicts.jsonl` und die `/code-review`-Liste bleiben lesbar |

### Evals

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-small-range-one-packet` | contract | `dr-seeded` | `file_matches` `.skills/cache/deep-review/*/plan.json` auf `"split":\s*false`; `artifact_header` auf `.skills/cache/deep-review/*/report.md`; `file_max_lines` dort 60; `git_head_unchanged` | `plan.json` schreibt nur `review_kit.py`; 60 = 20 Zeilen plus bis zu 40 Funde |
| 2 | `large-range-is-split-and-covered` | contract | `dr-split` | `file_matches` `.skills/cache/deep-review/*/plan.json` auf `"id":\s*"p3"`; `file_matches` `.skills/cache/deep-review/*/audit.json` auf `"complete":\s*true` und auf `"missing":\s*\[\]` | Prompt nennt „teile ab 200 Zeilen" → `packet_size` 200; rund 450 Zeilen in drei Verzeichnissen ergeben genau drei Pakete; ohne Skill weder Plan noch Audit |
| 3 | `narrowed-except-gets-callee-raises` | contract | `dr-contract` | `file_matches` `.skills/cache/deep-review/*/packets/p1.md` auf `wirft:[^\n]*TypeError` und auf `vendor/grouplib\.py` | die Fixture verengt `except (ValueError, TypeError)` vor einem Aufruf in `vendor/grouplib.py`, der `TypeError` wirft; der Paketblock entsteht nur im Skript |
| 4 | `delphi-extract-shows-ownership` | contract | `dr-delphi` | `file_matches` `.skills/cache/deep-review/*/packets/p1.md` auf `inherited Create\(True\)` und auf `TObjectList` | `TQueryTree = class(TObjectList<TNode>)` mit Konstruktor `inherited Create(True)` in `Tree.pas`; der Diff in `Query.pas` ersetzt `Remove` durch `Extract` auf einem Parameter dieses Typs; ein anderes Besitzmuster als das Beispiel in `references/delphi.md` |
| 5 | `security-focus-is-one-packet` | contract | `dr-contract` | `file_matches` `.skills/cache/deep-review/*/plan.json` auf `"focus":\s*"security"` und auf `"id":\s*"s1"`; `file_matches` `.skills/cache/deep-review/*/audit.json` auf `"complete":\s*true` | Plan und Audit schreibt nur das Skript; der Workspace hat kein `origin/HEAD`, also läuft der Review im Hauptkontext mit `--tool "Review ohne /security-review"`; welches Werkzeug lief, prüft kein Eval (Open questions) |
| 6 | `routing-large-branch-without-skill-name` | contract | `dr-split` | `file_exists` `.skills/cache/deep-review/*/plan.json` | stochastisch: ein roter Lauf zeigt eine Kollision mit `/code-review`; ein grüner beweist nichts |

Prompts: 1 „Review base..HEAD mit deep-review.", 2 „Prüf base..HEAD mit deep-review, teile ab
200 Zeilen.", 3 und 4 „Review den letzten Commit mit deep-review.", 5 „Mach ein
Sicherheitsreview von base..HEAD mit deep-review.", 6 „Prüf base..HEAD gründlich in Paketen auf
Fehler und weise nach, dass jedes Paket angeschaut wurde." Die Fixtures sind Git-Repos mit Tag
`base` und README.md; `dr-split` hat rund 450 geänderte Zeilen in drei Verzeichnissen (469;
mit dem Standard von 800 ein Paket `p1`), `dr-contract` und `dr-delphi` je unter 100. Die
Läufe im Workspace sind ein einziger je Eval; ein abgebrochener Lauf wird mit `counterparts`,
`record`, `merge` und `audit` über `--run <lauf>` fortgesetzt statt mit einem zweiten `plan`
neu begonnen, damit der Glob den richtigen Lauf trifft (ein gescheitertes `plan` hinterlässt
keinen Laufordner). Vor der Abnahme läuft jeder Eval einmal ohne Skill (Spec 18).

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
selbst wählt: HEAD gegen die Merge-Basis mit `origin/HEAD`, ohne einen Bereich anzunehmen. Die
Skill ruft es deshalb nur, wenn dieser Umfang dem Plan entspricht, sonst reviewt der
Hauptagent `s1` selbst („Review ohne /security-review"); welcher Weg lief, prüft kein Eval.
Sicherheit und Qualität sind nicht gemessen; von den eingebauten Sicherheitsfehlern
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

Plan `docs/superpowers/plans/2026-10-30-deep-review.md`, neu gefasst mit 16 Tasks statt der
23 vom 2026-10-30. Gebaut sind Task 1 (`dr-seeded`, `test_seeded_fixtures`,
Basislinie) und Tasks 2–13 mit den Prüfpunkten 1–9 (Report, Abschnitt „Bau"): `review_kit.py`
mit `plan`, `counterparts` für Python und Delphi, `record`, `merge`, `audit`, `cleanup`, die
References, die Berichtsvorlage, die Evals mit Fixtures und die Nachbarn (subagent-dev mit
checkpoints.md, `fix-task` und Spec 27). Offen: Task 14 (known-limits, mit den offenen Punkten
der Prüfpunkte aus dem Report), Task 15 (SKILL.md, Plugin, Projekt-Kopie) und Task 16 (Abnahme
mit review-bench, Evals mit und ohne Skill). Bau nach `skill-forge` (17) Schritt 3 bis 7.
