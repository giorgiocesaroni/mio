import { twMerge } from "tailwind-merge";

export const H1 = ({
  children,
  className,
}: Readonly<{ children: React.ReactNode; className?: string }>) => (
  <h1
    className={twMerge(
      "font-serif md:text-6xl text-4xl font-medium tracking-tight",
      className,
    )}
  >
    {children}
  </h1>
);

export const H2 = ({
  children,
  className,
}: Readonly<{ children: React.ReactNode; className?: string }>) => (
  <h2
    className={twMerge(
      "font-serif text-3xl font-medium tracking-tight",
      className,
    )}
  >
    {children}
  </h2>
);

export const H3 = ({
  children,
  className,
}: Readonly<{ children: React.ReactNode; className?: string }>) => (
  <h3 className={twMerge("font-medium", className)}>{children}</h3>
);

export const P = ({
  children,
  className,
}: Readonly<{ children: React.ReactNode; className?: string }>) => (
  <p className={twMerge("font-sans text-muted-foreground", className)}>
    {children}
  </p>
);
