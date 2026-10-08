# Spec 13: exercise\-forge — Verifizierte Lernaufgaben

Skill\-Spezifikation · Zyklus 13/14 · Entscheidung: Selbststudium, vier Aufgabentypen, Anki \+ Markdown\-Export · Abgeglichen mit Spec 00

## Problem

Aufgaben\-Generatoren liefern ungetestete Aufgaben: Musterlösungen sind falsch, Multiple\-Choice\-Distraktoren versehentlich auch richtig, Schwierigkeit ist ein Bauchgefühl\-Label, Aufgaben hängen an keinem Lernziel, und der Export in echte Lernwerkzeuge fehlt. Wer damit lernt, übt an fehlerhaftem Material — das Gegenteil des Zwecks.

## Constraints

Zielgruppe: Selbststudium (die Aufgaben füttern den Lernassistenten aus Zyklus 14 — gemeinsames Aufgaben\-Schema als Schnittstelle). Vier Typen: Multiple Choice, offene Fragen, Coding\-Aufgaben, Flashcards. Export: Markdown\-Übungsblatt (Aufgaben \+ getrennter Lösungsteil) und Anki (CSV/apkg). Blind\-Verifikation ist Pflicht\-Gate für jede Aufgabe — keine Ausnahme. Portables Frontmatter.

## Approach

**Keine Aufgabe erreicht den Lernenden, die nicht blind gelöst wurde.** Das ist das prüfende\-Skript\-Prinzip, angewandt auf Didaktik: Ein Subagent ohne Sicht auf die Musterlösung löst die Aufgabe; Abweichung heißt, die Aufgabe ist verdächtig — nicht der Agent.

**Skill\-Struktur:**

```
exercise-forge/
├── SKILL.md                (Workflow, Gate-Regeln, Schwierigkeits-Modell, Contract)
├── references/
│   ├── task-schemas.md     (die vier Typen: Aufbau, Qualitätsregeln, Beispiele)
│   ├── distractors.md      (MC-Distraktor-Handwerk: plausibel, eindeutig falsch,
│   │                        echte Denkfehler abbildend, kein „alle Antworten richtig")
│   └── difficulty.md       (operationalisierte Schwierigkeit: Schritte × Vorwissen × Transfer)
├── scripts/
│   ├── verify_blind.py     (Tier 1; Blind-Lösung orchestrieren, Abgleich, Urteil; G2)
│   ├── run_coding.py       (Tier 2: pytest; Test-Suite gegen Muster- und Blind-Lösung)
│   └── export.py           (Tier 1; Aufgaben-JSON → Markdown-Blatt / Anki-CSV)
└── evals/evals.json
```

**Workflow:** Lernziel klären (Thema \+ Bloom\-Ebene: Erinnern/Verstehen/Anwenden/Analysieren — bestimmt den Aufgabentyp: Flashcards fürs Erinnern, MC fürs Verstehen, Coding/Transfer fürs Anwenden) → Aufgabe im festen Schema erzeugen: Stamm, ggf. Optionen, Musterlösung, Lösungsweg, Bewertungskriterien (offene Fragen), Schwierigkeits\-Vektor → **Blind\-Gate** → Export.

**Blind\-Verifikation je Typ:** *MC:* Der Blind\-Agent wählt und begründet; wählt er einen Distraktor mit valider Begründung, ist der Distraktor kaputt (versehentlich richtig oder mehrdeutig). *Offene Fragen:* Blind\-Antwort wird gegen die Bewertungskriterien gescort; erfüllt eine fachlich richtige Antwort die Kriterien nicht, sind die Kriterien zu eng. *Coding:* vollständig mechanisch — `run_coding.py` lässt die Test\-Suite gegen Musterlösung (muss grün sein) und Blind\-Lösung laufen; scheitert eine korrekte Blind\-Lösung an den Tests, sind die Tests überspezifiziert. *Flashcards:* Rückseite beantwortet exakt die Vorderseite, eine Information pro Karte (Regeln in task\-schemas.md), Blind\-Check auf Eindeutigkeit der Frage.

**Schwierigkeit operationalisiert (difficulty.md):** kein „leicht/mittel/schwer" aus dem Bauch, sondern ein Vektor: Anzahl nötiger Lösungsschritte, vorausgesetztes Wissen (benannte Konzepte), Transferdistanz (Aufgabe ≙ gelerntem Beispiel vs. neuer Kontext). Das Label wird daraus abgeleitet und ist damit begründbar — und der Lernassistent (Zyklus 14) kann gezielt „eine Stufe schwerer" anfordern.

