#!/bin/bash
# run.sh <repo> <tool> <run-nr>   repo: py-diff|py-path|dl-diff|dl-path|py-c1..3   tool: cr|crc|crx|crb|eng|sp|dr|drnc
set -uo pipefail
[ $# -ge 3 ] || { echo "Aufruf: run.sh <repo> <tool> <nr>" >&2; exit 2; }
REPO=$1; TOOL=$2; N=$3
NAME=$REPO-$TOOL-$N
HERE=$(dirname "$(readlink -f "$0")")
ROOT=$(git -C "$HERE" rev-parse --show-toplevel)
COMMON=$(git -C "$HERE" rev-parse --path-format=absolute --git-common-dir)
if [ -z "$ROOT" ] || [ -z "$COMMON" ]; then echo "Repo von run.sh nicht gefunden" >&2; exit 2; fi
MAIN=$(dirname "$COMMON")
# Bis zum ersten mkdir wird nur geprüft, ohne Seiteneffekt. readlink -f gibt nichts aus, wenn mehr
# als die letzte Komponente von BENCH fehlt; ohne diese Prüfung entstünden out/ und work/ unter /.
BENCH_ARG=${BENCH:-}
[ -n "$BENCH_ARG" ] || { echo "BENCH auf das Arbeitsverzeichnis setzen; nichts angelegt" >&2; exit 2; }
B=$(readlink -f -- "$BENCH_ARG")
if [ -z "$B" ] || [ "$B" = / ] || [ ! -d "$(dirname "$B")" ] || { [ -e "$B" ] && [ ! -d "$B" ]; }; then
  echo "BENCH=$BENCH_ARG: Elternordner fehlt oder kein Ordner; nichts angelegt" >&2; exit 2
fi
case "$B/" in
  "$ROOT"/*|"$MAIN"/*) echo "BENCH=$B darf nicht im Repo $MAIN liegen; nichts angelegt" >&2; exit 2 ;;
esac
# Lesesperre (README, Abschnitt „Lesesperre"): eine Deny-Regel schlägt jede Allow-Regel und kennt
# keine Ausnahme, also darf der eigene Workspace unter keinem gesperrten Ordner liegen. Gruppe
# py (pip) und dl (DMVC) laufen je für sich nacheinander (flock), die andere Gruppe ist gesperrt.
case $REPO in
  py-*) GROUP=py; OTHER=dl ;;
  dl-*) GROUP=dl; OTHER=py ;;
  *) echo "unbekanntes Repo: $REPO" >&2; exit 2 ;;
esac
case $TOOL in
  cr|crc|crx|eng|sp|dr|drnc) ;;
  crb)
    # Stufe aus LEVEL; Name <repo>-crb-<stufe>-<nr>. Geprüft vor dem ersten mkdir.
    LEVEL=${LEVEL:-medium}
    case $LEVEL in
      low|medium|high) ;;
      *) echo "LEVEL=$LEVEL: erlaubt sind low|medium|high; nichts angelegt" >&2; exit 2 ;;
    esac
    # review_kit.py plan braucht einen Bereich; ein Pfad hat keinen.
    case $REPO in
      *-path) echo "crb nur für Bereiche (py-diff, dl-diff, py-c*), nicht für $REPO; nichts angelegt" >&2; exit 2 ;;
    esac
    NAME=$REPO-$TOOL-$LEVEL-$N ;;
  *) echo "unbekanntes Werkzeug: $TOOL" >&2; exit 2 ;;
esac
EXTRA=()
OUT=$B/out; mkdir -p "$OUT" "$B/work/$GROUP" "$B/work/$OTHER"
exec 9> "$B/work/$GROUP.lock"
flock 9
rm -rf "${B:?}/work/${GROUP:?}"/*   # Reste abgebrochener Läufe derselben Gruppe
W=$B/work/$GROUP/$NAME
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
  crb) PROMPT="/code-review $LEVEL --max-findings all $TARGET"
       # Block aus review_kit.py (nicht counterparts.py): Plan und Gegenstellen im Workspace, die
       # Skill wird nicht kopiert. Danach Laufordner und Refs weg, der Reviewer sieht beides nicht.
       KIT=$ROOT/skills/deep-review/scripts/review_kit.py
       RUN=$(python3 -I "$KIT" plan --repo "$W" --range "$TARGET" --split-at 100000 | sed -n '1s/^Lauf: *//p')
       if [ -z "$RUN" ] || ! python3 -I "$KIT" counterparts --repo "$W" --run "$RUN" >&2 \
          || [ ! -f "$W/.skills/cache/deep-review/$RUN/packets/p1.md" ]; then
         echo "$NAME: review_kit.py plan/counterparts gescheitert" >&2
         python3 -I "$KIT" cleanup --repo "$W" ${RUN:+--run "$RUN"} >&2 || true
         rm -rf "$W"; exit 1
       fi
       cp "$W/.skills/cache/deep-review/$RUN/packets/p1.md" "$OUT/$NAME.ctx.md"
       python3 -I "$KIT" cleanup --repo "$W" --run "$RUN" >&2
       rm -rf "$W/.skills"
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
    case $REPO in
      *-path) PROMPT="Prüf die Pfade $TARGET mit deep-review." ;;
      *) PROMPT="Review $TARGET mit deep-review." ;;
    esac
    # drnc: ohne Gegenstellen-Block. Schritt 3 läuft trotzdem, er baut die Paket-Bereiche.
    [ "$TOOL" = drnc ] && PROMPT="$PROMPT Führe Schritt 3 (counterparts) nur für die Paket-Bereiche aus: gib dem Reviewer den Block aus packets/<id>.md nicht mit und lies ihn nicht."
    ;;
  *) echo "unbekanntes Werkzeug: $TOOL" >&2; exit 2 ;;
