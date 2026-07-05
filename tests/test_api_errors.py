from postgrest.exceptions import APIError

from app.services.errors import database_http_exception


def test_missing_schema_error_is_service_unavailable():
    error = APIError(
        {
            "message": "Could not find the table 'public.agent_document_drafts' in the schema cache",
            "code": "PGRST205",
        }
    )

    response = database_http_exception(error)

    assert response.status_code == 503
    assert response.detail == "Required database tables are missing. Run docs/schema.sql in Supabase."
