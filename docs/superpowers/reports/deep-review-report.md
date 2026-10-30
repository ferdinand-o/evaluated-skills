<!-- skill: deep-review | schema: 1 | generated: von Hand nach docs/superpowers/plans/2026-10-30-deep-review.md, Task 1 -->
# deep-review — Abschlussbericht

Gebaut nach `specs/Spec 26 – deep-review.md` und
`docs/superpowers/plans/2026-10-30-deep-review.md`. Stand: Task 1 (Messfixture und
Basislinie, 2026-10-30). Die Skill selbst gibt es noch nicht; dieser Bericht hält fest,
woran sie sich in Task 23 messen lassen muss.

## Was entstanden ist

```
evals/fixtures/dr-seeded/fixture.json        Rechnungslauf, fünf eingebaute Fehler
evals/fixtures/dr-seeded/README.md           Projekt-README (Baseline-Commit)
evals/fixtures/dr-seeded-clean/fixture.json  dieselbe Fixture ohne die fünf Fehler
evals/fixtures/dr-seeded-clean/README.md     wie oben
tests/test_deep_review_kit.py                test_seeded_fixtures
```

Beide Fixtures bauen mit `prepare()` drei Commits: `fixture baseline` (README.md),
das Gerüst mit Tag `base` (`.gitignore`, `conftest.py`, `app/__init__.py`) und den Code
(`app/store.py`, `app/billing.py`, `app/export.py`, drei Testdateien, 166 Zeilen).
Der Bereich `base..HEAD` enthält damit genau den Code. Die README liegt als Datei im
Fixture-Ordner, weil `prepare()` den Baseline-Commit ohne `--allow-empty` macht und eine
Git-Fixture mit nur `fixture.json` dort abbricht.

Die fünf Fehler, je eine Klasse aus der Spec; Lage und Klasse stehen in `fixture.json`
unter `description`, nicht im Code:

| Nr. | Klasse | Stelle (`dr-seeded`) |
| --- | --- | --- |
| 1 | `None` über zwei Dateien | `app/store.py:31` liefert `None`, `app/billing.py:32` indiziert es; `build_invoices` fängt nur `UnknownCustomer` |
| 2 | Grenzwert um eins daneben | `app/billing.py:15`, `>=` statt `>` gegen `MAX_POSITIONS` |
| 3 | Ressourcenleck nur im Fehlerpfad | `app/export.py:7–12`, `open` ohne `with`/`finally` |
| 4 | verschluckte Exception | `app/billing.py:23–25`, `except (KeyError, ArithmeticError): continue` |
| 5 | Kommentar widerspricht Code | `app/store.py:34–35`, „neueste zuerst" über aufsteigendem `sorted` |

`test_seeded_fixtures` prüft: beide Manifeste mit `"git": true`, zwei Commits, Tag `base`
am ersten; Gerüst, Messages und Dateimenge gleich; genau fünf abweichende Blöcke, jeder
von einer `Datei:Zeile`-Angabe der `description` getroffen; keine verräterischen Wörter
im Code; die mitgelieferten Tests laufen auf beiden Fassungen grün (also trifft keiner
die fünf Fehler).

## Basislinie

**Aufbau.** Je Fixture und Werkzeug drei Läufe, jeder in einem frischen Workspace aus
`evalkit.workspace.prepare(dest, None, fixture_dir)`, Timeout 600 s, Claude Code 2.1.314,
Standard-Berechtigungsmodus:

- `/code-review`: `claude -p "/code-review base..HEAD" --output-format json`
  (Modell der Sitzung, laut `modelUsage` `claude-opus-5-5`; keine Stufe angegeben).
- Sonnet: `claude -p --model sonnet "Prüf den Diff base..HEAD auf Fehler. Nenne je Fund
  Datei:Zeile und Grund." --output-format json` (`claude-sonnet-5-5`), ohne Inventar.

Treffer heißt: richtige Datei und Stelle, Klasse sinngemäß. Ausgewertet von Hand aus dem
Feld `result`; die Rohantworten liegen nicht im Repo.

### Trefferquote auf `dr-seeded`

