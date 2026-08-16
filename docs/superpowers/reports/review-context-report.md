# Abschlussbericht: Skill `review-context`

Branch: `feat/review-context` · Basis: `0831fb7` (specs/skill-foundation)

## Was gebaut wurde

Der Kontextpaket-Zulieferer aus Spec 04, Zuschnitt (a) — **nicht** die Linsen-Engine. Gebaut:

```
skills/review-context/
├── SKILL.md                        (80 Zeilen, ≤150 eingehalten)
├── references/context-packets.md   (Feldreferenz je Linse, GWT-Format, Ränder-Tabelle)
└── scripts/collect_context.py      (Tier 1, nur Stdlib: ast, re, subprocess, json, argparse)
evals/review-context/evals.json     (4 Evals, alle class: "contract")
evals/fixtures/review-context-{no-soll,with-spec,mini-diff,caller}/
tests/test_review_context_collect.py  (85 Tests)
docs/known-limits.md                (Abschnitt „review-context" ergänzt)
docs/superpowers/plans/2026-08-15-review-context.md
```

`collect_context.py` baut aus einem Git-Diff (Range `BASIS..ZIEL` oder Arbeitsverzeichnis gegen
HEAD) drei gewichtete Kontextpakete — Spec-Compliance (viel Soll), Korrektheit (viel Ist,
Symbole + Aufrufer-Signaturen), Vereinfachung (Projekt-Konventionen) — und schreibt sie nach
`.skills/cache/review-context.json`. Es startet keinen Subagent, keine Linsen-Prompts, keinen
Widerlegungs-Pass und keinen Renderer; das komplette Review überlässt SKILL.md ausdrücklich
`/code-review`.

Alle 85 neuen Tests plus die 146 bestehenden sind grün (207 gesamt). `evalkit.schema.load_evals`
lädt die vier Evals ohne Fehler.

## Entscheidungen, die ich zusätzlich treffen musste

Spec 04 und der Auftrag (R12–R16) legen den Zuschnitt fest, aber nicht jedes Detail von
`collect_context.py`. Die wichtigsten eigenen Entscheidungen, alle in
`docs/superpowers/plans/2026-08-15-review-context.md` und `docs/known-limits.md` dokumentiert:

1. **Diff-Auswahl:** `--range BASIS..ZIEL` (Zwei-Punkt) oder ohne Flag = Arbeitsverzeichnis
   gegen HEAD (Uncommitted). Drei-Punkt-Syntax (`...`, Merge-Base) wird explizit abgelehnt —
   zusätzliche Komplexität ohne Tier-1-Nutzen.
