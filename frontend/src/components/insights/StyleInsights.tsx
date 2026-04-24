"use client"
import * as React from "react"
import { Scale, MessageSquare, Zap, Hash } from "lucide-react"

interface StyleInsightsProps {
  data?: {
    avgSelfFocus: number
    highlights: {
      date: string
      words: string[]
      feedback: string
      self_focus_feedback: string
    }[]
  }
}

export function StyleInsights({ data }: StyleInsightsProps) {
  if (!data || data.highlights.length === 0) return null

  const latest = data.highlights[data.highlights.length - 1]
  const selfFocusPct = (data.avgSelfFocus / 10) * 100

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Perspective Mirror (Balance Beam) */}
      <div className="p-5 lg:p-7 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg">
        <div className="flex items-center space-x-2 mb-6">
          <Scale className="w-5 h-5 text-indigo-500" />
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">Perspective Mirror</h3>
        </div>

        <div className="space-y-8">
          <div className="relative pt-4">
            {/* Balance Beam Track */}
            <div className="h-2 w-full bg-black/5 dark:bg-white/5 rounded-full overflow-hidden relative">
              {/* Gradient Overlay */}
              <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/20 via-primary/20 to-indigo-500/20" />
            </div>

            {/* Pivot Point */}
            <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-6 bg-gray-300 dark:bg-gray-600 rounded-full z-0" />

            {/* The Indicator */}
            <div 
              className="absolute top-1/2 -translate-y-1/2 transition-all duration-1000 ease-out z-10"
              style={{ left: `${selfFocusPct}%` }}
            >
              <div className="w-4 h-4 bg-primary rounded-full shadow-[0_0_12px_rgba(139,92,246,0.5)] border-2 border-white dark:border-gray-900" />
              <div className="absolute top-6 left-1/2 -translate-x-1/2 whitespace-nowrap text-[10px] font-bold uppercase tracking-wider text-primary">
                Your Focus
              </div>
            </div>

            {/* Labels */}
            <div className="flex justify-between mt-4 text-[11px] font-medium uppercase tracking-widest">
              <span className="text-emerald-500">World & Others</span>
              <span className="text-indigo-500">Internal & Self</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-primary/5 border border-primary/10">
            <div className="flex items-start space-x-3">
              <MessageSquare className="w-4 h-4 text-primary mt-0.5" />
              <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed italic">
                "{latest.self_focus_feedback}"
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Vocabulary Echoes */}
      <div className="p-5 lg:p-7 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg">
        <div className="flex items-center space-x-2 mb-6">
          <Hash className="w-5 h-5 text-amber-500" />
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">Vocabulary Echoes</h3>
        </div>

        <div className="space-y-6">
          <div className="flex flex-wrap gap-2">
            {latest.words.map((word, i) => (
              <div 
                key={i} 
                className="group relative px-3 py-1.5 rounded-lg bg-amber-500/5 border border-amber-500/10 text-amber-600 dark:text-amber-400 text-sm font-medium transition-all hover:bg-amber-500/10"
              >
                {word}
                <div className="absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-1 bg-gray-800 text-white text-[10px] rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-20">
                  Overused today
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/10">
            <div className="flex items-start space-x-3">
              <Zap className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-[11px] font-bold uppercase tracking-wider text-amber-600 mb-1">Writing Tip</p>
                <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                  {latest.feedback}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
