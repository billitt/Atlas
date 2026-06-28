"""FastAPI application factory and uvicorn entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import API_PORT, BIND_HOST, DEV_FRONTEND_ORIGIN
from api.runtime import boot_agent_runtime, shutdown_agent_servers
from api.routes.agents import router as agents_router
from api.routes.alerts import router as alerts_router
from api.routes.briefings import router as briefings_router
from api.routes.query import router as query_router
from api.routes.status import router as status_router
from api.routes.traces import router as traces_router
from observability.tracing import init_tracing, shutdown_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot specialist agents on startup; shut down on exit."""
    if os.getenv("OTEL_EXPORT_TO"):
        init_tracing()

    agent_cards, servers = await boot_agent_runtime()
    app.state.agent_cards = agent_cards
    app.state.agent_servers = servers

    try:
        yield
    finally:
        shutdown_agent_servers(servers)
        shutdown_tracing()


def create_app(*, production: bool = False) -> FastAPI:
    """Build the Atlas API application."""
    app = FastAPI(
        title="Atlas API",
        description="Streaming intelligence API over the Atlas synthesis graph.",
        lifespan=lifespan,
        docs_url=None if production else "/api/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[DEV_FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.get("/health")
    async def health_probe() -> dict[str, str]:
        """Unauthenticated liveness probe — no topology or secrets."""
        return {"status": "ok"}

    app.include_router(status_router, prefix="/api", tags=["status"])
    app.include_router(query_router, prefix="/api", tags=["query"])
    app.include_router(agents_router, prefix="/api", tags=["agents"])
    app.include_router(briefings_router, prefix="/api", tags=["briefings"])
    app.include_router(alerts_router, prefix="/api", tags=["alerts"])
    app.include_router(traces_router, prefix="/api", tags=["traces"])

    static_dir = Path(__file__).resolve().parent.parent / "web" / "dist"
    if production and static_dir.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


def main() -> None:
    """Run uvicorn bound to localhost only."""
    import uvicorn

    production = os.getenv("ATLAS_API_PRODUCTION", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    app = create_app(production=production)
    uvicorn.run(
        app,
        host=BIND_HOST,
        port=API_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
