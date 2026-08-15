# Spec 14: learning\-coach — Sokratischer Lernassistent mit Lernstandsdatei

Skill\-Spezifikation · Zyklus 14/14 · Entscheidung: Tech \+ Theorie/Zertifizierungen, passives Spacing, harte Hinweis\-Leiter · Abgeglichen mit Spec 00

## Problem

Lern\-Skills sind heute Prompt\-Personas ohne Struktur, und sie scheitern an vier Punkten: Der Assistent erklärt, statt zu lehren (gibt die Antwort, sobald man fragt — das Gegenteil von Lernen); er hat kein Gedächtnis (jede Session beginnt bei null); er betreibt keine Abrufübung, obwohl Retrieval Practice der am besten belegte Lerneffekt ist; und es gibt kein Spacing. Was fehlt, ist kein besserer Ton, sondern eine Struktur, die Lernen erzwingt.

## Constraints

Lerngebiete: Tech/Programmierung (Coding\-Anwendungsteil via exercise\-forge, Spec 13) und Theorie/Zertifizierungen (abruf\- und MC\-lastig). Spacing passiv: `learner.md` führt Fälligkeiten, jede Session beginnt mit dem Abruf\-Quiz zu fälligen Themen — keine Scheduled\-Task\-Infrastruktur. Sokratik hart: Die Lösung kommt nie ungefragt; auch bei Frust geht es eine Stufe weiter auf der Leiter, nie mehrere. Gemeinsames Aufgaben\-JSON mit exercise\-forge als Schnittstelle. Portables Frontmatter.

## Approach

**Das Kernstück ist die Lernstandsdatei; die Session ist ein fester Loop; die Hinweis\-Leiter ist Gesetz.**

**Skill\-Struktur:**

```
learning-coach/
├── SKILL.md                (Doktrin, Session-Loop, Hinweis-Leiter, Contract)
├── references/
│   ├── learner-schema.md   (Aufbau von learner.md + Beispiel)
│   ├── hint-ladder.md      (die Leiter je Aufgabentyp, mit Formulierungsbeispielen)
│   └── methods.md          (Abrufübung, Spacing-Intervalle, Fehleranalyse, Interleaving)
├── assets/
│   └── learner-template.md
├── scripts/
│   └── due_topics.py       (Tier 1; learner.md parsen → fällige Themen + Abruf-Quiz-Vorschlag)
└── evals/evals.json
```

**Lernstandsdatei (`~/.skills/learning-coach/learner.md`, projektlokal überschreibbar — Spec 00 §1):** pro Thema: Beherrschungsgrad (0–4, operationalisiert: 0 nie gesehen … 4 erklärt es fehlerfrei und wendet es im Transfer an), letzte Abfrage, nächste Fälligkeit (Intervall wächst mit Erfolg, schrumpft bei Fehlern — einfache Spacing\-Regel in methods.md), typische Fehler (wörtlich festgehalten — die wertvollste Zeile der Datei), offene Fragen. Contract: **Jede Session endet mit dem Update**; eine Session ohne Update ist unvollständig. Die Datei gehört dem Lernenden — sie ist lesbar, editierbar und wandert mit ins Repo/Notizsystem.

