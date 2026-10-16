---
name: bulk-inline-review
description: Review every open non-draft PR in the current GitHub repo that lacks the "inline-reviewed" label, a few at a time (default 3 concurrently, each in its own worktree). For each, runs /code-review high --comment on the PR, which posts every finding as an inline comment on the PR's diff. Changes nothing: no fixes, no pushes, no merges, no description edits. Then labels the PR "inline-reviewed" and checks for newly eligible PRs every 5 minutes until stopped (`--once` to skip). Use when asked to bulk inline review, comment-only review of all open PRs, or to leave review comments on PRs without fixing them.
---

# bulk-inline-review

Review open pull requests that do not carry the `inline-reviewed` label and post the findings as
inline comments on each PR. Nothing is fixed: the worker never commits, pushes, merges, edits a
PR's title or description, or replies to existing comments. The PR author acts on the comments.

Arguments, if given, narrow the run: a list of PR numbers limits it to those PRs, `--limit <n>`
stops after n PRs, `--concurrency <n>` sets how many PRs are reviewed at once (default 3),
`--max-findings <n|all>` is passed through to `code-review`, `--dry-run` stops after printing the
queue, and `--once` ends the run after the first report instead of watching for newly eligible PRs
(section 6). `--dry-run` implies `--once`, and `--limit` counts PRs across all rounds.

Draft PRs are always ignored, including a draft given explicitly by number: report it as skipped.
PRs labelled `deferred` are always ignored too, including one given explicitly by number: report it
as skipped (deferred).

## Concurrency

The main session is the coordinator. It builds the queue and hands each PR to a worker: a
background `general-purpose` agent launched with the Agent tool with `isolation: "worktree"`,
running the worker brief in section 3. At most `--concurrency` workers run at once. When one
finishes, the coordinator records its one-line result, checks the user's checkout, removes the
worker's worktree, and starts the next PR.

The isolation is required even though nothing is fixed. `code-review` with a PR target checks the
PR out in the agent's primary working directory, so a worker without isolation switches the user's
branch, and concurrent workers check out over each other. Never launch a worker without
`isolation: "worktree"`, never hand a worker a worktree the coordinator created, do not use a
Workflow, and never exceed the concurrency limit: each high-effort review is expensive, and the
limit keeps the run inside the user's quota.

The coordinator carries forward only each worker's one-line result. It does not read review output
or diffs itself.

Stacked PRs need no ordering here, since nothing is pushed: each PR is reviewed against its own
base, and a PR stacked on a draft is still reviewed.

## Ground rules

These apply to the coordinator and to every worker. Pass them to each worker in its brief.

- Read the repository's `AGENTS.md` and `CLAUDE.md` first.
- Never commit, push, merge, rebase, or edit any branch. Never edit a PR's title, description or
  labels other than `inline-reviewed` (worker) and `in-review` (coordinator).
- Never use `git stash`; it is shared by every worktree.
- Leave the user's own checkout untouched. A worker runs git commands only against its own
  worktree. The only exception is the coordinator's read-only snapshot check (section 2).
- Comments follow the user's writing rules and carry no tool attribution.

## 1. Build the queue

```sh
gh pr list --state open --limit 200 --json number,title,isDraft,labels,headRefName,baseRefName,isCrossRepository
```

The queue is every open, non-draft PR with none of the `inline-reviewed`, `in-review` or
`deferred` labels, in ascending PR number. Cross-repository PRs are included: commenting needs no push access. Print
the queue and the concurrency. With `--dry-run`, stop here.

## 2. Snapshot the user's checkout and claim the PR (coordinator)

Before launching the first worker, record the user's checkout: its absolute path
(`git rev-parse --show-toplevel`), branch, `HEAD`, and `git status --porcelain=v1
--untracked-files=all`, ignoring `.claude/worktrees/`. Save it to a scratchpad file and pass its
path to every worker. Compare the checkout with the snapshot after each worker reports and before
starting each new worker. If it differs, stop every running worker with TaskStop, start no new
ones, revert nothing, and report what changed and which worker was running.

Claim each PR with the `in-review` label, the same claim `bulk-review` uses, so the two skills
never work on one PR at the same time. Right before starting a PR's worker, re-read it with
`gh pr view <n> --json labels,isDraft,state`. Drop it if it now carries `in-review` or
`inline-reviewed`, or if it is a draft, labelled `deferred`, or no longer open. Otherwise:

