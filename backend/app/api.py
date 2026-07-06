from fastapi import APIRouter

from app.routes import agent, chat, courses, health, preview, refined, submissions, versions

router = APIRouter()

for route in (health, submissions, preview, refined, agent, chat, versions, courses):
    router.include_router(route.router)
