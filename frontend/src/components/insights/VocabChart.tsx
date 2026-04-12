"use client"
import * as React from "react"

interface VocabPoint {
  date: string
  uniqueWordCount: number
  newWordCount: number
}

export function VocabChart({ data }: { data: VocabPoint[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-[180px] text-gray-500 text-sm">
        No vocabulary data available.
      </div>
    )
  }

  const width = 600
  const height = 180
  const padding = { top: 15, right: 20, bottom: 30, left: 40 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const maxVal = Math.max(...data.map(d => d.uniqueWordCount), 1)
  const barWidth = Math.min(30, chartWidth / data.length - 4)

  const xScale = (i: number) => padding.left + (i + 0.5) * (chartWidth / data.length)
  const yScale = (v: number) => padding.top + chartHeight - (v / maxVal) * chartHeight

  // X-axis labels (show max 7)
  const step = Math.max(1, Math.floor(data.length / 6))

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgb(139, 92, 246)" stopOpacity="0.8" />
          <stop offset="100%" stopColor="rgb(139, 92, 246)" stopOpacity="0.3" />
        </linearGradient>
        <linearGradient id="newBarGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgb(16, 185, 129)" stopOpacity="0.9" />
          <stop offset="100%" stopColor="rgb(16, 185, 129)" stopOpacity="0.4" />
        </linearGradient>
      </defs>

      {/* Grid */}
      {[0, 0.25, 0.5, 0.75, 1].map(frac => {
        const val = Math.round(maxVal * frac)
        return (
          <g key={frac}>
            <line x1={padding.left} y1={yScale(val)} x2={width - padding.right} y2={yScale(val)} stroke="currentColor" strokeOpacity="0.06" strokeDasharray="3 3" />
            <text x={padding.left - 8} y={yScale(val) + 4} textAnchor="end" className="fill-gray-400 text-[9px]">{val}</text>
          </g>
        )
      })}

      {/* Bars */}
      {data.map((d, i) => (
        <g key={i}>
          {/* Unique words (total) */}
          <rect
            x={xScale(i) - barWidth / 2}
            y={yScale(d.uniqueWordCount)}
            width={barWidth}
            height={chartHeight - (yScale(d.uniqueWordCount) - padding.top)}
            fill="url(#barGrad)"
            rx="3"
          />
          {/* New words overlay */}
          {d.newWordCount > 0 && (
            <rect
              x={xScale(i) - barWidth / 2}
              y={yScale(d.newWordCount)}
              width={barWidth}
              height={chartHeight - (yScale(d.newWordCount) - padding.top)}
              fill="url(#newBarGrad)"
              rx="3"
            />
          )}
        </g>
      ))}

      {/* X labels */}
      {data.map((d, i) => {
        if (i % step !== 0 && i !== data.length - 1) return null
        const label = new Date(d.date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        return <text key={i} x={xScale(i)} y={height - 5} textAnchor="middle" className="fill-gray-400 text-[9px]">{label}</text>
      })}

      {/* Legend */}
      <rect x={width - 155} y={4} width={10} height={10} rx="2" fill="url(#barGrad)" />
      <text x={width - 140} y={13} className="fill-gray-500 text-[9px]">Unique Words</text>
      <rect x={width - 65} y={4} width={10} height={10} rx="2" fill="url(#newBarGrad)" />
      <text x={width - 50} y={13} className="fill-gray-500 text-[9px]">New</text>
    </svg>
  )
}
