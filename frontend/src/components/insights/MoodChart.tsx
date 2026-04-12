"use client"
import * as React from "react"
import { getMoodHex, getMoodTier } from "@/lib/mood"

interface DataPoint {
  date: string
  moodScore: number
  grammarScore: number
  sentiment?: string
}

export function MoodChart({ data }: { data: DataPoint[] }) {
  const [hovered, setHovered] = React.useState<number | null>(null)

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

  const yLabels = [1, 3, 5, 7, 10]
  const step = Math.max(1, Math.floor(data.length / 6))

  const moodGradientStops = [
    { offset: "0%", color: "#8b5cf6", opacity: 0.06 },
    { offset: "25%", color: "#10b981", opacity: 0.06 },
    { offset: "50%", color: "#f59e0b", opacity: 0.06 },
    { offset: "75%", color: "#f97316", opacity: 0.06 },
    { offset: "100%", color: "#ef4444", opacity: 0.06 },
  ]

  const hoveredData = hovered !== null ? data[hovered] : null

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="emotionalBg" x1="0" y1="0" x2="0" y2="1">
            {moodGradientStops.map((s, i) => (
              <stop key={i} offset={s.offset} stopColor={s.color} stopOpacity={s.opacity} />
            ))}
          </linearGradient>
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

        {/* Zone labels */}
        <text x={width - padding.right - 4} y={yScale(9)} textAnchor="end" fontSize="8" fill="#a78bfa" fillOpacity="0.5" fontWeight="500">Thriving</text>
        <text x={width - padding.right - 4} y={yScale(7)} textAnchor="end" fontSize="8" fill="#34d399" fillOpacity="0.5" fontWeight="500">Good</text>
        <text x={width - padding.right - 4} y={yScale(5)} textAnchor="end" fontSize="8" fill="#fbbf24" fillOpacity="0.5" fontWeight="500">Balanced</text>
        <text x={width - padding.right - 4} y={yScale(3)} textAnchor="end" fontSize="8" fill="#fb923c" fillOpacity="0.5" fontWeight="500">Low</text>

        {/* Grid lines */}
        {yLabels.map(v => (
          <g key={v}>
            <line x1={padding.left} y1={yScale(v)} x2={width - padding.right} y2={yScale(v)} stroke="currentColor" strokeOpacity="0.06" strokeDasharray="4 4" />
            <text x={padding.left - 8} y={yScale(v) + 4} textAnchor="end" fontSize="10" fill="#9ca3af">{v}</text>
          </g>
        ))}

        {/* Area fills */}
        <path d={buildArea("moodScore")} fill="url(#moodFill)" />
        <path d={buildArea("grammarScore")} fill="url(#grammarFill)" />

        {/* Lines */}
        <path d={buildPath("grammarScore")} fill="none" stroke="rgb(59, 130, 246)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="6 3" strokeOpacity="0.6" />
        <path d={buildPath("moodScore")} fill="none" stroke="rgb(139, 92, 246)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

        {/* Hover vertical line */}
        {hovered !== null && (
          <line
            x1={xScale(hovered)} y1={padding.top}
            x2={xScale(hovered)} y2={padding.top + chartHeight}
            stroke="currentColor" strokeOpacity="0.15" strokeWidth="1" strokeDasharray="3 3"
          />
        )}

        {/* Data points */}
        {data.map((d, i) => {
          const isHovered = hovered === i
          return (
            <g key={`m${i}`}>
              <circle cx={xScale(i)} cy={yScale(d.moodScore)} r={isHovered ? 7 : 5} fill={getMoodHex(d.moodScore)} fillOpacity={isHovered ? 0.3 : 0.2} className="transition-all duration-150" />
              <circle cx={xScale(i)} cy={yScale(d.moodScore)} r={isHovered ? 5 : 3.5} fill={getMoodHex(d.moodScore)} stroke="white" strokeWidth="1.5" className="drop-shadow-sm transition-all duration-150" />
              {/* Invisible hit area for hover */}
              <circle
                cx={xScale(i)} cy={(padding.top + chartHeight) / 2 + padding.top / 2}
                r={Math.max(chartWidth / data.length / 2, 12)}
                fill="transparent"
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                className="cursor-pointer"
              />
            </g>
          )
        })}

        {/* X-axis labels */}
        {data.map((d, i) => {
          if (i % step !== 0 && i !== data.length - 1) return null
          const label = new Date(d.date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
          return <text key={i} x={xScale(i)} y={height - 5} textAnchor="middle" fontSize="10" fill="#9ca3af">{label}</text>
        })}

        {/* Legend */}
        <circle cx={padding.left + 8} cy={12} r="4" fill="rgb(139, 92, 246)" />
        <text x={padding.left + 16} y={16} fontSize="10" fill="#6b7280">Mood</text>
        <line x1={padding.left + 55} y1={12} x2={padding.left + 70} y2={12} stroke="rgb(59, 130, 246)" strokeWidth="1.5" strokeDasharray="4 2" />
        <text x={padding.left + 74} y={16} fontSize="10" fill="#6b7280">Grammar</text>
      </svg>

      {/* Tooltip (HTML overlay for better styling) */}
      {hoveredData && hovered !== null && (
        <div
          className="absolute pointer-events-none z-10 px-3 py-2 rounded-xl bg-white/90 dark:bg-gray-900/90 backdrop-blur-md border border-black/10 dark:border-white/10 shadow-xl transform -translate-x-1/2 -translate-y-full transition-all duration-150"
          style={{
            left: `${(xScale(hovered) / width) * 100}%`,
            top: `${(yScale(hoveredData.moodScore) / height) * 100}%`,
            marginTop: '-8px',
          }}
        >
          <p className="text-xs text-gray-500 font-mono mb-1">
            {new Date(hoveredData.date + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
          </p>
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-1">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: getMoodHex(hoveredData.moodScore) }} />
              <span className="text-sm font-bold" style={{ color: getMoodTier(hoveredData.moodScore).hex }}>
                {getMoodTier(hoveredData.moodScore).label}
              </span>
              <span className="text-xs text-gray-400">{hoveredData.moodScore}/10</span>
            </div>
            <div className="text-xs text-gray-400">·</div>
            <div className="text-xs text-blue-400">G: {hoveredData.grammarScore}/10</div>
          </div>
          {hoveredData.sentiment && (
            <p className="text-xs text-gray-400 mt-0.5">{hoveredData.sentiment}</p>
          )}
        </div>
      )}
    </div>
  )
}
