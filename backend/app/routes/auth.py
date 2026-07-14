from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/auth/logout")
async def logout():
    return {"message": "Logged out"}


@router.get("/auth/check")
async def check_auth(request: Request):
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"authenticated": False}, status_code=401)
    return {"authenticated": True}