import { useSyncExternalStore } from "react";
import type { ModelChoices, ModelTask } from "@/repository/backend/types";

// The models picked in Settings, kept in this browser and sent with every
// request that runs a model; a task left out uses the backend's configured
// model. The sandbox sends its own picks instead.
const STORAGE_KEY = "mio:model-preferences";
const CHANGE_EVENT = "mio:model-preferences-change";
const TASKS: ModelTask[] = ["agent", "extract_photo", "extract_text", "resolve", "edit"];
const EMPTY: ModelChoices = {};

// The last value read, so the same stored text returns the same object.
let cached: { raw: string | null; value: ModelChoices } = { raw: null, value: EMPTY };

function parse(raw: string | null): ModelChoices {
  if (!raw) return EMPTY;
  try {
    const stored: unknown = JSON.parse(raw);
    if (!stored || typeof stored !== "object") return EMPTY;
    const choices: ModelChoices = {};
    for (const task of TASKS) {
      const model = (stored as Record<string, unknown>)[task];
      if (typeof model === "string" && model) choices[task] = model;
    }
    return choices;
  } catch {
    return EMPTY;
  }
}

/** The models picked in Settings; empty when none, or storage is unavailable. */
export function readModelPreferences(): ModelChoices {
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return cached.value;
  }
  if (raw !== cached.raw) cached = { raw, value: parse(raw) };
  return cached.value;
}

export function writeModelPreferences(choices: ModelChoices): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(choices));
  } catch {
    // Storage blocked (e.g. a private window): the pick lasts until reload.
    cached = { raw: JSON.stringify(choices), value: choices };
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, onChange);
  // Picks made in another tab.
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** The models picked in Settings, updating as they change. */
export function useModelPreferences(): ModelChoices {
  return useSyncExternalStore(subscribe, readModelPreferences, () => EMPTY);
}
