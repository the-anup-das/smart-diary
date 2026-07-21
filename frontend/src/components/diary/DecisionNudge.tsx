"use client"
import * as React from "react"
import Link from "next/link"
import { GitMerge, X, ChevronRight } from "lucide-react"

interface DueDecision {
  id: string
  topic: string
  review_date: string
}

/**
 * Surfaces decisions whose review date has arrived so the user closes the
 * loop: compare what they expected with what actually happened.
 */
export function DecisionNudge() {
  const [due, setDue] = React.useState<DueDecision[]>([])
  const [visible, setVisible] = React.useState(true)

  React.useEffect(() => {
    // Session-scoped dismissal — remind again tomorrow, don't nag today
    if (sessionStorage.getItem("decision_nudge_dismissed")) {
      setVisible(false)
      return
    }
    fetch("/api/decisions")
      .then(res => res.json())
      .then((decisions: any[]) => {
        if (!Array.isArray(decisions)) return
        const now = new Date()
        setDue(
          decisions.filter(d =>
            d.status !== "archived" &&
            d.review_date &&
            new Date(d.review_date) <= now &&
            !d.actual_outcome
          )
        )
      })
      .catch(() => {})
  }, [])

  function dismiss() {
    sessionStorage.setItem("decision_nudge_dismissed", "1")
    setVisible(false)
  }

  if (due.length === 0 || !visible) return null

  return (
    <div className="mb-6 fade-in relative mx-2 lg:mx-6">
      <div className="p-4 rounded-2xl bg-gradient-to-r from-blue-500/5 to-transparent border-l-4 border-blue-400 shadow-sm glass-panel flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <GitMerge className="w-5 h-5 text-blue-500 flex-shrink-0" />
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              {due.length === 1 ? "A decision is due for review" : `${due.length} decisions are due for review`}
            </h3>
            <p className="text-xs text-gray-500 truncate">
              How did “{due[0].topic}” turn out? Recording the outcome sharpens future judgment.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <Link
            href={`/decisions/${due[0].id}`}
            className="flex items-center gap-1 text-sm font-medium text-blue-500 hover:text-blue-600 transition-colors whitespace-nowrap"
          >
            Review <ChevronRight className="w-4 h-4" />
          </Link>
          <button
            onClick={dismiss}
            aria-label="Dismiss decision reminder"
            className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
