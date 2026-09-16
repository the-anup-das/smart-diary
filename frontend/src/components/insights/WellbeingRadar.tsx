"use client"
import * as React from "react"
import { Info, ExternalLink, X } from "lucide-react"
import { AXIS_GUIDES, type WellbeingAxis } from "@/lib/wellbeing"

/**
 * WellbeingRadar - six capacities on one scale, drawn as a radar with the exact values
 * listed beside it. The radar gives the shape; the bars give the numbers. When a previous
 * period is supplied it is drawn as a fainter dashed polygon and each bar shows the change.
 *
 * Rules that keep a radar honest: fixed axes in a fixed order, every axis pointing the
 * same way (higher is better), no score derived from the polygon area.
 */

const CURRENT = "#8b5cf6"
const PREVIOUS = "#9ca3af"
const VIEW_W = 440
const VIEW_H = 300
const CX = 220
const CY = 150
const R = 100
const LABEL_R = 128

export function WellbeingRadar({
  axes, currentLabel = "This period", compareLabel = null,
}: {
  axes: WellbeingAxis[]
  currentLabel?: string
  /** Label for the previous-period polygon; omit or null to hide the comparison. */
  compareLabel?: string | null
}) {
  const [hovered, setHovered] = React.useState<number | null>(null)
  const [openGuide, setOpenGuide] = React.useState<string | null>(null)
  const n = axes.length
  const angle = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / n
  const point = (i: number, radius: number): [number, number] => [CX + Math.cos(angle(i)) * radius, CY + Math.sin(angle(i)) * radius]
  const valuePoint = (i: number, v: number | null | undefined) => point(i, (R * Math.max(0, Math.min(100, v ?? 0))) / 100)
  const polygon = (get: (a: WellbeingAxis) => number | null | undefined) =>
    axes.map((a, i) => valuePoint(i, get(a))).map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ")

  const showPrevious = !!compareLabel && axes.some(a => typeof a.previous === "number")

  return (
    <div className="flex flex-col lg:flex-row items-center gap-6">
      <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} className="w-full max-w-[400px] h-auto flex-shrink-0" role="img" aria-label="Wellbeing profile radar">
        {[25, 50, 75, 100].map(ring => (
          <polygon
            key={ring}
            points={axes.map((_, i) => point(i, (R * ring) / 100)).map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ")}
            fill="none"
            stroke="currentColor"
            strokeOpacity={ring === 100 ? 0.18 : 0.07}
            strokeWidth="1"
          />
        ))}
        {axes.map((a, i) => {
          const [x, y] = point(i, R)
          return <line key={a.key} x1={CX} y1={CY} x2={x} y2={y} stroke="currentColor" strokeOpacity="0.1" strokeWidth="1" />
        })}

        {showPrevious && (
          <polygon points={polygon(a => a.previous)} fill={PREVIOUS} fillOpacity="0.12" stroke={PREVIOUS} strokeWidth="1.5" strokeDasharray="4 3" strokeLinejoin="round" />
        )}
        <polygon points={polygon(a => a.value)} fill={CURRENT} fillOpacity="0.22" stroke={CURRENT} strokeWidth="2.5" strokeLinejoin="round" className="transition-all duration-700 ease-out" />

        {axes.map((a, i) => {
          const [x, y] = valuePoint(i, a.value)
          const missing = a.value === null
          return (
            <g key={a.key} onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)}>
              <circle cx={x} cy={y} r={hovered === i ? 5.5 : 3.5} fill={missing ? "#d1d5db" : CURRENT} stroke="white" strokeWidth="1.5" className="transition-all duration-150" />
              <circle cx={x} cy={y} r="12" fill="transparent" />
            </g>
          )
        })}

        {axes.map((a, i) => {
          const [x, y] = point(i, LABEL_R)
          const c = Math.cos(angle(i))
          const anchor = Math.abs(c) < 0.2 ? "middle" : c > 0 ? "start" : "end"
          const active = hovered === i
          return (
            <text key={a.key} x={x} y={y + 4} textAnchor={anchor} fontSize="11" fontWeight={active ? 700 : 600} fill={active ? CURRENT : "currentColor"} fillOpacity={active ? 1 : 0.7}>
              {a.label}
              {active && a.value !== null && <tspan fontWeight="500" fillOpacity="0.8"> {Math.round(a.value)}</tspan>}
            </text>
          )
        })}
      </svg>

      <div className="w-full flex-1 min-w-0">
        {showPrevious && (
          <div className="flex items-center gap-4 text-xs text-gray-500 mb-3">
            <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: CURRENT, opacity: 0.8 }} /> {currentLabel}</span>
            <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-0 border-t-2 border-dashed" style={{ borderColor: PREVIOUS }} /> {compareLabel}</span>
          </div>
        )}
        <div className="space-y-2.5">
          {axes.map((a, i) => {
            const delta = a.value !== null && typeof a.previous === "number" && showPrevious ? Math.round(a.value - a.previous) : null
            return (
              <div
                key={a.key}
                className={`flex items-center gap-3 rounded-lg px-2 py-1 -mx-2 transition-colors ${hovered === i ? "bg-primary/5" : ""}`}
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                title={a.description}
              >
                <span className="w-28 text-sm font-medium text-gray-700 dark:text-gray-300 flex-shrink-0">{a.label}</span>
                <div className="relative flex-1 h-2 bg-black/5 dark:bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-700 ease-out" style={{ width: `${a.value ?? 0}%`, backgroundColor: CURRENT }} />
                  {showPrevious && typeof a.previous === "number" && (
                    <div className="absolute top-0 h-full w-0.5" style={{ left: `calc(${a.previous}% - 1px)`, backgroundColor: PREVIOUS }} aria-hidden="true" />
                  )}
                </div>
                <span className="w-10 text-right text-sm font-mono tabular-nums text-gray-600 dark:text-gray-300">
                  {a.value === null ? <span className="text-gray-400 text-xs">n/a</span> : Math.round(a.value)}
                </span>
                {showPrevious && (
                  <span className={`w-9 text-right text-xs font-mono tabular-nums ${
                    delta === null ? "text-gray-300" : delta > 0 ? "text-emerald-500" : delta < 0 ? "text-rose-500" : "text-gray-400"
                  }`}>
                    {delta === null ? "" : delta > 0 ? `+${delta}` : delta < 0 ? `−${Math.abs(delta)}` : "0"}
                  </span>
                )}
                <button
                  onClick={() => setOpenGuide(openGuide === a.key ? null : a.key)}
                  aria-expanded={openGuide === a.key}
                  aria-label={`About ${a.label}`}
                  title={`What ${a.label.toLowerCase()} means and why it matters`}
                  className={`p-1 rounded-md transition-colors cursor-pointer ${openGuide === a.key ? "text-primary bg-primary/10" : "text-gray-400 hover:text-primary hover:bg-primary/5"}`}
                >
                  <Info className="w-3.5 h-3.5" />
                </button>
              </div>
            )
          })}
        </div>
        {openGuide && AXIS_GUIDES[openGuide] && (
          <AxisGuidePanel axisKey={openGuide} label={axes.find(a => a.key === openGuide)?.label || openGuide} onClose={() => setOpenGuide(null)} />
        )}
        <div className="hidden">
        </div>
      </div>
    </div>
  )
}

