"use client"
import * as React from "react"
import { CalendarHeart, X } from "lucide-react"
import { getMoodHex } from "@/lib/mood"

interface Memory {
  id: string
  label: string
  date: string
  preview: string
  moodScore: number | null
}

export function OnThisDay() {
  const [memories, setMemories] = React.useState<Memory[]>([])
  const [visible, setVisible] = React.useState(true)

  React.useEffect(() => {
    fetch("/api/entries/on-this-day")
      .then(res => res.json())
      .then(data => setMemories(data.memories || []))
      .catch(() => {})
  }, [])

  if (memories.length === 0 || !visible) return null

  return (
    <div className="mb-6 fade-in relative mx-2 lg:mx-6">
      <div className="p-5 rounded-2xl bg-gradient-to-r from-amber-500/5 to-transparent border-l-4 border-amber-400 shadow-sm glass-panel">
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-center space-x-2">
            <CalendarHeart className="w-5 h-5 text-amber-500" />
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">On this day</h3>
          </div>
          <button
            onClick={() => setVisible(false)}
            aria-label="Dismiss memories"
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="space-y-3">
          {memories.map(m => (
            <div key={m.id} className="flex items-start gap-3">
              <div className="flex-shrink-0 flex items-center gap-2 w-28 pt-0.5">
                {m.moodScore != null && (
                  <span
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: getMoodHex(m.moodScore) }}
                    title={`Mood ${m.moodScore}/10`}
                  />
                )}
                <span className="text-xs font-semibold text-amber-600 dark:text-amber-400 whitespace-nowrap">{m.label}</span>
              </div>
              <p className="text-sm text-gray-700 dark:text-gray-300 italic leading-relaxed line-clamp-2 flex-1">
                “{m.preview}”
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
