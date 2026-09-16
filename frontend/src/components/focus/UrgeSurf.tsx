"use client"
import * as React from "react"
import { createPortal } from "react-dom"
import { X, Waves } from "lucide-react"

/**
 * UrgeSurf - ninety seconds of riding an urge instead of acting on it.
 *
 * Different from the 3-Minute Reset on purpose: that one settles a thought loop with
 * breathing, stillness and visualisation. This one is for a craving. Cravings rise,
 * peak and fall on their own within a couple of minutes if nothing feeds them, so the
 * job is to name the urge, find it in the body, breathe while the wave crests, and
 * choose afterwards. The outcome is logged either way, with no judgement attached.
 */

const TOTAL = 90

const PHASES = [
  { until: 12, title: "Name it", lines: ["Say to yourself what the urge is asking for.", "Just the name. No argument with it."] },
  { until: 35, title: "Find it in your body", lines: ["Where is it? Chest, stomach, jaw, hands.", "Notice its size, its temperature, whether it moves."] },
  { until: 62, title: "The wave rises", lines: ["Breathe out longer than you breathe in.", "Urges peak and fall by themselves when nothing feeds them. You are watching, not obeying."] },
  { until: 85, title: "The wave falls", lines: ["Notice what has changed. Smaller, duller, further away.", "It may come back later. That is a new wave, and you can surf that one too."] },
  { until: TOTAL, title: "Choose", lines: ["The urge has had its say.", "Now you decide, from a calmer place."] },
]

export function UrgeSurf({
  open, onClose, onOutcome,
}: {
  open: boolean
  onClose: () => void
  /** Called once at the end with whether the person acted on the urge. */
  onOutcome: (acted: boolean, intensity: number) => void
}) {
  const [mounted, setMounted] = React.useState(false)
  const [stage, setStage] = React.useState<"intensity" | "surf" | "choose">("intensity")
  const [intensity, setIntensity] = React.useState(3)
  const [remaining, setRemaining] = React.useState(TOTAL)
  const dialogRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => { setMounted(true) }, [])

  React.useEffect(() => {
    if (!open) return
    setStage("intensity")
    setIntensity(3)
    setRemaining(TOTAL)
    const t = window.setTimeout(() => dialogRef.current?.focus(), 0)
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", onKey)
    return () => { window.clearTimeout(t); window.removeEventListener("keydown", onKey) }
  }, [open, onClose])

  React.useEffect(() => {
    if (!open || stage !== "surf") return
    const end = Date.now() + TOTAL * 1000
    const id = window.setInterval(() => {
      const left = Math.max(0, Math.ceil((end - Date.now()) / 1000))
      setRemaining(left)
      if (left <= 0) { window.clearInterval(id); setStage("choose") }
    }, 250)
    return () => window.clearInterval(id)
  }, [open, stage])

  if (!open || !mounted) return null

  const elapsed = TOTAL - remaining
  const phase = PHASES.find(p => elapsed < p.until) ?? PHASES[PHASES.length - 1]
  const wave = Math.sin(Math.min(1, elapsed / TOTAL) * Math.PI) // rises then falls over the 90 seconds

  return createPortal(
    <div ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label="Surf an urge" className="fixed inset-0 z-[110] bg-background/95 backdrop-blur-xl text-foreground overflow-y-auto focus:outline-none">
      <div className="min-h-full flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-lg">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2 text-teal-600 dark:text-teal-400">
              <Waves className="w-5 h-5" />
              <span className="text-xs font-bold uppercase tracking-widest">Surf the urge</span>
            </div>
            <button onClick={onClose} aria-label="Close" className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 text-gray-500 cursor-pointer"><X className="w-5 h-5" /></button>
          </div>

          <div className="p-6 lg:p-8 rounded-2xl bg-white/60 dark:bg-black/30 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-xl">
            {stage === "intensity" && (
              <div>
                <h2 className="text-2xl font-serif font-bold text-center">Ninety seconds. Nothing to decide yet.</h2>
                <p className="text-sm text-gray-500 text-center mt-2">An urge is a wave. It rises, peaks and falls whether or not you act on it. This is practice at letting one pass.</p>
                <p className="text-sm font-medium text-center mt-8">How strong is it right now?</p>
                <div className="grid grid-cols-5 gap-2 mt-3" role="radiogroup" aria-label="Urge intensity">
                  {[1, 2, 3, 4, 5].map(v => (
                    <button key={v} role="radio" aria-checked={intensity === v} onClick={() => setIntensity(v)}
                      className={`py-3 rounded-xl border text-lg font-bold transition-all cursor-pointer ${intensity === v ? "bg-teal-600 border-teal-600 text-white shadow-md" : "bg-black/[0.03] dark:bg-white/5 border-black/5 dark:border-white/10 hover:border-teal-500/50"}`}>
                      {v}
                    </button>
                  ))}
                </div>
                <div className="flex justify-between text-[11px] text-gray-400 mt-1 px-1"><span>faint</span><span>overwhelming</span></div>
                <button onClick={() => setStage("surf")} className="mt-8 w-full py-3.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-semibold transition-colors cursor-pointer">Start the ninety seconds</button>
              </div>
            )}

            {stage === "surf" && (
              <div className="text-center">
                <p className="text-xs uppercase tracking-widest text-teal-600 dark:text-teal-400">{phase.title}</p>
                <div className="relative h-40 my-6 flex items-end justify-center" aria-hidden="true">
                  <div className="w-40 rounded-t-full bg-teal-400/30 border border-teal-400/40 transition-all duration-700 ease-in-out" style={{ height: `${20 + wave * 80}%` }} />
                  <span className="absolute bottom-2 text-lg font-mono tabular-nums text-foreground/80">{Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")}</span>
                </div>
                <div className="space-y-2 min-h-[4.5rem]" aria-live="polite">
                  {phase.lines.map((l, i) => <p key={i} className={i === 0 ? "text-lg font-serif" : "text-sm text-gray-500"}>{l}</p>)}
                </div>
              </div>
            )}

            {stage === "choose" && (
              <div className="text-center">
                <p className="text-xs uppercase tracking-widest text-teal-600 dark:text-teal-400">Ninety seconds done</p>
                <h2 className="text-xl font-serif font-bold mt-2">What happened to the urge?</h2>
                <p className="text-sm text-gray-500 mt-2">Either answer is useful data. Acting on it is not failure; it is a wave you can look at tomorrow.</p>
                <div className="flex flex-col sm:flex-row gap-3 mt-6">
                  <button onClick={() => { onOutcome(false, intensity); onClose() }} className="flex-1 py-3 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-semibold cursor-pointer transition-colors">It passed, I let it go</button>
                  <button onClick={() => { onOutcome(true, intensity); onClose() }} className="flex-1 py-3 rounded-xl border border-black/10 dark:border-white/15 hover:bg-black/5 dark:hover:bg-white/5 font-medium cursor-pointer transition-colors">I acted on it</button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body
  )
}
