"use client"
import React from "react"
import { motion } from "framer-motion"
import { Zap, ArrowUpCircle, ArrowDownCircle } from "lucide-react"
import { InfoTooltip } from "@/components/ui/InfoTooltip"

interface HumanBatteryProps {
  level: number // 0 to 100
  chargers: string[]
  drainers: string[]
}

export function HumanBattery({ level, chargers, drainers }: HumanBatteryProps) {
  // Determine color based on level
  let colorClass = "from-green-500 to-emerald-400"
  let bgClass = "bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20"
  if (level < 30) {
    colorClass = "from-red-500 to-rose-400"
    bgClass = "bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20"
  } else if (level < 60) {
    colorClass = "from-yellow-500 to-amber-400"
    bgClass = "bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 border-yellow-500/20"
  }

  return (
    <div className="bg-card border rounded-2xl p-6 shadow-sm overflow-hidden relative">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Zap className={`w-5 h-5 ${level < 30 ? 'text-red-500' : level < 60 ? 'text-yellow-500' : 'text-green-500'}`} />
            Current Energy
            <InfoTooltip text="Your overall battery is calculated using a formula based on your mood, the ratio of positive chargers vs. drainers, and how much you're focusing on things within your control." />
          </h2>
          <p className="text-sm text-muted-foreground mt-1">Based on today's analysis</p>
        </div>
        <div className={`text-3xl font-bold px-4 py-2 rounded-xl border ${bgClass}`}>
          {level}%
        </div>
      </div>

      {/* Battery Visual */}
      <div className="relative h-12 w-full bg-secondary rounded-full overflow-hidden mb-8 border shadow-inner">
        <motion.div 
          className={`absolute top-0 left-0 h-full rounded-full bg-gradient-to-r ${colorClass}`}
          initial={{ width: 0 }}
          animate={{ width: `${level}%` }}
          transition={{ duration: 1.5, ease: "easeOut" }}
        >
          {/* Shimmer effect */}
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent w-[200%] animate-shimmer" />
        </motion.div>
      </div>

      {/* Chargers and Drainers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-3 text-green-600 dark:text-green-400">
            <ArrowUpCircle className="w-4 h-4" />
            What's Charging You
          </h3>
          <div className="flex flex-wrap gap-2">
            {chargers.length === 0 ? (
              <span className="text-sm text-muted-foreground italic">No clear chargers identified yet.</span>
            ) : (
              chargers.map((charger, i) => (
                <span key={i} className="px-3 py-1.5 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 text-sm rounded-lg border border-green-200 dark:border-green-800/50">
                  {charger}
                </span>
              ))
            )}
          </div>
        </div>
        
        <div>
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-3 text-red-600 dark:text-red-400">
            <ArrowDownCircle className="w-4 h-4" />
            What's Draining You
          </h3>
          <div className="flex flex-wrap gap-2">
            {drainers.length === 0 ? (
              <span className="text-sm text-muted-foreground italic">No clear drainers identified yet.</span>
            ) : (
              drainers.map((drainer, i) => (
                <span key={i} className="px-3 py-1.5 bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 text-sm rounded-lg border border-red-200 dark:border-red-800/50">
                  {drainer}
                </span>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