**Session\-Loop (fester Ablauf):** (1) `due_topics.py` liefert fällige Themen → **Abruf\-Quiz zuerst** (2–4 Fragen aus dem Bestand, gern exercise\-forge\-Aufgaben; Abruf vor Input ist der Punkt — nicht „kurze Wiederholung" durch Vorlesen); (2) Fehleranalyse: falsche Antworten werden nicht korrigiert\-und\-weiter, sondern kurz seziert (welcher Denkfehler? → wandert in „typische Fehler"); (3) neuer Stoff in kleinen Einheiten mit sofortiger Anwendung (Tech: Mini\-Coding\-Aufgabe; Theorie: Anwendungsfrage) — nie mehr als eine Einheit ohne Anwendung dazwischen; (4) Abschluss: Selbsterklärung („erkläre es mir in zwei Sätzen zurück") und Update der Datei. Kurzform für 10\-Minuten\-Sessions definiert (nur Schritt 1\+4). Ohne Datei\-Zugriff (claude.ai, mobil) läuft die Skill als **Tier\-0\-Pfad**\: Der Loop funktioniert rein konversationell, `due_topics.py` entfällt, und das Update wird am Ende als kopierbarer Block ausgegeben und ausdrücklich als „nicht persistiert" gekennzeichnet — Sichtbarkeitsregel aus Spec 00 §3, kein stilles Auslassen des Contracts.

**Hinweis\-Leiter (hart):** Stufe 1 Rückfrage („was hast du versucht, wo hakt es?") → Stufe 2 Ansatz\-Hinweis (Konzept benennen, nicht anwenden) → Stufe 3 Teilschritt (der nächste Schritt, nicht der Rest) → Stufe 4 Lösung **nur auf explizite Aufforderung**, und dann mit Rück\-Erklärungspflicht (der Lernende erklärt die Lösung zurück, sonst zählt das Thema als offen, nicht gelernt). Pro Nachfrage genau eine Stufe; Überspringen ist verboten.

**Anti\-Rationalisierungs\-Tabelle (Auszug):** „Der Nutzer wirkt frustriert, ich gebe die Lösung" → eine Stufe weiter, nicht vier; Frust ist Teil des Abrufs. „Die Frage ist zu leicht für ein Quiz" → leicht gefühlt und abrufbar sind zwei Dinge; das Quiz läuft. „Erst alles erklären, dann üben" → nach jeder Einheit Anwendung; Vorlesungen sind kein Lernen. „Update der Datei spare ich mir heute" → ohne Update war die Session für das System unsichtbar.

**Zusammenspiel:** exercise\-forge liefert verifizierte Aufgaben ins gemeinsame JSON (learning\-coach fordert gezielt an: Thema, Bloom\-Ebene, „eine Stufe schwerer" über den Schwierigkeits\-Vektor); verified\-research (Spec 12) liefert Wissensdateien als Stoffquelle; visual\-summary (Spec 11) rendert Lernkarten. Der Lernassistent selbst erstellt keine Aufgaben — er nutzt geprüfte.

**Evals:** (1) Direkter Lösungs\-Wunsch mitten in der Aufgabe („sag mir einfach die Antwort") — kommt Stufe 4 mit Rück\-Erklärungspflicht statt nackter Lösung? (2) Frust\-Trap („das bringt nichts, ich versteh's nicht") — eine Stufe weiter statt Leiter\-Kollaps? (3) Session\-Start mit drei fälligen Themen — beginnt sie mit dem Abruf\-Quiz statt mit neuem Stoff? (4) Session\-Ende provoziert abrupt — wird das Update eingefordert/nachgeholt? (5) Falsche Quiz\-Antwort — folgt Fehleranalyse und landet der Denkfehler wörtlich in der Datei?

## Alternatives considered

Adaptive Hinweis\-Leiter (Abkürzung bei Blockade) verworfen per Nutzerentscheidung — der Abkürzungs\-Reflex ist genau das Risiko, das die harte Leiter neutralisiert. Aktives Spacing via Scheduled Tasks verworfen (passiv reicht; nachrüstbar als optionale Erinnerung ohne Strukturänderung). Fremdsprachen\-Modus verworfen (eigene Methodik — Produktion vor Rezeption, Audio — wäre ein eigener Adapter, wenn je gewünscht). Anki als alleiniges Spacing\-System erwogen: Anki behält die Karten (Export via exercise\-forge), aber die Session\-Führung und Fehleranalyse leisten Karten allein nicht — beides ergänzt sich.

## Out of scope

Aufgaben\-Erstellung (exercise\-forge), Fremdsprachen\-Didaktik, Scheduled\-Task\-Erinnerungen, Gamification (Punkte/Streaks — bewusst: die Fälligkeitsliste ist Motivation genug und lügt nicht), Multi\-Lerner\-Verwaltung.

## Open questions

Granularität der Themen in learner.md (Konzept\-Ebene „Closures" vs. Gebiets\-Ebene „JavaScript" — vermutlich zweistufig)? Beherrschungsgrad\-Herabstufung: nach wie vielen Fehlversuchen sinkt ein Grad\-4\-Thema zurück?

## Next steps

learner\-schema.md und Template festziehen (Schnittstellen\-Klärung mit exercise\-forge zuerst); hint\-ladder.md mit Formulierungsbeispielen je Aufgabentyp schreiben; due\_topics.py mit der Spacing\-Regel implementieren; Eval 1 und 2 (Lösungs\- und Frust\-Trap) zuerst fahren — sie prüfen den Kern der Doktrin; methods.md zuletzt (destilliert, keine Lernpsychologie\-Vorlesung).
