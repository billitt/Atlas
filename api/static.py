"""Production static file serving with SPA fallback."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_production_ui(app: FastAPI, static_dir: Path) -> None:
    """Serve the built Vite bundle from the same origin with client-route fallback."""
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    index_file = static_dir / "index.html"

    @app.get("/")
    async def spa_index() -> FileResponse:
        if not index_file.is_file():
            raise HTTPException(status_code=503, detail="UI bundle not built")
        return FileResponse(index_file)

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path in {"health", "docs", "openapi.json"}:
            raise HTTPException(status_code=404)
        candidate = static_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        if not index_file.is_file():
            raise HTTPException(status_code=503, detail="UI bundle not built")
        return FileResponse(index_file)
