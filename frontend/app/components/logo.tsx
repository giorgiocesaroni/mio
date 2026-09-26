import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex aspect-square size-14 items-center justify-center rounded-2xl border bg-brand text-brand-foreground md:size-18",
        className,
      )}
    >
      <p className="font-sans text-4xl md:text-5xl">m</p>
    </div>
  );
}
