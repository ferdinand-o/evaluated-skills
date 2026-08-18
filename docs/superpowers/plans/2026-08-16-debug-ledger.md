# debug-ledger Implementation Plan

**Goal:** Eine Debugging-Skill, die sich um das Schema einer Ledger-Datei organisiert statt um
Prosa-Phasen — leere Pflichtfelder sind der Durchsetzungsmechanismus. Ich bin der alleinige
Implementierer (kein Subagent-Dispatch), dieser Plan ist die Grundlage für die Umsetzung in
derselben Session, nicht für eine Übergabe.

**Spec:** `specs/Spec 01 – systematic-debugging.md`, gebunden an `specs/Spec 00 – skill-foundation.md`.

**Entscheidungen aus dem Auftrag, unverhandelbar (R1–R3):**
- R1: Verzeichnis heißt `skills/debug-ledger/`, `evals/debug-ledger/` — nicht `systematic-debugging`.
- R2: `docs/debugging/INDEX.md` bleibt flach, Warnung sichtbar ab 50 Einträgen, nie geprunt.
- R3: `assets/hooks/check-ledger.json` wird nie automatisch installiert. `check_ledger.py` ist
  G2 (skill-invoked, freiwillig), G3 nur wenn der Nutzer den Hook selbst einrichtet.

## Architektur

Drei Tier-1-Skripte, ein Artefakt-Typ (`docs/debugging/<datum>-<slug>.md`), ein Archiv-Index
(`docs/debugging/INDEX.md`). `new_ledger.py` deckt drei Aktionen über Flags ab, keine
Subcommands — näher an der Kopfzeilen-Konvention aus `docs/artifact-header.md`
(`python scripts/new_ledger.py --symptom "…"` ist dort bereits als Beispiel gesetzt):

```
new_ledger.py --symptom S --repro R --expected E --observed O   # anlegen (Mini-Ledger)
new_ledger.py --escalate PFAD                                    # volles Schema anhängen
new_ledger.py --resolve PFAD --cause TEXT                        # INDEX.md-Zeile schreiben
```

`check_ledger.py PFAD` prüft Pflichtfelder mechanisch (G2, Exit-Code 1 bei Verstoß).
`bisect_run.py --good REF --bad REF --command CMD` kapselt `git bisect run`.

### Ledger-Schema

Mini (immer, bei Anlage gefüllt): `## Symptom`, `## Repro-Kommando`,
`## Erwartung vs. Beobachtung`.

Voll (durch `--escalate` angehängt, startet mit Platzhalter `_(noch offen)_`):
`## Evidenz-Log`, `## Hypothesen` (Tabelle Hypothese|Test|Ergebnis|Verdict),
`## Root Cause`, `## Fix`, `## Verifikation`, `## Prävention`.

Kopfzeile jedes Ledgers: `<!-- skill: debug-ledger | schema: 1 | generated: python
skills/debug-ledger/scripts/new_ledger.py --symptom "…" -->` — volle Pfadangabe wie bei
`dev-report/scripts/collect.py`, nicht die verkürzte Form aus dem Beispiel in
`docs/artifact-header.md` (das Beispiel ist illustrativ, nicht die exakte Pfadvorschrift;
`docs/artifact-header.md` §"Die drei Felder" verlangt nur, dass der Befehl re-eintippbar ist).

`docs/debugging/INDEX.md` trägt dieselbe Kopfzeile (schema 1) — `dev-report/scripts/collect.py`
erwartet das bereits exakt so (`HARVEST_SOURCES`), also ist das keine neue Erfindung, sondern
Erfüllung eines bestehenden Konsumenten-Contracts.

### Contract-Durchsetzung in check_ledger.py

Mini-Felder müssen immer nicht-leer sein (nicht `_(noch offen)_`, nicht Whitespace).
Im vollen Modus (erkannt an `## Hypothesen`): Ist `## Fix` gefüllt und keine Zeile der
Hypothesen-Tabelle "getestet" (alle vier Zellen gefüllt, keine Platzhalter) → Verstoß.
Exit 0 clean, 1 Verstoß gefunden, 2 Datei fehlt/unlesbar.

