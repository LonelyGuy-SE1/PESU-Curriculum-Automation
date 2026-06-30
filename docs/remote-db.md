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
- The finalized table is not implemented in this repo yet. Decide its schema before adding code that writes final approved curriculum data.

## Refined Table Schema

Run `docs/refined-submissions-schema.sql` in the Supabase SQL editor when rebuilding the refined table. It backs up the current table as `refined_submissions_backup`, creates the template-ready table, and backfills current refined rows.

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
