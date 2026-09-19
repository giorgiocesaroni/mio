"use client";

import { useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider, useTheme } from "next-themes";
import { TooltipProvider } from "@/components/ui/tooltip";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: true },
  },
});

// Matches the --background value of each theme in globals.css.
const themeColors: Record<string, string> = {
  light: "#ffffff",
  dark: "#0a0a0a",
};

function ThemeColorSync() {
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const color = resolvedTheme ? themeColors[resolvedTheme] : undefined;
    if (!color) return;

    let meta = document.querySelector<HTMLMetaElement>(
      'meta[name="theme-color"]',
    );
    if (!meta) {
      meta = document.createElement("meta");
      meta.name = "theme-color";
      document.head.appendChild(meta);
    }
    meta.content = color;
  }, [resolvedTheme]);

  return null;
}

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <ThemeColorSync />
      <TooltipProvider>
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </TooltipProvider>
    </ThemeProvider>
  );
}
