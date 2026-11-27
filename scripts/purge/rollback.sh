#!/usr/bin/env bash
# Roll back: force-push the pre-rewrite backup mirror (branches + tags only).
# refs/pull/* cannot be pushed (GitHub rejects hidden refs); they were never changed.
# Usage: rollback.sh <backup-mirror.git> [remote-url]
set -euo pipefail
BK="$1"; URL="${2:-git@github.com:euno7/git-history-deletion-verification.git}"
git -C "$BK" push --force "$URL" 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*'
# delete branches that exist on the remote but not in the backup (created by the rewrite run)
for r in $(git ls-remote --heads "$URL" | awk '{print $2}'); do
  git -C "$BK" show-ref -q --verify "$r" || { echo "remote-only ref (left in place, review manually): $r"; }
done
