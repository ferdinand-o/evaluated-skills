# Spec 04: code\-review — Linsen\-Engine mit adversarialer Verifikation

Skill\-Spezifikation · Zyklus 4/14 · Entscheidung: Option B \+ zwei Renderer \+ Fix\-Schleife \+ Kontext\-Pakete · **Zuschnitt offen (Spec 00 §5)**

## Status

Spec 00 hält fest, dass Claude Code `/code-review` bereits mit dieser Pipeline ausliefert — Linsen parallel, adversariale Verifikation pro Finding, Verdicts confirmed/plausible, `--fix` als Selbst\-Modus und `--comment` als Fremd\-Modus. Additiv bleibt allein **Schritt 2**\: `collect_context.py`, das Ist\-/Soll\-Kontextpakete aus `docs/decisions.md` und der Feature\-Spec baut — Kontext, den ein generischer Reviewer nicht hat, weil ihm die Artefakte der Geschwister\-Skills fehlen. Der Rest dieser Spec beschreibt damit weitgehend Vorhandenes.

Zwei Wege, Entscheidung steht aus: **(a)** Spec schrumpft auf den Kontextpaket\-Zulieferer, der `/code-review` vorgelagert läuft; **(b)** die eigene Linsen\-Engine wird trotzdem gebaut, dann aber mit begründetem Delta gegenüber `/code-review` in Problem und Alternatives. Bis dahin bleibt der folgende Text unverändert stehen.

## Problem

LLM\-Reviews haben zwei systematische Fehler: Sie melden plausible, aber falsche Findings ungeprüft, und sie duplizieren Linter\-Arbeit, statt zu finden, was Maschinen nicht finden. Dazu kontaminieren sich Blickwinkel gegenseitig (wer Bugs sucht, prüft Spec\-Treue schlampiger), Findings kommen ohne konkretes Failure\-Szenario, und ein Diff ohne Ist\-/Soll\-Kontext lässt den Reviewer raten, was die Änderung eigentlich erreichen sollte.

## Constraints

Zwei gleichwertige Anlässe: Selbst\-Review von Claudes eigenen Änderungen und Review fremder Diffs/PRs. Drei Linsen: Spec\-Compliance, Korrektheit/Bugs, Vereinfachung — **keine Security\-Linse**; die Description routet Security\-Anliegen explizit zu spezialisierten Skills (trailofbits/skills). Ein Widerlegungs\-Pass pro Finding (kein Mehrfach\-Voting). Stacks primär Python und TypeScript (Linter\-Gate: ruff/mypy bzw. eslint/tsc). Subagent\-Nutzung mit dokumentiertem Sparmodus. Portables Frontmatter.

## Approach

**Ein Engine, zwei Renderer.** Selbst\- und Fremd\-Review unterscheiden sich nicht im Finden, nur im Ausgang: Der Selbst\-Modus endet in angewandten Fixes, der Fremd\-Modus in Review\-Kommentaren. Die Skill pflegt daher eine Pipeline und zwei Ausgabe\-Adapter — nicht zwei Tonlagen durch den ganzen Prozess.

**Pipeline:**

