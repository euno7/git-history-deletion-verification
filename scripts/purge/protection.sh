#!/usr/bin/env bash
# Save / lift / restore branch protection (classic) and rulesets.
# Usage: protection.sh export|lift|restore|compare <dir>
#   export : save classic protection of every protected branch + all rulesets
#   lift   : delete classic protection, set rulesets to enforcement=disabled
#   restore: re-apply what export saved (classic: PUT + required_signatures)
#   compare: diff the live settings with the export
set -euo pipefail
CMD="$1"; DIR="$2"
REPO="${REPO:-euno7/git-history-deletion-verification}"
mkdir -p "$DIR"
shopt -s nullglob
to_put() { # convert GET protection JSON to the PUT body
  jq '{required_status_checks: (if .required_status_checks then {strict: .required_status_checks.strict, contexts: .required_status_checks.contexts} else null end),
       enforce_admins: .enforce_admins.enabled,
       required_pull_request_reviews: (if .required_pull_request_reviews then (.required_pull_request_reviews | {dismiss_stale_reviews, require_code_owner_reviews, required_approving_review_count, require_last_push_approval}) else null end),
       restrictions: null,
       required_linear_history: .required_linear_history.enabled,
       allow_force_pushes: .allow_force_pushes.enabled,
       allow_deletions: .allow_deletions.enabled,
       block_creations: .block_creations.enabled,
       required_conversation_resolution: .required_conversation_resolution.enabled,
       lock_branch: .lock_branch.enabled,
       allow_fork_syncing: .allow_fork_syncing.enabled}'
}
norm() { jq -S 'walk(if type=="object" then del(.url, .created_at, .updated_at, ._links) else . end)'; }
case "$CMD" in
  export)
    gh api "repos/$REPO/branches?protected=true&per_page=100" --jq '.[].name' > "$DIR/protected_branches.txt"
    while read -r b; do
      # branches covered only by a ruleset have no classic protection (404): skip them
      if out=$(gh api "repos/$REPO/branches/$b/protection" < /dev/null 2>/dev/null); then
        echo "$out" > "$DIR/classic_$(echo "$b" | tr / _).json"
      fi
    done < "$DIR/protected_branches.txt"
    gh api "repos/$REPO/rulesets" --jq '.[].id' > "$DIR/ruleset_ids.txt"
    while read -r id; do gh api "repos/$REPO/rulesets/$id" < /dev/null > "$DIR/ruleset_$id.json"; done < "$DIR/ruleset_ids.txt"
    echo "exported: $(wc -l < "$DIR/protected_branches.txt" | tr -d ' ') classic, $(wc -l < "$DIR/ruleset_ids.txt" | tr -d ' ') rulesets" ;;
  lift)
    for f in "$DIR"/classic_*.json; do
      b=$(jq -r '.url' "$f" | sed 's#.*/branches/##; s#/protection$##')
      gh api -X DELETE "repos/$REPO/branches/$b/protection" && echo "lifted classic: $b"
    done
    while read -r id; do
      gh api -X PUT "repos/$REPO/rulesets/$id" -f enforcement=disabled < /dev/null --jq '"ruleset \(.id) -> \(.enforcement)"'
    done < "$DIR/ruleset_ids.txt" ;;
  restore)
    for f in "$DIR"/classic_*.json; do
      b=$(jq -r '.url' "$f" | sed 's#.*/branches/##; s#/protection$##')
      to_put < "$f" | gh api -X PUT "repos/$REPO/branches/$b/protection" --input - >/dev/null
      if [ "$(jq -r '.required_signatures.enabled' "$f")" = "true" ]; then
        gh api -X POST "repos/$REPO/branches/$b/protection/required_signatures" >/dev/null
      fi
      echo "restored classic: $b"
    done
    while read -r id; do
      enf=$(jq -r .enforcement "$DIR/ruleset_$id.json")
      gh api -X PUT "repos/$REPO/rulesets/$id" -f enforcement="$enf" < /dev/null --jq '"ruleset \(.id) -> \(.enforcement)"'
    done < "$DIR/ruleset_ids.txt" ;;
  compare)
    rc=0
    for f in "$DIR"/classic_*.json; do
      b=$(jq -r '.url' "$f" | sed 's#.*/branches/##; s#/protection$##')
      if command diff <(norm < "$f") <(gh api "repos/$REPO/branches/$b/protection" | norm) >/dev/null; then echo "classic $b: SAME"; else echo "classic $b: DIFFERENT"; rc=1; fi
    done
    while read -r id; do
      if command diff <(norm < "$DIR/ruleset_$id.json") <(gh api "repos/$REPO/rulesets/$id" < /dev/null | norm) >/dev/null; then echo "ruleset $id: SAME"; else echo "ruleset $id: DIFFERENT"; rc=1; fi
    done < "$DIR/ruleset_ids.txt"
    exit $rc ;;
esac
