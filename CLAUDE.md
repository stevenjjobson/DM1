# DungeonMasterONE

AI-powered Dungeon Master application with GraphRAG memory, multi-agent orchestration, and D&D 5e gameplay.

## Project Structure

```
DM1/
├── backend/                    # Python 3.14 / FastAPI
│   ├── dm1/
│   │   ├── api/                # FastAPI app, routes, middleware, WebSocket
│   │   │   ├── main.py         # App factory (create_app)
│   │   │   ├── database.py     # MongoDB connection (motor async)
│   │   │   ├── auth.py         # JWT token creation/verification
│   │   │   ├── routes/         # auth.py, campaigns.py (more to come)
│   │   │   └── middleware/     # auth.py (get_current_user_id)
│   │   ├── agents/             # LangGraph agent definitions
│   │   ├── graph/              # Neo4j + Graphiti knowledge graph
│   │   ├── rules/              # D&D 5e rule engine (pure logic)
│   │   ├── providers/          # LLM, image, TTS, embedding wrappers
│   │   ├── models/             # Pydantic data models
│   │   ├── mcp/                # MCP-shaped tool schemas
│   │   └── config/             # Settings (pydantic-settings)
│   ├── tests/
│   └── pyproject.toml
├── frontend/                   # Next.js 16+ (App Router, TypeScript, Tailwind)
├── srd-data/                   # 5e-SRD-API JSON (committed)
├── docker-compose.yml          # Neo4j + MongoDB + Qdrant
├── .env.example
└── CLAUDE.md
```

## Commands

```bash
# Infrastructure
docker compose up -d                        # Start Neo4j, MongoDB, Qdrant
docker compose down                         # Stop services
docker compose down -v                      # Stop + delete volumes (⚠️ data loss)

# Backend
cd backend
uv venv && uv pip install -e ".[dev]"       # Install deps
uv run uvicorn dm1.api.main:app --reload    # Run API server (port 8000)
uv run pytest                               # Run tests
uv run ruff check dm1/                      # Lint

# Frontend
cd frontend
npm install                                 # Install deps
npm run dev                                 # Dev server (port 3000)
npm run build                               # Production build
```

## Conventions

- **Backend:** Python 3.14, async everywhere (motor, httpx, AsyncQdrantClient), Pydantic v2 for all data models
- **Auth:** JWT Bearer tokens, access token (30 min) + refresh token (7 days), bcrypt password hashing
- **Database:** MongoDB for user accounts + campaign metadata + LangGraph checkpoints. Neo4j for knowledge graph game state. Qdrant for vector embeddings.
- **API prefix:** All REST endpoints under `/api/` (e.g., `/api/auth/login`, `/api/campaigns`)
- **Testing:** pytest + pytest-asyncio, test against real Docker services
- **Linting:** ruff with line-length 120
- **Frontend:** Next.js App Router, TypeScript strict, Tailwind v4, Zustand for client state
- **No manual game state edits:** All game state flows through the knowledge graph via the Archivist agent

## MCP Server

ForgeNTT MCP tools are available (34 tools). Use `discover` for library overview, `get_project dungeonmasterone` for project context.

**Portfolios for focused sessions:**
- `portfolios/dm1-backend-development.md` — backend coding sessions
- `portfolios/dm1-frontend-development.md` — frontend coding sessions
- `portfolios/dm1-visual-pipeline.md` — image generation work

**Technology skills:** `/graphiti-patterns`, `/langgraph-workflow`, `/gemini-integration`, `/imagen-pipeline`, `/qdrant-integration`, `/lm-studio-fallback`, `/fastapi-websocket`, `/nextjs-patterns`, `/srd-data-patterns`, `/hume-voice`

## Development Workflow

Follow these conventions during every development session:

1. **Session start:** Load context based on session type:
   - Backend work: `get_portfolio portfolios/dm1-backend-development.md`
   - Frontend work: `get_portfolio portfolios/dm1-frontend-development.md`
   - Planning/cross-cutting: `get_project dungeonmasterone`
2. **During work:** Commit after each logical unit of work — don't batch to session end. Invoke relevant `/skill` when working on a specific technology module.
3. **After features:** Call `update_requirement` via MCP against the relevant requirement file when the work shifted that file's scope. No-op sessions don't need to write.
4. **Plan archival:** When a plan is approved via ExitPlanMode, archive it via `import_plan`. The harness's working storage is not the canonical record.
5. **Research:** Call `store_context` via MCP to save durable findings worth keeping across sessions.
6. **Session end:** Verify any approved plan from this session has been archived via `import_plan`. Build the project.
