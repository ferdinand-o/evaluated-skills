# Spec 09: subagent\-dev — Plan\-getriebene Delegation mit Gate und Abnahme

Skill\-Spezifikation · Zyklus 9/14 · Entscheidung: Implementierung \+ Recherche, Pakete aus superpowers:writing\-plans, Abnahme via code\-review · Abgeglichen mit Spec 00

## Problem

Die Referenz\-Skill (superpowers/subagent\-driven\-development, 503 Zeilen) orchestriert auch dort, wo ein einzelner Agent schneller wäre, und lässt den kritischsten Punkt — Kontexttransfer — als textuelle Empfehlung stehen: Agents bekommen zu viel Kontext (halbe Historie) oder zu wenig (einen Satz), liefern ohne Abnahmekriterien zurück, und parallele Agents kollidieren in denselben Dateien. Token\-Kosten sind nirgends Entscheidungsgröße.

## Constraints

Zwei Delegations\-Fälle: parallele Implementierung disjunkter Pakete und Recherche\-/Analyse\-Fan\-out. Arbeitspakete stammen aus Plänen im **superpowers:writing\-plans\-Format** (`docs/superpowers/plans/…`), dessen `Files:`\- und `Interfaces:`\-Blöcke die Skill als maschinenlesbare Grundlage nutzt. Abnahme über die code\-review\-Skill (Spec 04). Worktree\-Isolation als Default bei parallelen Schreibzugriffen. Portables Frontmatter; Namenswahl vermeidet Kollision mit installiertem Superpowers (`subagent-dev`, mit Routing\-Hinweis in beiden Richtungen).

## Approach

**Delegation ist eine berechnete Entscheidung, kein Reflex — und jeder Agent bekommt eine Task\-Datei, nie die Historie.**

**Skill\-Struktur:**

```
subagent-dev/
├── SKILL.md                 (Gate-Regeln, Dispatch-Protokoll, Kostenmodell, Contract)
├── references/
│   ├── task-file.md         (Handoff-Schema + Beispiel)
│   ├── research-fanout.md   (Rückgabe-Schemata, Synthese-Disziplin)
│   └── merge-protocol.md    (Reihenfolge, Interface-Verifikation, Konfliktfall)
├── scripts/
│   └── plan_to_tasks.py     (Tier 1; Plan parsen → .skills/cache/tasks/ + Überlappungs-
│                             matrix + Gate-Urteil; G2)
└── evals/evals.json
```

**Das Gate (`plan_to_tasks.py` \+ Regeln):** Das Skript parst den Plan, extrahiert pro Task die `Files:`\-Liste und baut eine Datei\-Überlappungsmatrix. Delegations\-Urteil: **parallel** nur für Tasks mit leerem Schnitt (und ≥3 solcher Pakete, sonst lohnt der Overhead nicht); überlappende Tasks bleiben sequenziell beim selben Agent oder im Hauptkontext. Recherche\-Fan\-out qualifiziert sich unabhängig davon (Erkundung großer Codebasen/Fragen, deren Rohmaterial den Hauptkontext fluten würde). Das Urteil wird mit Begründung ausgegeben — auch das „Nein, nicht delegieren" ist ein Ergebnis. SKILL.md nennt Richtwerte der Token\-Kosten pro Muster (Agent\-Spawn, Review\-Pass), damit die Entscheidung ökonomisch nachvollziehbar ist.

**Task\-Dateien (der Kontexttransfer):** `plan_to_tasks.py` erzeugt pro Paket eine Handoff\-Datei nach `.skills/cache/tasks/` (Ephemera nach Spec 00 — aus dem Plan jederzeit neu erzeugbar, deshalb gitignored): Ziel des Tasks, **Datei\-Allowlist** (aus `Files:` — außerhalb wird nicht geschrieben), Interfaces (Consumes/Produces mit exakten Signaturen — so kennt der Agent seine Nachbarn, ohne sie zu sehen), Akzeptanzkriterien (aus den Plan\-Steps), Global Constraints des Plans wörtlich kopiert, Nicht\-Ziele. Der Agent erhält genau diese Datei plus Worktree — nicht die Konversationshistorie. Contract: Kein Dispatch ohne Task\-Datei; Schreiben außerhalb der Allowlist lässt die Abnahme scheitern — Durchsetzungsgrad **G2** (Spec 00 §4): Die Prüfung ist mechanisch und die Skill verweigert die Abnahme selbst; ein Hook hilft hier nicht, weil die Agents in eigenen Worktrees laufen.

