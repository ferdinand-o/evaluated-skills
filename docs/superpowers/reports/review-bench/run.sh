#!/bin/bash
# run.sh <repo> <tool> <run-nr>   repo: py-diff|py-path|dl-diff   tool: cr|eng|sp
set -uo pipefail
B=${BENCH:?BENCH auf das Arbeitsverzeichnis setzen}
REPO=$1; TOOL=$2; N=$3
NAME=$REPO-$TOOL-$N
W=$B/work/$NAME
OUT=$B/out; mkdir -p $OUT $B/work
rm -rf $W; git clone -q $B/repos/$REPO $W
git -C $W fetch -q --tags
BASE=$(git -C $W rev-parse --verify -q base || true)
HEAD=$(git -C $W rev-parse HEAD)
case $REPO in
  py-path) TARGET="src/pip/_internal/req src/pip/_internal/operations" ;;
  dl-path) TARGET="sources/MVCFramework.JWT.RefreshToken.pas sources/MVCFramework.Middleware.RangeMedia.pas sources/MVCFramework.Middleware.OIDC.pas sources/MVCFramework.OIDC.JWKS.pas sources/MVCFramework.Serializer.CSV.pas sources/MVCFramework.SSE.Writer.pas sources/MVCFramework.JWT.RSA.pas" ;;
  *) TARGET="base..HEAD" ;;
esac

case $TOOL in
  cr)  PROMPT="/code-review --max-findings all $TARGET" ;;
  eng) PROMPT="/engineering:code-review $TARGET" ;;
  sp)
    mkdir -p $W/.claude/skills
    cp -r $B/superpowers/skills/requesting-code-review $W/.claude/skills/
    echo ".claude/" >> $W/.git/info/exclude
    PROMPT="/requesting-code-review Review the change base..HEAD of this repository. BASE_SHA: $BASE HEAD_SHA: $HEAD. DESCRIPTION and PLAN_OR_REQUIREMENTS: the commit message of HEAD (git log -1 HEAD). When the reviewer returns, print its complete list of issues verbatim, each with file:line." ;;
esac

START=$(date +%s)
( cd $W && timeout 1800 claude -p "$PROMPT" --output-format json \
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
