"use client"

import * as React from "react"
import { Flame, Check, ArrowUpRight, ArrowDownRight, Minus } from "lucide-react"
import { fetchFuels, toggleChallenge, FUEL_STYLES, LEVEL_LABELS, type Fuel, type FuelsData } from "@/lib/fuels"

/**
 * Four Fuels: the last seven days of entries read as four gauges (drive, bond, calm, spark) with
 * one small act for whichever ran low. Honest by design: it counts what the entries mention and
 * says so; it does not claim to measure brain chemistry.
 */
export function FuelGauges() {
  const [data, setData] = React.useState<FuelsData | null>(null)
  const [busy, setBusy] = React.useState<string | null>(null)

  const load = React.useCallback(async () => {
    const d = await fetchFuels()
    setData(d)
  }, [])

  React.useEffect(() => {
    let cancelled = false
    fetchFuels().then(d => { if (!cancelled) setData(d) })
    return () => { cancelled = true }
  }, [])

  const onToggle = async (fuel: Fuel) => {
    if (busy) return
    setBusy(fuel.key)
    const next = !fuel.challenge.doneToday
    // Optimistic: flip the tick now, reload the gauges once the server has counted it.
    setData(prev => prev ? { ...prev, fuels: prev.fuels.map(f => f.key === fuel.key ? { ...f, challenge: { ...f.challenge, doneToday: next } } : f) } : prev)
    const ok = await toggleChallenge(fuel.challenge.id, next)
    if (ok) await load()
    else setData(prev => prev ? { ...prev, fuels: prev.fuels.map(f => f.key === fuel.key ? { ...f, challenge: { ...f.challenge, doneToday: !next } } : f) } : prev)
    setBusy(null)
  }

  if (!data) return null
  const empty = data.window.entries === 0

  return (
    <div className="p-5 lg:p-7 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg">
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 flex items-center space-x-2">
            <Flame className="w-5 h-5 text-orange-500" />
            <span>Four Fuels</span>
          </h3>
          <p className="text-xs text-gray-500 mt-1">
            Drive, bond, calm and spark: the four drives behind mood and motivation, read from what your last seven days of entries mention. One small act for whichever ran low.
          </p>
        </div>
        <div className="md:text-right md:max-w-xs">
          <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{data.headline}</p>
          {!empty && (
            <p className="text-xs text-gray-500 mt-0.5">
              from {data.window.entries} analysed {data.window.entries === 1 ? "entry" : "entries"} in the last {data.window.days} days
              {data.window.entries < 3 ? ", so take the gauges lightly" : ""}
            </p>
          )}
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 lg:grid-cols-2 gap-4">
        {data.fuels.map(fuel => (
          <FuelRow key={fuel.key} fuel={fuel} empty={empty} busy={busy === fuel.key} onToggle={() => onToggle(fuel)} />
        ))}
      </div>

      <details className="mt-4 text-xs text-gray-500">
        <summary className="cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-300">How this is worked out</summary>
        <p className="mt-2 leading-relaxed">
          {data.source.kind === "model"
            ? `The model${data.source.model ? ` (${data.source.model})` : ""} read this week's entries and noted, day by day, what fed or drained each fuel, quoting the entry for each. It is asked again once a day or when a new entry lands.`
            : "The model was not available, so these gauges come from the signals already stored with each analysed entry: activities, screen habits, mood, rumination and emotion words."}
          {" "}{data.note} Each analysed day counts once as fed, drained, both or neither, so the gauge is the balance of days, not of mentions.
          A challenge you tick counts as feeding its fuel that day, and where it matches a Mind Fitness activity it is logged there too.
          The framing follows the DOSE idea (dopamine, oxytocin, serotonin, endorphins): cheap rewards are everywhere, the other three take small daily acts.
        </p>
      </details>
    </div>
  )
}

