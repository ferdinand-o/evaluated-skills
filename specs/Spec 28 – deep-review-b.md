# Spec 28: deep-review B — auf jeder Eingabe mindestens so gut wie `/code-review`, besser, wo der Vertrag außerhalb des Diffs liegt

Skill-Spezifikation · Zyklus 28 · Entscheidung: deep-review bleibt `/code-review` je Paket mit Gegenstellen-Block und Audit (Spec 26); Abschnitt B schließt die Lücken aus der Abnahme vom 2026-11-03 — Kosten, Block-Übergabe, ganze Dateien als Pakete, Pfade, Sprachen ohne Sammler, Präzision — und misst vor dem Bau, welche Stufe die Treffer trägt · Abgeglichen mit Spec 00, Spec 26 und Spec 27

## Problem

Der Nutzer will deep-review „für alles gut (besser als code-review)" (2026-11-04). Gemessen
ist (`docs/superpowers/reports/deep-review-report.md`, Abschnitte „Nachmessung auf großen
Repos", „Abnahme (Task 16)" und die Basislinie auf `dr-seeded`):

| Eingabe | `/code-review` | deep-review | Lücke |
| --- | --- | --- | --- |
| großer Diff Python (`py-diff`, 4.097 Zeilen) | 4,5/6 im Mittel, P2 in keinem Lauf, 1,06 USD | 6/6 mit P2 und P4, ein Lauf, 5,87 USD | Kosten 5,5×, ein Lauf |
| großer Diff Delphi (`dl-diff`, 1.988 Zeilen) | 5,0/6, 2,33 USD | 6/6, ein Lauf, 7,43 USD | Kosten 3,2×; Block nicht ausdrücklich übergeben |
| kleiner Diff (`dr-seeded`, rund 400 Zeilen) | 5/5 in drei Läufen, 0,38–0,53 USD | nicht gemessen | `/code-review` am Anschlag |
| kleiner Diff mit Vertrag außerhalb (`dr-contract`, `dr-delphi`) | nicht gemessen | Fund gemeldet, 0,67 und 0,54 USD | Basislinie fehlt |
| Pfad ohne Diff (`dl-path`, 5.308 Zeilen) | 6/6 in drei Läufen, 1,29 USD | nimmt keinen Pfad | Eingabe fehlt |
| andere Sprachen als Python und Delphi | ungemessen | teilt, sammelt keine Gegenstellen | Block fehlt |

Dazu aus dem Bau (`docs/known-limits.md`, Abschnitt deep-review): Eine Datei wird nie geteilt
(ein neues Modul mit 5.000 Zeilen ist ein Paket); dass der Block den Reviewer erreicht, ist
Auskunft des Hauptagenten; den Bericht schreibt der Hauptagent, und `audit` liest ihn mit
regulären Ausdrücken; die Gegenstellen werden zweimal gesammelt. Ob die Treffer vom Block oder
vom Schneiden kommen, ist auf den großen Repos nicht getrennt (`drnc` entfiel), und die
Präzision ist ungemessen.

Was „besser" heißen kann, setzt die Messung: Wo `/code-review` alle eingebauten Fehler findet
(`dr-seeded`, `dl-path`), kann deep-review bei den Treffern nur gleichziehen. Dort heißt
besser: gleiche Treffer, Abdeckungsnachweis, wenig Mehrkosten. Echte Mehrtreffer gibt es nur,
wo der Vertrag außerhalb des Gelesenen liegt (P2) oder der Bereich zu groß ist.

## Constraints

Wie Spec 26: portables Frontmatter, Tier 1 mit `scripts/review_kit.py` (nur Stdlib, nie Import
des Zielcodes), Ablage unter `.skills/cache/deep-review/<lauf>/`, Hilfscommits unter
`refs/deep-review/<lauf>/`, Gate-Grade G1 (SKILL.md verlangt) und G2 (`audit` meldet), kein
Hook. Neu gesammelt wird für TypeScript/JavaScript mit einem Text-Scanner wie bei Delphi; für
weitere Sprachen nur Definitionen mit eindeutigem Namen, gekennzeichnet.

