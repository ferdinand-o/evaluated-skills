# `learner.md`: Aufbau, Beherrschungsgrad, Beispiel

Eine Datei, kein Themenbaum (A5) — flach bleiben, bis es weh tut. Der Lernende
besitzt die Datei: lesbar, editierbar, wandert mit ins Repo/Notizsystem.

## Ort

`.skills/learning-coach/learner.md`, projektlokal, sobald `.skills/learning-coach/`
im Projekt existiert — sonst `~/.skills/learning-coach/learner.md`
(`due_topics.py::resolve_base_dir()` implementiert diese Auflösung, dasselbe Muster
wie `verified-research/scripts/registry.py`). Erster Lauf kündigt die Anlage an
(Pfad nennen), aus dem Template unter `assets/learner-template.md`.

## Kopfzeile

Erste nicht-leere Zeile, nach der allgemeinen Artefakt-Konvention
(`docs/artifact-header.md`):

```
<!-- skill: learning-coach | schema: 1 | generated: python skills/learning-coach/scripts/due_topics.py --repo . due -->
```

## Aufbau

```
<!-- skill: learning-coach | schema: 1 | generated: ... -->

# Lernstand

## <slug>: <Anzeigename>

- Gebiet: tech | theorie
- Beherrschungsgrad: 0-4
- Letzte Abfrage: <YYYY-MM-DD>
- Nächste Fälligkeit: <YYYY-MM-DD>
- Typische Fehler:
  - <wörtlich, aus einer Fehleranalyse>
- Offene Fragen:
  - <was die letzte Session nicht klären konnte>
```

`<slug>` ist ein kurzer, sprechender Bezeichner (Kleinbuchstaben, Bindestriche) —
**derselbe Slug, unter dem exercise-forge das Aufgaben-JSON ablegt**
(`<slug>.exercises.json`, siehe unten). Ein Thema ohne austauschbaren Slug kann
`due_topics.py` keine Aufgaben zuordnen.

Felder dürfen leer bleiben (`- Letzte Abfrage:` ohne Wert) — das ist der Normalfall
für ein neues Thema, kein Fehler. Ein fehlendes oder unlesbares Datum bei
„Nächste Fälligkeit" macht das Thema fällig, nie unfällig (E4) — im Zweifel wird
erinnert, nicht vergessen.

## Beherrschungsgrad, operationalisiert (0-4)

| Grad | Bedeutung |
| --- | --- |
| 0 | nie gesehen |
| 1 | erkennt/wiedererkennt (Rezeption), kann es aber nicht selbst anwenden |
| 2 | wendet es mit Hinweis oder Vorlage an |
| 3 | wendet es selbstständig im bekannten Kontext an |
| 4 | erklärt es fehlerfrei und wendet es im Transfer an (neuer, unbekannter Kontext) |

Jeder Abruf ist entweder `success` (Grad steigt um eine Stufe, gedeckelt bei 4) oder
`failure` (Grad sinkt sofort um eine Stufe, gedeckelt bei 0 — kein Toleranz-Zähler,
das entspricht E4 und ist einfacher als ein Fehlversuchs-Zähler, den diese Datei
nicht separat führt). Das nächste Intervall danach liefert
`due_topics.py interval --grade <alt> --result success|failure`
(Formel und Begründung: `references/methods.md`).

## „Typische Fehler" ist die wertvollste Zeile

Wörtlich festhalten, was der Lernende falsch gesagt/gedacht hat — nicht
„Verständnisproblem", sondern der konkrete Denkfehler
(„Verwechselt Closure mit Callback", nicht „Closures nicht verstanden"). Nur ein
wörtlich festgehaltener Fehler lässt sich beim nächsten Abruf gezielt erneut prüfen.

## Beispiel

```
<!-- skill: learning-coach | schema: 1 | generated: python skills/learning-coach/scripts/due_topics.py --repo . due -->

# Lernstand

## closures: JavaScript – Closures

- Gebiet: tech
- Beherrschungsgrad: 2
- Letzte Abfrage: 2026-08-10
- Nächste Fälligkeit: 2026-08-17
- Typische Fehler:
  - Verwechselt Closure mit Callback
  - Vergisst, dass die Variable per Referenz erfasst wird, nicht per Wert kopiert
- Offene Fragen:
  - Wie verhält sich das bei `let` vs. `var` in Schleifen?

## netzwerksicherheit-grundlagen: Netzwerksicherheit – Grundlagen

- Gebiet: theorie
- Beherrschungsgrad: 3
- Letzte Abfrage: 2026-08-05
- Nächste Fälligkeit: 2026-08-12
- Typische Fehler:
  - Verwechselt Authentifizierung mit Autorisierung
- Offene Fragen:
```

## Schnittstelle zu exercise-forge (Spec 13)

Aufgaben-JSONs liegen **nicht** unter `learning-coach/`, sondern neben der
Wissensdatei aus Spec 12: `~/.skills/verified-research/research/<slug>.exercises.json`
(projektlokal nach demselben Muster). `due_topics.py::exercises_status()` prüft
Existenz und **grobe Struktur** dieser Datei, nie den Inhalt der einzelnen Aufgaben
— sie enthält nach Spec 13 pro Aufgabe mindestens Typ, Lernziel, Schwierigkeit und
ein Verifikations-Protokoll, aber die genauen Feldnamen legt exercise-forge fest
(wird parallel zu dieser Skill gebaut) und werden hier nicht angenommen. Die
Top-Level-Form ist ein JSON-**Objekt** mit dem Schlüssel `"exercises"`, dessen Wert
eine Liste von Aufgaben-Objekten ist — verifiziert gegen den echten Erzeuger
(`exercise-forge`s `export.py`: `data.get("exercises", [])`), nicht bloß aus dem
Spec-13-Text abgeleitet. Eine frühere Fix-Runde hatte fälschlich ein reines
Top-Level-*Array* angenommen; das ist jetzt korrigiert.

Vier Zustände, drei davon ergeben dieselbe Meldung:

| Zustand | Bedeutung | Meldung |
| --- | --- | --- |
| fehlt | Datei existiert nicht | „Keine verifizierten Aufgaben gefunden" |
| leer | `"exercises"` ist eine leere Liste | „Keine verifizierten Aufgaben gefunden" |
| strukturell unerwartet | kein gültiges JSON, kein Objekt, oder `"exercises"` fehlt/ist keine Liste | „Keine verifizierten Aufgaben gefunden" |
| gefunden | `"exercises"` ist eine nicht-leere Liste | Pfad wird genannt, Inhalt ungeprüft |

Alle drei Nicht-Erfolgsfälle sind aus Nutzersicht gleich (kein verwertbarer
Aufgabenbestand) und deshalb bewusst nicht unterschieden — nur der Detailtext im
Skript-Output unterscheidet sie für die Fehlersuche. Das ist normal, kein Fehler —
SKILL.md schlägt dann vor, exercise-forge aufzurufen.