| Lauf | F1 | F2 | F3 | F4 | F5 | Treffer | weitere Funde | `total_cost_usd` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/code-review` 1 | ja | ja | ja | ja | ja | 5/5 | 3 | 0,0811 |
| `/code-review` 2 | ja | ja | ja | ja | ja | 5/5 | 4 | 0,1206 |
| `/code-review` 3 | ja | ja | ja | ja | ja | 5/5 | 3 | 0,1215 |
| Sonnet 1 | ja | ja | ja | ja | ja | 5/5 | 1 | 0,0632 |
| Sonnet 2 | ja | ja | ja | ja | ja | 5/5 | 3 | 0,0840 |
| Sonnet 3 | ja | ja | ja | ja | ja | 5/5 | 1 | 0,0527 |

Mittel: `/code-review` 5,0 von 5, Sonnet 5,0 von 5; Vereinigung beider ebenfalls 5.
„Weitere Funde" sind Meldungen jenseits der fünf: nicht atomares `save()`, halb geladener
Store nach doppelter ID in `load()`, CSV-Formel-Injection, fehlende Grenzwerttests.

### Fehlalarme auf `dr-seeded-clean`

`/code-review` liefert eine JSON-Liste von Funden; Sonnet trennt selbst zwischen „Fehler"
und „Schwächen/Hinweisen". Gezählt ist beides, getrennt nach Code und Tests/Stil.

| Lauf | als Fehler gemeldet | davon Code | davon Tests/Stil | Hinweise ohne Fehler-Einstufung | `total_cost_usd` |
| --- | --- | --- | --- | --- | --- |
| `/code-review` 1 | 7 | 5 | 2 | — | 0,1366 |
| `/code-review` 2 | 8 | 4 | 4 | — | 0,1476 |
| `/code-review` 3 | 10 | 9 | 1 | — | 0,1420 |
| Sonnet 1 | 0 | 0 | 0 | 5 (3 Code, 2 Tests) | 0,0555 |
| Sonnet 2 | 0 | 0 | 0 | 6 (4 Code, 2 Tests) | 0,0446 |
| Sonnet 3 | 0 | 0 | 0 | 7 (5 Code, 2 Tests) | 0,0613 |

Zwei der `/code-review`-Läufe schreiben im Begleittext selbst, sie hätten keinen
eindeutigen Fehler gefunden, und geben die Liste trotzdem als Funde aus. Wiederkehrend in
allen sechs Läufen: `save()` schreibt nicht atomar, `load()` bleibt nach einer doppelten
ID halb gefüllt, der Grenzwert 50/51 ist ungetestet; in fünf von sechs: CSV-Injection.
Keiner dieser Funde betrifft eine der fünf Stellen.

**Kosten.** Diese zwölf Läufe: 1,1106 USD (`/code-review` 0,7494, Sonnet 0,3612; im Mittel
0,125 bzw. 0,060 je Lauf). Dazu kam eine erste Runde von zwölf Läufen auf einer früheren
Fassung der Fixtures für 1,8539 USD, zusammen 2,9645 USD.

**Erste Runde.** Auch dort fanden alle sechs Läufe auf `dr-seeded` 5 von 5. Auf der
sauberen Fassung meldeten drei von sechs Läufen zu Recht, dass `except LookupError` in
`build_invoices` auch einen `KeyError` aus fehlenden Kundenfeldern als „Kunde unbekannt"
verbucht, ein echter Fehler, den beide Fassungen gemeinsam hatten. Behoben in beiden
gleich (eigene Exception `UnknownCustomer`, Serialisieren vor dem Schreiben,
Duplikatprüfung beim Laden, `ROUND_HALF_UP`, dokumentierter Abbruch bei ungültiger
Bestellung), danach alle zwölf Läufe neu. Die Tabellen oben gelten für die eingecheckte
Fassung.

### Was das für die Abnahme heißt

Die Spec setzt als Schwelle: deep-review findet im Mittel mindestens so viele der fünf wie
`/code-review` und Sonnet zusammen. Beide Basislinien liegen schon bei 5 von 5, ihre
Vereinigung auch; deep-review kann auf `dr-seeded` also höchstens gleichziehen. Die
Fixture trennt in der Trefferquote nichts: 166 Zeilen passen ganz in den Kontext, und
jeder Fehler ist lokal sichtbar (Fehlermeldung „mehr als" neben `>=`, Kommentar direkt
über dem `sorted`, `UnknownCustomer` nirgends ausgelöst). Den Effekt, auf den die Spec
zielt (eine Stelle wird nicht gelesen, OverclaimBench), erzeugt sie nicht. Messbar bleibt
die Präzision: `/code-review` meldet auf der sauberen Fassung 7 bis 10 Funde.

## Was nicht gemessen wurde

**deep-review selbst** — die Skill ist noch nicht gebaut; ihre Läufe auf beiden Fixtures,
die Abschaltungen und der Vergleich mit dieser Basislinie folgen in Task 23.

**Ob die Fixture schwer genug ist** — die Basislinie sagt nein (siehe oben). Eine größere
Fixture, in der eine Fehlerstelle ohne Lesen der zweiten Datei nicht auffällt, ist nicht
gebaut und nicht gemessen.

**Tests im Lauf** — alle Läufe im Standard-Berechtigungsmodus; `permission_denials` ist
in 8 von 12 Läufen der zweiten Runde nicht leer: `python -m pytest`, `~/.claude/CLAUDE.md`
und verkettete Bash-Aufrufe (`git log && git diff …`) bekamen keine Freigabe. Den Diff
holten sich alle Läufe danach auf anderem Weg; die Funde stammen aus dem Lesen, nicht aus
Ausführung.

**Die Stufe von `/code-review`** — ohne Angabe übernimmt das Kommando die zuletzt
getippte Stufe; welche das headless war, steht nicht in der Antwort. Mehrere Läufe
schreiben, es habe keinen Verify-Schritt gegeben. Andere Stufen sind nicht gemessen.

**Kosten der Unteragenten** — `total_cost_usd` ist die Zahl der CLI. Ob sie Unteragenten
von `/code-review` vollständig enthält, ist nicht nachgeprüft; `modelUsage` nennt nur
`claude-opus-5-5`.

**Streuung** — drei Läufe je Zelle; bei 5 von 5 in allen sechs Läufen sagt das nichts über
seltene Ausfälle. Die Zählung der Fehlalarme ist eine Handauswertung durch eine Person
(den bauenden Agenten), ohne zweite Auswertung.
