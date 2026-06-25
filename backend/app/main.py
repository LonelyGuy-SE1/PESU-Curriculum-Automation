#run using uv run fastapi dev 

from fastapi import FastAPI
from app.api import router
#from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


app=FastAPI(title="PESU Curriculum Automation")
"""
app.add_middleware(
    CORSMiddleware,
     allow_origins=["*"],
     allow_methods=["*"],
     allow_headers=["*"],
)"""

app.include_router(router, prefix="/api")       

app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")