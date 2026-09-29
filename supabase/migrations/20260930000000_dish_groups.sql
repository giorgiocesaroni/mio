-- A logged dish: the component rows one dish was broken into at review time.
-- Rows that belong to the same dish share `dish_id`, so the day's log can show
-- them as one card — the same way a saved recipe's dispatched rows already
-- group by `recipe_id`. Both are null on a standalone food and on legacy logs.

alter table public.logs
  add column dish_id uuid,
  add column dish_name text;

create index logs_dish_idx on public.logs (dish_id);
