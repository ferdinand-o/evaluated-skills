# Bericht: Skill `debug-ledger`

Branch `feat/debug-ledger`, Basis `0831fb7` (Spec 00 §-konform, `specs/skill-foundation`).
Plan: `docs/superpowers/plans/2026-08-16-debug-ledger.md`. Spec: `specs/Spec 01 – systematic-debugging.md`.

## Was gebaut wurde

```
skills/debug-ledger/
├── SKILL.md                          (114 Zeilen)
├── references/
│   ├── ledger-schema.md              (Feld-Definitionen + ausgefülltes Beispiel)
│   ├── tooling-python.md             (debugpy headless, pytest -x --pdb, faulthandler)
│   ├── tooling-node.md               (node --inspect-brk, Vitest-Debugging)
│   └── escalation.md                 (Mini→Voll-Signale, 3-Fehlversuche-Regel, MIT-Attribution)
├── assets/
│   ├── ledger-template.md            (Mini- + Voll-Schema-Vorlage, von new_ledger.py geladen)
│   └── hooks/check-ledger.json       (G3-Vorlage, nie automatisch installiert)
└── scripts/                          (alle Tier 1: Python-Stdlib)
    ├── new_ledger.py                 (anlegen / eskalieren / auflösen)
    ├── check_ledger.py               (Pflichtfeld- und Hypothesen-Contract, plus --staged für den Hook)
    └── bisect_run.py                 (kapselt git bisect run um ein Repro-Kommando)

evals/debug-ledger/evals.json         (4 Evals: 1 contract, 3 behavior)
evals/fixtures/{masking-fix,typo-bug,env-var-layers,archived-cause}/

tests/test_debug_ledger_new_ledger.py       (23 Tests)
tests/test_debug_ledger_check_ledger.py     (25 Tests)
tests/test_debug_ledger_bisect_run.py       (7 Tests)
tests/test_debug_ledger_dev_report_wiring.py (2 Tests, Cross-Skill-Verdrahtung)
```

Testlauf: **203 von 203 grün** (146 Baseline + 57 neue). Keine Regression.

### Ledger-Schema

Mini (immer, bei Anlage gefüllt): `## Symptom`, `## Repro-Kommando`,
`## Erwartung vs. Beobachtung`. Voll (durch `--escalate` angehängt, Platzhalter
`_(noch offen)_`): `## Evidenz-Log`, `## Hypothesen` (Tabelle), `## Root Cause`,
`## Fix`, `## Verifikation`, `## Prävention`. Jedes Ledger und `INDEX.md` selbst
tragen die Kopfzeile aus `docs/artifact-header.md`.

### Contract-Durchsetzung

`check_ledger.py` meldet einen Verstoß, wenn `## Fix` gefüllt ist, aber keine
Zeile der Hypothesen-Tabelle vollständig (alle vier Spalten, kein Platzhalter)
ausgefüllt ist. Verifiziert per Unit-Test und per End-to-End-Simulation gegen
den realen Hook-Befehl (siehe unten).

## R1–R3 aus dem Auftrag: Status

- **R1 (Verzeichnisname):** `skills/debug-ledger/`, `evals/debug-ledger/` — umgesetzt.
- **R2 (INDEX.md flach, Warnung ab 50):** `new_ledger.py --resolve` zählt Einträge
  nach jedem Append und warnt sichtbar ab 50, ohne umzugliedern oder zu prunen.
  Getestet (`test_action_resolve_warns_visibly_at_fifty_entries`,
  `test_action_resolve_no_warning_below_fifty`).
- **R3 (Hook nie automatisch installiert):** `assets/hooks/check-ledger.json`
  wird von keinem Skript referenziert oder ausgeführt. SKILL.md nennt
  `check_ledger.py` explizit als G2 ("meldet Verstoß"), G3 nur mit selbst
  eingerichtetem Hook. Geprüft: `grep -rn "blockier" skills/debug-ledger/`
  findet keine Fehlbenennung außerhalb des Hook-eigenen Textes.

## Zusätzliche Entscheidungen (nicht im Auftrag vorgegeben)

1. **`new_ledger.py` hat drei Aktionen über Flags, keine Subcommands**
   (`--symptom`/`--escalate`/`--resolve`), näher am Beispiel aus
   `docs/artifact-header.md` (`python scripts/new_ledger.py --symptom "…"`).
   Die tatsächliche Kopfzeile nutzt trotzdem den vollen Pfad
   `skills/debug-ledger/scripts/new_ledger.py` statt der verkürzten Form aus dem
   Beispiel — konsistent mit `dev-report`s Konvention
   (`python skills/dev-report/scripts/collect.py …`). Das Beispiel in
   `docs/artifact-header.md` ist damit als illustrativ behandelt, nicht als
   Pfadvorschrift; die Regel selbst ("so wie man es erneut eintippen würde")
   verlangt den vollen, funktionierenden Pfad.
