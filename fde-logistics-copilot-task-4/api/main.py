"""FastAPI application factory for the Operations Copilot.

Run it with::

    uvicorn api.main:app --reload      # http://127.0.0.1:8000/docs

This layer is optional.  It exists to show how the same agent and tools are
exposed to other systems (a web UI, Slack/Teams bots, the client's portal)
without duplicating any business logic.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.routes import router
from core.config import (
    AGENT_MODE,
    API_HOST,
    API_PORT,
    API_TITLE,
    APP_NAME,
    APP_VERSION,
    ENVIRONMENT,
)
from core.exceptions import CopilotError, ValidationError
from core.logging_config import get_logger

logger = get_logger("copilot.api")

DESCRIPTION = """
Operations Copilot for logistics teams.

One natural language endpoint (`POST /api/v1/copilot/query`) plus explicit
capability endpoints for systems that already know what they want.
"""


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title=API_TITLE,
        description=DESCRIPTION,
        version=APP_VERSION,
        contact={"name": "Forward Deployment Engineering"},
    )

    @app.get("/health", tags=["monitoring"], summary="Liveness / readiness probe")
    def health() -> Dict[str, Any]:
        """Return service health - used by load balancers and Kubernetes."""
        return {
            "status": "ok",
            "app": APP_NAME,
            "version": APP_VERSION,
            "environment": ENVIRONMENT,
            "agent_mode": AGENT_MODE,
        }

    @app.exception_handler(ValidationError)
    def handle_validation_error(request: Request, exc: ValidationError) -> JSONResponse:
        """Map domain validation errors onto HTTP 400."""
        logger.warning("validation error on %s: %s", request.url.path, exc)
        return JSONResponse(status_code=400, content={"detail": str(exc), "error_type": "validation_error"})

    @app.exception_handler(CopilotError)
    def handle_copilot_error(request: Request, exc: CopilotError) -> JSONResponse:
        """Map any other domain error onto HTTP 500 without leaking internals."""
        logger.error("copilot error on %s: %s", request.url.path, exc)
        return JSONResponse(status_code=500, content={"detail": str(exc), "error_type": "copilot_error"})

    app.include_router(router)
    logger.info("%s v%s API initialised (env=%s)", APP_NAME, APP_VERSION, ENVIRONMENT)
    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover - manual run helper
    import uvicorn

    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, reload=True)
