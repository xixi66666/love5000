import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import (
    ApiError,
    api_error_handler,
    http_exception_handler,
    internal_error_handler,
)
from app.api.v1 import admin, collections, daily_reports, health, last30days, repositories, stats
from app.core.config import settings
from app.core.scheduler import start_scheduler

# Windows registers .js/.mjs as text/plain, which breaks strict MIME checks for ES modules.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")

FRONTEND_DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = start_scheduler() if settings.scheduler_enabled else None
    yield
    if scheduler is not None:
        scheduler.shutdown()


app = FastAPI(title="Skill Finder API", lifespan=lifespan)


@app.get("/api/health")
async def service_health() -> dict[str, object]:
    return {"success": True, "service": "skill-finder"}


app.include_router(health.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(collections.router, prefix="/api/v1")
app.include_router(repositories.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(last30days.router, prefix="/api/v1")
app.include_router(daily_reports.router, prefix="/api/v1")

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, internal_error_handler)


# Serve the built frontend (frontend/dist) from the same origin as the API.
if (FRONTEND_DIST_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="frontend-assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")

    index_file = FRONTEND_DIST_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(
            status_code=503,
            detail=(
                "Frontend build not found. Run 'npm install && npm run build' in "
                "website/skill-finder/frontend first."
            ),
        )

    dist_root = FRONTEND_DIST_DIR.resolve()
    if full_path:
        candidate = (FRONTEND_DIST_DIR / full_path).resolve()
        try:
            candidate.relative_to(dist_root)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not Found")
        if candidate.is_file():
            return FileResponse(candidate)

    return FileResponse(index_file)
