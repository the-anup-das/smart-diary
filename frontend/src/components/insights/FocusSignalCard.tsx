"use client"
import * as React from "react"
import Link from "next/link"
import { Crosshair, ArrowRight } from "lucide-react"
import { fetchOverview, type FocusOverview } from "@/lib/focus"

const LOAD_COLOUR = ["transparent", "#fbbf24", "#f97316", "#f43f5e"]

/** Insights card for stimulation signals. Renders nothing at all unless the entries carry a signal or a plan is running. */
export function FocusSignalCard() {
  const [data, setData] = React.useState<FocusOverview | null>(null)
  React.useEffect(() => {
    let cancelled = false
    fetchOverview().then(d => { if (!cancelled) setData(d) })
    return () => { cancelled = true }
  }, [])
  if (!data || !data.active) return null

  const top = data.topBehaviours.slice(0, 3)
  const tod = Object.entries(data.timeOfDay).sort((a, b) => b[1] - a[1])[0]?.[0]
  const after = Object.entries(data.afterStates).sort((a, b) => b[1] - a[1])[0]?.[0]
  const plan = data.plan

  return (
    <div className="p-5 lg:p-7 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg">
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 flex items-center space-x-2">
            <Crosshair className="w-5 h-5 text-teal-500" />
            <span>Focus & Stimulation</span>
          </h3>
          <p className="text-xs text-gray-500 mt-1">Reward-seeking habits your entries mention, over the last four weeks. Shown only while there is a signal.</p>
        </div>
        <Link href="/focus" className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-sm font-medium transition-colors whitespace-nowrap flex-shrink-0">
          {plan ? `Day ${plan.dayNumber} of ${plan.abstinenceDays}` : "Open Focus Reset"} <ArrowRight className="w-4 h-4" />
        </Link>
      </div>

      <div className="grid grid-cols-14 gap-1.5 mt-5">
        {data.days.map(d => (
          <div key={d.date} title={`${d.date}: ${d.analysed ? (d.load ? `load ${d.load}, ${d.behaviours.map(b => b.behaviour).join(", ")}` : "no signal") : "not reflected"}`}
            className={`aspect-square rounded-[3px] ${d.analysed ? "" : "border border-dashed border-black/10 dark:border-white/15"}`}
            style={{ backgroundColor: d.load ? LOAD_COLOUR[Math.min(3, d.load)] : d.analysed ? "rgba(156,163,175,0.25)" : "transparent", opacity: 0.85 }} />
        ))}
      </div>

      <p className="text-sm text-gray-600 dark:text-gray-300 mt-4">
        Signals on {data.signalDays} of {data.analysedDays} reflected days
        {data.heavyDays ? `, ${data.heavyDays} heavy` : ""}
        {top.length ? `. Mostly ${top.map(b => `${b.label} (${b.count})`).join(", ")}` : ""}
        {tod && tod !== "unknown" ? `, usually in the ${tod}` : ""}
        {after ? `, followed by feeling ${after}` : ""}.
        {data.lostControlDays ? ` Lost track of time on ${data.lostControlDays}.` : ""}
      </p>
      {plan && (
        <p className="text-sm text-teal-700 dark:text-teal-300 mt-2">
          Reset in progress for {plan.behaviour}: {plan.cleanStreak} clean {plan.cleanStreak === 1 ? "day" : "days"} in a row, {plan.urges.surfed} of {plan.urges.total} urges surfed.
        </p>
      )}
    </div>
  )
}
