---
name: bulk-review
description: Review every open PR in the current GitHub repo that lacks the "reviewed" label, a few at a time (default 3 concurrently, each in its own worktree). For each, runs /code-review high --fix on the PR, critically settles the PR's unaddressed review comments (a change, a different fix, or a reasoned reply), pushes the fixes to the PR's branch, brings the PR description up to date, adds the "reviewed" label, and then resolves any merge conflicts the PR has with its base. Then checks for newly eligible PRs every 5 minutes until stopped (`--once` to skip). Use when asked to bulk review, review all open PRs, or clear the unreviewed PR queue.
---

# bulk-review

Review open pull requests that do not carry the `reviewed` label, apply the review's fixes, settle
the comments already on the PR that nobody has addressed, push the changes to the PR's branch, label the PR, and resolve its conflicts with its base branch if it has
any.

Arguments, if given, narrow the run: a list of PR numbers limits it to those PRs, `--limit <n>`
stops after n PRs, `--concurrency <n>` sets how many PRs are reviewed at once (default 3),
`--proactivity <high|medium|none>` sets what a worker does with open questions (default `high`,
see 3c), `--dry-run` stops after printing the queue and the schedule, and `--once` ends the run
after the first report instead of watching for newly eligible PRs (section 6). `--dry-run` implies
`--once`, and `--limit` counts PRs across all rounds: the run ends once that many have been
started.

Draft PRs are reviewed like any other open PR.

PRs labelled `deferred` are always ignored: they are parked on purpose. The same holds for a
PR number given explicitly: report it as skipped (deferred).

## Concurrency

The main session is the coordinator. It builds the queue and hands each PR to a worker: a
background `general-purpose` agent launched with the Agent tool with `isolation: "worktree"`,
running the worker brief in section 3. At most `--concurrency` workers run at once. When one
finishes, the coordinator records its one-line result, checks the user's checkout, removes the
worker's worktree, and starts the next PR that is ready.

The isolation is required. `code-review` with a PR target checks the PR out and applies its fixes
in the agent's primary working directory, and a `cd` in the agent's shell does not change that
directory. A worker launched without isolation shares the coordinator's directory, which is the
user's checkout, so the review switches the user's branch and leaves its fixes there, and
concurrent workers overwrite each other. Never launch a worker without `isolation: "worktree"`,
and never hand a worker a worktree the coordinator created. Do not use a Workflow, and never exceed the concurrency limit: each high-effort review is
expensive, and the limit is what keeps the run inside the user's quota. `--concurrency 1` runs the
same flow one PR at a time.

To keep the coordinator's context from filling up, it carries forward only each worker's one-line
result. It does not read review output or diffs itself.

### Stacked PRs

A PR whose base branch is the head branch of another queued PR belongs to that PR's stack. A stack
uses one slot and runs in order, base first: the next PR in the stack starts only after the worker
for the PR below it has finished. This keeps a fix or conflict resolution pushed to a base branch
from landing while the PR above it is still being reviewed. Independent PRs and separate stacks
fill the other slots.

When a worker's result says it changed code (a fix, a removed helper, a changed signature), the
coordinator passes a short summary of those changes in the brief of the next PR in its stack, so
that worker's conflict step in 3f keeps both sides. The same goes across siblings: when one
worker settles a question in a way another queued PR could reuse (the same fallback, the same
pattern in a parallel code path), mention it in that PR's brief as something to weigh, not as an
instruction.

## Ground rules

These apply to the coordinator and to every worker. Pass them to each worker in its brief.

- Read the repository's `AGENTS.md` and `CLAUDE.md` first and follow them for every git command,
  push, commit and validation run (safe.directory exceptions, push-destination checks, which
  validation to run, pre-commit hooks, post-commit process audits).
- Before every push, confirm with `git remote get-url --push origin` that the destination is the
  repository the PRs live in. Never change a remote URL to make a push work.
- Never force-push and never pass `--no-verify`.
- Never use `git stash`. The stash is shared by every worktree, so another worker could pop it.
  Use a temporary commit to set work aside.
- Commit messages follow the user's writing rules and carry no tool attribution.
- Leave the user's own checkout and its uncommitted files untouched. All work happens in the
  worker's own isolated worktree, and a worker never edits, builds in or runs git commands against
  any other worktree. The only exception is the read-only snapshot check of the user's checkout
  (section 2).
