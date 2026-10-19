---
name: bulk-resolve-conflicts
description: Resolve merge conflicts and fix red CI on every open PR in the current GitHub repo that has either, a few at a time (default 3 concurrently, each in its own worktree). For each conflicting PR, merges its base branch into the head, resolves the conflicts keeping the intent of both sides, validates and pushes to the PR's branch; for every queued PR, conflicting or not, it then fixes failing CI checks until they are green. Then checks for new conflicts and red CI every 5 minutes until stopped (`--once` to skip). Use when asked to bulk resolve conflicts, fix conflicting PRs, fix red CI on PRs, or update all PRs with conflicts.
---

# bulk-resolve-conflicts

Find the open pull requests that conflict with their base branch or whose CI is red. Merge the
base into each conflicting one, resolve the conflicts, and push the result to the PR's branch.
Then, for every queued PR, wait for its CI and fix any failing check until it is green. A PR that
only has red CI skips the merge and goes straight to the CI step. Nothing is merged into the base.

Arguments, if given, narrow the run: a list of PR numbers limits it to those PRs,
`--concurrency <n>` sets how many PRs are worked on at once (default 3), `--dry-run` stops
after printing the queue and the schedule, and `--once` ends the run after the first report instead
of watching for new conflicts and red CI (section 6). `--dry-run` implies `--once`.

Draft PRs are always ignored, since their authors are still pushing to them. No argument overrides
this, including a PR number given explicitly: report a listed draft as skipped. PRs labelled
`deferred` are always ignored too: they are parked on purpose. The same holds for a PR number given
explicitly: report it as skipped (deferred).

## Concurrency

The main session is the coordinator. It builds the queue, creates one worktree per PR, and hands
each PR to a worker: a background `general-purpose` agent launched with the Agent tool, running the
worker brief in section 3. At most `--concurrency` workers run at once. When one finishes, the
coordinator records its one-line result, removes its worktree, and starts the next PR that is
ready. Do not use a Workflow, and never exceed the concurrency limit. `--concurrency 1` runs the
same flow one PR at a time.

The coordinator carries forward only each worker's one-line result. It does not read diffs or
conflict details itself.

### Stacked PRs

