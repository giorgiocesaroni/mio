-- Server routes in the frontend record what their LLM calls cost with the
-- user's own session, so a user can add invocations only for themselves.

create policy "Enable users to insert their own data only"
  on public.llm_invocations
  for insert
  to authenticated
  with check ((select auth.uid()) = user_id);
