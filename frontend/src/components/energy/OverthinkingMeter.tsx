"use client"
import React from "react"
import { BrainCircuit } from "lucide-react"
import { InfoTooltip } from "@/components/ui/InfoTooltip"

interface OverthinkingMeterProps {
  level: "low" | "moderate" | "high" | string
  coaching: string
}

export function OverthinkingMeter({ level, coaching }: OverthinkingMeterProps) {
  let indicatorColor = "bg-green-500"
  let bgColor = "bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20"
  let displayLevel = "Low"

  if (level.toLowerCase() === "high") {
    indicatorColor = "bg-red-500"
    bgColor = "bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20"
    displayLevel = "High"
  } else if (level.toLowerCase() === "moderate") {
    indicatorColor = "bg-yellow-500"
    bgColor = "bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 border-yellow-500/20"
    displayLevel = "Moderate"
  }

  return (
    <div className="bg-card border rounded-2xl p-6 shadow-sm flex flex-col sm:flex-row items-start sm:items-center gap-6">
      <div className="flex-shrink-0 flex items-center justify-center w-16 h-16 rounded-full bg-secondary/50 border relative">
        <BrainCircuit className="w-8 h-8 text-muted-foreground" />
        <div className={`absolute top-0 right-0 w-4 h-4 rounded-full border-2 border-card ${indicatorColor}`} />
      </div>
      
      <div className="flex-1">
        <div className="flex items-center gap-3 mb-2">
          <h2 className="text-lg font-semibold flex items-center">
            Overthinking Check
            <InfoTooltip text="The AI assesses if you are ruminating (dwelling on negative thoughts) or if your mental clarity is good today." />
          </h2>
          <span className={`text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-md border ${bgColor}`}>
            {displayLevel}
          </span>
        </div>
        <p className="text-muted-foreground text-sm italic">
          "{coaching || "Your mental clarity looks good today. Keep focusing on what's in your control."}"
        </p>
      </div>
    </div>
  )
}
