# Purging secrets from git history: verification report

[日本語](verification-report.ja.md)

> This report records an end-to-end run of a git-history secret purge against a sandbox repository built entirely from dummy data. The repository contents, commit authors and secret values are all made up.

## 1. Summary

**Do not run the original runbook as written. It becomes safe to proceed once the problems below are fixed.**

Running the original runbook exactly as written produced these results:

| # | What happened | Impact |
|---|---|---|
| 1 | `git filter-repo` removes the `origin` remote, so step 4 (`git push --force --mirror origin`) fails | The procedure stops halfway |
| 2 | Step 3 runs `gitleaks detect` with the default rules only. It found none of the custom-format values, not even before the rewrite | A "clean" result that means nothing |
| 3 | Listing only raw values in `--replace-text` leaves base64-encoded and URL-encoded copies behind, as well as values inside binary files and gzip archives | Leftovers |
| 4 | A `--mirror` push has every `refs/pull/*` rejected and exits with status 1 | Success or failure is easy to misread |
| 5 | A `--mirror` push deletes any branch created on the remote after the clone | Someone else's work is lost |
| 6 | Replacing a short value such as `password` verbatim also rewrote function names, tests and the scanner configuration. One test failed | Broken code |
| 7 | Removing whole files makes some commits empty. filter-repo drops them, so branch commit counts go down | Release records no longer line up |
| 8 | After the rewrite, old commit pages, raw files and `.patch` URLs are still served to anonymous users. `refs/pull/N/head` of merged PRs still points at the old history, which anyone can clone | The values are still on GitHub |

We fixed these issues in a revised procedure ([runbook-revised.en.md](runbook-revised.en.md)), rolled the repository back to its original state, and ran the revised procedure from the start. **All values were gone from every branch and tag.** **Per-branch commit counts, subjects, merge structure, merge-bases, and the count and subjects of `version..develop` all matched the original.** Machine time was about 30 seconds.

Some things cannot be removed with git alone:

- **Old commits on GitHub** (still reachable by SHA) and **merged PR refs** need a GitHub Support request. We did not file one in this verification, so the outcome is unverified.
- **PR descriptions and comments, their edit history, Actions logs, Release attachments and forks** each need their own cleanup.

**Rotating the secrets comes first.** Treat the history purge as a follow-up step that makes the old values harder to find.

## 2. Test setup

| Item | Details |
|---|---|
| Tools | Git 2.56.1, git filter-repo 2.47.0, gitleaks 8.30.1, GitHub CLI 2.103.3 |
| Repository | Public repository on a personal GitHub account, with secret scanning and push protection enabled |
| Contents | A small web API written with the Python standard library only, plus config files, tests and docs |
| History | 97 commits (8 merges, 19 SSH-signed). 13 branches: `main`, `develop`, `version/1.0`, `version/1.1`, abandoned `feature/*` branches, `stg`, and a branch whose tip still holds a value already removed from `main`. 3 tags: annotated, lightweight, and signed annotated. 2 Releases |
| Pull requests | 3 open: one whose commits get rewritten, one whose commits don't, and one with a dummy value in its description and review comments. 2 merged |
| Protection | `main`: classic branch protection (no force pushes, PR required, enforced for admins, signed commits required). `develop`: a ruleset (no force pushes, no deletion, PR required, signed commits required) |
| Actions | One workflow that prints a dummy value to its log, and one that scans history with gitleaks |
| Submodule | A local-only parent repository pins the sandbox at a fixed SHA |

Planted dummy secrets (all in made-up formats):

| Kind | Where |
|---|---|
| Still in the current code, across several files and branches | Config, deploy script, docs, an open PR branch |
| Removed from code; only in history | A chat-tool webhook URL |
| Only at the tip of an abandoned branch | `feature/legacy-export`, `stg` |
| Whole-file removal | `.env`, a fake key file |
| Easy to miss | base64-encoded, URL-encoded DB password, JSON with key and value on separate lines, `.ipynb` output cell, binary file, gzip |
| Collateral-damage bait | The short value `password` |
| Outside git | PR description, review comments, Actions log, Release attachment |

