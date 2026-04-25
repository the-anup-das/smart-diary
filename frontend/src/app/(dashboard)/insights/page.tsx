"use client"
import * as React from "react"
import { MoodChart } from "@/components/insights/MoodChart"
import { TopicRing } from "@/components/insights/TopicRing"
import { VocabChart } from "@/components/insights/VocabChart"
import { TargetsWidget } from "@/components/insights/TargetsWidget"
import { StyleInsights } from "@/components/insights/StyleInsights"
import { TrendingUp, TrendingDown, Brain, BookOpen, Flame, BarChart2, Check, X, Pin, Sparkles, PenTool } from "lucide-react"
import { getMoodTier, getSentimentStyle } from "@/lib/mood"

type TimeRange = "day" | "week" | "month" | "year" | "all"

interface OpenLoopItem {
  id: string
  text: string
  status: string
  urgency: "urgent" | "aging" | "fresh"
  ageDays: number
  detectedAt: string
}

interface InsightsData {
  summary: {
    totalEntries: number
    analyzedEntries: number
    avgMood: number
    avgGrammar: number
    moodTrend: number | null
    totalVocabulary: number
    topSentiment: string
    currentStreak: number
  }
  timeline: any[]
  topicAggregation: Record<string, number>
  sentimentDistribution: Record<string, number>
  topNewWords: string[]
  openLoops: {
    items: OpenLoopItem[]
    totalOpen: number
    totalResolved: number
  }
  targets: any
  writingStyle?: {
    avgSelfFocus: number
    highlights: {
      date: string
      words: string[]
      feedback: string
      self_focus_feedback: string
    }[]
  }
}

// --- Animated Counter Hook ---
function useAnimatedCounter(target: number, duration = 800) {
  const [value, setValue] = React.useState(0)
  const isFloat = target % 1 !== 0
  
  React.useEffect(() => {
    if (target === 0) { setValue(0); return }
    const startTime = performance.now()
    const animate = (now: number) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      // ease-out
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(isFloat ? parseFloat((eased * target).toFixed(1)) : Math.round(eased * target))
      if (progress < 1) requestAnimationFrame(animate)
    }
    requestAnimationFrame(animate)
  }, [target, duration, isFloat])
  
  return value
}

// --- Cache helper ---
const cacheKey = (range: string) => `insights_cache_${range}`
function getCached(range: string): InsightsData | null {
  try {
    const raw = sessionStorage.getItem(cacheKey(range))
    if (!raw) return null
    const { data, ts } = JSON.parse(raw)
    if (Date.now() - ts > 60_000) return null // 1min TTL
    return data
  } catch { return null }
}
function setCache(range: string, data: InsightsData) {
  try { sessionStorage.setItem(cacheKey(range), JSON.stringify({ data, ts: Date.now() })) } catch {}
}

