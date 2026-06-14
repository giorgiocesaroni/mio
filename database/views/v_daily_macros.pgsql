drop view if exists public.v_daily_macros;

create view public.v_daily_macros with (security_invoker=on) as
select
  date_trunc('day'::text, fl.created_at) as day,
  sum((f.protein_g * coalesce(ss.grams * fl.quantity, fl.quantity_g))::numeric / 100.0) as total_protein_g,
  sum((f.carbs_g * coalesce(ss.grams * fl.quantity, fl.quantity_g))::numeric / 100.0) as total_carbs_g,
  sum((f.fat_g * coalesce(ss.grams * fl.quantity, fl.quantity_g))::numeric / 100.0) as total_fat_g,
  sum(
    (f.calories_kcal * coalesce(ss.grams * fl.quantity, fl.quantity_g))::numeric / 100.0
  ) as total_calories_kcal
from
  food_logs fl
  join foods f on f.id = fl.food_id
  left join serving_sizes ss on ss.id = fl.serving_size_id
where
  date_trunc('day'::text, fl.created_at) = date_trunc('day'::text, now())
group by
  (date_trunc('day'::text, fl.created_at));