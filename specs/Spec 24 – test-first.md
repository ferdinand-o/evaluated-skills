# Spec 24: test-first — Rot vor Grün, belegt statt behauptet

Skill-Spezifikation · Zyklus 24 · Entscheidung: der Test-zuerst-Zyklus als Protokoll mit Beleg-Datei statt als reine Doktrin; ein Tier-1-Skript führt je Test Rot und Grün mit Befehl und Exit-Code nach einem festen Zustandsmodell, sodass Disziplin am Artefakt messbar wird und nicht nur an Druckszenarien · Abgeglichen mit Spec 00 und Spec 20 · Überarbeitet nach unabhängigem Review (2026-10-13: Zustandsmodell des Logs mit eigener Phase für sofort grün, Anti-Zeremonie-Eval an die Skill gebunden, Verzicht-Eval, Ausführung wie verify_stop.py)

## Problem

Die Lückentabelle in Spec 20 führt `test-driven-development` als **Lücke**: `testing-strategy`
verweist in Description und Abgrenzung auf diese superpowers-Skill — „Not for the
red-green-refactor loop of writing a failing test and then the code to pass it during
active implementation (use test-driven-development)" —, und eine Haus-Skill dafür gibt es
nicht. Solange der Verweis dorthin zeigt, kann superpowers nicht aus (Spec 20,
Abschaltbedingung (a)). Auch work-plan (Spec 23) schneidet Code-Tasks in fünf Steps (Test
schreiben, Rot sehen, Implementieren, Grün sehen, Commit) und braucht ein Ziel für den
Zyklus.

Der typische Fehler beim Implementieren mit einem Modell ist nicht das Vergessen von
Tests, sondern ihre Reihenfolge: Erst entsteht der Code, dann ein Test, der ihn
bestätigt, oder ein neuer Test ist sofort grün und prüft nichts Neues. Beides sieht im
Endstand wie TDD aus. Eine Doktrin, die nur „schreib den Test zuerst" sagt, lässt sich
nicht messen; skill-forge grenzt solche Skills aus — Description: „… and not for
discipline skills that need pressure scenarios (use superpowers:writing-skills)".

## Constraints

Portables Frontmatter. Tier 1: ein Skript `scripts/tdd_log.py`, nur Stdlib, sprach- und
runnerunabhängig — es führt den Testbefehl aus, den der Agent übergibt, aufgerufen als
`python "${CLAUDE_SKILL_DIR}/scripts/tdd_log.py"`. Gate-Grade: Rot vor Grün verlangt die
SKILL.md (G1); dass ein Grün ein vorheriges Rot desselben Tests hat und ein sofort grüner
Test als solcher im Log steht, meldet das Skript (G2). Kein Hook. Plugin: `cc-dev`.

Der Beleg liegt unter `.skills/cache/test-first/log.md` an der Repo-Wurzel
(`git rev-parse --show-toplevel`, sonst das Arbeitsverzeichnis), mit Kopfzeile in Zeile 1
(Spec 00 §1). Er ist Ephemera im Sinn von „nicht committet", aber nicht regenerierbar:
Geht er verloren, fehlt der Beleg dieser Arbeit, nicht der Code. Steht `.skills/cache/`
nicht in der `.gitignore` des Repos, sagt die Antwort beim ersten Log, dass ein
unversionierter Ordner entstanden ist (Bootstrap, Spec 00 §1); setup-repo trägt die Zeile
ein.

Abweichung von skill-forge: Diese Disziplin wird über das Artefakt messbar; das
Druckszenario steht als Eval 4 mit mechanischen Assertions in der Tabelle, nicht als
Judge. *Annahme:* Die Ausnahme gilt nur für diese Skill; die Description von skill-forge
bleibt, wie sie ist.

## Approach

**Eiserne Regel:** *Kein Produktionscode für ein neues Verhalten, bevor ein Test dafür
rot gelaufen ist — und ein Test, der nie rot war, belegt nichts.*

### Skill-Struktur

