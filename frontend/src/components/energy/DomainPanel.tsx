"use client"
import React, { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { PieChart } from "lucide-react"
import { InfoTooltip } from "@/components/ui/InfoTooltip"

interface DomainHistory {
  topic: string
  percentage: number
}

export function DomainPanel() {
  const [history, setHistory] = useState<DomainHistory[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchDomainHistory() {
      try {
        const res = await fetch("/api/energy/domain-history")
        const data = await res.json()
        if (data.success) {
          setHistory(data.history)
        }
      } catch (e) {
        console.error("Failed to fetch domain history", e)
      } finally {
        setLoading(false)
      }
    }
    fetchDomainHistory()
  }, [])

  if (loading) {
    return (
      <div className="bg-card border rounded-2xl p-6 shadow-sm animate-pulse h-32" />
    )
  }

  if (history.length === 0) {
    return null
  }

  // Define colors for domains
  const colors = [
    "bg-indigo-500", "bg-sky-500", "bg-emerald-500", 
    "bg-amber-500", "bg-rose-500", "bg-fuchsia-500", "bg-slate-500"
  ]

  return (
    <div className="bg-card border rounded-2xl p-6 shadow-sm">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
          <PieChart className="w-4 h-4" />
          Where Your Attention Went (Last 7 Days)
          <InfoTooltip text="This aggregates the topics you wrote about over the last week. High percentages on external factors (like Weather or Traffic) mean they are occupying a lot of your mental bandwidth." />
        </h2>
      </div>

      <div className="space-y-4">
        {/* Heatmap Bar */}
        <div className="h-4 w-full flex rounded-full overflow-hidden">
          {history.map((item, i) => (
            <motion.div
              key={item.topic}
              initial={{ width: 0 }}
              animate={{ width: `${item.percentage}%` }}
              transition={{ duration: 1, ease: "easeOut", delay: i * 0.1 }}
              className={`h-full ${colors[i % colors.length]}`}
              title={`${item.topic} (${item.percentage}%)`}
            />
          ))}
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-4 pt-2">
          {history.map((item, i) => (
            <div key={item.topic} className="flex items-center gap-2 text-sm">
              <div className={`w-3 h-3 rounded-full ${colors[i % colors.length]}`} />
              <span className="font-medium">{item.topic}</span>
              <span className="text-muted-foreground">{item.percentage}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
