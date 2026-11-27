#!/usr/bin/env bash
# Record the state of the repository before (or after) the history rewrite.
# Usage: scripts/baseline/record_baseline.sh <out-dir> [repo-dir]
#   repo-dir: a fresh clone (default: clones the remote into <out-dir>/clone)
# Output never contains secret values except the gitleaks report (redacted).
set -euo pipefail
REPO="${REPO:-euno7/git-history-deletion-verification}"
OUT="$1"
SRC="${2:-}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
mkdir -p "$OUT"
if [ -z "$SRC" ]; then
  SRC="$OUT/clone.git"
  rm -rf "$SRC"
  git clone -q --mirror "git@github.com:$REPO.git" "$SRC"
fi
ALLOWED="${ALLOWED_SIGNERS:-$HOME/purge-verify-work/keys/allowed_signers}"
g() { git -c gpg.ssh.allowedSignersFile="$ALLOWED" -C "$SRC" "$@"; }

g for-each-ref --format='%(objectname) %(objecttype) %(refname)' > "$OUT/refs.txt"

BRANCHES=$(g for-each-ref --format='%(refname:short)' refs/heads)
: > "$OUT/branch_counts.tsv"
mkdir -p "$OUT/subjects"
for b in $BRANCHES; do
  printf '%s\t%s\t%s\n' "$b" "$(g rev-list --count "$b")" "$(g rev-list --merges --count "$b")" >> "$OUT/branch_counts.tsv"
  g log --format='%s' "$b" > "$OUT/subjects/$(echo "$b" | tr '/' '_').txt"
done

# merge-base between interesting pairs (as subject lines, since SHAs change)
PAIRS="develop:main develop:version/1.1 develop:version/1.0 version/1.1:main version/1.0:main
feature/metrics:develop feature/rate-limit:develop docs/contributing:main stg:develop
hotfix/old-config:develop feature/legacy-export:develop feature/search:develop"
: > "$OUT/merge_bases.tsv"
for p in $PAIRS; do
  a=${p%%:*}; b=${p##*:}
  mb=$(g merge-base "$a" "$b")
  printf '%s\t%s\t%s\t%s\n' "$a" "$b" "$mb" "$(g log -1 --format='%s|%ad' --date=iso-strict "$mb")" >> "$OUT/merge_bases.tsv"
done

# release-flow view: version..develop
: > "$OUT/release_flow.txt"
for v in version/1.0 version/1.1; do
  f="$OUT/log_$(echo "$v" | tr '/' '_')..develop.txt"
  g log --format='%s' "$v..develop" > "$f"
  echo "$v..develop: $(wc -l < "$f" | tr -d ' ') commits" >> "$OUT/release_flow.txt"
done

# merge structure (first-parent graph shape by subject)
g log --branches --tags --merges --format='%s|%ad|parents=%p' --date=iso-strict | \
  awk -F'|' '{n=split($3,a," "); print $1"|"$2"|nparents="n}' | sort > "$OUT/merges.txt"

# tree diffs between branches
: > "$OUT/tree_diffs.txt"; : > "$OUT/trees.txt"
for p in "version/1.1 develop" "main version/1.1" "version/1.0 version/1.1" "main develop"; do
  set -- $p
  { echo "### $1..$2"; g diff --stat "$1" "$2" | tail -n 30; } >> "$OUT/tree_diffs.txt"
  printf '%s %s %s\n' "$1" "$2" "$(g rev-parse "$1^{tree}") $(g rev-parse "$2^{tree}")" >> "$OUT/trees.txt"
done

# tags (target subject + type)
g for-each-ref --format='%(refname:short) %(objecttype) %(*objecttype) %(subject)' refs/tags > "$OUT/tags.txt"

# signatures
g log --branches --tags --format='%G?' | sort | uniq -c > "$OUT/signatures.txt" || true

# GitHub settings (skip with SKIP_GH=1 when re-recording from a saved clone)
if [ -z "${SKIP_GH:-}" ]; then
gh api "repos/$REPO/branches/main/protection" > "$OUT/protection_main.json" 2>&1 || true
gh api "repos/$REPO/rulesets" > "$OUT/rulesets.json"
for id in $(jq -r '.[].id' "$OUT/rulesets.json"); do
  gh api "repos/$REPO/rulesets/$id" > "$OUT/ruleset_$id.json"
done
gh pr list -R "$REPO" --state all --json number,state,title,headRefName,baseRefName,headRefOid,mergeCommit,commits \
  > "$OUT/prs.json"
gh release list -R "$REPO" --json tagName,name,isDraft > "$OUT/releases.json"
fi

# commit / blob URLs for later 404 checks (all commits)
g rev-list --all | sed "s#^#https://github.com/$REPO/commit/#" > "$OUT/commit_urls.txt"

# old commits where files that held values exist (for raw/blob URL checks)
{
  for p in config/settings.py .env certs/server.fakekey config/database.py; do
    echo "$(g log -1 --format=%H --diff-filter=AM refs/heads/develop -- "$p") $p"
  done
  echo "$(g rev-parse refs/heads/main) config/settings.py"
  echo "$(g rev-parse refs/heads/stg) config/stg.py"
  echo "$(g rev-parse refs/heads/feature/legacy-export) config/export.py"
} > "$OUT/value_paths.txt"

# gitleaks (redacted)
gitleaks git --config "$HERE/gitleaks/gitleaks.toml" --log-opts="--all" --redact \
  --report-format json --report-path "$OUT/gitleaks.json" "$SRC" > "$OUT/gitleaks.log" 2>&1 || true
jq -r '.[] | [.RuleID, .File, .Commit] | @tsv' "$OUT/gitleaks.json" | sort > "$OUT/gitleaks_findings.tsv"
echo "recorded to $OUT ($(wc -l < "$OUT/gitleaks_findings.tsv" | tr -d ' ') gitleaks findings)"