A PR whose base branch is the head branch of another open PR belongs to that PR's stack. A stack
uses one slot and runs bottom first, because resolving the lower PR changes the branch the upper
PR merges in. Once the worker for a lower PR finishes, the coordinator re-checks the PR above it
(section 1's conflict and CI checks) even if it was not queued at the start, and queues it if it
now conflicts or has red CI and is neither a draft nor labelled `deferred`. Independent PRs and separate stacks fill the other slots. A
draft in a stack is skipped; a non-draft PR stacked on it is still handled, against the draft's
branch as its base.

## Ground rules

These apply to the coordinator and to every worker. Pass them to each worker in its brief.

- Read the repository's `AGENTS.md` and `CLAUDE.md` first and follow them for every git command,
  push, commit and validation run (safe.directory exceptions, push-destination checks, which
  validation to run, pre-commit hooks, post-commit process audits).
- Before every push, confirm with `git remote get-url --push origin` that the destination is the
  repository the PRs live in. Never change a remote URL to make a push work.
- Never force-push, never rebase a PR branch, and never pass `--no-verify`. Merging the base into
  the head keeps every push a fast-forward.
- Never use `git stash`. The stash is shared by every worktree, so another worker could pop it.
- Commit messages follow the user's writing rules and carry no tool attribution.
- Leave the user's own checkout and its uncommitted files untouched. All work happens in the PR's
  own worktree, and a worker never edits, builds in or runs git commands against any other
  worktree.
- Build output, caches and temp files stay inside the PR's worktree. Never point a build-output or
  cache setting (a target directory, an output path, a cache-dir override) at the user's checkout
  or another worktree.
- When the repository or the user's instructions name a machine-wide lock for builds, tests or app
  runs (a lock script, a lock file), every worker holds it as instructed. Before taking over a
  lock reported as stale, check that no build, test or app process started by another worker is
  still running (`tasklist`, `ps`). If one is, wait and retry instead of taking it.
- A worker never sends its final message while a background task it started (a validation run,
  the CI watch in 3e) is still running. A worker that hands back early leaves its merge or fix
  half done.

## 1. Build the queue

```sh
git fetch origin
gh pr list --state open --limit 200 --json number,title,isDraft,labels,headRefName,baseRefName,isCrossRepository,maintainerCanModify,mergeable,mergeStateStatus,statusCheckRollup
```

A PR conflicts when `mergeable == "CONFLICTING"` (its `mergeStateStatus` is then `DIRTY`). GitHub
computes mergeability lazily, so some PRs come back `UNKNOWN`. Re-query those one by one with
`gh pr view <n> --json mergeable,mergeStateStatus` after a few seconds, up to 3 times. If a PR is
still `UNKNOWN`, test it locally instead:

```sh
git merge-tree --write-tree origin/<baseRefName> origin/<headRefName>
```

A non-zero exit with conflicted paths in the output means it conflicts.

A PR has red CI when any entry of `statusCheckRollup` for its current head has finished as a
failure: a check run whose `conclusion` is `FAILURE`, `TIMED_OUT`, `CANCELLED`, `ACTION_REQUIRED`
or `STARTUP_FAILURE`, or a status context whose `state` is `FAILURE` or `ERROR`. Checks that are
still running or queued do not count either way. `gh pr checks <n>` shows the same thing for one PR.

The queue is every open, non-draft PR without the `deferred` label that conflicts, has red CI, or both, in ascending PR number.
Mark each with its reason (conflict, red CI, or both). Skip a cross-repository PR whose `maintainerCanModify` is false, since the merge cannot
be pushed to it, and report it as needing the author to update it. Group stacked PRs into stacks.
Print the queue with its stacks, the skipped PRs with reasons, and the concurrency. With
`--dry-run`, stop here.

## 2. Create the worktree (coordinator)

Right before starting a PR's worker, re-check `gh pr view <n> --json isDraft,labels,state`. If the PR has
been converted to a draft, is labelled `deferred`, or is no longer open, drop it from the queue and report it as skipped.

```sh
git fetch origin
git worktree add --detach <path> origin/<headRefName>
```

A detached worktree at the remote head works even when the branch is checked out in another
worktree, and pushing with `HEAD:<headRefName>` updates the branch. Put `<path>` in the directory
the repository already uses for worktrees (for example `.worktrees/`), named
`bulk-resolve-conflicts-<n>`; when there is none, use
`<repo>/../<repo-name>-bulk-resolve-conflicts/<n>`. Always pass the worktree's absolute path to the
worker. If the path already exists, another run may be using it: never remove it, skip the PR, and
report the path.

For a cross-repository PR, create a fresh worktree and fetch its head with `gh pr checkout <n>`
inside it.

## 3. Worker brief

Launch the worker with `run_in_background: true` and a prompt that gives it the PR number, the head
and base branches, the absolute worktree path, the ground rules above, the number of workers
running alongside it, and these steps.

### 3a. Enter the worktree

The worker sets its shell's working directory to the worktree and uses absolute paths (or
`git -C <path>`) in every command afterwards. It confirms that `git rev-parse --show-toplevel` is
the worktree path, `HEAD` is `origin/<headRefName>`, and `git status` is clean. If any check fails,
it stops and reports.

### 3b. Merge and resolve

Skip this step for a PR queued only for red CI: go to 3c, then 3e on the existing head (3d has
nothing to push). Merge the base into it only when the CI failure turns out to need a fix that is
already on the base.

Otherwise fetch, then merge the PR's current base:

```sh
git fetch origin
git merge origin/<baseRefName>
```

If the merge is clean (the base moved, or a PR below in the stack already absorbed the conflict),
go to 3c.

For each conflicted file:

1. Read both sides and the commits that produced them
   (`git log --oneline HEAD...origin/<baseRefName> -- <file>`, plus the PRs those commits came
   from) until the intent of each side is clear.
2. Write a resolution that keeps the intent of both. Take one side wholesale only when the other
   side's change is already contained in it. When a PR below in the stack was squash-merged, its
   commits are still on this branch under their old hashes, and the version on the base is that
   PR's final version.
3. Regenerate generated files (lockfiles, generated indexes, catalogs) with the repository's tool
   instead of hand-merging them.
4. If the two sides make decisions that contradict each other and the code does not show which
   should win, abort the merge (`git merge --abort`) and stop. The report names the file and the
   two competing changes.

Check that no conflict markers remain (`git diff --check`, and a search for `<<<<<<<`, `=======`,
`>>>>>>>` in the touched files).

### 3c. Validate

Run the repository's fast validation (whatever its `AGENTS.md` or `CLAUDE.md` names, or the build
and the tests covering the touched code). If it fails because of the merge, fix the resolution. If
it also fails on `origin/<headRefName>` before the merge, the failure is not the merge's doing:
note it in the result and continue, and fix it in 3e. For a PR queued only for red CI, a local
failure here is the first lead for 3e. Do not weaken or delete tests to make the merge pass.

