# Teuer umkehrbar: Kategorien, Schlüssel, was check sieht

Eine Entscheidung ist **groß**, wenn ihr Schritt in eine Kategorie dieser Tabelle fällt — egal
wie kurz der Diff ist. Die Tabelle ist die eine Quelle für Doktrin und Skript:
`decide_log.py` liest sie für die Kategorien eines Schlüssels (`add --class gross`) und für die
Pfadmuster von `check`. Was hier steht, gilt; eine zweite Liste der Kategorien und Pfadmuster im
Skript gibt es nicht. Nur die Befehle, die `guard` erkennt (unten), stehen auch als Konstante
`GUARD_COMMANDS` im Skript, weil die Hook-Kopie ohne `references/` läuft; ein Test hält beide
Listen gleich. Fehlt
die Datei oder parst die Tabelle nicht, endet `check` mit Exit 2 („ungeprüft —
references/reversibility.md fehlt“ bzw. mit dem Grund) und `add --class gross` mit Exit 1.

## Kategorien

| Kategorie | Bedeutung | Beispiel | Grad | Pfadmuster | Grenze |
| --- | --- | --- | --- | --- | --- |
| `api` | öffentliche Schnittstelle, auf die sich andere verlassen | ein Feld aus der Antwort von `GET /users` entfernen | teilweise | `openapi.*`, `api/openapi.*` | eine öffentliche Python- oder JS-Schnittstelle erkennt check nicht |
| `migration` | Schema- oder Datenänderung, die auf jeder Datenbank läuft | Spalte `fax` aus `customers` entfernen | teilweise | `**/migrations/`, `**/alembic/versions/`, `db/**/*.sql` | eine Spalte, die nur im Modell entfällt, sieht check nicht |
| `data-delete` | Löschen von Daten oder Dateien, die kein Revert zurückbringt | `rm -rf data/`, `DELETE FROM orders`, `git clean -fdx` | ungeprüft | — | steht in keinem Diff |
| `unsaved-work` | Verwerfen ungesicherter Arbeit im Arbeitsbaum | `git reset --hard`, `git checkout -- .`, `git stash drop` | ungeprüft | — | steht in keinem Diff |
| `push` | Veröffentlichen oder Umschreiben geteilter Historie | `git push --force` auf `main`, ein Tag pushen | ungeprüft | — | steht in keinem Diff |
| `external` | Nebenwirkung außerhalb des Repos | eine Mail senden, deployen, ein Issue schließen | ungeprüft | — | steht in keinem Diff |
| `dependency` | neue, entfernte oder gewechselte Abhängigkeit; Lieferkette und Lockfile anderer betroffen | `python-dateutil` in `pyproject.toml` aufnehmen | teilweise | `**/pyproject.toml`, `**/requirements*.txt`, `**/setup.py`, `**/setup.cfg`, `**/Pipfile`, `**/package.json`, `**/Cargo.toml`, `**/go.mod`, `**/Gemfile`, `**/poetry.lock`, `**/uv.lock`, `**/Pipfile.lock`, `**/package-lock.json`, `**/yarn.lock`, `**/pnpm-lock.yaml`, `**/Cargo.lock`, `**/go.sum`, `**/Gemfile.lock` | andere Ökosysteme und vendorte Abhängigkeiten sieht check nicht |
| `permissions` | Rechte, Automatisierung oder Zuständigkeit im Repo | einen Workflow mit `secrets.*` anlegen, `CODEOWNERS` ändern | teilweise | `.github/workflows/`, `**/CODEOWNERS`, `.claude/settings.json` | Berechtigungen im Code sieht check nicht |
| `cost` | laufende Kosten oder Kontingent | einen bezahlten API-Plan buchen, eine größere Instanz bestellen | ungeprüft | — | steht in keinem Diff |

So liest das Skript die Tabelle (die Kopfzeile oben bleibt wörtlich so):

- **Kategorie** — ein Name in Backticks, klein, mit Bindestrichen; jeder nur einmal. `rule` ist
  reserviert (unten).
- **Grad** — `geprüft` (check sieht jede Änderung an den Pfadmustern), `teilweise` (check sieht
  die Pfadmuster, aber nicht jeden Weg zur Änderung — Spalte Grenze), `ungeprüft` (steht in
  keinem Diff; check sieht sie nie). Ein anderes Wort ist ein Fehler. Keine Kategorie oben heißt
  `geprüft`: Jedes Pfadmuster kennt nur die Orte, die es nennt (Spec 28, Review 2026-11-02).