- Build output, caches and temp files stay inside the worker's own worktree. Never point a
  build-output or cache setting (a target directory, an output path, a cache-dir override) at
  the user's checkout or another worktree, and tell the `code-review` skill the same when invoking
  it. Gitignored output written there does not show in `git status`, so the snapshot check cannot
  catch it.
- Only the coordinator adds or removes the `in-review` label. A worker never touches it.
- When the repository or the user's instructions name a machine-wide lock for builds, tests or app
  runs (a lock script, a lock file), every worker holds it as instructed. Before taking over a
  lock reported as stale, check that no build, test or app process started by another worker is
  still running (`tasklist`, `ps`). If one is, wait and retry instead of taking it.

## 1. Build the queue

```sh
gh pr list --state open --limit 200 --json number,title,labels,headRefName,baseRefName,isCrossRepository,maintainerCanModify
```

Do not create or look up the `reviewed` label here. The worker creates it only if adding it fails.

The queue is every open PR with none of the `reviewed`, `in-review` or `deferred`
labels, in ascending PR number. Skip
a cross-repository PR whose `maintainerCanModify` is false, since fixes cannot be pushed to it,
and report it. Group stacked PRs into stacks. Print the queue with its stacks and the concurrency.
With `--dry-run`, stop here.

## 2. Snapshot the user's checkout and claim the PR (coordinator)

Before launching the first worker, record the user's checkout: its absolute path
(`git rev-parse --show-toplevel`), its branch, `HEAD`, and `git status --porcelain=v1` (including
untracked files), ignoring `.claude/worktrees/`: the harness creates the workers' worktrees there,
so they show up as untracked files in the user's checkout. Save the snapshot to a file in the
scratchpad and pass its path and the checkout's path to every worker, with the same rule about
`.claude/worktrees/`. A worker whose isolation blocks `git status` in the user's checkout compares
the branch and `HEAD` by reading the refs under its `.git` directory.

The coordinator compares the checkout with the snapshot again after each worker reports, and
before starting each new worker. If the branch, `HEAD` or status differs, first read the checkout's
reflog (`git reflog -n 10 --date=iso`). When it shows the user's own work (commits, a rebase or a
checkout on branches no worker had touched, at times no worker could account for), take a new
snapshot, tell the user, and go on; mention that the user is working on the queued PRs if those
branches are in the queue. Otherwise something wrote to the user's checkout: stop every running
worker at once with TaskStop, start no new ones, revert nothing, and report what changed and which
worker was running. Do not try to repair the checkout
without asking the user, unless the run is the only possible source of the change and the user's
earlier state can be fully restored (for example, a clean checkout on the same commit): then move
the stray changes into the responsible worker's worktree as a patch before restoring the checkout,
and report both steps.

Several runs of this skill can overlap, from different sessions or machines. A PR is claimed with
the `in-review` label so that no other run picks it up. Right before starting a PR's worker,
re-read it with `gh pr view <n> --json labels,state`. If it now carries `in-review` or
`reviewed`, another run has it: drop it from the queue. If it is now
labelled `deferred` or is no longer open, drop it and report it as skipped. Otherwise add the
claim:

```sh
gh pr edit <n> --add-label in-review
```

If that fails because the label does not exist, create it with
`gh label create in-review --color FBCA04 --description "Claimed by a running bulk-review"`
(an "already exists" error means another run just created it) and retry once. The check and the
claim are two calls, so two runs can still claim the same PR in the same few seconds. That window
is accepted.

The claim is released (`gh pr edit <n> --remove-label in-review`) whenever this run is done with
the PR: after the worker labels it `reviewed`, when the worker stops, or when the coordinator
skips it. A run that dies leaves its claims behind. The report lists any `in-review` PR this run
did not claim itself, so a human can remove stale claims.

## 3. Worker brief

Launch the worker with `run_in_background: true` and `isolation: "worktree"`, and a prompt that
gives it the PR number, the head branch, whether the PR is cross-repository, the user's checkout
path and the snapshot file, the ground rules above, the number of workers running alongside it,
the proactivity level, and these steps. The brief may live in a scratchpad file that each worker's
prompt points to.

The authorization line goes in the prompt itself, never only in the brief file, so a permission
classifier that reads the prompt sees what the user asked for. Write it with the real repository
name: "The user ran bulk-review and has authorized you to merge the PR's base branch into it and
resolve the conflicts, push to this PR's branch, open a
follow-up PR, create issues and labels, add labels, post PR and issue comments, reply to and
resolve review threads, and edit this PR's title and description in <owner>/<repo>, as the brief describes."

