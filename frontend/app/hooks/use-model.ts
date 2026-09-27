"use client";

import { getModels } from "@/repository/backend/queries";
import { useQuery } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

// The one model choice: every LLM call (chat, food logging, corrections) uses
// it; only transcription and embeddings keep their own models.
const STORAGE_KEY = "model";
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function useModel() {
  const stored = useSyncExternalStore(
    subscribe,
    () => window.localStorage.getItem(STORAGE_KEY),
    () => null,
  );
  const { data: modelsData } = useQuery({
    queryKey: ["models"],
    queryFn: getModels,
    staleTime: Infinity,
  });

  // A stored model that's no longer offered falls back to the default.
  const model =
    stored && modelsData?.models.some((m) => m.id === stored)
      ? stored
      : (modelsData?.default ?? undefined);

  const setModel = (value: string | null) => {
    if (!value) return;
    window.localStorage.setItem(STORAGE_KEY, value);
    listeners.forEach((listener) => listener());
  };

  return { models: modelsData?.models, model, setModel };
}
