from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dm1.api.database import close_database, get_database
from dm1.api.routes import auth, campaigns, llm
from dm1.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure DB connection and indexes
    await get_database()
    yield
    # Shutdown: close DB connections
    await close_database()


def create_app() -> FastAPI:
    app = FastAPI(
        title="DungeonMasterONE",
        description="AI-Powered Dungeon Master API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(campaigns.router, prefix="/api")
    app.include_router(llm.router, prefix="/api")

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
