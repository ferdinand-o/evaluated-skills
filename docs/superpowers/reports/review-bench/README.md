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

`match.py` sucht das Stichwort beim Klartext eines Werkzeugs in einem Fenster um die Nennung der
Datei. Bei `dr`/`drnc` gleicht es je Fund aus `findings.json` ab: das Datei-Muster auf `file`,
das Stichwort nur in `summary` und `failure_scenario` desselben Funds, damit ein Nachbarfund
keinen Treffer schenkt. Fehlt `findings.json` im Laufordner, gilt das Fenster über den Schlusstext
(Hinweis auf stderr). Alle Muster, auch die Datei-Muster, ignorieren Groß/Klein.

Werkzeuge von `run.sh`:

| Tool | Lauf | Timeout |
| --- | --- | --- |
| `cr` | `/code-review --max-findings all <bereich>` | 1800 s |
| `crc` | `cr` plus Auftrag „Gegenstelle prüfen" | 1800 s |
| `crx` | `cr` plus Ausgabe von `counterparts.py` | 1800 s |
| `crb` | `/code-review <LEVEL> --max-findings all <bereich>` plus Gegenstellen-Block aus `review_kit.py` (`plan`, `counterparts`, `packets/p1.md` ab der Dateiliste, ohne Kopfzeile, `# Paket` und `Bereich:`; Begleittext wie `crx`; Skill nicht im Workspace; Name `<repo>-crb-<stufe>-<nr>`, `LEVEL` = `low`, `medium` oder `high`, Standard `medium`) | 1800 s |
| `eng` | `/engineering:code-review <bereich>` | 1800 s |
| `sp` | superpowers `requesting-code-review` über `base..HEAD` | 1800 s |
| `dr` | `Review <bereich> mit deep-review.` mit `skills/deep-review` aus diesem Repo im Workspace | 3600 s |
| `drnc` | wie `dr`, der Gegenstellen-Block geht nicht an den Reviewer | 3600 s |

Der Bereich ist `base..HEAD`, bei `py-c*` `mid..HEAD`, bei den Pfad-Szenarien die Pfadliste.
`dr` und `drnc` laufen auch auf `py-path` und `dl-path`, aber nur, wenn `review_kit.py plan --help`
die Option `--path` nennt (Pfad-Modus, Spec 28, Task 7); sonst Exit 2 vor dem ersten `mkdir`. Der
Prompt lautet dort `Prüf die Pfade <liste> mit deep-review.`. `crb` läuft nur auf Bereichen (`review_kit.py plan`
braucht `--range`); auf `*-path` bricht `run.sh` mit Exit 2 ab, ebenso bei `LEVEL` außerhalb von
`low`, `medium`, `high`, jeweils vor dem ersten `mkdir`. Bei `crb` löscht `run.sh` nach dem Block
den Laufordner `.skills` und die Refs (`review_kit.py cleanup`); der Block liegt als
`$BENCH/out/<name>.ctx.md`. `crb` bricht mit Exit 1 ab, wenn `plan`, `counterparts` oder
`cleanup` scheitern, wenn der Plan nicht genau ein Paket hat, dessen Bereich der getippte ist
(geteilter Plan, Wurzel-Commit, Hilfsrefs), oder wenn danach noch Refs unter `refs/deep-review`
stehen; auch dann steht eine Zeile in `status.txt`, mit `cost/turns/err=abbruch:<schritt>` und
`probe=n/a`, und `out/<name>.json` und `.err` eines früheren Laufs gleichen Namens werden gelöscht,
damit `match.py` sie nicht unter diesem Namen wertet. Ebenso bricht `crx` mit
`abbruch:counterparts` ab, wenn `counterparts.py` scheitert oder einen leeren Block liefert, und
jedes Werkzeug mit `abbruch:klon`, wenn `git clone`, `fetch` oder `remote remove` scheitern
(`secs=0`). Begleittext und Block setzt `run.sh` für `crx` und `crb` an einer Stelle zusammen. Die Zeit (`secs`) läuft bei `crb` ab `plan`, wie bei `dr`/`drnc`. `dr` kopiert die Skill nach `$W/.claude/skills/deep-review` (über `.git/info/exclude` aus Git
heraus) und erlaubt zusätzlich `Bash(python3:*)`, `Bash(python:*)` für `review_kit.py`, `Skill`
und `Edit` nur unter `./.skills/cache/deep-review/` für `report.md`. Ein `claude -p` startet
je Paket ein `/code-review`; bei bis zu 7 Paketen zu 3–5 Minuten reichen 1800 s nicht. `drnc`
lässt Schritt 3 laufen, weil `counterparts` die Paket-Bereiche baut; nur der Block fehlt. Den
Laufordner (`report.md`, `findings.json`) sichert `run.sh` nach `$BENCH/out/<name>.kit/`;
`match.py` liest ihn mit.

