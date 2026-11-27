#!/usr/bin/env bash
# Check, without authentication, whether old commit / blob / compare URLs are
# still served by GitHub. Prints HTTP status per URL kind.
# Usage: scripts/verify/check_urls.sh <out.tsv> <baseline-dir> [sample-size]
set -uo pipefail
OUT="$1"; BASE="$2"; N="${3:-15}"
REPO="${REPO:-euno7/git-history-deletion-verification}"
UA="purge-verify-check"
: > "$OUT"
probe() { # kind url
  code=$(curl -s -o /dev/null -w '%{http_code}' -A "$UA" "$2")
  printf '%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$1" "$code" "$2" >> "$OUT"
}
# old commits (sample) + every old branch tip
OLD=$(awk '$2=="commit" && $3 ~ /^refs\/(heads|tags)/ {print $1}' "$BASE/refs.txt"; head -n "$N" "$BASE/commit_urls.txt" | sed 's#.*/##')
for sha in $(echo "$OLD" | sort -u); do
  probe commit "https://github.com/$REPO/commit/$sha"
  probe patch  "https://github.com/$REPO/commit/$sha.patch"
done
# raw file views at old commits for files that held values
while read -r sha path; do
  probe raw  "https://raw.githubusercontent.com/$REPO/$sha/$path"
  probe blob "https://github.com/$REPO/blob/$sha/$path"
done < "$BASE/value_paths.txt"
# API (unauthenticated) for an old commit
for sha in $(awk '$3=="refs/heads/main"{print $1}' "$BASE/refs.txt"); do
  probe api "https://api.github.com/repos/$REPO/commits/$sha"
done
cut -f2,3 "$OUT" | sort | uniq -c
