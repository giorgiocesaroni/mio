import { createClient } from "@supabase/supabase-js";
import { Database } from "./types";

const supabase = createClient<Database>(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
);

export const getDailyMacrosView = async () => {
  const { data, error } = await supabase
    .from("v_daily_macros")
    .select("*")
    .maybeSingle();
  if (error) throw error;
  return data;
};

export const getDailyFoodLogsWithFoodsView = async () => {
  const { data, error } = await supabase
    .from("v_daily_food_logs_with_foods")
    .select("*")
    .order("log_created_at", { ascending: false });
  if (error) throw error;
  return data;
};

export const getTotalLlmCost = async () => {
  const { data, error } = await supabase
    .from("v_total_llm_cost")
    .select("*")
    .maybeSingle();
  if (error) throw error;
  return data;
};
