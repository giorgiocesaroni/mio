drop view if exists public.v_daily_food_logs_with_foods;

create view public.v_daily_food_logs_with_foods with (security_invoker=on) as
with profile as (
  select p.timezone
  from profiles p
  where p.user_id = auth.uid()
  limit 1
)
select
  l.id as log_id,
  l.log_for,
  date_trunc('day'::text, coalesce(l.log_for, l.created_at) at time zone coalesce((select timezone from profile), 'UTC')) as day,
  coalesce(l.log_for, l.created_at) as log_created_at,
  l.food_id as log_food_id,
  l.recipe_id as log_recipe_id,
  coalesce(ss.grams * l.quantity, l.quantity_g) as log_quantity_g,
  l.serving_size_id as log_serving_size_id,
  l.quantity as log_quantity,
  ss.label as log_serving_size_label,
  ss.label_plural as log_serving_size_label_plural,
  ss.grams as log_serving_size_grams,
  i.name as food_name,
  i.protein_g as food_protein_g,
  i.carbs_g as food_carbs_g,
  i.fat_g as food_fat_g,
  i.calories_kcal as food_calories_kcal,
  r.name as recipe_name
from
  logs l
  join ingredients i on i.id = l.food_id
  left join serving_sizes ss on ss.id = l.serving_size_id
  left join recipes r on r.id = l.recipe_id
where
  date_trunc('day'::text, coalesce(l.log_for, l.created_at) at time zone coalesce((select timezone from profile), 'UTC')) = date_trunc('day'::text, now() at time zone coalesce((select timezone from profile), 'UTC'));
