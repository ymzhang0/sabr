import * as React from "react";

import { cn } from "@/lib/utils";

type ButtonVariant = "default" | "ghost" | "outline" | "subtle";
type ButtonSize = "sm" | "md" | "icon";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const variantMap: Record<ButtonVariant, string> = {
  default:
    "bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200",
  ghost:
    "bg-transparent text-zinc-700 hover:bg-zinc-900/5 dark:text-zinc-200 dark:hover:bg-white/10",
  outline:
    "border border-zinc-300 bg-white/70 text-zinc-700 hover:bg-zinc-100 dark:border-white/15 dark:bg-zinc-900/40 dark:text-zinc-200 dark:hover:bg-zinc-800/70",
  subtle:
    "bg-emerald-500/10 text-emerald-700 hover:bg-emerald-500/20 dark:text-emerald-300 dark:hover:bg-emerald-500/25",
};

const sizeMap: Record<ButtonSize, string> = {
  sm: "h-8 rounded-lg px-3 text-xs",
  md: "h-9 rounded-xl px-4 text-sm",
  icon: "h-9 w-9 rounded-xl",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "md", type = "button", ...props }, ref) => {
    return (
      <button
        ref={ref}
        type={type}
        className={cn(
          "inline-flex items-center justify-center gap-2 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-zinc-500 disabled:pointer-events-none disabled:opacity-60",
          variantMap[variant],
          sizeMap[size],
          className,
        )}
        {...props}
      />
    );
  },
);

Button.displayName = "Button";
