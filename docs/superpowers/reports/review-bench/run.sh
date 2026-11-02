#!/bin/bash
# run.sh <repo> <tool> <run-nr>   repo: py-diff|py-path|dl-diff|dl-path|py-c1..3   tool: cr|crc|crx|eng|sp
set -uo pipefail
B=${BENCH:?BENCH auf das Arbeitsverzeichnis setzen}
HERE=$(dirname "$(readlink -f "$0")")
REPO=$1; TOOL=$2; N=$3
NAME=$REPO-$TOOL-$N
EXTRA=()
W=$B/work/$NAME
OUT=$B/out; mkdir -p $OUT $B/work
rm -rf $W; git clone -q $B/repos/$REPO $W
git -C $W fetch -q --tags
BASE=$(git -C $W rev-parse --verify -q base || true)
HEAD=$(git -C $W rev-parse HEAD)
case $REPO in
  py-path) TARGET="src/pip/_internal/req src/pip/_internal/operations" ;;
  dl-path) TARGET="sources/MVCFramework.JWT.RefreshToken.pas sources/MVCFramework.Middleware.RangeMedia.pas sources/MVCFramework.Middleware.OIDC.pas sources/MVCFramework.OIDC.JWKS.pas sources/MVCFramework.Serializer.CSV.pas sources/MVCFramework.SSE.Writer.pas sources/MVCFramework.JWT.RSA.pas" ;;
  py-c*) TARGET="mid..HEAD" ;;
  *) TARGET="base..HEAD" ;;
esac

case $TOOL in
  cr)  PROMPT="/code-review --max-findings all $TARGET" ;;
  crc) PROMPT="/code-review --max-findings all $TARGET"
       EXTRA=(--append-system-prompt "In every review, for each changed line, look up the counterpart it calls or that calls it - including vendored libraries, base classes and framework code outside the diff - and check the contract the change relies on: which exceptions the callee raises, what it returns for edge cases (empty, None, zero), who owns and frees objects, and what a flag or parameter does downstream. Report a finding when the changed code violates that contract.") ;;
  crx) PROMPT="/code-review --max-findings all $TARGET"
       python3 -I $HERE/counterparts.py $W $TARGET --root src --max-bytes 60000 > $OUT/$NAME.ctx.md
       EXTRA=(--append-system-prompt "Below is a mechanically collected list of counterparts for the changed lines of this range: for each changed call the definition it reaches (including vendored code), the exceptions that definition raises, and where changed keyword arguments flow and which conditions test them. It was produced by a script for every changed call site, not chosen by suspicion. Pass it unchanged to every reviewer subagent you start and use it to check the changed code against the contracts it relies on.

$(cat $OUT/$NAME.ctx.md)") ;;
  eng) PROMPT="/engineering:code-review $TARGET" ;;
  sp)
    mkdir -p $W/.claude/skills
    cp -r $B/superpowers/skills/requesting-code-review $W/.claude/skills/
    echo ".claude/" >> $W/.git/info/exclude
    PROMPT="/requesting-code-review Review the change base..HEAD of this repository. BASE_SHA: $BASE HEAD_SHA: $HEAD. DESCRIPTION and PLAN_OR_REQUIREMENTS: the commit message of HEAD (git log -1 HEAD). When the reviewer returns, print its complete list of issues verbatim, each with file:line." ;;
esac

START=$(date +%s)
( cd $W && timeout 1800 claude -p "$PROMPT" "${EXTRA[@]}" --output-format json \
    --allowedTools "Bash(git:*)" Read Grep Glob \
    --disallowedTools "Read(//usr/**)" "Grep(//usr/**)" "Glob(//usr/**)" \
      "Read(//opt/**)" "Grep(//opt/**)" "Glob(//opt/**)" \
      "Read(//root/.cache/**)" "Read(/$B/pip-up/**)" "Read(/$B/dmvc-up/**)" "Grep(/$B/pip-up/**)" "Grep(/$B/dmvc-up/**)" "Read(/$B/repos/**)" "Bash(git -C:*)" "Bash(git diff --no-index:*)" \
    > $OUT/$NAME.json 2> $OUT/$NAME.err )
EC=$?
END=$(date +%s)
COST=$(python3 -c "import json;d=json.load(open('$OUT/$NAME.json'));print(d.get('total_cost_usd'), d.get('num_turns'), d.get('is_error'))" 2>/dev/null || echo "parse-fail")
echo "$NAME exit=$EC secs=$((END-START)) cost/turns/err=$COST" >> $OUT/status.txt
rm -rf $W
