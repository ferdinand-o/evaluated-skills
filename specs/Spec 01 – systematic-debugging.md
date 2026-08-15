# Spec 01: debug\-ledger — systematic\-debugging v2, Ledger\-first

Skill\-Spezifikation · Zyklus 1/14 · Entscheidung: Option B \+ Bisect/Debugger\-Rezepte aus C · Abgeglichen mit Spec 00

## Problem

Die beste existierende Debugging\-Skill (obra/superpowers, 283 Zeilen) erzwingt Root\-Cause\-Analyse nur rhetorisch: Hypothesen, Experimente und Ergebnisse leben ausschließlich im Chatverlauf, sind nach der Session verloren und für niemanden prüfbar. Es gibt keine Werkzeug\-Integration (kein Debugger, kein automatisiertes `git bisect`), kein Gedächtnis über gelöste Bugs — Teams debuggen dieselben Bug\-Klassen wiederholt — und keine Evals, die belegen, dass die Skill unter Druck hält.

## Constraints

Primärstack Python (debugpy, pytest), Sekundärstack TypeScript/Node (Inspector, Vitest). Läuft in Claude Code; Frontmatter bleibt auf die sechs portablen Spec\-Felder beschränkt. Das Ledger wächst als Wissensbasis im Repo (`docs/debugging/`). Triage ist leichtgewichtig\-immer: Ein Mini\-Ledger ist ausnahmslos Pflicht, der volle Prozess wird durch definierte Signale ausgelöst — nie durch Selbsteinschätzung „ist trivial". Übernommene Superpowers\-Inhalte (Iron Law, Rationalisierungs\-Tabelle, 3\-Fehlversuche\-Regel) werden mit MIT\-Attribution adaptiert. Skill\-Name ist `debug-ledger`\: Die Kollision mit dem installierten `superpowers:systematic-debugging` ist real, und nach Spec 00 §5 wird bei echter Kollision umbenannt — Präzedenz löst zwar den Ladekonflikt, nicht aber die Konkurrenz zweier fast gleicher Descriptions ums Triggering.

## Approach

Das Artefakt ist der Prozess: Die Skill organisiert sich um das Schema von `debug-ledger.md`, nicht um Prosa\-Phasen. Leere Pflichtfelder sind der Enforcement\-Mechanismus — ein vorgeschlagener Fix bei leerer Hypothesen\-Tabelle ist ein mechanisch sichtbarer Regelverstoß.

**Skill\-Struktur:**

```
systematic-debugging/
├── SKILL.md              (< 150 Zeilen: Doktrin, Triage, Contract)
├── references/
│   ├── ledger-schema.md  (Feld-Definitionen + ausgefülltes Beispiel)
│   ├── tooling-python.md (debugpy headless, pytest -x --pdb, faulthandler)
│   ├── tooling-node.md   (node --inspect-brk, Vitest-Debugging)
│   └── escalation.md     (3-Fehlversuche → Architekturfrage, adaptiert)
├── assets/
│   ├── ledger-template.md
│   └── hooks/check-ledger.json  (optionales G3-Snippet, Spec 00 §4 — nie automatisch installiert)
├── scripts/                     (alle Tier 1: Python-Stdlib)
│   ├── bisect_run.py     (kapselt git bisect run um ein Repro-Kommando)
│   ├── new_ledger.py     (legt Ledger an, aktualisiert INDEX.md)
│   └── check_ledger.py   (prüft Pflichtfelder; G2 skill-invoked, G3 mit Hook)
└── evals/evals.json
```

