"""Programmatic server launcher for the LiteLLM ADK visual workflow platform."""

import os
import uvicorn
from typing import Optional
from .app import create_app


def serve(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    workers: int = 1,
    database_url: Optional[str] = None,
    log_level: str = "info"
):
    """
    Starts the native visual workflow platform server.

    Example:
        >>> from litellm_adk.server import serve
        >>> serve(port=8000)
    """
    if database_url:
        os.environ["LITELLM_ADK_DB"] = database_url

    print(f"🚀 Starting LiteLLM ADK Workflow Platform on http://{host}:{port}")
    print(f"📖 API Documentation: http://{host}:{port}/docs")

    uvicorn.run(
        "litellm_adk.server.app:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level=log_level,
    )


if __name__ == "__main__":
    serve()
