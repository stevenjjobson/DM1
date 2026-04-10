---
name: claude-code-prd-session
description: "Six-step pattern for starting a Claude Code implementation session — load context, check git state, pick the next increment, build iteratively, verify, and log."
---

## When to Use

Starting a new Claude Code session to implement features from an existing PRD or plan.

## Steps

1. **Load project context** — run `get_project` at session start, not mid-session.
   Read the PRD, the most recent plan, and the activity log before writing any code.

2. **Establish current state** — check `git log --oneline -10` and `git status`.
   Understand what changed since the last session before touching anything.

3. **Identify the next increment** — pick the smallest verifiable unit from the plan.
   Resist the pull to start multiple things. One thing at a time, verified before moving on.

4. **Implement iteratively** — commit working increments. Don't accumulate uncommitted work.
   Commit messages should describe what changed and why, not just "updates."

5. **Verify before ending** — run the build. If there are tests, run them. Don't leave a
   broken build for the next session.

6. **Log and plan** — use the `import_plan` Outcome section to record what was done as
   part of archiving the next session's priorities while the context is still fresh.

## Expected Outcome

A committed, building increment with an archived plan (carrying the session's Outcome)
for the next session — so context is never lost between sessions and each session starts
from a known, clean state.

## Context to Include

- Project PRD (`get_project`)
- `CLAUDE.md` if present in the repo
- Recent git history (last 5-10 commits)
- The specific files being modified (not the whole codebase)

## Common Pitfalls

- **Skipping `get_project` at session start** — leads to implementing against stale context
- **Scope creep within a session** — one feature becomes three; none are finished
- **Not committing incrementally** — hard to recover from mid-session breakage
- **Ending without a plan** — next session starts from scratch on priorities
