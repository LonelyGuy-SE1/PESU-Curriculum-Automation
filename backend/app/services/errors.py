import sentry_sdk
from fastapi import HTTPException
from postgrest.exceptions import APIError


def database_http_exception(exc: APIError) -> HTTPException:
    message = str(exc)
    if "schema cache" in message and "Could not find the table" in message:
        return HTTPException(status_code=503, detail="Required database tables are missing. Run docs/schema.sql in Supabase.")
    sentry_sdk.capture_exception(exc)
    return HTTPException(status_code=500, detail="Database request failed.")
