"use client"
import * as React from "react"
import { getMoodHex, getMoodTier } from "@/lib/mood"

/**
 * MoodHeatmap - the last 28 days as a Monday-first calendar grid, each day coloured by
 * that entry's mood. Dashed cells are days without an entry, grey cells were written but
 * never reflected on, and a small dot marks a completed 3-Minute Reset.
 */

export interface PatternDay {
  date: string
  weekday: string
  hasEntry: boolean
  mood: number | null
  battery: number | null
  rumination: string | null
  resetDone: boolean
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

function describe(d: PatternDay) {
  const label = new Date(d.date + "T00:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })
  if (!d.hasEntry) return `${label}: no entry`
  if (d.mood === null) return `${label}: written, not reflected on`
  const parts = [`mood ${d.mood}/10, ${getMoodTier(d.mood).label.toLowerCase()}`]
  if (d.battery !== null) parts.push(`energy ${d.battery}%`)
  if (d.rumination) parts.push(`overthinking ${d.rumination}`)
  if (d.resetDone) parts.push("reset done")
  return `${label}: ${parts.join(", ")}`
}

export function MoodHeatmap({ days }: { days: PatternDay[] }) {
  if (!days.length) return null
  const first = new Date(days[0].date + "T00:00:00")
  const lead = (first.getDay() + 6) % 7 // Monday-first column index
  const cells: (PatternDay | null)[] = [...Array<null>(lead).fill(null), ...days]
  while (cells.length % 7 !== 0) cells.push(null)
  const todayDate = days[days.length - 1].date

  return (
    <div>
      <div className="grid grid-cols-7 gap-1.5 mb-1.5">
        {WEEKDAYS.map(w => (
          <div key={w} className="text-center text-[10px] uppercase tracking-widest text-gray-400">{w}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1.5">
        {cells.map((d, i) => {
          if (d === null) return <div key={`blank-${i}`} className="aspect-[2/1] sm:aspect-[5/2]" />
          const filled = d.mood !== null
          const isToday = d.date === todayDate
          const dayNumber = Number(d.date.slice(-2))
          return (
            <div
              key={d.date}
              title={describe(d)}
              className={`relative aspect-[2/1] sm:aspect-[5/2] rounded-md border transition-transform hover:scale-[1.04] cursor-default ${
                d.hasEntry ? "border-transparent" : "border-dashed border-black/10 dark:border-white/15"
              } ${isToday ? "ring-2 ring-primary/60 ring-offset-1 ring-offset-transparent" : ""}`}
              style={{
                backgroundColor: filled ? getMoodHex(d.mood as number) : d.hasEntry ? "rgba(156,163,175,0.35)" : "transparent",
                opacity: filled ? 0.88 : 1,
              }}
            >
              <span className={`absolute top-1 left-1.5 text-[10px] font-mono ${filled ? "text-white/90" : "text-gray-400"}`}>{dayNumber}</span>
              {d.resetDone && (
                <span className="absolute bottom-1 right-1.5 w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_0_1px_rgba(0,0,0,0.25)]" aria-hidden="true" />
              )}
            </div>
          )
        })}
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 mt-4 text-[11px] text-gray-500">
        <span className="flex items-center gap-2">
          <span className="text-gray-400">Low</span>
          <span className="inline-block h-2 w-24 rounded-full" style={{ background: "linear-gradient(90deg, #ef4444, #f97316, #f59e0b, #10b981, #8b5cf6)" }} />
          <span className="text-gray-400">Thriving</span>
        </span>
        <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: "rgba(156,163,175,0.35)" }} /> written, not reflected</span>
        <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-3 rounded-sm border border-dashed border-black/20 dark:border-white/20" /> no entry</span>
        <span className="flex items-center gap-1.5"><span className="inline-block w-1.5 h-1.5 rounded-full bg-gray-500" /> reset done</span>
      </div>
    </div>
  )
}