Die Reviews führt weiter `/code-review` aus. Es nimmt eine Stufe vor dem Ziel
(`low|medium|high|xhigh|max`); ohne Stufe nimmt es die zuletzt getippte. deep-review nennt
die Stufe künftig in jedem Aufruf ausdrücklich. `max` nur auf ausdrücklichen Wunsch des
Nutzers (Beschreibung von `/code-review`).

Messbudget: *Annahme:* rund 40 USD, davon rund 9 USD für die Sonde vor dem Bau (Ablauf
Schritt 0) und rund 31 USD für die Abnahme. Der Nutzer gibt das Budget vor dem Bau frei.

## Approach

**Eiserne Regel** (unverändert aus Spec 26): *Kein Bericht nennt sich vollständig, solange ein
Paket des Plans kein vom Skript angenommenes Ergebnis hat — und kein Fund eines Pakets fehlt in
`findings.json`.*

**Ziel je Eingabe** (Abnahme unten): Treffer im Mittel nie unter `/code-review`; auf den
Szenarien mit Vertrag außerhalb des Diffs mehr; Kosten auf großen Diffs höchstens 2× der
Basislinie, auf kleinen Diffs und Pfaden höchstens 1,5×; keine Meldung, die einer korrigierten
Stelle widerspricht, häufiger als bei `/code-review`.

### Skill-Struktur

```
skills/deep-review/
├── SKILL.md                         Ablauf mit Paket-Auftrag, Stufe je Profil, Pfad-Modus, `report`, optional `verify`; Description nach der Abnahme
├── references/packets.md            Spannen innerhalb einer Datei, Pfad-Modus mit eigenen Grenzwerten, Kosten-Hinweis im Plan
├── references/counterparts.md       TypeScript/JavaScript-Sammler, Namens-Rückfall für weitere Sprachen
├── references/review-brief.md       Paket-Auftrag als Datei mit Marke, Stufe je Profil, Prüfer-Auftrag für `verify`
├── references/delphi.md             unverändert
├── assets/report-template.md        entfällt; den Bericht schreibt `review_kit.py report`
└── scripts/review_kit.py            Tier 1 — dazu `report`, `verify`, `verdict`; Spannen, Pfad-Modus, Sammler TS/JS und Namens-Rückfall, Gegenstellen einmal gesammelt

docs/superpowers/reports/review-bench/run.sh, match.py, README.md   Werkzeug `crb` (Paket mit Block, Stufe wählbar), `dr` darf `report.md` schreiben, `match.py` liest `.kit/<lauf>/`, `dr` auf Pfaden
skills/subagent-dev/scripts/plan_to_tasks.py   `fix-task` lässt Funde mit Urteil `widerlegt` weg und nennt ihre Zahl
skills/subagent-dev/references/checkpoints.md  `verify` am finalen Prüfpunkt
specs/Spec 00 – skill-foundation.md, README.md   Routing nach der Abnahme
docs/known-limits.md, docs/superpowers/reports/deep-review-report.md
evals/deep-review/evals.json         Evals 7–11
evals/fixtures/dr-bigfile/, dr-ts/   neu
tests/test_deep_review_kit.py, tests/test_review_bench_match.py, tests/test_subagent_dev_plan_to_tasks.py
.claude/skills/deep-review/, .claude/skills/subagent-dev/   Projekt-Kopien über scripts/sync_skills.py
```

### Ablauf

