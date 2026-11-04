# Teuer umkehrbar: Kategorien, Schlüssel, was check sieht

Eine Entscheidung ist **groß**, wenn ihr Schritt in eine Kategorie dieser Tabelle fällt — egal
wie kurz der Diff ist. Die Tabelle ist die eine Quelle für Doktrin und Skript:
`decide_log.py` liest sie für die Kategorien eines Schlüssels (`add --class gross`) und für die
Pfadmuster von `check`. Was hier steht, gilt; eine zweite Liste der Kategorien und Pfadmuster im
Skript gibt es nicht — das gilt für Kategorien und Pfadmuster. Nur die Mustertabelle von `guard`
(unten) steht auch als Konstante `GUARD_PATTERNS` im Skript, weil die Hook-Kopie ohne `references/`
läuft; ein Test hält die Befehle beider gleich. Fehlt
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
die Skill installiert ihn nie). **Erkennen statt zerlegen:** guard baut die Shell nicht nach, sondern
sucht im ganzen Befehlstext nach den Mustern unten und fragt nach, sobald eines trifft. Genau zerlegt
wird nur ein schlichter `git push`, weil es für ihn eine Freigabe über die Ablage gibt. Schutzziel ist
das Versehen, nicht der verschleierte Befehl.

1. **Vorprüfung.** Enthält der Text keinen Programmnamen der Tabelle, endet guard ohne Ausgabe und
   ohne Subprozess.
