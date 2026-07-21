"use client"
import * as React from "react"
import { ScrollText, RefreshCw, Trophy, CloudRain, Repeat, Compass } from "lucide-react"

interface ReviewData {
  narrative: string
  winsOfTheWeek: string[]
  challenges: string[]
  recurringThemes: string[]
  moodArc: string
  nextWeekFocus: string
}

export function WeeklyReview() {
  const [review, setReview] = React.useState<ReviewData | null>(null)
  const [unavailableReason, setUnavailableReason] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState("")

  const fetchReview = React.useCallback(async (refresh = false) => {
    setLoading(true)
    setError("")
    try {
      const res = await fetch(`/api/insights/weekly-review${refresh ? "?refresh=true" : ""}`)
      if (!res.ok) {
        setError("Couldn't generate your weekly review right now.")
        return
      }
      const json = await res.json()
      if (json.available) {
        setReview(json.review)
        setUnavailableReason(null)
      } else {
        setReview(null)
        setUnavailableReason(json.reason || "Not enough entries yet this week.")
      }
    } catch {
      setError("Couldn't reach the server for your weekly review.")
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => { fetchReview() }, [fetchReview])

  return (
    <div className="p-5 lg:p-7 rounded-2xl bg-gradient-to-br from-primary/[0.07] to-blue-500/[0.05] dark:from-primary/10 dark:to-blue-500/5 backdrop-blur-xl border border-primary/10 dark:border-primary/20 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 flex items-center space-x-2">
          <ScrollText className="w-5 h-5 text-primary" />
          <span>Your Week in Review</span>
        </h3>
        {review && (
          <button
            onClick={() => fetchReview(true)}
            disabled={loading}
            aria-label="Regenerate weekly review"
            title="Regenerate"
            className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 text-gray-400 hover:text-primary transition-colors cursor-pointer disabled:opacity-40"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        )}
      </div>

      {loading && (
        <div className="space-y-3 animate-pulse">
          <div className="h-4 w-3/4 rounded bg-black/5 dark:bg-white/10" />
          <div className="h-4 w-full rounded bg-black/5 dark:bg-white/10" />
          <div className="h-4 w-5/6 rounded bg-black/5 dark:bg-white/10" />
        </div>
      )}

      {!loading && error && (
        <div className="text-sm text-red-500 dark:text-red-400 font-medium flex items-center justify-between gap-4">
          <span role="alert">{error}</span>
          <button onClick={() => fetchReview()} className="text-primary hover:underline cursor-pointer flex-shrink-0">Retry</button>
        </div>
      )}

      {!loading && !error && unavailableReason && (
        <p className="text-sm text-gray-500">{unavailableReason}</p>
      )}

      {!loading && !error && review && (
        <div className="space-y-5">
          <p className="text-sm italic text-primary/80 dark:text-primary/90 font-medium">{review.moodArc}</p>

          <div className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed space-y-3 whitespace-pre-line">
            {review.narrative}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ReviewList icon={<Trophy className="w-4 h-4 text-amber-500" />} title="Wins" items={review.winsOfTheWeek} />
            <ReviewList icon={<CloudRain className="w-4 h-4 text-blue-400" />} title="Challenges" items={review.challenges} />
          </div>

          {review.recurringThemes.length > 0 && (
            <div>
              <span className="text-xs text-gray-500 font-semibold uppercase tracking-wide flex items-center gap-1.5">
                <Repeat className="w-3.5 h-3.5" /> Recurring themes
              </span>
              <div className="flex flex-wrap gap-2 mt-2">
                {review.recurringThemes.map((t, i) => (
                  <span key={i} className="px-2.5 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium border border-primary/20">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="p-3.5 rounded-xl bg-white/50 dark:bg-black/20 border border-black/5 dark:border-white/10">
            <span className="text-xs text-gray-500 font-semibold uppercase tracking-wide flex items-center gap-1.5 mb-1">
              <Compass className="w-3.5 h-3.5 text-primary" /> Next week
            </span>
            <p className="text-sm text-gray-800 dark:text-gray-200">{review.nextWeekFocus}</p>
          </div>
        </div>
      )}
    </div>
  )
}

function ReviewList({ icon, title, items }: { icon: React.ReactNode; title: string; items: string[] }) {
  if (!items || items.length === 0) return null
  return (
    <div>
      <span className="text-xs text-gray-500 font-semibold uppercase tracking-wide flex items-center gap-1.5">
        {icon} {title}
      </span>
      <ul className="mt-2 space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start">
            <span className="mr-2 text-primary mt-0.5">•</span>{item}
          </li>
        ))}
      </ul>
    </div>
  )
}
