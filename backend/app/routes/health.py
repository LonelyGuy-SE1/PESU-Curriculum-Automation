from fastapi import APIRouter, HTTPException
from postgrest.exceptions import APIError

from app.services.errors import database_http_exception
from app.services.schema import schema_status

router = APIRouter()


@router.get("/health/schema")
def check_schema():
    try:
        status = schema_status()
    except APIError as exc:
        raise database_http_exception(exc) from exc
    if not status["ok"]:
        raise HTTPException(status_code=503, detail=status)
    return status
