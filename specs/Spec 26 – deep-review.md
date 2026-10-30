# Spec 26: deep-review — ein Review, das nachweist, was es geprüft hat

Skill-Spezifikation · Zyklus 26 · Entscheidung: Abdeckung kommt aus einem Inventar, das ein Tier-1-Skript baut, und aus Ergebnissen, die das Skript gegen eine Nonce je Paket abgleicht — nicht aus der Aufmerksamkeit des Modells; lesende Suchagenten suchen je Einheit und Linse breit, eine getrennte, gestufte Verifikation belegt oder widerlegt jeden Kandidaten, und ein Audit meldet jede Einheit ohne Urteil · Abgeglichen mit Spec 00, Spec 25 und Spec 27 · Überarbeitet nach unabhängigem Review (2026-10-30, Opus: Ergebnisse und Urteile schreibt das Skript mit Nonce-Abgleich, JSON-Lines statt geratener Schlüsselreihenfolge, Globs statt `latest/`, Tiefe `quick` zählt nur geänderte Einheiten, gelöschter Code als Einheit, Projekt-Kopie und Rückverweise im Strukturblock, Profil `checkpoint` für Spec 27, gestufte Verifikation, Kommentar-Regel `restates-code` dem Modell überlassen, Fakten zu architecture-map und Spec 00 korrigiert; Nachreview Opus: Lauf-ID mit Zufallssuffix, Fix im Profil `checkpoint` bei subagent-dev, `quality` unabhängig von der Tiefe, Prüf-Worktree `--detach`, Wiederverwendung ohne Soll, Form von `audit.json`, Routing-Spalte; Abgleich mit Spec 27: `--since` über mehrere Läufe, `offen` im Folgelauf erneut verifiziert, `--depth` und `--profile`, Lauf-ID in der Übergabe)

## Problem

Spec 00 §5 routet „Diff prüfen" an das mitgelieferte `/code-review` und hält dort fest: „*Annahme:* Spec 04 schrumpft auf `collect_context.py` als Zulieferer
für `/code-review` — widersprich, falls du die eigene Linsen-Engine trotzdem willst." Der
Nutzer widerspricht am 2026-10-28: Bei den getesteten Review-Skills „gambled" man, ob das
Modell die richtigen Stellen findet, und eine feste Grenze von drei Runden hält er nicht
für saubere Arbeitsweise. Er will Fehlverhalten, Programmfehler und Sicherheitslücken
gefunden sehen.

