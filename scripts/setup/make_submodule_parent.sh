#!/usr/bin/env bash
# Create a LOCAL-ONLY parent repository that pins the sandbox as a submodule
# at a fixed commit SHA (models a monorepo that uses submodules). Never pushed.
# Usage: scripts/setup/make_submodule_parent.sh [workdir] [ref-to-pin]
set -euo pipefail
WORK="${1:-$HOME/purge-verify-work}"
PIN_REF="${2:-version/1.1}"
URL="${SUBMODULE_URL:-https://github.com/euno7/git-history-deletion-verification.git}"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME="Dev Alpha" GIT_AUTHOR_EMAIL="dev-alpha@users.noreply.example.invalid"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
P="$WORK/parent-mono"
rm -rf "$P"; mkdir -p "$P"; cd "$P"
git init -q -b main
echo "# Local parent repo (not pushed)" > README.md
git add README.md && git commit -qm "Initial parent commit"
git submodule add -q "$URL" libs/sandbox
PIN=$(git -C libs/sandbox rev-parse "origin/$PIN_REF")
git -C libs/sandbox checkout -q "$PIN"
git add libs/sandbox .gitmodules
git commit -qm "Pin sandbox submodule at $PIN_REF"
echo "parent repo: $P"
echo "pinned submodule commit: $PIN"
git submodule status