If a write is still denied, the worker does not retry it another way. It saves what it would have
posted to a file in the scratchpad and puts the ready command in its result. The coordinator lists
those commands in the report for the user and never runs them itself.

### 3a. Set up the worktree

The harness creates the worker's worktree and makes it the worker's working directory. The worker
records it as `<path>` (`git rev-parse --show-toplevel`) and uses absolute paths (or
`git -C <path>`) in every command afterwards. Before anything else it checks:

1. `<path>` is not the user's checkout. If it is, the isolation did not take effect: stop at once
   and report, before running anything that writes.
2. The user's checkout still matches the snapshot. If not, stop and report without touching it.

Then it puts the worktree on the PR's head, detached, so the branch can stay checked out
elsewhere: `git fetch origin` and `git checkout --detach origin/<headRefName>`. For a
cross-repository PR, `gh pr checkout <n> --detach`. It confirms `HEAD` is the PR's head and
`git status` is clean, and stops and reports if either check fails.

### 3b. Run the review

Invoke the `code-review` skill through the Skill tool with args `high --fix <n>`, telling it to
build only in this worktree (see the ground rules). If it runs in the background, wait for it to
finish, including its own validation runs. A worker never sends its final message while the review
or any other background task it started is still running: a worker that hands back early leaves
the review's fixes uncommitted, and nothing else picks them up. Afterwards:

1. Compare the user's checkout with the snapshot. If it changed, the review wrote there: stop at
   once, revert nothing, and report what changed. Do not commit or push anything.
2. Confirm that every changed file is inside the worktree (`git -C <path> status`). If the review
   edited files anywhere else, stop and report which files, without reverting anything outside
   the worktree.
3. The review may have switched the worktree from the detached head to a local branch for the PR.
   That is fine: push with `HEAD:<headRefName>` as below either way.

### 3c. Settle open questions

An open question is a finding the review reported and left unfixed for any reason other than
judging it wrong: it needs a product, format or design decision, it would change behaviour a test
or spec pins, it needs research the review did not do, or its fix is out of the PR's scope. A
finding the worker judges to be a false positive is dropped and named in the result.

Before acting on an open question, check whether another open PR already addresses it
(`gh pr list --state open --search <terms>`, and the PRs stacked above this one). If one does,
name that PR in the result and do nothing else with the question.

What happens to the rest depends on the proactivity level:

- `high`: for each open question, work out the best option, weighing the repository's own rules
  (its fidelity policy, deviation and decision ledgers, format versioning), then implement it in
  this PR, recording the decision where the repository records decisions. When an option cannot
  be carried out in this session (it needs a tool, data or access the worker lacks), file an issue
  for it as below.
- `medium`: implement only the options that are strictly better: better on every axis that
  matters and worse on none, with no trade-off a maintainer could reasonably weigh differently.
  This includes a fix the repository's own rules already require. Every other open question
  becomes an issue.
- `none`: implement nothing beyond what the review fixed. Every open question becomes an issue.

To file an issue, first search open issues (`gh issue list --state open --search <terms>`) and
comment on a matching one instead of opening a duplicate. Otherwise open one with
`gh issue create --label needs-decision`; if the label does not exist, create it with
`gh label create needs-decision --color D93F0B --description "Open question from bulk-review"`
(an "already exists" error is fine) and retry once. The issue gives the PR number, the file and
line, what the code does now and what goes wrong, the options with their trade-offs, and the
worker's recommendation. It follows the user's writing rules and carries no tool attribution.
File issues after the push in 3d succeeds, or straight away when nothing is pushed, so an issue
never points at a fix that failed to land.

#### Address earlier comments on the PR

After the review, the worker reads every comment already on the PR and handles the ones nobody
has dealt with yet. Collect them from three places:

- review threads, with their state, through GraphQL:
  `gh api graphql -f query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){reviewThreads(first:100){nodes{id isResolved isOutdated path line comments(first:50){nodes{databaseId author{login} body createdAt}}}}}}}' -F o=<owner> -F r=<repo> -F n=<n>`
- review summaries: `gh pr view <n> --json reviews`
- conversation comments: `gh pr view <n> --json comments`

Skip resolved threads, summaries with no actionable content, CI and bot status messages, and
judgement-call comments posted by earlier bulk-review runs. Skip a comment when a later reply or
commit on the branch already settles it; check the commits since the comment was posted
(`git log --since=<createdAt>`) and the code at its `path` before deciding that. An outdated
thread still counts when its concern applies to the current code.

