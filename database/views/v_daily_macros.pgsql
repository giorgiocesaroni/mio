drop view if exists public.v_daily_macros;

create view public.v_daily_macros with (security_invoker=on) as
select
  date_trunc('day'::text, now()) as day,
  coalesce(sum((i.protein_g * coalesce(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) as total_protein_g,
  coalesce(sum((i.carbs_g * coalesce(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) as total_carbs_g,
  coalesce(sum((i.fat_g * coalesce(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) as total_fat_g,
  coalesce(sum((i.calories_kcal * coalesce(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) as total_calories_kcal
from
  logs l
  join ingredients i on i.id = l.food_id
  left join serving_sizes ss on ss.id = l.serving_size_id
where
  l.food_id is not null
  and date_trunc('day'::text, coalesce(l.log_for, l.created_at)) = date_trunc('day'::text, now());
