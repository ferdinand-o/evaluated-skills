# Recherche-/Analyse-Fan-out

Der zweite Delegations-Fall neben paralleler Implementierung: Erkundung einer
großen Codebase oder eine Frage, deren Rohmaterial (Dutzende Dateien, ein
langer Log, viele Suchtreffer) den Hauptkontext fluten würde, wenn du sie
selbst liest. Anders als bei Implementierungs-Tasks gibt es hier keinen
`Files:`-Block und keine Überlappungsmatrix — Recherche-Agents schreiben
nichts, sie liefern zurück.

**Qualifiziert sich unabhängig vom Gate.** `plan_to_tasks.py` prüft Files-
Überlappung; ein Recherche-Fan-out hat keine Files zum Überlappen. Die
Entscheidung "lohnt sich Fan-out" ist stattdessen: Würde das Rohmaterial (der
Dateiinhalt, die Grep-Treffer, das Diff) den Hauptkontext mit mehr fluten, als
das destillierte Ergebnis wiegt? Wenn ja, Fan-out.

## Rückgabe-Schema

Jeder Recherche-Agent liefert **destillierte Daten, nie einen Prosa-Aufsatz**:

```markdown
## Findings

- <eine Beobachtung, ein Satz>
  - Beleg: `pfad/zu/datei.py:42`
  - Konfidenz: hoch | mittel | niedrig

- <nächste Beobachtung>
  - Beleg: `pfad/zu/anderer/datei.py:10-25`
  - Konfidenz: mittel

## Offene Fragen

- <was die Recherche nicht klären konnte>
```

- **Beleg ist ein Pfad, keine Zusammenfassung.** Der Hauptkontext bekommt die
  Fundstelle, nicht den zitierten Absatz — wer nachlesen will, liest selbst.
- **Konfidenz ist Pflicht**, nicht Zierde: "hoch" heißt direkt im Code
  gesehen, "niedrig" heißt aus Namenskonvention oder Analogie geschlossen.
- **Kein Roh-Dump.** Ein Recherche-Agent, der ganze Dateien zitiert statt sie
  zu verdichten, hat die Aufgabe verfehlt — das Symptom, das Fan-out lösen
  sollte, kehrt sonst im Rückgabewert zurück.

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
