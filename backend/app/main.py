from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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