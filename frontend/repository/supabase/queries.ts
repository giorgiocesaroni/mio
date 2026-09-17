import { createClient } from "./client";
import { Database } from "./types";

export const supabase = createClient<Database>();

function nextDay(day: string): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}

export const getDailyMacrosView = async (day: string) => {
  const { data, error } = await supabase
    .from("v_daily_macros")
    .select("*")
    .gte("day", day)
    .lt("day", nextDay(day));
  if (error) throw error;
  return data?.[0] ?? null;
};

export const getDailyMacrosTrend = async (startDay: string) => {
  const { data, error } = await supabase
    .from("v_daily_macros")
    .select("*")
    .gte("day", startDay)
    .order("day", { ascending: true });
  if (error) throw error;
  return data;
};

export const getDailyFoodLogsWithFoodsView = async (day: string) => {
  const { data, error } = await supabase
    .from("v_daily_food_logs_with_foods")
    .select("*")
    .gte("day", day)
    .lt("day", nextDay(day))
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
