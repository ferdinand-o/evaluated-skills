#!/bin/bash
# run.sh <repo> <tool> <run-nr>   repo: py-diff|py-path|dl-diff|dl-path|py-c1..3   tool: cr|crc|crx|eng|sp|dr|drnc
set -uo pipefail
B=$(readlink -f "${BENCH:?BENCH auf das Arbeitsverzeichnis setzen}")
HERE=$(dirname "$(readlink -f "$0")")
REPO=$1; TOOL=$2; N=$3
NAME=$REPO-$TOOL-$N
EXTRA=()
# Lesesperre (README, Abschnitt „Lesesperre"): eine Deny-Regel schlägt jede Allow-Regel und kennt
# keine Ausnahme, also darf der eigene Workspace unter keinem gesperrten Ordner liegen. Gruppe
# py (pip) und dl (DMVC) laufen je für sich nacheinander (flock), die andere Gruppe ist gesperrt.
case $REPO in
  py-*) GROUP=py; OTHER=dl ;;
  dl-*) GROUP=dl; OTHER=py ;;
  *) echo "unbekanntes Repo: $REPO" >&2; exit 2 ;;
esac
OUT=$B/out; mkdir -p "$OUT" "$B/work/$GROUP" "$B/work/$OTHER"
exec 9> "$B/work/$GROUP.lock"
flock 9
rm -rf "${B:?}/work/${GROUP:?}"/*   # Reste abgebrochener Läufe derselben Gruppe
W=$B/work/$GROUP/$NAME
ROOT=$(git -C "$HERE" rev-parse --show-toplevel)
COMMON=$(git -C "$HERE" rev-parse --path-format=absolute --git-common-dir)
MAIN=$(dirname "$COMMON")
case "$W/" in
  "$ROOT"/*|"$MAIN"/*) echo "BENCH darf nicht im Repo $MAIN liegen" >&2; exit 2 ;;
esac
git clone -q "$B/repos/$REPO" "$W"
git -C "$W" fetch -q --tags
git -C "$W" remote remove origin
BASE=$(git -C "$W" rev-parse --verify -q base || true)
HEAD=$(git -C "$W" rev-parse HEAD)
case $REPO in
  py-path) TARGET="src/pip/_internal/req src/pip/_internal/operations" ;;
  dl-path) TARGET="sources/MVCFramework.JWT.RefreshToken.pas sources/MVCFramework.Middleware.RangeMedia.pas sources/MVCFramework.Middleware.OIDC.pas sources/MVCFramework.OIDC.JWKS.pas sources/MVCFramework.Serializer.CSV.pas sources/MVCFramework.SSE.Writer.pas sources/MVCFramework.JWT.RSA.pas" ;;
  py-c*) TARGET="mid..HEAD" ;;
  *) TARGET="base..HEAD" ;;
esac

ALLOW=("Bash(git:*)" Read Grep Glob)
TO=1800
case $TOOL in
  cr)  PROMPT="/code-review --max-findings all $TARGET" ;;
  crc) PROMPT="/code-review --max-findings all $TARGET"
       EXTRA=(--append-system-prompt "In every review, for each changed line, look up the counterpart it calls or that calls it - including vendored libraries, base classes and framework code outside the diff - and check the contract the change relies on: which exceptions the callee raises, what it returns for edge cases (empty, None, zero), who owns and frees objects, and what a flag or parameter does downstream. Report a finding when the changed code violates that contract.") ;;
  crx) PROMPT="/code-review --max-findings all $TARGET"
       # shellcheck disable=SC2086  # TARGET ist absichtlich eine Liste von Pfaden
       python3 -I "$HERE/counterparts.py" "$W" $TARGET --root src --max-bytes 60000 > "$OUT/$NAME.ctx.md"
       EXTRA=(--append-system-prompt "Below is a mechanically collected list of counterparts for the changed lines of this range: for each changed call the definition it reaches (including vendored code), the exceptions that definition raises, and where changed keyword arguments flow and which conditions test them. It was produced by a script for every changed call site, not chosen by suspicion. Pass it unchanged to every reviewer subagent you start and use it to check the changed code against the contracts it relies on.

$(cat "$OUT/$NAME.ctx.md")") ;;
  eng) PROMPT="/engineering:code-review $TARGET" ;;
  sp)
    mkdir -p "$W/.claude/skills"
    cp -r "$B/superpowers/skills/requesting-code-review" "$W/.claude/skills/"
    echo ".claude/" >> "$W/.git/info/exclude"
    PROMPT="/requesting-code-review Review the change base..HEAD of this repository. BASE_SHA: $BASE HEAD_SHA: $HEAD. DESCRIPTION and PLAN_OR_REQUIREMENTS: the commit message of HEAD (git log -1 HEAD). When the reviewer returns, print its complete list of issues verbatim, each with file:line." ;;
  dr|drnc)
    # deep-review aus diesem Repo; je Paket ein /code-review in einem claude -p (bis 7 Pakete
    # zu 3-5 Minuten), daher 3600 s. Python für review_kit.py, Edit für report.md im Laufordner.
    mkdir -p "$W/.claude/skills"
    cp -r "$ROOT/skills/deep-review" "$W/.claude/skills/deep-review"
    echo ".claude/" >> "$W/.git/info/exclude"
    TO=3600
    ALLOW+=("Bash(python3:*)" "Bash(python:*)" Skill "Edit(./.skills/cache/deep-review/**)")
    PROMPT="Review $TARGET mit deep-review."
    # drnc: ohne Gegenstellen-Block. Schritt 3 läuft trotzdem, er baut die Paket-Bereiche.
    [ "$TOOL" = drnc ] && PROMPT="$PROMPT Führe Schritt 3 (counterparts) nur für die Paket-Bereiche aus: gib dem Reviewer den Block aus packets/<id>.md nicht mit und lies ihn nicht."
    ;;
  *) echo "unbekanntes Werkzeug: $TOOL" >&2; exit 2 ;;
esac

# Gesperrt für Read/Grep/Glob (//pfad = absolut): System-Python, Caches und Nutzer-Installs
# (installiertes pip), Upstream-Klone, gebaute Repos, Ausgaben früherer Läufe, Workspaces der
# anderen Gruppe, Paket-Patches von build.sh, dieses Repo (seeds.py, truth.json, Berichte) und
# die Transkripte früherer Sitzungen.
P="/$B"
DENY=()
for d in //usr //opt "/$HOME/.cache" "/$HOME/.local" "/$HOME/.claude/projects" \
         "$P/pip-up" "$P/dmvc-up" "$P/repos" "$P/out" "$P/work/$OTHER" "/$ROOT" "/$MAIN"; do
  DENY+=("Read($d/**)" "Grep($d/**)" "Glob($d/**)")
done
DENY+=("Read($P/*.patch)" "Grep($P/*.patch)" "Glob($P/*.patch)")
# git, das ein anderes Repo liest oder holt
DENY+=("Bash(git -C:*)" "Bash(git --git-dir:*)" "Bash(git --work-tree:*)" "Bash(git diff --no-index:*)"
       "Bash(git fetch:*)" "Bash(git pull:*)" "Bash(git clone:*)" "Bash(git remote:*)"
       "Bash(git archive:*)" "Bash(git worktree:*)" "Bash(git submodule:*)")

STAMP=$(mktemp)
START=$(date +%s)
( cd "$W" && timeout "$TO" claude -p "$PROMPT" "${EXTRA[@]}" --output-format json \
    --allowedTools "${ALLOW[@]}" --disallowedTools "${DENY[@]}" \
    > "$OUT/$NAME.json" 2> "$OUT/$NAME.err" 9>&- )
EC=$?
END=$(date +%s)
COST=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get('total_cost_usd'), d.get('num_turns'), d.get('is_error'))" "$OUT/$NAME.json" 2>/dev/null || echo "parse-fail")
# Laufordner von deep-review sichern, bevor der Workspace geht (match.py liest report.md, findings.json)
if [ -d "$W/.skills/cache/deep-review" ]; then
  rm -rf "$OUT/$NAME.kit"; cp -r "$W/.skills/cache/deep-review" "$OUT/$NAME.kit"
fi
# Nachkontrolle der Sperre: gesperrte Pfade im Transkript dieses Laufs (auch abgewiesene Versuche
# und Python-Aufrufe, die keine Regel sieht). probe>0 heißt: $NAME.probe.txt von Hand lesen.
PROJ=${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/$(printf %s "$W" | sed 's/[^A-Za-z0-9]/-/g')
if [ -d "$PROJ" ]; then
  find "$PROJ" -name '*.jsonl' -newer "$STAMP" -exec cat {} + 2>/dev/null \
    | grep -oF -e pip-up -e dmvc-up -e "$B/repos" -e repos/py- -e repos/dl- -e "$B/out" \
        -e "$B/work/$OTHER" -e "$B/c1.patch" -e "$B/c2.patch" -e "$B/c3.patch" -e "$ROOT" -e "$MAIN" \
        -e /.claude/projects \
    | sort | uniq -c > "$OUT/$NAME.probe.txt"
  PROBE=$(awk '{s+=$1} END {print s+0}' "$OUT/$NAME.probe.txt")
else
  PROBE=n/a
fi
rm -f "$STAMP"
echo "$NAME exit=$EC secs=$((END-START)) cost/turns/err=$COST probe=$PROBE" >> "$OUT/status.txt"
rm -rf "$W"
