# Spec 19: human-prose — Texte, die nicht nach Modell klingen, mit Nachmessung statt Behauptung

Skill-Spezifikation · Zyklus 19 · Entscheidung: eine Tier-1-Skill mit `measure.py` für die zehn Prüfpunkte, zwei Modi (schreiben, überarbeiten), Vorher/Nachher als Artefakt; das Stilprofil bleibt bei `setup-writing-style` · Abgeglichen mit Spec 00 · Eingabe: `docs/superpowers/specs/2026-09-15-menschlich-schreiben-v0.1.md` (Entwurf des Nutzers, Version 0.1)

## Problem

Text aus einem Sprachmodell erkennt man an Zeichen, Rhythmus und Floskeln, nicht an
Fehlern. Der Entwurf des Nutzers (24 Regeln in fünf Gruppen, zwei Register, ein
Überarbeitungsablauf, zehn Prüfpunkte; 276 Zeilen) macht daraus prüfbare Kriterien.
Was fehlt, ist die Skill, die sie beim Schreiben lädt, und das Skript, das sie misst —
ohne Skript bleibt jede Regel ein Wunsch, wie der Entwurf in seiner zweiten Zeile
selbst sagt.

Gemessen am 2026-09-15:

- **Die Sammlung schreibt selbst so.** 65 Prosa-Dateien unter `docs/` und
  `skills/*/SKILL.md`, 128.532 Wörter, 2.219 Geviertstriche: 17,3 je 1000 Wörter, dazu
  57 Gedankenstriche mit Leerzeichen und 16 Semikolons. Nach R1.1 des Entwurfs ist
  jede dieser Dateien Modelltext. Das ist kein Auftrag, sie umzuschreiben (Out of
  scope), aber der Beleg, dass die Regeln ohne Messung nicht greifen: Die Konvention
  aus Spec 00 wurde von denselben Modellen geschrieben, die sie einhalten sollen.
- **Der Entwurf besteht seine eigene Prüfung nicht überall.** Ohne die Beispiele:
  1.588 Wörter, 44 auf -ung, also 27,7 je 1000 bei einer Grenze von 15 (R4.4);
  Doppelpunkte 2,9 je 150 Wörter bei einer Grenze von 1 (R1.4). Ein Regeldokument ist
  kein Fließtext, aber die Zahl zeigt, wie eng die Schwellen sind, und dass das Skript
  sagen muss, worauf es läuft.
- **Die Rhythmusregel trennt die Beispiele nicht, die Token-Regeln tun es.** R2.1
  verlangt eine Standardabweichung der Satzlänge von mindestens 40 Prozent des Mittels.
  Von den drei „Vorher"-Texten in Abschnitt 9 erfüllen zwei das schon (Beispiel 1: 57
  Prozent, Beispiel 3: 60 Prozent); Beispiel 2 ist ein einzelner Satz. Was die Vorher-
  von den Nachher-Texten unterscheidet, sind Geviertstrich, tote Phrasen,
  Partizip-Anhängsel, Rahmen und fehlende Zahlen (R1.1, R4.1 bis R4.3, R3.5, R5.1). Alle
  sechs Beispieltexte haben höchstens fünf Sätze; das Zehnerfenster von R2.1 greift bei
  keinem.
- **Nachbarn.** Keine Skill der Sammlung befasst sich mit Schreibstil; Spec 00 §5 hat
  keine Zeile dafür. Im Nutzerprofil liegt `setup-writing-style` (Anthropic): Es lernt
  aus gesendeten Mails ein Stimmprofil und speichert es als Skill `my-writing-style`
  unter `~/.claude/skills/my-writing-style/SKILL.md`, „only for drafting text the user
  will send as themselves, not for Claude's own replies". Das Profil ist hier nicht
  installiert, weder unter `~/.claude/skills/` noch im synchronisierten Profil.

## Constraints

- **Tier 1** (Spec 00 §3): `scripts/measure.py` nur Stdlib (`re`, `statistics`, `json`).
  Fehlt das Skript, sagt die Übergabe „ungeprüft — measure.py nicht verfügbar", nie
  „nachgemessen".