**Workflow:** Phase 0 ist der Archiv\-Check — `docs/debugging/INDEX.md` (eine Zeile pro gelöstem Fall: Symptom → Ursache) wird nach Symptom\-Stichworten durchsucht; Treffer werden zuerst als Hypothese getestet. Dann entsteht via `new_ledger.py` immer das Mini\-Ledger mit drei Pflichtfeldern: Symptom, Repro\-Kommando, Erwartung vs. Beobachtung. Eskalationssignale schalten auf das volle Schema um: zweiter fehlgeschlagener Fixversuch, Multi\-Komponenten\-Verdacht, kein zuverlässiges Repro, oder der Nutzer meldet „immer noch kaputt". Das volle Schema ergänzt: Evidenz\-Log (Instrumentierungs\-Outputs, Bisect\-Ergebnis), Hypothesen\-Tabelle (Hypothese | Test | Ergebnis | Verdict), Root Cause, Fix, Verifikation (failing test vor Fix, grün danach), Prävention.

**Contract:** Kein Fix\-Vorschlag im vollen Modus ohne mindestens eine *getestete* Zeile in der Hypothesen\-Tabelle (`check_ledger.py` prüft das). Der Fix\-Commit referenziert die Ledger\-Datei. Nach Auflösung bleibt das Ledger im Archiv und `INDEX.md` erhält seine Symptom→Ursache\-Zeile — so verzinst sich jeder gelöste Bug in Phase 0 aller zukünftigen.

**Werkzeuge:** `bisect_run.py` nimmt ein Repro\-Kommando und eine bekannte gute Referenz und automatisiert die komplette Bisektion. Die Tooling\-Referenzen liefern je Stack ein kuratiertes Rezept (Breakpoint\-Session headless starten, Variablen inspizieren, Ergebnis ins Evidenz\-Log übernehmen) statt generischer „nutze einen Debugger"\-Ermahnung.

**Evals (adversarial):** (1) Bug, dessen naheliegender Symptom\-Fix einen zweiten Bug maskiert — fällt die Skill darauf herein? (2) Trivialer Tippfehler\-Bug — bleibt der Mini\-Pfad wirklich mini (Anti\-Zeremonie\-Messung)? (3) Multi\-Komponenten\-Bug (Env\-Variable geht zwischen Layer 2 und 3 verloren) — wird an Grenzen instrumentiert statt geraten? (4) Bug, dessen Ursache bereits im Archiv steht — findet Phase 0 ihn?

## Alternatives considered

„Superpowers\+\+" (Prosa\-Kern plus Anbauten) behält das Kernproblem fehlender Durchsetzung. Der volle instrumentierte Harness (Debug\-CLI, auto\-befülltes Ledger) liefert die beste Evidenz, kostet aber laufende Pflege pro Projekt — nachrüstbar, falls sich CI\-/Flaky\-Debugging als Hauptfall erweist. Der 30\-Zeilen\-Hack wirft Archiv und Tooling weg. Ein Debugging\-Subagent wurde verworfen: Der Verlust von akkumuliertem Kontext und Werkzeugzustand ist beim Debugging fatal.

## Out of scope

Flaky\-CI\-Test\-Harness (eigener Skill\-Kandidat), Performance\-Profiling (eigene Spur), das automatische Evidenz\-CLI aus Option C, Debugger\-Rezepte jenseits Python/Node.

## Open questions

Skaliert `INDEX.md` als flache Datei oder braucht es ab \~50 Fällen Themenordner — und hängt dieselbe Entscheidung nicht auch an der Aufbewahrung (Archiv unbegrenzt vs. Prune\-Regel)? Beides ist eine Wachstumsfrage und sollte einmal gemeinsam beantwortet werden; Spec 03 hat sie für `docs/decisions.md` in identischer Form offen.

## Next steps

Skill\-Gerüst scaffolden; Ledger\-Template und SKILL.md schreiben (Rationalisierungs\-Tabelle mit Attribution portieren); `new_ledger.py`, `check_ledger.py`, `bisect_run.py` implementieren; die vier Evals ausformulieren und mit Subagents unter Druckszenarien testen; Description gegen Fehltrigger schärfen (greift bei Bugs/Testfehlern, nicht bei Feature\-Arbeit).
