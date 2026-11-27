#!/usr/bin/env bash
# Revised purge procedure (see report/runbook-revised.*.md). Each phase is a
# separate sub-command so a human can review between phases.
#
# Usage: scripts/purge/purge_revised.sh <phase> [workdir]
#   prepare : export protection, snapshot remote refs, take a backup mirror
#   rewrite : fresh mirror clone + one filter-repo run (--sensitive-data-removal)
#   review  : scanners + direct value search + per-branch diff summary
#   push    : check nothing moved on the remote, lift protection, push
#             branches/tags with explicit refspecs, restore + compare protection
#   after   : fresh clone from GitHub and re-scan; print data for GitHub Support
#
# Inputs: replacements file and path list are generated from planted.json for
# this sandbox; in real use, write them by hand (see the runbook).
set -euo pipefail
PHASE="$1"; WORK="${2:-$HOME/purge-verify-work}"
REPO="${REPO:-euno7/git-history-deletion-verification}"
URL="${URL:-git@github.com:$REPO.git}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
R="$WORK/revised"; mkdir -p "$R"
M="$R/mirror.git"
LOG="$R/log.txt"
GL_CONFIG="$HERE/gitleaks/gitleaks.toml"
REMOVE_PATHS=(.env certs/server.fakekey assets/model.bin data/fixtures.json.gz)

stamp() { echo "### [$PHASE] $1 $(date -u +%FT%TZ)" | tee -a "$LOG"; }

case "$PHASE" in
prepare)
  stamp "start"
  "$HERE/purge/protection.sh" export "$R/protection"
  git ls-remote "$URL" > "$R/remote_refs_before.txt"
  rm -rf "$R/backup.git"; git clone -q --mirror "$URL" "$R/backup.git"
  (cd "$R" && tar czf backup-mirror.tgz backup.git)
  echo "backup: $R/backup-mirror.tgz ($(du -h "$R/backup-mirror.tgz" | cut -f1))"
  stamp "done" ;;

rewrite)
  stamp "start"
  rm -rf "$M"; git clone -q --mirror "$URL" "$M"
  python3 "$HERE/purge/make_replacements.py" --mode revised --out "$R/replacements.txt"
  args=(); for p in "${REMOVE_PATHS[@]}"; do args+=(--path "$p"); done
  t0=$(date +%s)
  (cd "$M" && git filter-repo --sensitive-data-removal \
      --prune-empty never \
      --replace-text "$R/replacements.txt" --invert-paths "${args[@]}") 2>&1 | tee -a "$LOG"
  echo "filter-repo elapsed: $(( $(date +%s) - t0 ))s" | tee -a "$LOG"
  rm -f "$R/replacements.txt"
  cp -r "$M/filter-repo" "$R/filter-repo-output"
  echo "remote after rewrite: $(git -C "$M" remote -v | head -1 || true)"
  stamp "done" ;;

review)
  stamp "start"
  echo "== gitleaks (custom rules, branches+tags)"
  gitleaks git --config "$GL_CONFIG" --log-opts="--branches --tags" --redact --no-banner "$M" 2>&1 | tail -2 || true
  echo "== direct value search (branches+tags)"
  python3 "$HERE/verify/scan_values.py" "$M" --refs "refs/heads refs/tags" | sed -n '/== reachable/,$p'
  echo "== per-branch diff old tip -> new tip (files)"
  while read -r old new ref; do
    [ "$new" = "0000000000000000000000000000000000000000" ] && { echo "$ref: REMOVED"; continue; }
    case "$ref" in refs/heads/*|refs/tags/*) ;; *) continue;; esac
    git -C "$M" cat-file -e "$old" 2>/dev/null || git -C "$M" fetch -q "$R/backup.git" "$old" 2>/dev/null || true
    echo "$ref: $(git -C "$M" diff --name-only "$old" "$new" 2>/dev/null | tr '\n' ' ')"
  done < <(tail -n +2 "$R/filter-repo-output/ref-map")
  echo "== lines added by the rewrite at the develop tip (review these by eye)"
  old=$(awk '$3=="refs/heads/develop"{print $1}' "$R/filter-repo-output/ref-map")
  # show only the new (+) side; removed lines may contain the secret itself
  git -C "$M" diff -U0 "$old" refs/heads/develop -- . ':!*.bin' ':!*.gz' | grep -E '^(\+\+\+ |\+[^+])' | head -40
  echo "removed lines: $(git -C "$M" diff -U0 "$old" refs/heads/develop | grep -c '^-[^-]' || true) (not shown)"
  stamp "done" ;;

push)
  stamp "start"
  git ls-remote "$URL" > "$R/remote_refs_now.txt"
  if ! command diff <(grep -v 'refs/pull/' "$R/remote_refs_before.txt") <(grep -v 'refs/pull/' "$R/remote_refs_now.txt"); then
    echo "ABORT: remote branches/tags changed since prepare (freeze broken). Re-run rewrite." | tee -a "$LOG"; exit 1
  fi
  "$HERE/purge/protection.sh" lift "$R/protection"
  t0=$(date +%s)
  git -C "$M" push --force "$URL" 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*' 2>&1 | grep -v '^remote: *$' | tee -a "$LOG" || true
  # refs that filter-repo removed entirely
  dels=$(awk 'NR>1 && $2=="0000000000000000000000000000000000000000" && $3 ~ /^refs\/(heads|tags)\// {print ":"$3}' "$R/filter-repo-output/ref-map")
  [ -n "$dels" ] && git -C "$M" push "$URL" $dels 2>&1 | tee -a "$LOG"
  echo "push elapsed: $(( $(date +%s) - t0 ))s" | tee -a "$LOG"
  "$HERE/purge/protection.sh" restore "$R/protection"
  "$HERE/purge/protection.sh" compare "$R/protection" | tee -a "$LOG"
  stamp "done" ;;

after)
  stamp "start"
  rm -rf "$R/after.git"; git clone -q --mirror "$URL" "$R/after.git"
  echo "== branches/tags on GitHub"
  gitleaks git --config "$GL_CONFIG" --log-opts="--branches --tags" --redact --no-banner "$R/after.git" 2>&1 | tail -1 || true
  python3 "$HERE/verify/scan_values.py" "$R/after.git" --refs "refs/heads refs/tags" | sed -n '/== reachable/,$p'
  echo "== refs/pull/* on GitHub (cannot be fixed by us)"
  python3 "$HERE/verify/scan_values.py" "$R/after.git" --refs "refs/pull" | sed -n '/== reachable/,$p' | cut -c1-80
  echo "== data for a GitHub Support request"
  echo "repository: $REPO"
  echo "affected PRs: $(grep -c '^refs/pull/.*/head$' "$R/filter-repo-output/changed-refs" || true) (from changed-refs)"
  echo "first changed commits:"; cat "$R/filter-repo-output/first-changed-commits"
  stamp "done" ;;
*) echo "unknown phase"; exit 2 ;;
esac
