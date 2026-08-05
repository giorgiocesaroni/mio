-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.conversations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  user_id uuid NOT NULL,
  title text,
  CONSTRAINT conversations_pkey PRIMARY KEY (id),
  CONSTRAINT conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.messages (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  conversation_id uuid NOT NULL,
  raw_content json NOT NULL,
  user_id uuid NOT NULL,
  CONSTRAINT messages_pkey PRIMARY KEY (id),
  CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id),
  CONSTRAINT messages_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.ingredients (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  name text NOT NULL,
  protein_g numeric NOT NULL,
  carbs_g numeric NOT NULL,
  fat_g numeric NOT NULL,
  calories_kcal numeric NOT NULL,
  embedding USER-DEFINED,
  user_id uuid,
  brand text,
  source_url text,
  state USER-DEFINED NOT NULL,
  CONSTRAINT ingredients_pkey PRIMARY KEY (id),
  CONSTRAINT foods_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.logs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  food_id uuid NOT NULL,
  quantity_g numeric,
  user_id uuid NOT NULL,
  quantity numeric,
  serving_size_id uuid,
  recipe_id uuid,
  meal_type USER-DEFINED NOT NULL,
  log_for timestamp with time zone NOT NULL,
  CONSTRAINT logs_pkey PRIMARY KEY (id),
  CONSTRAINT food_logs_food_id_fkey FOREIGN KEY (food_id) REFERENCES public.ingredients(id),
  CONSTRAINT food_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id),
  CONSTRAINT food_logs_serving_size_id_fkey FOREIGN KEY (serving_size_id) REFERENCES public.serving_sizes(id),
  CONSTRAINT logs_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id)
);
CREATE TABLE public.goals (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  weight_kg bigint NOT NULL,
  calories_kcal bigint NOT NULL,
  protein_g bigint NOT NULL,
  carbs_g bigint NOT NULL,
  fat_g bigint NOT NULL,
  goal text NOT NULL,
  user_id uuid NOT NULL,
  CONSTRAINT goals_pkey PRIMARY KEY (id),
  CONSTRAINT goals_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.llm_invocations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  total_cost double precision NOT NULL,
  raw_usage_metadata jsonb NOT NULL,
  conversation_id uuid,
  user_id uuid NOT NULL,
  model_id text,
  uncached_input_tokens bigint,
  cached_input_tokens bigint,
  output_tokens bigint,
  CONSTRAINT llm_invocations_pkey PRIMARY KEY (id),
  CONSTRAINT llm_invocations_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id),
  CONSTRAINT llm_invocations_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.measurements (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  weight_kg double precision NOT NULL,
  user_id uuid NOT NULL,
  CONSTRAINT measurements_pkey PRIMARY KEY (id),
  CONSTRAINT measurements_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.serving_sizes (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  label text NOT NULL,
  grams numeric NOT NULL,
  food_id uuid,
  user_id uuid,
  label_plural text NOT NULL,
  CONSTRAINT serving_sizes_pkey PRIMARY KEY (id),
  CONSTRAINT serving_sizes_food_id_fkey FOREIGN KEY (food_id) REFERENCES public.ingredients(id),
  CONSTRAINT serving_sizes_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.profiles (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  user_id uuid NOT NULL,
  timezone text NOT NULL DEFAULT 'Europe/Rome'::text,
  CONSTRAINT profiles_pkey PRIMARY KEY (id),
  CONSTRAINT profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.recipes (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  user_id uuid NOT NULL,
  name text NOT NULL,
  image_url text,
  CONSTRAINT recipes_pkey PRIMARY KEY (id),
  CONSTRAINT recipes_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.recipe_ingredients (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  quantity_g numeric,
  quantity numeric,
  serving_size_id uuid,
  food_id uuid NOT NULL,
  recipe_id uuid NOT NULL,
  CONSTRAINT recipe_ingredients_pkey PRIMARY KEY (id),
  CONSTRAINT recipe_items_serving_size_id_fkey FOREIGN KEY (serving_size_id) REFERENCES public.serving_sizes(id),
  CONSTRAINT recipe_items_food_id_fkey FOREIGN KEY (food_id) REFERENCES public.ingredients(id),
  CONSTRAINT recipe_items_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id),
  CONSTRAINT recipe_items_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id)
);