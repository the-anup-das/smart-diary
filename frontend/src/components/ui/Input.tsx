import * as React from "react"
import { cn } from "@/lib/utils"

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-11 w-full rounded-md border border-[rgba(255,255,255,0.1)] bg-[rgba(255,255,255,0.03)] px-3 py-2 text-sm text-foreground",
          "transition-all file:border-0 file:bg-transparent file:text-sm file:font-medium",
          "placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:bg-[rgba(255,255,255,0.06)] shadow-sm",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input }
