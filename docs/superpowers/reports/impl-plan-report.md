# impl-plan — Abschlussbericht

Gebaut nach `specs/Spec 16 – impl-plan.md` und `docs/superpowers/plans/2026-09-02-impl-plan.md`.
Zyklus 16, Tier 1 ohne eigenes Skript, gebaut am 2026-09-02 sequenziell im Hauptkontext
(zehn Tasks, ein Commit je Task; das Gate sagte `sequential`, weil jede Task die
Plandatei oder `plan_to_tasks.py` berührt).

## Was entstanden ist

```
skills/impl-plan/SKILL.md                      99 Zeilen (Grenze 150)
skills/impl-plan/references/task-patterns.md   Code-/Doktrin-Task, Pflicht-Tasks, Vokabular
skills/impl-plan/references/reviewer-prompt.md übersetzter writing-plans-Reviewer, erweitert
skills/impl-plan/assets/plan-template.md       lint-sauberes Template, 156 Zeilen
evals/impl-plan/evals.json                     5 contract-Evals
evals/fixtures/ip-tiny, ip-five, ip-tier0      drei Specs, eine Mini-Skill, kein Plan
tests/test_plans_lint.py                       Repo-Test, 6 Tests
tests/test_impl_plan_evals_schema.py           15 Tests
```

In `subagent-dev`: `plan_to_tasks.py` um das Interface-Vokabular (`fn:`, `token:`,
`file:` mit `kind`), `lint --spec/--skill`, die Kopfzeilen-Prüfung und `_meta` in
`lint.json` erweitert — 215 Zeilen dazu, 27 weg im Bau, dazu die Fix-Runde unten; 66 Tests
dort grün vor der Fix-Runde. Nachgezogen:
`subagent-dev`s Description, Ablauf und Abgrenzung zeigen auf `impl-plan`; die
Routing-Matrix in Spec 00 §5 und `README.md` hat die Zeile „Implementierungsplan zu
einer Spec"; der explain-Plan trägt die Kopfzeile.

## Die drei Entscheidungen, die den Bau geprägt haben

**Der Parser bleibt bei `subagent-dev`.** Sauberer nach der Konsumentenregel wäre er
bei `impl-plan`, verworfen wegen der Konvention „Skill-Skripte importieren einander
nie": Ein Subprozess-JSON-Protokoll zwischen zwei Skills wäre eine Schnittstelle, die
es heute nicht gibt — genau die Fehlerklasse „parallel gebaute Schnittstellen". Der
Preis ist sichtbar: `impl-plan` ruft ein fremdes Skript per Kommando auf und muss eine
Degradationszeile kennen, falls es fehlt.

**Das Legacy-Register friert nach Namen ein, nicht nach Befund-Zahl.** Der erste
Entwurf wollte pro Plan eine erlaubte Anzahl Befunde einfrieren. Der Review hat das
gekippt: nicht monoton, für unparsbare Pläne gibt es keine Zahl, und schon die
Kopfzeilen-Prüfung dieser Spec hätte alle Zahlen falsch gemacht, ohne dass ein Plan
angefasst wurde. Jetzt gilt: 16 Namen, nicht gelintet, Menge darf nur schrumpfen.

**Kein Eval hängt am Lint.** Der Eval-Workspace kopiert nur das Skill-Verzeichnis;
`subagent-dev`s Skript ist dort nicht. Statt einen Eval zu schreiben, der strukturell
rot bliebe, prüfen alle fünf die Plandatei direkt — über die Kopfzeile als
Diskriminator, die nur diese Skill schreibt, und über Hausvokabular (kanonische Titel,
`token:`), das `writing-plans` nicht kennt.

## Was gemessen wurde

- **1025 Tests grün beim Bau, 1038 nach den zwei Fix-Runden**, einer fremd rot:
  `test_rest_api_architect_gate.py::test_main_exit_zero_when_degraded_but_checklist_clean`
  ist vorbestehend und fremd — per `git stash` auf unverändertem Stand gegengeprüft; er
  erwartet ein fehlendes Spectral, das in dieser Umgebung über `npx` erreichbar ist.
