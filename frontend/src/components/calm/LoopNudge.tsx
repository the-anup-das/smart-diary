"use client"
import * as React from "react"
import { Wind, X, Timer } from "lucide-react"

/**
 * LoopNudge - a quiet, dismissible hint shown while an entry is being written,
 * when the text itself starts to sound like a loop ("what if", "should have",
 * "over and over", ...). It is a cheap heuristic on the client; the real
 * rumination rating still comes from the analysis after Save & Reflect.
 */

const LOOP_PATTERNS: RegExp[] = [
  /\bwhat if\b/gi,
  /\bshould(?:n't| not)? have\b/gi,
  /\bshould've\b/gi,
  /\b(?:can'?t|cannot|couldn'?t) stop thinking\b/gi,
  /\bkeeps? (?:thinking|replaying|going over|wondering|worrying|coming back)\b/gi,
  /\bover and over\b/gi,
  /\bwhy did(?:n't)? i\b/gi,
  /\bwhat (?:will|do|would) (?:they|people|everyone) think\b/gi,
  /\boverthink(?:ing)?\b/gi,
  /\bif only\b/gi,
  /\bruminat\w*/gi,
  /\bwhat'?s wrong with me\b/gi,
  /\bi can'?t (?:sleep|switch off|let (?:it|this) go)\b/gi,
]

export const LOOP_NUDGE_THRESHOLD = 2
export const LOOP_NUDGE_MIN_WORDS = 40

/** Number of loop-like phrases in the text. */
export function detectLoopScore(text: string): number {
  if (!text) return 0
  let score = 0
  for (const pattern of LOOP_PATTERNS) {
    const matches = text.match(pattern)
    if (matches) score += matches.length
  }
  return score
}

function dismissKey() {
  return `loop_nudge_dismissed_${new Date().toISOString().slice(0, 10)}`
}

export function LoopNudge({
  score, wordCount, hidden, onStart,
}: {
  score: number; wordCount: number; hidden?: boolean; onStart: () => void
}) {
  const [dismissed, setDismissed] = React.useState(true) // assume dismissed until storage is read, avoids a flash
  React.useEffect(() => {
    try { setDismissed(sessionStorage.getItem(dismissKey()) === "1") } catch { setDismissed(false) }
  }, [])

  const show = !hidden && !dismissed && score >= LOOP_NUDGE_THRESHOLD && wordCount >= LOOP_NUDGE_MIN_WORDS
  if (!show) return null

  const dismiss = () => {
    setDismissed(true)
    try { sessionStorage.setItem(dismissKey(), "1") } catch {}
  }

  return (
    <div role="status" className="mb-6 mx-2 lg:mx-6 p-4 rounded-xl bg-sky-500/5 border border-sky-500/20 flex flex-col sm:flex-row sm:items-center gap-3 fade-in">
      <div className="flex items-start gap-3 flex-1">
        <Wind className="w-5 h-5 text-sky-500 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">This sounds like your mind is looping.</p>
          <p className="text-xs text-gray-500 mt-0.5">Keep writing if it helps. A three-minute reset is here whenever you want it. Nothing to solve.</p>
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          onClick={onStart}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-sm font-medium transition-colors cursor-pointer"
        >
          <Timer className="w-4 h-4" /> 3-minute reset
        </button>
        <button onClick={dismiss} aria-label="Dismiss for today" className="p-2 rounded-lg text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
