"use client"
import * as React from "react"
import Link from "next/link"
import { Timer } from "lucide-react"
import type { PatternDay } from "./MoodHeatmap"

/**
 * OverthinkingTrend - the answer to "am I an overthinker lately", not just "was I today".
 * A 28-day strip coloured by each reflected day's rumination level, with dots for the days
 * a 3-Minute Reset was completed, and a plain sentence that puts the two together.
 */

export interface OverthinkingStats {
  analysedDays: number
  loopingDays: number
  highDays: number
  resetDays: number
  loopingDaysWithReset: number
}

const LEVEL_COLOUR: Record<string, string> = {
  high: "#f43f5e",
  moderate: "#f59e0b",
  low: "#34d399",
}

function cellColour(d: PatternDay) {
  if (!d.hasEntry) return "transparent"
  if (d.rumination && LEVEL_COLOUR[d.rumination]) return LEVEL_COLOUR[d.rumination]
  return "rgba(156,163,175,0.35)"
}

export function OverthinkingTrend({ days, stats, unlockAt = 3 }: { days: PatternDay[]; stats: OverthinkingStats; unlockAt?: number }) {
  const locked = stats.analysedDays < unlockAt
  const share = stats.analysedDays ? stats.loopingDays / stats.analysedDays : 0
  const pattern = !locked && share >= 0.5

  let sentence: string | null = null
  if (!locked) {
    if (stats.loopingDays === 0) {
      sentence = `No looping days across ${stats.analysedDays} reflected days in the last four weeks.`
    } else {
      sentence =
        `Your mind was looping on ${stats.loopingDays} of ${stats.analysedDays} reflected days in the last four weeks` +
        (stats.highDays ? `, ${stats.highDays} of them rated high.` : ".") +
        ` You took the reset on ${stats.loopingDaysWithReset} of those ${stats.loopingDays === 1 ? "day" : "days"}.`
    }
  }

  return (
    <div>
      <div className="grid grid-cols-14 gap-1.5">
        {days.map(d => {
          const label = new Date(d.date + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })
          const title = !d.hasEntry ? `${label}: no entry` : d.rumination ? `${label}: overthinking ${d.rumination}${d.resetDone ? ", reset done" : ""}` : `${label}: not reflected on`
          return (
            <div
              key={d.date}
              title={title}
              className={`relative aspect-square rounded-[3px] ${d.hasEntry ? "" : "border border-dashed border-black/10 dark:border-white/15"}`}
              style={{ backgroundColor: cellColour(d), opacity: d.rumination ? 0.85 : 1 }}
            >
              {d.resetDone && <span className="absolute inset-0 m-auto w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_0_1px_rgba(0,0,0,0.25)]" aria-hidden="true" />}
            </div>
          )
        })}
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3 text-[11px] text-gray-500">
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ backgroundColor: LEVEL_COLOUR.low }} /> low</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ backgroundColor: LEVEL_COLOUR.moderate }} /> moderate</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ backgroundColor: LEVEL_COLOUR.high }} /> high</span>
        <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-gray-500" /> reset done</span>
      </div>

      {locked ? (
        <p className="text-xs text-gray-500 mt-4">
          Reflect on {unlockAt - stats.analysedDays} more {unlockAt - stats.analysedDays === 1 ? "day" : "days"} to see your overthinking pattern.
        </p>
      ) : (
        <p className="text-sm text-gray-600 dark:text-gray-300 mt-4">{sentence}</p>
      )}

      {pattern && (
        <div className="mt-3 p-3 rounded-xl bg-sky-500/5 border border-sky-500/20 text-sm text-gray-700 dark:text-gray-300">
          That is a pattern worth working on, not a bad day. A daily three-minute reset, ideally first thing in the morning, is the practice this app tracks.{" "}
          <Link href="/energy" className="inline-flex items-center gap-1 text-sky-600 dark:text-sky-400 font-medium hover:underline">
            <Timer className="w-3.5 h-3.5" /> Go to the practice
          </Link>
        </div>
      )}
    </div>
  )
}
