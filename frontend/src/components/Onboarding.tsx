"use client"
import * as React from "react"
import { PenSquare, BatteryCharging, MessageCircle, GitMerge, ChevronRight, ChevronLeft } from "lucide-react"

const SLIDES = [
  {
    icon: PenSquare,
    title: "Write, your way",
    body: "One entry per day — typed or dictated with the mic. Use the template button for guided structures (gratitude, CBT, Stoic review), the focus button for distraction-free writing, and the History calendar to backfill missed days.",
  },
  {
    icon: BatteryCharging,
    title: "Reflect with AI",
    body: "Hit Save & Reflect and the AI reads your day: mood, themes, open loops, and your mental battery on the Energy page. Every Monday, Insights writes you a Weekly Review of the week that was.",
  },
  {
    icon: MessageCircle,
    title: "Ask your journal",
    body: "Chat answers questions from your own entries — \"when did I last feel like this?\" — with dated citations you can click. Search in History finds any entry by word, mood, or topic.",
  },
  {
    icon: GitMerge,
    title: "Decide, then learn",
    body: "Facing a hard choice? The Decision canvas breaks it into paths using your own history. Set a review date and the app asks you later how it really went — that's how judgment improves.",
  },
]

/** First-run welcome carousel; shows once, dismissible, state kept in preferences. */
export function Onboarding() {
  const [visible, setVisible] = React.useState(false)
  const [slide, setSlide] = React.useState(0)
  const prefsRef = React.useRef<any>({})

  React.useEffect(() => {
    fetch("/api/users/me")
      .then(res => (res.ok ? res.json() : null))
      .then(data => {
        if (!data || data.detail) return
        prefsRef.current = data.preferences || {}
        if (!prefsRef.current.onboarded) setVisible(true)
      })
      .catch(() => {})
  }, [])

  const finish = React.useCallback(() => {
    setVisible(false)
    fetch("/api/users/me", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preferences: { ...prefsRef.current, onboarded: true } }),
    }).catch(() => {})
  }, [])

  if (!visible) return null

  const { icon: Icon, title, body } = SLIDES[slide]
  const isLast = slide === SLIDES.length - 1

  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm fade-in" role="dialog" aria-modal="true" aria-label="Welcome tour">
      <div className="w-full max-w-md rounded-3xl bg-background border border-black/10 dark:border-white/10 shadow-2xl p-8 text-center">
        <div className="mx-auto w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-6">
          <Icon className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-2xl font-serif font-bold text-gray-900 dark:text-gray-100 mb-3">{title}</h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed min-h-[7.5rem]">{body}</p>

        {/* Dots */}
        <div className="flex justify-center gap-2 my-6">
          {SLIDES.map((_, i) => (
            <button
              key={i}
              onClick={() => setSlide(i)}
              aria-label={`Go to step ${i + 1}`}
              className={`h-1.5 rounded-full transition-all cursor-pointer ${i === slide ? "w-6 bg-primary" : "w-1.5 bg-black/15 dark:bg-white/15"}`}
            />
          ))}
        </div>

        <div className="flex items-center justify-between">
          <button
            onClick={finish}
            className="text-xs font-medium text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors cursor-pointer px-2 py-2"
          >
            Skip tour
          </button>
          <div className="flex items-center gap-2">
            {slide > 0 && (
              <button
                onClick={() => setSlide(s => s - 1)}
                aria-label="Previous"
                className="p-2.5 rounded-xl border border-black/10 dark:border-white/10 text-gray-500 hover:border-primary/30 hover:text-primary transition-colors cursor-pointer"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => (isLast ? finish() : setSlide(s => s + 1))}
              className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold shadow-md hover:bg-primary/90 transition-colors cursor-pointer"
            >
              {isLast ? "Start writing" : "Next"}
              {!isLast && <ChevronRight className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
