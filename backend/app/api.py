from fastapi import APIRouter

from app.routes import agent, chat, health, preview, refined, submissions, versions

router = APIRouter()

for route in (health, submissions, preview, refined, agent, chat, versions):
    router.include_router(route.router)
