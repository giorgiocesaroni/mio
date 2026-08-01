drop view if exists public.v_daily_food_logs_with_foods;

create view public.v_daily_food_logs_with_foods with (security_invoker=on) as
select
  fl.id as log_id,
  date_trunc('day'::text, fl.created_at) as day,
  fl.created_at as log_created_at,
  fl.food_id as log_food_id,
  coalesce(ss.grams * fl.quantity, fl.quantity_g) as log_quantity_g,
  fl.serving_size_id as log_serving_size_id,
  fl.quantity as log_quantity,
  ss.label as log_serving_size_label,
  ss.label_plural as log_serving_size_label_plural,
  ss.grams as log_serving_size_grams,
  f.name as food_name,
  f.protein_g as food_protein_g,
  f.carbs_g as food_carbs_g,
  f.fat_g as food_fat_g,
  f.calories_kcal as food_calories_kcal
from
  food_logs fl
  join foods f on f.id = fl.food_id
  left join serving_sizes ss on ss.id = fl.serving_size_id
where
  date_trunc('day'::text, fl.created_at) = date_trunc('day'::text, now());
