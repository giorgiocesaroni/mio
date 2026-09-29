-- Full record of a sandbox pipeline run: every stage's input and output, the
-- outcome, and the draft it produced. Only `via = 'sandbox'` runs write here,
-- so a QA run can be replayed and inspected from the database while the app's
-- real tables stay clean. `steps` is the streamed sequence of stage/done
-- objects, exactly as the sandbox UI shows them.

create table public.pipeline_runs (
  id uuid not null default gen_random_uuid(),
  created_at timestamp with time zone not null default now(),
  user_id uuid not null,
  day date,
  message text,
  outcome text,
  outcome_message text,
  total_ms integer,
  total_cost numeric,
  draft_id uuid,
  steps jsonb not null,
  constraint pipeline_runs_pkey primary key (id),
  constraint pipeline_runs_user_id_fkey foreign key (user_id) references auth.users(id),
  constraint pipeline_runs_draft_id_fkey foreign key (draft_id)
    references public.log_drafts(id) on delete set null
);

create index pipeline_runs_user_created_idx
  on public.pipeline_runs (user_id, created_at desc);

alter table public.pipeline_runs enable row level security;

create policy "Enable users to view their own data only"
  on public.pipeline_runs
  for select
  to authenticated
  using ((select auth.uid()) = user_id);
