---
title: Environment Variables
layout: default
permalink: /environment/
---

# Environment Variables

Required backend (`/api` server, loaded from repo-root `.env`):

- `SUPABASE_URL`, `SUPABASE_KEY`
- `OPENROUTER_URL`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`

Optional:

- `CURRICULUM_YEAR` -- the active batch label (e.g. `2025-2026`)
- `OPENROUTER_FALLBACK_MODEL` -- backup model used when the primary model fails after retries (e.g. `google/gemma-3-27b-it:free`)
- `REDIS_URL` -- Upstash Redis URL for persistent caching (falls back to in-memory)
- `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE`

The frontend uses the public Supabase anon key directly in `shared/supabase-client.js`.