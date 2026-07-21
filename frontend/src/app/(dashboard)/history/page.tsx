"use client"
import * as React from "react"
import { useRouter } from "next/navigation"
import { Calendar, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Sparkles, BookOpen, FileText, Trash2, AlertTriangle, X, Search } from "lucide-react"
import { SENTIMENT_STYLES } from "@/lib/mood"
import { DeleteConfirmationModal } from "@/components/diary/DeleteConfirmationModal"
import { getMoodTier, getSentimentStyle } from "@/lib/mood"
import { ReadOnlyEditor } from "@/components/diary/ReadOnlyEditor"

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

type ViewMode = "month" | "year"

export default function HistoryPage() {
  const router = useRouter()
  const [entries, setEntries] = React.useState<EntryData[]>([])
  const [loading, setLoading] = React.useState(true)
  const [expandedId, setExpandedId] = React.useState<string | null>(null)
  const [viewMode, setViewMode] = React.useState<ViewMode>("month")
  const [preferences, setPreferences] = React.useState<any>({})
  const [selectedEntry, setSelectedEntry] = React.useState<EntryData | null>(null)
  const [confirmDeleteEntry, setConfirmDeleteEntry] = React.useState<EntryData | null>(null)
  const [currentMonth, setCurrentMonth] = React.useState(() => {
    const now = new Date()
    return { year: now.getFullYear(), month: now.getMonth() }
  })
  const [currentYear, setCurrentYear] = React.useState(() => new Date().getFullYear())

  // Search state
  const [searchQ, setSearchQ] = React.useState("")
  const [searchSentiment, setSearchSentiment] = React.useState("")
  const [searchMood, setSearchMood] = React.useState("any")
  const [searchResults, setSearchResults] = React.useState<{ id: string; snippet: string }[] | null>(null)
  const [searching, setSearching] = React.useState(false)
  const searchActive = searchQ.trim().length > 0 || searchSentiment !== "" || searchMood !== "any"

  const entryRefs = React.useRef<Map<string, HTMLDivElement>>(new Map())

  // Debounced server-side search
  React.useEffect(() => {
    if (!searchActive) {
      setSearchResults(null)
      return
    }
    const moodRanges: Record<string, [number, number]> = { low: [1, 4], mid: [5, 6], high: [7, 10] }
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const params = new URLSearchParams()
        if (searchQ.trim()) params.set("q", searchQ.trim())
        if (searchSentiment) params.set("sentiment", searchSentiment)
        if (searchMood !== "any") {
          const [lo, hi] = moodRanges[searchMood]
          params.set("mood_min", String(lo))
          params.set("mood_max", String(hi))
        }
        const res = await fetch(`/api/entries/search?${params}`, { signal: controller.signal })
        if (res.ok) {
          const json = await res.json()
          setSearchResults((json.results || []).map((r: any) => ({ id: r.id, snippet: r.snippet })))
        } else {
          setSearchResults([])
        }
      } catch (err: any) {
        if (err?.name !== "AbortError") setSearchResults([])
      } finally {
        setSearching(false)
      }
    }, 350)
    return () => { clearTimeout(timer); controller.abort() }
  }, [searchQ, searchSentiment, searchMood, searchActive])

  React.useEffect(() => {
    async function fetchHistory() {
      try {
        const res = await fetch('/api/entries/history')
        if (res.ok) {
          const json = await res.json()
          setEntries(json.entries || [])
        }
        
        const prefRes = await fetch('/api/users/me')
        if (prefRes.ok) {
          const prefJson = await prefRes.json()
          setPreferences(prefJson.preferences || {})
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

  // Lookup by id so search hits can reuse the fully-loaded entries
  const entryById = React.useMemo(() => {
    const map = new Map<string, EntryData>()
    for (const e of entries) map.set(e.id, e)
    return map
  }, [entries])

  // Filter entries for the timeline below calendar
  const filteredEntries = React.useMemo(() => {
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
    if (!entry) {
      // Empty past day → open the editor in backfill mode for that date
      const todayStr = new Date().toISOString().slice(0, 10)
      if (date < todayStr) router.push(`/?date=${date}`)
      else if (date === todayStr) router.push('/')
      return
    }
    setExpandedId(entry.id)
    setTimeout(() => {
      const el = entryRefs.current.get(entry.id)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 100)
  }

  // Deep link: /history?date=YYYY-MM-DD (e.g. from chat citation pills) jumps
  // to that month and expands the entry. window.location avoids the Suspense
  // boundary useSearchParams requires.
  const deepLinkHandled = React.useRef(false)
  React.useEffect(() => {
    if (deepLinkHandled.current || entries.length === 0) return
    deepLinkHandled.current = true
    const date = new URLSearchParams(window.location.search).get('date')
    const entry = date ? entryMap.get(date) : undefined
    if (!date || !entry) return
    const d = new Date(date + 'T00:00:00')
    setViewMode("month")
    setCurrentMonth({ year: d.getFullYear(), month: d.getMonth() })
    setExpandedId(entry.id)
    setTimeout(() => {
      entryRefs.current.get(entry.id)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 300)
  }, [entries, entryMap])

  const viewModes: { key: ViewMode; label: string }[] = [
    { key: "month", label: "Month" },
    { key: "year", label: "Year" },
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

      {/* Search Bar */}
      {!loading && entries.length > 0 && (
        <div className="mb-6 px-2">
          <div className="flex flex-col md:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
              <input
                type="search"
                value={searchQ}
                onChange={e => setSearchQ(e.target.value)}
                placeholder="Search your journal…"
                aria-label="Search journal entries"
                className="w-full pl-11 pr-10 py-3 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-sm text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary/30 transition-shadow"
              />
              {searchQ && (
                <button
                  onClick={() => setSearchQ("")}
                  aria-label="Clear search"
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-black/5 dark:hover:bg-white/10 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 cursor-pointer transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            <div className="flex gap-3">
              <select
                value={searchSentiment}
                onChange={e => setSearchSentiment(e.target.value)}
                aria-label="Filter by sentiment"
                className="px-4 py-3 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-sm text-sm text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-primary/30 cursor-pointer"
              >
                <option value="">Any feeling</option>
                {Object.keys(SENTIMENT_STYLES).map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <select
                value={searchMood}
                onChange={e => setSearchMood(e.target.value)}
                aria-label="Filter by mood level"
                className="px-4 py-3 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-sm text-sm text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-primary/30 cursor-pointer"
              >
                <option value="any">Any mood</option>
                <option value="low">Low (1–4)</option>
                <option value="mid">Balanced (5–6)</option>
                <option value="high">High (7–10)</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Search Results */}
      {!loading && searchActive && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide px-1">
            {searching ? "Searching…" : `${searchResults?.length ?? 0} ${(searchResults?.length ?? 0) === 1 ? "match" : "matches"}`}
            {searchQ.trim() && !searching && <> for “{searchQ.trim()}”</>}
          </h3>
          {!searching && (searchResults?.length ?? 0) === 0 && (
            <p className="text-center text-gray-400 py-10">Nothing found. Try a different word or loosen the filters.</p>
          )}
          {(searchResults ?? []).map(hit => {
            const full = entryById.get(hit.id)
            if (!full) return null
            return (
              <EntryCard
                key={hit.id}
                entry={{ ...full, preview: hit.snippet || full.preview }}
                isExpanded={expandedId === hit.id}
                onToggle={() => setExpandedId(expandedId === hit.id ? null : hit.id)}
                onReadFull={() => setSelectedEntry(full)}
                preferences={preferences}
                onDelete={() => setConfirmDeleteEntry(full)}
              />
            )
          })}
        </div>
      )}

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

      {!loading && entries.length > 0 && !searchActive && (
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

            {/* Color Guide */}
            <MoodColorGuide />
          </GlassCard>

          {/* Entry Timeline */}
          {filteredEntries.length > 0 ? (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide px-1">
                {viewMode === "month" && new Date(currentMonth.year, currentMonth.month).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                {viewMode === "year" && `${currentYear}`}
                {' '} · {filteredEntries.length} {filteredEntries.length === 1 ? 'entry' : 'entries'}
              </h3>
              {filteredEntries.map(entry => (
                <div key={entry.id} ref={(el) => { if (el) entryRefs.current.set(entry.id, el) }}>
                  <EntryCard
                    entry={entry}
                    isExpanded={expandedId === entry.id}
                    onToggle={() => { setExpandedId(expandedId === entry.id ? null : entry.id) }}
                    onReadFull={() => setSelectedEntry(entry)}
                    preferences={preferences}
                    onDelete={(id, date) => setConfirmDeleteEntry(entry)}
                  />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-gray-400 py-8">No entries in this period.</p>
          )}
        </div>
      )}

      {/* Full Entry Modal Overlay */}
      {selectedEntry && (
        <FullEntryModal 
          entry={selectedEntry} 
          onClose={() => setSelectedEntry(null)} 
          preferences={preferences}
        />
      )}

      {/* Delete Confirmation Modal */}
      {confirmDeleteEntry && (
        <DeleteConfirmationModal
          entry={confirmDeleteEntry}
          onCancel={() => setConfirmDeleteEntry(null)}
          onConfirm={async () => {
            const res = await fetch(`/api/entries/${confirmDeleteEntry.id}`, { method: 'DELETE' })
            if (res.ok) {
              setEntries(prev => prev.filter(e => e.id !== confirmDeleteEntry.id))
            }
            setConfirmDeleteEntry(null)
          }}
        />
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
function EntryCard({ entry, isExpanded, onToggle, onReadFull, preferences, onDelete }: {
  entry: EntryData; isExpanded: boolean;
  onToggle: () => void; onReadFull: () => void;
  preferences: any; onDelete: (id: string, date: string) => void;
}) {
  const fb = entry.feedback
  const moodTier = fb ? getMoodTier(fb.moodScore) : null
  const sentStyle = fb ? getSentimentStyle(fb.sentiment) : null
  const dateLabel = new Date(entry.date + 'T00:00:00').toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
  })

  return (
    <div className="rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg overflow-hidden transition-all duration-300">
      <div
        onClick={onToggle}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } }}
        role="button"
        tabIndex={0}
        className="w-full flex items-center justify-between p-4 lg:p-5 cursor-pointer hover:bg-black/[0.02] dark:hover:bg-white/[0.02] transition-colors text-left focus:outline-none focus:ring-2 focus:ring-primary/20"
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
            {preferences?.enable_deletion && (
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(entry.id, entry.date) }}
                className="p-2 rounded-full hover:bg-red-500/10 text-gray-400 hover:text-red-500 transition-colors cursor-pointer mr-1 focus:outline-none focus:ring-2 focus:ring-red-500/40"
                title="Delete Entry"
                aria-label={`Delete entry from ${dateLabel}`}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
            <span className="text-xs text-gray-400 font-mono">{entry.wordCount}w</span>
            {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
          </div>
        </div>
      </div>

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
              onClick={onReadFull}
              className="flex items-center space-x-2 text-sm text-primary hover:text-primary/80 font-medium cursor-pointer transition-colors"
            >
              <FileText className="w-4 h-4" />
              <span>Read full entry</span>
              <ChevronRight className="w-3 h-3 ml-1" />
            </button>
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

// ============================
// FULL ENTRY MODAL
// ============================
function FullEntryModal({ entry, onClose, preferences }: { 
  entry: EntryData; 
  onClose: () => void; 
  preferences: any;
}) {
  const dateLabel = new Date(entry.date + 'T00:00:00').toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
  })

  // Prevent background scrolling
  React.useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = 'unset' }
  }, [])

  // Close on Escape
  React.useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-[100] flex flex-col bg-background/80 backdrop-blur-2xl fade-in overflow-hidden">
      {/* Modal Header - Matches JournalEditor exactly */}
      <div className="w-full max-w-5xl mx-auto pt-10 px-4 lg:px-8 flex justify-between items-center mb-10">
        <h1 className="text-3xl font-serif font-bold tracking-tight text-gray-900 dark:text-gray-100">
          {dateLabel}
        </h1>
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-400 font-mono tracking-wide">{entry.wordCount} words</span>
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 text-gray-500 hover:text-gray-900 dark:hover:text-white transition-all cursor-pointer"
            title="Close"
            aria-label="Close full entry"
          >
            <ChevronDown className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Editor Content - Matches JournalEditor structure */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="max-w-5xl mx-auto h-full pb-32">
          <ReadOnlyEditor content={entry.content} typography={preferences?.typography} />
        </div>
      </div>
      
      {/* Bottom Gradient Overlay */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-background to-transparent pointer-events-none"></div>
    </div>
  )
}