2. **`docs/debugging/INDEX.md` trägt selbst die Artefakt-Kopfzeile.** Das ist
   keine neue Erfindung: `skills/dev-report/scripts/collect.py` erwartet das
   bereits exakt so (`HARVEST_SOURCES`, schema 1). Per Integrationstest verifiziert
   (`tests/test_debug_ledger_dev_report_wiring.py`) — `collect.harvest()` liest
   ein von `new_ledger.py` erzeugtes `INDEX.md` mit Status `"read"`, nicht
   `"no_header"`.
3. **`check_ledger.py --staged` statt einer vierten Skriptdatei für den Hook.**
   Die Struktur aus Spec 01 nennt genau drei Skripte; ein Hook, der bei
   `git commit` alle gestagten Ledger prüft, braucht aber eine Funktion, die
   nicht weiß, welche Ledger-Datei gemeint ist. Statt eines separaten
   `hook_check.py` bekam `check_ledger.py` einen `--staged`-Modus
   (`git diff --cached --name-only`, gefiltert auf `docs/debugging/*.md` ohne
   `INDEX.md`). Bleibt bei drei Skripten, ist eigenständig unit-getestet.
4. **Der Hook-Befehl in `assets/hooks/check-ledger.json` wurde funktional
   gegengeprüft**, nicht nur als JSON validiert: Ich habe den eingebetteten
   Python-Einzeiler extrahiert und mit einem simulierten `PreToolUse`-Stdin-Payload
   (`{"tool_input": {"command": "git commit -m x"}}`) gegen einen echten
   Workspace mit einem Contract-Verstoß laufen lassen — Exit 2, Verstoßmeldung
   auf stderr; bei `git commit` ohne Verstoß Exit 0; bei einem Nicht-`git
   commit`-Aufruf Exit 0 ohne zu prüfen. Was ich **nicht** verifizieren konnte:
   ob Claude Code den Tool-Aufruf tatsächlich als JSON auf stdin an
   `PreToolUse`-Hooks reicht (mein Verständnis der Konvention) — ich hatte
   keinen Zugriff auf eine echte Hook-Ausführung, um das gegenzuprüfen. Das ist
   ohnehin G3, also nutzergesteuert und pro Fall bewusst installiert; ein
   falsches Stdin-Format würde beim ersten `git commit` sichtbar auffallen
   (Exception, kein stiller Fehlschlag), nicht heimlich falsch entscheiden.
5. **`bisect_run.py` setzt `git bisect reset` immer im `finally`-Block**, auch
   bei Erfolg — sonst bliebe das Repo im detached HEAD des gefundenen Commits
   zurück. Per Test verifiziert (`test_run_bisect_leaves_repo_on_original_branch`).
6. **Platzhalter-Konvention `_(noch offen)_`** statt leerer Felder für den
   Voll-Schema-Zustand nach `--escalate` — macht "noch nicht bearbeitet" von
   "vergessen zu füllen" unterscheidbar und ist die Grundlage, auf der
   `check_ledger.py` prüft, ob eine Hypothesen-Zeile wirklich getestet wurde.

## Die vier Evals: Assertion-Design

Kernproblem, das die Eval-Architektur bestimmt hat: `new_ledger.py` leitet den
Dateinamen des Ledgers aus `--symptom` (vom Agenten frei formuliertem Text) und
dem realen Tagesdatum ab. Beides ist zur Eval-Autorenzeit unbekannt — anders als
bei `dev-report`, dessen Report-Pfad rein aus dem vom Nutzer im Prompt
genannten Git-Ref berechnet wird. `evalkit`s Assertion-Primitive
(`file_exists`, `file_matches`, `artifact_header`) verlangen aber einen exakten
Pfad; es gibt kein Glob-Primitiv. Deshalb:

- **`docs/debugging/INDEX.md`** ist der einzige deterministische Pfad (wird von
  `new_ledger.py` bei *jedem* Aufruf gebootstrapt) und trägt die mechanischen
  `must`-Assertions in allen vier Evals — der Beweis, dass das Skript wirklich
  lief, nicht nur geredet wurde.