Laufnummer nur `0-9`, `A-Z`, `a-z` (nicht leer), Repo und Werkzeug zusätzlich `-`; sonst Exit 2
vor dem ersten `mkdir`.

`DRY=1 bash run.sh …` führt alles bis unmittelbar vor `claude -p` aus, gibt Prompt, Länge des
Systemprompts und den Anfang des Blocks auf stderr aus, löscht den Workspace und endet mit Exit 0.
Jeder nichtleere Wert außer `0` gilt als Probe (`DRY=true`, `DRY=yes`). Nach `out/` schreibt und
löscht es nichts: der Block liegt unter `work/`, eine Abbruchzeile geht nur auf stderr; ein
Klonfehler endet mit Exit 1 ohne Abbruchzeile, ein anderer Abbruch mit Exit 1.

Vorbereitung:

    export BENCH=/pfad/zum/arbeitsverzeichnis
    git clone --filter=blob:none https://github.com/pypa/pip $BENCH/pip-up
    git clone --filter=blob:none https://github.com/danieleteti/delphimvcframework $BENCH/dmvc-up
    git clone --depth 1 https://github.com/obra/superpowers $BENCH/superpowers
    bash build.sh

`$BENCH` darf nicht in diesem Repo (Worktree oder Haupt-Checkout) liegen, und sein Elternordner
muss existieren. Beides prüft `run.sh` vor dem ersten `mkdir`; sonst bricht es mit Exit 2 ab,
ohne etwas anzulegen.

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
  (`seeds.py`, `truth.json`, Berichte).
- `Read`, `Grep`, `Glob` auf die Transkripte anderer Sitzungen, einzeln je Projektordner unter
  `$CFG/projects` (`$CFG` ist `${CLAUDE_CONFIG_DIR:-~/.claude}`). Claude Code legt je
  Arbeitsordner einen Ordner an, dessen Name der Pfad ist mit `-` für jedes Zeichen außer
  `A-Z`, `a-z`, `0-9` (`/tmp/x/y` → `-tmp-x-y`), und speichert zu große Werkzeugausgaben dort
  unter `<sitzung>/tool-results/`. Der eigene Ordner (aus `$W` so berechnet) darf nicht unter
  eine Sperre fallen, sonst sieht ein Reviewer von einem großen Diff nur die Vorschau; weil eine
  Deny-Regel keine Ausnahme kennt, sperrt `run.sh` beim Start jeden vorhandenen Projektordner
  außer dem eigenen einzeln, und im eigenen jeden Eintrag, der schon da ist (Transkripte
  früherer Läufe gleichen Namens). Mit gesetztem `CLAUDE_CONFIG_DIR` ist zusätzlich
  `~/.claude/projects` ganz gesperrt.
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
- Projektordner, die erst während des Laufs entstehen, sind nicht gesperrt: ein parallel
  gestarteter Lauf der anderen Gruppe oder eine andere Sitzung mit neuem Arbeitsordner. Den
  Zugriff darauf zählt nur die Nachkontrolle. Auch neue Sitzungen in einem beim Start schon
  vorhandenen fremden Ordner sind gesperrt, neue Einträge im eigenen Ordner nicht.
- Der eigene Ordnername folgt der Kodierung oben (an den vorhandenen Ordnern abgelesen). Weicht
  Claude Code davon ab, etwa wenn es sehr lange Pfade kürzt (nicht geprüft), findet die
  Nachkontrolle den Ordner nicht und meldet `probe=n/a`; lag er schon von einem früheren Lauf
  gleichen Namens da, ist er dann ganz gesperrt.

Nachkontrolle: Nach jedem Lauf sucht `run.sh` in den Transkripten dieses Laufs
(`$CFG/projects/<workspace>/`, auch die der Subagenten) nach gesperrten Pfaden (`pip-up`,
`dmvc-up`, `repos/py-`, `repos/dl-`, `$BENCH/out`, die andere Gruppe, die Patches, dieses Repo,
`$CFG/projects` außer dem eigenen Ordner, im eigenen die Einträge früherer Läufe) und schreibt
die Zahl als `probe=` in `status.txt`, die Treffer in `<name>.probe.txt`. Ein Pfad zählt nur
ganz, also gefolgt von `/` oder einem Zeichen, das keinen Namen fortsetzt: Ein `$BENCH` wie
`/home/user/evaluated-skills-bench` neben dem Repo `/home/user/evaluated-skills` zählt nicht
über das `cwd` jeder Zeile mit. Pfade im eigenen Projektordner (die eigenen `tool-results`)
zählen nicht, außer sie führen mit `..` hinaus. Auch abgewiesene Versuche zählen. `probe`
größer 0 heißt: Transkript von Hand lesen, bevor der Lauf zählt; `probe=fehler` heißt, die
Nachkontrolle selbst ist gescheitert.
