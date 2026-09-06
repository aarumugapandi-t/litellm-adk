"""FastAPI application for LiteLLM ADK Visual Workflow Platform."""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .routes import workflows, executions, stream, metadata
from ..persistence.sqlite_workflow import workflow_store

STATIC_DIR = Path(__file__).parent / "static"


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await workflow_store.init_db()
    yield

def create_app() -> FastAPI:
    """Factory creating and configuring the LiteLLM ADK FastAPI server."""
    app = FastAPI(
        title="LiteLLM ADK Visual Workflow Platform",
        description="Visual AI workflow builder and execution engine powered by LiteLLM ADK.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes under /api/v1
    app.include_router(workflows.router, prefix="/api/v1")
    app.include_router(executions.router, prefix="/api/v1")
    app.include_router(stream.router, prefix="/api/v1")
    app.include_router(metadata.router, prefix="/api/v1")


    # Mount static assets if directory exists
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa_or_landing(full_path: str):
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            # If path points to an actual file in static, serve it
            target_path = STATIC_DIR / full_path
            if full_path and target_path.exists() and target_path.is_file():
                return FileResponse(str(target_path))
            return FileResponse(str(index_file))

        # Fallback developer landing page if frontend bundle not yet compiled
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>LiteLLM ADK Workflow Platform</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                .card { background: #1e293b; padding: 2.5rem; border-radius: 1rem; box-shadow: 0 10px 25px rgba(0,0,0,0.5); max-width: 540px; text-align: center; border: 1px solid #334155; }
                h1 { color: #38bdf8; font-size: 1.8rem; margin-bottom: 0.5rem; }
                p { color: #94a3b8; line-height: 1.6; margin-bottom: 1.5rem; }
                .btn { display: inline-block; background: #2563eb; color: #fff; padding: 0.75rem 1.5rem; border-radius: 0.5rem; text-decoration: none; font-weight: 600; transition: background 0.2s; }
                .btn:hover { background: #1d4ed8; }
                .badge { background: #0369a1; color: #bae6fd; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.85rem; font-weight: 500; }
            </style>
        </head>
        <body>
            <div class="card">
                <span class="badge">Backend Active</span>
                <h1>LiteLLM ADK Workflow Platform</h1>
                <p>The native FastAPI workflow engine and persistence services are online and ready to accept graph executions.</p>
                <a href="/docs" class="btn">Explore Interactive API Docs</a>
            </div>
        </body>
        </html>
        """)

    return app


app = create_app()