- **Gate-Grade:** Die SKILL.md *verlangt* Messung vor der Übergabe und Rückfrage statt
  erfundener Zahl (G1). `measure.py` *meldet* (G2): Exit 1 bei Befund, Exit 2, wenn
  der Text nicht lesbar ist. Kein Hook; nichts blockiert.
- **Was das Skript nicht messen kann, ist `unchecked`, nie `pass`:** ob eine Liste eine
  Liste ist (R3.1), ob eine Zahl erfunden ist (R5.2), ob eine Haltung dasteht (R5.3),
  ob Alt vor Neu steht (R5.4), ob ein Absatzende nur wiederholt (R2.3, zweiter Punkt).
  Das Skript nennt diese fünf als „Urteil des Schreibenden" im Artefakt.
- **Schwellen sind Annahmen des Entwurfs**, nicht Messwerte (Abschnitt 10, erster
  Punkt). Sie stehen im Skript als Konstanten mit dem Vermerk `geschätzt`, und der
  Report nennt sie so. Kein Korpus liegt vor.
- **Kurze Texte:** Unter zehn Sätzen ist der ganze Text das Fenster für R2.1; unter
  vier Sätzen ist R2.1 `unchecked`. Der Entwurf lässt das offen; die sechs Beispiele
  zwingen zur Entscheidung.
- **Artefakt:** `.skills/cache/human-prose/measure.json` mit `_meta` nach
  `docs/artifact-header.md` (JSON-Konvention; `artifact_header` prüft JSON nicht, die
  Evals binden per `file_matches` an `"skill": "human-prose"`). Je Prüfpunkt eine Zeile
  `{"id": "R1.1", "status": "pass|finding|unchecked", "value": …, "limit": …, "reason": …}`
  in fester Reihenfolge; bei Modus B unter den Schlüsseln `before` und `after`.
- **Register** `fach` oder `kurz` wählt die Skill und nennt es in der Übergabe; das
  Skript bekommt es als `--register`, ohne Angabe gilt `fach`.
- **SKILL.md ≤ 150 Zeilen**, Deutsch mit englischen Bezeichnern; die 24 Regeln stehen
  in `references/rules.md`, nicht in der SKILL.md.
- **Keine Tippfehler als Stilmittel** (R5.5); keine Änderung an fremdem Text ohne
  Faktenabgleich (Modus B, Schritt 5).

## Approach

**Eiserne Regel:** *Kein überarbeiteter Text ohne Nachmessung, und keine Zahl im
Ergebnis, die nicht im Original oder in der Antwort auf eine Rückfrage stand.*

### Skill-Struktur

```
skills/human-prose/
├── SKILL.md                     Eiserne Regel, Register, Modus A und B, Anti-Zeremonie, Contract, Abgrenzung
├── references/
│   ├── rules.md                 der Entwurf v0.1, Abschnitte 0 bis 6 und 9: die 24 Regeln mit Prüfkriterium und Beispielen
│   └── revise.md                Modus B: die sieben Schritte, Eingriffstiefe leicht/mittel/stark, Format der Rückfrage und des Berichts
└── scripts/measure.py           Tier 1 — die zehn Prüfpunkte aus Abschnitt 8, measure.json mit Vorher/Nachher

evals/human-prose/evals.json, evals/fixtures/hp-cache/, hp-vague/, hp-mail/
tests/test_human_prose_measure.py
```

### Ablauf

1. **Register nennen.** `fach` für Doku, Artikel, Fachtext; `kurz` für Mail, Chat,
   Kommentar. Ein Satz in der Übergabe, kein Absatz.
2. **Modus A, schreiben.** Der Text entsteht nach `references/rules.md`. Ab 120 Wörtern
   läuft das Skript über den Entwurf, Befunde werden behoben, und die Übergabe endet
   mit einer Zeile `Nachgemessen: <n> Prüfpunkte pass, <m> ungeprüft (Urteil)`. Unter
   120 Wörtern gelten die Regeln ohne Messung, und es gibt keine Zeile — das ist der
   Anti-Zeremonie-Fall.