export default function InsightsPage() {
  const [range, setRange] = React.useState<TimeRange>("week")
  const [data, setData] = React.useState<InsightsData | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  const fetchInsights = React.useCallback(async (r: TimeRange, skipCache = false) => {
    if (!skipCache) {
      const cached = getCached(r)
      if (cached) { setData(cached); setLoading(false); return }
    }
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/insights?range=${r}`)
      if (!res.ok) {
        const text = await res.text()
        try { setError(JSON.parse(text).detail || `Error ${res.status}`) }
        catch { setError(`Server Error (${res.status})`) }
        return
      }
      const json = await res.json()
      setData(json)
      setCache(r, json)
    } catch (err: any) {
      setError(err.message || "Failed to load insights")
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => { fetchInsights(range) }, [range, fetchInsights])

  const handleLoopAction = async (loopId: string, action: string) => {
    try {
      await fetch(`/api/open-loops/${loopId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      })
      // Refetch to update UI
      fetchInsights(range, true)
    } catch {}
  }

  const ranges: { key: TimeRange; label: string }[] = [
    { key: "day", label: "Today" },
    { key: "week", label: "Week" },
    { key: "month", label: "Month" },
    { key: "year", label: "Year" },
    { key: "all", label: "All Time" },
  ]

  return (
    <div className="flex flex-col w-full pt-6 pb-16 fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8 px-2">
        <div className="flex items-center space-x-3">
          <BarChart2 className="w-7 h-7 text-primary" />
          <h1 className="text-3xl font-serif font-bold tracking-tight text-gray-900 dark:text-gray-100">
            Insights
          </h1>
        </div>

        {/* Time Range Selector */}
        <div className="flex items-center bg-black/5 dark:bg-white/5 rounded-full p-1 border border-black/5 dark:border-white/10">
          {ranges.map(r => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all cursor-pointer ${
                range === r.key
                  ? "bg-primary text-white shadow-md"
                  : "text-gray-500 hover:text-gray-900 dark:hover:text-gray-100"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-xl text-red-600 dark:text-red-400 text-sm font-medium">
          ⚠️ {error}
        </div>
      )}

      {/* Skeleton Loading */}
      {loading && <SkeletonDashboard />}

      {/* Empty State */}
      {!loading && data && data.summary.analyzedEntries === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <BarChart2 className="w-16 h-16 text-gray-300 dark:text-gray-600 mb-4" />
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">No Insights Yet</h2>
          <p className="text-gray-500 max-w-md">
            Write journal entries and use <strong>Save & Reflect</strong> to generate AI analysis. 
            Your mood trends, vocabulary growth, and focus topics will appear here.
          </p>
        </div>
      )}

      {/* Dashboard Content */}
      {!loading && data && data.summary.analyzedEntries > 0 && (
        <div className="space-y-6">
          {/* Targets Module */}
          <TargetsWidget targets={data.targets} />
          
          {/* Summary Stats */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <AnimatedStatCard icon={<BookOpen className="w-5 h-5 text-violet-500" />} label="Entries" target={data.summary.totalEntries} />
            <MoodStatCard avgMood={data.summary.avgMood} moodTrend={data.summary.moodTrend} />
            <AnimatedStatCard icon={<Brain className="w-5 h-5 text-blue-500" />} label="Vocabulary" target={data.summary.totalVocabulary} />
            <StreakCard streak={data.summary.currentStreak} />
          </div>

          {/* Mood & Grammar Timeline */}
          <GlassCard>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center space-x-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              <span>Mood & Grammar Timeline</span>
            </h3>
            <MoodChart data={data.timeline} />
          </GlassCard>

          {/* Middle Row: Topics + Sentiment */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Topic Focus */}
            <GlassCard>
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Focus Distribution</h3>
              <TopicRing data={data.topicAggregation} />
            </GlassCard>

            {/* Sentiment Breakdown */}
            <GlassCard>
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Emotional Climate</h3>
              <SentimentPills data={data.sentimentDistribution} />
            </GlassCard>
          </div>

          {/* Vocabulary Growth */}
          <GlassCard>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center space-x-2">
              <Brain className="w-5 h-5 text-violet-500" />
              <span>Vocabulary Growth</span>
            </h3>
            <VocabChart data={data.timeline} />
          </GlassCard>

          {/* Top New Words */}
          {data.topNewWords && data.topNewWords.length > 0 && (
            <GlassCard>
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center space-x-2">
                <Sparkles className="w-5 h-5 text-amber-500" />
                <span>New Words Discovered</span>
              </h3>
              <div className="flex flex-wrap gap-2">
                {data.topNewWords.map((word, i) => (
                  <span key={i} className="px-3 py-1.5 rounded-full bg-primary/10 text-primary text-sm font-medium border border-primary/20 shadow-[0_0_8px_rgba(139,92,246,0.15)]">
                    {word}
                  </span>
                ))}
              </div>
            </GlassCard>
          )}

          {/* Open Loops */}
          <OpenLoopsCard loops={data.openLoops} onAction={handleLoopAction} />

          {/* Writing Style Insights */}
          {data.writingStyle && (
            <div className="space-y-4">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 flex items-center space-x-2 px-1">
                <PenTool className="w-5 h-5 text-indigo-500" />
                <span>Writing Style & Perspective</span>
              </h3>
              <StyleInsights data={data.writingStyle} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// --- Skeleton Loading ---
function SkeletonDashboard() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-[140px] rounded-2xl bg-black/5 dark:bg-white/5" />
        ))}
      </div>
      <div className="h-[280px] rounded-2xl bg-black/5 dark:bg-white/5" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-[240px] rounded-2xl bg-black/5 dark:bg-white/5" />
        <div className="h-[240px] rounded-2xl bg-black/5 dark:bg-white/5" />
      </div>
    </div>
  )
}

// --- Animated Stat Card ---
function AnimatedStatCard({ icon, label, target }: { icon: React.ReactNode; label: string; target: number }) {
  const animatedValue = useAnimatedCounter(target)
  return (
    <div className="p-5 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg">
      <div className="flex items-center space-x-2 mb-2">
        {icon}
        <span className="text-sm text-gray-500 font-medium">{label}</span>
      </div>
      <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
        {animatedValue.toLocaleString()}
      </p>
    </div>
  )
}

// --- Mood Stat Card with Radial Gauge + Trend Arrow ---
function MoodStatCard({ avgMood, moodTrend }: { avgMood: number; moodTrend: number | null }) {
  const tier = getMoodTier(avgMood)
  const pct = ((avgMood - 1) / 9) * 100
  const radius = 40
  const circumference = 2 * Math.PI * radius
  const arcLength = circumference * 0.75
  const filledArc = arcLength * (pct / 100)

  return (
    <div className={`p-5 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border-2 ${tier.border} shadow-lg relative overflow-hidden`}>
      <div className={`absolute top-0 right-0 w-24 h-24 rounded-full ${tier.bg} blur-2xl -translate-y-8 translate-x-8`} />
      <div className="flex items-center justify-between mb-1 relative">
        <div className="flex items-center space-x-2">
          <TrendingUp className={`w-4 h-4 ${tier.color}`} />
          <span className="text-sm text-gray-500 font-medium">Mood</span>
        </div>
        {/* Trend Arrow */}
        {moodTrend !== null && moodTrend !== 0 && (
          <div className={`flex items-center space-x-0.5 px-2 py-0.5 rounded-full text-xs font-bold ${
            moodTrend > 0 
              ? 'bg-emerald-500/10 text-emerald-500' 
              : 'bg-red-500/10 text-red-500'
          }`}>
            {moodTrend > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            <span>{moodTrend > 0 ? '+' : ''}{moodTrend}</span>
          </div>
        )}
      </div>
      <div className="relative flex items-center justify-center">
        <svg viewBox="0 0 100 100" className="w-[110px] h-[110px]">
          <circle cx="50" cy="50" r={radius} fill="none" stroke="currentColor" strokeOpacity="0.08" strokeWidth="8" strokeDasharray={`${arcLength} ${circumference}`} strokeLinecap="round" transform="rotate(135, 50, 50)" />
          <circle cx="50" cy="50" r={radius} fill="none" stroke={tier.hex} strokeOpacity="0.85" strokeWidth="8" strokeDasharray={`${filledArc} ${circumference}`} strokeLinecap="round" transform="rotate(135, 50, 50)" className="transition-all duration-1000 ease-out" />
          <text x="50" y="46" textAnchor="middle" fontSize="14" fontWeight="700" fill={tier.hex}>{tier.label}</text>
          <text x="50" y="62" textAnchor="middle" fontSize="11" fill="#9ca3af" fontFamily="monospace">{avgMood}/10</text>
        </svg>
      </div>
    </div>
  )
}

// --- Streak Card with Animated Fire ---
function StreakCard({ streak }: { streak: number }) {
  const intensity = Math.min(streak / 10, 1)
  const fireSize = 1.5 + intensity * 1.5
  const glowSize = 40 + intensity * 60
  const pulseSpeed = streak >= 7 ? '1s' : streak >= 3 ? '2s' : '3s'
  
  return (
    <div className="p-5 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg relative overflow-hidden">
      <div 
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full pointer-events-none transition-all duration-700"
        style={{
          width: `${glowSize}px`,
          height: `${glowSize}px`,
          background: `radial-gradient(circle, rgba(245,158,11,${0.05 + intensity * 0.15}) 0%, transparent 70%)`,
        }}
      />
      <div className="flex items-center space-x-2 mb-2 relative">
        <span className="text-sm text-gray-500 font-medium">Streak</span>
      </div>
      <div className="relative flex items-center space-x-3">
        <div className="relative flex-shrink-0">
          <span
            className="block transition-all duration-500"
            style={{
              fontSize: `${fireSize}rem`,
              filter: streak >= 3 ? `drop-shadow(0 0 ${4 + intensity * 12}px rgba(245,158,11,${0.4 + intensity * 0.4}))` : 'none',
              animation: streak >= 1 ? `fireFlicker ${pulseSpeed} ease-in-out infinite` : 'none',
            }}
          >
            🔥
          </span>
        </div>
        <div>
          <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">{streak}</p>
          <p className="text-xs text-gray-400">{streak === 1 ? "day" : "days"}</p>
        </div>
      </div>
      <style>{`
        @keyframes fireFlicker {
          0%, 100% { transform: scale(1) translateY(0); }
          25% { transform: scale(1.05) translateY(-2px); }
          50% { transform: scale(0.97) translateY(1px); }
          75% { transform: scale(1.08) translateY(-3px); }
        }
      `}</style>
    </div>
  )
}

// --- Open Loops Card ---
function OpenLoopsCard({ loops, onAction }: { loops: InsightsData['openLoops']; onAction: (id: string, action: string) => void }) {
  if (!loops || loops.totalOpen === 0) return null
  
  const [showAll, setShowAll] = React.useState(false)
  const display = showAll ? loops.items : loops.items.slice(0, 5)
  
  const urgencyStyle = {
    urgent: "border-l-red-500 bg-red-500/5",
    aging: "border-l-amber-500 bg-amber-500/5",
    fresh: "border-l-emerald-500 bg-emerald-500/5",
  }
  
  const urgencyBadge = {
    urgent: "text-red-500",
    aging: "text-amber-500", 
    fresh: "text-emerald-500",
  }

  return (
    <GlassCard>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Open Loops</h3>
        <div className="flex items-center space-x-2 text-xs">
          <span className="px-2 py-1 bg-primary/10 text-primary rounded-full font-medium">{loops.totalOpen} open</span>
          <span className="px-2 py-1 bg-black/5 dark:bg-white/5 text-gray-400 rounded-full">{loops.totalResolved} resolved</span>
        </div>
      </div>
      <div className="space-y-2">
        {display.map(loop => (
          <div 
            key={loop.id} 
            className={`flex items-center justify-between p-3 rounded-lg border-l-4 ${urgencyStyle[loop.urgency]} transition-all`}
          >
            <div className="flex items-center space-x-3 flex-1 min-w-0">
              {loop.status === 'pinned' && <Pin className="w-3.5 h-3.5 text-primary flex-shrink-0" />}
              <span className="text-sm text-gray-700 dark:text-gray-300 truncate">{loop.text}</span>
              <span className={`text-xs font-mono flex-shrink-0 ${urgencyBadge[loop.urgency]}`}>{loop.ageDays}d</span>
            </div>
            <div className="flex items-center space-x-1 ml-2 flex-shrink-0">
              <button onClick={() => onAction(loop.id, 'resolve')} className="p-1 rounded hover:bg-emerald-500/10 text-gray-400 hover:text-emerald-500 transition-colors cursor-pointer" title="Done">
                <Check className="w-4 h-4" />
              </button>
              <button onClick={() => onAction(loop.id, loop.status === 'pinned' ? 'reopen' : 'pin')} className={`p-1 rounded hover:bg-primary/10 transition-colors cursor-pointer ${loop.status === 'pinned' ? 'text-primary' : 'text-gray-400 hover:text-primary'}`} title={loop.status === 'pinned' ? 'Unpin' : 'Pin'}>
                <Pin className="w-4 h-4" />
              </button>
              <button onClick={() => onAction(loop.id, 'dismiss')} className="p-1 rounded hover:bg-red-500/10 text-gray-400 hover:text-red-500 transition-colors cursor-pointer" title="Dismiss">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
      {loops.items.length > 5 && (
        <button 
          onClick={() => setShowAll(!showAll)} 
          className="mt-3 text-sm text-primary hover:text-primary/80 font-medium cursor-pointer"
        >
          {showAll ? "Show less" : `View all (${loops.items.length})`}
        </button>
      )}
    </GlassCard>
  )
}

function GlassCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="p-5 lg:p-7 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg">
      {children}
    </div>
  )
}

function SentimentPills({ data }: { data: Record<string, number> }) {
  if (!data || Object.keys(data).length === 0) {
    return <div className="text-gray-500 text-sm">No sentiment data yet.</div>
  }

  const entries = Object.entries(data).sort((a, b) => b[1] - a[1])
  const total = entries.reduce((s, [, v]) => s + v, 0) || 1

  return (
    <div className="space-y-3">
      {entries.map(([sentiment, count]) => {
        const style = getSentimentStyle(sentiment)
        const pct = Math.round((count / total) * 100)
        return (
          <div key={sentiment} className="flex items-center space-x-3">
            <div className={`flex items-center space-x-2 px-3 py-1.5 rounded-full border ${style.bg} border-current/10 ${style.glow} min-w-[110px]`}>
              <div className={`w-2 h-2 rounded-full ${style.color.replace('text-', 'bg-')}`} />
              <span className={`text-sm font-medium ${style.color}`}>{sentiment}</span>
            </div>
            <div className="flex-1 h-2 bg-black/5 dark:bg-white/5 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ease-out ${style.color.replace('text-', 'bg-')}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs text-gray-400 font-mono w-12 text-right">{pct}%</span>
          </div>
        )
      })}
    </div>
  )
}
