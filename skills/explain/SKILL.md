---
name: explain
description: Use to explain a concept, term, mechanism, or theory topic with a fixed answer contract — a short correct answer first (never longer than four sentences, at any depth), then an explanation scaled by an effort level (low/medium/high/xhigh/max), then at most two named follow-up topics. Marks what it is not certain about with a literal `Unverified:` instead of softening the wording, and researches before answering from high upward. Triggers include "erklär mir X", "was ist X", "wie funktioniert X", "erklär mir X ausführlich", "explain X", "/explain X". Not for anything about a codebase, repository or architecture — those go to architecture-map or /code-review, never here. Not a study session with retrieval and spacing (use learning-coach) and not a summary of material you already have (use visual-summary).
---

# explain — kurze Antwort zuerst, Tiefe auf Abruf, Unsicherheit benannt

**Die Kurzantwort ist der Vertrag.** Was danach kommt, skaliert mit `effort` — die
ersten vier Sätze nie.

## Antwortform

1. **Kurzantwort** — höchstens **vier Sätze**, ohne Überschrift, ohne Beispiel, ohne
   Randfall, ohne Quellenangabe, ohne Marker. Auf jeder Effort-Stufe gleich knapp.
   Sie ist vollständig korrekt: Ein Vorbehalt, ohne den die Aussage falsch wäre,
   gehört hierher. „Es kommt darauf an" ist keine Kurzantwort, sondern deren
   Vermeidung — wenn es darauf ankommt, steht hier, worauf.
2. **Ausführung** — Umfang nach Stufe, siehe Tabelle und
   `references/effort-ladder.md`.
3. **Anschluss** — beginnt mit der wörtlichen Zeile `Next:` und nennt **höchstens
   zwei benannte** Themen, die sachlich als Nächstes kommen, plus das Angebot, in
   einen Punkt tiefer zu gehen. **Bei `low` entfällt Teil 3 ersatzlos.** Nie eine
   Optionsliste, nie ein generisches „möchtest du mehr wissen?".

`Next:`, `Unverified:` und `Source:` sind **wörtliche englische Tokens**, unabhängig
von der Antwortsprache. Sie werden nicht übersetzt und nicht umformuliert.

## Effort

| Stufe | Zusätzliche Schicht in Teil 2 | Teil 3 | Recherche |
| --- | --- | --- | --- |
| `low` | der Mechanismus, ein Absatz | entfällt | nein |
| `medium` (Default) | warum es so gebaut ist; ein durchgerechnetes Beispiel | ja | nein |
| `high` | Randfälle, Missverständnisse, Geltungsgrenzen | ja | ja |
| `xhigh` | konkurrierende Erklärungen desselben Gegenstands, abgewogen | ja | ja |
| `max` | Herkunft, Entwicklung, offene Streitfragen, Primärquellen | ja | ja |

Der Aufruf ist natürlichsprachlich; `/explain <Thema> <effort>` ist nur eine
Kurzform, die es im Web nicht gibt. Welche Formulierung welche Stufe auslöst, steht
in `references/effort-ladder.md`. Bei Mehrdeutigkeit gilt die niedrigere Stufe, und
die gewählte wird genannt — keine Rückfrage vor der Antwort.

## Ehrlichkeit — `references/honesty.md`

**Eine unmarkierte Aussage behauptet Gewissheit.** Das ist der Normalfall und wird
nicht ausgewiesen. Markiert wird nur, was davon abweicht:

- `Unverified:` — aus dem Gedächtnis, nicht belegt.
- `Source:` — nachgeschlagen, Quelle in derselben Zeile. Nie zitieren, was nicht
  tatsächlich geöffnet wurde.

Teil 1 trägt nie einen Marker. Ist nichts Gesichertes verfügbar, sagt Teil 1 in
einem Satz genau das.

**Hedging ist kein Marker.** Eine Formulierung weichzuspülen, statt die Unsicherheit
zu benennen, ist der Fehler, gegen den diese Skill existiert. Entscheidend ist,
worauf sich die Abschwächung bezieht: auf den Gegenstand (erlaubt und oft nötig) oder
auf die eigene Sicherheit (dann Marker statt Adverb).

Braucht eine Frage Provenienz, die einer Prüfung durch Dritte standhält —
regulatorisch, medizinisch, juristisch, finanziell —, sag das und verweise auf
`verified-research`, statt eine schwache Version davon zu liefern.

## Contract

- **Teil 1 ist nie länger als vier Sätze**, unabhängig von der Stufe.
- **Teil 3 entfällt bei `low`**, vollständig — kein verkürzter Anschluss.
- **Die drei Tokens sind wörtlich.** Übersetzt oder umformuliert sind sie wertlos.
- **`low` steuert den Umfang, nie die Korrektheit.**
- **Kein Codebase-Wissen.** Fragen zu diesem Projekt, seiner Architektur oder seinem
  Code gehören nicht hierher — auch dann nicht, wenn sie mit „erklär mir" beginnen.
- **Frontmatter:** nur `name`/`description`, portabel über Agenten hinweg.

Alles hier ist **G1 — Selbstauskunft** (Spec 00 §4): Diese Datei verlangt es; kein
Mechanismus erzwingt es. Es gibt kein Skript, keine Datei, keinen Zustand — die Skill
ist Tier 0 und läuft in claude.ai, Cowork und Claude Code identisch.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Bei `max` darf die Kurzantwort ausführlicher sein" | Vier Sätze auf jeder Stufe. Der Vertrag gilt oben, nicht nur unten. |
| „Ich bin mir nicht ganz sicher, ich formuliere es vorsichtiger" | Vorsichtige Formulierung ist kein Marker; `Unverified:` ist einer. |
| „Ich bin sicher genug, das braucht keinen Marker" | Dann ohne Marker — und du stehst für die Aussage gerade. Unmarkiert ist eine Behauptung, kein Ausweichen. |
| „Die Antwort ist deutsch, ich übersetze die Tokens mit" | Nein. Feste Tokens in jeder Sprache. |
| „Die Frage ist simpel, ich lasse die Form trotzdem stehen" | Bei `low` entfällt `Next:` ersatzlos und Teil 2 ist ein Absatz. |
| „Ich liste alle möglichen Anschlussthemen auf" | Höchstens zwei, benannt. Eine Auswahlliste ist Zeremonie. |
| „Erst mal nachfragen, wie tief er es will" | Nein — niedrigere Stufe wählen und sie nennen. Die Rückfrage kostet einen Zug und bringt nichts dazu. |
| „Er fragt nach Code, aber ‚erklär mir' ist doch mein Stichwort" | Der Auslöser ist das Thema, nicht das Verb. Codebase gehört woanders hin. |

## Abgrenzung

- **architecture-map**, **`/code-review`** — alles, was Code, Repo oder Architektur
  betrifft. `explain` erklärt Konzepte, nie ein konkretes Projekt.
- **learning-coach** — die strukturierte Lernsession mit Abruf, Fehleranalyse und
  Spacing. `explain` erklärt einmal und merkt sich nichts. Am Ende darf ein Satz das
  Thema dorthin anbieten; die Einstufung nimmt `learning-coach` vor, nicht diese
  Skill.
- **visual-summary** — verdichtet vorliegendes Material. `explain` erklärt einen
  Gegenstand, auch ohne dass etwas vorliegt.
- **human-prose** (19) — formt Prosa auf Zuruf und überarbeitet Texte; die drei
  wörtlichen Tokens dieser Skill bleiben stehen, auch wenn sie eine Erklärung umschreibt.
- **verified-research** — Recherche mit Quellenregister und Stichprobenprüfung.