3. **Modus B, überarbeiten** (`references/revise.md`): messen, Diagnose je Regelnummer,
   Rückfrage bei Faktenlücke, umschreiben in der Reihenfolge Zeichen, Struktur,
   Satzbau, Wortwahl, Faktenabgleich, nachmessen, Bericht in drei bis fünf Zeilen.
   Liegt der Text in einer Datei, wird sie ersetzt; sonst steht der Text in der
   Antwort. Kommt auf die Rückfrage keine Antwort (etwa im `-p`-Modus), bleibt die
   Stelle allgemein und der Bericht führt sie unter `Offen:`.
   ```bash
   python skills/human-prose/scripts/measure.py original.md --after text.md --register kurz --out .skills/cache/human-prose/measure.json
   # installiert: python .claude/skills/human-prose/scripts/measure.py …
   ```
4. **Stilprofil.** Existiert `my-writing-style` (Profil oder Projekt), gelten dessen
   Regeln im Konflikt; `measure.py` läuft trotzdem, und der Bericht nennt, welche
   Befunde das Profil überstimmt. Die Skill baut kein Profil; das tut
   `setup-writing-style`.

### `measure.py` — zehn Prüfpunkte

| # | Prüfpunkt (Abschnitt 8) | Mechanismus | Status |
| --- | --- | --- | --- |
| 1 | R1.1 Geviertstrich, Gedankenstrich mit Leerzeichen, Semikolon | Zeichensuche außerhalb von Code und Zitatblöcken | pass/finding |
| 2 | R4.1, R4.2 tote Phrasen | Wortliste aus `rules.md`, Groß-/Kleinschreibung ignoriert, Wortgrenzen | pass/finding |
| 3 | R4.3 Partizip-Anhängsel | Muster `, wodurch|, was es|, ensuring|, allowing|, making it|, resulting in` je 300 Wörter | pass/finding |
| 4 | R2.1 Streuung | Satzteiler mit Abkürzungsliste (`z. B.`, `bzw.`, `Nr.`, `ca.`); je Zehnerfenster kürzester ≤ 6, längster ≥ 20, Standardabweichung ≥ 40 Prozent; Fenster nach Constraints | pass/finding/unchecked |
| 5 | R2.2 Konnektor am Absatzanfang | Liste aus `rules.md` | pass/finding |
| 6 | R3.5 Rahmen | Eröffnungs- und Schlussphrasen im ersten und letzten Absatz | pass/finding |
| 7 | R5.1 Konkretion je Behauptungsabsatz | Absatz ohne Ziffer, Pfad, Backtick, Eigenname (Großwort, das nicht am Satzanfang steht) oder Datum | pass/finding — grob, der Bericht sagt „Heuristik" |
| 8 | R5.2 erfundene Zahl oder Zitat | nicht messbar | unchecked, immer |
| 9 | R3.3 Dreier-Aufzählungen | Listen und Aufzählungen mit Komma; Anteil mit genau drei Elementen | pass/finding |
| 10 | R4.4 Wörter auf -ung je 1000 | Wortendung, Grenze 15 (geschätzt) | pass/finding |

Dazu, weil der Entwurf sie mit Zahl versieht: R1.4 (Klammern, Doppelpunkte im
Fließtext), R4.5 Passivanteil (Hilfsverb `werden` plus Partizip II, Heuristik), R4.6
Hedges je 300 Wörter, R2.4 Fragmente (Satz ohne finites Verb, Heuristik). Alle mit
Register-Grenzen aus Abschnitt 6. Ausgabe: `measure.json` und eine Zusammenfassung auf
stdout mit Vorher und Nachher nebeneinander.

### Contract

- **Kein überarbeiteter Text ohne Nachmessung.** Modus B endet mit `measure.json`
  (Schlüssel `before`, `after`) und dem Bericht; ohne Skript lautet die Übergabe
  „ungeprüft — measure.py nicht verfügbar".
- **Keine erfundene Konkretion.** Fehlt eine Zahl, die R5.1 verlangt, steht eine
  `Rückfrage:`-Zeile in der Antwort, oder die Stelle bleibt allgemein und steht unter
  `Offen:`. Ins Ergebnis kommt keine Zahl, kein Name, kein Datum, das nicht im Original
  oder in einer Antwort des Nutzers stand.
- **`unchecked` ist kein `pass`.** Fünf Prüfpunkte sind Urteil des Schreibenden;
  `measure.json` nennt sie so, und die Übergabezeile zählt sie getrennt.
