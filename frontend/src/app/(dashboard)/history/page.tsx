"use client"
import * as React from "react"
import { Calendar, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Sparkles, BookOpen, FileText } from "lucide-react"
import { getMoodTier, getSentimentStyle } from "@/lib/mood"

interface EntryData {
  id: string
  date: string
  preview: string
  wordCount: number
  content: string
  feedback: {
    moodScore: number
    sentiment: string
    grammarScore: number
    topics: Record<string, number> | null
    openLoops: string[] | null
    grammarFixes: any[] | null
    cognitiveReframes: any[] | null
  } | null
}

type ViewMode = "month" | "year" | "all"

export default function HistoryPage() {
  const [entries, setEntries] = React.useState<EntryData[]>([])
  const [loading, setLoading] = React.useState(true)
  const [expandedId, setExpandedId] = React.useState<string | null>(null)
  const [showFullTextId, setShowFullTextId] = React.useState<string | null>(null)
  const [viewMode, setViewMode] = React.useState<ViewMode>("month")
  const [currentMonth, setCurrentMonth] = React.useState(() => {
    const now = new Date()
    return { year: now.getFullYear(), month: now.getMonth() }
  })
  const [currentYear, setCurrentYear] = React.useState(() => new Date().getFullYear())

  const entryRefs = React.useRef<Map<string, HTMLDivElement>>(new Map())

  React.useEffect(() => {
    async function fetchHistory() {
      try {
        const res = await fetch('/api/entries/history')
        if (res.ok) {
          const json = await res.json()
          setEntries(json.entries || [])
        }
      } catch {}
      finally { setLoading(false) }
    }
    fetchHistory()
  }, [])

  // Build lookup: date string -> entry
  const entryMap = React.useMemo(() => {
    const map = new Map<string, EntryData>()
    for (const e of entries) {
      map.set(e.date, e)
    }
    return map
  }, [entries])

  // Filter entries for the timeline below calendar
  const filteredEntries = React.useMemo(() => {
    if (viewMode === "all") return entries
    if (viewMode === "year") {
      return entries.filter(e => {
        const d = new Date(e.date + 'T00:00:00')
        return d.getFullYear() === currentYear
      })
    }
    // month
    return entries.filter(e => {
      const d = new Date(e.date + 'T00:00:00')
      return d.getFullYear() === currentMonth.year && d.getMonth() === currentMonth.month
    })
  }, [entries, viewMode, currentMonth, currentYear])

  const handleDayClick = (date: string) => {
    const entry = entryMap.get(date)
    if (!entry) return
    setExpandedId(entry.id)
    setShowFullTextId(null)
    setTimeout(() => {
      const el = entryRefs.current.get(entry.id)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 100)
  }

  const viewModes: { key: ViewMode; label: string }[] = [
    { key: "month", label: "Month" },
    { key: "year", label: "Year" },
    { key: "all", label: "All Time" },
  ]

  return (
    <div className="flex flex-col w-full pt-6 pb-16 fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8 px-2">
        <div className="flex items-center space-x-3">
          <Calendar className="w-7 h-7 text-primary" />
          <h1 className="text-3xl font-serif font-bold tracking-tight text-gray-900 dark:text-gray-100">
            History
          </h1>
          {!loading && (
            <span className="text-sm text-gray-400 font-mono">{entries.length} entries</span>
          )}
        </div>

        {/* View Mode Selector */}
        <div className="flex items-center bg-black/5 dark:bg-white/5 rounded-full p-1 border border-black/5 dark:border-white/10">
          {viewModes.map(m => (
            <button
              key={m.key}
              onClick={() => setViewMode(m.key)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all cursor-pointer ${
                viewMode === m.key
                  ? "bg-primary text-white shadow-md"
                  : "text-gray-500 hover:text-gray-900 dark:hover:text-gray-100"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-4 animate-pulse">
          <div className="h-[300px] rounded-2xl bg-black/5 dark:bg-white/5" />
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-[80px] rounded-xl bg-black/5 dark:bg-white/5" />
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && entries.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <BookOpen className="w-16 h-16 text-gray-300 dark:text-gray-600 mb-4" />
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">No Entries Yet</h2>
          <p className="text-gray-500 max-w-md">
            Start writing in the <strong>Today</strong> tab. Your journal history will appear here.
          </p>
        </div>
      )}

      {!loading && entries.length > 0 && (
        <div className="space-y-8">
          {/* Calendar View */}
          <GlassCard>
            {viewMode === "month" && (
              <MonthCalendar
                year={currentMonth.year}
                month={currentMonth.month}
                entryMap={entryMap}
                onDayClick={handleDayClick}
                onPrev={() => setCurrentMonth(prev => {
                  if (prev.month === 0) return { year: prev.year - 1, month: 11 }
                  return { ...prev, month: prev.month - 1 }
                })}
                onNext={() => setCurrentMonth(prev => {
                  if (prev.month === 11) return { year: prev.year + 1, month: 0 }
                  return { ...prev, month: prev.month + 1 }
                })}
              />
            )}
            {viewMode === "year" && (
              <YearCalendar
                year={currentYear}
                entryMap={entryMap}
                onDayClick={handleDayClick}
                onPrev={() => setCurrentYear(y => y - 1)}
                onNext={() => setCurrentYear(y => y + 1)}
              />
            )}
            {viewMode === "all" && (
              <AllTimeCalendar entryMap={entryMap} onDayClick={handleDayClick} />
            )}

            {/* Color Guide */}
            <MoodColorGuide />
          </GlassCard>

          {/* Entry Timeline */}
          {filteredEntries.length > 0 ? (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide px-1">
                {viewMode === "month" && new Date(currentMonth.year, currentMonth.month).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                {viewMode === "year" && `${currentYear}`}
                {viewMode === "all" && "All Entries"}
                {' '} · {filteredEntries.length} {filteredEntries.length === 1 ? 'entry' : 'entries'}
              </h3>
              {filteredEntries.map(entry => (
                <div key={entry.id} ref={(el) => { if (el) entryRefs.current.set(entry.id, el) }}>
                  <EntryCard
                    entry={entry}
                    isExpanded={expandedId === entry.id}
                    showFullText={showFullTextId === entry.id}
                    onToggle={() => { setExpandedId(expandedId === entry.id ? null : entry.id); setShowFullTextId(null) }}
                    onToggleFullText={() => setShowFullTextId(showFullTextId === entry.id ? null : entry.id)}
                  />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-gray-400 py-8">No entries in this period.</p>
          )}
        </div>
      )}
    </div>
  )
}

// ============================
// MONTH CALENDAR
// ============================
function MonthCalendar({ year, month, entryMap, onDayClick, onPrev, onNext }: {
  year: number; month: number;
  entryMap: Map<string, EntryData>;
  onDayClick: (date: string) => void;
  onPrev: () => void; onNext: () => void;
}) {
  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const today = new Date().toISOString().slice(0, 10)
  const monthLabel = new Date(year, month).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

  const cells: (number | null)[] = []
  for (let i = 0; i < firstDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)
  // fill remaining grid cells for a clean full row
  const totalCells = Math.ceil(cells.length / 7) * 7
  while (cells.length < totalCells) cells.push(null)

  return (
    <div className="w-full">
      {/* Nav */}
      <div className="flex items-center justify-between mb-6">
        <button onClick={onPrev} className="p-2 rounded-xl hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer transition-colors"><ChevronLeft className="w-5 h-5 text-gray-500" /></button>
        <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{monthLabel}</h3>
        <button onClick={onNext} className="p-2 rounded-xl hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer transition-colors"><ChevronRight className="w-5 h-5 text-gray-500" /></button>
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-7 gap-2 sm:gap-3 mb-2">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d, i) => (
          <div key={i} className="text-center text-xs font-semibold uppercase tracking-wider text-gray-400 py-1">{d}</div>
        ))}
      </div>

      {/* Day cells */}
      <div className="grid grid-cols-7 gap-2 sm:gap-3">
        {cells.map((day, i) => {
          if (day === null) {
            return (
              <div key={i} className="h-12 sm:h-16 lg:h-20 w-full rounded-2xl bg-black/[0.01] dark:bg-white/[0.01]" />
            )
          }
          const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
          const entry = entryMap.get(dateStr)
          const isToday = dateStr === today
          const fb = entry?.feedback

          let bgStyle = "bg-black/[0.03] dark:bg-white/[0.03]"
          let textColor = "text-gray-400"
          let ring = "border border-transparent"
          let hoverScale = "hover:scale-[1.03]"

          if (entry && fb) {
            const tier = getMoodTier(fb.moodScore)
            bgStyle = tier.bg
            textColor = `${tier.color} font-bold`
            ring = `border ${tier.border} shadow-sm`
          } else if (entry) {
            bgStyle = "bg-primary/10"
            textColor = "text-primary font-bold"
            ring = "border border-primary/20 shadow-sm"
          }

          if (isToday) ring += " ring-2 ring-primary/40 ring-offset-1 dark:ring-offset-gray-900" 

          return (
            <button
              key={i}
              onClick={() => entry && onDayClick(dateStr)}
              title={fb ? `${dateStr} · ${fb.sentiment} (${fb.moodScore}/10)` : dateStr}
              className={`flex items-center justify-center w-full h-12 sm:h-16 lg:h-20 rounded-2xl text-sm sm:text-base transition-all duration-200
                ${bgStyle} ${ring} ${entry ? `cursor-pointer ${hoverScale} hover:shadow-md z-10` : 'cursor-default'}`}
            >
              <span className={textColor}>{day}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ============================
// YEAR CALENDAR (12 mini months)
// ============================
function YearCalendar({ year, entryMap, onDayClick, onPrev, onNext }: {
  year: number;
  entryMap: Map<string, EntryData>;
  onDayClick: (date: string) => void;
  onPrev: () => void; onNext: () => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <button onClick={onPrev} className="p-2 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer transition-colors"><ChevronLeft className="w-5 h-5 text-gray-500" /></button>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{year}</h3>
        <button onClick={onNext} className="p-2 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer transition-colors"><ChevronRight className="w-5 h-5 text-gray-500" /></button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
        {Array.from({ length: 12 }).map((_, month) => (
          <MiniMonth key={month} year={year} month={month} entryMap={entryMap} onDayClick={onDayClick} />
        ))}
      </div>
    </div>
  )
}

function MiniMonth({ year, month, entryMap, onDayClick }: {
  year: number; month: number;
  entryMap: Map<string, EntryData>;
  onDayClick: (date: string) => void;
}) {
  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const monthLabel = new Date(year, month).toLocaleDateString('en-US', { month: 'short' })

  const cells: (number | null)[] = []
  for (let i = 0; i < firstDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)

  return (
    <div>
      <h4 className="text-xs font-semibold text-gray-500 mb-1">{monthLabel}</h4>
      <div className="grid grid-cols-7 gap-px">
        {cells.map((day, i) => {
          if (day === null) return <div key={i} className="w-full aspect-square" />
          const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
          const entry = entryMap.get(dateStr)
          const fb = entry?.feedback

          let bg = "bg-black/[0.04] dark:bg-white/[0.04]"
          if (entry && fb) {
            const tier = getMoodTier(fb.moodScore)
            bg = tier.bg.replace('/10', '/40')
          } else if (entry) {
            bg = "bg-primary/20"
          }

          return (
            <button
              key={i}
              onClick={() => entry && onDayClick(dateStr)}
              className={`w-full aspect-square rounded-sm ${bg} ${entry ? 'cursor-pointer hover:ring-1 hover:ring-primary/30' : 'cursor-default'} transition-all`}
              title={`${dateStr}${fb ? ` · ${fb.sentiment} (${fb.moodScore}/10)` : entry ? ' · Entry (not analyzed)' : ''}`}
            />
          )
        })}
      </div>
    </div>
  )
}

// ============================
// ALL TIME (list of year sections)
// ============================
function AllTimeCalendar({ entryMap, onDayClick }: {
  entryMap: Map<string, EntryData>;
  onDayClick: (date: string) => void;
}) {
  const years = React.useMemo(() => {
    const ys = new Set<number>()
    for (const key of entryMap.keys()) {
      ys.add(new Date(key + 'T00:00:00').getFullYear())
    }
    return Array.from(ys).sort((a, b) => b - a)
  }, [entryMap])

  if (years.length === 0) return <p className="text-gray-500 text-sm text-center py-4">No entries found.</p>

  return (
    <div className="space-y-8">
      {years.map(year => (
        <div key={year}>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">{year}</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {Array.from({ length: 12 }).map((_, month) => (
              <MiniMonth key={month} year={year} month={month} entryMap={entryMap} onDayClick={onDayClick} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ============================
// COLOR GUIDE
// ============================
function MoodColorGuide() {
  const tiers = [
    { range: "1-2", ...getMoodTier(1) },
    { range: "3-4", ...getMoodTier(3) },
    { range: "5-6", ...getMoodTier(5) },
    { range: "7-8", ...getMoodTier(7) },
    { range: "9-10", ...getMoodTier(9) },
  ]

  return (
    <div className="mt-5 pt-4 border-t border-black/5 dark:border-white/5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="text-xs text-gray-400 font-medium uppercase tracking-wide">Mood Guide</span>
        {tiers.map(t => (
          <div key={t.range} className="flex items-center space-x-1.5">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: t.hex }} />
            <span className="text-xs text-gray-500">{t.label}</span>
            <span className="text-[10px] text-gray-400 font-mono">({t.range})</span>
          </div>
        ))}
        <div className="flex items-center space-x-1.5">
          <div className="w-3 h-3 rounded-full bg-black/[0.06] dark:bg-white/[0.06] border border-dashed border-gray-300 dark:border-gray-600" />
          <span className="text-xs text-gray-400">No entry</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <div className="w-3 h-3 rounded-sm ring-2 ring-primary/40" />
          <span className="text-xs text-gray-400">Today</span>
        </div>
      </div>
    </div>
  )
}

// ============================
// ENTRY CARD
// ============================
function EntryCard({ entry, isExpanded, showFullText, onToggle, onToggleFullText }: {
  entry: EntryData; isExpanded: boolean; showFullText: boolean;
  onToggle: () => void; onToggleFullText: () => void;
}) {
  const fb = entry.feedback
  const moodTier = fb ? getMoodTier(fb.moodScore) : null
  const sentStyle = fb ? getSentimentStyle(fb.sentiment) : null
  const dateLabel = new Date(entry.date + 'T00:00:00').toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
  })

  return (
    <div className="rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg overflow-hidden transition-all duration-300">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 lg:p-5 cursor-pointer hover:bg-black/[0.02] dark:hover:bg-white/[0.02] transition-colors text-left"
      >
        <div className="flex items-center space-x-4 flex-1 min-w-0">
          {moodTier ? (
            <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${moodTier.bg} border-2 ${moodTier.border}`}>
              <span className={`text-sm font-bold ${moodTier.color}`}>{fb!.moodScore}</span>
            </div>
          ) : (
            <div className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 bg-black/5 dark:bg-white/5 border-2 border-black/5 dark:border-white/10">
              <span className="text-sm text-gray-400">—</span>
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center space-x-2 mb-0.5 flex-wrap gap-y-1">
              <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">{dateLabel}</span>
              {sentStyle && (
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${sentStyle.bg} ${sentStyle.color}`}>{fb!.sentiment}</span>
              )}
            </div>
            <p className="text-sm text-gray-500 truncate">{entry.preview || "No content"}</p>
          </div>
          <div className="flex items-center space-x-3 flex-shrink-0 ml-2">
            <span className="text-xs text-gray-400 font-mono">{entry.wordCount}w</span>
            {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
          </div>
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-black/5 dark:border-white/5 p-4 lg:p-6 space-y-4 fade-in">
          <div className="flex flex-wrap gap-3 items-center">
            {fb && <MiniStat label="Mood" value={`${fb.moodScore}/10`} sublabel={moodTier?.label} color={moodTier?.hex || '#8b5cf6'} />}
            {fb && <MiniStat label="Grammar" value={`${fb.grammarScore}/10`} color="#3b82f6" />}
            <span className="text-xs text-gray-400 font-mono">{entry.wordCount} words</span>
          </div>

          {fb?.topics && Object.keys(fb.topics).length > 0 && (
            <div>
              <span className="text-xs text-gray-500 font-medium uppercase tracking-wide">Focus Areas</span>
              <div className="flex flex-wrap gap-2 mt-2">
                {Object.entries(fb.topics).sort(([,a],[,b]) => b - a).map(([topic, weight]) => (
                  <span key={topic} className="px-2.5 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium capitalize border border-primary/20">
                    {topic.replace(/_/g, ' ')} {Math.round(weight * 100)}%
                  </span>
                ))}
              </div>
            </div>
          )}

          {fb?.openLoops && fb.openLoops.length > 0 && (
            <div>
              <span className="text-xs text-gray-500 font-medium uppercase tracking-wide">Open Loops</span>
              <ul className="mt-2 space-y-1.5">
                {fb.openLoops.map((loop, i) => (
                  <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start">
                    <span className="mr-2 text-primary mt-0.5">•</span>{loop}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {fb?.cognitiveReframes && fb.cognitiveReframes.length > 0 && (
            <div>
              <span className="text-xs text-gray-500 font-medium uppercase tracking-wide">Reframes</span>
              <div className="mt-2 space-y-2">
                {fb.cognitiveReframes.map((item: any, i: number) => (
                  <div key={i} className="p-3 rounded-lg bg-primary/5 border border-primary/10">
                    <p className="text-xs text-gray-500 italic mb-1">"{item.negativeThought}"</p>
                    <p className="text-sm text-gray-800 dark:text-gray-200">✨ {item.reframe}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="pt-2 border-t border-black/5 dark:border-white/5">
            <button
              onClick={onToggleFullText}
              className="flex items-center space-x-2 text-sm text-primary hover:text-primary/80 font-medium cursor-pointer transition-colors"
            >
              <FileText className="w-4 h-4" />
              <span>{showFullText ? "Hide full entry" : "Read full entry"}</span>
              {showFullText ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            {showFullText && (
              <div
                className="mt-3 p-4 rounded-lg bg-black/[0.02] dark:bg-white/[0.02] border border-black/5 dark:border-white/5 prose prose-sm dark:prose-invert max-w-none text-gray-700 dark:text-gray-300 fade-in"
                dangerouslySetInnerHTML={{ __html: entry.content }}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function MiniStat({ label, value, sublabel, color }: { label: string; value: string; sublabel?: string; color: string }) {
  return (
    <div className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-full bg-black/5 dark:bg-white/5">
      <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
      <span className="text-xs text-gray-500">{label}</span>
      <span className="text-xs font-bold text-gray-700 dark:text-gray-300">{value}</span>
      {sublabel && <span className="text-xs font-medium" style={{ color }}>{sublabel}</span>}
    </div>
  )
}

function GlassCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="p-5 lg:p-7 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg">
      {children}
    </div>
  )
}
