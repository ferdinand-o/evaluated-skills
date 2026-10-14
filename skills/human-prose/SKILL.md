---
name: human-prose
description: Use when someone orders a text or hands one over to be reworked and it must not read like model output — "schreib mir eine Mail", "schreib einen Abschnitt für die Doku", "das klingt nach KI", "überarbeite den Text", "mach das menschlicher", "make this sound human". Not for building the personal voice profile (use setup-writing-style; its my-writing-style is only read here), not for condensing material into a summary format (use visual-summary), and not for explaining a concept (explain keeps its answer contract even when this skill shapes the prose).
---

# human-prose — Texte, die nicht nach Modell klingen, mit Nachmessung

**Eiserne Regel:** *Kein überarbeiteter Text ohne Nachmessung, und keine Zahl im
Ergebnis, die nicht im Original, im Auftrag oder in der Antwort auf eine Rückfrage
stand.* G1 — diese Datei verlangt es; `scripts/measure.py` meldet (G2), was die
vierzehn Prüfpunkte aus `references/rules.md` finden, und schreibt es nach
`.skills/cache/human-prose/measure.json`.

## Ablauf

1. **Register nennen.** `Register: fach` für Doku, Artikel, Fachtext; `Register: kurz`
   für Mail, Chat, Kommentar. Eine wörtliche Zeile in jeder Übergabe, auch im kleinsten
   Fall. Die Grenzen je Register stehen in `rules.md`, Abschnitt 6.
2. **Modus A, schreiben.** Der Text entsteht nach `rules.md`: keine Geviertstriche,
   keine toten Phrasen, konkret wo der Auftrag Stoff liefert, Haltung wo eine gefragt
   ist. Ab 120 Wörtern kommt der Entwurf nach `.skills/cache/human-prose/draft.md`
   und wird gemessen:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/measure.py" .skills/cache/human-prose/draft.md --register fach --out .skills/cache/human-prose/measure.json
   ```
   Befunde beheben, dann die Übergabe mit der Zeile
   `Nachgemessen: <p> pass, <f> Befunde, <u> ungeprüft`. Unter 120 Wörtern gelten die
   Regeln ohne Skript, ohne Zeile, ohne Artefakt — der Anti-Zeremonie-Fall.
3. **Modus B, überarbeiten** nach `references/revise.md`: messen, Diagnose je
   Regelnummer, umschreiben (Zeichen, Struktur, Satzbau, Wortwahl), Faktenabgleich,
   nachmessen, Bericht in drei bis fünf Zeilen. Die Skill wartet nie: Fehlt eine Zahl,
   die R5.1 verlangt, fällt die vage Formel, die Stelle bleibt allgemein, und die
   Antwort endet mit `Rückfrage:` und der Liste der Stellen.
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/measure.py" original.md --after text.md --register kurz --out .skills/cache/human-prose/measure.json
   ```
   Liegt der Text in einer Datei, ersetzt das Ergebnis sie; sonst steht es in der
   Antwort.
4. **Stilprofil.** Existiert `my-writing-style` (Profil unter
   `~/.claude/skills/my-writing-style/SKILL.md` oder im Projekt), gelten dessen Regeln
   im Konflikt; das Skript läuft trotzdem, und der Bericht nennt, welche Befunde das
   Profil überstimmt. Diese Skill baut kein Profil; das tut `setup-writing-style`.

Fehlt das Skript, lautet die Übergabe „ungeprüft: measure.py nicht verfügbar", nie
„nachgemessen".

## Contract

- **Kein überarbeiteter Text ohne Nachmessung.** Modus B endet mit `measure.json`
  (Schlüssel `before` und `after`) und dem Bericht.
- **Keine erfundene Konkretion.** Keine Zahl, kein Name, kein Datum, kein Zitat im
  Ergebnis, das nicht im Original, im Auftrag oder in einer Antwort des Nutzers stand.
  Fehlt etwas, das R5.1 verlangt, steht die Stelle unter `Rückfrage:`.
- **`unchecked` ist kein `pass`.** Fünf Regeln (R3.1, R5.3, R5.4, R2.3 zweiter Punkt,
  R5.2) misst kein Skript; `measure.json` führt sie unter `judgement`, die
  Übergabezeile zählt `ungeprüft` mit Zahl.
- **Faktenabgleich vor Nachmessung.** Jede Aussage des Originals steht im Ergebnis
  und umgekehrt; Kürzen ist erlaubt, eine weggelassene Aussage ist ein Befund im
  Bericht.
- **Fremde Verträge bleiben.** Kopfzeilen, Tokens und Marker anderer Skills
  (`# Handoff — …`, `Next:`, `Unverified:`, `Einschätzung:`) bleiben in Modus B
  unverändert; die Regeln gelten für den Fließtext dazwischen.
- **Anti-Zeremonie-Fall:** Unter 120 Wörtern in Modus A gibt es die Register-Zeile und
  die Regeln, kein Skript, keine `Nachgemessen:`-Zeile, kein Artefakt. Eine
  Chat-Antwort, die niemand als Text bestellt hat, löst die Skill nicht aus.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Eine kleine Zahl macht es konkreter" | Eine erfundene Zahl ist die schlimmste Zeile im Text (R5.2). Die Stelle bleibt allgemein, und `Rückfrage:` holt die echte. |
| „Der Leser merkt den Gedankenstrich nicht" | Doch, das ist der erste Marker, den jeder kennt (R1.1). Komma, Klammer, Punkt oder Doppelpunkt, je nach Funktion (R1.3). |
| „Ich frage kurz nach und warte" | Im `-p`-Modus kommt keine Antwort, und der Text bleibt, wie er war. Umschreiben, Stelle allgemein lassen, am Ende fragen. |
| „Der Text ist kurz, da brauche ich das Skript nicht" | Unter 120 Wörtern stimmt das. Darüber ist „ich sehe keine Marker" die Selbstauskunft, die das Skript ersetzt. |
| „Drei Beispiele lesen sich runder" | Wenn zwei reichen, zwei (R3.3). Der Anteil der Dreier ist gemessen, nicht gefühlt. |
| „Ein zusammenfassender Schlusssatz schadet nicht" | Er ist der Rahmen, den R3.5 verbietet. Der Text endet, wenn er fertig ist. |
| „Die Schwellen sind doch nur geschätzt" | Stimmt, und das steht in jeder Zeile des Artefakts. Bis ein Korpus sie ersetzt, sind sie die Regel; ein Befund wird benannt, nicht wegdiskutiert. |

## Abgrenzung

- **setup-writing-style** (Anthropic, im Nutzerprofil) — baut das Stimmprofil
  `my-writing-style` aus gesendeten Mails, „only for drafting text the user will send
  as themselves". Diese Skill liest das Profil, wenn es da ist, und baut es nie.
- **visual-summary** (11) — verdichtet Vorliegendes in eines von vier Formaten und
  ändert keinen Stil. „Fass das zusammen" gehört dorthin; „mach das menschlicher"
  hierher, auch über eine Zusammenfassung von dort.
- **explain** (15) — erklärt einen Begriff mit festem Antwortvertrag; seine Tokens
  `Next:`, `Unverified:`, `Source:` bleiben, auch wenn diese Skill den Text formt.
- **dev-report** (02), **handoff** — erzeugen Texte aus Git und Sitzung; ein „mach den
  Wochenreport menschlicher" ist Modus B über deren Fließtext, ihre Kopfzeilen und
  Marker bleiben. `/simplify` betrifft Code, nicht Prosa.
