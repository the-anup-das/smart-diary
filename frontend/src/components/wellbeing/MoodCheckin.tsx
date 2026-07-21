"use client"
import * as React from "react"

const LEVELS = [
  { value: 2, emoji: "🌧️", label: "Struggling" },
  { value: 4, emoji: "🌫️", label: "Low" },
  { value: 6, emoji: "⛅", label: "Okay" },
  { value: 8, emoji: "🌤️", label: "Good" },
  { value: 10, emoji: "☀️", label: "Great" },
]

/** One-tap arrival mood before writing. Compared with the post-writing AI
 *  score, the delta becomes personal evidence that journaling helps. */
export function MoodCheckin({ onCheckin }: { onCheckin: (mood: number) => void }) {
  const [picked, setPicked] = React.useState<number | null>(null)

  function pick(value: number) {
    if (picked !== null) return
    setPicked(value)
    fetch("/api/users/checkin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mood: value }),
    }).catch(() => {})
    onCheckin(value)
  }

  if (picked !== null) return null

  return (
    <div className="mx-2 lg:mx-6 mb-6 flex flex-wrap items-center gap-3 fade-in">
      <span className="text-sm text-gray-500 dark:text-gray-400">How are you arriving?</span>
      <div className="flex gap-1.5" role="group" aria-label="Arrival mood">
        {LEVELS.map(level => (
          <button
            key={level.value}
            onClick={() => pick(level.value)}
            title={level.label}
            aria-label={`Feeling ${level.label.toLowerCase()}`}
            className="px-2.5 py-1.5 rounded-xl border border-black/5 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] hover:border-primary/40 hover:scale-110 transition-all cursor-pointer text-lg leading-none"
          >
            {level.emoji}
          </button>
        ))}
      </div>
    </div>
  )
}
