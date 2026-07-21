"use client"
import * as React from "react"

/**
 * Calm breathing orb with cycling status lines — the signature "AI is
 * reflecting" moment, used instead of generic spinners for analysis waits.
 */
export function ReflectingIndicator({
  messages,
  compact = false,
  className = "",
}: {
  messages: string[]
  compact?: boolean
  className?: string
}) {
  const [index, setIndex] = React.useState(0)

  React.useEffect(() => {
    const timer = setInterval(() => setIndex(i => (i + 1) % messages.length), 2200)
    return () => clearInterval(timer)
  }, [messages.length])

  if (compact) {
    return (
      <span className={`flex items-center gap-2.5 ${className}`} role="status" aria-live="polite">
        <span className="relative flex items-center justify-center w-4 h-4 flex-shrink-0">
          <span className="absolute w-4 h-4 rounded-full bg-current opacity-30 [animation:breathe_2.4s_ease-in-out_infinite]" />
          <span className="w-1.5 h-1.5 rounded-full bg-current" />
        </span>
        <span key={index} className="fade-in whitespace-nowrap">{messages[index]}</span>
      </span>
    )
  }

  return (
    <div className={`flex flex-col items-center justify-center gap-6 ${className}`} role="status" aria-live="polite">
      <span className="relative flex items-center justify-center w-20 h-20">
        <span className="absolute w-16 h-16 rounded-full bg-primary/20 [animation:breathe_2.4s_ease-in-out_infinite]" />
        <span className="absolute w-10 h-10 rounded-full bg-primary/30 [animation:breathe_2.4s_ease-in-out_infinite_0.35s]" />
        <span className="w-3.5 h-3.5 rounded-full bg-primary shadow-[0_0_24px_rgba(139,92,246,0.6)]" />
      </span>
      <span key={index} className="text-sm font-medium text-gray-500 dark:text-gray-400 fade-in text-center">
        {messages[index]}
      </span>
    </div>
  )
}
