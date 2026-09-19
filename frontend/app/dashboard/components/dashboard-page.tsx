"use client";

import { useEffect, useState } from "react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

export function DashboardHeader({
  title,
  actions,
  subtitle,
  className,
}: {
  title: React.ReactNode;
  actions?: React.ReactNode;
  subtitle?: React.ReactNode;
  className?: string;
}) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 0);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "sticky top-0 z-10 border-b bg-background/80 backdrop-blur-md transition-colors",
        scrolled ? "border-border" : "border-transparent",
        className,
      )}
    >
      <div className="mx-auto w-full max-w-3xl px-6 py-3">
        <div className="flex items-center gap-1">
          <SidebarTrigger className="-ml-2 text-muted-foreground md:hidden" />
          <h1 className="font-sans text-xl font-medium tracking-tight">
            {title}
          </h1>
          {actions ? (
            <div className="ml-auto flex items-center gap-2">{actions}</div>
          ) : null}
        </div>
        {subtitle ? (
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
        ) : null}
      </div>
    </header>
  );
}

export function DashboardBody({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mx-auto grid w-full max-w-3xl flex-1 content-start p-6",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function DashboardPage({
  title,
  subtitle,
  actions,
  children,
  bodyClassName,
  headerClassName,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  bodyClassName?: string;
  headerClassName?: string;
}) {
  return (
    <>
      <DashboardHeader
        title={title}
        subtitle={subtitle}
        actions={actions}
        className={headerClassName}
      />
      <DashboardBody className={bodyClassName}>{children}</DashboardBody>
    </>
  );
}