0. **Sonde vor dem Bau** (einmalig, Report Abschnitt „Sonde B"). Gemessen wird, was den Bau
   entscheidet:
   - `drnc` auf `py-diff`, ein Lauf: Findet deep-review ohne Block P2 und P4, trägt das
     Schneiden die Treffer, und der Block bleibt nur, wenn ein weiterer Lauf ihn stützt.
   - `/code-review` auf `dr-contract` und `dr-delphi`, je zwei Läufe: die fehlende Basislinie
     der kleinen Diffs mit Vertrag außerhalb.
   - Stufe je Paket: `crb` auf dem Paket von `py-diff`, das P2 und P4 trägt (`py-c1`), mit `low`,
     `medium` und `high`, je ein Lauf. Die billigste Stufe, die P2 und P4 findet, wird die des Profils
     `standard`; `checkpoint` nimmt eine Stufe höher.
   - Übergabe des Blocks: ein Lauf `/code-review` mit einer eindeutigen Marke im Aufruf; in den
     Transkripten seiner Unteragenten wird nach der Marke gesucht. Dazu ein Lauf, der
     `/code-review` aus einem Unteragenten (Agent-Werkzeug) startet. Das Ergebnis legt fest,
     ob Schritt 4 im Hauptkontext bleibt oder je Paket einen Unteragenten startet.
1. **Bereich oder Pfad.** Neu: `plan --path <pfad>[,<pfad>…]` statt `--range`. Ein Pfad wird
   wie ein Bereich vom leeren Stand bis zum Ziel behandelt: Hilfscommits mit den Dateien des
   Pfads als neu. Grenzwerte im Pfad-Modus: `PATH_SPLIT_AT = 5000`, `PATH_PACKET_SIZE = 2500`
   Zeilen (*Annahme:* gemessen ist nur, dass `/code-review` bis 5.308 Zeilen alles fand).
   Gegenstellen sammelt der Pfad-Modus nur für Aufrufe, die den Pfad verlassen.
2. **Plan** wie bisher, dazu: Eine Datei mit mehr als `PACKET_SIZE` geänderten Zeilen wird an
   Definitionsgrenzen geteilt (Python über `ast`, Delphi und TS/JS über den Scanner, sonst an
   Hunk-Lücken). Ein Paket trägt dann `spans` (`{file, lines}`), und seine Hilfscommits zeigen
   nur die Hunks seiner Spanne; `bis^{tree}` bleibt der Baum des Ziels. Datei-Schlüssel für
   `--since` bleiben je Datei. `plan` nennt in einer Zeile die Zahl der Reviews
   (`Reviews: <n> × /code-review <stufe>`), damit der Nutzer die Kosten vor dem Lauf sieht.
   Die Gegenstellen sammelt `plan` einmal und legt sie im Laufordner ab; `counterparts` liest
   sie von dort.
3. **Paket-Auftrag.** `counterparts` schreibt je Paket `packets/<id>.md` (Block wie bisher) und
   `packets/<id>.prompt.md`: Auftrag aus `review-brief.md` (Fassung nach Profil und Fokus),
   Bereich, Stufe, Block und am Ende eine Zeile `Paket-Marke: <marke>` mit zufälligem Anteil.
4. **Review je Paket** mit `/code-review <stufe> --max-findings all <von>..<bis>`; der Auftrag
   ist der Inhalt von `packets/<id>.prompt.md`. Das Ergebnis ist ein Objekt
   `{"marke": …, "findings": […]}`; `record` weist ein Ergebnis ohne passende Marke mit Exit 1
   ab. `record --no-block` nimmt ein Ergebnis ohne Marke an und schreibt das in Ergebnis und
   Bericht („ohne Gegenstellen-Block"); gedacht für die Abschaltung und Läufe, in denen der
   Nutzer den Block abwählt.
5. **Vereinigen** wie bisher.
6. **Prüfen (optional, `--verify` beim Plan, im Profil `checkpoint` Standard).** `verify`
   schreibt je Fund ohne Beleg des Reviewers einen Prüfauftrag `verify/<n>.md` mit Datei,
   Zeile, Szenario und Commit, ohne die Begründung des Reviewers. Je Auftrag ein Unteragent
   (Modell Sonnet) mit Urteil `bestätigt`, `widerlegt` oder `unklar` und Beleg (Befehl und
   Ausgabe); `verdict` nimmt es an. Nur `widerlegt` mit Beleg nimmt einen Fund aus der Liste
   für `fix-task`; in `findings.json` und im Bericht bleibt er mit Urteil stehen.
7. **Bericht, Audit, Aufräumen.** Neu: `report --run <lauf>` schreibt `report.md` mit allen
   datentragenden Zeilen (Kopfzeile, Funde, Abdeckung, Hinweise, Übernommen, Nicht geprüft,
   Fundzeilen, Urteile, Stufe, Reviews). Der Hauptagent darf nur einen Abschnitt
   `## Einordnung` anfügen. `audit` vergleicht die datentragenden Zeilen mit einer neu
   erzeugten Fassung statt mit regulären Ausdrücken; jede Abweichung ist `report_mismatch`.

### Sammler

| Sprache | sammelt | nicht |
| --- | --- | --- |
| Python, Delphi | wie Spec 26 | — |
| TypeScript, JavaScript (`.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs`) | Definition über `import`/`require` mit relativem Pfad, `throw`-Stellen der Gegenstelle bis `RAISE_DEPTH`, `async`-Gegenstelle bei einem Aufruf ohne `await` | Typinferenz, `node_modules`, Pfad-Aliase aus `tsconfig.json` |
| Java, C#, Go, Rust, C, C++, Kotlin, Swift | Definition mit eindeutigem Namen im Repo, markiert „(Name eindeutig, ohne Sammler)", `throw`/`panic!`-Zeilen ihres Rumpfs | Importe, Überladungen, Besitz |
| andere | nichts, „Gegenstellen nicht gesammelt (Sprache)" | — |

### Contract

- `record` nimmt ein Ergebnis nur mit der Marke seines Pakets an, außer mit `--no-block`; das
  meldet `audit` je Paket unter `no_block`.
- `report.md` schreibt das Skript; `audit` meldet jede Abweichung der datentragenden Zeilen.
- Ein Urteil `widerlegt` ohne Beleg weist `verdict` ab.
- Die Stufe je Paket steht im Plan (`level`) und in der Kopfzeile des Berichts.
- Pfad-Modus und Bereichsmodus schreiben dieselben Dateien; `plan.json` trägt `mode`
  (`range` oder `path`).

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| großen Bereich, Branch oder Prüfpunkt gründlich prüfen | **deep-review** | `/code-review` über alles |
| kleinen Diff oder Pfad prüfen, mit Nachweis oder Gegenstellen | **deep-review**, wenn die Abnahme B das Ziel für diese Eingabe erreicht; sonst `/code-review` | — |
| schneller Blick auf einen kleinen Diff ohne Nachweis | `/code-review` | deep-review |
| Kontext und Soll für einen Diff | **review-context** | deep-review |
| Prüfpunkte planen, Fixes dispatchen | **subagent-dev** | deep-review |
| bestätigter Fund mit unklarer Ursache | **debug-ledger** | deep-review |
| Sicherheitsaudit eines Systems | `/security-review` | deep-review |

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_b_record_needs_packet_marker` | `tests/test_deep_review_kit.py` | Ergebnis ohne oder mit fremder Marke → Exit 1, nichts geschrieben; `--no-block` → angenommen, `audit` nennt `no_block` |
| `test_b_report_is_written_by_the_script` | dito | `report` schreibt alle Pflichtzeilen; geänderte Fundzeile → `report_mismatch`; angefügtes `## Einordnung` → keine Abweichung |
| `test_b_counterparts_collected_once` | dito | `counterparts` ruft den Sammler nicht erneut, wenn `plan` ihn abgelegt hat |
| `test_b_big_file_split_at_definitions` | dito | Python-Datei mit 1.300 geänderten Zeilen → zwei Pakete mit `spans` an einer `def`-Grenze; Hilfscommits zeigen nur ihre Hunks; `bis^{tree}` = Ziel |
| `test_b_path_mode` | dito | `plan --path` → `mode: path`, Hilfscommits mit den Dateien als neu; über `PATH_SPLIT_AT` geteilt; Gegenstellen nur für Aufrufe außerhalb des Pfads |
| `test_b_typescript_collector` | dito | relativer Import → Definition und `throw`-Zeile; Aufruf einer `async`-Funktion ohne `await` → Eintrag |
| `test_b_name_fallback_marks_unique_names` | dito | Go-Datei: eindeutiger Name → Definition mit Kennzeichnung; doppelter Name → nicht aufgelöst |
| `test_b_verdict_needs_evidence` | dito | `widerlegt` ohne Beleg → abgewiesen; mit Beleg → Fund bleibt in `findings.json` mit Urteil |
| `test_b_fix_task_skips_refuted` | `tests/test_subagent_dev_plan_to_tasks.py` | Fund mit `widerlegt` fehlt in der Task-Datei, die Zahl steht dort |
| `test_match_reads_kit_run_folder` | `tests/test_review_bench_match.py` | `findings.json` unter `.kit/<lauf>/` wird je Fund abgeglichen |

### Evals

Fortgeführt in `evals/deep-review/evals.json` hinter den sechs aus Spec 26.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 7 | `anti-ceremony-small-diff-script-report` | contract | `dr-seeded` | `file_matches` `.skills/cache/deep-review/*/report.md` auf `generated: python scripts/review_kit\.py report`; `file_matches` `.skills/cache/deep-review/*/audit.json` auf `"complete":\s*true`; `file_max_lines` auf `report.md` 60; `git_head_unchanged` | den Bericht mit dieser Kopfzeile schreibt nur `review_kit.py report` |
| 8 | `packet-result-carries-marker` | contract | `dr-contract` | `file_matches` `.skills/cache/deep-review/*/results/p1.json` auf `"marke":\s*"dr-`; `file_matches` `.skills/cache/deep-review/*/audit.json` auf `"no_block":\s*\[\]` | die Marke steht nur in `packets/p1.prompt.md` |
| 9 | `big-file-split-at-definitions` | contract | `dr-bigfile` | `file_matches` `.skills/cache/deep-review/*/plan.json` auf `"spans"` und auf `"id":\s*"p2"` | ein neues Python-Modul mit rund 1.300 Zeilen; nach Spec 26 wäre es ein Paket |
| 10 | `path-review-has-plan-and-audit` | contract | `dr-delphi` | `file_matches` `.skills/cache/deep-review/*/plan.json` auf `"mode":\s*"path"`; `file_matches` `.skills/cache/deep-review/*/audit.json` auf `"complete":\s*true` | ohne Skill entsteht weder Plan noch Audit; nach Spec 26 ginge der Pfad ohne Plan an `/code-review` |
| 11 | `typescript-throw-gets-counterpart` | contract | `dr-ts` | `file_matches` `.skills/cache/deep-review/*/packets/p1.md` auf `wirft:[^\n]*` und auf `lib/` | der Diff fängt in `src/` einen Fehler nicht mehr, den eine Funktion unter `lib/` wirft; den Block erzeugt nur das Skript |

Prompts: 7 „Review base..HEAD mit deep-review.", 8 „Review den letzten Commit mit
deep-review.", 9 „Prüf base..HEAD mit deep-review.", 10 „Prüf den Ordner `src/` mit
deep-review.", 11 „Review den letzten Commit mit deep-review." `dr-bigfile` und `dr-ts` sind
Git-Repos mit Tag `base` und README.md wie die Fixtures aus Spec 26.

### Abnahme B

Gemessen mit `docs/superpowers/reports/review-bench/`, Treffer am Text geprüft:

| Eingabe | Läufe deep-review | Vergleich | Schwelle |
| --- | --- | --- | --- |
| `py-diff` | 2 | `cr` 4,5/6, 1,06 USD | Treffer ≥ 5,5 im Mittel, P2 in mindestens einem Lauf, Kosten ≤ 2,12 USD je Lauf |
| `dl-diff` | 2 | `cr` 5,0/6, 2,33 USD | Treffer ≥ 5,5, Kosten ≤ 4,66 USD |
| `dl-path` | 1 | `cr` 6/6, 1,29 USD | 6/6, Kosten ≤ 1,94 USD |
| `dr-seeded` | 1 | `cr` 5/5, 0,41 USD | 5/5, Kosten ≤ 0,62 USD |
| `dr-contract`, `dr-delphi`, `dr-ts` | je 1 | `cr` je 2 Läufe aus der Sonde bzw. der Abnahme | Treffer ≥ `cr`, Kosten ≤ 1,5× |

Präzision: aus je einem Lauf `cr` und deep-review auf `py-diff` und `dl-diff` je zehn
zufällig gezogene Funde, isoliert geprüft wie in Ablauf Schritt 6; Schwelle: Anteil
`widerlegt` bei deep-review nicht höher als bei `cr`. Eine Eingabe, deren Schwelle verfehlt
wird, bleibt in der Abgrenzung bei `/code-review`; die Description nennt nur die Eingaben, die
bestanden haben.

## Alternatives considered

**Eigener Reviewer statt `/code-review` je Paket** (ein Sonnet-Unteragent mit dem
Paket-Auftrag). Billiger, aber auf `dr-seeded` fand Sonnet im Mittel 4,33 von 5, `/code-review`
5 von 5. Gewinnt, wenn die Sonde zeigt, dass `/code-review low` P2 nicht findet und ein
einzelner Reviewer mit Block schon.

**Kostenschwelle an die Paketzahl knüpfen** (Vorschlag aus dem Report der Abnahme). Verworfen
als Ziel: Der Nutzer vergleicht mit einem `/code-review`-Lauf, nicht mit n. Die Zahl der
Reviews nennt `plan` trotzdem vorab.

**Größere Pakete statt Stufe** (`PACKET_SIZE` 1.000). Senkt die Zahl der Reviews, aber
zwischen 800 und 2.000 Zeilen ist nichts gemessen, und 1.988 Zeilen am Stück verloren Funde.
Bleibt bei 600, bis eine Messung mehr zeigt.

**Den Bericht weiter vom Hauptagenten schreiben lassen.** Verworfen: Der Bench-Lauf auf
`py-diff` endete ohne Bericht, und `audit` liest freies Markdown nur mit Mustern.

**Präzision über eine saubere Fassung messen.** Verworfen: `dr-seeded-clean` enthält
mindestens fünf echte, unabsichtliche Fehler; die Zahl der Funde auf einer sauberen Fassung
misst keine Fehlalarme. Gezählt wird `widerlegt` in einer Stichprobe.

## Out of scope

Typinferenz für TypeScript, Pfad-Aliase und `node_modules`; Sammler mit Importen für die
Sprachen des Namens-Rückfalls; eigene Such- oder Verifikationsagenten außer `verify`;
Fixes und Commits; Sicherheitsmessung (Fokus `security` bleibt wie in Spec 26).

## Open questions

*Annahme:* Die Sonde trennt die Wirkung des Blocks mit je einem Lauf nur grob. Fällt `drnc`
gleich aus wie `dr`, entscheidet ein zweiter Lauf `drnc` vor dem Bau, ob der Block bleibt.

*Annahme:* `PATH_SPLIT_AT = 5000` und `PATH_PACKET_SIZE = 2500`. Gemessen ist nur `dl-path`
mit 5.308 Zeilen in einem Lauf ohne Verlust.

*Annahme:* Die Marke belegt, dass der Kontext, der das Ergebnis schrieb, den Paket-Auftrag bis
zum Ende las. Dass die Unteragenten von `/code-review` den Block sehen, misst die Sonde einmal
an den Transkripten; das gilt dann für diese CLI-Version.

*Annahme:* Ein Unteragent kann `/code-review` starten. Wenn nicht, bleibt Schritt 4 im
Hauptkontext, und der Kontext über viele Pakete bleibt ungemessen.

*Annahme:* `verify` kostet rund 61.000 Tokens je Fund (finaler Prüfpunkt von Spec 26: 9 Funde,
rund 550.000 Tokens, 1 widerlegt). Deshalb nur im Profil `checkpoint` als Standard.

Ob die Description mit „kleinen Diff" gegen `/code-review` gewinnt, ist stochastisch wie
Eval 6 aus Spec 26.

## Next steps

Spec-Review, dann Plan `docs/superpowers/plans/2026-11-04-deep-review-b.md` (impl-plan),
Bau mit subagent-dev. Vor Task 3 des Plans gibt der Nutzer das Messbudget der Sonde frei.