**Aufgaben\-JSON als Schnittstelle:** Alle Aufgaben leben in einem festen JSON\-Schema (Typ, Lernziel, Bloom, Schwierigkeit, Stamm, Lösung, Kriterien, Verifikations\-Protokoll). `export.py` rendert daraus das Markdown\-Übungsblatt (Lösungsteil getrennt, für ehrliches Üben) und Anki\-CSV (Flashcards direkt; MC als Karte mit verdeckten Optionen). CSV bleibt der Default, weil es mit der Stdlib auskommt (Tier 1); `.apkg` via genanki wäre Tier 2 und damit nach der Tier\-Regel aus Spec 00 §3 begründungspflichtig — der Anki\-UI\-Import kostet einen Klick und spart eine Abhängigkeit. Die Aufgaben\-JSONs liegen neben der Wissensdatei aus Spec 12 unter `~/.skills/verified-research/research/<thema>.exercises.json`. Das Verifikations\-Protokoll bleibt am Aufgaben\-Objekt — jede exportierte Aufgabe trägt ihren Prüfnachweis.

**Anti\-Rationalisierungs\-Tabelle (Auszug):** „Die Lösung ist offensichtlich richtig" → offensichtlich ist kein Prüfverfahren; Blind\-Gate läuft immer. „Der Distraktor ist halt knapp daneben" → knapp daneben mit valider Begründung ist kaputt. „Zehn Aufgaben auf einmal sparen Prüfzeit" → ungeprüfte Menge ist kein Wert; das Gate skaliert mit. „Schwierig heißt: klingt kompliziert" → der Vektor entscheidet, nicht der Klang.

**Evals:** (1) Eingepflanzte MC\-Aufgabe mit versehentlich\-richtigem Distraktor — fängt sie das Gate? (2) Coding\-Aufgabe mit überspezifizierten Tests (korrekte Alternativlösung scheitert) — wird sie als Aufgaben\-Fehler erkannt? (3) Offene Frage mit zu engen Kriterien — schlägt der Kriterien\-Check an? (4) „Mach mir 20 Karten zu X" — bleibt jede Karte atomar (eine Information) statt Karten\-Müllhalde? (5) Schwierigkeits\-Anforderung „eine Stufe schwerer" — ändert sich der Vektor nachvollziehbar (mehr Schritte/Transfer), nicht nur die Wortwahl?

## Alternatives considered

Lehre\-Modus (Aufgaben für Dritte, Moodle/GIFT\-Export, Rubrics für Bewertende) verworfen per Nutzerentscheidung — das Schema ist erweiterbar, ein Lehre\-Renderer wäre v2 ohne Kernänderung. Verifikation per Selbst\-Check im selben Kontext verworfen: Wer die Lösung kennt, löst nicht blind — die Unabhängigkeit des Subagents ist der Mechanismus. Fertige Aufgabenbanken importieren statt generieren verworfen: Der Wert liegt in Aufgaben zum *eigenen* aktuellen Lernstoff (Anschluss an Zyklus 14 und an visual\-summary\-Lernkarten).

## Out of scope

Lernstands\-Tracking und Session\-Führung (Lernassistent, Zyklus 14), Moodle/GIFT\-Export, Aufgaben\-Pools für Klassen/Teams, Plagiats\-/Ähnlichkeitsprüfung, PDF\-Layout (Markdown reicht; visual\-summary kann hübschen).

## Open questions

Blind\-Verifikation bei sehr leichten Flashcards — Stichprobe statt 100 %, um Token zu sparen, oder kompromisslos alle? Die Antwort entscheidet zugleich, ob das Blind\-Gate das teuerste oder das billigste Gate der Sammlung wird.

## Next steps

Aufgaben\-JSON\-Schema festziehen (Schnittstelle zu Zyklus 14 zuerst klären); verify\_blind.py mit den vier Typ\-Protokollen implementieren; run\_coding.py (pytest\-basiert); distractors.md und difficulty.md schreiben; export.py für Markdown \+ Anki\-CSV; Eval 1 (Distraktor\-Trap) und 2 (überspezifizierte Tests) zuerst fahren.