- **Faktenabgleich vor Nachmessung.** Jede Aussage des Originals steht im Ergebnis
  und umgekehrt (Modus B, Schritt 5); Kürzen ist erlaubt, Weglassen einer Aussage
  ist ein Befund im Bericht.
- **Anti-Zeremonie-Fall:** Ein Text unter 120 Wörtern in Modus A bekommt Regeln, kein
  Skript, keine `Nachgemessen:`-Zeile, kein Artefakt. Eine Antwort im Chat, die
  niemand als Text bestellt hat, löst die Skill nicht aus.
- **Das Profil gewinnt, das Skript bleibt.** Ein installiertes `my-writing-style`
  überstimmt einzelne Regeln; der Bericht nennt, welche.

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| „schreib mir eine Mail / einen Abschnitt / einen Artikel", „das klingt nach KI", „überarbeite den Text", „menschlicher" | **human-prose** | setup-writing-style (baut das Stimmprofil `my-writing-style` aus gesendeten Mails; diese Skill liest es nur); visual-summary (11) verdichtet Vorliegendes in ein Format, ändert keinen Stil; explain (15) erklärt einen Begriff mit festem Antwortvertrag, dessen Tokens `Next:`, `Unverified:`, `Source:` bleiben, auch wenn human-prose den Text formt |

`dev-report` (02) und `handoff` erzeugen Texte aus Git und Sitzung; sie sind
Zulieferer, keine Konkurrenten — ein „mach den Wochenreport menschlicher" ist Modus B
über deren Ausgabe. `/simplify` betrifft Code, nicht Prosa.

### Evals

