# review-bench — Nachmessung Review-Werkzeuge auf großen Repos

Skripte zur Messung vom 2026-11-01, Ergebnisse in `../deep-review-report.md`,
Abschnitt „Nachmessung auf großen Repos". Die Repos selbst liegen nicht im Repo; `build.sh`
baut sie aus Upstream-Tags neu.

```
seeds.py     Fehler-Einbauten je Szenario (genaue Ersetzung, muss genau einmal passen)
truth.json   Grundwahrheit: eingebaute (P, Q, D, E) und echte (R) Fehler mit Datei und Zeile;
             py-c1..c3 tragen die Einbauten aus py-diff, deren Datei im jeweiligen Paket liegt
build.sh     baut py-diff, py-path, dl-diff, dl-path und die Pakete py-c1..c3 unter $BENCH/repos
run.sh       ein Lauf: run.sh <repo> <tool> <nr>, Ergebnis in $BENCH/out/<repo>-<tool>-<nr>.json
counterparts.py  Prototyp: Gegenstellen der geaenderten Python-Zeilen (ast) fuer tool crx
match.py     Vorauswahl der Treffer je Lauf (Datei plus Stichwort); jeder Treffer wird am Text nachgeprüft
```

Werkzeuge von `run.sh`:

| Tool | Lauf | Timeout |
| --- | --- | --- |
| `cr` | `/code-review --max-findings all <bereich>` | 1800 s |
| `crc` | `cr` plus Auftrag „Gegenstelle prüfen" | 1800 s |
| `crx` | `cr` plus Ausgabe von `counterparts.py` | 1800 s |
| `eng` | `/engineering:code-review <bereich>` | 1800 s |
| `sp` | superpowers `requesting-code-review` über `base..HEAD` | 1800 s |
| `dr` | `Review <bereich> mit deep-review.` mit `skills/deep-review` aus diesem Repo im Workspace | 3600 s |
| `drnc` | wie `dr`, der Gegenstellen-Block geht nicht an den Reviewer | 3600 s |

Der Bereich ist `base..HEAD`, bei `py-c*` `mid..HEAD`, bei den Pfad-Szenarien die Pfadliste.
`dr` kopiert die Skill nach `$W/.claude/skills/deep-review` (über `.git/info/exclude` aus Git
heraus) und erlaubt zusätzlich `Bash(python3:*)`, `Bash(python:*)` für `review_kit.py`, `Skill`
und `Edit` nur unter `./.skills/cache/deep-review/` für `report.md`. Ein `claude -p` startet
je Paket ein `/code-review`; bei bis zu 7 Paketen zu 3–5 Minuten reichen 1800 s nicht. `drnc`
lässt Schritt 3 laufen, weil `counterparts` die Paket-Bereiche baut; nur der Block fehlt. Den
Laufordner (`report.md`, `findings.json`) sichert `run.sh` nach `$BENCH/out/<name>.kit/`;
`match.py` liest ihn mit.

Vorbereitung:

    export BENCH=/pfad/zum/arbeitsverzeichnis
    git clone --filter=blob:none https://github.com/pypa/pip $BENCH/pip-up
    git clone --filter=blob:none https://github.com/danieleteti/delphimvcframework $BENCH/dmvc-up
    git clone --depth 1 https://github.com/obra/superpowers $BENCH/superpowers
    bash build.sh

`$BENCH` darf nicht in diesem Repo liegen; `run.sh` bricht sonst ab.

## Lesesperre

Der erste Pfad-Lauf auf pip hat ohne Sperre das lokal installierte pip als Vergleich benutzt.
Eine Deny-Regel schlägt jede Allow-Regel und kennt keine Ausnahme; der eigene Workspace lässt
sich unter einem gesperrten `$BENCH/work` also nicht ausnehmen. Deshalb liegt er unter
`$BENCH/work/<gruppe>/<name>` (Gruppe `py` für pip, `dl` für DMVC), und Läufe derselben Gruppe
laufen nacheinander (`flock` auf `$BENCH/work/<gruppe>.lock`; ein zweiter Aufruf wartet). Vor
dem Klonen löscht `run.sh` die Reste abgebrochener Läufe der Gruppe. Neben dem eigenen Workspace
gibt es so keinen fremden derselben Gruppe; die andere Gruppe ist gesperrt. Parallel laufen
können ein `py-*`- und ein `dl-*`-Lauf.

Gesperrt (`--disallowedTools`):

- `Read`, `Grep`, `Glob` auf `/usr`, `/opt`, `~/.cache`, `~/.local` (installiertes pip),
  `$BENCH/pip-up`, `$BENCH/dmvc-up` (unveränderter Upstream), `$BENCH/repos` (alle gebauten
  Repos), `$BENCH/out` (Ergebnisse und Gegenstellen früherer Läufe), `$BENCH/work/<andere
  gruppe>`, `$BENCH/*.patch` (Paket-Patches von `build.sh`), dieses Repo samt Haupt-Checkout
  (`seeds.py`, `truth.json`, Berichte) und `~/.claude/projects` (Transkripte früherer Sitzungen).
- `git`, das ein anderes Repo liest oder holt: `git -C`, `git --git-dir`, `git --work-tree`,
  `git diff --no-index`, `git fetch`, `git pull`, `git clone`, `git remote`, `git archive`,
  `git worktree`, `git submodule`. Der Workspace hat kein `origin` mehr; `base` und `mid` holt
  `run.sh` vorher.

Bewusst offen:

- Bash-Regeln vergleichen nur den Anfang des Befehls. `git --no-pager --git-dir=…` oder
  `git -c k=v -C …` beginnt mit `git`, passt auf `Bash(git:*)` und auf keine Deny-Regel.
  `env git …` und `GIT_DIR=… git …` passen auf keine Deny-Regel; ob `Bash(git:*)` sie erlaubt,
  hängt davon ab, wie Claude Code solche Präfixe auflöst (nicht geprüft). Ein Befehl ohne
  passende Allow-Regel ist in `claude -p` abgewiesen.
- Bei `dr`/`drnc` umgeht Python jede Sperre: `python3 -c "open('…/pip-up/…')"` oder ein
  `subprocess` mit `git -C` ist durch `Bash(python3:*)` erlaubt. Die Skill braucht Python für
  `review_kit.py`; enger als `python3:*` lässt sich der Aufruf nicht fassen, weil der Pfad über
  `${CLAUDE_SKILL_DIR}` in wechselnder Schreibweise kommt.
- Die Gruppensperre wirkt nur zwischen `run.sh`-Aufrufen; ein von Hand gestartetes `claude`
  im selben `$BENCH` sieht sie nicht.
- `Read`-Regeln gelten für `Grep` und `Glob` nur nach bestem Bemühen von Claude Code; deshalb
  stehen alle drei einzeln in der Liste.

Nachkontrolle: Nach jedem Lauf sucht `run.sh` in den Transkripten dieses Laufs
(`~/.claude/projects/<workspace>/`, auch die der Subagenten) nach gesperrten Pfaden (`pip-up`,
`dmvc-up`, `repos/py-`, `repos/dl-`, `$BENCH/out`, die andere Gruppe, die Patches, dieses Repo)
und schreibt die Zahl als `probe=` in `status.txt`, die Treffer in `<name>.probe.txt`. Auch
abgewiesene Versuche zählen. `probe` größer 0 heißt: Transkript von Hand lesen, bevor der Lauf
zählt.
