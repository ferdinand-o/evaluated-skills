---
name: testing-strategy
description: Use when planning how to test a repository or a change before any test is written — classifying the repo type, choosing test layers with a reason, deciding what deliberately stays untested, and scoping even a single new test for code that already exists ("I added a function, need a test for it"). Triggers include "Testplan", "Teststrategie", "wie teste ich das", "welche Tests brauche ich", "Testpyramide", "ich hab eine Funktion ergänzt, brauche einen Test", questions about repo type for testing purposes. Not for the red-green-refactor loop of writing a failing test and then the code to pass it during active implementation (use test-first) and not for generating test stubs from Given/When/Then acceptance criteria (use feature-spec once built — testing-strategy implements the stubs feature-spec exports, it never generates them itself).
---

# testing-strategy — Kern plus Adapter

Eine Skill, nicht sechs. Die Varianz liegt in `references/`, nicht in
konkurrierenden Descriptions. `detect_stack.py` klassifiziert, eine harte
Tabelle bestimmt genau eine Adapter-Referenz zusätzlich zur querliegenden
`test-design.md`.

## Doktrin

Testen optimiert **Regressions-Fang pro Wartungskosten**, nicht
Coverage-Prozente — Coverage-Ziele sind bewusst verworfen, sie laden zum
Gaming ein. Der Repo-Typ bestimmt die Pyramide: Legacy bekommt erst ein
Sicherheitsnetz aus Characterization-Tests, *dann* Refactoring, nie umgekehrt.
APIs testen Contracts vor Implementierungsdetails. Extensions testen
Kontextgrenzen und Neustarts. **Was nicht getestet wird, ist eine
dokumentierte Entscheidung** — das Feld `Ausgelassen:` im Test-Plan, nicht ein
Versehen.

## Ablauf

1. **Immer zuerst klassifizieren**, auch wenn der Repo-Typ schon bekannt
   scheint:
   ```bash
   python skills/testing-strategy/scripts/detect_stack.py
   ```
   Schreibt `.skills/cache/detect_stack.json` neu — der Cache ist reine
   Ephemera und wird nie gelesen, nur überschrieben. Jeder explizite Aufruf
   klassifiziert neu, es gibt keine Veraltungsregel an Manifest- oder
   Lockfile-Änderungen.
2. **`ambiguous: true`** → nicht raten. Die Kandidaten aus `candidates`
   nennen und fragen, welcher zutrifft.
3. **`legacy.suspected: true`** → `references/legacy-monolith.md` laden,
   unabhängig vom erkannten Typ. Das Sicherheitsnetz kommt vor jedem
   Refactoring.
4. Sonst per Routing-Tabelle genau eine Typ-Referenz laden, zusätzlich zur
   immer geladenen `references/test-design.md`.
5. **Test-Plan-Block ausgeben**, bevor der erste Test geschrieben wird
   (Ausnahme: Anti-Zeremonie-Fall unten).
6. Tests schreiben, Layer für Layer, in der im Plan begründeten Reihenfolge.

## Routing-Tabelle

| `detect_stack.json` | Referenz | Bedingung |
| --- | --- | --- |
| `ambiguous: true` | keine — erst fragen | mehrere Kandidaten, gleiche Punktzahl |
| `legacy.suspected: true` | `references/legacy-monolith.md` | zuerst, egal welcher `primary` |
| `primary: "chrome-extension"` | `references/chrome-extension.md` | |
| `primary: "rest-api"` | `references/rest-api.md` | |
| `primary: "frontend-spa"` | `references/frontend-spa.md` | |
| `primary: "cli-library"` | `references/cli-library.md` | |
| `primary: null`, nicht ambiguous | keine — fragen, was geplant ist | keine Signale gefunden |
| immer zusätzlich | `references/test-design.md` | querliegend, jeder Fall |

Ein `languages[].runner: null` ist ein eigener Leerfall: vor dem Test-Plan
fragen, welcher Runner gilt, statt einen zu raten.

## Test-Plan-Block (Contract)

Vor dem ersten geschriebenen Test, wörtlich mit diesen vier Feldern:

```
## Test-Plan
- Repo-Typ: <aus detect_stack.json>
- Runner: <Name, oder "unbekannt — bitte angeben">
- Schichten: <je Schicht ein Satz Begründung>
- Ausgelassen: <bewusst nicht Getestetes mit Grund, oder "keine">
```