Alle mechanisch. Diskriminator ist `measure.json` mit `"skill": "human-prose"`, die
Zeile `Nachgemessen:`, das Wort `Rückfrage:` — und die Abwesenheit von Geviertstrich
und Floskeln in einem Text, den ein Basismodell nachweislich mit beidem schreibt
(17,3 Geviertstriche je 1000 Wörter in der eigenen Sammlung). Abwesenheit allein ist
stochastisch; deshalb hängt jeder Eval zusätzlich an einem skill-eigenen Token.
Fixture-Texte stammen aus Abschnitt 9 des Entwurfs.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-short-mail-no-measurement` | contract | `hp-mail`: leeres Repo mit `.git`. Prompt: „Schreib mit human-prose eine kurze Mail ans Team: Deployment gestern 21:40 bis 22:15 down, Ursache Migration lief auf Prod länger als im Test, Rollback-Plan heute Abend." | `file_absent .skills/cache/human-prose/measure.json`; `must_not: output_matches "Nachgemessen:"`; `must_not: output_matches "—"`; `must_not: output_matches "(?i)ich hoffe"` | Unter 120 Wörtern läuft kein Skript — das Artefakt fehlt, weil die Regel es sagt, nicht weil die Skill fehlte; die Floskel „ich hoffe" ist im Prompt-Stoff angelegt (Beispiel 3) |
| 2 | `revise-writes-before-and-after` | contract | `hp-cache`: `text.md` mit dem Vorher-Text aus Beispiel 1 (Caching, 63 Wörter, vier tote Phrasen, ein Partizip-Anhängsel, Rahmen), `"git": true`. Prompt: „Überarbeite text.md mit human-prose, Register fach, Eingriffstiefe mittel." | `file_exists .skills/cache/human-prose/measure.json`; `file_matches measure.json "\"skill\": \"human-prose\""`; `file_matches measure.json "\"before\""`; `file_matches measure.json "\"after\""`; `must_not: file_matches text.md "(?i)zusammenfassend lässt sich sagen|es ist wichtig zu beachten|spielt eine entscheidende Rolle"`; `must_not: file_matches text.md ", wodurch"` | `measure.json` an diesem Ort schreibt nur diese Skill; die vier Phrasen sind die Liste aus R4.1 |
| 3 | `vague-text-asks-instead-of-inventing` | contract | `hp-vague`: `text.md` mit „Verschiedene Faktoren beeinflussen die Latenz. In vielen Fällen hilft ein Cache, und zahlreiche Unternehmen setzen ihn ein." — keine Zahl, kein Name. Prompt: „Mach text.md mit human-prose konkreter." | `output_matches "Rückfrage:|Offen:"`; `must_not: file_matches text.md "\d+\s*(ms|Millisekunden|Prozent|%)"`; `must_not: file_matches text.md "(?i)verschiedene Faktoren|zahlreiche Unternehmen"` | Ein Basismodell, das „konkreter" hört, erfindet 400 Millisekunden; die Skill fragt. Das Token `Rückfrage:` ist Doktrin |
| 4 | `long-draft-ends-with-measurement-line` | contract | `hp-mail` (leer). Prompt: „Schreib mit human-prose einen Doku-Abschnitt von etwa 300 Wörtern darüber, warum ein Cache für Preise ein kürzeres TTL braucht als für Stammdaten; Zahlen nur, wenn ich sie dir gebe: Stammdaten TTL eine Stunde, Preise fünf Minuten." | `output_matches "Nachgemessen: \d+ Prüfpunkte pass, \d+ ungeprüft"`; `file_exists .skills/cache/human-prose/measure.json`; `must_not: output_matches "—"`; `must_not: output_matches "(?i)darüber hinaus|zudem|in diesem abschnitt"` | Zeile und Artefakt sind skill-eigen; die Konnektoren sind der Marker aus R2.2 |
| 5 | `routing-sounds-like-ai-without-skill-name` | contract | `hp-cache`. Prompt: „Das klingt nach KI. Überarbeite text.md." — ohne Skill-Namen | `file_exists .skills/cache/human-prose/measure.json`; `must_not: file_matches text.md "—"` | Pflicht-Routing-Eval; stochastisch — ein roter Lauf zeigt die Kollision mit `visual-summary` oder mit gar keiner Skill, ein grüner beweist nichts |

Je Eval ein Prompt; Typen `file_exists`, `file_absent`, `file_matches`,
`output_matches` aus `evalkit/schema.py`. Das Skript ist im Eval-Workspace unter
`.claude/skills/human-prose/scripts/` vorhanden (`prepare()` kopiert den
Skill-Ordner). Ein Judge kommt nicht vor; die Frage „ist der Text besser" beantwortet
kein Eval, nur „hat die Skill getan, was der Contract sagt". Sobald der Harness beim
Nutzer läuft: `--without-skill` über alle fünf (Spec 18).

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

**Streuung als Hauptkriterium.** Verworfen nach Messung: Zwei von drei Vorher-Texten
erfüllen R2.1 bereits. Das Skript prüft sie weiter, aber die Skill lernt aus den
Beispielen, dass Floskel, Zeichen und Konkretion den Unterschied machen.

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
  Default; Datei wird in Modus B ersetzt, nicht kopiert.
- *Annahme:* Unter zehn Sätzen ist der ganze Text das Fenster von R2.1, unter vier ist
  R2.1 ungeprüft.
- **Ungemessen:** ob die Heuristiken für Passiv, Fragment, Eigenname und Satzgrenze auf
  echten Texten tragen; der Bau prüft sie an den sechs Beispieltexten des Entwurfs und
  nennt im Report, was sie dort falsch zählen. Ob der Trigger „das klingt nach KI" hier
  landet, entscheidet der Harness (Eval 5).
- **Ungemessen:** ob die `Rückfrage:` in Modus B den Nutzer erreicht, bevor die Skill
  weiterschreibt — im Chat ja, im `-p`-Modus nein; Eval 3 akzeptiert beide Wege.
- Beim Bau zu entscheiden: ob `measure.py` Markdown-Listen als Sätze zählt (Vorschlag:
  je Punkt ein Satz) und ob Zitatblöcke ganz ausgenommen sind (Vorschlag: ja, fremder
  Text wird nicht gemessen).

## Next steps

Plan mit `impl-plan` (16); Bau nach `skill-forge` (17) Schritt 3 bis 7. Reihenfolge im
Plan: `measure.py` mit Tests an den sechs Beispieltexten zuerst, dann `rules.md` aus
dem Entwurf, `revise.md`, SKILL.md, Evals, Nachbarn (Spec 00 §5, README, Abgrenzungen
von `explain` und `visual-summary`), known-limits, Report. Nach dem Bau die fünf Evals
außerhalb des Harness fahren wie bei Spec 17 und 18.