Review each remaining comment critically, the way the review treats its own findings: check the
claim against the current head, the spec and the repository's rules before accepting it. A
commenter can be wrong, can be right about the problem and wrong about the fix, or can ask for
something out of the PR's scope. Then settle it in whichever way is most reasonable:

- implement the suggestion as proposed, when it is correct and the best fix;
- implement a different change that addresses the underlying concern better, and say why the
  proposed one was not used;
- answer without a change, when the comment is mistaken, already handled, or asks a question
  the code answers, giving the evidence (file and line, spec ID, test);
- treat it as an open question (above), when it needs a decision or work this session cannot
  do, handled by the proactivity level like any other open question.

Changes go on the PR's branch with the review's fixes and are validated with them in 3d. Each
comment's outcome is a judgement call unless it applied a fix the comment spelled out exactly.

Answer each comment where it was made, after the push in 3d succeeds or straight away when nothing
is pushed. Reply in a review thread with
`gh api repos/<owner>/<repo>/pulls/<n>/comments/<databaseId>/replies -f body=...` (the id of the
thread's first comment), naming the commit when there is one. Resolve the thread
(`gh api graphql -f query='mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}' -F id=<thread id>`)
only when a pushed commit addresses it; a thread answered without a change stays open so the
commenter can reply. Conversation comments and review summaries are answered in the
judgement-call comment below, quoting or linking each one. Replies follow the user's writing rules
and carry no tool attribution.

#### Keep the PR description current

Every review ends with this check, whether or not the worker changed anything: a description can
be stale before the review starts. After the push in 3d succeeds (or straight away when nothing is
pushed), and again after a merge in 3f, read the PR's description (`gh pr view <n> --json body`)
against what the PR now contains (`git diff origin/<baseRefName>...HEAD --stat`, the diff itself
and the commits). Update it when any part is stale or an important part is missing:

- it claims a change the diff does not carry, or one the base branch already has;
- it describes behaviour, names, settings, versions or spec IDs that no longer hold;
- it leaves out something a reader needs: a change the worker's fixes or settled comments added, a
  new or changed setting, deviation, decision, spec entry, version bump or migration, or a
  behaviour change a reviewer would want to know about.

Rewrite the affected parts with `gh pr edit <n> --body-file <file>`. When the title no longer
describes what the PR carries (for example, its original fix landed on the base and only a
smaller part is left), retitle it with `gh pr edit <n> --title`. Follow
the user's PR description rules: describe the PR as it stands now, with no mention of review
rounds or earlier iterations. Keep the author's structure and wording wherever it is still
accurate.

#### Explain judgement calls on the PR

A judgement call is any choice the worker makes that a maintainer could have made differently:
settling an open question, picking one fix among several, dropping a finding as wrong, leaving a
question to another PR, or reverting a fix that broke validation. Mechanical steps (applying a
fix the review spelled out, retrying a contention failure) are not judgement calls.

For each one, post a comment on the PR the call pertains to: the reviewed PR in most cases, or the
PR a question was left to. One comment per PR collects that PR's calls. Each call gets the
dilemma, the options considered, what was decided and why, and the commit that carries it, if any.
The comment links any issues filed for the PR. Post it with `gh pr comment <n> --body-file <file>`
after the push in 3d succeeds, or straight away when nothing is pushed. It follows the user's
writing rules and carries no tool attribution.

### 3d. Validate and commit

If the review, 3c and the handling of earlier comments changed nothing, go to 3e.

Otherwise, read the diff they produced, then run the repository's fast validation (whatever its
`AGENTS.md` or `CLAUDE.md` names, or the build and the tests covering the touched code). If a fix
breaks the build or a test, revert that fix and keep the rest. A reverted fix becomes an open
question and is handled as 3c says for the proactivity level, except that `high` files an issue
for it instead of trying again. Do not weaken or delete tests to make a fix pass.

