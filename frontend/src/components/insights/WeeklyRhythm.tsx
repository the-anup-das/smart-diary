"use client"
import * as React from "react"
import { getMoodHex } from "@/lib/mood"

/**
 * WeeklyRhythm - average mood by weekday across every reflected entry, so a person can
 * see which day of the week tends to be their low one. Locked until a week of data exists,
 * because a rhythm drawn from three days is noise dressed up as a pattern.
 */

export interface WeekdayStat {
  day: string
  entries: number
  avgMood: number | null
  avgCalm: number | null
}

export function WeeklyRhythm({ weekday, analysedDays, unlockAt = 7 }: { weekday: WeekdayStat[]; analysedDays: number; unlockAt?: number }) {
  const locked = analysedDays < unlockAt
  const withMood = weekday.filter(w => w.avgMood !== null)
  const best = withMood.length >= 2 ? withMood.reduce((a, b) => ((b.avgMood as number) > (a.avgMood as number) ? b : a)) : null
  const worst = withMood.length >= 2 ? withMood.reduce((a, b) => ((b.avgMood as number) < (a.avgMood as number) ? b : a)) : null

  return (
    <div>
      <div className={`relative ${locked ? "select-none" : ""}`} aria-hidden={locked}>
        <div className={`grid grid-cols-7 gap-2 items-end h-36 ${locked ? "opacity-30 blur-[1.5px]" : ""}`}>
          {weekday.map(w => {
            const pct = w.avgMood !== null ? (w.avgMood / 10) * 100 : 0
            const title = w.avgMood !== null
              ? `${w.day}: mood ${w.avgMood}/10 over ${w.entries} ${w.entries === 1 ? "entry" : "entries"}${w.avgCalm !== null ? `, calm ${w.avgCalm}/100` : ""}`
              : `${w.day}: no reflected entries`
            return (
              <div key={w.day} className="flex flex-col items-center justify-end h-full" title={title}>
                <span className="text-[10px] font-mono text-gray-500 mb-1">{w.avgMood !== null ? w.avgMood : ""}</span>
                <div
                  className="w-full rounded-t-md transition-all duration-700 ease-out"
                  style={{
                    height: `${w.avgMood !== null ? Math.max(pct, 6) : w.entries ? 4 : 0}%`,
                    backgroundColor: w.avgMood !== null ? getMoodHex(w.avgMood) : "rgba(156,163,175,0.3)",
                    opacity: 0.85,
                  }}
                />
              </div>
            )
          })}
        </div>
        <div className="grid grid-cols-7 gap-2 mt-2 text-center">
          {weekday.map(w => (
            <div key={w.day}>
              <div className="text-[10px] uppercase tracking-widest text-gray-400">{w.day}</div>
              <div className="text-[10px] text-gray-400 font-mono">{w.entries || ""}</div>
            </div>
          ))}
        </div>
        {locked && (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-xs text-gray-600 dark:text-gray-300 bg-white/80 dark:bg-black/60 backdrop-blur px-3 py-2 rounded-lg text-center">
              Reflect on {unlockAt - analysedDays} more {unlockAt - analysedDays === 1 ? "day" : "days"} to unlock your weekly rhythm.
            </p>
          </div>
        )}
      </div>
      {!locked && best && worst && best.day !== worst.day && (
        <p className="text-sm text-gray-600 dark:text-gray-300 mt-4">
          Your mood tends to be highest on <span className="font-medium">{best.day}</span> and lowest on <span className="font-medium">{worst.day}</span>.
        </p>
      )}
    </div>
  )
}
