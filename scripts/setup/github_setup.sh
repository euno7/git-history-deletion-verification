#!/usr/bin/env bash
# Push the sandbox to GitHub and create PRs, review comments, a Release,
# branch protection (main) and a ruleset (develop).
#
# Usage: scripts/setup/github_setup.sh [workdir]
# Requires: gh (logged in, admin on the repo), jq, python3.
set -euo pipefail

REPO="${REPO:-euno7/git-history-deletion-verification}"
WORK="${1:-$HOME/purge-verify-work}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PLANTED="$WORK/planted.json"
SANDBOX="$WORK/sandbox"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

val() { jq -r --arg k "$1" '.values[$k]' "$PLANTED"; }

echo "== phase A push (develop before PR merges + PR branches to be merged)"
PUSH_PHASE=A python3 "$HERE/build_sandbox.py" --workdir "$WORK" --no-build --push

gh api -X PATCH "repos/$REPO" -f default_branch=main >/dev/null

echo "== open the two PRs that will be merged"
M1=$(gh pr create -R "$REPO" --base develop --head feature/healthcheck \
  --title "Add deep health check" --body "Adds a deep health check and readiness probe.")
M2=$(gh pr create -R "$REPO" --base develop --head feature/logging \
  --title "Add logging setup" --body "Configures basic logging.")
echo "$M1"; echo "$M2"

echo "== phase B push (everything; develop now contains the merges)"
PUSH_PHASE=B python3 "$HERE/build_sandbox.py" --workdir "$WORK" --no-build --push
sleep 10
gh pr view -R "$REPO" "$M1" --json state,mergedAt
gh pr view -R "$REPO" "$M2" --json state,mergedAt

echo "== open PRs"
gh pr create -R "$REPO" --base develop --head feature/rate-limit \
  --title "Add rate limiter" --body "Adds a simple rate limiter. No config changes."
PRB_URL=$(gh pr create -R "$REPO" --base develop --head feature/metrics \
  --title "Add metrics exporter" \
  --body "Adds metrics exporter config.

For local testing use this dummy key: $(val PR_TEXT_KEY)")
echo "$PRB_URL"
gh pr create -R "$REPO" --base main --head docs/contributing \
  --title "Add contributing guide" --body "Docs only."

PRB=${PRB_URL##*/}
HEAD_SHA=$(gh api "repos/$REPO/pulls/$PRB" --jq .head.sha)
gh api "repos/$REPO/pulls/$PRB/comments" \
  -f body="Please do not hard-code this. Same value as in chat: $(val PR_TEXT_KEY)" \
  -f commit_id="$HEAD_SHA" -f path=config/metrics.py -F line=1 -f side=RIGHT --jq .html_url
gh pr review -R "$REPO" "$PRB" --comment -b "Review summary: key $(val PR_TEXT_KEY) must move to the environment."

echo "== release v1.1.0 with an attached config bundle"
ASSET_DIR=$(mktemp -d)
git -C "$SANDBOX" archive --format=tar.gz -o "$ASSET_DIR/config-bundle-1.1.0.tar.gz" v1.1.0 config
gh release create v1.1.0 -R "$REPO" --title "1.1.0" --notes "Dummy release 1.1.0" --verify-tag \
  "$ASSET_DIR/config-bundle-1.1.0.tar.gz"
gh release create v1.0.0 -R "$REPO" --title "1.0.0" --notes "Dummy release 1.0.0" --verify-tag

echo "== branch protection on main (classic)"
gh api -X PUT "repos/$REPO/branches/main/protection" --input - <<'JSON' >/dev/null
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": {"required_approving_review_count": 0},
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
gh api -X POST "repos/$REPO/branches/main/protection/required_signatures" >/dev/null

echo "== ruleset on develop"
gh api -X POST "repos/$REPO/rulesets" --input - <<'JSON' --jq '.id'
{
  "name": "protect-develop",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["refs/heads/develop"], "exclude": []}},
  "rules": [
    {"type": "non_fast_forward"},
    {"type": "deletion"},
    {"type": "required_signatures"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": false,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": false}}
  ]
}
JSON
echo "done"