Other workers run the same validation and may launch the same app at the same time, so a failure
can come from contention: a file or lock held by another process, a port already in use, a
single-instance app or window that is already open, a busy audio or graphics device, a NuGet,
package-store or build-server lock, a full disk (several workers' build output at once), or a
timeout waiting on one of these. Such a failure says
nothing about the fix. Wait 30 to 120 seconds (pick a different delay each time, so workers do not
retry in step) and run the same command again, up to 3 times. Treat the failure as real only when
it repeats with no sign of contention, or when it points at the changed code.

Commit the remaining changes with a message that lists each fix and why it was needed, then push:

```sh
git push origin HEAD:<headRefName>
```

If the push is rejected because the branch moved, fetch, merge `origin/<headRefName>`, re-run
validation, and push again. If that merge conflicts, abort it, leave the PR unlabelled, and report
it.

#### The PR merged during the review

Another run or a human may merge the PR while the review is still going. Right before pushing,
and again if a push is rejected, check `gh pr view <n> --json state,baseRefName`. When the state
is `MERGED`, the fixes always go out in a follow-up PR. This holds whatever the fixes are and
whatever the proactivity level; never drop them, and never ask whether to.

1. Do not push to `<headRefName>`. Its branch is usually deleted after the merge, and a push would
   recreate it outside any PR.
2. Commit the fixes, fetch, and merge the branch the PR merged into: `origin/<baseRefName>`, or
   `origin/main` when that branch no longer exists. If the merge conflicts, resolve it keeping the
   intent of both sides. Re-run validation.
3. Push to a new branch, `git push origin HEAD:refs/heads/review-followup/<n>`, and open a PR from
   it to that base with `gh pr create --label reviewed`. Its description says it carries the
   review fixes for #<n>, which merged before they landed, and lists each fix and why, describing
   the follow-up as it stands (see the user's PR description rules).
4. Label #<n> `reviewed`, and post the judgement-call comment (3c) on #<n> with a link to the
   follow-up PR. Issues filed for #<n> name the follow-up PR as well.

If the PR was closed without merging, push nothing, leave it unlabelled, and report it.

### 3e. Label

Add the label only after the push succeeded, or when there was nothing to push:

```sh
gh pr edit <n> --add-label reviewed
```

If this fails because the label does not exist in the repository, create it and retry once:

```sh
gh label create reviewed --color 0E8A16 --description "Reviewed and fixed by bulk-review"
gh pr edit <n> --add-label reviewed
```

Another worker may create the label at the same moment. If `gh label create` fails because the
label already exists, retry the `gh pr edit`.

### 3f. Resolve conflicts

Once the review's fixes are pushed (or there were none) and the PR is labelled, check whether the
PR conflicts with its base. Skip this step when a follow-up PR was opened in 3d, or when
`gh pr view <n> --json state,baseRefName` shows the PR is no longer open.
Use the `baseRefName` from that call, since the base may have been retargeted during the review.

```sh
git fetch origin
git merge-tree --write-tree origin/<baseRefName> HEAD
```

A zero exit means no conflicts: go to 3g. GitHub's own `mergeable` field lags behind a fresh push,
so trust the local check.

On conflicts, merge and resolve in the worktree:

1. `git merge origin/<baseRefName>`.
2. For each conflicted file, read both sides and the commits that produced them
   (`git log --oneline HEAD...origin/<baseRefName> -- <file>`, plus the PRs those commits came
   from) until the intent of each side is clear, then write a resolution that keeps the intent of
   both. Take one side wholesale only when the other side's change is already contained in it.
   When a PR below in the stack was squash-merged, its commits are still on this branch under their
   old hashes, and the version on the base is that PR's final version.
3. Regenerate generated files (lockfiles, generated indexes, catalogs) with the repository's tool
   instead of hand-merging them.
4. If the two sides make decisions that contradict each other and the code does not show which
   should win, abort the merge (`git merge --abort`), push nothing more, and report the file and
   the two competing changes. The PR keeps its `reviewed` label.
5. Check that no conflict markers remain (`git diff --check`, and a search for `<<<<<<<`,
   `=======`, `>>>>>>>` in the touched files).

Validate as in 3d, including its contention retries. If validation fails because of the merge, fix
the resolution; if it also failed before the merge, note that in the result and continue. Do not
weaken or delete tests to make the merge pass. A resolution choice a maintainer could have made
differently is a judgement call: add it to the PR comment from 3c, or post one if there was none.

Commit the merge with a message that names the base that was merged and, for each conflicted file,
how the two sides were combined. Never rebase and never force-push; merging keeps the push a
fast-forward. Push with `git push origin HEAD:<headRefName>`. If the push is rejected because the
branch moved, fetch, merge `origin/<headRefName>`, resolve and validate again, and push. Give up
after 2 rejections and report the conflicts as unresolved because the branch is busy.

### 3g. Process audit and result

When the repository asks for a post-commit process audit, the worker stops only processes whose
command line, parent or paths tie them to its own worktree. Processes tied to another worktree
belong to a worker still running: leave them alone and do not log them.

Once nothing is left uncommitted in the worktree, the worker deletes its regenerable build output
there (a `target`, `bin`/`obj`, `dist` or similar folder the build created, never anything git
tracks). Each worktree's build can take gigabytes, and several finished worktrees can fill the disk
for the workers still running.

The worker waits until the review and every background task it started have finished before
writing its result. The worker's final message is one line: the PR number, its worktree `<path>`,
the outcome (fixed and labelled, labelled with no changes, follow-up PR opened, or stopped), the commit pushed if any, the follow-up PR if
any, the conflict outcome from 3f (none, resolved with the merge commit and the files that
conflicted, or left unresolved with the reason), the open questions it decided itself, the
issues it filed or commented on, the PR comments it posted, the earlier PR comments it handled
(implemented, implemented differently, answered without a change, or turned into open questions),
whether it updated the PR description and what it changed there, the questions left to other
PRs, the findings it dropped as wrong,
and for a stop, the reason and what a human needs to do. It does not remove the worktree.

## 4. Clean up (coordinator)

When a worker reports, first compare the user's checkout with the snapshot (section 2).

A worker can come back before it is done: its result says the review or a validation run was
still going, and the worktree holds uncommitted fixes. That is not a stop. Keep the claim, and
resume the same worker with SendMessage, repeating the authorization line from section 3, and tell
it to wait for or redo the pending step and then carry on from 3c. Do not do the remaining steps
in the coordinator, and do not launch a fresh worker on that PR. Only a worker that reports a real
stop (a failed check, a conflict it left, a denied write) counts as stopped.

Then release the PR's `in-review` claim and remove the worker's worktree with
`git worktree remove <path>` from outside it, if the harness has not already removed it. The
harness locks each worktree for its agent and the lock can outlive the agent: when `remove` fails
on a lock and the worker has finished with a clean worktree, run `git worktree unlock <path>`
first. Delete the local branch the harness created for the worktree, if any, once nothing
references it; never delete a branch that existed before the run. Leave a worktree in place when
its worker stopped mid-merge or with uncommitted changes, and say so in the report.

Before starting the next ready PR, check the free space on the disk that holds the worktrees.
When it is too low for another build (less than a few times what one worker's build takes), delete
the build output of finished, clean worktrees first, and start no new worker until there is room.
Then start the next ready PR.

## 5. Report

End with a short table: each PR, its outcome (fixed and labelled, labelled with no changes,
follow-up PR opened, skipped), the commit pushed if any, the follow-up PR if any, the conflict
outcome, the issues filed, and for anything skipped or left with conflicts, the reason and what a
human needs to do. Under `high`, list the open questions workers decided themselves, so a human
can check those decisions. List the earlier PR comments that workers answered without a change
or settled with a different fix than the commenter proposed, since those are the ones a commenter
may want to dispute.

The label does not record which commit was reviewed. A PR that receives new commits after being
labelled keeps the label, and this skill will not review it again until someone removes the label.
Say so in the report when a labelled PR from this run has since gained commits from someone else.

## 6. Watch for new PRs

Unless `--once` was given, the run does not end after the report. Once every worker has finished
and the report is printed, wait 5 minutes and check again:

1. Wait by running `sleep 300` with the Bash tool and `run_in_background: true`. The harness
   blocks a foreground sleep and re-invokes the coordinator when the background one exits. Do
   nothing else while waiting.
2. Build the queue again as in section 1, with the same PR-number filter if one was given. A PR
   becomes eligible when it is opened, marked ready for review, or has its `reviewed` label
   removed.
3. Leave out a PR that a previous round stopped on or skipped (a push conflict, a busy branch, a
   write that was denied, a check of the user's checkout that failed) unless its head commit has
   changed since that round. Keep the head SHA of each such PR to compare against.
4. Before starting a round, compare the user's checkout with the snapshot from section 2. If it
   changed, the user has been working there: take a new snapshot instead of stopping, since no
   worker is running.
5. If the queue is empty, print one line with the time of the check and that nothing is waiting
   for review, then go back to step 1.
6. Otherwise run sections 2 to 5 for the new queue, and go back to step 1 after its report.

Keep watching until the user interrupts the run, tells it to stop, or `--limit` is reached. Each
round's report covers only that round's PRs.