## 3. Results at a glance

| # | Check | Original runbook | Revised procedure |
|---|---|---|---|
| 1 | Gone according to gitleaks and a direct search? | **NG** | **OK** (branches and tags) |
| 2 | Old-SHA URLs still reachable? | **NG** (yes) | **NG** (same; needs GitHub Support) |
| 3 | `refs/pull/*`, PRs, Actions, Releases, tags | **NG** | **Conditional** (some can be cleaned by hand; merged PRs need Support) |
| 4 | Pushing from an old clone brings values back? | **NG** (yes, via unprotected branches) | **Conditional** (prevented by wider protection) |
| 5 | Branch protection | **Conditional** (must be lifted; restores cleanly; all signatures lost) | Same |
| 6 | Release-flow consistency | **NG** (empty commits dropped; counts change) | **OK** (`--prune-empty never`) |
| 7 | Old-to-new SHA map | **OK** | **OK** |
| 8 | Phantom diffs | **Yes** (when old clones are used) | Same (avoided by re-cloning) |
| 9 | Pull requests | **Conditional** | **Conditional** |
| 10 | Tags and Releases | **Conditional** (signatures lost, attachments remain) | Same |
| 11 | Submodules | **Conditional** (doesn't break right away, but still points at old SHAs) | Same (re-pin with the map) |
| 12 | Collateral damage from replacements | **NG** (a test failed) | **OK** (context-anchored regex) |
| 13 | Run time | About 10 s at 10,000 commits | Similar |
| 14 | Freeze length | About 1 min of machine time | About 45 s. Plan a 30–60 min window including human review |
| 15 | Developer steps | Verified | Verified |
| 16 | Effect of only deleting abandoned branches | **Limited** | — |
| 17 | Forks | **Unverified** (documented behavior only) | — |

## 4. Details

### A. Did the values go away?

#### 1. Re-scan — original: NG / revised: OK

**Evidence**

- Running step 3 exactly as written (`gitleaks detect --source . --log-opts="--all" --redact`) uses only the default rules. Even before the rewrite, the only hits were 2 generic Kubernetes-secret findings on one manifest, and none of the custom-format values. The `detect` subcommand is deprecated; `gitleaks git` replaces it.
- With the custom rules (`scripts/gitleaks/gitleaks.toml`), the scan before the rewrite found 17 findings. gitleaks 8.30 decodes base64 and percent-encoding automatically and tags those hits `decoded:base64` or `decoded:percent`. **It did not find the values inside the binary file or inside the gzip archive.**
- After the original runbook's rewrite, we checked with gitleaks (custom rules) and with a direct value search. The search tool, `scripts/verify/scan_values.py`, looks through every object for the raw value, its base64 and URL-encoded forms, and the contents of gzip archives. These were left behind:

| What remained | Why |
|---|---|
| The base64-encoded value | `replacements.txt` listed only the raw values |
| The URL-encoded DB password | Same |
| The value inside a binary file | `--replace-text` doesn't touch binary blobs (GitHub's docs also say it applies to "non-binary files") |
| The value inside a gzip archive | It's compressed, so the string never matches |

- `--replace-text` did remove the value in the `.ipynb` output cell and the JSON value that sits on a separate line from its key. A custom gitleaks rule with `\s*` also caught the multi-line JSON value.
- In the revised procedure we added the encoded forms to the replacement list and removed the binary and gzip files entirely. Result: 0 gitleaks findings, and 0 hits from the direct search on branches and tags.

**Fix**: run the scanner with custom rules, and first confirm those rules catch every known value in the pre-rewrite history. Search for the known values directly, separately from the scanner. Add encoded forms (base64, URL-encoded, escaped) to the replacement list. Remove binary and compressed files that contain values, or replace them with regenerated copies.

#### 2. Old-SHA URLs — NG

**Evidence** (unauthenticated `curl`; `scripts/verify/check_urls.sh`):

