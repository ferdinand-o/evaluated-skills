#!/bin/bash
# Baut die vier Test-Repos als frische Git-Repos ohne Upstream-Historie.
set -euo pipefail
B=${BENCH:?BENCH auf das Arbeitsverzeichnis setzen}
PIP=$B/pip-up
DMVC=$B/dmvc-up
OUT=$B/repos
SEEDS=$(dirname "$(readlink -f "$0")")/seeds.py
mkdir -p $OUT

init() { git -C "$1" init -q -b main; git -C "$1" config user.name "Fixture"; git -C "$1" config user.email "fixture@example.invalid"; }
wipe() { find "$1" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +; }

# --- py-diff: Basis pip 25.0 (Vendor schon auf 25.1), HEAD 25.1 + P1..P6
R=$OUT/py-diff; rm -rf $R; mkdir -p $R; init $R
git -C $PIP archive 25.0 | tar -x -C $R
rm -rf $R/src/pip/_vendor; git -C $PIP archive 25.1 src/pip/_vendor | tar -x -C $R
git -C $R add -A; git -C $R commit -qm "pip 25.0"; git -C $R tag base
wipe $R; git -C $PIP archive 25.1 | tar -x -C $R
python3 $SEEDS py-diff $R
git -C $R add -A
git -C $R commit -qF - <<'MSG'
Release 25.1

- New experimental `pip lock` command writing a pylock.toml (PEP 751).
- `--group [path:]group` installs a dependency group from pyproject.toml (PEP 735).
- Interrupted downloads are resumed with HTTP range requests (`--resume-retries`).
- Progress bar while installing several packages.
- Wheel filenames are parsed with packaging; legacy names are deprecated.
- PackageFinder caches its results in dicts instead of lru_cache.
- Python 3.8 is no longer supported.
MSG

# --- py-path: Schnappschuss pip 25.1 + Q1..Q6, eine Revision
R=$OUT/py-path; rm -rf $R; mkdir -p $R; init $R
git -C $PIP archive 25.1 | tar -x -C $R
python3 $SEEDS py-path $R
git -C $R add -A; git -C $R commit -qm "pip 25.1"

# --- dl-diff: Basis rc7 ausser sources/ (rc6, JsonDataObjects schon rc7), HEAD rc7 + D1..D6
R=$OUT/dl-diff; rm -rf $R; mkdir -p $R; init $R
git -C $DMVC archive v3.5.0-silicon-rc7 | tar -x -C $R
rm -rf $R/sources; git -C $DMVC archive v3.5.0-silicon-rc6 sources | tar -x -C $R
git -C $DMVC archive v3.5.0-silicon-rc7 sources/JsonDataObjects.pas | tar -x -C $R
git -C $R add -A; git -C $R commit -qm "3.5.0-silicon-rc6"; git -C $R tag base
rm -rf $R/sources; git -C $DMVC archive v3.5.0-silicon-rc7 sources | tar -x -C $R
python3 $SEEDS dl-diff $R
git -C $R add -A
git -C $R commit -qF - <<'MSG'
3.5.0-silicon-rc7

- SQL Server: foRefresh re-reads the row by key, tables with triggers work; limit(n,0) returns no rows.
- WebSocket server: bounded frame payload length, handshake and frame read timeouts.
- One request, one answer, on every host: real HTTP verb (no method override), duplicated
  security headers refused, dot segments refused in paths and route parameters,
  first query value wins, cookies decoded on Indy.
- Session cookie: HttpOnly by default, optional Secure attribute.
- Rate limit store: throttled cleanup, ceiling on distinct keys.
- QUERY HTTP method in router and REST client; MapQuery in the minimal API.
- Delphi 13.2 and current TaurusTLS build fixes.
MSG

for r in py-diff py-path dl-diff; do echo "== $r"; git -C $OUT/$r log --oneline; done
git -C $OUT/py-diff diff --shortstat base..HEAD
git -C $OUT/dl-diff diff --shortstat base..HEAD

# --- dl-path: Schnappschuss rc7 + E1..E6, eine Revision (Units aus 2026, nach dem Wissensstand)
R=$OUT/dl-path; rm -rf $R; mkdir -p $R; init $R
git -C $DMVC archive v3.5.0-silicon-rc7 | tar -x -C $R
python3 $SEEDS dl-path $R
git -C $R add -A; git -C $R commit -qm "3.5.0-silicon-rc7"