- **Pfadmuster** — Muster in Backticks, durch Komma getrennt, relativ zur Repo-Wurzel; `—` bei
  `ungeprüft`. `geprüft` und `teilweise` brauchen mindestens ein Muster, `ungeprüft` hat keines.
- **Bedeutung** — der Grund, den check je gemeldeter Stelle nennt.

Die Schlusszeile jeder Ausgabe von check entsteht aus der Spalte Grad, in Tabellenreihenfolge:
„ungeprüft: data-delete, unsaved-work, push, external, cost; teilweise: api, migration,
dependency, permissions“.

## Pfadmuster

- Endet ein Muster auf `/`, ist es ein Präfix: `.github/workflows/` trifft jede Datei darunter.
  `x/**/` ist dasselbe wie `x/` (`**/` sind null oder mehr Ordner): es trifft `x/datei` und
  tiefer, nicht `x` selbst.
- Sonst ist es ein Glob, den das Skript selbst in eine Regex übersetzt: `*` trifft beliebige
  Zeichen außer `/`, `?` ein Zeichen außer `/`, `**/` null oder mehr Ordner, ein `**` ohne `/`
  danach beliebige Zeichen samt `/`. Alles andere gilt wörtlich (`[` ist kein Zeichensatz).
- `pyproject.toml` trifft nur die Datei an der Wurzel, `**/pyproject.toml` auch
  `svc/pyproject.toml`, `**/migrations/` auch `evals/fixtures/x/migrations/0001.py`,
  `db/**/*.sql` sowohl `db/schema.sql` als auch `db/a/b.sql`.

Eine **Stelle** ist eine Datei im Diff: geändert, neu, gelöscht oder unversioniert.

## Schlüssel

Jede große Frage in `docs/big-decisions.md` trägt einen Schlüssel
`<kategorie>:<pfadmuster>[#<text>]`, zum Beispiel:

- `dependency:pyproject.toml` — jede Änderung an `pyproject.toml` an der Wurzel, auch das Entfernen
  einer Abhängigkeit
- `dependency:pyproject.toml#python-dateutil` — `pyproject.toml` nur, wenn eine hinzugefügte
  Zeile `python-dateutil` enthält (Aufnehmen); weitere Änderungen in derselben Datei gibt der
  Eintrag dann mit frei
- `migration:migrations/` — jede Datei unter `migrations/` (ebenso `migration:migrations/**/`)
- `migration:evals/fixtures/` — die Fixtures unter `evals/fixtures/*/migrations/` in diesem Repo