| URL kind | Right after the push | About 3 hours later |
|---|---|---|
| `github.com/<repo>/commit/<old SHA>` | 200 (24/24) | 200 (24/24) |
| `github.com/<repo>/commit/<old SHA>.patch` | 200 (24/24); the diff includes the value | 200 (24/24); the diff includes the value |
| `raw.githubusercontent.com/<repo>/<old SHA>/<path>` | 200; the content includes the value | 200 (7/7); the content includes the value |
| `api.github.com/repos/<repo>/commits/<old SHA>` | 200 | 200 |
| `github.com/<repo>/blob/<old SHA>/<path>` | 503 (temporarily not served to anonymous `curl`) | 200 (7/7); the page includes the value |

Commits that existed only at the tips of abandoned branches stayed reachable in the same way after those branches were rewritten. About 3 hours later, not a single URL had stopped working: they don't go away on their own over time.

**Fix**: this can't be done with git. According to GitHub's docs, GitHub Support removes cached views and PR references and runs server-side garbage collection. A request needs the repository name, the number of affected PRs, and the "First Changed Commit(s)" that filter-repo prints. The docs say Support only helps when rotating the credentials can't mitigate the risk. We did not file a request in this verification (unverified).

#### 3. `refs/pull/*`, PRs, Actions, Releases, tags — NG (some can be cleaned by hand)

| Item | State after the rewrite | What you can do yourself | Result |
|---|---|---|---|
| `refs/pull/N/head` (open PRs) | Follows the force-pushed branch and points at the new SHA | Nothing needed | OK |
| `refs/pull/N/head` (merged PRs) | **Still points at the old SHA**. `git clone --mirror` downloads the whole old history, values included | Can't push it (`deny updating a hidden ref`) | **Needs Support** |
| PR description, line comments, review comments | Not touched by the git rewrite | Edit the description, delete line comments, edit the review body (`gh` and the API) | Gone from the API responses. **But the edit history (GraphQL `userContentEdits`) keeps the original text.** Deleting an edit-history revision is only possible in the web UI; unverified |
| Actions logs | Logs from runs before the rewrite still contain the value | Delete the runs with `gh run delete` | 404 after deletion |
| Release attachments | Unchanged | Delete and re-upload | Deleted |
| Release source archives | Rebuilt from the rewritten tag; no value | Nothing needed | OK |
| Tags | Rewritten by the push | Nothing needed | OK (signatures lost; see item 10) |

Note: every push to `main` during the rewrite and the rollback triggered the workflow that prints the value again, so **the value showed up in new logs**. Disable such workflows for the duration of the work.

#### 4. Pushing from an old clone — Conditional

| Action from a pre-rewrite clone | Result |
|---|---|
| `git push origin develop` | Rejected (not a fast-forward) |
| `git push --force origin develop` (ruleset) | Rejected (no force pushes, PR required, signed commits required; any one of these is enough to block it) |
| `git push --force origin main` (classic protection) | Rejected |
| `git push --force origin feature/search` (unprotected) | **Accepted; old history is back** |
| Pushing an unpushed branch as a new branch | **Accepted; old history is back** |
| `git pull` (merging the new `develop` into the old one) | Refused as "unrelated histories". That happened here only because the root commit was rewritten too. If the root commit stays the same, the merge may **go through silently** |

The CI gitleaks job flagged the new branch that brought values back (the workflow failed). Two caveats:

- CI runs **after** the push, so it can't block it.
- If the old commits predate the workflow file, the **workflow never runs**. Force-pushing `feature/search` triggered nothing.

**Fix**: for a while after the rewrite, add a ruleset on **all branches** (`refs/heads/**`) that blocks force pushes and restricts branch creation. Confirm that everyone has re-cloned. Push protection with custom patterns might stop such pushes, but it's an organization feature, so it's unverified here.

### B. What broke

#### 5. Branch protection — Conditional

- Protection had to be lifted to force-push. Force pushes from an old clone were rejected by both classic protection and the ruleset.
- Both can be lifted and restored with `gh api`:
  - Classic protection: lift with `DELETE /branches/<b>/protection`, restore with `PUT /branches/<b>/protection` and `POST .../required_signatures`.
  - Rulesets: `PUT /rulesets/<id>` with `enforcement` set to `disabled`, then back to `active`.