1. **Gate (Skript):** `gate.py` führt Linter/Typechecker aus. Deren Funde werden gemeldet, aber aus dem LLM\-Review *ausgeschlossen* — Claude sucht nur, was Maschinen nicht sehen. Diffs unter \~50 geänderten Zeilen überspringen die Subagent\-Stufe (Schwelle in SKILL.md dokumentiert) und laufen sequenziell im Hauptkontext.
2. **Kontext\-Pakete (Skript):** `collect_context.py` baut deterministisch je Linse ein Paket aus Diff plus gezieltem Ist\- und Soll\-Zustand. **Soll:** die Feature\-Spec, sofern vorhanden (Given/When/Then aus Spec 03 ist das ideale Format), sonst Commit\-Message/PR\-Beschreibung — fehlt beides, wird das als eigenes Finding gemeldet („Änderung ohne benanntes Soll ist nicht reviewbar"). **Ist:** Vorher\-Stand der berührten Dateien, Signaturen aufgerufener und aufrufender Symbole (grep/AST), relevante `docs/decisions.md`\-Einträge. Gewichtung je Linse: Spec\-Compliance bekommt viel Soll; Korrektheit viel Ist (Umgebungscode, Aufrufer); Vereinfachung die Projekt\-Konventionen.
3. **Drei Linsen\-Subagents parallel:** Jeder erhält nur sein Paket und liefert Findings im festen Schema: Datei/Zeile, Behauptung, **Failure\-Szenario** („bei Input X passiert Y") — ein Finding ohne konkretes Szenario ist ungültig und wird verworfen.
4. **Widerlegungs\-Pass:** Pro Finding ein Subagent mit explizitem Auftrag, es zu widerlegen (Default bei Unsicherheit: widerlegt). Verdicts: confirmed / plausible; nur diese beiden erreichen den Nutzer, klar getrennt.
5. **Renderer:** *Selbst\-Modus:* bestätigte Findings werden gefixt, das Delta re\-reviewt (nur betroffene Linse), Schleife bis nichts Bestätigtes übrig ist; Abbruch nach 3 Runden mit Eskalation an den Nutzer. *Fremd\-Modus:* Kommentare je Finding mit Verdict, Szenario und konkretem Vorschlag (GitHub\-Suggestion\-Format wo möglich), respektvoller Ton laut Referenz.

**Skill\-Struktur:** `SKILL.md` (Pipeline, Schwellen, Contract), `references/` (lenses.md mit den drei Linsen\-Prompts, context\-packets.md, tone\-foreign.md), `scripts/` (gate.py, collect\_context.py), `evals/evals.json`.

**Contract:** Kein Finding ohne Failure\-Szenario; kein Finding, das ein Linter hätte finden können; jedes gemeldete Finding trägt ein Verdict; im Selbst\-Modus endet das Review erst mit leerer Confirmed\-Liste oder expliziter Nutzer\-Entscheidung.

**Anti\-Rationalisierungs\-Tabelle (Auszug):** „Sieht verdächtig aus, melde ich mal" → ohne Szenario kein Finding. „Der Linter hat's übersehen" → dann Gate\-Konfiguration fixen, nicht das Review aufblähen. „Widerlegung kostet zu viel" → ein falsches Finding kostet mehr Vertrauen als drei Widerlegungs\-Pässe Tokens.

**Evals:** (1) Diff mit einem subtilen echten Bug und drei plausiblen Nicht\-Bugs — überlebt genau der echte? (2) Änderung, die die Spec verfehlt, aber sauber implementiert ist — schlägt die Spec\-Linse an, obwohl der Code „gut aussieht"? (3) Diff ohne jede Soll\-Beschreibung — kommt das Meta\-Finding statt eines Rate\-Reviews? (4) 20\-Zeilen\-Mini\-Diff — bleibt die Pipeline im dokumentierten Sparmodus?

## Alternatives considered

Sequenzieller Ein\-Kontext\-Prüfstand (Option A) verliert die Unabhängigkeit der Linsen und bleibt als dokumentierter Sparmodus für kleine Diffs erhalten. Mehrfach\-Voting pro Finding wäre präziser, wurde aus Kostengründen auf einen Widerlegungs\-Pass reduziert — nachrüstbar für kritische Pfade. Eine Security\-Linse verworfen zugunsten von Routing zu Trail of Bits. Checklisten\-Review ohne Subagents scheitert am Kernproblem unverifizierter Findings.

## Out of scope

Security\-Audits (Routing zu trailofbits/skills), Architektur\-Bewertung ganzer Codebasen (eigene Skill, Zyklus 10), Reviews ohne Diff\-Grundlage („schau mal über das Projekt"), CI\-Integration als Pflicht\-Gate.

## Open questions

Woher kommt die Spec im Fremd\-Modus, wenn der PR keine hat — PR\-Beschreibung als Soll akzeptieren oder Meta\-Finding? Schwellenwert 50 Zeilen: pauschal oder pro Linse (Spec\-Compliance lohnt auch bei Mini\-Diffs)? Sollen confirmed\-Findings aus Fremd\-Reviews in einer Wissensdatei landen (Muster wiederkehrender Fehler — Brücke zu Spec 01/02)? Falls ja, ist der Pfad durch Spec 00 vorgezeichnet: `docs/reviews/findings.md` als Wissens\-Artefakt mit Kopfzeile.

## Next steps

gate.py und collect\_context.py implementieren (Kontext\-Paket zuerst — es trägt die Qualität); die drei Linsen\-Prompts schreiben und gegeneinander abgrenzen; Widerlegungs\-Prompt mit Default\-widerlegt\-Regel formulieren; beide Renderer bauen; Eval 1 (Bug vs. Nicht\-Bugs) als ersten Härtetest fahren.
