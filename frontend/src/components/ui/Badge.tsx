import * as React from "react"
import { cn } from "@/lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'success' | 'danger' | 'ghost'
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none",
        {
          'border-transparent bg-primary/20 text-primary-hover': variant === 'default',
          'border-transparent bg-success/20 text-success': variant === 'success',
          'border-transparent bg-danger/20 text-danger': variant === 'danger',
          'border-[rgba(255,255,255,0.1)] text-foreground': variant === 'ghost',
        },
        className
      )}
      {...props}
    />
  )
}

export { Badge }
