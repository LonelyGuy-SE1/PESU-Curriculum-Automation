create table if not exists submissions (
  id bigint generated always as identity primary key,
  faculty_email text not null,
  course_title text not null,
  course_code text not null,
  offering_department text not null default 'CS',
  target_department text not null default 'CSE',
  semester int not null default 1,
  credit_category text not null default '4',
  raw_course_content text not null,
  text_books text not null default '',
  reference_books text not null default '',
  preferred_tools text not null default '',
  status text not null default 'pending',
  created_at timestamptz default now()
);

-- Refined / template-ready courses
create table if not exists refined_submissions (
  id bigint generated always as identity primary key,
  submission_id bigint references submissions(id),
  faculty_email text not null default '',
  course_title text not null default '',
  course_code text not null default '',
  offering_department text not null default 'CS',
  target_department text not null default 'CSE',
  semester int not null default 1,
  credit_category text not null default '4',
  program text not null default 'B. TECH',
  lecture_hours int not null default 0,
  tutorial_hours int not null default 0,
  practical_hours int not null default 0,
  self_study int not null default 0,
  credits int not null default 0,
  course_type text not null default '',
  is_elective boolean not null default false,
  visible boolean not null default true,
  units jsonb not null default '[]'::jsonb,
  objectives text not null default '',
  course_outcomes text not null default '',
  text_books text not null default '',
  reference_books text not null default '',
  lab_experiments text not null default '',
  tools_languages text not null default '',
  raw_course_content text not null default '',
  status text not null default 'refined',
  created_at timestamptz default now()
);

-- Specialization track definitions (e.g. SCC, MIDS, CSCS for semesters 5 & 6)
create table if not exists specialization_definitions (
  id bigint generated always as identity primary key,
  semester int not null,
  letter text not null,
  name text not null,
  key text not null,
  academic_year text not null default '',
  created_at timestamptz default now()
);

-- Which electives belong to which specialization tracks
create table if not exists course_specialization_assignments (
  id bigint generated always as identity primary key,
  refined_id bigint references refined_submissions(id) on delete cascade,
  specialization_id bigint references specialization_definitions(id) on delete cascade,
  created_at timestamptz default now(),
  unique (refined_id, specialization_id)
);

-- Curriculum version snapshots
create table if not exists curriculum_versions (
  id bigint generated always as identity primary key,
  name text not null default '',
  program text not null default '',
  academic_year text not null default '',
  status text not null default 'draft',
  created_at timestamptz default now()
);

-- Course snapshots within a version
create table if not exists finalized_submissions (
  id bigint generated always as identity primary key,
  curriculum_version_id bigint references curriculum_versions(id) on delete cascade,
  refined_id bigint references refined_submissions(id),
  course_json jsonb not null default '{}'::jsonb,
  created_at timestamptz default now()
);

-- Revision history for applied drafts
create table if not exists course_revision_history (
  id bigint generated always as identity primary key,
  refined_id bigint references refined_submissions(id),
  draft_id bigint,
  old_json jsonb not null default '{}'::jsonb,
  new_json jsonb not null default '{}'::jsonb,
  created_at timestamptz default now()
);

-- Agent-proposed course drafts
create table if not exists agent_drafts (
  id bigint generated always as identity primary key,
  refined_id bigint references refined_submissions(id),
  document_draft_id bigint,
  base_refined_json jsonb not null default '{}'::jsonb,
  proposed_json jsonb not null default '{}'::jsonb,
  json_patch jsonb not null default '[]'::jsonb,
  diff_summary jsonb not null default '{}'::jsonb,
  change_reason text not null default '',
  status text not null default 'proposed',
  created_at timestamptz default now()
);

-- Agent-proposed document drafts (multi-course)
create table if not exists agent_document_drafts (
  id bigint generated always as identity primary key,
  curriculum_version_id bigint,
  uploaded_document_id text not null default '',
  diff_summary jsonb not null default '{}'::jsonb,
  change_reason text not null default '',
  status text not null default 'proposed',
  created_at timestamptz default now()
);

-- Chat sessions
create table if not exists chat_sessions (
  id bigint generated always as identity primary key,
  refined_id bigint,
  document_draft_id bigint,
  title text not null default '',
  status text not null default 'active',
  created_at timestamptz default now()
);

-- Chat messages
create table if not exists chat_messages (
  id bigint generated always as identity primary key,
  session_id bigint references chat_sessions(id) on delete cascade,
  role text not null default 'user',
  content text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz default now()
);

-- Chat attachments (files, reports)
create table if not exists chat_attachments (
  id bigint generated always as identity primary key,
  session_id bigint references chat_sessions(id) on delete cascade,
  message_id bigint,
  filename text not null default '',
  content_type text not null default '',
  size_bytes bigint not null default 0,
  extracted_text text not null default '',
  content_base64 text not null default '',
  status text not null default 'pending',
  error text not null default '',
  created_at timestamptz default now()
);
