create view public.v_daily_food_logs_with_foods as
select
  fl.id as log_id,
  date_trunc('day'::text, fl.created_at) as day,
  fl.created_at as log_created_at,
  fl.food_id as log_food_id,
  fl.quantity_g as log_quantity_g,
  f.name as food_name,
  f.protein_g as food_protein_g,
  f.carbs_g as food_carbs_g,
  f.fat_g as food_fat_g,
  f.calories_kcal as food_calories_kcal
from
  food_logs fl
  join foods f on f.id = fl.food_id
where
  date_trunc('day'::text, fl.created_at) = date_trunc('day'::text, now());