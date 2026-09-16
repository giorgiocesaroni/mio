"use client";

import { SidebarTrigger } from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

export function PageTitle({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className="flex items-center gap-1">
      <SidebarTrigger className="-ml-2 text-muted-foreground md:hidden" />
      {children ? (
        <h1
          className={cn(
            "font-sans text-xl font-medium tracking-tight md:text-xl",
            className,
          )}
        >
          {children}
        </h1>
      ) : null}
    </div>
  );
}
