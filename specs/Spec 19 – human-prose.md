# Spec 19: human-prose — Texte, die nicht nach Modell klingen, mit Nachmessung statt Behauptung

Skill-Spezifikation · Zyklus 19 · Entscheidung: eine Tier-1-Skill mit `measure.py` für vierzehn Prüfpunkte, zwei Modi (schreiben, überarbeiten), Vorher/Nachher als Artefakt; das Stilprofil bleibt bei `setup-writing-style` · Abgeglichen mit Spec 00 · Überarbeitet nach unabhängigem Review · Eingabe: `docs/superpowers/specs/2026-09-15-menschlich-schreiben-v0.1.md` (Entwurf des Nutzers, Version 0.1)

## Problem

Text aus einem Sprachmodell erkennt man an Zeichen, Rhythmus und Floskeln, nicht an
Fehlern. Der Entwurf des Nutzers (24 Regeln `### R…` in fünf Gruppen, zwei Register,
ein Überarbeitungsablauf in sieben Schritten, zehn Prüfpunkte; 276 Zeilen) macht daraus
prüfbare Kriterien. Was fehlt, ist die Skill, die sie beim Schreiben lädt, und das
Skript, das sie misst — ohne Skript bleibt jede Regel ein Wunsch, wie der Entwurf in
seiner zweiten nicht-leeren Zeile selbst sagt.

Gemessen am 2026-09-15 (Python, `str.split` für Wörter, wo nichts anderes steht):

- **Die Sammlung schreibt selbst so.** 65 Prosa-Dateien (44 unter `docs/**/*.md`, 21
  `skills/*/SKILL.md`), 128.532 Wörter, 2.219 Geviertstriche: 17,3 je 1000 Wörter, dazu
  57 Gedankenstriche mit Leerzeichen und 422 Semikolons zwischen Buchstaben (970 roh,
  der Rest in Code und Tabellen). Jede der 65 Dateien enthält mindestens eines der drei
  Zeichen aus R1.1. Das ist kein Auftrag, sie umzuschreiben (Out of scope), aber der
  Beleg, dass die Regeln ohne Messung nicht greifen: Die Konvention aus Spec 00 wurde
  von denselben Modellen geschrieben, die sie einhalten sollen.
- **Der Entwurf besteht seine eigene Prüfung nicht überall.** Ohne Abschnitt 9: 1.672
  Wörter (`\w+`-Token; `str.split` zählt 1.716), 37 bis 48 Wörter auf -ung je nach
  Zählung von -ungen und -ungs, also 22 bis 29 je 1000 bei einer Grenze von 15 (R4.4);
  31 Doppelpunkte außerhalb von Tabellen, Überschriften und Listen, also 2,7 bis 2,9 je
  150 Wörter bei einer Grenze von 1 (R1.4). Ein Regeldokument ist kein Fließtext, aber
  die Spanne zeigt zweierlei: wie eng die Schwellen sind, und dass jede Zahl von der
  Zählmethode abhängt. Das Skript nennt seine Methode im Artefakt.
- **Die Rhythmusregel trennt die Beispiele nicht, die Token-Regeln tun es.** R2.1 hat
  drei Klauseln: ein Satz mit höchstens sechs Wörtern, einer mit mindestens zwanzig,
  Standardabweichung mindestens 40 Prozent des Mittels. Beispiel 3 Vorher (Satzlängen
  8, 11, 22, 7, 4) erfüllt alle drei; Beispiel 1 Vorher (9, 31, 13, 10) erfüllt die
  Streuungsklausel mit 57 Prozent (Populations-Standardabweichung) und reißt nur die
  Sechs-Wörter-Klausel; Beispiel 2 Vorher ist ein einzelner Satz. Was die Vorher- von
  den Nachher-Texten unterscheidet, sind Geviertstrich, tote Phrasen,
  Partizip-Anhängsel, Rahmen und fehlende Zahlen (R1.1, R4.1 bis R4.3, R3.5, R5.1). Alle
  sechs Beispieltexte haben höchstens fünf Sätze; das Zehnerfenster von R2.1 greift bei
  keinem.
