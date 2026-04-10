---
name: claude-code-project-setup
description: "Step-by-step setup pattern for integrating Claude Code with a new project via ForgeNTT MCP — covers CLAUDE.md, .mcp.json, settings.local.json with SessionStart hook, full tool permissions, project creation, and verification."
---

# Claude Code Project Setup

A step-by-step pattern for integrating Claude Code with a new project using ForgeNTT's MCP server.

## When to Use

- Starting a new software project that will have regular Claude Code sessions
- Onboarding an existing project to the ForgeNTT context management workflow
- After reinstalling ForgeNTT or setting up on a new machine
- When a project lacks structured context delivery and sessions feel inconsistent

## Prerequisites

- ForgeNTT desktop app installed and library initialized
- MCP server built: `cd mcp-server && npm run build`
- Node.js available on system PATH

## Steps

### 1. Create CLAUDE.md in your project root

This is the primary instructions file Claude Code reads every session. Include:

- **Tech stack** — languages, frameworks, databases, build tools
- **Project structure** — directory layout, key files
- **Architecture rules** — patterns to follow, anti-patterns to avoid
- **Build commands** — how to build, test, lint, deploy
- **Conventions** — naming, file organization, error handling
- **MCP Server section** — reference to ForgeNTT MCP tools available
- **Development Workflow section** — when to use MCP tools (see `patterns/mcp-development-workflow.md`)

### 2. Create .mcp.json in your project root

Register the ForgeNTT MCP server for VS Code's Claude Code extension:

```json
{
  "mcpServers": {
    "forgentt": {
      "command": "node",
      "args": ["<absolute-path-to>/ForgeNTT/mcp-server/dist/index.js"]
    }
  }
}
```

### 3. Create .claude/settings.local.json

Pre-approve all ForgeNTT MCP tools and git operations so Claude Code doesn't prompt for each one:

```json
{
  "permissions": {
    "allow": [
      "mcp__forgentt__discover",
      "mcp__forgentt__search",
      "mcp__forgentt__list",
      "mcp__forgentt__read",
      "mcp__forgentt__get_portfolio",
      "mcp__forgentt__get_project",
      "mcp__forgentt__get_backlinks",
      "mcp__forgentt__get_schema",
      "mcp__forgentt__create_from_template",
      "mcp__forgentt__store_context",
      "mcp__forgentt__import_plan",
      "mcp__forgentt__update_requirement",
      "mcp__forgentt__update_file",
      "mcp__forgentt__create_file",
      "mcp__forgentt__delete_file",
      "mcp__forgentt__rename_file",
      "mcp__forgentt__move_file",
      "mcp__forgentt__create_category",
      "mcp__forgentt__delete_category",
      "mcp__forgentt__create_portfolio",
      "mcp__forgentt__modify_portfolio",
      "mcp__forgentt__list_templates",
      "mcp__forgentt__create_template",
      "mcp__forgentt__update_template",
      "mcp__forgentt__delete_template",
      "mcp__forgentt__create_project",
      "mcp__forgentt__get_quality",
      "mcp__forgentt__get_broken_references",
      "mcp__forgentt__fix_reference",
      "mcp__forgentt__ingest_feed",
      "mcp__forgentt__scaffold_claude_code",
      "mcp__forgentt__sync_agents",
      "mcp__forgentt__sync_skills",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git status:*)",
      "Bash(git diff:*)"
    ]
  },
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo SESSION START: Load project context with get_project. Load relevant portfolio with get_portfolio. Review the latest plan for continuity. Check git log --oneline -10 for current repo state."
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo BEFORE COMPACTING: Archive any active plan via import_plan with an Outcome section recapping the session. Call update_requirement on any requirement file whose scope shifted. Commit any uncommitted work."
          }
        ]
      }
    ]
  }
}
```

**Note on hooks:** SessionStart and PreCompact hooks can only echo reminders — they cannot call MCP tools directly. Treat the echo output as a checklist of MCP calls to make manually at that point in the session.

### 4. Create a ForgeNTT project

In Claude Desktop or Claude Code, use the MCP tool:
```
create_project("my-project-name")
```

Then link the dev repo in the PRD frontmatter:
```yaml
dev_repo: "C:\\path\\to\\your\\project"
```

### 5. Create a portfolio for the project

Bundle relevant context files into a portfolio:
```
create_portfolio("My Project Context", includes: ["identity/professional-context.md", "patterns/mcp-development-workflow.md", ...])
```

## Verification

1. Open VS Code in the project directory
2. Start Claude Code — it should read CLAUDE.md automatically
3. SessionStart hook fires — prints context loading checklist
4. Try an MCP tool: `discover` — should execute without permission prompt
5. Try `git status` — should execute without permission prompt
6. Trigger context compaction — PreCompact hook should print state-saving checklist

## Expected Outcome

- Claude Code reads CLAUDE.md on session start with no manual prompt injection
- SessionStart hook reminds Claude to call `get_project` and `get_portfolio` every session
- All ForgeNTT MCP tools execute without individual permission prompts
- `get_project` loads structured project context in under 2 seconds
- Git operations (add, commit, status, diff) run without approval prompts
- PreCompact hook fires before context compaction, reminding Claude to save session state via `import_plan` (with an Outcome section) and `update_requirement` for any scope-shifted requirement files
