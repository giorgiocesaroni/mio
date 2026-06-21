"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AudioStreamProvider } from "./hooks/use-audio-stream";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: true },
  },
});

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AudioStreamProvider>{children}</AudioStreamProvider>
    </QueryClientProvider>
  );
}
