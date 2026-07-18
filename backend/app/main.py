import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
if sentry_dsn:
    sentry_config = {"dsn": sentry_dsn, "environment": os.getenv("SENTRY_ENVIRONMENT", "").strip() or "production"}
    sentry_release = os.getenv("SENTRY_RELEASE", "").strip()
    if sentry_release:
        sentry_config["release"] = sentry_release
    sentry_sdk.init(**sentry_config)

from app.api import router
from app.routes.auth import router as auth_router


def frontend_directory():
    app_root = Path(__file__).resolve().parents[1]
    candidates = (
        app_root / "frontend",
        app_root.parent / "frontend",
        app_root.parent.parent / "frontend",
        Path("/frontend"),
    )
    return next((path for path in candidates if path.exists()), None)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.routes.preview import preload_pdfs
    preload_pdfs()
    yield
    from app import cache
    cache.close()


app = FastAPI(title="PESU Curriculum Automation", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(auth_router, prefix="/api")

frontend_dir = frontend_directory()
if not frontend_dir:
    raise RuntimeError("Frontend directory not found")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
