from fastapi import APIRouter

from app.routes import agent, chat, health, preview, refined, submissions

router = APIRouter()

for route in (health, submissions, preview, refined, agent, chat):
    router.include_router(route.router)
