-- Drafts produced by the structured logging pipeline. A draft holds the
-- proposed log entries until the user confirms (or edits, or discards) them,
-- so nothing reaches `logs` without review. `rows` is owned by the backend:
-- each row carries its chosen target plus the alternatives the user may pick
-- from, so edits never introduce ids the pipeline didn't retrieve.

create type public.log_draft_status as enum ('pending', 'confirmed', 'discarded');

create table public.log_drafts (
  id uuid not null default gen_random_uuid(),
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  user_id uuid not null,
  day date not null,
  status public.log_draft_status not null default 'pending',
  message text,
  rows jsonb not null,
  confirmed_at timestamp with time zone,
  constraint log_drafts_pkey primary key (id),
  constraint log_drafts_user_id_fkey foreign key (user_id) references auth.users(id)
);

create index log_drafts_pending_idx
  on public.log_drafts (user_id, day)
  where status = 'pending';

alter table public.log_drafts enable row level security;

create policy "Enable users to view their own data only"
  on public.log_drafts
  for select
  to authenticated
  using ((select auth.uid()) = user_id);
