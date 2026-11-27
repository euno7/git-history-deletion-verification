# Purging secrets from git history: revised runbook

[日本語](runbook-revised.ja.md)

This runbook fixes the problems found when the original procedure was tested on a dummy repository (see [verification-report.en.md](verification-report.en.md)). `scripts/purge/purge_revised.sh` and `scripts/purge/protection.sh` implement its core steps.

> **Prerequisite: the secrets have already been rotated.** Even after a rewrite, the values can survive in old commits on GitHub, in forks, in people's clones and in CI logs. A history purge does not replace rotation.

## 0. What changed from the original runbook

| Original | Revised | Why (what the verification showed) |
|---|---|---|
| `git filter-repo --replace-text ...`, then a separate `--invert-paths ...` run | **One** run with `--sensitive-data-removal --prune-empty never` | `origin` is kept. `first-changed-commits` is written. Empty commits are kept, so commit counts don't change |
| List only the raw values in `replacements.txt` | Also list encoded forms (base64, URL-encoded and so on). Write short values as context-anchored regexes | Prevents leftovers, and prevents collateral damage to function names and the like |
| — | Remove binary and compressed files that contain values | `--replace-text` doesn't touch binary blobs |
| `gitleaks detect` (default rules) | `gitleaks git --config <custom rules>`, plus a direct search for the values | The default rules don't recognize custom-format values |
| `git push --force --mirror origin` | `git push --force <url> 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*'`; delete removed branches separately | `--mirror` gets `refs/pull/*` rejected, which makes the push exit 1. It also deletes branches created after the clone |
| "Lift branch protection temporarily" | Export classic protection and rulesets as JSON, lift and restore them with `gh api`, and confirm there's no diff | The signed-commits rule has to be lifted too, and there has to be a way to confirm the restore |
| — | Right before the push, check that no remote ref has changed | A broken freeze must not overwrite someone else's push |
| — | Take a backup before the rewrite and keep a rollback procedure | To restore the original if something goes wrong (verified) |

## 1. Preparation (days before)

1. **Rotate** every affected value and replace it with a new one.
2. **Inventory** the values: run gitleaks with custom rules and a direct value search on the pre-rewrite repository, and write down every value found. Keep the list outside the repository with permissions 600.
   - Look for encoded forms (base64, URL-encoded, JSON- or YAML-escaped), not just raw values.
   - Look for binary and compressed files that contain values; gitleaks doesn't scan inside them.
   - For short values such as `password`, find every place they appear.
3. **Validate the scanner rules**: confirm that the custom rules detect every known value in the pre-rewrite history. **Zero findings means the rules are wrong.**
4. **Write the replacement list and the path list** (outside the repository):

   ```text
   <value>==>REMOVED_SECRET
   <base64 of value>==>REMOVED_SECRET
   <URL-encoded value>==>REMOVED_SECRET
   regex:(ADMIN_PASSWORD\s*=\s*)"<short value>"==>\1"REMOVED_SECRET"
   ```

   Files to remove entirely: `.env`, key files, and binary or compressed files that contain values.

5. **Dry run**: on a copy of the mirror, run steps 3–4 below (rewrite and review) and time them. Don't push.
6. **Open PRs**: merge or close as many as you can. GitHub recommends this because comments on old diffs can be lost.
7. **Check what else is affected**:
   - Forks: `gh api repos/<owner>/<repo>/forks --paginate`
   - Repositories that use this one as a submodule
   - Anything that records SHAs (deploy records, release notes, issue trackers)
8. **Announce** the freeze window and the follow-up steps to developers ([developer-notice.en.md](developer-notice.en.md)).
9. **Disable workflows that print values to their logs** (`gh workflow disable <name>`). Every push would otherwise write the value into Actions logs again.

## 2. Run it (the freeze starts)

Plan a 30–60 minute freeze even for a small repository. The machine work takes about a minute, but the human review takes longer.

```bash
# 2-1. protection settings + remote ref snapshot + backup mirror
scripts/purge/purge_revised.sh prepare
#   = protection.sh export <dir>            (classic protection and rulesets as JSON)
#   = git ls-remote <url> > remote_refs_before.txt
#   = git clone --mirror <url> backup.git && tar czf backup-mirror.tgz backup.git

# 2-2. rewrite (one filter-repo run)
scripts/purge/purge_revised.sh rewrite
#   = git clone --mirror <url> mirror.git
#     cd mirror.git
#     git filter-repo --sensitive-data-removal --prune-empty never \
#       --replace-text ../replacements.txt \
#       --invert-paths --path .env --path <key file> --path <binary> ...
#   (delete replacements.txt afterwards)
```

`--sensitive-data-removal` requires git filter-repo 2.47 or later. Record the "First Changed Commit(s)" it prints.

