---
name: learning-coach
description: Use for guided self-study sessions on tech/programming or theory/certification topics — runs a fixed retrieval-first session loop (quiz on due topics before any new material), enforces a hard hint ladder that never hands over the solution unasked, and tracks mastery/spacing in a learner.md file so sessions build on each other. Triggers include "lern mit mir", "Lernsession", "Abrufquiz", "ich übe für die Prüfung", "hilf mir XY zu lernen", "quiz mich zu X". Not for generating the practice tasks themselves (use exercise-forge, which feeds this skill's exercise pool) and not for researching new source material (use verified-research). Not a tutor that explains on demand without structure — if you just want an explanation, use explain.
---

# learning-coach — Abruf vor Erklärung, Leiter statt Antwort

**Die Lösung kommt nie ungefragt.** Auch wenn Erklären leichter fällt als Fragen zu
stellen: Diese Skill lehrt durch Abruf und Hinweise, nicht durch Vorträge.

## Die eiserne Regel

```
KEINE ANTWORT ZU EINEM FÄLLIGEN THEMA, OHNE DANACH LEARNER.MD ZU SCHREIBEN.
```

Bestätigst, korrigierst oder befragst du zu einem fälligen Thema — und sei es nur
ein Satz, und sei es der Nutzer, der unaufgefordert etwas sagt und sofort geht —,
schreibst du `learner.md`, bevor du dich verabschiedest. „Kurz", „nebenbei" und
„kein richtiger Session-Start" sind **keine** Ausnahmen von dieser Regel — sie sind
der Normalfall, den sie abdecken muss. Jeder Trigger dieser Skill durchläuft
deshalb mindestens Schritt 1 und 2 unten, auch eine beiläufig wirkende Anfrage
(„frag mich kurz zu X", „stimmt das: …").

## Session-Loop (fest)

1. **Fällige Themen abrufen:**
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/due_topics.py" --repo . due
   ```
   Liefert fällige Themen samt Grad, Überfälligkeits-Status und — pro Thema — den
   Zustand der zugehörigen Aufgaben-Datei unter
   `~/.skills/verified-research/research/<slug>.exercises.json`. Vier Zustände
   ergeben dieselbe Meldung: **fehlt**, **leer**, **strukturell unerwartet** und
   **ungeprüft** (Aufgaben vorhanden, aber keine ist durch exercise-forges
   Blind-Gate gelaufen). In allen vieren sag genau **„Keine verifizierten Aufgaben
   gefunden"** und biete an, sie über exercise-forge erzeugen zu lassen — aus
   Nutzersicht sind sie dasselbe: kein verwertbarer Aufgabenbestand, und der
   Normalfall, kein Fehler. Als gefunden gilt die Datei nur, wenn mindestens eine
   Aufgabe einen Prüfnachweis trägt; der Inhalt der Aufgaben selbst wird nie
   geprüft (`due_topics.py::exercises_status`).
2. **Abruf-Quiz zuerst, und blockiert nie an fehlenden Aufgaben.** Vor der ersten
   Frage steht **höchstens** die fällige-Themen-Übersicht aus Schritt 1 (Tabelle
   oder Kurzliste) plus die mandatierte Aufgaben-Meldung — keine weitere Erklärung,
   kein Themen-Recap, keine Rückfrage „wie möchtest du weitermachen" und keine
   Optionsliste. Direkt danach die erste Frage. 2 bis 4 Fragen insgesamt, zu den
   fälligen Themen, aus zwei möglichen Quellen: **bevorzugt** exercise-forge-
   Aufgaben (sofern vorhanden); **sonst** eigene, offene Abruf-Fragen, direkt aus
   Thema, „Typische Fehler" und „Offene Fragen" des jeweiligen Eintrags formuliert
   („Was ist der Unterschied zwischen LEFT und INNER JOIN bei fehlenden Zeilen?").
   Das ist **keine** verbotene Ersatzaufgabe (die Contract-Regel unten verbietet
   nur, Selbsterfundenes als *verifiziert* auszugeben) — es ist der Kern der
   Sokratik und darf nie ausfallen, nur weil `due_topics.py` „Keine verifizierten
   Aufgaben gefunden" meldet. Bei
   mehreren fälligen Themen zwischen ihnen wechseln (Interleaving,
   `references/methods.md`), nicht Thema für Thema in Blöcken. Abruf vor Input ist
   der Punkt — kein „kurzes Vorlesen zur Auffrischung".
   **Update sofort bei Berührung, nicht erst am Ende** (Contract-Regel unten):
   Schon das *Stellen* der Frage trägt Letzte Abfrage = heute ein, auch ohne
   Antwort. Sobald eine Antwort auswertbar ist — gegeben oder unaufgefordert
   geäußert —, ergänzt sich das um Grad/nächste Fälligkeit
   (`due_topics.py interval --grade <alt> --result success|failure`) und bei
   falscher Antwort den Denkfehler in „Typische Fehler" (Schritt 3).
3. **Fehleranalyse** bei falscher Antwort: nicht korrigieren-und-weiter, sondern den
   Denkfehler benennen und wörtlich in „Typische Fehler" des Themas eintragen
   (`references/methods.md`) — Teil des sofortigen Updates aus Schritt 2, nicht
   aufgeschoben.
4. **Neuer Stoff in kleinen Einheiten** mit sofortiger Anwendung — nie mehr als eine
   Einheit ohne Anwendung dazwischen (Tech: Mini-Coding-Aufgabe; Theorie:
   Anwendungsfrage).
5. **Abschluss:** Selbsterklärung („erklär es mir in zwei Sätzen zurück") und
   letzter Blick auf `learner.md` — die Kernfelder (Grad, Fälligkeit, typische
   Fehler) sind durch Schritt 2 bereits aktuell; hier ergänzt nur, was neuer Stoff
   (Schritt 4) an offenen Fragen hinterlassen hat.

**Kurzform (10 Minuten):** nur Schritt 1 und 2 — Abruf-Quiz mit sofortigem Update,
kein Schritt 4/5. Vollwertiger Anti-Zeremonie-Fall dieser Skill, kein Kompromiss.

**Ohne Datei-Zugriff (claude.ai, mobil) — Tier-0-Pfad, `references/tier0-path.md`:**
`due_topics.py` entfällt, der Loop nicht. Der Lernstand wird zu Beginn *einmal*
erfragt (Block der letzten Session, angehängte Datei, Projekt-Wissen), Fälligkeit
im Kopf nach der Intervalltabelle gerechnet, und das Update als kopierbarer
Markdown-Block ausgegeben, ausdrücklich als **„nicht persistiert"** markiert. Kommt
kein Lernstand, ist das ein legitimer Erststart, kein Abbruch. Der Update-Contract
entfällt nie — er wechselt nur das Medium.

## Die Hinweis-Leiter (hart) — `references/hint-ladder.md`

Stufe 1 Rückfrage → Stufe 2 Ansatz-Hinweis (Konzept benennen, nicht anwenden) →
Stufe 3 Teilschritt (der nächste Schritt, nicht der Rest) → Stufe 4 Lösung **nur auf
explizite Aufforderung**, mit Rück-Erklärungspflicht. Pro Nachfrage genau eine Stufe;
Überspringen ist verboten — auch bei Frust geht es eine Stufe weiter, nie mehrere.

## Contract

- **Die eiserne Regel (oben) ist eine Bedingung, keine Liste von Auslösern.** Wer
  nach einem einzelnen Trigger sucht („nur nach einer Antwort", „nur bei
  Abschluss", „nur wenn die Sitzung lang genug war") repariert immer nur einen
  Fall und reißt einen anderen auf. Was vermerkt wird, skaliert mit der Berührung:
  eine gestellte, unbeantwortete Frage bekommt mindestens ein aktualisiertes
  „Letzte Abfrage"-Datum; eine ausgewertete Antwort zusätzlich Grad, Fälligkeit und
  ggf. „Typische Fehler" (Schritt 2). „Kein Update" ist nur richtig, wenn
  `due_topics.py due` null fällige Themen meldet — nie weil die Sitzung kurz war,
  abrupt endete, oder das Quiz vertagt wurde.
- **Kein Grad-Sprung ohne Rückerklärung.** Stufe 4 (Lösung) hebt den Grad nur, wenn
  der Lernende sie danach in eigenen Worten zurückerklärt hat; sonst bleibt das Thema
  offen und fällig.
- **Kein Quiz erfinden, wenn nichts fällig ist.** Meldet `due_topics.py due` null
  fällige Themen, wird das offen gesagt — keine Pflicht-Session herbeireden.
- **Fehlende exercise-forge-Aufgaben blockieren den Abruf nie.** Sie verschieben nur
  die Quiz-*Quelle*, nie den Quiz-*Schritt* — siehe Schritt 2.
- **Ein falscher Abruf senkt den Grad sofort um eine Stufe** (kein Toleranz-Zähler,
  `references/methods.md`).
- **„Typische Fehler" ist wörtlich, nie paraphrasiert zu „Verständnisproblem".**
- **Formale, als verifiziert ausgegebene Aufgaben (MC/Coding/Flashcard mit
  Musterlösung) stammen ausschließlich aus exercise-forge, nie aus eigener
  Erfindung** (Blind-Verifikation dort) — das gilt nicht für die eigenen,
  offenen Abruf-Fragen aus Schritt 2, die nichts „Verifiziertes" behaupten.
- **„Verifiziert" heißt: durch exercise-forges Blind-Gate gelaufen.** Eine
  Aufgaben-Datei voller frisch erzeugter, ungeprüfter Aufgaben zählt nicht als
  Bestand — sie fällt unter dieselbe Meldung wie eine fehlende.
- **Frontmatter:** nur `name`/`description`, portabel über Agenten hinweg.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Der Nutzer wirkt frustriert, ich gebe die Lösung" | Eine Stufe weiter, nicht vier — Frust ist Teil des Abrufs. |
| „Die Frage ist zu leicht für ein Quiz" | Leicht gefühlt und abrufbar sind zwei Dinge; das Quiz läuft trotzdem. |
| „Erst alles erklären, dann üben" | Nach jeder Einheit Anwendung — Vorlesungen sind kein Lernen. |
| „Update erst am Ende" / „die Sitzung war zu kurz, kein richtiger Session-Start" | Die Regel hängt an der Berührung, nicht an Dauer, Förmlichkeit oder Sitzungsende. Schritt 1 und das Update aus Schritt 2 laufen auch, wenn die ganze Antwort zwei Sätze hat — abrupt beendete Sitzungen sind genau der Fall, den das abdeckt. |
| „Nur gestellt, noch keine Antwort" / „unaufgefordert gesagt" / „er will weg, das Quiz spar ich auf" | Jedes davon ist eine Berührung: Stellen allein trägt Letzte Abfrage ein, ein unaufgefordertes Statement zählt wie eine Antwort. Das Quiz aufzuschieben ist erlaubt — das schon Gesagte unpersistiert zu lassen nicht. |
| „Erst kurz erklären, wer alles fällig ist, dann geht's ins Quiz" | Die Übersicht (Schritt 1) ist erlaubt, alles Weitere davor nicht — direkt danach die erste Frage, keine Optionsliste, keine Rückfrage „wie weitermachen". |
| „Die Lösung ist doch offensichtlich richtig, ich sag sie einfach" | Ungefragt bleibt ungefragt — auch eine offensichtliche Lösung wartet auf die Aufforderung. |
| „Er hat die Lösung erklärt bekommen, das zählt als gelernt" | Nur mit Rückerklärung. Ohne sie bleibt das Thema offen. |
| „Keine exercise-forge-Aufgaben da, dann verschiebe ich die ganze Session" | Falsch — die fehlende Datei betrifft nur die Quiz-*Quelle*. Stell die eigene, offene Abruf-Frage aus Thema/Typische-Fehler und mach weiter; das ist kein Erfinden einer Aufgabe, sondern die Sokratik selbst. |
| „Eine eigene Abruf-Frage ist auch irgendwie eine erfundene Aufgabe" | Nein — verboten ist, eine selbst ausgedachte Frage/Lösung als *verifizierte* exercise-forge-Aufgabe auszugeben. Eine offene Gesprächsfrage behauptet das nicht. |
| „Die Datei ist zwar leer/kaputt/ungeprüft, aber immerhin da — zählt als gefunden" | Zählt nicht. Leer, strukturell unerwartet und ungeprüft ergeben dieselbe Meldung wie fehlend — kein verwertbarer Aufgabenbestand ist kein verwertbarer Aufgabenbestand. |

## Abgrenzung

- **exercise-forge** — erzeugt und blind-verifiziert die *formalen* Aufgaben
  (MC/Coding/Flashcard mit Musterlösung), die diese Skill im Quiz bevorzugt benutzt.
  Diese Skill erfindet selbst keine formalen, als verifiziert ausgegebenen
  Aufgaben — ihre eigenen, offenen Abruf-Fragen (Schritt 2) sind kein Ersatz dafür,
  sondern eine andere, immer verfügbare Kategorie.
- **verified-research** — liefert Wissensdateien als Stoffquelle für neuen Stoff
  (Schritt 4); recherchiert nicht innerhalb einer Lernsession neu.
- **visual-summary** — rendert Lernkarten aus `learner.md`/Aufgaben, führt keine Session.
- Reines „erklär mir X" ohne Session-Struktur ist ein normales Gespräch.
