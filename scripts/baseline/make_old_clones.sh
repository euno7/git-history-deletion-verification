#!/usr/bin/env bash
# Make two "old clones" before the rewrite, to replay later what a developer
# with a stale clone would do.
#   old-clone-a: plain clone with local branches for every remote branch
#   old-clone-b: clone with an unpushed local commit (holds a new fake value,
#                recorded into planted.json as UNPUSHED_KEY)
# Usage: scripts/baseline/make_old_clones.sh [workdir]
set -euo pipefail
WORK="${1:-$HOME/purge-verify-work}"
URL="${CLONE_URL:-git@github.com:euno7/git-history-deletion-verification.git}"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME="Dev Beta" GIT_AUTHOR_EMAIL="dev-beta@users.noreply.example.invalid"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
D="$WORK/old-clones"; rm -rf "$D"; mkdir -p "$D"

git clone -q "$URL" "$D/old-clone-a"
for b in $(git -C "$D/old-clone-a" for-each-ref --format='%(refname:lstrip=3)' refs/remotes/origin | grep -v '^HEAD$'); do
  git -C "$D/old-clone-a" branch -q -f --track "$b" "origin/$b" 2>/dev/null || true
done

git clone -q "$URL" "$D/old-clone-b"
cd "$D/old-clone-b"
git checkout -q -b feature/unpushed-work origin/develop
KEY=$(python3 -c "import secrets,string;a=string.ascii_letters+string.digits;print(\"FAKESECRET_\"+\"\".join(secrets.choice(a) for _ in range(32)))")
printf 'CACHE_KEY = "%s"\n' "$KEY" > config/cache.py
git add config/cache.py && git commit -qm "WIP: cache config (unpushed)"
echo "local work in progress" >> docs/api.md
git checkout -q develop
git commit -qam "Tweak API docs (unpushed, on develop)"
python3 - "$WORK/planted.json" "$KEY" <<'PY'
import json, sys
p, k = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d["values"]["UNPUSHED_KEY"] = k
d["items"] = [i for i in d["items"] if i["id"] != "UNPUSHED_KEY"]
d["items"].append({"id": "UNPUSHED_KEY", "kind": "unpushed local commit in an old clone",
                   "where": ["old-clone-b feature/unpushed-work config/cache.py"]})
json.dump(d, open(p, "w"), indent=2)
PY
echo "old clones in $D"
git -C "$D/old-clone-b" log --oneline -3 --all --not --remotes
