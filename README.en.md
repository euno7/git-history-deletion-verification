# Verifying secret removal from git history

[日本語](README.ja.md)

This repository records a hands-on test, using dummy data, of **a procedure for removing secrets from git history** by rewriting it with git filter-repo and force-pushing.

- The repository contents, branches, pull requests, commit authors and secret values are **all dummies made for this test**. Nothing here refers to a real organization, service or person.
- The dummy secrets use made-up formats (`FAKESECRET_...`, `fakekey-...`, `FAKEPW-...` and so on), not formats of real services.
- The history of this repository has been rewritten many times as part of the test.

## Outcome

The original runbook, followed as written, either stopped halfway or left values behind. The revised procedure removed every value from branches and tags and kept the release flow intact, including commit counts and merge structure. Old commits on GitHub and the refs of merged pull requests can't be removed with git alone. See the report for details.

## What's here

| Path | Contents |
|---|---|
| [report/verification-report.en.md](report/verification-report.en.md) | The verification report: summary, checks 1–17, answers to common concerns, what couldn't be verified |
| [report/runbook-revised.en.md](report/runbook-revised.en.md) | The revised runbook: preparation, execution, review, follow-up, rollback, completion criteria |
| [report/developer-notice.en.md](report/developer-notice.en.md) | A template notice for developers |
| `scripts/setup/` | Builds the sandbox repository |
| `scripts/baseline/` | Records the before and after state, and creates old clones |
| `scripts/purge/` | Runs the original runbook step by step; the revised procedure; saving and restoring protection; rollback |
| `scripts/verify/` | Direct value search, URL checks, before/after comparison, timing on large repositories |
| `scripts/gitleaks/gitleaks.toml` | gitleaks rules for the made-up formats |

The application files (`app/`, `config/`, `tests/` and so on) are dummy test content.

## Running it again

### Requirements

- Git 2.40+, git filter-repo 2.47+, gitleaks 8.24+, the GitHub CLI (`gh`, logged in with admin rights on the target repository), Python 3 and jq
- SSH push access

### Before you start

- The scripts write the list of dummy values to `planted.json` in the work directory (`~/purge-verify-work` by default). **Never commit or push that file.**
- The scripts use dummy author names and `noreply` addresses, and set `GIT_CONFIG_GLOBAL=/dev/null` so your personal git config isn't used.
- Set `REPO` (`owner/name`) to target another repository. **Only use a repository whose history you can afford to rewrite.**

### Steps

```bash
# 1. build the sandbox (fresh random fake values every run) and set up GitHub
python3 scripts/setup/build_sandbox.py --workdir ~/purge-verify-work
scripts/setup/github_setup.sh ~/purge-verify-work      # push, PRs, Release, protection
scripts/setup/make_submodule_parent.sh                  # local-only parent repo

# 2. baseline + old clones
scripts/baseline/record_baseline.sh ~/purge-verify-work/baseline
scripts/baseline/make_old_clones.sh

# 3a. the ORIGINAL runbook, one step at a time (logs: ~/purge-verify-work/logs/runbook/)
for s in 0-lift 1-clone 2a-replace 2b-invert 3-verify 4-push 5-restore; do
  scripts/purge/run_runbook.sh "$s"
done

# 3b. the REVISED runbook
for p in prepare rewrite review push after; do
  scripts/purge/purge_revised.sh "$p"
done

# 4. checks
python3 scripts/verify/scan_values.py <mirror.git> --refs "refs/heads refs/tags"
scripts/verify/check_urls.sh <out.tsv> ~/purge-verify-work/baseline
scripts/baseline/record_baseline.sh <after-dir>
scripts/verify/compare_baseline.sh ~/purge-verify-work/baseline <after-dir>
python3 scripts/verify/bench_large.py --commits 10000 --gitleaks-config scripts/gitleaks/gitleaks.toml

# rollback to the backup taken by "prepare"
scripts/purge/protection.sh lift <protection-dir>
scripts/purge/rollback.sh <backup.git>
scripts/purge/protection.sh restore <protection-dir>
```

Notes:

- Step 4 of the original runbook fails as written because `origin` has been removed. We recorded the failure, re-added `origin`, and carried on (report item 1, first row of the summary table).
- Rebuilding never deletes the repository. Branches and tags are replaced by force push, and new PRs and Releases are added.