/** What an axis means, why it matters for wellbeing, how this app measures it, and where to read more. */
function AxisGuidePanel({ axisKey, label, onClose }: { axisKey: string; label: string; onClose: () => void }) {
  const guide = AXIS_GUIDES[axisKey]
  return (
    <div className="mt-3 p-4 rounded-xl bg-primary/5 border border-primary/15 text-sm fade-in" role="region" aria-label={`About ${label}`}>
      <div className="flex items-start justify-between gap-3">
        <h4 className="font-semibold text-gray-900 dark:text-gray-100">{label}</h4>
        <button onClick={onClose} aria-label="Close" className="p-1 rounded-md text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
      </div>
      <p className="text-gray-700 dark:text-gray-300 mt-1">{guide.what}</p>
      <dl className="mt-3 space-y-2 text-[13px]">
        <div><dt className="text-[10px] uppercase tracking-widest text-gray-400">Why it matters</dt><dd className="text-gray-700 dark:text-gray-300">{guide.why}</dd></div>
        <div><dt className="text-[10px] uppercase tracking-widest text-gray-400">How it is measured here</dt><dd className="text-gray-600 dark:text-gray-400">{guide.measured}</dd></div>
        <div><dt className="text-[10px] uppercase tracking-widest text-gray-400">What tends to move it</dt><dd className="text-gray-600 dark:text-gray-400">{guide.moves}</dd></div>
      </dl>
      <a href={guide.link.href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 mt-3 text-xs font-medium text-primary hover:underline">
        Read more: {guide.link.label} <ExternalLink className="w-3 h-3" />
      </a>
    </div>
  )
}
