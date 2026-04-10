---
name: mcp-development-workflow
description: "Four-phase session lifecycle for AI-assisted development with ForgeNTT MCP — context loading, requirement updates via update_requirement, plan archival via import_plan, and session-end checks. The plan archive replaced log.md and append_log in April 2026."
---

## When to Use

Use this workflow for any AI-assisted development session with ForgeNTT MCP tools.
Start here whenever beginning a coding session, planning session, or library curation
task using Claude Code or Claude Desktop with the forgentt project loaded.

## Steps

### Phase 1: Session Start
1. **Load project context:** `get_project <name>` — loads the six requirement files (intent, roadmap, stack, ui, behaviour, architecture), recent plans, recent git history, dev_repo path, and portfolio paths
2. **Review library state:** `discover` — overview of categories, portfolios, projects, health
3. **Load relevant portfolio:** `get_portfolio <name>` — bundles relevant context files
4. **Review the most recent archived plan:** It's the canonical cross-session continuity record (carries the previous session's Outcome section)

### Phase 2: During Work
5. **Commit frequently:** After each logical unit of work (feature, fix, refactor), not at session end
6. **Track milestones in the active plan:** Build up the plan's Outcome section as you go — this carries the session narrative forward via `import_plan` at session end
7. **Save findings:** `store_context` type=finding for research discoveries, design decisions, or observations worth preserving
8. **Verify quality:** After major refactors, run `get_quality` and `get_broken_references` to catch regressions

### Phase 3: After Features
9. **Update requirements:** `update_requirement` after significant feature additions or architectural changes — pick the right requirement file (intent, roadmap, stack, ui, behaviour, or architecture) for the scope that shifted
10. **Update files:** `update_file` to promote draft documents to active, update tags, fix descriptions

### Phase 4: Session End
11. **Build the Outcome section into the plan archive:** Capture what was accomplished, key decisions, issues found, and next priorities as the Outcome section of the plan you'll archive next. This is the primary cross-session continuity mechanism — do not skip it for significant sessions.
12. **Archive plan:** `import_plan` with session progress (Outcome section) and next-session priorities
13. **Build:** Run the project's build command to verify everything compiles
14. **Final commit:** Ensure all changes are committed

## Expected Outcome

A well-logged session with a structured summary captured in the archived plan's
Outcome section (via `import_plan`), committed changes, updated requirement files
(if applicable, via `update_requirement`), and a fresh next-session plan — so the
next session can resume without losing context or progress.

## Tool Quick Reference

| When | Tool | Purpose |
|---|---|---|
| Need project context | `get_project` | Load six requirement files, plans, git history |
| Need library overview | `discover` | Categories, portfolios, health |
| Need bundled context | `get_portfolio` | All files in a package |
| Found something worth saving | `store_context` type=finding | Persist durable research finding |
| End of session (any size) | `import_plan` | Archive plan with Outcome section for cross-session continuity |
| Made architectural change | `update_requirement` | Update the matching requirement file (intent/roadmap/stack/ui/behaviour/architecture) |
| Edit existing file | `update_file` | Change content or frontmatter |
| Check library health | `get_quality` | Scores per file |
| Find broken links | `get_broken_references` | Dead file references |
| Check what references a file | `get_backlinks` | Safety check before delete/rename |
| Deploy agents to Claude Code | `sync_agents` | Copy agent definitions to .claude/agents/ |
| Deploy skills to Claude Code | `sync_skills` | Copy skill definitions to .claude/skills/ |

## Anti-Patterns

- Don't batch all commits to session end — commit after each logical unit
- Don't skip `import_plan` Outcome section — next session loses structured context about what happened and continuity on priorities
- Don't update requirement files for minor changes — only when the file's scope actually shifted (each requirement file's body has its own Update Contract describing scope)
- Don't create files via direct filesystem writes — use MCP tools for frontmatter and git
- Don't ignore the PreCompact hook reminder — save state before context loss
- Don't put session summaries in research/ — they belong in the plan archive's Outcome section, not as standalone research files
