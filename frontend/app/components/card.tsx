import { twMerge } from "tailwind-merge";
import { H3 } from "./typography";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}

export const Card = ({ className, children, ...props }: CardProps) => (
  <div
    className={twMerge(
      "border border-border p-4 rounded-2xl grid gap-2",
      className,
    )}
    {...props}
  >
    {children}
  </div>
);

export const CardHeader = ({
  children,
  className,
}: Readonly<{ children: React.ReactNode; className?: string }>) => (
  <div className={twMerge("flex items-center gap-2", className)}>
    {children}
  </div>
);

export const CardTitle = ({
  children,
  className,
}: Readonly<{ children: React.ReactNode; className?: string }>) => (
  <H3 className={twMerge(className)}>{children}</H3>
);

export const CardDescription = ({
  children,
  className,
}: Readonly<{ children: React.ReactNode; className?: string }>) => (
  <p className={twMerge("text-base text-muted-foreground", className)}>
    {children}
  </p>
);
