# Recherche-/Analyse-Fan-out

Der zweite Delegations-Fall neben paralleler Implementierung: Erkundung einer
großen Codebase oder eine Frage, deren Rohmaterial (Dutzende Dateien, ein
langer Log, viele Suchtreffer) den Hauptkontext fluten würde, wenn du sie
selbst liest. Anders als bei Implementierungs-Tasks gibt es hier keinen
`Files:`-Block und keine Überlappungsmatrix — Recherche-Agents schreiben
keinen Produktivcode, sie liefern zurück.

**Qualifiziert sich unabhängig vom Gate.** `plan_to_tasks.py` prüft Files-
Überlappung; ein Recherche-Fan-out hat keine Files zum Überlappen. Die
Entscheidung "lohnt sich Fan-out" ist stattdessen: Würde das Rohmaterial (der
Dateiinhalt, die Grep-Treffer, das Diff) den Hauptkontext mit mehr fluten, als
das destillierte Ergebnis wiegt? Wenn ja, Fan-out.

## Rückgabe-Schema

Jeder Recherche-Agent liefert **destillierte Daten, nie einen Prosa-Aufsatz**.
Das Schema ist absichtlich eng — nicht nur eine Empfehlung, ein Format, das
nichts anderes zulässt:

```markdown
## Findings

- <eine Beobachtung, ein Satz>
  - Beleg: `pfad/zu/datei.py:42`
  - Konfidenz: hoch | mittel | niedrig

- <nächste Beobachtung>
  - Beleg: `pfad/zu/anderer/datei.py:10-25`
  - Konfidenz: mittel
```

**Nichts anderes steht in der Datei.** Kein Titel, der den Auftrag
wiederholt; keine Einleitung ("Ich habe folgende Dateien durchsucht: …");
kein Abschnitt zum Vorgehen oder zur Methode; keine Zusammenfassung der
Zusammenfassung nach der Liste; keine wiederholte volle Pfadangabe außerhalb
der Beleg-Zeile; kein Meta-Kommentar über den Fan-out selbst ("Ich habe 3
Subagenten dispatcht, die …"). Ein Fund ist genau drei Zeilen: die
Beobachtung, `Beleg:`, `Konfidenz:`. Eine Findings-Datei mit drei Funden ist
zwölf bis fünfzehn Zeilen lang, nicht sechzig — jede Zeile darüber ist
Beiwerk, das der Hauptkontext genauso wenig braucht wie das Rohmaterial, das
der Fan-out ihm ersparen sollte.

**„Offene Fragen" ist kein Pflichtabschnitt.** Nur anhängen, wenn die
Recherche tatsächlich etwas nicht klären konnte — nie als leere oder
pro-forma-Sektion ("keine offenen Fragen"). Fehlt er, ist die Recherche
vollständig, und das sagt die Abwesenheit des Abschnitts bereits.

- **Beleg ist ein Pfad, keine Zusammenfassung.** Der Hauptkontext bekommt die
  Fundstelle, nicht den zitierten Absatz — wer nachlesen will, liest selbst.
- **Konfidenz ist Pflicht**, nicht Zierde: "hoch" heißt direkt im Code
  gesehen, "niedrig" heißt aus Namenskonvention oder Analogie geschlossen.
- **Kein Roh-Dump.** Ein Recherche-Agent, der ganze Dateien zitiert statt sie
  zu verdichten, hat die Aufgabe verfehlt — das Symptom, das Fan-out lösen
  sollte, kehrt sonst im Rückgabewert zurück.
- **Eine Datei, die zu drei Funden fünfzig Zeilen Beiwerk trägt, hat den
  Zweck verfehlt — selbst wenn jeder einzelne Satz darin richtig ist.** Der
  Sinn des Fan-outs ist ein schlanker Hauptkontext; Vorgehensberichte,
  Meta-Ebenen und Wiederholungen sind selbst Rohmaterial, nur eine Stufe
  näher an der Prosa.

### Beispiel (drei Funde)

Für eine Recherche über verstreute `TODO(security)`-Kommentare sieht eine
vollständige, korrekte Findings-Datei so aus — nichts wird ergänzt:

```markdown
## Findings

- `login()` validiert die Passwortstärke noch nicht.
  - Beleg: `src/auth/login.py:2`
  - Konfidenz: hoch

- `charge()` prüft die Betragssignatur nicht vor der Ausführung.
  - Beleg: `src/payments/charge.py:2`
  - Konfidenz: hoch

- Die Middleware begrenzt anonyme Requests nicht.
  - Beleg: `src/api/middleware.py:2`
  - Konfidenz: hoch
```

Das sind elf Zeilen für drei Funde. Jede zusätzliche Zeile in diesem Beispiel
wäre bereits eine Verletzung des Schemas oben.

## Als Artefakt festhalten

Wenn der Nutzer die Findings über die Antwort hinaus braucht (zum
Nachschlagen, für einen Folgeschritt, oder weil mehrere Recherche-Agenten
zusammengeführt werden), schreib **genau das Rückgabe-Schema oben und nichts
zusätzlich** als Datei nach `.skills/cache/tasks/research-<slug>.md`
(Ephemera, Spec 00 §1) statt es nur im Chat zu belassen — dann liest der
Hauptkontext beim Synthetisieren nur diese destillierte Datei, nie die
durchsuchten Rohdateien erneut. Die Kopfzeile aus `docs/artifact-header.md`
zählt nicht als "zusätzlich" (sie ist die einzige erlaubte Zeile vor
`## Findings`); jede andere Zeile vor der ersten Beobachtung ist ein
Vorgehensbericht und gehört nicht in die Datei. `<slug>` kommt aus der
Recherche-Frage; nennt der Nutzer einen konkreten Dateinamen, gilt der.

## Synthese-Disziplin

Die Synthese über mehrere Findings-Listen bleibt im Hauptkontext — dafür ist
er da. Ein Recherche-Agent synthetisiert nicht über andere Recherche-Agenten
hinweg (er sieht sie nicht); er liefert nur seinen eigenen Fund-Bericht.

## Dispatch

Kein Worktree nötig (Recherche-Agents schreiben nichts). Jeder Agent bekommt:
die Frage, den Suchraum (Verzeichnis/Dateimuster, nicht "die ganze Codebase"),
und das Rückgabe-Schema oben. Mehrere Recherche-Agents können parallel laufen,
weil sie sich per Definition nicht in Dateien überschneiden können — die
Überlappungsmatrix aus `plan_to_tasks.py` ist für diesen Fall nicht nötig.