- **Inhaltliche Checks** (Root-Cause-Text, Hypothesen-Tabelle, Multi-Layer-
  Instrumentierung, Archiv-Treffer) sind `judge`-Claims, die sich explizit auf
  "eine neue Ledger-Datei unter docs/debugging/" beziehen — der Judge sieht den
  vollen `dump_changed_files()`-Dump und braucht keinen Pfad. Das macht 3 der 4
  Evals zu `class: behavior`; dokumentiert als neue Grenze in
  `docs/known-limits.md` ("Kein Pfad-Primitiv für 'irgendeine Datei unter
  Verzeichnis X'").
- **Jede Assertion wurde gegen die Frage geprüft: "Könnte eine generische
  Debugging-Skill ohne Ledger-Artefakt das auch erfüllen?"** Alle Claims
  beziehen sich auf Struktur oder Inhalt der Ledger-Datei bzw. auf
  `docs/debugging/INDEX.md` mit seiner Kopfzeile — nichts prüft nur "wurde der
  Bug gefunden" als Chat-Aussage.
- **Eval 2 (Anti-Zeremonie, Tippfehler-Bug)** ist bewusst `class: contract`
  (billig, läuft im Routine-Gate) mit `must_not: output_matches` gegen
  Eskalations-Vokabular ("Hypothesen-Tabelle", "Root Cause", "--escalate" etc.)
  plus den beiden `INDEX.md`-Checks.

**Gegenproben durchgeführt** (mechanisch, ohne `run_evals.py` oder LLM-Aufruf):
Für alle vier Fixtures `evalkit.workspace.prepare()` real ausgeführt und
geprüft, dass es fehlerfrei durchläuft. Für Eval 2 zusätzlich `new_ledger.py`
im vorbereiteten Workspace real aufgerufen und die mechanischen `must`/`must_not`
sowohl gegen eine "gute" (bleibt mini) als auch eine "schlechte" (eskaliert
grundlos) simulierte Agent-Antwort geprüft — Ergebnis kippt korrekt. Für Eval 4
den `file_matches`-Regex gegen den echten Fixture-Inhalt getestet. Für Eval 1
und 3 die mechanischen `INDEX.md`-Checks nach realem Skript-Lauf verifiziert.
**Nicht verifiziert:** die `judge`-Claims selbst — das erfordert einen echten
LLM-Judge-Lauf, den ich laut Auftrag nicht starte (`run_evals.py` bleibt
unausgeführt). Schema-Validierung erfolgte über
`python3 -c "from evalkit.schema import load_evals; print(len(load_evals(...)))"`
→ 4 Evals, keine `EvalSchemaError`.

## Description-Schärfung gegen `superpowers:systematic-debugging`

Die Description benennt explizit den Unterschied (persistiertes, archiviertes,
mechanisch geprüftes Ledger-Artefakt unter `docs/debugging/` vs. reine
Prosa-Doktrin im Chatverlauf) statt um dieselben Trigger-Wörter zu konkurrieren,
und grenzt zusätzlich gegen `feature-spec` ab.

**Wie sicher ich mir bin, dass sie gewinnt: mittel, nicht verifiziert.** Ich
habe keinen Zugriff auf den tatsächlichen Trigger-/Routing-Mechanismus des
Eval-Agenten aus diesem Implementierungsschritt heraus — das würde einen echten
Claude-Lauf mit beiden Skills sichtbar brauchen, und genau den soll ich laut
Auftrag nicht selbst starten. Meine Einschätzung stützt sich nur auf die
Textqualität der Abgrenzung, nicht auf eine Beobachtung. Das gehört explizit in
die Bewertung durch den Koordinator, nicht in eine Erfolgsbehauptung von mir.

## Was ich nicht verifizieren konnte (Zusammenfassung)

1. Ob die vier `judge`-Claims bei einem echten LLM-Lauf tatsächlich so
   urteilen wie beabsichtigt (nur mechanisch/strukturell geprüft, s. o.).
2. Ob die Description tatsächlich gegen `superpowers:systematic-debugging`
   gewinnt (s. o.) — als offene, bewusst unsichere Einschätzung markiert.
3. Ob Claude Code `PreToolUse`-Hooks exakt im angenommenen JSON-auf-stdin-Format
   aufruft (G3, nutzerinstalliert, dokumentiert als Annahme).
4. Ob die im Prompt/Fixture-Design gewählten Symptom-Formulierungen in Eval 1/3/4
   tatsächlich zu einer für Phase 0 grep-baren Überschneidung mit `INDEX.md`
   führen (nur für Eval 4 direkt per Regex gegengeprüft, für 1 und 3 gibt es
   keine Archiv-Erwartung).

## Ergänzung in `docs/known-limits.md`

Neuer Punkt unter "Assertion-Vokabular": fehlendes Glob-Primitiv für Artefakte
mit freitext- und laufzeitabhängigen Dateinamen, mit `debug-ledger` als
konkretem Beispiel und der Konsequenz (3 von 4 Evals müssen `behavior` sein,
obwohl ihr Kerncheck mechanisch billig wäre). Commit `f618681`.