check gibt eine Stelle frei, wenn ein Block mit Status `freigegeben` einen Schlüssel derselben
Kategorie trägt, dessen Pfadmuster die Datei trifft (und dessen `#<text>` in einer hinzugefügten
Zeile steht; eine unversionierte Datei ist ganz hinzugefügt). Nur entfernte Zeilen gibt nur ein
Schlüssel ohne Text frei: Eine Datei, deren Diff nur entfernte Zeilen hat (Entfernen einer
Abhängigkeit, Löschen einer Migration), braucht einen Schlüssel ohne `#<text>`. Ein Text, der mit `-`
oder `+` beginnt, ist kein Schlüssel: `add` weist ihn ab, und einer, der von Hand so in der Ablage
steht, gibt nichts frei (Hinweis in der Ausgabe von check). Kann check die Zeilen einer Datei für
`#<text>` nicht lesen (Kodierung, Rechte, binär), meldet es sie als Stelle „unlesbar — selbst
prüfen“. Ein Block mit `offen` oder `abgelehnt` gibt nichts frei. Für Frage plus Schlüssel gilt nur
der jüngste Block: Ist eine freigegebene Frage neu gestellt und offen, gibt der ältere Block nichts
mehr frei („D-<neu> … steht offen, D-<alt> überholt“). Eine Freigabe gilt für ihren Schlüssel,
nicht für eine einzelne Änderung — wer sie enger will, nimmt `#<text>`. Ein `#` ohne Text oder ein
Tab im Pfadmuster ist kein Schlüssel: `add` weist ihn ab („hat leeren Text nach #“), und einer, der
von Hand so in der Ablage steht, gibt nichts frei — `add` und check prüfen die Form mit derselben
Funktion. Das Pfadmuster ist relativ zur Repo-Wurzel wie die Pfade im Diff: ein führendes `./`
fällt weg; ein absoluter Pfad oder ein Teil `..` träfe nie eine Datei — `add` weist ihn ab
(„Pfadmuster muss relativ zur Repo-Wurzel sein“), und von Hand in der Ablage gibt er nichts frei
(Hinweis in der Ausgabe von check).

check nimmt genau eine Revision (`--range <rev>`) und vergleicht sie mit dem Arbeitsbaum:
`git diff <commit>` mit dem Commit, den `git rev-parse --verify <rev>^{commit}` nennt, dazu die
unversionierten Dateien; ein Merge-Commit wird wie jede Revision verglichen. Die Freigaben kommen
immer aus der Arbeitskopie von `docs/big-decisions.md`. Ein Bereich (`<a>..<b>`, `<a>...<b>`,
`^!`, `^@`, `^-`, ein führendes `^`) endet mit Exit 2 („ungeprüft — check nimmt eine Revision,
nicht „<angabe>“; den Bereich selbst prüfen“) — einen PR-Diff prüft der Nutzer selbst; eine
einzelne Revision, die nicht auflöst, endet mit Exit 2 („ungeprüft — Revision „<angabe>“ nicht
gefunden (<erste Zeile der Meldung von git>)“); ein Repo ohne Arbeitsbaum (Bare-Repo, aus `.git` heraus) endet mit Exit 2 („ungeprüft —
kein Arbeitsbaum“). Fehlt die Ablage, ist sie unlesbar oder wird sie übersprungen, sagt jede Stelle
„Freigaben nicht gelesen (<Grund>)“.

### rule

`rule:<thema>` ist die Kategorie für Fragen, die eine Regel `immer fragen` hochgestuft hat. Sie
hat keine Pfadmuster und steht deshalb nicht in der Tabelle; check vergleicht sie nie.
`add` nimmt `rule:<thema>` nur an, wenn eine Regel `immer fragen` das Thema trifft.

## Befehle, die guard erkennt

`decide_log.py guard` ist ein optionaler `PreToolUse`-Hook auf Bash (`assets/hooks/decide-guard.json`,
die Skill installiert ihn nie). Er zerlegt den Befehl an `&&`, `||`, `;`, `|`, `&` und
Zeilenumbruch außerhalb von Anführungszeichen, überspringt je Teil führende Zuweisungen und
`sudo`, bei `git` die globalen Optionen (`-C <pfad>` setzt das Verzeichnis), und erkennt
Kurzoptionen auch gebündelt (`-rf`, `-sSd`, `-XPOST`). Ein erkannter Teil wird zur Rückfrage an den
Nutzer (`ask`); nur `git push` mit freigegebenem Ziel geht still durch. Diese Tabelle ist dieselbe
Liste wie `GUARD_COMMANDS` im Skript:

| Kategorie | Befehl | erkannt, wenn | Freigabe über die Ablage |
| --- | --- | --- | --- |
| `push` | `git push` | immer, außer mit `-n`/`--dry-run` | ja: Schlüssel `push:<muster>`, das Muster trifft `<remote>/<zweig>` |
| `push` | `gh pr merge` | immer | nein, immer Rückfrage |
| `push` | `gh release create` | immer | nein, immer Rückfrage |
| `external` | `gh pr create` | immer | nein, immer Rückfrage |
| `external` | `gh issue create` | immer | nein, immer Rückfrage |
| `external` | `gh issue close` | immer | nein, immer Rückfrage |
| `external` | `gh issue comment` | immer | nein, immer Rückfrage |
| `external` | `npm publish` | immer | nein, immer Rückfrage |
| `external` | `twine upload` | immer | nein, immer Rückfrage |
| `external` | `docker push` | immer | nein, immer Rückfrage |
| `external` | `terraform apply` | immer | nein, immer Rückfrage |
| `external` | `terraform destroy` | immer | nein, immer Rückfrage |
| `external` | `kubectl apply` | immer | nein, immer Rückfrage |
| `external` | `kubectl delete` | immer | nein, immer Rückfrage |
| `external` | `curl` | Methode außer `GET`/`HEAD` (`-X`, `-X<methode>`, `--request`, `--request=<methode>`), `--data*`, `--form*`, `--json`, `-T`/`--upload-file` oder ein Kurzoptions-Bündel mit `d` oder `F` | nein, immer Rückfrage |
| `external` | `wget` | `--post-data`, `--post-file` oder `--method` | nein, immer Rückfrage |
| `data-delete` | `rm` | `-r`, `-R`, `--recursive` oder ein Bündel mit `r`/`R`, außer jedes Ziel liegt unter `/tmp/` oder in der Ausnahmeliste | nein, immer Rückfrage |
| `data-delete` | `git clean` | `-f`/`--force`, auch gebündelt (`-fdx`) | nein, immer Rückfrage |
| `data-delete` | `git branch` | `-D` oder `--delete --force` | nein, immer Rückfrage |
| `data-delete` | `psql` | `DROP`, `TRUNCATE` oder `DELETE FROM` ohne `WHERE` (ohne Groß-/Kleinschreibung) in einem Argument | nein, immer Rückfrage |
| `data-delete` | `sqlite3` | wie `psql` | nein, immer Rückfrage |
| `data-delete` | `mysql` | wie `psql` | nein, immer Rückfrage |
| `unsaved-work` | `git reset` | `--hard` | nein, immer Rückfrage |
| `unsaved-work` | `git checkout` | `--`, `.`, `-f`/`--force` oder ein Argument, das als Pfad im Arbeitsverzeichnis existiert | nein, immer Rückfrage |
| `unsaved-work` | `git restore` | immer, außer nur mit `--staged`/`-S` ohne `--worktree`/`-W` | nein, immer Rückfrage |
| `unsaved-work` | `git stash drop` | immer | nein, immer Rückfrage |
| `unsaved-work` | `git stash clear` | immer | nein, immer Rückfrage |

Ausnahmeliste für `rm` (*Annahme:* der Inhalt ist regenerierbar): `.skills/cache` als Präfix
relativ zur Repo-Wurzel, sonst die Pfadkomponenten `__pycache__`, `.pytest_cache`, `.mypy_cache`,
`.ruff_cache`, `node_modules`, `build`, `dist`, `.venv` in beliebiger Tiefe.

**Push-Ziel.** `-u`, `--set-upstream`, `-v`, `--verbose`, `-q`, `--quiet`, `--no-verify`,
`--progress` und `--porcelain` ändern das Ziel nicht; jede andere Option (`--force`,
`--force-with-lease`, `--delete`, `--tags`, `--all`, `--mirror`, `-o` …) ist immer Rückfrage. Ohne
Argumente ist das Ziel der Upstream des Zweigs (ohne Upstream: Rückfrage), mit nur `<remote>`
`<remote>/<aktueller zweig>`, mit genau einem Refspec `<remote>/<ziel>`: `HEAD` wird der aktuelle
Zweig (abgelöster `HEAD`: Rückfrage), `refs/heads/<x>` wird `<x>`; ein anderes Ziel unter `refs/`,
ein führendes `+`, eine leere Quelle (`:<ziel>`) und mehr als ein Refspec sind Rückfrage. Ein
beauftragter Push wird einmal abgelegt (`--approved-by-request`, `--key push:origin/claude/x`) und
gilt dann für jeden weiteren Push dorthin; wie bei check gilt je Frage und Schlüssel nur der jüngste
Block.

Der Grund der Rückfrage lautet „decide: <kategorie> — <befehl, höchstens 80 Zeichen>: <grund>“ mit
„immer Rückfrage“, „keine Freigabe mit Schlüssel push:<ziel> in docs/big-decisions.md“ oder
„Befehl nicht zerlegbar“ (unbalancierte Anführungszeichen und ein Programmname der Tabelle im
Text). Ein eigener Fehler des Hooks hält nichts an: `{"systemMessage": "[decide] Hook ungeprüft —
<grund>"}`, Exit 0. Was guard nicht zerlegt — `$(…)` und Backticks außerhalb von Anführungszeichen,
`bash -c`, `eval`, `xargs`, Aliase, Skripte, Werkzeuge außer Bash —, sieht es nicht; deshalb nennt
check `push`, `external`, `data-delete` und `unsaved-work` weiter als ungeprüft.

## Bis zur Freigabe bleibt alles stehen

Bis zur Freigabe unterbleibt die ganze Antwort auf eine große Frage, nicht nur ihr teuerster Teil.
Wer über das Löschen einer Spalte entscheiden lässt, entfernt auch das Feld im Modell nicht, obwohl
check eine Spalte, die nur im Modell entfällt, nicht sieht; dasselbe gilt für jede Änderung, die
check nicht oder nur teilweise sieht. Die übrige Arbeit läuft weiter.
