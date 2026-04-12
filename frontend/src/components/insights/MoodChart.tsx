"use client"
import * as React from "react"
import { getMoodHex } from "@/lib/mood"

interface DataPoint {
  date: string
  moodScore: number
  grammarScore: number
}

export function MoodChart({ data }: { data: DataPoint[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-[200px] text-gray-500 text-sm">
        No data available for this period.
      </div>
    )
  }

  const width = 600
  const height = 220
  const padding = { top: 20, right: 20, bottom: 30, left: 35 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const xScale = (i: number) => padding.left + (i / Math.max(data.length - 1, 1)) * chartWidth
  const yScale = (v: number) => padding.top + chartHeight - ((v - 1) / 9) * chartHeight

  const buildPath = (key: "moodScore" | "grammarScore") => {
    return data.map((d, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yScale(d[key])}`).join(" ")
  }

  const buildArea = (key: "moodScore" | "grammarScore") => {
    const line = data.map((d, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yScale(d[key])}`).join(" ")
    return `${line} L ${xScale(data.length - 1)} ${padding.top + chartHeight} L ${xScale(0)} ${padding.top + chartHeight} Z`
  }

  // Y-axis labels
  const yLabels = [1, 3, 5, 7, 10]

  // X-axis labels (show max 7)
  const step = Math.max(1, Math.floor(data.length / 6))

  // Build gradient stops for the emotional landscape background
  const moodGradientStops = [
    { offset: "0%", color: "#8b5cf6", opacity: 0.06 },    // violet (top = 10)
    { offset: "25%", color: "#10b981", opacity: 0.06 },    // green (7-8)
    { offset: "50%", color: "#f59e0b", opacity: 0.06 },    // amber (5-6)
    { offset: "75%", color: "#f97316", opacity: 0.06 },    // orange (3-4)
    { offset: "100%", color: "#ef4444", opacity: 0.06 },   // red (bottom = 1)
  ]

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
      <defs>
        {/* Emotional landscape background gradient */}
        <linearGradient id="emotionalBg" x1="0" y1="0" x2="0" y2="1">
          {moodGradientStops.map((s, i) => (
            <stop key={i} offset={s.offset} stopColor={s.color} stopOpacity={s.opacity} />
          ))}
        </linearGradient>

        {/* Mood line fill gradient — colored by data */}
        <linearGradient id="moodFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgb(139, 92, 246)" stopOpacity="0.25" />
          <stop offset="100%" stopColor="rgb(139, 92, 246)" stopOpacity="0.02" />
        </linearGradient>

        <linearGradient id="grammarFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgb(59, 130, 246)" stopOpacity="0.15" />
          <stop offset="100%" stopColor="rgb(59, 130, 246)" stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {/* Emotional landscape background */}
      <rect x={padding.left} y={padding.top} width={chartWidth} height={chartHeight} fill="url(#emotionalBg)" rx="6" />

      {/* Zone labels on the right */}
      <text x={width - padding.right - 4} y={yScale(9)} textAnchor="end" className="fill-violet-400/50 text-[8px] font-medium">Thriving</text>
      <text x={width - padding.right - 4} y={yScale(7)} textAnchor="end" className="fill-emerald-400/50 text-[8px] font-medium">Good</text>
      <text x={width - padding.right - 4} y={yScale(5)} textAnchor="end" className="fill-amber-400/50 text-[8px] font-medium">Balanced</text>
      <text x={width - padding.right - 4} y={yScale(3)} textAnchor="end" className="fill-orange-400/50 text-[8px] font-medium">Low</text>

      {/* Grid lines */}
      {yLabels.map(v => (
        <g key={v}>
          <line x1={padding.left} y1={yScale(v)} x2={width - padding.right} y2={yScale(v)} stroke="currentColor" strokeOpacity="0.06" strokeDasharray="4 4" />
          <text x={padding.left - 8} y={yScale(v) + 4} textAnchor="end" className="fill-gray-400 text-[10px]">{v}</text>
        </g>
      ))}

      {/* Area fills */}
      <path d={buildArea("moodScore")} fill="url(#moodFill)" />
      <path d={buildArea("grammarScore")} fill="url(#grammarFill)" />

      {/* Lines */}
      <path d={buildPath("grammarScore")} fill="none" stroke="rgb(59, 130, 246)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="6 3" strokeOpacity="0.6" />
      <path d={buildPath("moodScore")} fill="none" stroke="rgb(139, 92, 246)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

      {/* Data points — colored by mood value */}
      {data.map((d, i) => (
        <g key={`m${i}`}>
          <circle cx={xScale(i)} cy={yScale(d.moodScore)} r="5" fill={getMoodHex(d.moodScore)} fillOpacity="0.2" />
          <circle cx={xScale(i)} cy={yScale(d.moodScore)} r="3.5" fill={getMoodHex(d.moodScore)} stroke="white" strokeWidth="1.5" className="drop-shadow-sm" />
        </g>
      ))}

      {/* X-axis labels */}
      {data.map((d, i) => {
        if (i % step !== 0 && i !== data.length - 1) return null
        const label = new Date(d.date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        return (
          <text key={i} x={xScale(i)} y={height - 5} textAnchor="middle" className="fill-gray-400 text-[10px]">{label}</text>
        )
      })}

      {/* Legend */}
      <circle cx={padding.left + 8} cy={12} r="4" fill="rgb(139, 92, 246)" />
      <text x={padding.left + 16} y={16} className="fill-gray-500 text-[10px]">Mood</text>
      <line x1={padding.left + 55} y1={12} x2={padding.left + 70} y2={12} stroke="rgb(59, 130, 246)" strokeWidth="1.5" strokeDasharray="4 2" />
      <text x={padding.left + 74} y={16} className="fill-gray-500 text-[10px]">Grammar</text>
    </svg>
  )
}
