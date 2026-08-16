---
name: review-context
description: Use before a code review runs — builds a deterministic context package (diff plus targeted Ist/Soll — feature spec, PR description, or commit messages; touched symbols and their callers; project conventions) so the reviewer does not have to guess what a change should achieve. Triggers include "bereite den Review-Kontext vor", "sammle den Kontext für den PR", "was ist das Soll für diesen Diff". Does NOT perform the review itself — for that use /code-review ("review mal meinen Diff", "schau dir den PR an"). For security questions route to /security-review or trailofbits/skills, not here — this skill has no security lens.
---

# review-context — Kontextpaket für /code-review

**Diese Skill reviewt nichts.** Sie sammelt nur, was ein Reviewer sonst raten müsste: das
Soll (Feature-Spec, PR-Beschreibung, Commit-Messages) und gezieltes Ist (Vorher-Stand,
Signaturen berührter Symbole und ihrer Aufrufer, Projekt-Konventionen). Das eigentliche
Review — Linsen, Widerlegung, Verdicts, Fixes/Kommentare — liefert Claude Code bereits als
`/code-review` mit.

## Warum diese Skill existiert

Spec 04 beschrieb ursprünglich eine eigene Linsen-Engine mit drei parallelen Subagents,
Widerlegungs-Pass und zwei Renderern. Sie wird **nicht** gebaut: `/code-review` liefert genau
diese Pipeline bereits aus, und eine zweite Fassung würde nur um dasselbe Triggering
konkurrieren (Spec 00 §5 — echte Namenskollision verlangt Umbenennung oder Verzicht, nicht
Koexistenz). Additiv bleibt allein Schritt 2 der ursprünglichen Pipeline — das Kontextpaket —,
weil ein generischer Reviewer keinen Zugriff auf die Artefakte der Geschwister-Skills dieser
Sammlung hat (Feature-Specs unter `docs/specs/wip/`, `docs/decisions.md`) und deshalb raten
muss, was eine Änderung erreichen sollte.

## Ablauf

1. **Sammeln:**
   ```bash
   python skills/review-context/scripts/collect_context.py --range HEAD~1..HEAD
   python skills/review-context/scripts/collect_context.py                      # Arbeitsverzeichnis gg. HEAD
   python skills/review-context/scripts/collect_context.py --range main..feature/x --pr-description "…"
   ```
   Schreibt `.skills/cache/review-context.json` (Ephemera nach Spec 00 §1, gitignored,
   jederzeit neu erzeugbar — kein Grund, es zu committen oder von Hand zu pflegen).
2. **Befunde lesen.** `findings` im Paket ist kein „nice to have". Meldet es „Änderung ohne
   benanntes Soll ist nicht reviewbar" oder „Diff ist leer", sag das dem Nutzer, bevor
   `/code-review` läuft — nicht stillschweigend übergehen.
3. **An `/code-review` übergeben.** Nenne den Pfad `.skills/cache/review-context.json` und
   welches Teilpaket zu welcher Linse gehört (siehe `references/context-packets.md`). Rufe
   danach `/code-review` auf — diese Skill tut das Review nicht selbst.

## Contract

- **Kein Soll wird erfunden.** Fehlt Feature-Spec, PR-Beschreibung und (bei Ranges mit
  mindestens zwei Commits) Commit-Messages, trägt das Paket den Befund „Änderung ohne
  benanntes Soll ist nicht reviewbar" — es verweigert nicht, es liefert das Paket mitsamt
  dieser Feststellung.
- Ein Range mit genau **einem** Commit zählt dessen eigene Subject-Zeile nicht als Soll — sie
  beschreibt den Diff, nicht das Ziel dahinter. Erst ab zwei Commits im Range erzählt die
  Historie mehr als der Diff selbst.
- Eine PR-Beschreibung zählt als Soll, ist im Paket aber `"weak": true` — schwächer als eine
  Feature-Spec, weil sie kein festes Schema hat.
- Jede Kappung (Aufrufer, Geschwisterdateien, Dateiinhalt, Patch) trägt ihre Zahl im Paket
  (`"N weitere … nicht gezeigt (Obergrenze M)"`). Stilles Abschneiden ist der einzige
  verbotene Weg.
- Kleine Diffs bekommen kleine Pakete — kein Subagent, keine Linsen-Prompts, keine feste
  Zeremonie. Das Skript ist Tier 1 und läuft immer im Hauptkontext.
- `docs/decisions.md` wird nach der Konsumenten-Regel gelesen (Spec 00 §1): fehlt die
  Kopfzeile oder passt das Schema nicht, wird die Datei sichtbar übersprungen, nie geraten.

## Anti-Rationalisierungs-Tabelle

| Gedanke | Realität |
| --- | --- |
| „Ich weiß doch, was der Diff soll" | Dein Wissen steht nirgends im Paket — der Reviewer sieht nur, was `collect_context.py` gefunden hat. |
| „Kein Soll gefunden, dann schreib ich halt eins" | Das Skript markiert den Befund, es erfindet nichts. Ein geratenes Soll ist schlimmer als ein benanntes Fehlen. |
| „Ich sollte jetzt gleich reviewen, ich hab doch den Kontext" | Das ist `/code-review`. Diese Skill endet mit dem Paket, nicht mit einem Urteil. |
| „Sicherheitsfragen kann ich hier mit reinpacken" | Spec 04 schließt eine Security-Linse ausdrücklich aus. `/security-review` oder trailofbits/skills. |
| „100 Aufrufer, zeig sie alle, sonst fehlt was" | Deckelung mit benannter Grenze — die Zahl steht im Paket, nicht die volle Liste. |
| „Ein Zweizeiler braucht das volle Paket auch" | Er bekommt es — nur klein. Kein Sondermodus für Mini-Diffs, nur weniger Inhalt. |

## Abgrenzung

- **`/code-review`** — das eigentliche Review (Linsen parallel, adversariale Verifikation je
  Finding, Verdicts confirmed/plausible, `--fix` im Selbst-Modus, `--comment` im Fremd-Modus).
  Trigger wie „review mal meinen Diff", „schau dir den PR an" gehören dorthin, nicht hierher.
- **`/security-review`, trailofbits/skills** — Sicherheitsfragen. Diese Skill hat keine
  Security-Linse (Spec 04, Constraints) und routet nicht selbst dorthin weiter, sondern nennt
  nur die Zuständigkeit.
- Diese Skill braucht ein Git-Repository für den Diff. Ohne Repo sagst du das und hörst auf.
