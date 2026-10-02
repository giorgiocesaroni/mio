-- The last reads the frontend made through the backend, as functions it calls
-- straight from Supabase.

-- A conversation's messages in order, with the drafts its `log_food` results
-- refer to, as they are now. The frontend turns them into chat steps.
-- `draft_id` is matched loosely here; the frontend only shows a draft for a
-- tool result whose `draft_id` it can parse.
create or replace function public.get_conversation(p_conversation_id uuid)
returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
  with m as (
    select raw_content, created_at
    from messages
    where conversation_id = p_conversation_id and user_id = auth.uid()
  ),
  draft_ids as (
    select distinct (regexp_match(
      raw_content->>'content', '"draft_id":\s*"([0-9a-f-]{36})"'
    ))[1]::uuid as id
    from m
    where raw_content->>'role' = 'tool'
  )
  select jsonb_build_object(
    'messages', coalesce(
      (select jsonb_agg(raw_content::jsonb order by created_at) from m),
      '[]'::jsonb
    ),
    'drafts', coalesce((
      select jsonb_agg(jsonb_build_object(
        'id', d.id,
        'created_at', d.created_at,
        'day', d.day,
        'status', d.status,
        'message', d.message,
        'via', d.via,
        'rows', d.rows
      ))
      from log_drafts d
      where d.id in (select id from draft_ids) and d.user_id = auth.uid()
    ), '[]'::jsonb)
  );
$$;

-- What the LLM calls cost: in total, by model, by day over the last week, and
-- per log created from chat, by route.
create or replace function public.get_usage_overview()
returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
  select jsonb_build_object(
    'total', (
      select jsonb_build_object(
        'total_invocations', count(*),
        'total_cost', coalesce(sum(total_cost), 0)::float,
        'prompt_tokens', coalesce(sum(
          coalesce(uncached_input_tokens, 0) + coalesce(cached_input_tokens, 0)
        ), 0),
        'completion_tokens', coalesce(sum(coalesce(output_tokens, 0)), 0)
      )
      from llm_invocations
    ),
    'models', coalesce((
      select jsonb_agg(to_jsonb(m) order by m.total_cost desc)
      from (
        select
          coalesce(model_id, 'unknown') as model_id,
          count(*) as invocations,
          coalesce(sum(total_cost), 0)::float as total_cost,
          coalesce(sum(total_cost), 0)::float / count(*) as cost_per_message,
          coalesce(sum(uncached_input_tokens), 0) as uncached_input_tokens,
          coalesce(sum(cached_input_tokens), 0) as cached_input_tokens,
          coalesce(sum(output_tokens), 0) as output_tokens
        from llm_invocations
        group by model_id
      ) m
    ), '[]'::jsonb),
    'daily', coalesce((
      select jsonb_agg(jsonb_build_object(
        'day', d.day,
        'total_cost', d.total_cost,
        'models', d.models
      ) order by d.day)
      from (
        select
          day,
          sum(cost) as total_cost,
          jsonb_agg(
            jsonb_build_object('model_id', model_id, 'cost', cost)
            order by cost desc
          ) as models
        from (
          select
            created_at::date as day,
            coalesce(model_id, 'unknown') as model_id,
            coalesce(sum(total_cost), 0)::float as cost
          from llm_invocations
          where created_at >= current_date - interval '6 days'
          group by 1, 2
        ) per_model
        group by day
      ) d
    ), '[]'::jsonb),
    'logs', coalesce((
      select jsonb_agg(jsonb_build_object(
        'via', via,
        'logs', logs,
        'total_cost', total_cost,
        'cost_per_log', total_cost / logs
      ) order by via)
      from (
        select via, count(*) as logs, sum(cost)::float as total_cost
        from log_drafts
        where cost is not null and via in ('pipeline', 'agent')
        group by via
      ) l
    ), '[]'::jsonb)
  );
$$;

revoke execute on function public.get_conversation(uuid) from public, anon;
grant execute on function public.get_conversation(uuid) to authenticated;
revoke execute on function public.get_usage_overview() from public, anon;
grant execute on function public.get_usage_overview() to authenticated;