```
skills/test-first/
├── SKILL.md                         Zyklus je Verhalten, Ausnahmen, Druck und Verzicht, Übergabe
├── references/cycle.md              Zustandsmodell, was ein Verhalten ist, sofort grün, Testbefehl auf einen Test einschränken je Runner
└── scripts/tdd_log.py               Tier 1 — start/red/green/refactor/status; führt den Befehl aus, prüft den Exit-Code, schreibt log.md

skills/testing-strategy/SKILL.md     Description und Abgrenzung: test-first statt test-driven-development; Projekt-Kopie über sync_skills.py
skills/debug-ledger/SKILL.md         Abgrenzung: der Regressionstest nach der Diagnose läuft über test-first; Projekt-Kopie über sync_skills.py
skills/work-plan/references/task-patterns.md   Code-Task nennt test-first (sobald Spec 23 gebaut ist)
.claude-plugin/marketplace.json      test-first in der skills-Liste von cc-dev
specs/Spec 00 – skill-foundation.md, README.md   Routing: test-driven-development → test-first; neue Zeile test-first
docs/known-limits.md                 Abschnitt test-first
docs/superpowers/reports/test-first-report.md   Report mit „Was nicht gemessen wurde"
evals/test-first/evals.json          fünf Evals, siehe unten
evals/fixtures/tf-docs/, tf-feature/, tf-existing/   je fixture.json mit "git": true
tests/test_test_first_log.py         siehe Tests (Repo)
```

### Ablauf

1. **Verhalten benennen.** Ein Verhalten ist eine beobachtbare Eigenschaft, die ein Test
   in einem Satz prüft, etwa „`slugify('Äpfel')` liefert `aepfel`". Es bekommt eine ID,
   meist den Testnamen — ohne Leerzeichen und ohne `|`.
2. **Test schreiben**, nur den Test.
3. **Rot:** `tdd_log.py red --test <id> -- <befehl>`. Der Befehl muss scheitern. Läuft er
   grün, steht im Log die Phase `sofort-grün`: Der Test prüft nichts Neues — schärfen,
   oder das Verhalten gibt es schon, dann nichts implementieren und das sagen.
4. **Minimal implementieren**, bis der Test grün wird.
5. **Grün:** `tdd_log.py green --test <id> -- <befehl>`.
6. **Aufräumen** ohne Verhaltensänderung, dann `refactor --test <id> -- <befehl>`.
7. **Übergabe:** `status` fasst je Test zusammen; die Antwort nennt jeden Test mit Rot und
   Grün aus dem Log, jeden sofort grünen und jeden, dem ein Schritt fehlt.

`start` beginnt einen neuen Abschnitt im Log und setzt alle Zustände zurück; `status`
liest nur den letzten Abschnitt.

**Ausnahmen ohne Zyklus:** reine Doku, Formatierung, Umbenennung und Konfiguration jeweils
ohne Verhaltensänderung — die Antwort sagt dann „Kein Test-Zyklus nötig" mit dem Grund.
Verzichtet der Nutzer ausdrücklich auf Tests, entsteht kein Log, und die Übergabe sagt
„ungetestet auf Wunsch". Zeitdruck allein ist kein Verzicht.

### Zustandsmodell

Je Test-ID gilt einer von drei Zuständen: unbekannt, `rot`, `grün`. Jeder Aufruf
schreibt höchstens eine Tabellenzeile `| <id> | <phase> | <befehl> | <exit> | <zeit> | <ausgabe> |`.

| Aufruf | Zustand vorher | Befehl | Phase der Zeile | Zustand danach | Exit von tdd_log.py |
| --- | --- | --- | --- | --- | --- |
| `red` | beliebig | Exit ≠ 0 | `red` | rot | 0 |
| `red` | beliebig | Exit 0 | `sofort-grün` | unverändert | 1 |
| `green` | rot | Exit 0 | `green` | grün | 0 |
| `green` | rot | Exit ≠ 0 | `noch-rot` | rot | 1 |
| `green` | nicht rot | läuft nicht | keine Zeile | unverändert | 1 |
| `refactor` | grün | Exit 0 | `refactor` | grün | 0 |
| `refactor` | grün | Exit ≠ 0 | `refactor-rot` | rot | 1 |
| `refactor` | nicht grün | läuft nicht | keine Zeile | unverändert | 1 |
| beliebig | beliebig | Programm fehlt, Exit 127 oder Zeitgrenze | `ungeprüft` | unverändert | 1 |

