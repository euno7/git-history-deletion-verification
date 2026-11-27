#!/usr/bin/env bash
# Compare two records made by record_baseline.sh (before vs after rewrite).
# Usage: scripts/verify/compare_baseline.sh <before-dir> <after-dir>
set -uo pipefail
B="$1"; A="$2"
d() { command diff -u "$@" >/dev/null && echo "SAME" || { echo "DIFFERENT"; command diff -u "$@" | head -40; }; }
echo "== branch commit counts / merge counts";  d "$B/branch_counts.tsv" "$A/branch_counts.tsv"
echo "== release flow (version..develop counts)"; d "$B/release_flow.txt" "$A/release_flow.txt"
for f in "$B"/log_*; do n=$(basename "$f"); echo "== subjects $n"; d "$f" "$A/$n"; done
echo "== subjects per branch"
for f in "$B"/subjects/*; do n=$(basename "$f"); printf '  %-28s ' "$n"; command diff -q "$f" "$A/subjects/$n" >/dev/null && echo SAME || echo DIFFERENT; done
echo "== merge-bases (by subject|date; SHAs are expected to change)"
d <(cut -f1,2,4 "$B/merge_bases.tsv") <(cut -f1,2,4 "$A/merge_bases.tsv")
echo "== merge structure (subject|date|parent count)"; d "$B/merges.txt" "$A/merges.txt"
echo "== tree diff --stat between branches"; d "$B/tree_diffs.txt" "$A/tree_diffs.txt"
echo "== tags (type / target type / subject)"; d "$B/tags.txt" "$A/tags.txt"
echo "== signatures (%G? counts)"; echo "before:"; cat "$B/signatures.txt"; echo "after:"; cat "$A/signatures.txt"