### Leerfälle, die die Skill explizit behandelt

- `docs/debugging/INDEX.md` fehlt bei Phase 0 → kein Fehler, einfach kein Archiv-Treffer;
  bei `--resolve` wird es dann neu angelegt (Bootstrap-Meldung).
- `docs/debugging/` fehlt komplett beim ersten `new_ledger.py`-Lauf → Bootstrap-Regel greift,
  Anlage wird angekündigt und der Pfad genannt (Spec 00 §1).
- Kein Git-Repo bei `bisect_run.py` → sichtbare Meldung "kein Git-Repository", Exit 2, kein
  stiller Fehlschlag.
- `--escalate` auf ein bereits volles Ledger → idempotent, meldet das, ändert nichts.
- `--resolve` auf ein Ledger, das schon eine INDEX-Zeile hat → idempotent, keine Dopplung.
- INDEX.md wird nach `--resolve` ≥ 50 Einträge groß → sichtbare Warnung, keine automatische
  Restrukturierung (R2).

## Was gebaut wird (Dateien)

```
skills/debug-ledger/SKILL.md
skills/debug-ledger/references/{ledger-schema,tooling-python,tooling-node,escalation}.md
skills/debug-ledger/assets/ledger-template.md
skills/debug-ledger/assets/hooks/check-ledger.json
skills/debug-ledger/scripts/{new_ledger,check_ledger,bisect_run}.py
tests/test_debug_ledger_new_ledger.py
tests/test_debug_ledger_check_ledger.py
tests/test_debug_ledger_bisect_run.py
evals/debug-ledger/evals.json
evals/fixtures/masking-fix/          (Eval 1: Symptom-Fix maskiert zweiten Bug)
evals/fixtures/typo-bug/             (Eval 2: Anti-Zeremonie, trivialer Tippfehler)
evals/fixtures/env-var-layers/       (Eval 3: Multi-Komponenten, Env-Var geht verloren)
evals/fixtures/archived-cause/       (Eval 4: Ursache steht schon im INDEX.md)
docs/superpowers/reports/debug-ledger-report.md
```

## Reihenfolge

1. Tests + Implementierung `new_ledger.py` (create/escalate/resolve), inkl. Bootstrap- und
   Idempotenz-Fälle.
2. Tests + Implementierung `check_ledger.py` (Pflichtfeld- und Hypothesen-Contract).
3. Tests + Implementierung `bisect_run.py` (inkl. Kein-Git-Fall, `git bisect reset` in
   `finally`).
4. `assets/ledger-template.md`, `assets/hooks/check-ledger.json`.
5. `references/*.md` — Schema-Referenz mit ausgefülltem Beispiel, Python-/Node-Tooling,
   Eskalations-Doktrin (Iron Law, Rationalisierungstabelle, 3-Fehlversuche-Regel) mit
   MIT-Attribution auf `obra/superpowers`.
6. `SKILL.md` (< 150 Zeilen), Description scharf gegen `superpowers:systematic-debugging` und
   `feature-spec` abgegrenzt.
7. Vier Evals + Fixtures — jede Assertion daraufhin geprüft, ob `debug` (global installiert)
   sie auch erfüllen könnte; wenn ja, verworfen oder auf Ledger-spezifische Beobachtung
   umgehängt (Kopfzeile, Pflichtfelder, INDEX.md-Zeile, `check_ledger.py`-Ausgabe).
8. Schema-Validierung (`load_evals`), vollständiger Testlauf, Bericht schreiben, Commits.

## Bekanntes Risiko, das in den Bericht gehört

Die Description-Schärfung gegen `superpowers:systematic-debugging` ist nicht mechanisch
verifizierbar (kein Zugriff auf den echten Trigger-Mechanismus des Eval-Agenten aus diesem
Plan-Schritt heraus) — wird im Bericht als Unsicherheit benannt, nicht als erledigt behauptet.