2. **Commit-Messages zählen erst ab zwei Commits im Range als Soll.** Weder Spec 04 noch der
   Auftrag nennen eine Mindestanzahl. Ohne diese Regel wäre der wichtigste Eval („Diff ohne
   jedes Soll") nicht deterministisch konstruierbar, weil ein Single-Commit-Range sonst immer
   dessen eigene Subject-Zeile als Soll zählen würde — eine Tautologie (die Message beschreibt
   den Diff, nicht das Ziel dahinter). Das ist eine begründete, aber widersprechbare Annahme;
   in `docs/known-limits.md` markiert, samt Anleitung, wie man sie umkehrt.
3. **PR-Beschreibung kommt nur über `--pr-description`/`--pr-description-file` herein.** Ein
   lokales Tier-1-Skript kann keine GitHub-API abfragen; der Aufrufer (Agent oder Mensch, der
   z. B. `gh pr view` gelesen hat) reicht den Text explizit rein.
4. **Eine Feature-Spec ohne geparste Given/When/Then zählt trotzdem als Soll**, mit einem
   Rohtext-Excerpt statt strukturierter Kriterien. R13 verlangt „gar nichts gefunden" als
   Auslöser für den Befund, nicht „nicht ideal formatiert".
5. **`docs/decisions.md` folgt derselben Konsumenten-Regel wie `dev-report`s Harvest** (Header
   nach `docs/artifact-header.md`, sonst sichtbar übersprungen) — eigene Wahl, weil weder Spec 04
   noch der Auftrag ein Format für diese Datei festlegen, aber Spec 00 „jedes Artefakt trägt die
   Kopfzeile" für alle Konsumenten verlangt.
6. **Aufrufer-Suche ist grep-basiert für beide Sprachen** (`\bname\s*\(`, gedeckelt auf 20 mit
   benannter Grenze). R16 erlaubt das explizit für TypeScript; ich habe es aus Konsistenzgründen
   auf die Python-Aufrufer-*Fundstellen* ausgedehnt — nur die Python-*Signaturen* selbst (sowohl
   des berührten Symbols als auch der umschließenden Aufrufer-Funktion) kommen aus `ast`.
7. **Symbol-/Aufrufer-Erkennung entfällt für gelöschte Dateien** — kein „Nachher"-Zustand, aus
   dem sich Symbolgrenzen ableiten ließen. Als Rand benannt, nicht stillschweigend übersprungen.
8. **R15 (keine `docs/reviews/findings.md`) wurde wörtlich umgesetzt** — es gibt keine
   Wissensdatei, die Befunde archiviert. `collect_context.py` erzeugt nur Ephemera
   (`.skills/cache/`), nichts unter `docs/`.

## Was ich nicht verifizieren konnte

- **Der Uncommitted-Modus (kein `--range`) läuft nur gegen Unit-Tests, nicht gegen einen echten
  Agenten-Lauf.** `evalkit.workspace.prepare()` hinterlässt nach dem Fixture-Aufbau immer einen
  sauberen Baum (dieselbe Grenze wie `dirty-worktree`, s. `docs/known-limits.md`), ein Eval kann
  diesen Pfad also nicht auslösen. Alle vier Evals nutzen `--range HEAD~1..HEAD`.
- **TS/JS-Symbolerkennung ist nur unit-getestet**, keiner der vier Evals nutzt eine TS-Fixture.
  Die dokumentierte Asymmetrie zu Python (nur Deklarationszeile, kein Body-Tracking) ist damit
  mechanisch abgesichert, aber nicht gegen einen realistischeren TS-Diff eval-geprüft.
- **Die Aufrufer-Deckelung bei > 20 Treffern** ist nur unit-getestet
  (`test_find_callers_caps_with_named_limit`), nicht eval-getestet — der Auftrag begrenzte die
  Eval-Zahl auf vier, und die anderen drei Ränder wogen dafür schwerer.
- **`docs/decisions.md` wurde nie gegen eine reale Instanz gelesen**, weil die erzeugende Skill
  (feature-spec, Spec 03) noch nicht gebaut ist. `read_decisions()` ist nur gegen synthetischen
  Testinhalt geprüft.
- **Ob `run_evals.py` die vier Evals tatsächlich grün bewertet**, habe ich nicht geprüft —
  weisungsgemäß nicht ausgeführt. Ich habe stattdessen `collect_context.py` manuell gegen alle
  vier per `evalkit.workspace.prepare()` gebauten Fixture-Workspaces laufen lassen und jede
  `must`/`must_not`-Assertion am realen JSON-Output verifiziert (nicht nur am Design).
- **Alles oben Genannte steht bereits in `docs/known-limits.md`** unter dem neuen Abschnitt
  „review-context" — nichts davon ist zusätzlich offen geblieben.

## Zur Description: Trigger-Sicherheit gegenüber `/code-review`

Einschätzung: **mittelhoch bis hoch sicher**, dass „review mal meinen Diff" nicht bei
`review-context` landet. Die Description beginnt mit „Use **before** a code review runs" und
sagt explizit „Does NOT perform the review itself — for that use `/code-review`", mit genau den
zwei Formulierungen als Gegenbeispiel, die ein Nutzer für ein echtes Review sagen würde („review
mal meinen Diff", „schau dir den PR an"). Die genannten Trigger-Phrasen für `review-context`
selbst („bereite den Review-Kontext vor", „sammle den Kontext für den PR") sind vorbereitende
Formulierungen, keine Review-Aufforderungen. Restrisiko: Ein Nutzer, der informell „bereite
meinen Review vor" statt „bereite den Review-*Kontext* vor" sagt, könnte mehrdeutig sein — dieses
Risiko lässt sich nur durch echte Trigger-Evals (nicht Teil des Vier-Eval-Kontingents hier)
empirisch prüfen, nicht durch Text-Analyse allein.

## Bekannte, bewusst nicht gebaute Teile (R15)

Keine Wissensdatei `docs/reviews/findings.md`. Wiederkehrende Fehler zu sammeln gehört der
Review-Engine (`/code-review`), die diese Skill nicht baut — ein Zulieferer, der Befunde
archiviert, die er selbst nie erzeugt, hätte eine Zuständigkeit ohne Grundlage.
