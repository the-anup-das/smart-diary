"use client"
import * as React from "react"
import { ThumbsUp, ThumbsDown } from "lucide-react"

/** 👍/👎 on an AI output — the signal behind "is this tool actually helping?" */
export function HelpfulnessVote({
  kind,
  refId = null,
  className = "",
}: {
  kind: "reflection" | "chat" | "weekly_review"
  refId?: string | null
  className?: string
}) {
  const [voted, setVoted] = React.useState<number | null>(null)

  function vote(value: 1 | -1) {
    if (voted !== null) return
    setVoted(value)
    fetch("/api/ai-feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, ref_id: refId, vote: value }),
    }).catch(() => {})
  }

  return (
    <div className={`flex items-center gap-2 text-xs text-gray-400 ${className}`}>
      {voted === null ? (
        <>
          <span>Was this helpful?</span>
          <button
            onClick={() => vote(1)}
            aria-label="Helpful"
            className="p-1.5 rounded-lg hover:bg-success/10 hover:text-success transition-colors cursor-pointer"
          >
            <ThumbsUp className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => vote(-1)}
            aria-label="Not helpful"
            className="p-1.5 rounded-lg hover:bg-danger/10 hover:text-danger transition-colors cursor-pointer"
          >
            <ThumbsDown className="w-3.5 h-3.5" />
          </button>
        </>
      ) : (
        <span className="fade-in">Thanks — noted.</span>
      )}
    </div>
  )
}
