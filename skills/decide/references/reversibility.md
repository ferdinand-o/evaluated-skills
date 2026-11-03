# Teuer umkehrbar: Kategorien, Schlüssel, was check sieht

Eine Entscheidung ist **groß**, wenn ihr Schritt in eine Kategorie dieser Tabelle fällt — egal
wie kurz der Diff ist. Die Tabelle ist die eine Quelle für Doktrin und Skript:
`decide_log.py` liest sie für die Kategorien eines Schlüssels (`add --class gross`) und für die
Pfadmuster von `check`. Was hier steht, gilt; eine zweite Liste im Skript gibt es nicht. Fehlt
die Datei oder parst die Tabelle nicht, endet `check` mit Exit 2 („ungeprüft —
references/reversibility.md fehlt“ bzw. mit dem Grund) und `add --class gross` mit Exit 1.

## Kategorien

| Kategorie | Bedeutung | Beispiel | Grad | Pfadmuster | Grenze |
| --- | --- | --- | --- | --- | --- |
| `api` | öffentliche Schnittstelle, auf die sich andere verlassen | ein Feld aus der Antwort von `GET /users` entfernen | teilweise | `openapi.*`, `api/openapi.*` | eine öffentliche Python- oder JS-Schnittstelle erkennt check nicht |
| `migration` | Schema- oder Datenänderung, die auf jeder Datenbank läuft | Spalte `legacy_id` aus `users` entfernen | teilweise | `**/migrations/`, `**/alembic/versions/`, `db/**/*.sql` | eine Spalte, die nur im Modell entfällt, sieht check nicht |
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

- `dependency:pyproject.toml` — jede Änderung an `pyproject.toml` an der Wurzel
- `dependency:pyproject.toml#python-dateutil` — `pyproject.toml` nur, wenn eine hinzugefügte
  Zeile `python-dateutil` enthält; weitere Änderungen in derselben Datei gibt der Eintrag dann
  mit frei
- `migration:migrations/` — jede Datei unter `migrations/` (ebenso `migration:migrations/**/`)
- `migration:evals/fixtures/` — die Fixtures unter `evals/fixtures/*/migrations/` in diesem Repo

check gibt eine Stelle frei, wenn ein Block mit Status `freigegeben` einen Schlüssel derselben
Kategorie trägt, dessen Pfadmuster die Datei trifft (und dessen `#<text>` in einer
hinzugefügten Zeile steht). Ein Block mit `offen` oder `abgelehnt` gibt nichts frei. Eine
Freigabe gilt für ihren Schlüssel, nicht für eine einzelne Änderung — wer sie enger will, nimmt
`#<text>`. Ein `#` ohne Text oder ein Tab im Pfadmuster ist kein Schlüssel: `add` weist ihn ab
(„hat leeren Text nach #“), und einer, der von Hand so in der Ablage steht, gibt nichts frei —
`add` und check prüfen die Form mit derselben Funktion.

Woher die Freigaben kommen: bei einer einzelnen Revision (`--range <rev>`) aus der Arbeitskopie
von `docs/big-decisions.md`; bei einem Bereich ohne Arbeitsbaum (`<a>..<b>`, `<rev>^!` — auch auf
dem ersten Commit —, `<rev>^-<n>`, und `<a>...<b>` wie `git diff <a>...<b>`: Basis die Merge-Base,
Ende `<b>`, die übliche Form für einen PR-Diff) aus der Ablage im Ende, aufgelöst auf seinen Commit
(`<b>^{commit}:docs/big-decisions.md`). Fehlt sie dort, ist sie wie eine fehlende Ablage. Meldungen
nennen das Ende so, wie es angegeben wurde (`v2`, nicht ein Hash). Fehlt die Ablage, ist sie unlesbar oder wird
sie übersprungen, sagt jede Stelle „Freigaben nicht gelesen (<Grund>)“.

### rule

`rule:<thema>` ist die Kategorie für Fragen, die eine Regel `immer fragen` hochgestuft hat. Sie
hat keine Pfadmuster und steht deshalb nicht in der Tabelle; check vergleicht sie nie.
`add` nimmt `rule:<thema>` nur an, wenn eine Regel `immer fragen` das Thema trifft.

## Bis zur Freigabe bleibt alles stehen

Beispiel: In `app/models.py` steht `legacy_id = Column(Integer)`, ein Kommentar fragt, ob die
Spalte weg kann. Die Spalte zu entfernen ist `migration` (oder `data-delete`, wenn Daten
verloren gehen). Bis ein Block mit diesem Schlüssel `freigegeben` ist, unterbleibt der ganze
Schritt: keine Migration unter `migrations/` **und auch das Feld im Modell bleibt** — eine
Spalte, die nur im Modell entfällt, sieht check nicht (Grad `teilweise`), sie ist trotzdem
dieselbe große Entscheidung. Der kleine Teil daneben (ein ungenutzter `import json`) wird
erledigt; die große Frage steht als `D-<n>` mit Status `offen` in der Ablage.
