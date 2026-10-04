-- The models a user picked for each task (agent, extract_photo, extract_text,
-- resolve, edit), as {task: OpenRouter model id}; a missing task uses the
-- backend's configured model. Written by the backend, which checks each model
-- can do its task.

alter table public.profiles
  add column model_preferences jsonb not null default '{}'::jsonb;