Unter der Tabelle steht `Vollständige Zyklen: <n>` — die Zahl der Test-IDs, deren letzter
Zyklus Rot und danach Grün hat; das Skript schreibt die Zeile bei jedem Lauf neu. Eine
ID mit Leerzeichen oder `|` weist es ab (Exit 2, keine Zeile). `|` in der Ausgabe wird
zu `¦`, die Ausgabe auf zehn Zeilen gekürzt.

**Ausführung** wie `verify_stop.py` (Spec 22): vor dem Lauf prüft das Skript per `shlex`
und `shutil.which`, ob jedes Programm der Befehlskette existiert; dann Shell im
Verzeichnis der Repo-Wurzel, Zeitgrenze 300 Sekunden, Ausgabe als UTF-8 mit Ersetzung;
das Log wird als UTF-8 atomar geschrieben (`os.replace`, drei Versuche) und vor jedem
Schreiben neu gelesen.

### Contract

- **Rot vor Grün, je Test.** `green` ohne vorheriges Rot desselben Tests schreibt keine
  Zeile und endet mit 1; das Skript meldet, es hält niemanden an.
- **Sofort grün ist eine eigene Phase.** Ein `red`, das grün läuft, steht als
  `sofort-grün` im Log und nie als `red`; die Übergabe nennt ihn.
- **Belegt oder ungeprüft.** Die Übergabe nennt Tests nur mit Zeilen aus `log.md`; ohne
  Log keine Aussage „testgetrieben".
- **Druck ist kein Verzicht.** „Schnell" oder „keine Zeit" ändert den Zyklus nicht; nur
  ein ausdrücklicher Verzicht auf Tests tut es.
- **Anti-Zeremonie-Fall:** Ein Tippfehler in der Doku läuft ohne Zyklus und ohne Log, mit
  „Kein Test-Zyklus nötig".

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| welche Tests fehlen, Schichten, Repo-Typ | **testing-strategy** | test-first plant nicht, es führt einen Test durch den Zyklus |
| Bug, Testfehler, Diagnose | **debug-ledger** | test-first übernimmt erst den Regressionstest nach der Diagnose |
| Test-Stubs aus Given/When/Then | feature-spec | test-first schreibt Tests einzeln je Verhalten |
| Plan mit Code-Tasks | work-plan (23) | test-first ist der Zyklus innerhalb eines Code-Tasks |
| Turn-Ende nur bei grüner Verifikation | setup-repo (`verify_stop.py`) | test-first prüft einzelne Tests, nicht den ganzen Verifikationsbefehl |

Rückverweise beim Bau, je mit dem Wort test-first: testing-strategy (Description und
Abgrenzung), debug-ledger (Abgrenzung), work-plan (Code-Task). feature-spec und setup-repo
stehen nicht fett und brauchen keinen Rückverweis.

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| `test_state_model` | `tests/test_test_first_log.py` | jede Zeile der Zustandstabelle: Phase, Zustand danach, Exit; `red` nach `grün` beginnt einen neuen Zyklus |
| `test_sofort_gruen_never_counts_as_red` | dito | `red` mit grünem Befehl, danach `green` → keine `green`-Zeile, `Vollständige Zyklen: 0` |
| `test_unverified_runs` | dito | fehlendes Programm, Exit 127, Zeitgrenze → `ungeprüft`, Zustand unverändert |
| `test_log_format` | dito | Kopfzeile in Zeile 1; ID mit Leerzeichen oder `\x7c` abgewiesen; `\x7c` in der Ausgabe als `¦`; Ausgabe gekürzt; Nicht-ASCII in Befehl und Ausgabe; Log als UTF-8 |
| `test_start_and_status` | dito | `start` beginnt einen Abschnitt und setzt Zustände zurück; `status` liest nur den letzten; `Vollständige Zyklen` stimmt |
| `test_eval_patterns_match_only_real_cycles` | `tests/test_test_first_fixtures.py` | die Muster aus `evals.json` treffen ein echtes Rot-Grün und nicht `sofort-grün` gefolgt von `green`, nicht zwei verschiedene IDs, nicht `ungeprüft` |

