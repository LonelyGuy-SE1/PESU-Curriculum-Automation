---
title: Database Schema
layout: default
permalink: /database-schema/
---

# Database Schema

Run `docs/schema.sql` in the Supabase SQL editor. Required tables:

`submissions`, `refined_submissions`, `curriculum_versions`, `finalized_submissions`,
`agent_drafts`, `agent_document_drafts`, `course_revision_history`, `chat_sessions`,
`chat_messages`, `chat_attachments`, `specialization_definitions`,
`course_specialization_assignments`.

## Course Status Lifecycle

```
submissions.status:    pending  ->  refined
refined_submissions:   draft    ->  refined  ->  archived
agent_drafts:          proposed ->  applied
                       blocked  ->  proposed (on user edit)
chat_sessions:         active   ->  archived
```

## Key Columns on `refined_submissions`

`course_code, course_title, semester, credit_category, program, lecture_hours, tutorial_hours, practical_hours, self_study, credits, course_type, is_elective, visible, units (jsonb), objectives/text_books/... (arrays), status`.

`visible` (default `true`) controls whether a course renders in preview/PDF output. Toggle it from the course management page. Hidden courses stay in the database and remain editable but are excluded from every rendered document.

Verify with `GET /api/health/schema`.

## Table Relationships

```
refined_submissions (1) ----< (N) agent_drafts
refined_submissions (1) ----< (N) course_revision_history
curriculum_versions (1) ----< (N) finalized_submissions
agent_document_drafts (1) ----< (N) agent_drafts
chat_sessions (1) ----< (N) chat_messages
chat_sessions (1) ----< (N) chat_attachments
specialization_definitions (1) ----< (N) course_specialization_assignments
refined_submissions (1) ----< (N) course_specialization_assignments
```

## Specialization Tables

- `specialization_definitions` -- one row per track: `id, semester, letter (A/B/C...), name, key (SCC/MIDS/CSCS), academic_year`
- `course_specialization_assignments` -- one row per (course, track) membership: `id, refined_id, specialization_id`
- `refined_submissions.is_elective` -- boolean flag marking a course as an elective