```sh
gh pr edit <n> --add-label in-review
```

If the label does not exist, create it with
`gh label create in-review --color FBCA04 --description "Claimed by a running bulk review"`
("already exists" is fine) and retry once. Release the claim
(`gh pr edit <n> --remove-label in-review`) when the worker reports or is stopped, or when the
coordinator skips the PR.

## 3. Worker brief

Launch the worker with `run_in_background: true` and `isolation: "worktree"`. Its prompt gives the
PR number, head and base branch, whether the PR is cross-repository, the user's checkout path and
the snapshot file, the ground rules, the `--max-findings` value if one was given, and these steps.
The brief may live in a scratchpad file that each prompt points to.

The authorization line goes in the prompt itself, with the real repository name: "The user ran
bulk-inline-review and has authorized you to post inline review comments on this PR, and to create
and add the inline-reviewed label, in <owner>/<repo>, as the brief describes."

If a write is denied, the worker does not retry it another way. It saves what it would have posted
to a scratchpad file and puts the ready command in its result. The coordinator lists those commands
in the report and never runs them itself.

### 3a. Set up the worktree

The worker records its worktree as `<path>` (`git rev-parse --show-toplevel`) and checks:

1. `<path>` is not the user's checkout. If it is, stop at once and report.
2. The user's checkout still matches the snapshot, as far as the worker can read it. If not, stop.

Then `git fetch origin` and `git checkout --detach origin/<headRefName>` (for a cross-repository
PR, `gh pr checkout <n> --detach`), and confirm `HEAD` is the PR's head and `git status` is clean.

### 3b. Check what is already posted

Read the PR's existing review threads
(`gh api repos/<owner>/<repo>/pulls/<n>/comments --paginate`). The review must not repost a
finding that an existing comment already raises at the same place; pass that list to the review as
context, or remove duplicates before posting if the review lets you approve its comments first.

### 3c. Run the review

Invoke the `code-review` skill through the Skill tool with args `high --comment <n>` (plus
`--max-findings <value>` if given). Do not pass `--fix`. If it runs in the background, wait for it.

Afterwards:

1. Compare the user's checkout with the snapshot. If it changed, stop and report.
2. If the review left any change in the worktree (`git -C <path> status`), discard it inside the
   worktree only (`git -C <path> checkout -- .` and `git -C <path> clean -fd`). Nothing is
   committed.
3. Confirm the comments landed: list the PR's review comments again and count the new ones. If the
   review found nothing, post nothing.

### 3d. Label

After the comments are posted, or when the review found nothing:

```sh
gh pr edit <n> --add-label inline-reviewed
```

If the label does not exist, create it with
`gh label create inline-reviewed --color 1D76DB --description "Inline review comments posted by bulk-inline-review"`
("already exists" is fine) and retry once. Do not label a PR whose comments failed to post.

### 3e. Result

The worker's final message is one line: the PR number, its worktree `<path>`, the outcome
(commented and labelled, labelled with no findings, or stopped), the number of inline comments
posted and how many were skipped as duplicates of existing ones, the most severe finding in a few
words, and for a stop, the reason and what a human needs to do. It does not remove the worktree.

## 4. Clean up (coordinator)

When a worker reports, compare the user's checkout with the snapshot, release the PR's `in-review`
claim, and remove the worker's worktree with `git worktree remove <path>` from outside it. If the
harness still holds a lock on it, leave it and retry at the next cleanup. Delete the local branch
the harness created for the worktree once nothing references it; never delete a branch that existed
before the run. Then start the next PR.

## 5. Report

End with a short table: each PR, its outcome, the inline comments posted, the most severe finding,
and for anything skipped or stopped, the reason and what a human needs to do. List any denied write
with its ready command.

The label does not record which commit was reviewed. A PR that gains commits after being labelled
keeps the label and is not reviewed again until someone removes it.

## 6. Watch for new PRs

Unless `--once` was given, after the report wait with `sleep 300` in the Bash tool with
`run_in_background: true`, doing nothing else meanwhile. Then build the queue again as in section 1
with the same PR filter, leaving out a PR a previous round stopped on unless its head commit has
changed. Before starting a round, compare the user's checkout with the snapshot; if it changed and
no worker is running, take a new snapshot. If the queue is empty, print one line with the time of
the check and go back to waiting; otherwise run sections 2 to 5 again. Keep watching until the user
stops the run or `--limit` is reached.
