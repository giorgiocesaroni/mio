import { cva, VariantProps } from "class-variance-authority";
import { twMerge } from "tailwind-merge";

const buttonVariants = cva(
  "cursor-pointer font-medium px-4 py-1.5 rounded-xl border flex gap-2 items-center",
  {
    variants: {
      variant: {
        default: "border-foreground bg-foreground text-background",
        outline: "border-foreground bg-background text-foreground",
        ghost: "border-transparent",
      },
    },
  },
);

export interface ButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = ({
  variant,
  className,
  children,
  ...props
}: ButtonProps) => (
  <button
    className={twMerge(buttonVariants({ variant }), className)}
    {...props}
  >
    {children}
  </button>
);
