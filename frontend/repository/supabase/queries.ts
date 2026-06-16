import { createClient } from "./client";
import { Database } from "./types";

export const supabase = createClient<Database>();

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

export const getConversations = async () => {
  const { data, error } = await supabase
    .from("conversations")
    .select("*")
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data;
};

export const getCurrentGoal = async () => {
  const { data, error } = await supabase
    .from("goals")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) throw error;
  return data;
};