Ein Test-PR ohne diesen Block ist ein sichtbarer Regelverstoß; ein Block, der
der Klassifikation widerspricht (z. B. `Repo-Typ: rest-api` bei
`primary: "chrome-extension"`), ebenso. Ist `legacy.suspected: true`, beginnt
`Repo-Typ:` mit dem Wort **legacy** — mit `primary` in Klammern, falls
`detect_stack.json` zusätzlich einen Typ erkannt hat (`legacy (rest-api)`),
sonst ohne Zusatz (`legacy`). Legacy geht dem Typ immer voran, weil das
Sicherheitsnetz vor dem Typ-Adapter kommt. Bei jeder neuen oder geänderten
Message-Route in einer Chrome-Extension nennt `Schichten:` explizit
**SW-Termination** mit dem betroffenen Route-Namen — das ist das Kernrisiko
jeder MV3-Extension und darf nie stillschweigend fehlen.

## Die Playwright-Fixture ist ungeprüft

`references/chrome-extension.md` enthält eine vollständig ausgeschriebene
Playwright-Persistent-Context-Fixture und ein SW-Termination-Chaostest-Muster.
**Keines von beiden ist je gegen einen echten Browser gelaufen.** Schreib
nirgends — auch nicht sinngemäß, auch nicht in einer Randbemerkung — dass
diese Fixture „getestet", „erprobt", „verifiziert" oder „funktioniert" sei.
Jeder Verweis darauf trägt den Vorbehalt „ungeprüft, siehe
`docs/known-limits.md`". Das gilt unabhängig davon, ob der Test-Plan-Block
oder die Anti-Zeremonie-Ausnahme greift.

## Anti-Zeremonie-Ausnahme

Ein einzelner neuer Test in einem laut `detect_stack.json` bereits getesteten,
eindeutigen Repo (`tests_found: true`, `legacy.suspected: false`,
`ambiguous: false`) braucht **keinen** Test-Plan-Block. Drei Zeilen Fließtext
reichen: Zielort des Tests, Runner, ein Satz Begründung. Keine
`##`-Überschriften, keine Feldliste, keine Abwägung der Schichten — das wäre
die Zeremonie, die diese Regel verhindert. `detect_stack.py` läuft trotzdem,
auch hier: die Klassifikation entfällt nie, nur ihre ausführliche Darstellung.

## Promotion-Regel

Braucht ein Adapter eigene Skripte oder überschreitet er ~300 Zeilen, wird er
zur Geschwister-Skill befördert — mit Description-Routing in beide
Richtungen (diese SKILL.md verweist auf die neue Skill, die neue grenzt sich
hier ab). `references/chrome-extension.md` ist der erste Kandidat: Die
Playwright-Fixture allein ist bereits umfangreich genug, dass eine eigene
`scripts/`-Hilfe (z. B. zum Auslösen der SW-Termination) den Adapter über die
Schwelle heben würde.

## Tier

`detect_stack.py` ist Tier 1 (nur Stdlib, plus `git`-CLI wie bei
`dev-report/collect.py`) — eine Abweichung von der in Spec 05 vorgesehenen
Tier-2-Einstufung. Begründung im Skriptkopf: Manifest-Dateien sind JSON,
`pyproject.toml` muss nur nach Substrings durchsucht werden, keine echte
TOML-Semantik nötig. Ohne PyPI-Abhängigkeit gibt es hier keine
Degradationszeile ab Tier 2 zu deklarieren — nichts kann fehlen, das nicht
schon Teil der Python-Stdlib ist.

## Abgrenzung

- **test-first** — der Rot-Grün-Refactor-Zyklus *während* der
  Implementierung eines einzelnen, bereits geplanten Tests, mit Beleg im Log. Diese Skill plant
  *davor*: welche Schichten, welcher Repo-Typ, was bewusst ausgelassen wird.
- **feature-spec** *(geplant)* — erzeugt Test-Stubs aus Given/When/Then.
  `testing-strategy` implementiert diese Stubs aus, erzeugt sie nie selbst.
  Kommt ein Stub-Export von `feature-spec`, ist `detect_stack.py` trotzdem
  zuerst dran — die Stubs sagen nichts über Repo-Typ oder Schichten.
- setup-repo — übernimmt nur vorhandene Befehle als Verifikation; findet es keinen,
  verweist es hierher, um zu klären, welche Tests fehlen.
- Ohne jedes Manifest und ohne Git bleibt `detect_stack.py` trotzdem lauffähig
  (Tier 1) — es liefert dann nur `primary: null` und einen Legacy-Score ohne
  Historienkomponente, keinen Fehler.
