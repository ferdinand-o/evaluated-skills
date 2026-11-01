# review-bench — Nachmessung Review-Werkzeuge auf großen Repos

Skripte zur Messung vom 2026-11-01, Ergebnisse in `../deep-review-report.md`,
Abschnitt „Nachmessung auf großen Repos". Die Repos selbst liegen nicht im Repo; `build.sh`
baut sie aus Upstream-Tags neu.

```
seeds.py     Fehler-Einbauten je Szenario (genaue Ersetzung, muss genau einmal passen)
truth.json   Grundwahrheit: eingebaute (P, Q, D, E) und echte (R) Fehler mit Datei und Zeile
build.sh     baut py-diff, py-path, dl-diff, dl-path unter $BENCH/repos
run.sh       ein Lauf: run.sh <repo> <cr|eng|sp> <nr>, Ergebnis in $BENCH/out/<repo>-<tool>-<nr>.json
match.py     Vorauswahl der Treffer je Lauf (Datei plus Stichwort); jeder Treffer wird am Text nachgeprüft
```

Vorbereitung:

    export BENCH=/pfad/zum/arbeitsverzeichnis
    git clone --filter=blob:none https://github.com/pypa/pip $BENCH/pip-up
    git clone --filter=blob:none https://github.com/danieleteti/delphimvcframework $BENCH/dmvc-up
    git clone --depth 1 https://github.com/obra/superpowers $BENCH/superpowers
    bash build.sh

`run.sh` sperrt Lesezugriffe auf `/usr`, `/opt`, die Upstream-Klone und `git -C`. Der erste
Pfad-Lauf auf pip hat ohne diese Sperre das lokal installierte pip als Vergleich benutzt.
