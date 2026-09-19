"use client";

import { useTheme } from "next-themes";
import { Toaster, type ToasterProps } from "sonner";

/**
 * Sonner's built-in `theme="system"` follows the OS `prefers-color-scheme`
 * media query, so it ignores a manual light/dark choice made through
 * next-themes (which toggles the `.dark` class). Reading the resolved theme
 * keeps toasts in sync with the rest of the UI.
 */
export function ThemedToaster(props: ToasterProps) {
  const { theme, resolvedTheme } = useTheme();
  const sonnerTheme: ToasterProps["theme"] =
    resolvedTheme === "dark" || resolvedTheme === "light"
      ? resolvedTheme
      : theme === "dark" || theme === "light"
        ? theme
        : "system";

  return (
    <Toaster
      theme={sonnerTheme}
      toastOptions={{
        classNames: {
          toast:
            "bg-popover! text-popover-foreground! border-border!",
          description: "text-muted-foreground!",
          actionButton: "bg-primary! text-primary-foreground!",
          cancelButton: "bg-muted! text-muted-foreground!",
          closeButton: "bg-popover! text-muted-foreground! border-border!",
        },
      }}
      {...props}
    />
  );
}