## 3. Review (before pushing)

```bash
scripts/purge/purge_revised.sh review
```

Do not push until all of these hold:

- [ ] gitleaks with the custom rules (`--log-opts="--branches --tags"`) reports 0 findings
- [ ] The direct value search (`scripts/verify/scan_values.py`: raw, base64, URL-encoded, inside gzip) finds 0 values reachable from branches and tags
- [ ] For every branch and tag, only the expected files changed
- [ ] On the main branch tips, you checked the **added lines** by eye and no unrelated code changed. Never print the removed lines; they contain the values
- [ ] Tests pass on the rewritten tips
- [ ] Compared with the pre-rewrite state, per-branch commit counts, subjects, the count and subjects of `version..develop`, merge-bases and merge structure all match (`scripts/baseline/record_baseline.sh` and `scripts/verify/compare_baseline.sh`)

## 4. Push

```bash
scripts/purge/purge_revised.sh push
#   1. abort if branches/tags on the remote changed since "prepare"
#   2. protection.sh lift      (DELETE classic protection, rulesets -> disabled)
#   3. git push --force <url> 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*'
#   4. delete refs that filter-repo removed (ref-map rows whose new SHA is all zeros)
#   5. protection.sh restore   (PUT classic protection + required_signatures, rulesets -> active)
#   6. protection.sh compare   (must print SAME for every item)
```

- Don't use `--mirror`. GitHub rejects updates to `refs/pull/*` as hidden refs, and `--mirror` deletes branches created on the remote after the clone.
- If step 1 aborts, the freeze was broken. Start again from step 2-2.

## 5. Afterwards

```bash
scripts/purge/purge_revised.sh after
#   fresh mirror clone from GitHub -> gitleaks + direct search on branches/tags
#   lists what still remains under refs/pull/*
#   prints the data for a GitHub Support request
```

1. **Protection restored**: `protection.sh compare` reports SAME for every item.
2. **Workflows that print values**: keep them disabled, or fix them before re-enabling.
3. **PR descriptions and comments**: edit descriptions and delete comments that contain values. **The edit history keeps the original text**, so open the "edited" menu in the web UI and delete those revisions.
4. **Actions logs**: delete runs whose logs contain values with `gh run delete <id>`.
5. **Release attachments**: delete attachments that contain values and upload regenerated ones.
6. **Submodule pins**: in repositories that use this one, re-pin to the new SHA using `commit-map`.
7. **SHA records**: store `commit-map`, `ref-map` and `first-changed-commits` somewhere safe and internal. They hold no values, but they point to the old commits.
8. **Developers re-clone**: get a "done" from every developer ([developer-notice.en.md](developer-notice.en.md)).
9. **Restrict branch creation**: until everyone has re-cloned, consider a ruleset on `refs/heads/**` that restricts creation and force pushes. Pushes from old clones would otherwise bring the values back.
10. **GitHub Support request** (if needed):
    - GitHub only helps when rotating the credentials can't mitigate the risk.
    - Include the repository name, the number of affected PRs (`grep -c '^refs/pull/.*/head$' .git/filter-repo/changed-refs`) and the First Changed Commit(s).
    - Support removes cached views, removes or dereferences PR refs, and runs server-side GC.
    - Support cannot clean forks.
11. **Forks**: ask fork owners to delete their fork or apply the same rewrite.

## 6. Rollback

If something is wrong after the push, restore the backup taken in step 2-1. This was verified: the original SHAs and signatures came back exactly.

```bash
scripts/purge/protection.sh lift <protection-dir>
scripts/purge/rollback.sh <backup.git>   # git push --force <url> 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*'
scripts/purge/protection.sh restore <protection-dir>
scripts/purge/protection.sh compare <protection-dir>
```

Caveats:

- Rolling back **brings the values back** and makes them public again.
- Branches and commits created after the rewrite are not in the backup.
- Pushing to `main` can trigger the workflow that prints values again. Disable it first.

## 7. When the purge counts as done

The purge is done when all of these are true:

1. Every affected value has been rotated, and the old values no longer work.
2. On a fresh mirror clone from GitHub, gitleaks with the custom rules and the direct value search both report 0 for branches and tags.
3. Branch protection and rulesets match the export taken beforehand.
4. No value remains in PR descriptions, comments, their edit history, Actions logs or Release attachments.
5. Every developer has re-cloned and deleted their old clone.
6. Submodule pins and SHA records have been updated.
7. If a GitHub Support request was needed, Support has removed the stale `refs/pull/*` refs and old commit URLs, and you have confirmed those URLs no longer resolve. If you decided not to file one, the decision and the reason (for example, the values were rotated) are on record.
8. Any forks have been dealt with.