- After restoring, the settings matched the JSON exported beforehand (ignoring URL and timestamp fields). `scripts/purge/protection.sh` exports, lifts, restores and compares.
- **Signatures**: git filter-repo **strips every commit signature and tag signature**. Signed commits went from 19 to 0, and the signed tag became a plain annotated tag. There's no way to keep the signatures; both GitHub's docs and the filter-repo manual say so.
- **Signed-commits rule**: unsigned commits are rejected by the signed-commits rule too, so that rule has to be lifted along with the force-push rule. Once restored, the rule only applies to new pushes and doesn't affect existing commits. If PRs are merged on GitHub, GitHub signs the merge commits, so that workflow keeps working.
- Because this sandbox uses dummy author emails, signatures could never show as "Verified" on GitHub. We checked them locally with `git verify-commit` (SSH signatures).

#### 6. Release flow — original: NG / revised: OK

| Comparison | Original | Revised (`--prune-empty never`) |
|---|---|---|
| Commit count per branch | **Down by 2** | Same |
| Subject list per branch | **Different** ("Add .env" and "Add key file" disappeared) | Same |
| Count and subjects of `version/1.0..develop` and `version/1.1..develop` | Same (43 and 7) | Same |
| Merge-bases (compared by subject and date) | Same | Same |
| Merge structure (subject, date, parent count) | Same | Same |
| Diffs between branches (`git diff --stat`) | Differ only by the removed files | Same (as intended) |
| Tags (type, subject of the target) | Same | Same |

Removing a whole file empties any commit that only added that file, and filter-repo's default (`--prune-empty auto`) drops those commits. `--prune-empty never` keeps them as empty commits, so counts and subjects are preserved.

#### 7. Old-to-new SHA map — OK

filter-repo writes these files under `.git/filter-repo/`:

| File | Contents |
|---|---|
| `commit-map` | Old SHA → new SHA. Dropped commits map to all zeros |
| `ref-map` | Old → new SHA for each ref |
| `changed-refs` | The refs that changed |
| `first-changed-commits` | The first rewritten commits (used in a GitHub Support request) |

Across two filter-repo runs, `commit-map` still mapped the original SHAs to the final ones. We used it to re-pin the submodule (item 11). For release records and audits, translate any recorded old SHA to its new SHA with `commit-map`. The map contains no secret values, but old SHAs let anyone view old commits on GitHub (item 2), so keep it internal.

#### 8. Phantom diffs — Yes (when old clones are used)

Comparing an old clone's `develop` with the rewritten `version/1.1` gave these results:

- `git log origin/version/1.1..develop` listed **81 commits** instead of 7. Commits with identical content count as different because their SHAs differ.
- Merging with `git merge --allow-unrelated-histories` produced **conflicts in 12 files**. Forcing the merge through left **73 duplicated commit subjects** in the history.

Comparing fresh clones gives the same counts and subjects as before the rewrite (item 6). Phantom diffs appear **only when old-clone history gets mixed into the new history**.

#### 9. Pull requests — Conditional

| PR | Result |
|---|---|
| Open (3) | Followed the force-pushed branches and showed the new SHAs. Commit counts were unchanged and they stayed mergeable. No need to recreate them |
| Open, with a line comment | The line comment became "outdated". The timeline shows a force-push event whose link to the old SHA still opens the old commit |
| PR with no rewritten commits of its own | The root commit was signed, so stripping its signature changed every SHA. The actual diff was unchanged |
| Merged (2) | The commit list and diff came from the old `refs/pull/N/head`, so **they still showed old SHAs and the value** |

GitHub's docs recommend merging or closing open PRs before the rewrite, because comments on old diffs can be lost.

#### 10. Tags and Releases — Conditional

- Lightweight tags stayed lightweight and annotated tags stayed annotated.
- The signed tag lost its signature and became a plain annotated tag.
- Releases are bound to the tag name, so they survived. Source archives are generated from the new tag.
- Uploaded attachments are not touched by the rewrite and must be deleted and re-uploaded.