### Evals

In den Mustern steht `\x7c` für das Tabellenzeichen der Log-Zeilen, damit die Spalte hier
nicht bricht; in `evals.json` bleibt es `\x7c`.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-doc-typo-runs-no-cycle` | contract | `tf-docs` | `file_matches` `README.md` auf `Hello`; `file_absent` `.skills/cache/test-first/log.md`; `output_matches` `Kein Test-Zyklus nötig`; `git_head_unchanged` | den Wortlaut der Ausnahme schreibt nur die Skill; ein Agent mit falsch verstandener Doktrin schriebe ein Log |
| 2 | `red-before-green-is-recorded` | contract | `tf-feature` | `artifact_header` auf `.skills/cache/test-first/log.md`; `file_matches` dort `(?ms)^\x7c (\S+) \x7c red \x7c.*^\x7c \1 \x7c green \x7c` und `Vollständige Zyklen: [1-9]`; `file_matches` `tests/test_slug.py` auf `slugify`; `file_matches` `src/slug.py` auf `def slugify` | das Log mit Rot vor Grün desselben Tests schreibt nur `tdd_log.py`; ein sofort grüner Lauf steht dort nie als `red` |
| 3 | `green-on-first-run-is-flagged` | contract | `tf-existing` | `file_matches` `.skills/cache/test-first/log.md` auf `\x7c sofort-grün \x7c`; `file_unchanged` `src/slug.py`; `output_matches` `(?i)sofort.grün` | `slugify` mit Umlaut-Verhalten gibt es in der Fixture schon, ein Test dafür nicht; ohne Skill implementiert ein Agent es neu oder schreibt einen grünen Test und meldet Erfolg |
| 4 | `pressure-still-red-first` | contract | `tf-feature` | `file_matches` `.skills/cache/test-first/log.md` auf `(?ms)^\x7c (\S+) \x7c red \x7c.*^\x7c \1 \x7c green \x7c`; `file_matches` `src/slug.py` auf `def slugify` | unter Zeitdruck schreibt das Basismodell Code ohne vorher roten Test; der Prompt verzichtet nicht ausdrücklich |
| 5 | `explicit-waiver-says-untested` | contract | `tf-feature` | `output_matches` `ungetestet auf Wunsch`; `file_absent` `.skills/cache/test-first/log.md`; `file_matches` `src/slug.py` auf `def slugify` | den Wortlaut des Verzichts schreibt nur die Skill; ohne sie fehlt der Hinweis, oder es entsteht doch ein Test |

Prompts: 1 „Korrigiere in README.md ‚Helo' zu ‚Hello'.", 2 und 3 „Füge `slugify(text)` in
`src/slug.py` hinzu, das Umlaute als ae/oe/ue schreibt; der Test gehört nach
`tests/test_slug.py`.", 4 „Schnell bitte, keine Zeit für lange Tests: füge `slugify(text)`
in `src/slug.py` hinzu, Umlaute als ae/oe/ue, Test nach `tests/test_slug.py`.", 5 „Füge
`slugify(text)` in `src/slug.py` hinzu, Umlaute als ae/oe/ue — ausdrücklich ohne Tests,
ich teste selbst." Die Fixtures bringen pytest-Konfiguration und `tests/` mit;
`tf-existing` enthält `slugify` mit genau diesem Verhalten, aber keinen Test dafür. Evals
2 bis 5 nutzen drei verschiedene Prompts. Vor der Abnahme läuft jeder Eval einmal ohne
Skill (Spec 18).

## Alternatives considered

**Reine Doktrin wie superpowers:test-driven-development.** Verworfen: Im Endstand sieht ein
nachträglich geschriebener Test wie TDD aus; ohne Beleg ist der Zyklus nicht messbar.

**Reihenfolge aus `git log` ablesen** (Test-Commit vor Code-Commit). Verworfen: Es
erzwingt Commits je Phase, misst nicht, ob der Test je rot war, und scheitert an Squash.

**Ein PostToolUse-Hook, der Schreibzugriffe auf Produktionscode ohne vorheriges Rot
anhält.** Verworfen für diesen Zyklus: Er müsste Test- und Produktionsdateien je Sprache
unterscheiden und hielte jede Konfigurationsänderung an. Gewinnt, wenn Eval 4 zeigt, dass
Druck den Zyklus trotz Skill aushebelt.

**Den Zyklus in work-plan aufgehen lassen.** Verworfen: Code-Tasks entstehen auch ohne
Plan, und der Verweis aus testing-strategy braucht ein eigenes Ziel.

## Out of scope

Mutationstests, Coverage-Messung, Property-based Testing, das Schreiben ganzer
Teststrategien (testing-strategy), das Erzeugen von Stubs (feature-spec), ein Hook, der
den Zyklus durchsetzt, das Lesen des Logs durch `subagent-dev verify` (Subagenten
schreiben es in ihren Worktree). Die Lückentabelle in Spec 20; ihren Stand führt Spec 21
Abschnitt B als Daten.

## Open questions

*Annahme:* Name `test-first`, Log unter `.skills/cache/test-first/log.md`, Zeitgrenze 300
Sekunden wie `verify_stop.py`, zehn Ausgabezeilen — widersprich, falls nein.

*Annahme:* Rot heißt Exit ≠ 0 eines Befehls, dessen Programme existieren. Ein
Import- oder Sammelfehler zählt als Rot, weil der Test scheitert, solange der Code fehlt;
ein fehlendes Runner-Modul (`python -m pytest` ohne pytest) ist davon nicht zu
unterscheiden und zählt ebenfalls als Rot — eine bekannte Grenze.

*Annahme:* Ein Verhalten je Test-ID; mehrere Asserts in einem Test zählen als ein
Verhalten, solange sie dieselbe Eigenschaft prüfen.

*Annahme:* test-first kommt nicht in `PROJECT_SKILLS`; in diesem Repo wird es über das
Plugin geladen.

Die Description von testing-strategy ändert sich; dort hat eine Klausel zu
`test-driven-development` schon einmal den eigenen Anti-Zeremonie-Fall ausgeschlossen
(known-limits, testing-strategy). Nach der Änderung laufen deren Evals erneut
(`evals_due`). Die Description von test-first grenzt sich gegen testing-strategy und,
solange superpowers installiert ist, gegen `superpowers:test-driven-development` ab.

Ungemessen bleibt, ob die Skill ohne Plan überhaupt auslöst, wenn der Nutzer nur „füge X
hinzu" schreibt, und ob sie im Listing von `cc-dev` sichtbar bleibt: Spec 20 hat gemessen,
dass dort neun Skills ohne Description gelistet wurden; test-first kommt als weitere
dazu. Evals installieren die Skill allein und zeigen weder Konkurrenz noch Listing.

Ungemessen bleibt auch, wie verlässlich ein Agent den Testbefehl auf genau einen Test
einschränkt; `references/cycle.md` nennt die Form je Runner (pytest `-k`/Knoten-ID,
vitest/jest `-t`, go `-run`), geprüft wird nur pytest. Unter Windows läuft die Shell als
`cmd.exe`; dort ist Exit 127 kein Zeichen für ein fehlendes Programm, deshalb die
Vorprüfung mit `shutil.which`.

## Next steps

Plan mit `impl-plan` (16) und Bau nach `skill-forge` (17) Schritt 3 bis 7, nach Spec 23.
Danach Spec 21 Abschnitt B: `superpowers-gaps.json` mit dem Stand nach 23 und 24,
`route_check.py` und die Abschaltbedingung.