**Dispatch & Isolation:** Parallel\-Pakete laufen je in einem eigenen Git\-Worktree. Recherche\-Agents erhalten stattdessen ein Rückgabe\-Schema (Findings \+ Belege/Pfade \+ Konfidenz) — destillierte Daten statt Prosa\-Aufsatz, Synthese bleibt im Hauptkontext.

**Abnahme (zweistufig):** (1) Mechanisch: Tests des Tasks grün, Allowlist eingehalten, Produces\-Signaturen vorhanden und typkonform. (2) code\-review\-Skill (Spec 04) im Selbst\-Modus über das Task\-Diff — die Spec\-Compliance\-Linse prüft gegen die Task\-Datei als Soll; bestätigte Findings fixt der Agent in seinem Worktree (max. 2 Runden, dann Eskalation an den Nutzer).

**Merge\-Protokoll:** Sequenziell in Abhängigkeitsreihenfolge des Plans; nach jedem Merge laufen die Tests des Gesamtstands; Interface\-Brüche zwischen Paketen sind per Definition ein Gate\-Fehler (Überlappung falsch beurteilt) und werden als Lesson im Plan vermerkt. Kein „alles auf einmal mergen und hoffen".

**Anti\-Rationalisierungs\-Tabelle (Auszug):** „Vier Agents wirken produktiver" → Überlappungsmatrix entscheidet, nicht das Gefühl. „Der Agent braucht mehr Kontext, ich gebe ihm die Historie" → dann ist die Task\-Datei unvollständig; Datei verbessern, nicht Kontext fluten. „Review pro Task ist zu teuer" → ein kollidierter Merge kostet mehr als alle Reviews zusammen. „Recherche mache ich schnell selbst" → wenn das Rohmaterial den Hauptkontext flutet, ist das Fan\-out billiger.

**Evals:** (1) Plan mit verdeckt überlappenden Tasks (gemeinsame Config\-Datei) — verweigert das Gate die Parallelisierung? (2) Mini\-Plan mit 2 Tasks — kommt „nicht delegieren" mit Begründung? (3) Agent liefert abweichende Produces\-Signatur — fängt es die mechanische Abnahme vor dem Review? (4) Recherche\-Fan\-out über eine große Codebase — kommen destillierte Schema\-Rückgaben statt Prosa\-Fluten, und bleibt der Hauptkontext schlank?

## Alternatives considered

Eigenständige Zerlegung beliebiger Aufträge (ohne Plan) verworfen: dupliziert writing\-plans und verliert dessen Files\-/Interfaces\-Präzision — wer keinen Plan hat, wird zur writing\-plans\-Skill geroutet. Leichte Inline\-Abnahme statt Review\-Engine verworfen (Nutzerentscheidung): unverifizierte Agent\-Ergebnisse sind das Kernrisiko; die gestufte Variante (Review nur für kritische Pakete) bleibt als dokumentierter Sparmodus erwähnt. Superpowers' 503\-Zeilen\-Prosa\-Ansatz als Ganzes: Die guten Ideen (Task\-Isolation, zweistufiges Review) sind übernommen und mechanisiert; der Rest ist bewusst gekürzt.

## Out of scope

Plan\-Erstellung selbst (superpowers:writing\-plans bleibt zuständig), Spec\-Erstellung (feature\-spec/Spec 03), CI\-Orchestrierung, verteilte Ausführung über mehrere Maschinen, automatisches Re\-Planning bei Gate\-Ablehnung (die Skill schlägt Umschnitt vor, entscheidet aber nicht allein).

## Open questions

Worktree\-Aufräum\-Politik bei Eskalation (behalten zur Diagnose vs. sofort löschen)? Kostenmodell: statische Richtwerte in SKILL.md oder gemessene Werte aus vergangenen Läufen loggen?

## Next steps

`plan_to_tasks.py` implementieren (Parser für writing\-plans\-Format, Überlappungsmatrix, Task\-Datei\-Generator) — es trägt Gate und Kontexttransfer; task\-file.md\-Schema festziehen; merge\-protocol.md schreiben; Eval 1 (verdeckte Überlappung) zuerst; Routing\-Sätze in beide Richtungen zu writing\-plans und code\-review ergänzen.
