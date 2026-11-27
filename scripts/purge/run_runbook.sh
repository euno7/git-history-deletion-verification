#!/usr/bin/env bash
# Execute the ORIGINAL runbook one step at a time, logging command, output,
# exit code and elapsed time. Failures are recorded, not hidden.
# Usage: scripts/purge/run_runbook.sh <step> [workdir]
#   steps: 0-lift  1-clone  2a-replace  2b-invert  3-verify  4-push  5-restore
set -uo pipefail
STEP="$1"; WORK="${2:-$HOME/purge-verify-work}"
REPO="${REPO:-euno7/git-history-deletion-verification}"
OWNER=${REPO%%/*}; NAME=${REPO##*/}
HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$WORK/runbook-run"; LOG="$WORK/logs/runbook"; mkdir -p "$RUN" "$LOG"
BASE="$WORK/baseline"

run() {  # run <label> <command...>
  local label="$1"; shift
  local f="$LOG/$STEP.log"
  { echo "### [$label] $(date -u +%FT%TZ)"; echo "\$ $*"; } >> "$f"
  local t0=$(python3 -c 'import time;print(time.time())')
  "$@" >> "$f" 2>&1; local rc=$?
  local t1=$(python3 -c 'import time;print(time.time())')
  printf -- "--> exit=%s elapsed=%.2fs\n\n" "$rc" "$(echo "$t1 - $t0" | bc)" >> "$f"
  printf "[%s] exit=%s elapsed=%.2fs\n" "$label" "$rc" "$(echo "$t1 - $t0" | bc)"
  return $rc
}

case "$STEP" in
  0-lift)
    RS=$(jq -r '.[] | select(.name=="protect-develop") | .id' "$BASE/rulesets.json")
    run "delete main protection" gh api -X DELETE "repos/$REPO/branches/main/protection"
    run "disable develop ruleset" gh api -X PUT "repos/$REPO/rulesets/$RS" -f enforcement=disabled --jq .enforcement
    ;;
  1-clone)
    cd "$RUN" && rm -rf "$NAME.git"
    run "git clone --mirror" git clone --mirror "https://github.com/$OWNER/$NAME.git"
    run "refs fetched" git -C "$NAME.git" for-each-ref --format='%(refname)'
    ;;
  2a-replace)
    cd "$RUN/$NAME.git"
    python3 "$HERE/purge/make_replacements.py" --out "$RUN/replacements.txt" ${REPL_ARGS:-}
    run "filter-repo --replace-text" git filter-repo --replace-text ../replacements.txt
    ;;
  2b-invert)
    cd "$RUN/$NAME.git"
    run "filter-repo --invert-paths" git filter-repo --invert-paths --path .env --path certs/server.fakekey ${FR_EXTRA:-}
    ;;
  3-verify)
    cd "$RUN/$NAME.git"
    run "gitleaks detect" gitleaks detect --source . --log-opts="--all" --redact ${GL_EXTRA:-}
    ;;
  4-push)
    cd "$RUN/$NAME.git"
    run "remotes before push" git remote -v
    run "git push --force --mirror origin" git push --force --mirror origin
    ;;
  5-restore)
    RS=$(jq -r '.[] | select(.name=="protect-develop") | .id' "$BASE/rulesets.json")
    run "restore main protection" gh api -X PUT "repos/$REPO/branches/main/protection" --input "$WORK/restore_main_protection.json"
    run "restore main required signatures" gh api -X POST "repos/$REPO/branches/main/protection/required_signatures"
    run "enable develop ruleset" gh api -X PUT "repos/$REPO/rulesets/$RS" -f enforcement=active --jq .enforcement
    ;;
  *) echo "unknown step $STEP"; exit 2;;
esac
