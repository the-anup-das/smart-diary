"use client"
import * as React from "react"
import { Flame, Check } from "lucide-react"

/**
 * WritingGoalChip - the word count as progress toward today's goal, with the streak beside it.
 * Replaces a bare number with an answer to the two questions a writer has mid-entry:
 * "have I done enough?" and "does today count?"
 */
export function WritingGoalChip({
  wordCount, goal, streak, wroteToday,
}: {
  wordCount: number
  goal: number
  streak: number
  wroteToday: boolean
}) {
  const pct = goal > 0 ? Math.min(100, (wordCount / goal) * 100) : 0
  const met = goal > 0 && wordCount >= goal
  const remaining = Math.max(0, goal - wordCount)
  const r = 7
  const c = 2 * Math.PI * r

  // Today counts as soon as anything is written, so a streak of N with today done reads "N-day streak".
  let streakLabel: string | null = null
  let streakTone = "text-gray-500 dark:text-gray-400 bg-black/5 dark:bg-white/5 border-black/5 dark:border-white/10"
  if (wroteToday && streak >= 1) {
    streakLabel = streak === 1 ? "Day 1 of a new streak" : `${streak}-day streak, today counts`
    streakTone = "text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/20"
  } else if (!wroteToday && streak >= 1) {
    streakLabel = `Write today to keep your ${streak}-day streak`
    streakTone = "text-amber-700 dark:text-amber-300 bg-amber-500/15 border-amber-500/30"
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div
        title={met ? `Daily goal of ${goal} words met` : `${remaining} words to today's goal of ${goal}`}
        className={`flex items-center gap-2 px-3 py-1 rounded-full border transition-colors ${
          met
            ? "bg-green-500/10 border-green-500/20 text-green-600 dark:text-green-400"
            : "bg-black/5 dark:bg-white/5 border-black/5 dark:border-white/10 text-gray-600 dark:text-gray-300"
        }`}
      >
        <svg viewBox="0 0 20 20" className="w-5 h-5 -rotate-90" aria-hidden="true">
          <circle cx="10" cy="10" r={r} fill="none" stroke="currentColor" strokeOpacity="0.2" strokeWidth="2.5" />
          <circle cx="10" cy="10" r={r} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeDasharray={`${(c * pct) / 100} ${c}`} className="transition-all duration-500" />
        </svg>
        <span className="text-sm font-mono tracking-wide font-medium">
          {wordCount} <span className="opacity-60 font-normal">/ {goal}</span>
        </span>
        <span className="text-xs whitespace-nowrap">
          {met ? <span className="inline-flex items-center gap-1"><Check className="w-3 h-3" /> goal met</span> : `${remaining} to go`}
        </span>
      </div>
      {streakLabel && (
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium whitespace-nowrap ${streakTone}`} title="Consecutive days with an entry">
          <Flame className="w-3.5 h-3.5" /> {streakLabel}
        </div>
      )}
    </div>
  )
}