Other workers run the same validation at the same time, so a failure can come from contention: a
file or lock held by another process, a port already in use, a single-instance app that is already
open, a package-store or build-server lock, a full disk (several workers' build output at once),
or a timeout waiting on one of these. Wait 30 to 120
seconds (a different delay each time) and run the same command again, up to 3 times. Treat the
failure as real only when it repeats with no sign of contention, or when it points at the merged
code.

### 3d. Commit and push

Commit the merge. The message names the base that was merged and, for each conflicted file, how
the two sides were combined. Then push:

```sh
git push origin HEAD:<headRefName>
```

If the push is rejected because the branch moved, fetch, merge `origin/<headRefName>`, resolve and
validate again, and push. Give up after 2 rejections and report the PR as busy.

### 3e. Get CI green

After the push (or, when the merge found nothing to do, on the existing head), wait for the PR's
checks to finish. Run the watch with the Bash tool and `run_in_background: true`, so the worker is
notified when it exits instead of polling:

```sh
gh pr checks <n> --watch --fail-fast
```

Make sure the checks belong to the commit just pushed: `gh pr view <n> --json headRefOid` must match
`git rev-parse HEAD`. If no checks have started yet, wait a minute and watch again; if none appear
after 5 minutes, report that the PR has no CI for this commit and finish.

If every check passes, go to 3f. Otherwise, for each failing check:

1. Read the failure: `gh pr checks <n>` for the run links, then `gh run view <run-id> --log-failed`.
2. Decide whether it comes from the merge resolution, from the PR's own code, from the
   interaction with the new base, or from infrastructure (runner crash, network fetch, timeout
   with no assertion failure).
3. Infrastructure, or a test known to flake: rerun once with `gh run rerun <run-id> --failed`. A
   second failure of the same check is treated as a real failure.
4. Real failure: reproduce it locally in the worktree, fix the cause, run the relevant validation
   (with the contention retries from 3c), commit with a message that says what was broken and why,
   and push as in 3d. Fix the code under test; do not delete, skip or weaken a test to turn it
   green unless the test itself is wrong, and say so in the commit message when it is.

Repeat until green. Stop and report, leaving the pushed merge in place, when:

- the same check is still red after three fix attempts;
- the fix needs a product decision, or would change behaviour the PR did not set out to change;
- the failure is in infrastructure the repository does not control and a rerun did not clear it.

### 3f. Result

When the repository asks for a post-commit process audit, the worker stops only processes tied to
its own worktree, and leaves processes tied to another `bulk-resolve-conflicts-<n>` worktree alone.

Once nothing is left uncommitted in the worktree, the worker deletes its regenerable build output
there (a `target`, `bin`/`obj`, `dist` or similar folder the build created, never anything git
tracks). Several finished worktrees' builds can fill the disk for the workers still running.

The worker's final message is one line: the PR number, why it was queued (conflict, red CI, or
both), the outcome (resolved and pushed, clean merge pushed, CI fixed without a merge, already up
to date, or stopped), the last commit pushed if any, the files that
conflicted, the CI state (green, green after fixes with what was fixed, no CI, or still red), any
pre-existing validation failure, and for a stop, the reason and what a human needs to do. It
does not remove the worktree.

## 4. Clean up (coordinator)

A worker can come back before it is done: its result says a validation run or the CI watch was
still going. That is not a stop. Resume the same worker with SendMessage and tell it to wait for
or redo the pending step and carry on from there; do not finish its steps in the coordinator.

When a worker reports, remove its worktree with `git worktree remove <path>` from outside it. Leave
the worktree in place when its worker stopped mid-merge or with uncommitted changes, and say so in
the report. Before starting the next ready PR, check the free space on the disk that holds the
worktrees. When it is too low for another build, delete the build output of finished, clean
worktrees first, and start no new worker until there is room. Then start the next ready PR,
re-checking the PR above it in its stack as described under Stacked PRs.

## 5. Report

End with a short table: each PR, why it was queued, its outcome, the last commit pushed if any, the files that
conflicted, the CI state, and for anything skipped or stopped, the reason and what a human needs to do.

## 6. Watch for new conflicts and red CI

Unless `--once` was given, the run does not end after the report. Once every worker has finished
and the report is printed, wait 5 minutes and check again:

1. Wait by running `sleep 300` with the Bash tool and `run_in_background: true`. The harness
   blocks a foreground sleep and re-invokes the coordinator when the background one exits. Do
   nothing else while waiting.
2. Build the queue again as in section 1, with the same PR-number filter if one was given.
3. Leave out a PR that a previous round stopped on or skipped (a contradiction a human must
   settle, a PR reported busy, a cross-repository PR that cannot be pushed to, a worktree path
   already in use) unless its head commit has changed since that round. Keep the head SHA of each
   such PR to compare against.
4. If the queue is empty, print one line with the time of the check and that nothing conflicts
   or has red CI,
   then go back to step 1.
5. Otherwise run sections 2 to 5 for the new queue, and go back to step 1 after its report.

Keep watching until the user interrupts the run or tells it to stop. Each round's report covers
only that round's PRs.
