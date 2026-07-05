from postgrest.exceptions import APIError

from app.supabase import supabase

REQUIRED_TABLES = (
    "submissions",
    "refined_submissions",
    "curriculum_versions",
    "finalized_submissions",
    "agent_document_drafts",
    "agent_drafts",
    "course_revision_history",
    "chat_sessions",
    "chat_messages",
    "chat_attachments",
)


def schema_status() -> dict:
    missing = []
    for table in REQUIRED_TABLES:
        try:
            supabase.table(table).select("id").limit(1).execute()
        except APIError as exc:
            if "schema cache" not in str(exc):
                raise
            missing.append(table)
    return {"ok": not missing, "missing_tables": missing, "required_tables": list(REQUIRED_TABLES)}
