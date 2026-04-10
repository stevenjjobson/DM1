---
name: prd-design-session
description: "Problem-first design pattern for PRD sessions — from problem statement to update_requirement handoff (formerly update_prd, replaced April 2026)"
---

## When to Use

Designing a new feature, refining a PRD, or making architectural decisions before
handing off to Claude Code for implementation.

## Steps

1. **Start with the problem, not the solution.** State what's broken or missing before
   proposing anything. Force the problem statement to be precise — vague problems
   produce vague designs.

2. **Load relevant context** — current requirement files, constraints, and any prior
   decisions that bear on this feature. Use `get_project` if the project lives in
   ForgeNTT — it returns all six requirement files inline.

3. **Explore options with explicit tradeoffs.** Ask for 2-3 approaches and what each
   sacrifices. Avoid jumping to implementation details before the approach is settled.

4. **Draft or update the requirement section.** Once an approach is decided, write it
   into the relevant requirement file (intent, roadmap, stack, ui, behaviour, or
   architecture). Use `update_requirement` to commit the decision to the project record.

5. **Review for scope and feasibility.** Can this be built in one Claude Code session?
   If not, break it into phases. Design should produce implementable units.

6. **Capture the decision rationale.** Not just what was decided — why this over the
   alternatives. This is the first thing that degrades.

## Expected Outcome

An updated requirement file committed via `update_requirement`, a next-session plan
ready for `import_plan`, and captured decision rationale — so the implementation
session starts from a clear, agreed design with no ambiguity about what was decided
and why.

## Context to Include

- All six requirement files for the project (via `get_project`)
- Architecture constraints and key decisions already made
- Relevant knowledge files (patterns, guardrails)
- The most recent archived plan's Outcome section (what the previous session produced)
