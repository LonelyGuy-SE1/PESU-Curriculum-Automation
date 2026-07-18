## Table `submissions`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary |
| `created_at` | `timestamptz` |  Nullable |
| `status` | `text` |  Nullable |
| `faculty_email` | `text` |  |
| `course_title` | `text` |  |
| `offering_department` | `text` |  |
| `target_department` | `text` |  |
| `semester` | `text` |  |
| `credit_category` | `text` |  |
| `raw_course_content` | `text` |  |
| `text_books` | `text` |  |
| `reference_books` | `text` |  Nullable |
| `preferred_tools` | `text` |  Nullable |

## Table `refined_submissions_backup`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary |
| `submission_id` | `int8` |  Nullable |
| `semester` | `int4` |  |
| `course_code` | `text` |  Nullable |
| `course_title` | `text` |  |
| `refined_content` | `text` |  |
| `prelude` | `text` |  Nullable |
| `objectives` | `jsonb` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

## Table `refined_submissions`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `submission_id` | `int8` |  Unique |
| `semester` | `int4` |  |
| `course_code` | `text` |  |
| `course_title` | `text` |  |
| `program` | `text` |  |
| `lecture_hours` | `int4` |  |
| `tutorial_hours` | `int4` |  |
| `practical_hours` | `int4` |  |
| `self_study` | `int4` |  |
| `credits` | `int4` |  |
| `course_type` | `text` |  |
| `tools_languages` | `text` |  |
| `desirable_knowledge` | `text` |  |
| `prelude` | `text` |  |
| `objectives` | `_text` |  |
| `units` | `jsonb` |  |
| `lab_experiments` | `_text` |  |
| `text_books` | `_text` |  |
| `reference_books` | `_text` |  |
| `status` | `text` |  |
| `created_at` | `timestamptz` |  |
| `updated_at` | `timestamptz` |  |
| `course_outcomes` | `_text` |  |

## Table `curriculum_versions`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `name` | `text` |  |
| `program` | `text` |  |
| `academic_year` | `text` |  |
| `status` | `text` |  |
| `created_at` | `timestamptz` |  |
| `updated_at` | `timestamptz` |  |

## Table `finalized_submissions`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `curriculum_version_id` | `int8` |  |
| `refined_id` | `int8` |  |
| `course_json` | `jsonb` |  |
| `created_at` | `timestamptz` |  |
| `updated_at` | `timestamptz` |  |

## Table `agent_document_drafts`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `curriculum_version_id` | `int8` |  Nullable |
| `uploaded_document_id` | `text` |  |
| `diff_summary` | `jsonb` |  |
| `change_reason` | `text` |  |
| `status` | `text` |  |
| `created_at` | `timestamptz` |  |
| `updated_at` | `timestamptz` |  |

## Table `agent_drafts`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `refined_id` | `int8` |  |
| `document_draft_id` | `int8` |  Nullable |
| `base_refined_json` | `jsonb` |  |
| `proposed_json` | `jsonb` |  |
| `json_patch` | `jsonb` |  |
| `diff_summary` | `jsonb` |  |
| `change_reason` | `text` |  |
| `status` | `text` |  |
| `created_at` | `timestamptz` |  |
| `updated_at` | `timestamptz` |  |

## Table `course_revision_history`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `refined_id` | `int8` |  |
| `agent_draft_id` | `int8` |  Nullable |
| `source` | `text` |  |
| `previous_json` | `jsonb` |  |
| `next_json` | `jsonb` |  |
| `json_patch` | `jsonb` |  |
| `diff_summary` | `jsonb` |  |
| `change_reason` | `text` |  |
| `changed_by` | `text` |  |
| `created_at` | `timestamptz` |  |

## Table `chat_sessions`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `refined_id` | `int8` |  Nullable |
| `document_draft_id` | `int8` |  Nullable |
| `title` | `text` |  |
| `status` | `text` |  |
| `created_at` | `timestamptz` |  |
| `updated_at` | `timestamptz` |  |

## Table `chat_messages`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `session_id` | `int8` |  |
| `role` | `text` |  |
| `content` | `text` |  |
| `metadata` | `jsonb` |  |
| `created_at` | `timestamptz` |  |

## Table `chat_attachments`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `session_id` | `int8` |  |
| `message_id` | `int8` |  Nullable |
| `filename` | `text` |  |
| `content_type` | `text` |  |
| `size_bytes` | `int4` |  |
| `extracted_text` | `text` |  |
| `status` | `text` |  |
| `error` | `text` |  |
| `created_at` | `timestamptz` |  |
| `content_base64` | `text` |  |

## Table `specialization_definitions`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `semester` | `int4` |  |
| `letter` | `text` |  |
| `name` | `text` |  |
| `key` | `text` |  |
| `academic_year` | `text` |  |
| `created_at` | `timestamptz` |  Nullable |

## Table `course_specialization_assignments`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `refined_id` | `int8` |  Nullable |
| `specialization_id` | `int8` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

