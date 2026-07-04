# Remote Database Access

This project uses Supabase as the remote database. The backend client is configured in `backend/app/supabase.py` and reads credentials from the repo root `.env` file.

## Required Access

Ask the project owner for:

- Supabase dashboard access.
- The backend `SUPABASE_URL`.
- The backend `SUPABASE_KEY`.

Keep these values in `.env` only. Do not commit credentials or paste them into frontend code.

## Current Data Flow

- `submissions` stores the raw form input.
- `refined_submissions` stores the template-ready refined fields used by the preview template.
- `agent_drafts` and `agent_document_drafts` store proposed AI changes before human approval.
- `finalized_submissions` and `curriculum_versions` store approved curriculum snapshots.

## Schema

Run `docs/schema.sql` in the Supabase SQL editor to create the public project tables. This file is schema-only: it does not rename tables, backfill data, or insert test rows.

## Read Data From Code

Run these commands from the repo root after `.env` is configured:

```bash
source .venv/bin/activate
cd backend
python3 - <<'PY'
from app.supabase import supabase

raw = supabase.table("submissions").select("id,course_title,status,semester").limit(5).execute()
refined = supabase.table("refined_submissions").select("id,submission_id,course_title,semester").limit(5).execute()

print("submissions")
print(raw.data)
print("refined_submissions")
print(refined.data)
PY
```
