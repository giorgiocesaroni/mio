-- A day's pending drafts and logs, read by the frontend straight from Supabase
-- instead of through the backend. One statement reads both from one snapshot:
-- confirming takes a draft's rows before it writes their logs, so a row is
-- either still a draft or already a log, never both.
--
-- Draft rows are stored with their derived fields (grams, macros, flags), so
-- they're returned as they are.

create or replace function public.get_day_entries(p_day date)
returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
  select jsonb_build_object(
    'drafts', coalesce((
      select jsonb_agg(
        jsonb_build_object(
          'id', d.id,
          'created_at', d.created_at,
          'day', d.day,
          'status', d.status,
          'message', d.message,
          'via', d.via,
          'rows', d.rows
        )
        order by d.created_at desc
      )
      from log_drafts d
      where d.user_id = auth.uid() and d.day = p_day and d.status = 'pending'
    ), '[]'::jsonb),
    'logs', coalesce((
      select jsonb_agg(to_jsonb(v) - 'day' order by v.log_created_at desc)
      from v_daily_food_logs_with_foods v
      where v.day = p_day::timestamp
    ), '[]'::jsonb)
  );
$$;

revoke execute on function public.get_day_entries(date) from public, anon;
grant execute on function public.get_day_entries(date) to authenticated;
