"use client";

import { getDayEntries } from "@/repository/backend/queries";
import { useQuery } from "@tanstack/react-query";

export const DAY_ENTRIES_QUERY_KEY = ["entries"] as const;

export function dayEntriesQueryKey(day: string) {
  return [...DAY_ENTRIES_QUERY_KEY, day] as const;
}

/**
 * A day's pending drafts and logs. They come from one request, so a draft
 * being confirmed is replaced by its log in a single update.
 */
export function useDayEntries(day: string) {
  return useQuery({
    queryKey: dayEntriesQueryKey(day),
    queryFn: () => getDayEntries(day),
  });
}
