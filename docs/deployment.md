---
title: Deployment
layout: default
permalink: /deployment/
---

# Deployment

## Backend (HF Spaces)

Docker image runs `uvicorn app.main:app --host 0.0.0.0 --port 7860` (HF Space).

`.github/workflows/sync-to-hub.yml` syncs `main` to the HF Space.

Required HF Space secrets:
- `SUPABASE_URL`, `SUPABASE_KEY`
- `OPENROUTER_URL`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`
- `OPENROUTER_FALLBACK_MODEL` (recommended)
- `REDIS_URL` (optional)
- `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE` (optional)

## Frontend (Vercel)

Static hosting with `frontend/vercel.json` rewriting `/api/*` to the backend.

Required Vercel environment variables:
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (public anon key)

## CI (`.github/workflows/ci.yml`)

Runs on push/PR: checkout, Python 3.12, pip install (cached), `apt-get install poppler-utils`, `pytest`, `python -m compileall backend/app`.

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd backend && fastapi dev app/main.py
```

Server at `http://127.0.0.1:8000`. API under `/api`. Frontend served from `frontend/`.

```bash
source .venv/bin/activate
pytest                              # all tests
python -m compileall backend/app    # also runs in CI
```