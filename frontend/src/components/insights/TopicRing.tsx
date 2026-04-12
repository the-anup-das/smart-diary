"use client"
import * as React from "react"

interface TopicData {
  [key: string]: number
}

const COLORS = [
  "rgb(139, 92, 246)",   // violet
  "rgb(59, 130, 246)",   // blue
  "rgb(16, 185, 129)",   // emerald
  "rgb(245, 158, 11)",   // amber
  "rgb(239, 68, 68)",    // red
  "rgb(236, 72, 153)",   // pink
  "rgb(14, 165, 233)",   // sky
  "rgb(168, 85, 247)",   // purple
]

export function TopicRing({ data }: { data: TopicData }) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="flex items-center justify-center h-[200px] text-gray-500 text-sm">
        No focus data available.
      </div>
    )
  }

  const entries = Object.entries(data).sort((a, b) => b[1] - a[1])
  const size = 200
  const cx = size / 2
  const cy = size / 2
  const outerR = 80
  const innerR = 50
  const total = entries.reduce((s, [, v]) => s + v, 0) || 1

  // Build arc segments
  let currentAngle = -90 // Start from top

  const segments = entries.map(([topic, value], i) => {
    const angle = (value / total) * 360
    const startAngle = currentAngle
    const endAngle = currentAngle + angle
    currentAngle = endAngle

    const startRad = (startAngle * Math.PI) / 180
    const endRad = (endAngle * Math.PI) / 180

    const x1Outer = cx + outerR * Math.cos(startRad)
    const y1Outer = cy + outerR * Math.sin(startRad)
    const x2Outer = cx + outerR * Math.cos(endRad)
    const y2Outer = cy + outerR * Math.sin(endRad)
    const x1Inner = cx + innerR * Math.cos(endRad)
    const y1Inner = cy + innerR * Math.sin(endRad)
    const x2Inner = cx + innerR * Math.cos(startRad)
    const y2Inner = cy + innerR * Math.sin(startRad)

    const largeArc = angle > 180 ? 1 : 0

    const path = `
      M ${x1Outer} ${y1Outer}
      A ${outerR} ${outerR} 0 ${largeArc} 1 ${x2Outer} ${y2Outer}
      L ${x1Inner} ${y1Inner}
      A ${innerR} ${innerR} 0 ${largeArc} 0 ${x2Inner} ${y2Inner}
      Z
    `

    return { topic, value, path, color: COLORS[i % COLORS.length] }
  })

  return (
    <div className="flex items-center gap-6">
      <svg viewBox={`0 0 ${size} ${size}`} className="w-[180px] h-[180px] flex-shrink-0">
        {segments.map((seg, i) => (
          <path key={i} d={seg.path} fill={seg.color} stroke="rgb(var(--background))" strokeWidth="2" className="transition-all duration-500 hover:opacity-80" />
        ))}
        {/* Center text */}
        <text x={cx} y={cy - 4} textAnchor="middle" className="fill-gray-500 text-[10px] font-medium">Focus</text>
        <text x={cx} y={cy + 12} textAnchor="middle" className="fill-gray-900 dark:fill-gray-100 text-[14px] font-bold">Topics</text>
      </svg>

      {/* Legend */}
      <div className="flex flex-col space-y-2">
        {segments.map((seg, i) => (
          <div key={i} className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: seg.color }} />
            <span className="text-sm text-gray-700 dark:text-gray-300 capitalize">{seg.topic.replace(/_/g, ' ')}</span>
            <span className="text-xs text-gray-400 font-mono">{Math.round(seg.value * 100)}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}
