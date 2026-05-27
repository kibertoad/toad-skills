---
name: kibertoad-review
description: Review a solution for bugs, implementation gaps, performance concerns, weak typing, low-value or redundant tests, and other code quality issues. Produces a prioritized list of findings with a recommendation on what to address.
---

# kibertoad-review

Review a solution for bugs, implementation gaps, performance concerns, weak typing, low-value or redundant tests, and other code quality issues. Produce a prioritized list of findings with a recommendation on what to address.

## Scope of review

Look for issues in each of these categories. Don't pad the report — if a category has nothing worth raising, omit it.

1. **Bugs** — incorrect behavior, off-by-one, wrong branches, race conditions, null/undefined hazards, broken error handling, swallowed exceptions, mishandled async, incorrect SQL/queries, wrong return values.
2. **Implementation gaps** — missing cases the requirements imply, unhandled inputs at real boundaries (user input, external APIs, untrusted data), missing cleanup/teardown, partial features the diff leaves half-finished.
3. **Performance concerns** — N+1 queries, unnecessary work inside hot loops, redundant allocations, blocking I/O on hot paths, missing indexes, unbounded memory growth, sync work that should be async (or vice versa). Flag only when it matters for this code's actual usage.
4. **Weak / low-quality types** — `any`, unjustified casts, overly wide unions, stringly-typed values where a discriminated union or enum fits, missing generics that force unsafe consumers, types that lie about what the function actually accepts or returns.
5. **Tests that don't earn their keep** — tests asserting on implementation details instead of behavior, tests that would pass even if the code under test were deleted, redundant duplicates of other tests, mocks so thorough the test no longer verifies anything real. Also flag *missing* tests for valuable behaviors the diff introduces or changes.
6. **Code quality / clear improvements** — duplicated logic that should be extracted, dead code, misleading names, comments explaining what the code already says, unnecessary abstractions, missing abstractions where three+ near-duplicates exist, inconsistent error handling, inconsistent style within the changed area.

## What to skip

- Style nits already enforced by the project's linter/formatter.
- Restating what the code does.

## How to investigate

- Read the diff first, then read enough surrounding code to judge whether each finding is real in context (callers, types, tests, config).
- Verify claims against the actual code — don't report bugs that depend on a misreading.

## Output format

Produce a single report in this shape. Keep each finding to 2–4 lines.

```
## Findings

### P0 — must fix before merge
- **[Category]** <one-line summary> — `path/to/file.ts:LINE`
  <what's wrong, why it matters, and the suggested fix in one or two sentences>

### P1 — should fix
- ...

### P2 — nice to have
- ...

## Recommendation
<2–4 sentences: which findings to address now, which to defer, and why. If the diff is in good shape, say so directly.>
```

Priority rubric:
- **P0** — correctness bug, security issue, data loss risk, or a gap that breaks a stated requirement.
- **P1** — meaningful quality/perf/typing/test issue that will bite later but isn't blocking.
- **P2** — small cleanup, naming, minor redundancy.

If there are no findings in a tier, omit that subsection. If there are zero findings overall, say so plainly in the recommendation and stop.

## Tone

Direct and specific. Quote file paths and line numbers. No hedging language ("might want to consider possibly…"). If you're uncertain, say *why* you're uncertain in one phrase and move on.