2. **Commit-Vorlage ausblenden.** Der Rumpf der Commit-Vorlage von Claude Code
   (`"$(cat <<'WORT'` … `WORT` … `)"`, auch `<< 'WORT'`, `<<-'WORT'`, `"WORT"`) ist Text und wird
   durch ein leeres Wort ersetzt, wenn direkt davor `-m`, `--message`, `-F`, `--body`, `--title`
   oder `--notes` steht (hinter `bash -c` oder `eval` bleibt er Befehl). Ein `\` am Zeilenende
   verbindet zwei Zeilen zu einer; `;`, `&` und `|` innerhalb von Anführungszeichen trennen keine
   Befehle (die SQL-Muster sehen den Text unverändert).
3. **Muster.** Jedes Muster läuft über den ganzen übrigen Text, mit Wortgrenzen (`/bin/rm` trifft,
   `format` nicht); die Optionen eines Befehls sucht es bis zum nächsten `;`, `&`, `|` oder
   Zeilenende. Trifft eines außer `git push`, ist die Antwort Rückfrage mit „immer Rückfrage“ —
   auch wenn der Treffer in einer Zeichenkette steht (`echo "rm -rf x"`, eine Commit-Nachricht in
   `-m '…'`).
4. **Push genau.** Trifft nur `git push`, muss der Text **schlicht** sein: außerhalb von
   Anführungszeichen kein `$`, kein Backtick, kein `(`, `)`, `<`, `>` (außer `2>&1` und
   `>/dev/null`), kein `|`, kein einzelnes `&`, kein Heredoc und kein `cd`, `pushd`, `popd`;
   innerhalb doppelter Anführungszeichen kein unmaskiertes `$(` und kein unmaskierter Backtick
   (Klammern und Backticks in `-m '…'` sind schlicht, ein Backtick in `-m "…"` nicht). Die
   Teile zwischen `&&`, `;` und Zeilenumbruch sind dann einfache Befehle, genau einer davon beginnt
   mit `git … push`; nur ihn zerlegt guard mit `shlex.split`. Sonst — auch bei einem Fehler von
   `shlex` — „Befehl nicht schlicht“.

Diese Tabelle ist dieselbe wie `GUARD_PATTERNS` im Skript. Kurzoptionen zählen auch gebündelt
(`-rf`, `-fdx`, `-sSd`, `-XPOST`); SQL ohne Groß-/Kleinschreibung.

| Kategorie | Befehl | erkannt, wenn | Freigabe über die Ablage |
| --- | --- | --- | --- |
| `push` | `git push` | immer, auch mit globalen Optionen davor (`git -C x push`); `-n`/`--dry-run` ist nichts | ja, nur schlicht: Schlüssel `push:<muster>`, das Muster trifft `<remote>/<zweig>` |
| `push` | `gh pr merge` | immer | nein, immer Rückfrage |
| `push` | `gh release create` | immer | nein, immer Rückfrage |
| `external` | `gh pr create` | immer | nein, immer Rückfrage |
| `external` | `gh pr comment` | immer | nein, immer Rückfrage |
| `external` | `gh pr close` | immer | nein, immer Rückfrage |
| `external` | `gh pr review` | immer | nein, immer Rückfrage |
| `external` | `gh pr edit` | immer | nein, immer Rückfrage |
| `external` | `gh issue create` | immer | nein, immer Rückfrage |
| `external` | `gh issue close` | immer | nein, immer Rückfrage |
| `external` | `gh issue comment` | immer | nein, immer Rückfrage |
| `external` | `gh repo delete` | immer | nein, immer Rückfrage |
| `external` | `gh release delete` | immer | nein, immer Rückfrage |
| `external` | `gh api` | `-X`/`--method` außer `GET`, oder `-f`, `-F`, `--field`, `--raw-field`, `--input` | nein, immer Rückfrage |
| `external` | `npm publish` | `publish` im selben Befehl (`npm --tag x publish`) | nein, immer Rückfrage |
| `external` | `yarn publish` | wie `npm publish` | nein, immer Rückfrage |
| `external` | `pnpm publish` | wie `npm publish` | nein, immer Rückfrage |
| `external` | `cargo publish` | wie `npm publish` | nein, immer Rückfrage |
| `external` | `uv publish` | wie `npm publish` | nein, immer Rückfrage |
| `external` | `poetry publish` | wie `npm publish` | nein, immer Rückfrage |
| `external` | `twine upload` | immer | nein, immer Rückfrage |
| `external` | `docker push` | immer, auch `docker image push` | nein, immer Rückfrage |
| `external` | `terraform apply` | immer | nein, immer Rückfrage |
| `external` | `terraform destroy` | immer (nicht `terraform plan -destroy`) | nein, immer Rückfrage |
| `external` | `kubectl apply` | `apply` im selben Befehl (`kubectl -n x apply`) | nein, immer Rückfrage |
| `external` | `kubectl delete` | wie `kubectl apply` | nein, immer Rückfrage |
| `external` | `curl` | `-X`/`--request` außer `GET`/`HEAD`, oder `-d`, `--data*`, `-F`, `--form*`, `--json`, `-T`, `--upload-file` (auch gebündelt, `-sSd`) | nein, immer Rückfrage |
| `external` | `wget` | `--post-data`, `--post-file` oder `--method` | nein, immer Rückfrage |
| `data-delete` | `rm` | `-r`, `-R`, `--recursive` (auch gebündelt), außer die Ausnahmeliste trifft | nein, immer Rückfrage |
| `data-delete` | `find` | `-delete`, oder `-exec`/`-execdir`/`-ok`/`-okdir` mit `rm` | nein, immer Rückfrage |
| `data-delete` | `git clean` | `-f`/`--force` (auch gebündelt, `-fdx`) | nein, immer Rückfrage |
| `data-delete` | `git branch` | `-D`, oder `--delete`/`-d` mit `--force`/`-f` | nein, immer Rückfrage |
| `data-delete` | `psql` | `DROP TABLE`, `DROP DATABASE`, `DROP SCHEMA`, `DROP COLUMN`, `TRUNCATE` oder `DELETE FROM` ohne folgendes `WHERE` bis zum nächsten `;`, Anführungszeichen oder `&&`, irgendwo im Text (auch im Heredoc), wenn `psql` im Text steht | nein, immer Rückfrage |
| `data-delete` | `sqlite3` | wie `psql` | nein, immer Rückfrage |
| `data-delete` | `mysql` | wie `psql` | nein, immer Rückfrage |
| `unsaved-work` | `git reset` | `--hard`, `--merge` oder `--keep` | nein, immer Rückfrage |
| `unsaved-work` | `git checkout` | `--`, `.`, `-f`/`--force` | nein, immer Rückfrage |
| `unsaved-work` | `git restore` | immer, außer mit `--staged`/`-S` ohne `--worktree`/`-W` | nein, immer Rückfrage |
| `unsaved-work` | `git switch` | `-f`, `--force` oder `--discard-changes` | nein, immer Rückfrage |
| `unsaved-work` | `git stash drop` | immer | nein, immer Rückfrage |
| `unsaved-work` | `git stash clear` | immer | nein, immer Rückfrage |

Ausnahmeliste für `rm -r` (*Annahme:* der Inhalt ist regenerierbar): Die Wörter hinter `rm` bis zum
nächsten `;`, `&`, `|` oder Zeilenende werden mit `shlex.split` gelesen (Fehler → keine Ausnahme);
nach `--` ist jedes Wort ein Ziel, Umleitungen (`2>/dev/null`, `> log`) sind keine.
Sind alle Ziele relative Pfade ohne `..`, `~`, `$`, Backtick und Glob-Zeichen unter `.skills/cache/`
oder mit einer Komponente `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`,
`node_modules`, `build`, `dist`, `.venv`, oder absolute Pfade unter `/tmp/`, gibt es keine
Rückfrage. Kein Ziel → Rückfrage; `rm -rf ~/build` und `rm -rf /home/u/dist` fragen nach.

**Push-Ziel** (nur für den schlichten Teil). `-u`, `--set-upstream`, `-v`, `--verbose`, `-q`,
`--quiet`, `--no-verify`, `--progress` und `--porcelain` ändern das Ziel nicht; `-n`/`--dry-run` als
eigenes Wort (nicht als Wert von `-o`) heißt keine Rückfrage. Jede andere Option (`--force`,
`--force-with-lease`, `--delete`, `--tags`, `-o` …), jede globale git-Option außer `-C <pfad>`
(`git -c k=v push`), ein Refspec mit `+` oder leerer Quelle (`:x`), mehr als ein Refspec, ein Ziel
unter `refs/` außer `refs/heads/<x>`, eine Quelle, die ein Tag ist, ein abgelöster `HEAD`,
`push.default=matching`, ein gesetztes `remote.<remote>.push` oder `remote.<remote>.mirror=true`
(auch ohne Wert) sind immer Rückfrage. Sonst ist das Ziel ohne Argumente `@{push}` des Zweigs, mit
nur `<remote>` dasselbe, wenn dessen Remote `<remote>` ist (sonst Rückfrage), mit
`<remote> <quelle>[:<ziel>]` dann `<remote>/<ziel>` (`HEAD` und `@` werden der aktuelle Zweig,
`refs/heads/<x>` wird `<x>`). Alle Git-Aufrufe laufen im Verzeichnis des Befehls (`cwd` des
Hook-JSON) oder im Pfad von `-C`. Ein beauftragter Push wird einmal abgelegt
(`--approved-by-request`, `--key push:origin/claude/x`) und gilt dann für jeden weiteren Push
dorthin; wie bei check gilt je Frage und Schlüssel nur der jüngste Block.

**Kosten.** Ein Python-Start je Bash-Aufruf: Das Snippet nimmt `python3`, sonst `python`; fehlen
beide, meldet es „[decide] Hook ungeprüft — kein Python“. Git-Prozesse startet guard nur im
Push-Fall.

Der Grund der Rückfrage lautet „decide: <kategorie> — <befehl, höchstens 80 Zeichen>: <grund>“ mit
„immer Rückfrage“, „keine Freigabe mit Schlüssel push:<ziel> in docs/big-decisions.md“ oder
„Befehl nicht schlicht“. Ein eigener Fehler des Hooks hält nichts an: `{"systemMessage": "[decide]
Hook ungeprüft — <grund>"}`, Exit 0. Nach einer Ablehnung wiederholt Claude den Befehl nicht,
weicht nicht auf eine andere Form aus (`bash -c`, ein Skript, ein MCP-Werkzeug) und nennt den
unterlassenen Schritt in der Übergabe.

**Was guard nicht sieht** (known-limits): Befehle, die erst die Shell zusammensetzt — `$VAR`,
`eval`, `bash -c "$X"`, Skripte, Aliase —, Werkzeuge außer Bash (MCP) und Python 2 als einziges
Python. Deshalb nennt check `push`, `external`, `data-delete` und `unsaved-work` weiter als
ungeprüft. **Unnötig gefragt** wird, wenn ein Muster nur in einer Zeichenkette steht, und bei einem
freigegebenen Push in einem Befehl, der nicht schlicht ist (`git push origin x | tail`,
`cd ../o && git push`).

## Bis zur Freigabe bleibt alles stehen

Bis zur Freigabe unterbleibt die ganze Antwort auf eine große Frage, nicht nur ihr teuerster Teil.
Wer über das Löschen einer Spalte entscheiden lässt, entfernt auch das Feld im Modell nicht, obwohl
check eine Spalte, die nur im Modell entfällt, nicht sieht; dasselbe gilt für jede Änderung, die
check nicht oder nur teilweise sieht. Die übrige Arbeit läuft weiter.