function FuelRow({ fuel, empty, busy, onToggle }: { fuel: Fuel; empty: boolean; busy: boolean; onToggle: () => void }) {
  const style = FUEL_STYLES[fuel.key]
  const score = fuel.score ?? 0
  const delta = fuel.score !== null && fuel.previous !== null ? fuel.score - fuel.previous : null
  const done = fuel.challenge.doneToday
  const levelTone =
    fuel.level === "low" ? "text-rose-500" :
    fuel.level === "strong" ? "text-emerald-500" :
    fuel.level === "steady" ? "text-amber-500" : "text-gray-400"

  return (
    <div className="rounded-xl border border-black/5 dark:border-white/10 bg-white/40 dark:bg-white/5 p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <div className="min-w-0">
          <span className="font-semibold text-gray-900 dark:text-gray-100">{fuel.label}</span>
          <span className="ml-2 text-xs text-gray-500">{fuel.chemical} · {fuel.tagline}</span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 text-xs">
          <span className={`font-medium ${levelTone}`}>{LEVEL_LABELS[fuel.level]}</span>
          {delta !== null && (
            <span className="inline-flex items-center gap-0.5 text-gray-500" title="compared with the seven days before">
              {delta > 0 ? <ArrowUpRight className="w-3.5 h-3.5 text-emerald-500" /> : delta < 0 ? <ArrowDownRight className="w-3.5 h-3.5 text-rose-500" /> : <Minus className="w-3.5 h-3.5" />}
              {delta > 0 ? `+${delta}` : delta}
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex-1 h-2 rounded-full bg-black/5 dark:bg-white/10 overflow-hidden">
          <div className={`h-full ${style.bar} transition-all duration-700`} style={{ width: `${fuel.score === null ? 0 : score}%` }} />
        </div>
        <span className="w-8 text-right font-mono text-xs text-gray-500">{fuel.score === null ? "–" : fuel.score}</span>
      </div>

      <div className="flex items-center gap-1" aria-label="the last seven days">
        {fuel.days.map(d => (
          <span
            key={d.date}
            title={`${d.date}: ${!d.analysed ? "no entry" : d.fed && d.drained ? "fed and drained" : d.fed ? "fed" : d.drained ? "drained" : "no signal"}`}
            className={`h-2 flex-1 rounded-sm ${
              !d.analysed ? "bg-transparent border border-dashed border-black/10 dark:border-white/15" :
              d.fed && d.drained ? "bg-amber-400" : d.fed ? "bg-emerald-500" : d.drained ? "bg-rose-500" : "bg-gray-300 dark:bg-gray-600"
            }`}
          />
        ))}
      </div>

      <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">{empty ? `Fed by ${fuel.fedBy}. Drained by ${fuel.drainedBy}.` : fuel.because}</p>

      <div className={`rounded-lg p-3 flex items-start gap-3 ${done ? "bg-emerald-500/10" : "bg-black/5 dark:bg-white/5"}`}>
        <button
          type="button"
          onClick={onToggle}
          disabled={busy}
          aria-pressed={done}
          className={`mt-0.5 w-5 h-5 rounded-md border flex items-center justify-center flex-shrink-0 transition-colors ${
            done ? "bg-emerald-500 border-emerald-500 text-white" : "border-gray-400 dark:border-gray-500 hover:border-emerald-500"
          } ${busy ? "opacity-60" : ""}`}
          title={done ? "Done today. Click to undo." : "Mark done for today"}
        >
          {done && <Check className="w-3.5 h-3.5" />}
        </button>
        <div className="min-w-0">
          <p className={`text-sm ${done ? "line-through text-gray-500" : "text-gray-800 dark:text-gray-200"}`}>{fuel.challenge.text}</p>
          <p className="text-xs text-gray-500 mt-0.5">{fuel.challenge.why}{fuel.challenge.builder ? ` Counts towards ${fuel.challenge.builder.replace("_", " ")} in Mind Fitness.` : ""}</p>
        </div>
      </div>
    </div>
  )
}
