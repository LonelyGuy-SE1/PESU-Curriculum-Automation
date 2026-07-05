import os
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
if sentry_dsn:
    sentry_sdk.init(dsn=sentry_dsn)

from app.api import router

app = FastAPI(title="PESU Curriculum Automation")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

if Path("../frontend").exists():
    app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
