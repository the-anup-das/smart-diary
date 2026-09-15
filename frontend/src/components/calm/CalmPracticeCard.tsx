"use client"
import * as React from "react"
import { Wind, Timer, Check } from "lucide-react"

/**
 * CalmPracticeCard - habit-style view of the 3-Minute Reset on the Energy page:
 * streak, 28-day strip, average before/after change and recent reflections.
 * Data comes from GET /api/calm/summary (routers/calm.py).
 */

interface DayCell {
  date: string
  completed: boolean
  delta: number | null
  sessions: number
}

interface RecentSession {
  id: string
  date: string | null
  delta: number | null
  mindBefore: number | null
  mindAfter: number | null
  note: string | null
  loopThought: string | null
  ruminationType: string | null
  personalized: boolean
}

interface CalmSummary {
  success: boolean
  streak: number
  totalSessions: number
  completedSessions: number
  avgDelta: number | null
  energyBonus?: number
  last28: DayCell[]
  today: { completed: boolean; note: string | null } | null
  recent: RecentSession[]
}

export function CalmPracticeCard({ onStart, refreshKey = 0 }: { onStart: () => void; refreshKey?: number }) {
  const [summary, setSummary] = React.useState<CalmSummary | null>(null)
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    let cancelled = false
    // Days are bucketed in the viewer's local time so a late-night reset counts for the right day.
    fetch(`/api/calm/summary?tz_offset=${-new Date().getTimezoneOffset()}`)
      .then(res => (res.ok ? res.json() : null))
      .then(data => { if (!cancelled && data?.success) setSummary(data) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [refreshKey])

  const doneToday = !!summary?.today?.completed
  const streak = summary?.streak ?? 0
  const strip = summary?.last28 ?? []
  const recent = (summary?.recent ?? []).filter(r => r.note).slice(0, 3)
  const avgDelta = summary?.avgDelta ?? null

  return (
    <div className="p-5 lg:p-7 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Wind className="w-5 h-5 text-sky-500" />
            3-Minute Reset
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            One minute of breathing, one of stillness, one of visualisation. Best done daily, ideally in the morning,
            and any time your thoughts start racing. Rate your mind before and after to watch it settle over time.
            {summary?.energyBonus ? ` A completed reset adds ${summary.energyBonus}% to today's energy battery.` : ""}
          </p>
        </div>
        <button
          onClick={onStart}
          className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-700 text-white font-medium transition-colors cursor-pointer whitespace-nowrap flex-shrink-0"
        >
          <Timer className="w-4 h-4" /> {doneToday ? "Do another reset" : "Start today's reset"}
        </button>
      </div>

      {loading ? (
        <div className="mt-6 h-20 rounded-xl bg-black/5 dark:bg-white/5 animate-pulse" />
      ) : (
        <>
          <div className="mt-6 grid grid-cols-3 gap-3">
            <Stat label="Streak" value={`${streak}`} unit={streak === 1 ? "day" : "days"} accent={streak > 0} />
            <Stat label="Completed" value={`${summary?.completedSessions ?? 0}`} unit="resets" />
            <Stat label="Mind settles by" value={avgDelta === null ? "–" : avgDelta.toFixed(1)} unit="on a 5-point scale" />
          </div>

          <div className="mt-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] uppercase tracking-widest text-gray-400">Last 28 days</span>
              {doneToday && (
                <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                  <Check className="w-3.5 h-3.5" /> Done today
                </span>
              )}
            </div>
            <div className="grid grid-cols-14 gap-1.5">
              {strip.map((day, i) => {
                const isToday = i === strip.length - 1
                const title = `${day.date}${day.completed ? ", done" : day.sessions > 0 ? ", started" : ""}${day.delta !== null ? `, settled by ${day.delta}` : ""}`
                return (
                  <div
                    key={day.date}
                    title={title}
                    className={`aspect-square rounded-[3px] ${
                      day.completed ? "bg-sky-500" : day.sessions > 0 ? "bg-sky-500/30" : "bg-black/5 dark:bg-white/10"
                    } ${isToday ? "ring-2 ring-sky-500/50" : ""}`}
                  />
                )
              })}
            </div>
          </div>

          {recent.length > 0 && (
            <div className="mt-5 space-y-2">
              <span className="text-[11px] uppercase tracking-widest text-gray-400">After recent resets</span>
              {recent.map(r => (
                <div key={r.id} className="flex items-start gap-3 text-sm p-3 rounded-lg bg-black/[0.03] dark:bg-white/5">
                  <span className="font-mono text-xs text-gray-400 flex-shrink-0 mt-0.5">{r.date}</span>
                  <span className="text-gray-700 dark:text-gray-300 flex-1">{r.note}</span>
                  {r.delta !== null && r.delta > 0 && (
                    <span className="text-xs text-emerald-600 dark:text-emerald-400 flex-shrink-0">settled by {r.delta}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Stat({ label, value, unit, accent }: { label: string; value: string; unit: string; accent?: boolean }) {
  return (
    <div className="p-3 rounded-xl bg-black/[0.03] dark:bg-white/5 text-center">
      <p className="text-[10px] uppercase tracking-widest text-gray-400">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${accent ? "text-sky-600 dark:text-sky-400" : ""}`}>{value}</p>
      <p className="text-[11px] text-gray-500">{unit}</p>
    </div>
  )
}
