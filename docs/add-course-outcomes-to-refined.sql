alter table refined_submissions
add column if not exists course_outcomes text[] not null default '{}';