- **Die Phrasenliste trifft wörtlich fast nichts.** Beispiel 1 Vorher (63 Wörter)
  enthält aus R4.1 wörtlich nur „es ist wichtig zu beachten". „spielt Caching eine
  entscheidende Rolle" hat ein Subjekt zwischen Verb und Objekt, „nicht nur … sondern
  auch" eine Lücke; „In der heutigen Softwareentwicklung" steht nicht in der Liste
  (dort „in der heutigen Welt"). Mit zwei Lückenmustern trifft die Liste drei Phrasen.
  Dazu kommen ein Partizip-Anhängsel (`, wodurch`), ein Konnektor am Satzanfang
  („Darüber hinaus", R2.2) und die Schlussfloskel aus R3.5 — je eigene Prüfpunkte.
- **Nachbarn.** Keine Skill der Sammlung befasst sich mit Schreibstil; Spec 00 §5 hat
  keine Zeile dafür. Im Nutzerprofil liegt `setup-writing-style` (im Skill-Katalog
  unter dem Präfix `anthropic-skills`): Es lernt aus gesendeten Mails ein Stimmprofil
  und speichert es als Skill `my-writing-style` unter
  `~/.claude/skills/my-writing-style/SKILL.md`, „only for drafting text the user will
  send as themselves, not for Claude's own replies". Das Profil ist hier nicht
  installiert, weder unter `~/.claude/skills/` noch im synchronisierten Profil.

## Constraints

- **Tier 1** (Spec 00 §3): `scripts/measure.py` nur Stdlib (`re`, `statistics`, `json`).
  Fehlt das Skript, sagt die Übergabe „ungeprüft: measure.py nicht verfügbar", nie
  „nachgemessen". Kein Geviertstrich in einem Wortlaut, den die Skill vorschreibt —
  `output_matches` liest alle Züge einer Antwort (`evalkit/dispatch.py::assistant_text`).
- **Gate-Grade:** Die SKILL.md *verlangt* Messung vor der Übergabe und Rückfrage statt
  erfundener Zahl (G1). `measure.py` *meldet* (G2): Exit 1 bei Befund, Exit 2, wenn
  der Text nicht lesbar ist. Kein Hook; nichts blockiert.
- **Vierzehn Prüfpunkte, fünf Urteile.** `measure.json` trägt vierzehn Zeilen: die
  zehn aus Abschnitt 8 (R5.2 darunter immer `unchecked`, R2.1 `unchecked` unter vier
  Sätzen) und vier Frequenzregeln, die der Entwurf mit Zahl versieht (R1.4, R4.5, R4.6,
  R2.4). Was das Skript nicht messen kann, steht getrennt unter `"judgement"`: ob eine
  Liste eine Liste ist (R3.1), ob eine Haltung dasteht (R5.3), ob Alt vor Neu steht
  (R5.4), ob ein Absatzende nur wiederholt (R2.3, zweiter Punkt), ob eine Zahl erfunden
  ist (R5.2). `unchecked` und `judgement` sind nie `pass`.
- **Schwellen sind Annahmen des Entwurfs**, nicht Messwerte (Abschnitt 10, erster
  Punkt). Sie stehen im Skript als Konstanten mit dem Vermerk `geschätzt`, und der
  Report nennt sie so. Kein Korpus liegt vor.
- **Phrasen sind Muster, keine Literale.** Die Listen aus R4.1 und R4.2 werden in
  `rules.md` als Regex geführt: Groß-/Kleinschreibung ignoriert, Wortgrenzen, bis zu
  zwei Wörter Lücke zwischen Verb und Objekt („spielt (\w+ ){0,2}eine entscheidende
  Rolle"), Lücke bis 80 Zeichen bei „nicht nur … sondern auch". Erwartungswert für
  Beispiel 1 Vorher: drei Treffer (siehe Problem), nicht vier.
- **Kurze Texte:** Unter zehn Sätzen ist der ganze Text das Fenster für R2.1; unter
  vier Sätzen ist R2.1 `unchecked`. Der Entwurf lässt das offen; die sechs Beispiele
  zwingen zur Entscheidung.
- **Artefakt:** `.skills/cache/human-prose/measure.json` mit `_meta` nach
  `docs/artifact-header.md` (JSON-Konvention; `artifact_header` prüft JSON nicht, die
  Evals binden per `file_matches` an `"skill": "human-prose"`). Je Prüfpunkt eine Zeile
  `{"id": "R1.1", "status": "pass|finding|unchecked", "value": …, "limit": …, "reason": …}`
  in fester Reihenfolge, dazu `"method"` (Satzteiler, Wortzählung) und `"judgement"`.
  Modus B: Schlüssel `before` und `after`; Modus A: Schlüssel `text`. Ohne Repo nach
  Spec 00 §1 unter `~/.skills/human-prose/`; der erste Lauf in einem Repo kündigt die
  Anlage von `.skills/cache/human-prose/` an (Bootstrap-Regel, `docs/artifact-header.md`).
- **Register** `fach` oder `kurz` wählt die Skill und nennt es in der Übergabe als
  wörtliche Zeile `Register: fach` oder `Register: kurz`; das Skript bekommt es als
  `--register`, ohne Angabe gilt `fach`.
- **Fremde Verträge bleiben.** Läuft Modus B über die Ausgabe einer anderen Skill
  (`handoff` verlangt `# Handoff — <Projektname>`, `dev-report` und `visual-summary`
  tragen Geviertstriche und Marker in ihren Templates, `explain` die Tokens `Next:`,
  `Unverified:`, `Source:`), bleiben deren Kopfzeilen, Tokens und Marker unverändert;
  R1.1 gilt für den Fließtext dazwischen. Der Bericht nennt, was ausgenommen wurde.
- **SKILL.md ≤ 150 Zeilen**, Deutsch mit englischen Bezeichnern; die 24 Regeln stehen
  in `references/rules.md`, nicht in der SKILL.md.
- **Keine Tippfehler als Stilmittel** (R5.5); keine Änderung an fremdem Text ohne
  Faktenabgleich (Modus B, Schritt 5).

## Approach

**Eiserne Regel:** *Kein überarbeiteter Text ohne Nachmessung, und keine Zahl im
Ergebnis, die nicht im Original, im Auftrag oder in der Antwort auf eine Rückfrage
stand.*

### Skill-Struktur

```
skills/human-prose/
├── SKILL.md                     Eiserne Regel, Register, Modus A und B, Anti-Zeremonie, Contract, Abgrenzung
├── references/
│   ├── rules.md                 der Entwurf v0.1, Abschnitte 0 bis 6 und 9: die 24 Regeln, Phrasenlisten als Muster, Beispiele
│   └── revise.md                Modus B: die sieben Schritte, Eingriffstiefe leicht/mittel/stark, Format von Rückfrage und Bericht
└── scripts/measure.py           Tier 1 — vierzehn Prüfpunkte, measure.json mit before/after oder text

evals/human-prose/evals.json, evals/fixtures/hp-empty/ (README.md, "git": true), hp-cache/, hp-vague/
tests/test_human_prose_measure.py
```

### Ablauf

1. **Register nennen.** `Register: fach` für Doku, Artikel, Fachtext; `Register: kurz`
   für Mail, Chat, Kommentar. Eine Zeile, in jeder Übergabe, auch im Anti-Zeremonie-Fall.
2. **Modus A, schreiben.** Der Text entsteht nach `references/rules.md`. Ab 120 Wörtern
   wird der Entwurf nach `.skills/cache/human-prose/draft.md` geschrieben und gemessen,
   Befunde werden behoben, und die Übergabe endet mit der Zeile
   `Nachgemessen: <p> pass, <f> Befunde, <u> ungeprüft`. Unter 120 Wörtern gelten die
   Regeln ohne Messung, ohne Zeile, ohne Artefakt — der Anti-Zeremonie-Fall.
   ```bash
   python skills/human-prose/scripts/measure.py .skills/cache/human-prose/draft.md --register fach --out .skills/cache/human-prose/measure.json
   ```
3. **Modus B, überarbeiten** (`references/revise.md`): messen, Diagnose je Regelnummer,
   umschreiben in der Reihenfolge Zeichen, Struktur, Satzbau, Wortwahl, Faktenabgleich,
   nachmessen, Bericht in drei bis fünf Zeilen. Liegt der Text in einer Datei, wird sie
   ersetzt; sonst steht der Text in der Antwort. **Die Skill wartet nie.** Verlangt R5.1
   eine Zahl, die das Original nicht hat, bleibt die Stelle allgemein (die vage Formel
   fällt trotzdem), und die Antwort endet mit `Rückfrage:` und der Liste der Stellen —
   im Chat füllt die Antwort des Nutzers sie in einer zweiten Runde, im `-p`-Modus
   bleibt es bei der Liste. So ist das Verhalten in einem Zug und in zwei Zügen dasselbe.
   ```bash
   python skills/human-prose/scripts/measure.py original.md --after text.md --register kurz --out .skills/cache/human-prose/measure.json
   # installiert: python .claude/skills/human-prose/scripts/measure.py …
   ```
4. **Stilprofil.** Existiert `my-writing-style` (Profil oder Projekt), gelten dessen
   Regeln im Konflikt; `measure.py` läuft trotzdem, und der Bericht nennt, welche
   Befunde das Profil überstimmt. Die Skill baut kein Profil; das tut
   `setup-writing-style`.

### `measure.py` — vierzehn Prüfpunkte

| # | Prüfpunkt | Mechanismus | Status |
| --- | --- | --- | --- |
| 1 | R1.1 Geviertstrich, Gedankenstrich mit Leerzeichen, Semikolon | Zeichensuche außerhalb von Code und Zitatblöcken | pass/finding |
| 2 | R4.1, R4.2 tote Phrasen | Muster aus `rules.md` (Constraints) | pass/finding |
| 3 | R4.3 Partizip-Anhängsel | `, wodurch|, was es|, ensuring|, allowing|, making it|, resulting in` je 300 Wörter | pass/finding |
| 4 | R2.1 Streuung | Satzteiler mit Abkürzungsliste (`z. B.`, `bzw.`, `Nr.`, `ca.`); je Zehnerfenster kürzester ≤ 6, längster ≥ 20, Populations-Standardabweichung ≥ 40 Prozent; Fenster nach Constraints | pass/finding/unchecked |
| 5 | R2.2 Konnektor am Absatzanfang | `(?im)^(darüber hinaus|zudem|außerdem|furthermore|moreover|additionally)\b` | pass/finding |
| 6 | R3.5 Rahmen | Eröffnungsphrasen im ersten, Schlussphrasen im letzten Absatz, Listen aus R3.5 | pass/finding |
| 7 | R5.1 Konkretion je Behauptungsabsatz | Absatz ohne Ziffer, Pfad, Backtick, Datum oder Großwort im Satzinneren — Heuristik, der Grund sagt es | pass/finding |
| 8 | R5.2 erfundene Zahl oder Zitat | nicht messbar | unchecked, immer |
| 9 | R3.3 Dreier-Aufzählungen | Listen und Komma-Aufzählungen; Anteil mit genau drei Elementen | pass/finding |
| 10 | R4.4 Wörter auf -ung je 1000 | Endungen -ung, -ungen, -ungs; Grenze 15 (geschätzt) | pass/finding |
| 11 | R1.4 Klammern, Doppelpunkte im Fließtext | je 200 bzw. 150 Wörter, Doppelpunkte vor Listen ausgenommen | pass/finding |
| 12 | R4.5 Passivanteil | `werden`-Form plus Partizip II im Satz — Heuristik | pass/finding |
| 13 | R4.6 Hedges | Liste aus R4.6 je 300 Wörter | pass/finding |
| 14 | R2.4 Fragmente | Satz ohne finites Verb — Heuristik; je 200 Wörter im Register `fach` | pass/finding |

Alle Grenzen nach Register (Abschnitt 6). Ausgabe: `measure.json` und eine
Zusammenfassung auf stdout, bei `--after` mit Vorher und Nachher nebeneinander.
Zitatblöcke (`> `) werden nicht gemessen: fremder Text. Markdown-Listenpunkte zählen
als je ein Satz.

### Contract

- **Kein überarbeiteter Text ohne Nachmessung.** Modus B endet mit `measure.json`
  (Schlüssel `before`, `after`) und dem Bericht; ohne Skript lautet die Übergabe
  „ungeprüft: measure.py nicht verfügbar".
- **Keine erfundene Konkretion.** Ins Ergebnis kommt keine Zahl, kein Name, kein
  Datum, das nicht im Original, im Auftrag oder in einer Antwort des Nutzers stand.
  Fehlt eine Zahl, die R5.1 verlangt, steht die Stelle unter `Rückfrage:`.
- **`unchecked` ist kein `pass`.** `measure.json` zählt `unchecked` getrennt und führt
  die fünf Urteile unter `judgement`; die Übergabezeile nennt `ungeprüft` mit Zahl.
- **Faktenabgleich vor Nachmessung.** Jede Aussage des Originals steht im Ergebnis
  und umgekehrt (Modus B, Schritt 5); Kürzen ist erlaubt, Weglassen einer Aussage
  ist ein Befund im Bericht.
- **Anti-Zeremonie-Fall:** Ein Text unter 120 Wörtern in Modus A bekommt Regeln und die
  Register-Zeile, kein Skript, keine `Nachgemessen:`-Zeile, kein Artefakt. Eine Antwort
  im Chat, die niemand als Text bestellt hat, löst die Skill nicht aus.
- **Das Profil gewinnt, das Skript bleibt.** Ein installiertes `my-writing-style`
  überstimmt einzelne Regeln; der Bericht nennt, welche.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| „schreib mir eine Mail / einen Abschnitt / einen Artikel", „das klingt nach KI", „überarbeite den Text", „menschlicher" | **human-prose** | setup-writing-style (baut das Stimmprofil `my-writing-style` aus gesendeten Mails; diese Skill liest es nur); visual-summary (11) verdichtet Vorliegendes in ein Format, ändert keinen Stil; explain (15) erklärt einen Begriff mit festem Antwortvertrag, dessen Tokens `Next:`, `Unverified:`, `Source:` bleiben, auch wenn human-prose den Text formt |

`dev-report` (02) und `handoff` erzeugen Texte aus Git und Sitzung; sie sind
Zulieferer, keine Konkurrenten — ein „mach den Wochenreport menschlicher" ist Modus B
über deren Fließtext, ihre Kopfzeilen und Marker bleiben (Constraints). `/simplify`
betrifft Code, nicht Prosa.

### Evals

Alle mechanisch. Jeder Eval hängt an einem skill-eigenen Token oder Artefakt:
`measure.json` mit `"skill": "human-prose"`, die Zeilen `Register:`, `Nachgemessen:`,
`Rückfrage:`. Die Abwesenheit von Geviertstrich und Floskeln kommt dazu, weil ein
Basismodell beides nachweislich schreibt (17,3 Geviertstriche je 1000 Wörter in der
eigenen Sammlung), aber Abwesenheit allein ist stochastisch und trägt keinen Eval.
Die Fixture-Texte von `hp-cache` stammen aus Abschnitt 9 des Entwurfs; der Text von
`hp-vague` ist eigener Text dieser Spec nach dem Muster von R5.1.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-short-mail-no-measurement` | contract | `hp-empty`: `README.md` mit einer Zeile, `"git": true` (eine Git-Fixture ohne Datei scheitert in `prepare()` am leeren Commit). Prompt: „Schreib mit human-prose eine kurze Mail ans Team: Deployment gestern 21:40 bis 22:15 down, Ursache Migration lief auf Prod länger als im Test, Rollback-Plan heute Abend." | `output_matches "^Register: kurz"`; `file_absent .skills/cache/human-prose/measure.json`; `must_not: output_matches "Nachgemessen:"`; `must_not: output_matches "—"`; `must_not: output_matches "(?i)ich hoffe"` | Die Register-Zeile ist Doktrin; unter 120 Wörtern läuft kein Skript, das Artefakt fehlt, weil die Regel es sagt. Die Floskel „ich hoffe" steht zweimal im Vorbild (Beispiel 3 Vorher) |
| 2 | `revise-writes-before-and-after` | contract | `hp-cache`: `text.md` mit dem Vorher-Text aus Beispiel 1 (63 Wörter; drei Phrasen nach Muster, ein Partizip-Anhängsel, ein Konnektor, Rahmen), `"git": true`. Prompt: „Überarbeite text.md mit human-prose, Register fach, Eingriffstiefe mittel." | `file_exists .skills/cache/human-prose/measure.json`; `file_matches measure.json "\"skill\": \"human-prose\""`; `file_matches measure.json "\"before\""`; `file_matches measure.json "\"after\""`; `must_not: file_matches text.md "(?i)zusammenfassend lässt sich sagen|es ist wichtig zu beachten|entscheidende Rolle"`; `must_not: file_matches text.md ", wodurch"` | `measure.json` an diesem Ort schreibt nur diese Skill; die drei Muster stehen wörtlich in der Fixture (R4.1 zweimal, R3.5 einmal) |
| 3 | `vague-text-asks-instead-of-inventing` | contract | `hp-vague`: `text.md` mit „Verschiedene Faktoren beeinflussen die Latenz. In vielen Fällen hilft ein Cache, und zahlreiche Unternehmen setzen ihn ein." — keine Zahl, kein Name; `"git": true`. Prompt: „Mach text.md mit human-prose konkreter." | `output_matches "^Rückfrage:"`; `file_exists .skills/cache/human-prose/measure.json`; `must_not: file_matches text.md "\d+\s*(ms|Millisekunden|Prozent|%)"`; `must_not: file_matches text.md "(?i)verschiedene Faktoren|zahlreiche Unternehmen"` | Ein Basismodell, das „konkreter" hört, erfindet 400 Millisekunden; die Skill schreibt um, lässt die Stelle allgemein und fragt. In einem Zug grün, weil sie nie wartet |
| 4 | `long-draft-ends-with-measurement-line` | contract | `hp-empty`. Prompt: „Schreib mit human-prose einen Doku-Abschnitt von etwa 300 Wörtern darüber, warum ein Cache für Preise ein kürzeres TTL braucht als für Stammdaten; Zahlen nur, wenn ich sie dir gebe: Stammdaten TTL eine Stunde, Preise fünf Minuten." | `output_matches "^Nachgemessen: \d+ pass, \d+ Befunde, \d+ ungeprüft"`; `file_exists .skills/cache/human-prose/measure.json`; `file_matches measure.json "\"text\""`; `must_not: output_matches "—"`; `must_not: output_matches "(?im)^(darüber hinaus|zudem|außerdem)\b"` | Zeile und Artefakt sind skill-eigen; das Konnektor-Muster ist R2.2 wörtlich, am Zeilenanfang. Die Zahlen kommen aus dem Auftrag (Eiserne Regel) |
| 5 | `routing-sounds-like-ai-without-skill-name` | contract | `hp-cache`. Prompt: „Das klingt nach KI. Überarbeite text.md." — ohne Skill-Namen | `file_exists .skills/cache/human-prose/measure.json`; `file_matches measure.json "\"skill\": \"human-prose\""` | Pflicht-Routing-Eval; stochastisch — ein roter Lauf zeigt die Kollision mit `visual-summary` oder mit gar keiner Skill, ein grüner beweist nichts |

Je Eval ein Prompt; Typen `file_exists`, `file_absent`, `file_matches`,
`output_matches` aus `evalkit/schema.py`; `output_matches` läuft mit `re.MULTILINE`,
deshalb tragen die Zeilen-Tokens `^`. Das Skript ist im Eval-Workspace unter
`.claude/skills/human-prose/scripts/` vorhanden (`prepare()` kopiert den
Skill-Ordner). Ein Judge kommt nicht vor; die Frage „ist der Text besser" beantwortet
kein Eval, nur „hat die Skill getan, was der Contract sagt". Sobald der Harness beim
Nutzer läuft: `--without-skill` über alle fünf (Spec 18) — bei Eval 1 entscheidet
dann die Register-Zeile, ob er etwas misst.

## Alternatives considered

**Nur das Skript, keine Skill** — `measure.py` als Prüfer über beliebige Texte, die
Regeln in `CLAUDE.md`. Verworfen: Ein Prüfer ohne Ablauf misst, nachdem der Text
fertig ist; die Rückfrage statt erfundener Zahl und der Faktenabgleich sind Ablauf,
nicht Messung. Gewinnt, wenn es nur um einen Lint für vorhandene Texte geht.

**Vollbau** — dazu eine Regel in `lint_skill.py` für die Prosa der Sammlung, ein Hook
auf `docs/`-Commits, Korpus-Kalibrierung, Profil-Erzeugung. Verworfen: vier Zuschnitte
auf einmal; die 2.219 Geviertstriche der Sammlung sind Konvention aus Spec 00, kein
Fehler; ein Hook wäre G3 ohne irreversiblen Schaden. Gewinnt, sobald die Sammlung
selbst nach diesen Regeln schreiben soll — dann als eigene Spec mit Register wie in
Spec 17.

**Die Regeln in eine bestehende Skill hängen** (`references/` von `explain` oder
`visual-summary`). Verworfen: keine Skill dort schreibt Mails oder überarbeitet
fremden Text; der Trigger „das klingt nach KI" hätte keinen Ort.

**Evals mit Judge** („der Text klingt menschlich"). Verworfen: Stimmungsurteil, das
Spec 00 §2 ausschließt, und ein Judge, der selbst Modelltext bevorzugt. Die
mechanischen Assertions binden an das, was der Entwurf messbar gemacht hat.

**Modus A für jede Antwort** (Abschnitt 10, vierter Punkt). Verworfen: Eine Skill
lädt, wenn ihr Trigger greift, nicht bei jedem Chat; und eine Zwei-Satz-Antwort mit
`Nachgemessen:` wäre Zeremonie. Die Grenze liegt bei 120 Wörtern und bei „ein Text
wurde bestellt".

**Warten auf die Rückfrage** (Entwurf Abschnitt 7, Schritt 3 wörtlich: „wird gefragt
statt erfunden"). Verworfen als Halt: Im `-p`-Modus gibt es einen Zug, und ein Eval,
dessen Skill anhält, lässt `text.md` unverändert. Die Skill fragt, aber nach dem
Umschreiben, mit der Stelle allgemein gehalten. Gefragt wird trotzdem, erfunden nie.

**Streuung als Hauptkriterium.** Verworfen nach Messung: Die Streuungsklausel von R2.1
erfüllen zwei von drei Vorher-Texten, Beispiel 3 sogar alle drei Klauseln. Das Skript
prüft sie weiter, aber die Skill lernt aus den Beispielen, dass Floskel, Zeichen und
Konkretion den Unterschied machen.

## Out of scope

- Die Prosa dieser Sammlung (Specs, Reports, SKILL.md) umschreiben oder linten; Spec 00
  bleibt die Konvention dort.
- Das Stimmprofil bauen oder ändern — `setup-writing-style`.
- Ein Referenzkorpus und kalibrierte Schwellen (Abschnitt 10); die Fixture dafür
  entsteht, wenn der Nutzer Texte gibt.
- Übersetzung, Rechtschreibprüfung, Lesbarkeitsindizes (Flesch), Erkennung fremden
  Modelltexts als Urteil („das hat eine KI geschrieben").
- Englische Register: Die Regeln R4.2, R4.3 und R3.5 gelten für Englisch, die
  Schwellen aus Abschnitt 6 sind für Deutsch geschätzt; das Skript nimmt sie für beide.

## Open questions

- *Annahme:* Geltungsbereich sind Texte auf Zuruf (Mail, Doku, Artikel, Überarbeiten),
  nicht Claudes Chat-Antworten und nicht die Dokumente der Sammlung — widersprich,
  falls die Sammlung selbst so schreiben soll; dann wird das eine eigene Spec mit
  Register.
- *Annahme:* Ein installiertes `my-writing-style` gewinnt im Konflikt, das Skript
  läuft trotzdem — widersprich, falls das Profil das Skript aussetzen soll.
- *Annahme:* Die Schwellen des Entwurfs (Satzlänge, 15 -ung je 1000, 20 Prozent Passiv,
  drei Hedges je 300 Wörter) gelten ungemessen, als Konstanten mit Vermerk `geschätzt`
  — widersprich, falls fünf bis zehn eigene Texte vorliegen; dann werden sie Fixture
  und die Schwellen Messwerte.
- *Annahme:* Name `human-prose`; Modus-A-Grenze 120 Wörter; Register `fach` als
  Default; Datei wird in Modus B ersetzt, nicht kopiert; die Skill wartet nie auf die
  Rückfrage, sondern fragt nach dem Umschreiben.
- *Annahme:* Unter zehn Sätzen ist der ganze Text das Fenster von R2.1, unter vier ist
  R2.1 ungeprüft; Phrasen mit bis zu zwei Wörtern Lücke gelten als Treffer.
- *Annahme:* Ohne Repo liegt das Artefakt unter `~/.skills/human-prose/` (Spec 00 §1);
  der Harness isoliert `HOME` nicht (known-limits, „Isolation"), deshalb tragen alle
  fünf Fixtures `"git": true`.
- **Ungemessen:** ob die Heuristiken für Passiv, Fragment, Konkretion und Satzgrenze auf
  echten Texten tragen; der Bau prüft sie an den sechs Beispieltexten des Entwurfs mit
  den hier genannten Erwartungswerten und nennt im Report, was sie dort falsch zählen.
  Ob der Trigger „das klingt nach KI" hier landet, entscheidet der Harness (Eval 5).
- **Ungemessen:** ob ein Basismodell in Eval 1 und 4 tatsächlich Geviertstriche setzt;
  die 17,3 je 1000 sind aus Dokumenten gemessen, nicht aus Mails.

## Next steps

Plan mit `impl-plan` (16); Bau nach `skill-forge` (17) Schritt 3 bis 7. Reihenfolge im
Plan: `measure.py` mit Tests an den sechs Beispieltexten zuerst (Erwartungswerte aus
Problem und Constraints), dann `rules.md` aus dem Entwurf mit den Phrasen als Muster,
`revise.md`, SKILL.md, Evals, Nachbarn (Spec 00 §5, README, Abgrenzungen von `explain`
und `visual-summary`), known-limits, Report. Nach dem Bau die fünf Evals außerhalb des
Harness fahren wie bei Spec 17 und 18.
