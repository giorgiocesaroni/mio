drop view if exists public.v_daily_macros;

create view public.v_daily_macros with (security_invoker=on) as
with
-- Macros from direct ingredient logs
ingredient_macros as (
  select
    coalesce(sum((i.protein_g * coalesce(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) as protein_g,
    coalesce(sum((i.carbs_g * coalesce(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) as carbs_g,
    coalesce(sum((i.fat_g * coalesce(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) as fat_g,
    coalesce(sum((i.calories_kcal * coalesce(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) as calories_kcal
  from logs l
    join ingredients i on i.id = l.food_id
    left join serving_sizes ss on ss.id = l.serving_size_id
  where l.food_id is not null
    and date_trunc('day'::text, coalesce(l.log_for, l.created_at)) = date_trunc('day'::text, now())
),
-- Macros from recipe logs: sum each recipe item's ingredient nutrition
recipe_macros as (
  select
    coalesce(sum((i.protein_g * coalesce(ss.grams * ri.quantity, ri.quantity_g))::numeric / 100.0), 0) as protein_g,
    coalesce(sum((i.carbs_g * coalesce(ss.grams * ri.quantity, ri.quantity_g))::numeric / 100.0), 0) as carbs_g,
    coalesce(sum((i.fat_g * coalesce(ss.grams * ri.quantity, ri.quantity_g))::numeric / 100.0), 0) as fat_g,
    coalesce(sum((i.calories_kcal * coalesce(ss.grams * ri.quantity, ri.quantity_g))::numeric / 100.0), 0) as calories_kcal
  from logs l
    join recipe_items ri on ri.recipe_id = l.recipe_id
    join ingredients i on i.id = ri.food_id
    left join serving_sizes ss on ss.id = ri.serving_size_id
  where l.recipe_id is not null
    and date_trunc('day'::text, coalesce(l.log_for, l.created_at)) = date_trunc('day'::text, now())
)
select
  date_trunc('day'::text, now()) as day,
  im.protein_g + rm.protein_g as total_protein_g,
  im.carbs_g + rm.carbs_g as total_carbs_g,
  im.fat_g + rm.fat_g as total_fat_g,
  im.calories_kcal + rm.calories_kcal as total_calories_kcal
from ingredient_macros im, recipe_macros rm;
