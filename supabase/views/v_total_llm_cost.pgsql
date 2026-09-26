create view public.v_total_llm_cost as
select
  COALESCE(sum(total_cost), 0::double precision) as total_cost
from
  llm_invocations;