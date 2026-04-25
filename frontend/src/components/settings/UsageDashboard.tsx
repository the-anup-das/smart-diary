"use client"
import React, { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { Coins, Zap, Activity, Info, BarChart3 } from "lucide-react"

interface UsageStats {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  analysis_count: number
  estimated_cost_usd: number
}

export function UsageDashboard() {
  const [stats, setStats] = useState<UsageStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch("/api/user/usage")
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setStats(data.usage)
        }
        setLoading(false)
      })
      .catch(err => {
        console.error("Failed to fetch usage stats:", err)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!stats) return null

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <div>
        <h2 className="text-xl font-semibold mb-1">AI Usage & Cost</h2>
        <p className="text-sm text-muted-foreground">Transparency on how your smart diary utilizes AI resources.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <UsageCard 
          icon={<Activity className="w-5 h-5 text-blue-500" />}
          label="Total Analyses"
          value={stats.analysis_count.toString()}
          subtext="Sessions recorded"
        />
        <UsageCard 
          icon={<Zap className="w-5 h-5 text-yellow-500" />}
          label="Total Tokens"
          value={stats.total_tokens.toLocaleString()}
          subtext={`${stats.prompt_tokens.toLocaleString()} in / ${stats.completion_tokens.toLocaleString()} out`}
        />
        <UsageCard 
          icon={<Coins className="w-5 h-5 text-emerald-500" />}
          label="Estimated Cost"
          value={`$${stats.estimated_cost_usd.toFixed(4)}`}
          subtext="Standard analysis rates"
        />
      </div>

      <div className="bg-muted/30 border rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="w-5 h-5 text-primary" />
          <h3 className="font-medium">Optimization Status</h3>
        </div>
        
        <div className="space-y-4">
          <OptimizationItem 
            label="Smart Caching"
            status="Active"
            description="Identical entries use cached analysis to avoid LLM costs."
          />
          <OptimizationItem 
            label="Prompt Compression"
            status="Active"
            description="Compressed system instructions to minimize token overhead."
          />
        </div>
      </div>

      <div className="flex items-start gap-3 p-4 bg-blue-50/50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900/50 rounded-xl text-sm">
        <Info className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
        <p className="text-blue-800/80 dark:text-blue-200/80">
          We believe in "Privacy-First AI." Your token usage is tracked only for transparency and cost management. We never use your diary entries to train external models.
        </p>
      </div>
    </motion.div>
  )
}

function UsageCard({ icon, label, value, subtext }: { icon: React.ReactNode, label: string, value: string, subtext: string }) {
  return (
    <div className="bg-card border rounded-2xl p-5 shadow-sm">
      <div className="flex items-center gap-3 mb-3">
        <div className="p-2 bg-muted rounded-lg">{icon}</div>
        <span className="text-sm font-medium text-muted-foreground">{label}</span>
      </div>
      <div className="text-2xl font-bold mb-1">{value}</div>
      <div className="text-xs text-muted-foreground">{subtext}</div>
    </div>
  )
}

function OptimizationItem({ label, status, description }: { label: string, status: string, description: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 border-b last:border-0">
      <div>
        <div className="text-sm font-medium">{label}</div>
        <div className="text-xs text-muted-foreground mt-0.5">{description}</div>
      </div>
      <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/50">
        {status}
      </span>
    </div>
  )
}