esac

# Gesperrt für Read/Grep/Glob (//pfad = absolut): System-Python, Caches und Nutzer-Installs
# (installiertes pip), Upstream-Klone, gebaute Repos, Ausgaben früherer Läufe, Workspaces der
# anderen Gruppe, Paket-Patches von build.sh, dieses Repo (seeds.py, truth.json, Berichte) und
# die Transkripte anderer Sitzungen.
P="/$B"
DENY=()
deny() { DENY+=("Read($1)" "Grep($1)" "Glob($1)"); }
for d in //usr //opt "/$HOME/.cache" "/$HOME/.local" \
         "$P/pip-up" "$P/dmvc-up" "$P/repos" "$P/out" "$P/work/$OTHER" "/$ROOT" "/$MAIN"; do
  deny "$d/**"
done
deny "$P/*.patch"
# Transkripte: Claude Code legt je Arbeitsordner $CFG/projects/<ordner> an (jedes Zeichen außer
# A-Z, a-z, 0-9 wird '-') und dort zu große Werkzeugausgaben unter <sitzung>/tool-results/ ab. Der
# eigene Ordner bleibt lesbar, damit der Lauf seine eigenen tool-results liest; gesperrt sind alle
# anderen, die beim Start da sind, und im eigenen die Einträge früherer Läufe gleichen Namens.
# Ordner, die erst während des Laufs entstehen, sind nicht gesperrt (README).
CFG=$(readlink -m -- "${CLAUDE_CONFIG_DIR:-$HOME/.claude}")
OWN=$(printf %s "$W" | sed 's/[^A-Za-z0-9]/-/g')
PROJ=$CFG/projects/$OWN
OLD=()
shopt -s nullglob dotglob
for d in "$CFG/projects"/*; do
  if [ "${d##*/}" != "$OWN" ]; then
    deny "/$d/**"
    continue
  fi
  for e in "$d"/*; do
    OLD+=("${e##*/}")
    if [ -d "$e" ]; then deny "/$e/**"; else deny "/$e"; fi
  done
done
shopt -u nullglob dotglob
# Mit eigenem CLAUDE_CONFIG_DIR liegen die Transkripte unter ~/.claude/projects nicht im Weg.
[ "$CFG" != "$(readlink -m -- "$HOME/.claude")" ] && deny "/$HOME/.claude/projects/**"
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
# Ein Pfad zählt nur ganz: danach '/' oder ein Zeichen, das keinen Namen fortsetzt, sonst passt
# $ROOT=/x/repo auch auf ein $BENCH=/x/repo-bench daneben. Pfade im eigenen Projektordner (die
# tool-results dieses Laufs) zählen nicht, die Einträge früherer Läufe darin schon.
# shellcheck disable=SC2016  # Python-Quelltext, keine Shell-Variablen
PROBE_PY='
import re, sys
own, projects, b, other, root, main, *old = sys.argv[1:]
names = sys.stdin.buffer.read().decode("utf-8", "replace").split("\0")
text = "\n".join(open(n, encoding="utf-8", errors="replace").read() for n in names if n)
END = r"(?![\w.-])"
counts = {}
def count(label, pattern):
    n =len(re.findall(pattern, text))
    if n:
        counts[label] = counts.get(label, 0) + n
for e in old:
    count(f"{own}/{e}", re.escape(f"{own}/{e}") + END)
text = re.sub(re.escape(own) + r"(?:/[^\s\"\x27\\]*)?" + END,
              lambda m: m[0] if "/.." in m[0] else "", text)
for s in ("pip-up", "dmvc-up", "repos/py-", "repos/dl-"):
    count(s, re.escape(s))
for p in dict.fromkeys((f"{b}/repos", f"{b}/out", f"{b}/work/{other}", f"{b}/c1.patch",
                        f"{b}/c2.patch", f"{b}/c3.patch", root, main, projects)):
    count(p, re.escape(p) + END)
for label in sorted(counts):
    print(f"{counts[label]:7d} {label}")
'
if [ -d "$PROJ" ]; then
  find "$PROJ" -name '*.jsonl' -newer "$STAMP" -print0 2>/dev/null \
    | python3 -I -c "$PROBE_PY" "$PROJ" "$CFG/projects" "$B" "$OTHER" "$ROOT" "$MAIN" ${OLD[@]+"${OLD[@]}"} \
    > "$OUT/$NAME.probe.txt"
  if [ "${PIPESTATUS[1]}" -eq 0 ]; then
    PROBE=$(awk '{s+=$1} END {print s+0}' "$OUT/$NAME.probe.txt")
  else
    PROBE=fehler   # Probe selbst gescheitert: Transkript von Hand lesen
  fi
else
  PROBE=n/a
fi
rm -f "$STAMP"
echo "$NAME exit=$EC secs=$((END-START)) cost/turns/err=$COST probe=$PROBE" >> "$OUT/status.txt"
rm -rf "$W"