- **Der Repo-Test über alle Pläne (2026-09-02):** 18 Pläne unter
  `docs/superpowers/plans/`, 16 im Legacy-Register, 2 gelintet (explain, impl-plan),
  beide sauber; das Template sauber. Von den 16 eingefrorenen parsen 8 nicht, die
  übrigen 8 tragen 15 bis 79 Befunde.
- **Der Lint fand beim Bau zwei echte Fehler in diesem Plan selbst:** `--spec` meldete
  fünf Eval-IDs der Spec, die im Plan in keinem Task standen; und ein Sammel-Task
  `Pflicht` im Template-Fließtext wurde als Task geparst. Beides behoben, bevor
  weitergebaut wurde — der Mechanismus hat sich an seinem eigenen Bau bewährt.
- **Schema-Test:** die `file_matches`-Regexe von Eval 3 und 4 greifen an einem
  templatekonformen Tier-0-Beispielplan, Eval 5s `must_not` greift dort nicht; Eval 1
  ist an einem eigenen Anti-Zeremonie-Beispielplan gemessen; beide Beispielpläne sind
  lint-sauber. Eval 2 ist nicht an einen Beispielplan gebunden — seine fünf IDs werden
  gegen die Fixture-Spec geprüft, die beiden Tokens in Eval 4 gegen die Tier-0-Spec.

## Fix-Runde nach dem Review (2026-09-03)

Zwei unabhängige Reviews des Baus — ein Subagent mit frischem Kontext gegen Spec und
Plan, dazu `/code-review` über den Diff — fanden keinen Spec-Bruch, aber vier
Fail-open-Stellen im Lint und zwei Evals, die einen doktrintreuen Plan zu Unrecht
rot gemacht hätten. Alles behoben, jeder Punkt mit Test:

- **Coverage ist jetzt eine Eigenschaft des Plans.** Ohne `--spec` zählt die Datei aus
  der `Spec:`-Zeile; damit prüft auch der Repo-Test die Coverage jedes Plans. Der
  explain-Plan hatte dadurch acht ungedeckte IDs — er nennt sie jetzt in seinem
  Eval-Task. `--skill` ohne auflösbare Spec ist ein Befund, kein stilles Nichts.
- **`lint.json` trägt `coverage`** mit `status: checked | unchecked` und Grund; ein
  übersprungener Abgleich sieht nicht mehr aus wie ein bestandener. `_meta.generated`
  nennt das volle Kommando mit `--spec`/`--skill`.
- **Die Eval-Tabelle wird unter einer Evals-Überschrift gesucht**, nicht als erste
  Tabelle mit einer Spalte `id`; eine id-Zelle ohne Backtick-Wert ist ein Befund. IDs
  zählen nur als ganzes Wort und nur innerhalb von Task-Blöcken — Lint und Eval 2
  messen jetzt dasselbe.
- **Eval 4** erkennt den SKILL.md-Task an `SKILL.md` irgendwo im Titel; task-patterns.md
  sagt das jetzt auch. **Eval 1** zieht die Grenze bei 45 Zeilen, gemessen an einem
  Anti-Zeremonie-Beispielplan von 40 Zeilen, und SKILL.md, Template und task-patterns.md
  sagen, was im Anti-Zeremonie-Fall aus dem Kopf entfällt.
- Ein Verify-Test, der nie rot werden konnte (`rc != 2` bei einem Kommando, das nur 0
  oder 1 liefert), prüft jetzt `present`/`missing` im Ergebnis-JSON. Toter Code
  (`SYMBOL_KINDS`, der Kompatibilitäts-Shim) ist weg, die doppelte Spec-Auflösung durch
  `_resolve_near` ersetzt.

Stand danach: 92 Tests in den drei betroffenen Dateien, Legacy-Messung unverändert
(8 unparsbar, 8 mit 15–79 Befunden), beide neuen Pläne und das Template sauber, der
impl-plan-Plan mit `--skill impl-plan` sauber und `coverage.status: checked`.

### Zweite Runde (2026-09-04)

Dieselben zwei Reviewer über die Fix-Runde. Alle elf Punkte galten als behoben; neu
gefunden und behoben:

- **Eval 4 war zu locker geworden:** SKILL.md zuerst, Evals danach, und ein späterer
  Nachbarn-Task mit „SKILL.md" im Titel bestand. Die Regex verlangt jetzt, dass kein
  SKILL.md-Task vor dem Evals-Task steht; der Test prüft genau diese Reihenfolge.
