import * as React from "react"
import { Target } from "lucide-react"

export function TargetsWidget({ targets }: { targets: any }) {
  if (!targets) return null

  const targetItems = [
    { key: "daily_words", label: "Daily Words", unit: "words", color: "from-blue-500 to-cyan-400" },
    { key: "consistency_streak", label: "Writing Streak", unit: "days", color: "from-amber-500 to-orange-400" },
    { key: "target_mood", label: "Min Mood", unit: "/ 10", color: "from-emerald-500 to-green-400" },
    { key: "weekly_vocab", label: "New Vocab", unit: "words", color: "from-violet-500 to-purple-400" },
    { key: "weekly_loops", label: "Loops Closed", unit: "tasks", color: "from-pink-500 to-rose-400" },
    { key: "weekly_reframes", label: "Reframes", unit: "insights", color: "from-indigo-500 to-blue-400" },
    { key: "sentiment_diversity", label: "Sentiments", unit: "distinct", color: "from-teal-500 to-emerald-400" },
  ]

  return (
    <div className="p-5 lg:p-7 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg mb-6">
      <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-6 flex items-center space-x-2">
        <Target className="w-5 h-5 text-primary" />
        <span>Current Target Progress</span>
      </h3>
      
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
        {targetItems.map(item => {
          const data = targets[item.key]
          if (!data) return null;
          
          const maxVal = Math.max(data.target, 1)
          const pct = Math.min((data.current / maxVal) * 100, 100)
          const isComplete = data.current >= data.target

          return (
            <div key={item.key} className="flex flex-col items-center justify-center p-3 rounded-xl bg-black/5 dark:bg-white/5 relative overflow-hidden group">
              {/* Subtle background fill when complete */}
              {isComplete && <div className={`absolute inset-0 opacity-10 bg-gradient-to-br ${item.color}`} />}
              
              <div className="relative w-16 h-16 mb-2">
                <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                  <circle cx="50" cy="50" r="40" fill="none" stroke="currentColor" strokeOpacity="0.1" strokeWidth="8" />
                  <circle 
                    cx="50" cy="50" r="40" 
                    fill="none" 
                    stroke="url(#grad)" 
                    strokeOpacity="1" 
                    strokeWidth="8" 
                    strokeDasharray={`${(pct / 100) * 2 * Math.PI * 40} ${2 * Math.PI * 40}`} 
                    strokeLinecap="round" 
                    className="transition-all duration-1000 ease-out" 
                  />
                  <defs>
                    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" className="text-primary" stopColor="currentColor" />
                      <stop offset="100%" className="text-violet-500" stopColor="currentColor" />
                    </linearGradient>
                  </defs>
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className={`text-sm font-bold ${isComplete ? 'text-primary' : 'text-gray-900 dark:text-gray-100'}`}>
                    {data.current}
                  </span>
                </div>
              </div>
              <span className="text-xs font-semibold text-center text-gray-800 dark:text-gray-200">{item.label}</span>
              <span className="text-[10px] text-gray-500 uppercase tracking-widest mt-1">/{data.target} {item.unit}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
