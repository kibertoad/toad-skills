# toad-skills

A collection of Claude Code skills.

## Available skills

- [`kibertoad-review`](./kibertoad-review/SKILL.md) — Review a solution for bugs, gaps, perf concerns, weak types, low-value tests, and quality issues; produces a prioritized list and a recommendation.
- [`bulk-review`](./bulk-review/SKILL.md) — Review every open non-draft PR without the `reviewed` label a few at a time, each in its own worktree: run `/code-review high --fix`, settle unaddressed review comments, push the fixes, update the description, label the PR and resolve its conflicts.
- [`bulk-inline-review`](./bulk-inline-review/SKILL.md) — Review every open non-draft PR without the `inline-reviewed` label and post the findings as inline comments on the diff. Changes no code.
- [`bulk-resolve-conflicts`](./bulk-resolve-conflicts/SKILL.md) — Merge the base into every open PR that conflicts with it, resolve the conflicts keeping both sides' intent, push, and fix red CI until it is green.
- [`cleanup-leftovers`](./cleanup-leftovers/SKILL.md): Find stale git worktrees, agent scratchpads and temp folders, and regenerable tool caches older than a given age, check that nothing is uncommitted, unpushed or in use, and remove them. Written for Windows.

## Installing a skill locally

Claude Code looks for skills in two places:

- **User scope** (available in every project): `~/.claude/skills/<skill-name>/SKILL.md`
- **Project scope** (only in that repo): `<repo>/.claude/skills/<skill-name>/SKILL.md`

Each skill in this repo is a directory containing a `SKILL.md`. To install one, copy or symlink its directory into the target `skills` folder.

### macOS / Linux

User scope:

```sh
mkdir -p ~/.claude/skills
cp -r kibertoad-review ~/.claude/skills/
```

Or symlink so updates from `git pull` are picked up automatically:

```sh
ln -s "$(pwd)/kibertoad-review" ~/.claude/skills/kibertoad-review
```

Project scope (run from inside the target project):

```sh
mkdir -p .claude/skills
ln -s /path/to/toad-skills/kibertoad-review .claude/skills/kibertoad-review
```

### Windows (PowerShell)

User scope:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
Copy-Item -Recurse .\kibertoad-review "$env:USERPROFILE\.claude\skills\"
```

Or symlink (requires Developer Mode or an elevated shell):

```powershell
New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.claude\skills\kibertoad-review" `
  -Target "$PWD\kibertoad-review"
```

Project scope (run from inside the target project):

```powershell
New-Item -ItemType Directory -Force .\.claude\skills | Out-Null
New-Item -ItemType SymbolicLink `
  -Path .\.claude\skills\kibertoad-review `
  -Target C:\path\to\toad-skills\kibertoad-review
```

## Verifying the install

Start Claude Code in any project and type `/`. The skill should appear in the list (e.g. `/kibertoad-review`). Invoke it the same way you would any other slash command.

If it doesn't show up, check that:

- The directory name and the `name:` field in `SKILL.md` match.
- The file is named `SKILL.md` (uppercase).
- The path is `<scope>/skills/<skill-name>/SKILL.md`, not nested deeper.

## Uninstalling

Delete the skill directory (or remove the symlink) from `~/.claude/skills/` or `<repo>/.claude/skills/`.
