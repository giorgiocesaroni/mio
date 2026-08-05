-- 0001_recipe_dispatch.sql
--
-- Recipe dispatch refactor.
--
-- Motivation:
--   Recipes were a first-class loggable thing (logs.recipe_id) and v_daily_macros
--   needed a separate recipe branch. That made portioned recipe logging
--   impossible and forced two macro code paths.
--
-- New model:
--   * `recipes` + `recipe_ingredients` are a pure *template* (proportions).
--   * Logging a recipe *dispatches* into per-ingredient logs (one `logs` row per
--     template item, amount scaled to the logged quantity). Instances are
--     detached: each log row carries `recipe_id` only as provenance and always
--     has `food_id` set.
--   * Logs therefore only ever contain *ingredients*. v_daily_macros collapses
--     to the single ingredient path. No recipe branch anywhere.

BEGIN;

-- ── 1. Fractional precision so dispatch can be non-integer ──────────────────
ALTER TABLE public.logs
  ALTER COLUMN quantity_g TYPE numeric USING quantity_g::numeric;

-- ── 2. Rename template table: recipe_items → recipe_ingredients ──────────────
ALTER TABLE public.recipe_items RENAME TO recipe_ingredients;

ALTER TABLE public.recipe_ingredients
  ALTER COLUMN quantity TYPE numeric USING quantity::numeric;
ALTER TABLE public.recipe_ingredients
  ALTER COLUMN quantity_g TYPE numeric USING quantity_g::numeric;

-- ── 3. All recipes are now templates ─────────────────────────────────────────
ALTER TABLE public.recipes DROP COLUMN IF EXISTS is_template;

-- ── 4. FK behavior ───────────────────────────────────────────────────────────
-- Detached logs survive recipe deletion (instance kept, provenance lost).
ALTER TABLE public.logs DROP CONSTRAINT IF EXISTS logs_recipe_id_fkey;
ALTER TABLE public.logs
  ADD CONSTRAINT logs_recipe_id_fkey
  FOREIGN KEY (recipe_id) REFERENCES public.recipes(id) ON DELETE SET NULL;

-- Template items are owned by their recipe.
ALTER TABLE public.recipe_ingredients DROP CONSTRAINT IF EXISTS recipe_items_recipe_id_fkey;
ALTER TABLE public.recipe_ingredients
  ADD CONSTRAINT recipe_ingredients_recipe_id_fkey
  FOREIGN KEY (recipe_id) REFERENCES public.recipes(id) ON DELETE CASCADE;

-- ── 5. Exactly one amount mode per template item ─────────────────────────────
ALTER TABLE public.recipe_ingredients
  ADD CONSTRAINT recipe_ingredients_amount_check CHECK (
    (quantity_g IS NOT NULL AND serving_size_id IS NULL AND quantity IS NULL)
    OR (quantity_g IS NULL AND serving_size_id IS NOT NULL AND quantity IS NOT NULL)
  );

-- ── 6. Data migration: expand legacy recipe-only logs into ingredient logs ─────
-- Old model stored one row per recipe log (food_id NULL, recipe_id set) and the
-- macro view summed the whole recipe. We map each legacy log to a full recipe
-- (scale = 1): one ingredient log per template item, preserving provenance.
WITH legacy AS (
  SELECT
    l.id        AS log_id,
    l.recipe_id,
    l.meal_type,
    l.log_for,
    l.user_id
  FROM logs l
  WHERE l.food_id IS NULL AND l.recipe_id IS NOT NULL
)
INSERT INTO logs (food_id, quantity_g, recipe_id, meal_type, log_for, user_id)
SELECT
  ri.food_id,
  CASE
    WHEN ri.serving_size_id IS NOT NULL THEN ss.grams * ri.quantity
    ELSE ri.quantity_g
  END AS grams,
  legacy.recipe_id,
  legacy.meal_type,
  legacy.log_for,
  legacy.user_id
FROM legacy
JOIN recipe_ingredients ri ON ri.recipe_id = legacy.recipe_id
LEFT JOIN serving_sizes ss ON ss.id = ri.serving_size_id;

DELETE FROM logs WHERE food_id IS NULL AND recipe_id IS NOT NULL;

-- ── 7. Invariant: logs only ever contain ingredients ─────────────────────────
ALTER TABLE public.logs
  ADD CONSTRAINT logs_recipe_has_food_check
  CHECK (recipe_id IS NULL OR food_id IS NOT NULL);

-- ── 8. Views ─────────────────────────────────────────────────────────────────
-- v_daily_macros no longer needs a recipe branch. The source-of-truth copies
-- are database/views/*.pgsql (idempotent, security_invoker=on). Recreating it
-- here keeps this migration self-contained.
DROP VIEW IF EXISTS public.v_daily_macros;

CREATE VIEW public.v_daily_macros
WITH (security_invoker = on) AS
SELECT
  date_trunc('day'::text, now()) AS day,
  COALESCE(sum((i.protein_g * COALESCE(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) AS total_protein_g,
  COALESCE(sum((i.carbs_g  * COALESCE(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) AS total_carbs_g,
  COALESCE(sum((i.fat_g    * COALESCE(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) AS total_fat_g,
  COALESCE(sum((i.calories_kcal * COALESCE(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) AS total_calories_kcal
FROM logs l
JOIN ingredients i ON i.id = l.food_id
LEFT JOIN serving_sizes ss ON ss.id = l.serving_size_id
WHERE l.food_id IS NOT NULL
  AND date_trunc('day'::text, coalesce(l.log_for, l.created_at)) = date_trunc('day'::text, now());

COMMIT;