#### 11. Submodules — Conditional

- A fresh clone of the parent repository followed by `git submodule update --init` **still fetched the old SHA**, because GitHub still serves the old object.
- That SHA is not reachable from any rewritten branch, though. Once GitHub Support runs server-side GC it is expected to become unfetchable (unverified).
- Fix: look up the new SHA in `commit-map`, check the submodule out at that SHA, and commit in the parent. We confirmed that the re-pinned SHA equals the new `version/1.1`. **Past commits** in the parent still point at the old SHA.

#### 12. Collateral damage — original: NG / revised: OK

Replacing the bare word (`password==>REMOVED_SECRET`) also rewrote:

- Function and parameter names (for example, `check_password` became `check_REMOVED_SECRET`)
- Docstrings and tests
- **A rule in the gitleaks config** (`admin_password` became `admin_REMOVED_SECRET`)

One test failed. The revised procedure replaces the value only where it is assigned: `regex:(ADMIN_PASSWORD\s*=\s*)"password"==>\1"REMOVED_SECRET"`.

**How to review the rewrite** (`scripts/purge/purge_revised.sh review`):

1. Use `ref-map` to list the files that changed between the old and new SHA of each branch and tag tip, and check that only the expected files appear.
2. In `git diff -U0` of the main branch tips, inspect **only the added lines** by eye. Never print the removed lines; they contain the values.
3. Run the tests on the rewritten tips.

### C. Operations

#### 13. Run time

Measured on this sandbox (about 100 commits, about 70 KB):

| Task | Original | Revised |
|---|---|---|
| Lift protection (`gh api`) | Under 1 s × 2 | Same |
| `git clone --mirror` | 1.0 s | Under 1 s |
| filter-repo | 0.45 s + 0.35 s (two runs) | Under 1 s (one run) |
| gitleaks | 0.1 s | 0.1 s |
| Push | 4.2 s | 3 s |
| Whole procedure, prepare through after | — | 27 s |

Measured on larger, local-only dummy repositories (`scripts/verify/bench_large.py`; never pushed):

| Commits | Pack size | `--replace-text` | `--invert-paths` | gitleaks |
|---|---|---|---|---|
| 1,000 | 0.5 MB | 0.6 s | 0.5 s | 0.2 s |
| 10,000 | 5.3 MB | 6.0 s | 3.9 s | 1.0 s |
| 50,000 (5,000 files) | 29 MB | 61.5 s | 42.6 s | about 10 s |

Time grows roughly with commit count, and faster still when there are many files (larger trees). On a real repository, clone and push time also depend on network speed and repository size.

#### 14. Freeze length

- Machine time was about 1 minute with the original runbook and about 45 seconds with the revised procedure.
- The real freeze has to cover:
  - A human review of the rewrite (item 12)
  - Confirming that protection was lifted and then restored
  - The post-push re-scan
- Even for a small repository, **plan a 30–60 minute freeze window**.
- Right before pushing, the revised script checks whether any remote ref changed since the prepare step and aborts if one did. That way, a broken freeze never overwrites someone else's push.

#### 15. What developers need to do

The rescue procedure we tested (written up in [developer-notice.en.md](developer-notice.en.md), not scripted):

1. In the old clone, list unpushed commits (`git log --branches --not --remotes`).
2. Make a fresh clone.
3. In the fresh clone, fetch the old clone's branches into `refs/rescue/*`.
4. Replay only the unpushed commits onto a new branch with `git cherry-pick <old base>..<branch>`.
5. Delete `refs/rescue/*` and drop the old objects with `git gc --prune=now`.

We confirmed that the rescued branch does not reach the old history (about 3 seconds). The replayed commits may themselves contain a value; one planted example here did. Scan them with gitleaks before pushing.

#### 16. Only deleting abandoned branches — Limited

We deleted the four abandoned branches (`feature/search`, `feature/legacy-export`, `stg`, `hotfix/old-config`) and nothing else. Only **the 2 values that existed solely at those branch tips** became unreachable. Every other value was still in the history of `main` or `develop`.

