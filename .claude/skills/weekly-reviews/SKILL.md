---
name: weekly-reviews
description: "Weekly review pattern — project triage, feed review, library health check, focus statement"
---

## When to Use

End of week or start of new week. Review progress across active projects, check
learning momentum, collect what needs attention next.

## Steps

1. **Review active projects.** For each project in ForgeNTT: what moved forward this
   week? What's stalled? Does the current plan still reflect reality?
   Use `get_project` for each active project.

2. **Check learning progress.** Open the learning files for Rust, Python, and context
   engineering. Did practice happen? Update current level or resources if they've changed.

3. **Scan feed items.** Review anything in `feeds/` collected during the week.
   Useful findings should be promoted to `knowledge/` or a project research file.
   Discard noise.

4. **Update project statuses.** If a requirement file's scope shifted this week (new
   shipped capability, blocker, decision), call `update_requirement` against the right
   file. If priorities have shifted, archive a fresh next-session plan via `import_plan`.

5. **Set next week's focus.** Pick one primary project and one secondary. Avoid spreading
   across too many things — momentum requires concentration.

## Expected Outcome

Updated requirement files where scope shifted, revised next-session plans where needed,
feed items either promoted to knowledge or trashed, and one focus statement for the week:
"This week: [primary]. Secondary: [secondary]."

## Context to Include

- All active project requirement files (`get_project` for each)
- Learning category files
- Recent feed items
- Calendar/commitments for the coming week (to set realistic scope)
