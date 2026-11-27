# Developer notice (template)

[日本語](developer-notice.ja.md)

> Replace the `<...>` placeholders before sending.

---

**Subject: Action needed: `<repository>` history will be rewritten on `<date>`, `<start>`–`<end>`**

We found credentials in the git history of `<repository>`. They have already been revoked. To remove them from the history as well, we will rewrite it during the window below.

## 1. Freeze window: `<date>`, `<start>`–`<end>`

- During this window, **do not push** to `<repository>`. Also don't merge PRs, create or delete branches, or create tags.
- Branch protection will be switched off briefly while we work.

## 2. Before the freeze

- **Check for unpushed commits:**

  ```bash
  git log --branches --not --remotes --oneline
  ```

- Push anything you need and open a PR before the freeze if you can.
- Merge or close your open PRs before the freeze where possible.

## 3. After the rewrite (required)

Every commit ID (SHA) will change. **Your existing clone can't be used as is.**

1. **Make a fresh clone:**

   ```bash
   git clone <repository URL> <new directory>
   ```

2. **If you have unpushed work, move it to the new clone:**

   ```bash
   cd <new directory>
   # bring your old branch in under a temporary name
   git fetch <path to old clone> "+refs/heads/<branch>:refs/rescue/<branch>"
   # start a branch from the new base and replay only your unpushed commits
   git switch -c <branch> origin/<base branch>
   git cherry-pick <SHA of origin/<base branch> in the old clone>..refs/rescue/<branch>
   # drop the temporary ref and clean out the old objects
   git update-ref -d refs/rescue/<branch>
   git reflog expire --expire=now --all && git gc --prune=now
   ```

   - Get `<SHA of origin/<base branch> in the old clone>` by running `git rev-parse origin/<base branch>` in the old clone **before you fetch there**.
   - Before pushing, make sure the replayed commits don't contain credentials.

3. **Delete your old clone**, including stashes, worktrees and copies on other machines.

4. **Tell `<contact>` when you're done.**

## 4. Please don't

- Push from an old clone (especially with `--force`). It brings the removed credentials back.
- Run `git pull` or `git merge` in an old clone. If you see "refusing to merge unrelated histories", stop there. Don't use `--allow-unrelated-histories`.
- Merge an old branch into a branch of the new history. You'll get large phantom diffs: duplicates of commits with the same content.

## 5. What changes

- Every commit ID (SHA) changes. The old-to-new map is at `<location>`.
- Commit signatures are removed, and signed tags become unsigned annotated tags.
- Open PRs keep working on the new history, though line comments may be marked "outdated".
- Commit counts per branch, commit subjects and merge structure stay the same.

## 6. Questions

`<contact>`
