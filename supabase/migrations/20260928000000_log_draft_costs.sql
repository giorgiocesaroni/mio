-- What creating each draft cost (routing, extraction, resolution, and the
-- agent's turn when the agent drafted it), and which path created it, for
-- the cost per log on the usage page. Null for drafts created before.

alter table public.log_drafts
  add column cost numeric,
  add column via text;