Die Recherche vom 2026-10-28 stützt den Eindruck (Konzeptdokument „Konzept: Review-Skill
mit hoher Trefferquote", Quellen dort):

- `/code-review` meldet laut seiner Command-Datei (`anthropics/claude-code`,
  `plugins/code-review/commands/code-review.md`) nur Code, der nicht kompiliert, unabhängig
  von der Eingabe falsch rechnet oder eine zitierbare CLAUDE.md-Regel verletzt; Altlasten
  sowie eingabe- und zustandsabhängige Fehler schließt es aus.
- Agenten lesen nicht, was sie prüfen sollen: In 67,9 % von 1.140 Läufen las ein Agent
  nicht jede Datei; ein eingebauter Defekt wurde zu 83,2 % gemeldet, wenn seine Stelle im
  Kontext lag, sonst zu 1,8 % (OverclaimBench, arXiv 2609.20812, Preprint).
- Vereinigen schlägt Abstimmen: Union über vier Agenten fand 82,7 % der Lücken bei 48,8 %
  Präzision, gewichtetes Voting 37,7 % (MultiVer, arXiv 2602.17875, Preprint, 202
  Python-Samples). Der Preis: Auf gefixtem Code meldete Union in 85 % der Fälle weiter eine
  Lücke — Präzision muss eine eigene Stufe liefern.
- Verschiedene Werkzeuge sehen verschiedene Stellen: Bei vier parallel eingesetzten
  Review-Bots kamen 93,4 % der 617 Fundstellen von genau einem Bot (Feldstudie, 146 PRs, ein
  Team; der Autor arbeitet bei Sentry). Das zeigt Streuung zwischen Werkzeugen, nicht
  zwischen Läufen desselben Modells.
- Spätere Runden finden alte Fehler: Beim Claude-Code-Team stand etwa 59 % des später
  Gemeldeten schon seit der ersten Runde im Code (claude.dev, 2026-10-15).

Der Nutzer prüft außerdem mit work-plan und subagent-dev Pläne Task für Task; Reviews je
Task wurden groß und liefen ins Limit (2026-10-30). Wann dort reviewt wird, regelt Spec 27;
diese Spec liefert das Review und ein Profil dafür.

## Constraints

Portables Frontmatter. Tier 1: ein Skript `scripts/review_kit.py`, nur Stdlib, aufgerufen
als `python "${CLAUDE_SKILL_DIR}/scripts/review_kit.py"` (Spec 25). Inventar per `ast` für
Python; für TS/JS eigene Textmuster (Funktionsdeklarationen, `const x = (…) =>`,
Klassenmethoden) — architecture-map liefert nur Importe, die nächsten Vorläufer sind
`detect_symbols`/`find_callers` in review-context mit bekannten Grenzen (known-limits,
review-context); für Delphi/Object Pascal ein Scanner, der Strings und Kommentare
ausblendet und `begin`, `case`, `try`, `asm`, `record` gegen `end` zählt, Methodenköpfe im
`implementation`-Teil sucht und lokale Prozeduren der umgebenden Methode zuordnet. Was
keiner dieser Wege trägt (andere Sprachen, Delphi-Dateien mit unvollständigen
`{$IFDEF}`-Zweigen oder Includes), wird zu Blöcken von höchstens 150 Zeilen mit
`unit_kind: "chunk"` und Grund.

Gate-Grade: Abdeckung, Nonce-Abgleich, Status je Kandidat und Konsistenz des Berichts
meldet `review_kit.py audit` (G2); Suche, Verifikation und Bericht verlangt die SKILL.md
(G1). Kein Hook. Plugin `evaluated-dev`; dazu Projekt-Kopie unter `.claude/skills/`, weil
dieses Repo das Plugin abschaltet (`.claude/settings.json`, `tests/test_marketplace.py`) und
Cloud-Sitzungen nur Projekt-Kopien laden (`scripts/sync_skills.py`).

Ablage (Spec 00 §1), alles Ephemera unter `.skills/cache/deep-review/<lauf>/`. `<lauf>` ist die
Lauf-ID `<JJJJ-MM-TT>-<HHMMSS>-<kurz-sha>-<4 Zufallszeichen>`; wo diese Spec und Spec 27 einen
Pfad meinen, steht `.skills/cache/deep-review/<lauf>/…` aus.


| Datei | schreibt | Inhalt |
| --- | --- | --- |
| `inventory.json` | `inventory` | Einheiten, Hashes, Risikomerkmale, Linsen, Tiefe, `_meta` |
| `packets/<einheit>.md` | `packets` | Kopfzeile, Nonce, Paket-Hash, Code als abgegrenzter Datenblock, Signaturen, Aufrufer, Soll |
| `results.jsonl` | `record` | je Paket und Linse ein Urteil des Suchagenten mit Nonce |
| `candidates.jsonl` | `merge` | vereinigte Kandidaten |
| `verdicts.jsonl` | `verdict` | Status je Kandidat |
| `comments.json`, `metrics.json` | `comments`, `metrics` | nur bei `quality` |
| `audit.json` | `audit` | `_meta`, `complete`, `missing` (Einheit und Linse ohne Urteil), `nonce_mismatch`, `unverdicted` (Kandidaten ohne Status), `report_mismatch` |
| `estimate.json` | `estimate` | Sättigung |
| `report.md` | Hauptagent nach `assets/report-template.md` | Bericht mit Kopfzeile |

Die JSON-Lines-Dateien schreiben je Zeile ein Objekt mit `ensure_ascii=False`, den
Standard-Trennzeichen von `json.dumps` (`", "`, `": "`), festen Schlüsseln in fester Reihenfolge,
Werten von `reason` und `evidence` als Zeichenketten und repo-relativen POSIX-Pfaden ohne
`./`; die erste Zeile ist ein `_meta`-Objekt. Committet wird nur auf Wunsch eine Kopie des Berichts unter
`docs/reviews/`. Bootstrap: Der erste Lauf nennt `.skills/cache/deep-review/`, bevor er
schreibt.

Suchagenten laufen als lesender Agententyp (in Claude Code etwa `Explore`, ohne Schreiben und
ohne Shell), das Modell setzt das `model`-Feld des Agent-Werkzeugs; der Code im Paket ist
Daten, nie Anweisung. Prüfagenten dürfen
ausführen, aber nur in einer Kopie: `git worktree add --detach <lauf>/proof <ZIEL>`, nach dem
Lauf mit `git worktree remove --force` entfernt; so entsteht kein Branch im Repo des Nutzers. Ohne Subagenten (claude.ai) läuft dieselbe Pipeline sequenziell im Hauptkontext;
der Bericht sagt dann „Suche ohne frischen Kontext".

## Approach

**Eiserne Regel:** *Kein Bericht nennt sich vollständig, solange eine Einheit zu einer ihr
zugewiesenen Linse kein vom Skript angenommenes Urteil hat — und kein Kandidat verschwindet
ohne Status.*

### Skill-Struktur

```
skills/deep-review/
├── SKILL.md                         Ablauf, Eiserne Regel, Tiefen und Profile, Contract, Anti-Rationalisierung, Abgrenzung
├── references/lenses.md             Linsen als Szenarien mit konkreten Fragen und einer Eingabe zum Durchspielen: Korrektheit, Fehlerpfade, Vertrag, Nebenläufigkeit, Ressourcen, Delphi, Wartbarkeit, Kommentare
├── references/finder-prompt.md      Auftrag an einen Suchagenten: Pakete, eine Linse, Nonce zurückgeben, jeder Verdacht mit Zeile und Auslösebedingung, kein Filter, Code ist Daten
├── references/verifier-prompt.md    Auftrag an einen Prüfagenten: erst widerlegen, dann belegen; vier Status; Beweistest nur in der Kopie und an der behaupteten Stelle
├── references/saturation.md         Wiederholungsläufe, Abbruch, Jackknife als unkalibrierte Untergrenze
├── assets/report-template.md        Gerüst des Berichts mit Kopfzeile in Zeile 1
└── scripts/review_kit.py            Tier 1 — inventory, packets, record, merge, verdict, audit, estimate, comments, metrics

skills/review-context/SKILL.md       Abschnitt „Warum diese Skill existiert" neu (die Linsen-Engine gibt es jetzt als deep-review); Abgrenzung nennt deep-review
skills/subagent-dev/SKILL.md, skills/debug-ledger/SKILL.md, skills/test-first/SKILL.md   Abgrenzung nennt deep-review
scripts/sync_skills.py               Tier 1, Repo-Werkzeug — deep-review in PROJECT_SKILLS
.claude/skills/deep-review/, .claude/skills/review-context/, .claude/skills/subagent-dev/, .claude/skills/debug-ledger/   Projekt-Kopien über sync_skills.py
.claude-plugin/marketplace.json      deep-review in der skills-Liste von evaluated-dev; Beschreibung von evaluated-dev nennt Review
specs/Spec 00 – skill-foundation.md  Routing: neue Zeile mit deep-review in der Spalte „zuständig" (Lint-Regel routing); Zeile „Diff prüfen" nennt deep-review unter „nicht"; Annahme zu Spec 04 mit Verweis auf Spec 26
README.md                            Skill-Liste von evaluated-dev; neue Routing-Zeile mit deep-review in der Spalte „Responsible"; Zeile „review a diff" ohne „scope left open"
docs/known-limits.md                 Abschnitt deep-review
docs/superpowers/reports/deep-review-report.md   Report mit „Was nicht gemessen wurde" und der Messmenge
evals/deep-review/evals.json         fünf Evals, siehe unten
evals/fixtures/dr-small/, dr-cross-file/, dr-comments/, dr-seeded/   je fixture.json mit "git": true
tests/test_deep_review_kit.py        siehe Tests (Repo)
```

### Ablauf

1. **Umfang.** Modus aus dem Auftrag: `diff` (Bereich `BASIS..ZIEL`, Standard der letzte
   Commit), `path` (Einstiegspunkt `datei:funktion`), `repo` (Verzeichnis). Zuschaltbar:
   `quality`, unabhängig von der Tiefe. Profil `checkpoint` für Aufrufe aus subagent-dev
   (siehe unten); dort kann der Aufrufer mit `--soll-file <datei>` das Soll mitgeben.
   `inventory --depth quick|standard|deep` überschreibt die Tiefe, `--profile checkpoint`
   setzt das Profil; `inventory.json` trägt `depth` und `profile` (sonst `null`).
2. **Inventar:** `review_kit.py inventory`; Pfade unter `.skills/` zählen nie. Im Modus `diff` sind Einheiten die geänderten
   Funktionen, die direkten Aufrufer geänderter Funktionen (Linse Vertrag) und gelöschter
   Code als Vorher-Einheit (Linse Vertrag: hing etwas daran?). Im Modus `path` die Glieder
   der Aufrufkette ab dem Einstiegspunkt, transitiv bis zur Tiefe 4, plus ein Pfad-Paket über
   die ganze Kette. Je Einheit Datei, Zeilen, Hash, Risikomerkmale (berührt Auth, SQL,
   Dateisystem, Netz, Shell, Geld, Parsing; Länge; Änderungshäufigkeit aus `git log`),
   zugewiesene Linsen, Tiefe des Laufs.
3. **Ausführung zuerst**, falls vorhanden: der Verifikationsbefehl aus der CLAUDE.md-Zeile
   `Verifikation:` und Linter oder Typprüfer, die das Repo konfiguriert hat. Rote Tests und
   Meldungen werden Kandidaten mit Quelle `tool`. Fehlt ein Werkzeug, steht es unter „Nicht
   geprüft".
4. **Pakete:** `review_kit.py packets`. Je Einheit ein Paket mit Nonce, Paket-Hash (über
   Code der Einheit, Signaturen der Aufgerufenen und Soll), Code als abgegrenztem
   Datenblock, Aufrufern und Soll. Das Soll holt das Skript im Modus `diff` mit
   `python "${CLAUDE_SKILL_DIR}/../review-context/scripts/collect_context.py" --range <bereich>`
   (mit `--soll-file` zusätzlich `--pr-description-file <datei>`)
   und liest `.skills/cache/review-context.json` nur, wenn dessen `range.raw` dem eigenen
   Bereich entspricht; sonst „Soll ungeprüft". Ein Einheiten-Paket bleibt unter 8.000
   Zeichen Code und wird sonst geteilt; ein Pfad-Paket enthält je Glied Signatur und die
   Zeilen, die Werte weiterreichen, höchstens 16.000 Zeichen.
5. **Suche:** je Linse lesende Suchagenten nach `references/finder-prompt.md`, mehrere
   Pakete je Agent. Ihre Antwort gibt der Hauptagent an `review_kit.py record` weiter; das
   Skript nimmt ein Urteil nur an, wenn Nonce und Paket-Hash zum Paket passen, und schreibt
   es nach `results.jsonl`. Linsen für `quality` laufen in eigenen Durchläufen.
6. **Vereinigen:** `review_kit.py merge` dedupliziert nach Datei, überlappendem
   Zeilenbereich und Klasse (geschlossene Liste in `references/lenses.md`) und behält alle
   Quellen. Abgestimmt wird nicht.
7. **Verifizieren, gestuft:** Ein Sonnet-Prüfagent versucht zuerst, den Kandidaten zu
   widerlegen; was übersteht, versucht er zu belegen. Kandidaten der Klassen Datenverlust
   und Nebenläufigkeit, die den Widerlegungsversuch überstehen, prüft danach Opus.
   `review_kit.py verdict` schreibt je Kandidat einen Status nach `verdicts.jsonl`:
   `bestätigt` (ein Test oder eine Ausführung in der Kopie löst den Fehler an der
   behaupteten Stelle aus), `plausibel` (Argument mit konkreter Eingabe, die durchgespielt
   wurde), `widerlegt` (mit Grund) oder `offen`.
8. **Sättigung**, nur in Tiefe `deep`: Suchläufe auf der oberen Risikogruppe (Einheiten mit
   mindestens zwei Risikomerkmalen) wiederholen sich mit anderer Reihenfolge, einer davon
   mit Opus. Abbruch, wenn zwei Läufe hintereinander keinen neuen `bestätigt`- oder
   `plausibel`-Fund bringen, spätestens nach sechs Läufen. `review_kit.py estimate` schreibt
   ab vier Läufen eine Jackknife-Schätzung als unkalibrierte Untergrenze, darunter
   `ungeprüft`.
9. **Bericht und Audit:** Bericht nach `assets/report-template.md`, dann
   `review_kit.py audit <lauf>`. Übergabe: Lauf-ID, Pfad des Berichts, Funde je Status, Abdeckung
   `<angenommen>/<zugewiesen>`, „Nicht geprüft". Meldet das Audit eine Lücke, sagt die
   Übergabe „unvollständig" mit der Liste, nie „fertig". Im Profil `checkpoint` endet
   deep-review hier; die Funde mit Status `bestätigt` oder `plausibel` behebt subagent-dev
   über seinen Fix-Pfad (Spec 27). Sonst gehen bestätigte Funde mit unklarer Ursache an
   debug-ledger, die übrigen behebt der Hauptagent, und der Beweistest wird über test-first
   zum Regressionstest.

**Tiefen und Profile**, vom Inventar gesetzt und vom Nutzer überschreibbar:

| Tiefe/Profil | wann | Linsen | Wiederholungen | Verifikation |
| --- | --- | --- | --- | --- |
| `quick` | Modus `diff`, höchstens eine geänderte Einheit (Aufrufer nicht mitgezählt) mit höchstens 20 geänderten Zeilen, kein Risikomerkmal | Korrektheit (mit `quality` zusätzlich Wartbarkeit und Kommentare); Aufrufer nur als Kontext im Paket | keine | Sonnet |
| `standard` | Normalfall, auch Modus `path` und `repo` | alle Fehlerlinsen der Einheit | keine | gestuft |
| `deep` | nur auf ausdrücklichen Wunsch („Audit", „so gründlich wie möglich") | alle Fehlerlinsen | Sättigung wie in Schritt 8 | gestuft |
| Profil `checkpoint` | Aufruf aus subagent-dev (Spec 27) | Korrektheit und Vertrag | keine | gestuft, höchstens 15 Verifikationen; der Rest bleibt `offen`, steht im Bericht und wird im nächsten Folgelauf ohne dieses Profil erneut verifiziert, in subagent-dev am finalen Prüfpunkt |

**Folgeläufe** (`--since <lauf>[,<lauf>…]`) übernehmen die Urteile der Suchagenten und die
Kandidaten samt Status von Einheiten, deren Wiederverwendungsschlüssel gleich geblieben ist —
ein Hash über den Code der Einheit und die Signaturen der Aufgerufenen, ohne das Soll, das
sich mit jedem Bereich ändert. Mehrere Läufe sind nötig, wenn ein Folgelauf einen größeren
Bereich prüft als jeder frühere (finaler Prüfpunkt in Spec 27, der die Bereiche aller
früheren Prüfpunkte umfasst); steht eine Einheit in mehreren, gilt der jüngste Lauf.
Geänderte Einheiten und deren direkte Aufrufer prüfen sie neu; Linsen, die die früheren
Läufe nicht hatten, laufen auf allen Einheiten. Übernommene Kandidaten mit Status `offen`
gehen außerhalb des Profils `checkpoint` erneut in die Verifikation; im Profil `checkpoint`
bleiben sie `offen` und zählen nicht gegen die Grenze von 15.

### Wartbarkeit und Kommentare (`quality`)

Wartbarkeitsfunde sind Hinweise mit eigener Stufe und eigenem Berichtsabschnitt. Jede
Kritik nennt ihre Grundlage — eine Projektregel aus CLAUDE.md oder `.claude/rules/`, einen
Messwert aus `review_kit.py metrics` (Funktionslänge, Verschachtelung, Verzweigungen, je
gegen den Median des Repos) oder einen konkreten Lesefehler — und einen Umbauvorschlag.
Ohne Grundlage wird sie nicht gemeldet.

`review_kit.py comments` sortiert Kommentare vor; im Modus `diff` nur neue und geänderte:

| Regel | erkennt mechanisch |
| --- | --- |
| `change-narration` | Erzählung der Änderung: `added`, `now`, `previously`, `updated`, `jetzt`, `neu:`, `geändert` |
| `ticket-ref` | Verweis auf Ticket, PR oder Gespräch statt auf den Code |
| `docstring-oversize` | Docstring länger als der Funktionskörper |
| `commented-out-code` | Kommentarblock, der sich als Python parsen lässt (`ast`); andere Sprachen: Zeile endet auf `;` oder `)` und enthält einen Bezeichner des Moduls |
| `comment-ratio` | Anteil Kommentarzeilen im Diff über dem Doppelten des Repo-Medians |

Ob ein Kommentar nur die nächste Zeile wiederholt, entscheidet das Modell: `comments` legt
jeden neuen Kommentar mit der folgenden Codezeile als Kandidaten vor, weil eine
Wortüberlappung über Sprachen hinweg nicht trägt (`# erhöhe Zähler` über `count += 1`). Ein
Kommentar, der dem Code widerspricht, ist ein Kandidat der Linse Vertrag und wird
verifiziert wie ein Bug.

### Contract

- **Abdeckung gegen das Inventar.** Der Code einer Einheit steht in ihrem Paket; `audit`
  meldet jede Einheit-Linse-Kombination ohne angenommenes Urteil und jedes Urteil, dessen
  Nonce oder Hash nicht passt (G2). Die Nonce erschwert ein erfundenes „geprüft", sie macht
  es nicht unmöglich: Wer das Paket liest, kennt sie. Das steht im Bericht.
- **Kein Kandidat verschwindet.** Jeder Kandidat in `candidates.jsonl` hat in
  `verdicts.jsonl` einen Status; `widerlegt` steht mit Grund im Anhang. `audit` meldet
  Kandidaten ohne Status.
- **Bericht und Daten stimmen überein.** `audit` meldet einen Bericht, der „vollständig"
  sagt, obwohl `audit.json` Lücken trägt, und Zahlen im Bericht, die nicht zu den Dateien
  passen.
- **Ausführung nur in der Kopie, Suche nur lesend.** Prüfagenten führen Code nur unter
  `<lauf>/proof/` aus; Suchagenten haben keine Schreibwerkzeuge.
- **Sättigung nur mit Zahl und Vorbehalt.** Eine Aussage über Restfehler steht nur mit
  `estimate.json`, der Zahl der Läufe und dem Wort „unkalibriert".
- **Anti-Zeremonie-Fall:** Ein Diff mit einer geänderten Einheit und höchstens 20 Zeilen ohne
  Risikomerkmal läuft in Tiefe `quick`: eine Fehlerlinse, kein Opus, keine Wiederholung, ein
  Bericht von höchstens 40 Zeilen.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| schneller Check eines PR, wenige sichere Funde | `/code-review` (mitgeliefert) | deep-review — teurer, mit Abdeckungsnachweis |
| Code gründlich prüfen und belegen, was geprüft wurde: Diff, Pfad, Modul, Prüfpunkt eines Plans | **deep-review** | `/code-review` — kein Inventar, keine Abdeckung |
| Kontext und Soll für einen Diff sammeln | **review-context** | deep-review ruft es auf, baut es nicht nach |
| wann zwischen Tasks reviewt wird | **subagent-dev** (Spec 27) | deep-review prüft, plant keine Prüfpunkte |
| Sicherheitsaudit | `/security-review`, trailofbits | deep-review hat in diesem Zyklus keine Security-Linse (siehe Open questions) |
| bestätigter Fund mit unklarer Ursache | **debug-ledger** | deep-review meldet, diagnostiziert nicht |
| Beweistest eines bestätigten Funds wird Regressionstest | **test-first** | deep-review schreibt den Test nur in der Kopie |

Rückverweise beim Bau, je mit dem Wort deep-review: review-context, subagent-dev,
debug-ledger, test-first (alle im Strukturblock oben). Das Register der Lint-Befunde in
`tests/test_skills_lint.py` ist voll (79 von 79 Paaren); ein fehlender Rückverweis macht
`test_no_finding_outside_the_register` rot.

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_inventory_python` | `tests/test_deep_review_kit.py` | Funktionen, Methoden, verschachtelte Funktionen; Hash ändert sich nur mit dem Inhalt; Modus diff: geänderte Einheiten, direkte Aufrufer, gelöschte Funktion als Vorher-Einheit |
| `test_inventory_path_chain` | dito | Aufrufkette ab Einstiegspunkt transitiv bis Tiefe 4; Pfad-Paket enthält jedes Glied |
| `test_inventory_ts` | dito | Funktionsdeklaration, Pfeilfunktion an `const`, Klassenmethode; Änderung im Rumpf erkannt |
| `test_inventory_delphi_and_chunks` | dito | Methode mit lokaler Prozedur endet am eigenen `end;`; `case`, `try`, `record`, `asm` gezählt; varianter `record … case X of … end` schließt mit einem `end`; `forward;`- und `external`-Köpfe ohne Rumpf sind keine Einheit; `end` in String und Kommentar ignoriert; Deklaration im `interface`-Teil keine Einheit; unvollständiger `{$IFDEF}` → `chunk` mit Grund |
| `test_depth_and_profiles` | dito | quick zählt keine Aufrufer; Risikomerkmal → standard; path → standard; deep nur mit Schalter; `--depth` überschreibt die gesetzte Tiefe; `--profile checkpoint` setzt Linsen und Grenze 15 |
| `test_packets_and_nonce` | dito | Einheiten-Paket über 8.000 Zeichen wird geteilt; Pfad-Paket bis 16.000; Paket-Hash deckt Signaturen und Soll; review-context-Paket mit fremdem Bereich wird nicht gelesen |
| `test_record_rejects_wrong_nonce` | dito | falsche Nonce oder alter Hash → abgewiesen, nichts in `results.jsonl` |
| `test_merge_without_voting` | dito | gleiche Stelle und Klasse → ein Kandidat mit allen Quellen; andere Klasse → zwei; kein Kandidat fällt weg |
| `test_jsonl_format` | dito | `_meta` in Zeile 1, feste Schlüsselreihenfolge, `ensure_ascii=False`, Trennzeichen `", "` und `": "`, `reason` und `evidence` als Zeichenketten, Pfade ohne `./` |
| `test_audit` | dito | fehlendes Urteil (`missing`), Nonce-Abweichung (`nonce_mismatch`), fehlender Status (`unverdicted`), Bericht „vollständig" trotz Lücke oder abweichende Zahl (`report_mismatch`) → je ein Eintrag und `complete: false`; sauberer Lauf → `complete: true` |
| `test_estimate` | dito | Jackknife erster Ordnung an bekannten Zahlen; unter vier Läufen `ungeprüft` |
| `test_comment_rules` | dito | jede Regel der Tabelle trifft ihr Beispiel, nicht einen Warum-Kommentar; `comments` legt jeden neuen Kommentar mit Folgezeile vor |
| `test_metrics_against_median` | dito | Länge, Verschachtelung, Verzweigungen je Funktion und Median des Repos |
| `test_since_reuses_unchanged_verdicts` | dito | gleicher Schlüssel → Urteile und Kandidaten übernommen, auch bei anderem Soll; geänderte Signatur eines Aufgerufenen → neu geprüft; neue Linse → auf allen Einheiten; zwei Läufe mit disjunkten Bereichen in `--since` → Urteile aus beiden, bei derselben Einheit der jüngere; übernommener `offen`-Kandidat → in Tiefe `standard` erneut verifiziert, im Profil `checkpoint` unverändert |
| `test_run_ids_do_not_collide` | dito | zwei Läufe in derselben Sekunde mit gleichem Commit → verschiedene Lauf-IDs dank Zufallssuffix |

### Evals

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-one-line-fix-stays-quick` | contract | `dr-small` | `file_matches` `.skills/cache/deep-review/*/inventory.json` auf `"depth":\s*"quick"`; `artifact_header` auf `.skills/cache/deep-review/*/report.md`; `file_max_lines` dort 40; `git_head_unchanged` | Inventar mit Tiefe und Bericht mit Kopfzeile schreibt nur die Skill |
| 2 | `every-unit-gets-a-verdict` | contract | `dr-cross-file` | `file_matches` `.skills/cache/deep-review/*/audit.json` auf `"missing":\s*\[\]`, auf `"nonce_mismatch":\s*\[\]` und auf `"complete":\s*true`; `file_matches` `.skills/cache/deep-review/*/inventory.json` auf `app/orders\.py` und auf `app/report\.py` | `audit.json` schreibt nur `review_kit.py`; ohne Inventar gibt es keine Liste, gegen die etwas fehlen könnte |
| 3 | `cross-file-none-bug-is-found` | contract | `dr-cross-file` | `file_matches` `.skills/cache/deep-review/*/verdicts.jsonl` auf `^\{"id":[^\n]*"path": "app/(report\|orders)\.py"[^\n]*"status": "(bestätigt\|plausibel)"` | `parse_order` gibt bei leerer Zeile `None` zurück, `summarize` greift ungeprüft auf `.total` zu; beide hängen an `main`, der Pfad-Modus nimmt beide als Einheiten; `verdicts.jsonl` entsteht nur in der Pipeline |
| 4 | `comment-ballast-is-flagged` | contract | `dr-comments` | `file_matches` `.skills/cache/deep-review/*/comments.json` auf `"rule":\s*"change-narration"` und auf `"rule":\s*"commented-out-code"`; `file_matches` `.skills/cache/deep-review/*/report.md` auf `app/stats\.py:\d+` | `comments.json` schreibt nur `review_kit.py comments`; die Fixture fügt `# jetzt mit Cache` und `# old_total = sum(values)` hinzu |
| 5 | `routing-thorough-check-without-skill-name` | contract | `dr-cross-file` | `file_exists` `.skills/cache/deep-review/*/inventory.json` | stochastisch: ein roter Lauf zeigt eine Kollision mit `/code-review` oder einer global installierten Review-Skill (known-limits, „Isolation"); ein grüner beweist nichts |

Die Pfade nutzen Globs (`evalkit/assertions.py`, `resolve_target`). In Eval 3 steht `\|`
nur für die Tabelle; in `evals.json` ist es `|`. Das Muster bindet an eine Zeile von
`verdicts.jsonl` mit der Schlüsselfolge `id`, `path`, `lines`, `class`, `status`, `reason`,
`evidence`, `related` (weitere betroffene Dateien eines Funds über Dateigrenzen) und den
Trennzeichen von `json.dumps` (`": "`).

Prompts: 1 „Review den letzten Commit mit deep-review.", 2 und 3 „Prüf mit deep-review den
Pfad ab `app/cli.py:main`.", 4 „Review den letzten Commit mit deep-review, inklusive
quality.", 5 „Prüf den Ablauf ab `app/cli.py:main` auf Fehler und sag mir, ob wirklich jede
Funktion angeschaut wurde." Die Fixtures sind Git-Repos mit einem Commit für den Diff;
`dr-cross-file` bringt pytest und einen grünen Test mit, der den leeren Fall nicht abdeckt.
Vor der Abnahme läuft jeder Eval einmal ohne Skill (Spec 18).

### Messung der Trefferquote

Die Evals prüfen den Vertrag, nicht die Trefferquote. Die misst der Report vor der Abnahme
an `dr-seeded`: eine Fixture mit fünf eingebauten Fehlern verschiedener Klassen (`None`
über zwei Dateien, Grenzwert um eins daneben, Ressourcenleck nur im Fehlerpfad, verschluckte
Exception, Kommentar widerspricht Code) und einer sauberen Fassung für die Präzision. Je drei
Läufe von deep-review in Tiefe `standard`, von `/code-review` und von einem einzelnen
Sonnet-Lauf ohne Inventar über denselben Bereich. *Annahme:* Abnahmeschwelle — deep-review
findet im Mittel mindestens so viele der fünf wie die beiden anderen zusammen, bei höchstens
zwei `plausibel`-Funden auf der sauberen Fassung. Jede Stufe, die gegenüber ihrer
Abschaltung (Pfad-Pakete, Verifikation, Aufrufer als Einheiten) keinen messbaren Unterschied
bringt, fliegt vor dem Bau des nächsten Zyklus raus.

## Alternatives considered

**Bei `/code-review` bleiben und nur den Kontext verbessern** (Stand nach Spec 04).
Verworfen: Das Plugin schließt eingabeabhängige Fehler und Altlasten aus und weist nicht
aus, was es gelesen hat. Gewinnt, wenn `/code-review` in der Messung auf `dr-seeded`
genauso viele Fehler findet.

**Eine Abschrift des Codes als JSON durch Haiku, die Sonnet oder Opus statt des Codes
liest** (erste Idee des Nutzers, 2026-10-28). Verworfen: Der Reviewer prüft dann Haikus
Deutung, die Abschrift ist länger als der Code, und Fehler der ersten Stufe sind in der
zweiten unsichtbar. Übernommen ist die Idee der Pfade vom Einstieg bis zum Endpunkt, als
Pfad-Paket mit echtem Code.

**Ein Skript dispatcht die Suche selbst** (`claude -p --bare` mit JSON-Schema). Dann wäre
die Abdeckung nicht mehr Auskunft des Hauptagenten. Verworfen für diesen Zyklus: Tier 3
(braucht die CLI), läuft nicht in claude.ai, und Kosten und Limit liegen außerhalb der
Sitzung. Gewinnt, wenn das Audit zeigt, dass Hauptagenten Urteile ohne Dispatch eintragen.

**Mehrheitsvotum über Suchläufe.** Verworfen nach MultiVer (Recall 37,7 % statt 82,7 %).

**Feste Zahl von Runden.** Verworfen: Sie regelt den Kreislauf zwischen Autor und Reviewer,
nicht die Restfehler. Ersetzt durch Abdeckung, Abbruch nach zwei fundlosen Läufen und
Folgeläufe nur über geänderte Einheiten.

**Sättigung ganz weglassen.** Erwogen, weil die Schätzung unkalibriert ist (Läufe desselben
Modells sind korreliert, Fehlalarme blähen Einzelfunde auf). Behalten nur in `deep`, mit
Abbruchregel als eigentlichem Mechanismus und der Schätzung als markierter Untergrenze.

**Wartbarkeit als eigene Skill.** Verworfen: Inventar, Pakete, Audit und Bericht wären
doppelt. Gewinnt, wenn `quality` die Trefferquote der Fehlerlinsen messbar senkt.

**Modi `security`, `tests`, `migration`, `iac` gleich mitbauen** (Konzeptdokument).
Verworfen für diesen Zyklus: Security routet Spec 00 an `/security-review`, Migrationen
prüft sql-schema-architect, Tests plant testing-strategy, für IaC fehlt eine Messung.

## Out of scope

Sicherheitsaudit und Security-Linse (siehe Open questions), Migrationen
(sql-schema-architect), Teststrategie (testing-strategy), Fixes schreiben (Hauptagent),
Pläne prüfen, Prüfpunkte zwischen Tasks planen (subagent-dev, Spec 27), Taint-Analyse mit
CodeQL oder Semgrep (als Werkzeugmeldungen in Schritt 3 erlaubt, nicht gebaut),
Testabdeckung als Karte (Tier 2), ein Parser über tree-sitter (Tier 2).

## Open questions

*Annahme:* Keine Security-Linse in diesem Zyklus, obwohl der Nutzer Sicherheitslücken
gefunden sehen will — Spec 00 §5 routet Sicherheit an `/security-review` und trailofbits und
nennt in der Spalte „nicht" alle eigenen Skills. Eine Security-Linse hieße, diese Zeile zu
ändern; das ist eine Entscheidung des Nutzers — widersprich, falls sie in diesen Zyklus
gehört. Risikomerkmale wie Auth oder SQL steuern bis dahin nur die Tiefe.

*Annahme:* Name `deep-review`; Ablage nur im Cache, Bericht nach `docs/reviews/` nur auf
Wunsch — widersprich, falls er immer committet werden soll.

*Annahme:* Risikomerkmal Länge ab 80 Zeilen, Änderungshäufigkeit ab fünf Commits im letzten
Jahr; Sättigung mit Jackknife erst ab vier Läufen und Abbruch nach zwei fundlosen Läufen.
Grenzen `quick` bei einer geänderten Einheit und 20 Zeilen, Bericht höchstens 40
Zeilen, Paket unter 8.000 und Pfad-Paket unter 16.000 Zeichen, Kette bis Tiefe 4, Chunk 150
Zeilen, obere Risikogruppe ab zwei Merkmalen, Sättigung bis sechs Läufe, Profil
`checkpoint` mit 15 Verifikationen, `comment-ratio` beim Doppelten des Medians. Keine ist
gemessen; der Report nennt die Werte, mit denen die Evals liefen.

*Annahme:* Die Delphi-Linse (Besitz und Freigabe mit `try/finally` und Owner,
Interface-Referenzzählung gemischt mit Objektreferenzen, VCL-Hauptthread, verschluckte
Exceptions, String-Kodierung) stammt aus Praxiswissen, nicht aus einer Studie.

*Annahme:* Die Linsen sind als Szenarien mit konkreten Fragen geschrieben, weil
Szenario- und Perspektiven-Lesen bei Menschen besser abschnitt als Checklisten (Porter u. a.
1995; Laitenberger u. a. 2000: 58 % gegen 43 %, 18 Praktiker; es gibt Gegenbefunde). Ob das
für Modelle gilt, ist ungemessen.

Ob ein zusätzlicher Suchlauf mit Haiku über alle Einheiten Recall bringt oder nur
Prüfaufwand, ist ungemessen und nicht Teil dieses Zyklus.

Eval-Läufe enden nach 600 Sekunden (`evalkit/dispatch.py`, `DEFAULT_TIMEOUT`), ein Timeout
wird nicht bewertet. Ob Tiefe `standard` auf `dr-cross-file` darunter bleibt, ist
ungemessen; die Evals rufen deshalb keine Tiefe `deep` auf.

Die Kosten sind geschätzt, nicht gemessen: ein PR mit 400 Zeilen in Tiefe `standard` unter
1 $, ein Repo mit 20.000 Zeilen in Tiefe `deep` etwa 16 $ (Konzeptdokument). Der Report
misst sie mit `total_cost_usd` aus `claude -p`.

Ob ein Subagent, der deep-review aufruft, selbst Subagenten starten kann, ist ungemessen;
Spec 27 ruft deep-review deshalb aus dem Hauptkontext auf.

evaluated-dev ist immer an und hat das längste Listing; Spec 20 hat kurze Listings gemessen
und vermutet, ohne es zu beweisen, dass dort Descriptions wegfallen. deep-review kommt mit
einer weiteren Description dazu.

## Next steps

**Stand 2026-10-30: Bau pausiert.** Task 1 des Plans ist gebaut (`dr-seeded`,
`dr-seeded-clean`, Basislinie im Report). Ergebnis: `/code-review` findet auf beiden Fassungen
der Fixture in jedem Lauf alle fünf Fehler, auch die, die nur mit unverändertem Code aus
`base` erkennbar sind; seine weiteren Funde auf der „sauberen" Fassung sind echte Fehler der
Fixture, keine Fehlalarme. Damit trifft die Bedingung aus „Alternatives considered" zu, unter
der „bei `/code-review` bleiben" gewinnt. Der Nutzer hat entschieden: Spec 27 zuerst, mit dem
Ersatz `/code-review` an den Prüfpunkten. deep-review wird wieder aufgenommen, wenn sich im
Einsatz eine Lücke von `/code-review` zeigt (große Diffs, Delphi; das runlog aus Spec 27 hält
Funde je Prüfpunkt fest), dann in der schlanken Fassung: Python-Inventar mit Chunks,
Delphi-Scanner, Pakete, record, merge/verdict, audit, Profil `checkpoint`, `--since`; ohne
Sättigung, `quality`, TS-Muster und Pfad-Modus.

Plan mit `impl-plan` (16); Bau nach `skill-forge` (17) Schritt 3 bis 7. Erste Aufgabe des
Plans ist die Fixture `dr-seeded` mit der Messung aus „Messung der Trefferquote", damit die
Abnahmeschwelle vor dem Ausbau steht. Danach Spec 27.
