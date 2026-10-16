---
name: cleanup-leftovers
description: Find and remove stale leftovers on this machine's drive, such as git worktrees, agent scratchpads and temp folders, and regenerable tool caches in repositories, older than a given age. Use when asked to clean up stale worktrees, old caches, scratchpads or leftovers ("clean up everything older than two days").
---

# Cleaning up leftovers

Inventory first, delete second. Show the person what was found and what will be kept before removing anything, unless they already gave the scope and age ("clean up everything older than two days" is that authorization for the categories below; anything outside them needs a question).

Age a thing by the newest file inside it, never by the folder's own timestamp or by the last commit date. A worktree whose last commit is old can hold edits from an hour ago.

## 1. Git worktrees

Repositories live under `C:\sources` (and siblings like `C:\sources\*-wt`). For each repository:

```powershell
Get-ChildItem C:\sources -Directory | Where-Object { Test-Path "$($_.FullName)\.git" } | ForEach-Object { "=== $($_.Name)"; git -C $_.FullName worktree list; git -C $_.FullName worktree prune --dry-run -v }
```

Worktrees can sit outside the repository: opencode keeps them in `~\.local\share\opencode\worktree\` and `%TEMP%\opencode\`, Claude Code in `<repo>\.claude\worktrees\`. For every worktree other than the main checkout, check before removing:

- newest file outside `.git` and `node_modules` (`Get-ChildItem -Recurse -File -Force`, sorted by `LastWriteTime`)
- uncommitted changes: `git -C <wt> status --porcelain`
- commits on no remote and not on main: `git -C <wt> log --oneline HEAD --not --remotes main`
- whether a running process uses it (an editable `pip install -e` or a long job started from that checkout): `Get-CimInstance Win32_Process | Select-Object ProcessId, CommandLine`

Remove only worktrees past the age with no uncommitted changes, no unpushed commits and no process using them, with `git worktree remove <path>` (then delete the branch if it holds nothing). Report the others and why they stayed. `git worktree prune` clears registrations whose folder is gone.

## 2. Agent scratchpads and temp folders

- Claude Code: `%LOCALAPPDATA%\Temp\claude\<project>\<session id>\`. Never touch the current session's folder (its id is in the scratchpad path of the system prompt), and leave any session folder written to today: another session may be running.
- Claude Code agent worktrees: `<repo>\.claude\worktrees\agent-<id>\`. Each is registered with git, so section 1 applies. One modified today usually belongs to a subagent that is still running.
- opencode: `%LOCALAPPDATA%\Temp\opencode\<name>\`. Its worktrees there are covered by section 1; check `git worktree list` output before deleting a folder that might be one.

Age each folder by its newest file.

Look in `~\.claude` too, but expect nothing to remove there. `projects` holds transcripts and memory (Claude Code expires transcripts itself through `cleanupPeriodDays`), `skills` and `plugins` are installed, and `backups`, `file-history` and `sessions` are Claude Code's own state. Old files in them are not leftovers.

## 3. Regenerable caches in repositories

Use the bundled scanner. It prunes `node_modules` and `.git` and finishes a large `C:\sources` in seconds:

```powershell
python -I "$HOME\.claude\skills\cleanup-leftovers\scripts\cache_scan.py" C:\sources "<scratchpad>\old-caches.txt" 2
```

Do not scan with `Get-ChildItem -Recurse -Include <names>` or `-Filter` over the repositories. It walks every `node_modules` tree and took more than an hour on this machine before it was stopped; the Python walk took seconds.

What the scanner counts as a cache: `.turbo`, `node_modules\.cache`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.vite`, `.parcel-cache`, `.nx`, `.eslintcache`.

Never treat these as caches:

- `.wrangler`: holds wrangler's local dev state, including local D1, KV and R2 data.
- `node_modules` itself, `.venv`, and build outputs (`bin`, `obj`, `dist`, `build`): costly to rebuild and sometimes hand-edited. Only on explicit request.
- anything tracked by git.

## Deleting

Delete path by path from the reviewed list, collecting failures instead of stopping at the first:

```powershell
$ok = 0; $fail = @(); foreach ($p in Get-Content <list>) { try { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction Stop; $ok++ } catch { $fail += "$p : $($_.Exception.Message)" } }; "removed $ok"; $fail
```

## Report

Per category: what was removed (count and size), what was kept and why (too recent, uncommitted changes, unpushed commits, in use, not a cache), and any deletion that failed.
