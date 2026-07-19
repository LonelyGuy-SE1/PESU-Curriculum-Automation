import logging

import sentry_sdk
from fastapi import HTTPException
from postgrest.exceptions import APIError

logger = logging.getLogger(__name__)


def database_http_exception(exc: APIError) -> HTTPException:
    message = str(exc)
    if "schema cache" in message and "Could not find the table" in message:
        return HTTPException(status_code=503, detail="Required database tables are missing. Run docs/schema.sql in Supabase.")
    logger.error("Supabase APIError: %s", message)
    sentry_sdk.capture_exception(exc)
    return HTTPException(status_code=500, detail=f"Database request failed: {message[:200]}")
