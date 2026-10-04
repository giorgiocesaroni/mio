import { createClient } from "./client";
import { Database } from "./types";
import { conversationSteps } from "./conversation";
import type {
  DayEntries,
  LogDraft,
  ModelChoices,
  RunAgentStep,
  UsageOverview,
} from "@/repository/backend/types";

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

/**
 * A day's pending drafts and logs, read from one snapshot so a draft being
 * confirmed is never shown alongside its log.
 */
export const getDayEntries = async (day: string): Promise<DayEntries> => {
  const { data, error } = await supabase.rpc("get_day_entries", { p_day: day });
  if (error) throw error;
  return data as unknown as DayEntries;
};

/** A conversation as the steps the chat shows, drafts as they are now. */
export const getConversationMessages = async (
  conversationId: string,
): Promise<RunAgentStep[]> => {
  const { data, error } = await supabase.rpc("get_conversation", {
    p_conversation_id: conversationId,
  });
  if (error) throw error;
  const { messages, drafts } = data as unknown as {
    messages: Parameters<typeof conversationSteps>[0];
    drafts: LogDraft[];
  };
  return conversationSteps(messages, drafts);
};

/** What the LLM calls cost: in total, by model, by day, and per log. */
export const getUsage = async (): Promise<UsageOverview> => {
  const { data, error } = await supabase.rpc("get_usage_overview");
  if (error) throw error;
  return data as unknown as UsageOverview;
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

/** The models the user picked for the app; empty when none. */
export const getModelPreferences = async (): Promise<ModelChoices> => {
  const { data, error } = await supabase
    .from("profiles")
    .select("model_preferences")
    .maybeSingle();
  if (error) throw error;
  return (data?.model_preferences ?? {}) as ModelChoices;
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