Deleted commits also stay reachable on GitHub by SHA (same as item 2). Deleting branches only helps make values harder to find after they have been rotated.

#### 17. Forks — Unverified (documented behavior only)

A personal account can't fork its own repository, so we couldn't test this. GitHub's docs say:

- A commit containing the value stays accessible in any fork that has it. You have to ask fork owners to remove it or to delete the fork. GitHub Support can't clean forks and won't share fork owners' contact details.
- Git data in a repository network (a parent and its forks) may be accessible from any repository in the network, including the upstream one, **even after a fork is deleted**.
- If a public repository is made private, its public forks stay public in a separate network.

References:

- https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
- https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/what-happens-to-forks-when-a-repository-is-deleted-or-changes-visibility

**How to check on a real repository**:

- List the forks and their owners with `gh api repos/<owner>/<repo>/forks --paginate`. For a private organization repository, forks should belong only to organization members.
- Check whether the organization's settings allow forking.
- Ask fork owners to delete their fork or apply the same rewrite.

## 5. Common concerns

| Concern | Does it happen? | Mitigation |
|---|---|---|
| Every branch containing the value changes, and some branches are protected against force pushes | **Yes.** Every branch and tag after the first changed commit gets new SHAs. Here even unrelated branches changed, because the root commit was signed. Protection (no force pushes, signed commits) has to be lifted temporarily | Export the protection settings as JSON, lift them with `gh api`, and confirm there's no diff after restoring (verified). Protection is off for about a minute |
| Everyone has to update their local clones | **Yes.** Pushing from an old clone brought the values back through unprotected or new branches | Make re-cloning mandatory. Rescue unpushed work with cherry-pick (verified). Restrict branch creation with a ruleset for a while |
| Commit IDs change and phantom diffs appear, which hurts release flows where every commit in a diff has to be explained | SHAs **do** change. In fresh clones, though, the count and subjects of `version..develop`, the merge structure and the merge-bases **stay the same** (with `--prune-empty never`). Phantom diffs **do** appear when old-clone history gets mixed in | Use `--prune-empty never`. Keep `commit-map` to translate old SHAs to new ones. Don't use old clones |
| The develop and version branch histories must stay clean | Within the new history, the structure is preserved (verified) | Forbid merges from old clones. If `git pull` reports "unrelated histories", stop and re-clone |
| Nobody has done this before, and an accident is scary | The original runbook had a problem that stops it halfway and problems that silently leave values behind | Rehearse on a sandbox or a mirror first. The revised procedure includes a backup, a review phase, a check for remote ref changes before the push, and a tested rollback |

## 6. What we couldn't verify, and what to check on a private organization repository

**Not verified here**

- The effect of a GitHub Support request (cache removal, `refs/pull/*` removal, GC). We didn't file one
- Forks (a personal account can't fork its own repository)
- Organization-level rulesets and settings, and push-protection custom patterns (organization features)
- The signed-commits rule with signatures that GitHub shows as "Verified" (impossible here because the authors are dummies)
- Deleting PR description and review edit-history revisions in the web UI
- Repositories that use Git LFS

**Extra checks for a private organization repository**

1. Organization rulesets (whether they need lifting as well as the repository's own settings) and who can bypass them
2. The organization's fork policy and the list of existing forks
3. Whether old-SHA URLs are visible only to people with repository access (for a private repository they shouldn't be visible to outsiders)
4. Whether push-protection and secret-scanning custom patterns are available (if so, they might block pushes from old clones)
5. Actions log retention settings and who has permission to delete logs
6. Anything that records SHAs (deploy records, issue trackers, audit logs) and how to translate them with `commit-map`
7. How long clone, filter-repo and push take at the repository's actual size (estimate from the table in item 13, then measure on a mirror)

## 7. Records and scripts

- All scripts used are under `scripts/`. The README explains how to use them.
- Raw run logs, the list of planted values (`planted.json`) and working notes were kept only on the local machine so nothing sensitive leaks. They are not in this repository.