- **Die Überschriften-Heuristik der Eval-Tabelle** hatte drei Fail-open-Pfade: ein
  H1-Titel mit „Evals" machte das ganze Dokument zum Abschnitt, ein `#`-Kommentar in
  einem Codezaun schloss ihn, „Evaluation der Alternativen" öffnete ihn. Jetzt: ab
  Ebene 2, ganzes Wort, auf maskiertem Text, tiefere Unterüberschriften schließen nicht.
- **Coverage zählt nur Task-Blöcke:** ein Block endet an der nächsten Überschrift bis
  Ebene 3, Prosa hinter dem letzten Task deckt keine ID mehr. Eine `Spec:`-Zeile ohne
  Backtick-Pfad ist ein Befund; ein `--spec`, das von der Zeile abweicht, ebenfalls.
- **Der Anti-Zeremonie-Test asserted jetzt `coverage.status: checked`** — die ip-tiny-Spec
  trägt dafür eine Eval-Tabelle mit einer bestehenden ID, die der Beispielplan nennt.
- **Spec 16 nachgezogen** (Grenze 45, strikte Eval-4-Regex, Spec aus der `Spec:`-Zeile,
  `extract_symbols`), und ein Test vergleicht ihre Eval-Tabelle mit `evals.json`:
  IDs, Zeilengrenze, Regex.

Stand danach: 97 Tests in den drei Dateien, volle Suite 1038 grün mit demselben fremden
Fehlschlag, Legacy-Messung unverändert.

## Was NICHT gemessen wurde

**Kein einziger der fünf Evals ist gefahren.** Derselbe Grund wie bei `explain`:
`evalkit/dispatch.py` verdrahtet `permission_mode="bypassPermissions"`, die
Claude-CLI verweigert das unter uid 0 (`docs/known-limits.md`, „Betrieb"). Was
vorliegt, ist eine schema-valide, regex-geprüfte Eval-Sammlung, kein Nachweis über das
Verhalten der Skill.

**Der Trigger ist ungemessen — und er war die Diagnose.** Spec 16 ist entstanden, weil
„schreib mir den Implementierungsplan" bei `writing-plans` landete und acht unparsbare
Pläne hinterließ. Ob die neue Description das ändert, entscheidet der Harness pro Lauf
(`routing-house-header-not-superpowers` ist stochastisch), und dieser Lauf hat nicht
stattgefunden. Die Kollision ist auf Description-Ebene entschärft, nicht bewiesen
aufgelöst.

**Ob die Skill den Lint benutzt, misst kein Eval.** Im Eval-Workspace fehlt das
Skript; ein Agent, der die SKILL.md befolgt, landet dort in der Degradationszeile. Die
Evals messen, ob der Plan dem Template folgt — die Eiserne Regel („kein Plan fertig
ohne Lint oder ohne dass das gesagt wurde") ist G1-Selbstauskunft, mit dem Repo-Test
als einzigem Zahn, und der beißt nur, wenn jemand `pytest` startet.

**Die 45-Zeilen-Grenze des Anti-Zeremonie-Evals ist an einem Plan gemessen, den ich
selbst geschrieben habe.** Ob ein Agent den Anti-Zeremonie-Fall überhaupt als solchen
erkennt und den Sammel-Task `Pflicht` wählt, statt vier volle Pflicht-Tasks zu
schreiben, ist die eigentliche Frage des Evals — und unbeantwortet.

## Offen für die nächste Runde

- Die fünf Evals außerhalb eines Root-Containers fahren. Am aussagekräftigsten:
  `routing-house-header-not-superpowers` (die Diagnose) und
  `anti-ceremony-two-task-change-stays-small` (die Zeremonie-Falle).
- Beim nächsten echten Plan dieser Sammlung: Schreibt die Skill ihn, oder greift
  wieder `writing-plans`? Das ist die einzige Messung des Triggers, die es heute gibt.
- Ob das Interface-Vokabular im Gebrauch trägt oder ob Pläne weiter nackte Bezeichner
  schreiben, weil die Präfixe im Kopf nicht ankommen — dann wäre `token:` Doktrin ohne
  Konsumenten.
