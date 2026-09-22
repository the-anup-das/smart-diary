"use client"
import * as React from "react"
import { createPortal } from "react-dom"
import { X, Wind, Check, PenLine, ChevronRight, Timer, Volume2, VolumeX, WifiOff } from "lucide-react"

/**
 * ThreeMinuteReset - a full-screen, timed antidote to overthinking.
 *
 * Follows the 1-1-1 practice from Dr. Saloni Singh's "How to Stop Overthinking
 * in 3 Minutes": one minute of affectionate breathing, one minute of complete
 * stillness, one minute of visualisation closed with affirmations. The app
 * keeps time and plays a soft chime at each minute boundary so the person can
 * keep their eyes closed; the backend (routers/calm.py) personalises minute
 * three to today's entry and stores the session so the practice can be tracked.
 *
 * Mounted from the feedback view after an entry is analysed and from the live
 * nudge in the editor (source "entry"), and from the Energy page (source "manual").
 */

type Source = "entry" | "manual"
type Step = "checkin" | "breathe" | "still" | "visualise" | "checkout"

export interface ResetPlan {
  loopThought: string | null
  ruminationType: string
  acknowledgement: string
  letGo: string
  whatMatters: string
  visualisation: string[]
  affirmations: string[]
  lessonQuestion: string
}

interface CalmSession {
  id: string
  plan: ResetPlan
  personalized: boolean
  ruminationLevel: string | null
}

export interface ThreeMinuteResetProps {
  open: boolean
  source: Source
  onClose: () => void
  /** Called once the user finishes the check-out step. */
  onCompleted?: (result: { mindBefore: number | null; mindAfter: number | null; note: string }) => void
  /** When provided, the check-out screen offers to add a one-line reflection to today's entry. */
  onAppendToEntry?: (text: string) => void
  /** Coaching line from today's analysis, shown on the check-in screen when the plan is not personalised. */
  ruminationCoaching?: string | null
}

export const STEP_SECONDS = 60
const SOUND_PREF_KEY = "calm_reset_sound"

const MIND_SCALE = [
  { value: 1, label: "Still" },
  { value: 2, label: "Settled" },
  { value: 3, label: "Busy" },
  { value: 4, label: "Noisy" },
  { value: 5, label: "Racing" },
]

/** Used when the session could not be created (offline, server error) so the practice still runs. */
const FALLBACK_PLAN: ResetPlan = {
  loopThought: null,
  ruminationType: "mixed",
  acknowledgement: "Your mind has been busy. That is allowed. Nothing needs to be solved in the next three minutes.",
  letGo: "For now, set down the version of events that only exists in your head.",
  whatMatters: "Only what is in front of you today, and only the part of it you can actually influence.",
  visualisation: [
    "Picture yourself moving through the rest of today with a gentle smile.",
    "See yourself doing each task unhurried, one at a time, with room to breathe.",
    "When the familiar worry shows up, watch yourself notice it and stay steady.",
    "See the day end well, your mind quiet and your body at ease.",
  ],
  affirmations: [
    "My mind is settling. It is clear and calm.",
    "I give space only to what truly matters.",
    "I can meet whatever comes with a steady mind.",
  ],
  lessonQuestion: "What is this situation trying to teach me?",
}

const STILLNESS_CUES = [
  "Decide that, whatever happens, you are not going to move.",
  "If an itch comes, let it be there.",
  "If a thought comes, let it pass. Nothing needs a response right now.",
  "Notice that you are still here, unmoved, and that is enough.",
]

const STEP_ANNOUNCEMENTS: Record<Step, string> = {
  checkin: "Three-minute reset. Rate how busy your mind is, then press Begin.",
  breathe: "Minute one of three, affectionate breathing. You can close your eyes; a chime marks the end of each minute.",
  still: "Minute two of three, complete stillness. Do not move until the chime.",
  visualise: "Minute three of three, visualisation. Lines will appear one at a time, then affirmations.",
  checkout: "Three minutes done. Rate how busy your mind is now, add a note if you like, then press Done.",
}

const JSON_HEADERS = { "Content-Type": "application/json" }

function mindLabel(value: number | null) {
  return MIND_SCALE.find(m => m.value === value)?.label ?? "not rated"
}

function formatClock(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, "0")}`
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = React.useState(false)
  React.useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)")
    const update = () => setReduced(mq.matches)
    update()
    mq.addEventListener("change", update)
    return () => mq.removeEventListener("change", update)
  }, [])
  return reduced
}

/** Sound preference, remembered per browser. Defaults to on. */
function useSoundPreference(): [boolean, () => void] {
  const [on, setOn] = React.useState(true)
  React.useEffect(() => {
    try {
      const stored = localStorage.getItem(SOUND_PREF_KEY)
      if (stored !== null) setOn(stored === "1")
    } catch {}
  }, [])
  const toggle = React.useCallback(() => {
    setOn(prev => {
      try { localStorage.setItem(SOUND_PREF_KEY, prev ? "0" : "1") } catch {}
      return !prev
    })
  }, [])
  return [on, toggle]
}

/** Two or three soft sine notes, synthesised so no audio asset is needed. */
function playChime(ctx: AudioContext, final: boolean) {
  try {
    const now = ctx.currentTime
    const notes = final ? [523.25, 659.25, 783.99] : [523.25, 659.25]
    notes.forEach((freq, i) => {
      const start = now + i * 0.35
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = "triangle"   // a little harmonic content: a pure sine at this level vanishes on laptop speakers
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0.0001, start)
      gain.gain.exponentialRampToValueAtTime(0.3, start + 0.05)
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 1.6)
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start(start)
      osc.stop(start + 1.7)
    })
  } catch { /* audio is a nicety; never let it break the practice */ }
}

/** Wall-clock countdown, so a backgrounded tab still finishes at the right moment. */
function useCountdown(seconds: number, onDone: () => void) {
  const [remaining, setRemaining] = React.useState(seconds)
  const onDoneRef = React.useRef(onDone)
  React.useEffect(() => { onDoneRef.current = onDone }, [onDone])
  React.useEffect(() => {
    const end = Date.now() + seconds * 1000
    const id = window.setInterval(() => {
      const left = Math.max(0, Math.ceil((end - Date.now()) / 1000))
      setRemaining(left)
      if (left <= 0) {
        window.clearInterval(id)
        onDoneRef.current()
      }
    }, 250)
    return () => window.clearInterval(id)
  }, [seconds])
  return remaining
}

// ---------------------------------------------------------------- small pieces

function ProgressRing({ remaining, total }: { remaining: number; total: number }) {
  const r = 54
  const c = 2 * Math.PI * r
  const progress = Math.min(1, Math.max(0, 1 - remaining / total))
  return (
    <div className="relative w-[140px] h-[140px] mx-auto">
      <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90" aria-hidden="true">
        <circle cx="60" cy="60" r={r} fill="none" stroke="currentColor" strokeOpacity="0.1" strokeWidth="6" />
        <circle
          cx="60" cy="60" r={r} fill="none"
          stroke="#0ea5e9" strokeWidth="6" strokeLinecap="round"
          strokeDasharray={`${c * progress} ${c}`}
          className="transition-all duration-300 ease-linear"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-2xl font-mono font-semibold tabular-nums">{formatClock(remaining)}</span>
      </div>
    </div>
  )
}

function StepHeading({ n, title }: { n: number; title: string }) {
  return (
    <div className="text-center">
      <p className="text-xs uppercase tracking-widest text-sky-600 dark:text-sky-400">Minute {n} of 3</p>
      <h2 className="text-xl font-serif font-bold mt-1">{title}</h2>
    </div>
  )
}

function StepDots({ step }: { step: Step }) {
  const order: Step[] = ["breathe", "still", "visualise"]
  const active = order.indexOf(step)
  return (
    <div className="flex items-center gap-1.5" aria-hidden="true">
      {order.map((s, i) => (
        <span
          key={s}
          className={`h-1.5 rounded-full transition-all ${
            i < active || step === "checkout" ? "w-4 bg-sky-500" : i === active ? "w-6 bg-sky-500" : "w-4 bg-black/10 dark:bg-white/15"
          }`}
        />
      ))}
    </div>
  )
}

function MindScale({ value, onChange, label }: { value: number | null; onChange: (v: number) => void; label: string }) {
  return (
    <div className="grid grid-cols-5 gap-2 mt-3" role="radiogroup" aria-label={label}>
      {MIND_SCALE.map(m => {
        const selected = value === m.value
        return (
          <button
            key={m.value}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={`${m.value}, ${m.label}`}
            onClick={() => onChange(m.value)}
            className={`py-3 rounded-xl border text-center transition-all cursor-pointer ${
              selected
                ? "bg-sky-600 border-sky-600 text-white shadow-md"
                : "bg-black/[0.03] dark:bg-white/5 border-black/5 dark:border-white/10 hover:border-sky-500/50"
            }`}
          >
            <span className="block text-lg font-bold leading-none">{m.value}</span>
            <span className={`block text-[11px] mt-1 ${selected ? "text-white/90" : "text-gray-500"}`}>{m.label}</span>
          </button>
        )
      })}
    </div>
  )
}

function UnrecordedNotice() {
  return (
    <p className="mt-4 text-xs text-amber-600 dark:text-amber-400 flex items-center justify-center gap-1.5">
      <WifiOff className="w-3.5 h-3.5" /> Offline or server unavailable: this reset will not be recorded.
    </p>
  )
}

// ---------------------------------------------------------------- steps

function CheckIn({
  plan, planPending, personalized, unrecorded, ruminationCoaching, mind, setMind, onBegin,
}: {
  plan: ResetPlan; planPending: boolean; personalized: boolean; unrecorded: boolean; ruminationCoaching?: string | null
  mind: number | null; setMind: (v: number) => void; onBegin: () => void
}) {
  return (
    <div>
      <h2 className="text-2xl font-serif font-bold text-center">Three minutes. Nothing to solve.</h2>
      <p className="text-sm text-gray-500 text-center mt-2">
        One minute of breathing, one of stillness, one of picturing today going calmly.
      </p>

      <div className="mt-6 p-4 rounded-xl bg-sky-500/5 border border-sky-500/20 min-h-[76px]">
        {planPending && !personalized ? (
          <p className="text-sm text-gray-500 animate-pulse">Reading today's entry so the last minute fits your day...</p>
        ) : (
          <>
            {plan.loopThought && <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{plan.loopThought}</p>}
            <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
              {personalized || !ruminationCoaching ? plan.acknowledgement : ruminationCoaching}
            </p>
          </>
        )}
      </div>

      <p className="text-sm font-medium text-center mt-8">How busy is your mind right now?</p>
      <MindScale value={mind} onChange={setMind} label="How busy is your mind right now" />

      <button
        onClick={onBegin}
        className="mt-8 w-full py-3.5 rounded-xl bg-sky-600 hover:bg-sky-700 text-white font-semibold transition-colors cursor-pointer flex items-center justify-center gap-2"
      >
        <Timer className="w-5 h-5" /> Begin
      </button>
      <p className="text-xs text-gray-400 text-center mt-3">
        Sit comfortably. You can close your eyes; a soft chime marks the end of each minute. Stop at any time.
      </p>
      {unrecorded && <UnrecordedNotice />}
    </div>
  )
}

function BreatheStep({ onDone, reducedMotion }: { onDone: () => void; reducedMotion: boolean }) {
  const remaining = useCountdown(STEP_SECONDS, onDone)
  const elapsed = STEP_SECONDS - remaining
  const cycle = Math.floor(elapsed / 8)
  const inhaling = elapsed % 8 < 4
  const cue = cycle < 3
    ? (inhaling ? "Breathe in, with affection for your body." : "Breathe out, and soften.")
    : (inhaling ? "Keep breathing naturally. Feel your chest and belly move." : "Feel the breath soothing you. Be grateful for it.")
  return (
    <div className="text-center">
      <StepHeading n={1} title="Affectionate breathing" />
      <div className="relative h-[220px] flex items-center justify-center my-4">
        <div
          aria-hidden="true"
          className={`w-28 h-28 rounded-full bg-sky-400/30 border border-sky-400/40 ${reducedMotion ? "" : "animate-[calmBreathe_8s_ease-in-out_infinite]"}`}
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-mono tabular-nums text-foreground/80">{formatClock(remaining)}</span>
        </div>
      </div>
      <p className="text-lg font-serif min-h-[3.5rem]">{cue}</p>
      <p className="text-sm text-gray-500 mt-2">Three deep breaths, then let the breath find its own pace.</p>
    </div>
  )
}

function StillStep({ onDone }: { onDone: () => void }) {
  const remaining = useCountdown(STEP_SECONDS, onDone)
  const cueIndex = Math.min(STILLNESS_CUES.length - 1, Math.floor((STEP_SECONDS - remaining) / 15))
  return (
    <div className="text-center">
      <StepHeading n={2} title="Complete stillness" />
      <div className="my-6">
        <ProgressRing remaining={remaining} total={STEP_SECONDS} />
      </div>
      <p className="text-lg font-serif min-h-[3.5rem]">{STILLNESS_CUES[cueIndex]}</p>
      <p className="text-sm text-gray-500 mt-2">Body and mind still, for one whole minute.</p>
    </div>
  )
}

function VisualiseStep({ plan, onDone }: { plan: ResetPlan; onDone: () => void }) {
  const remaining = useCountdown(STEP_SECONDS, onDone)
  const elapsed = STEP_SECONDS - remaining
  const linesShown = Math.min(plan.visualisation.length, Math.floor(elapsed / 12) + 1)
  const showAffirmations = elapsed >= 48
  return (
    <div>
      <StepHeading n={3} title="Now visualise" />
      <p className="text-sm text-gray-500 text-center mt-2">Bring a gentle smile to your face and picture this.</p>
      <div className="mt-6 space-y-3 min-h-[220px]" aria-live="polite">
        {plan.visualisation.slice(0, linesShown).map((line, i) => (
          <p key={i} className="text-lg font-serif leading-relaxed text-center fade-in">{line}</p>
        ))}
        {showAffirmations && (
          <div className="pt-4 mt-4 border-t border-black/5 dark:border-white/10 space-y-2 fade-in">
            <p className="text-xs uppercase tracking-widest text-sky-600 dark:text-sky-400 text-center">Affirm, in your heart</p>
            {plan.affirmations.map((a, i) => (
              <p key={i} className="text-base font-medium text-center">{a}</p>
            ))}
          </div>
        )}
      </div>
      <div className="mt-6 flex justify-center">
        <span className="text-sm font-mono tabular-nums text-gray-500">{formatClock(remaining)}</span>
      </div>
    </div>
  )
}

function CheckOut({
  plan, mindBefore, mindAfter, setMindAfter, note, setNote, onFinish, finishing, onAppend, appended, canAppend, unrecorded,
}: {
  plan: ResetPlan; mindBefore: number | null; mindAfter: number | null; setMindAfter: (v: number) => void
  note: string; setNote: (v: string) => void; onFinish: () => void; finishing: boolean
  onAppend: () => void; appended: boolean; canAppend: boolean; unrecorded: boolean
}) {
  const delta = mindBefore !== null && mindAfter !== null ? mindBefore - mindAfter : null
  const deltaText =
    delta === null ? null
    : delta > 0 ? `Your mind settled from ${mindLabel(mindBefore).toLowerCase()} to ${mindLabel(mindAfter).toLowerCase()}.`
    : delta === 0 ? "About the same as before. That is fine too; the practice works with repetition."
    : "A little busier than before. That happens. Stillness can stir things up before they settle."

  return (
    <div>
      <div className="flex items-center justify-center gap-2 text-sky-600 dark:text-sky-400">
        <Check className="w-5 h-5" />
        <span className="text-xs font-bold uppercase tracking-widest">Three minutes done</span>
      </div>

      <p className="text-sm font-medium text-center mt-6">How busy is your mind now?</p>
      <MindScale value={mindAfter} onChange={setMindAfter} label="How busy is your mind now" />
      {deltaText && <p className="text-center text-sm mt-4 text-gray-600 dark:text-gray-300">{deltaText}</p>}

      <div className="mt-6 space-y-3">
        <div className="p-4 rounded-xl bg-black/[0.03] dark:bg-white/5 border border-black/5 dark:border-white/10">
          <p className="text-[11px] uppercase tracking-widest text-gray-400 mb-1">Let go of</p>
          <p className="text-sm">{plan.letGo}</p>
        </div>
        <div className="p-4 rounded-xl bg-black/[0.03] dark:bg-white/5 border border-black/5 dark:border-white/10">
          <p className="text-[11px] uppercase tracking-widest text-gray-400 mb-1">What matters</p>
          <p className="text-sm">{plan.whatMatters}</p>
        </div>
        <div className="p-4 rounded-xl bg-sky-500/5 border border-sky-500/20">
          <p className="text-[11px] uppercase tracking-widest text-sky-600 dark:text-sky-400 mb-1">To sit with</p>
          <p className="text-sm italic">{plan.lessonQuestion}</p>
        </div>
      </div>

      <label htmlFor="calm-reset-note" className="block mt-6 text-sm font-medium">
        How do you feel? <span className="text-gray-400 font-normal">(one line, optional)</span>
      </label>
      <textarea
        id="calm-reset-note"
        value={note}
        onChange={e => setNote(e.target.value)}
        rows={2}
        maxLength={500}
        placeholder="Lighter. The meeting can wait until tomorrow."
        className="mt-2 w-full rounded-xl border border-black/10 dark:border-white/10 bg-transparent p-3 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/50"
      />

      <div className="mt-6 flex flex-col sm:flex-row gap-3">
        {canAppend && (
          <button
            onClick={onAppend}
            disabled={appended}
            className="flex-1 py-3 rounded-xl border border-sky-500/40 text-sky-700 dark:text-sky-300 font-medium hover:bg-sky-500/10 disabled:opacity-60 disabled:cursor-default cursor-pointer flex items-center justify-center gap-2 transition-colors"
          >
            <PenLine className="w-4 h-4" /> {appended ? "Added to today's entry" : "Add a line to today's entry"}
          </button>
        )}
        <button
          onClick={onFinish}
          disabled={finishing}
          className="flex-1 py-3 rounded-xl bg-sky-600 hover:bg-sky-700 text-white font-semibold disabled:opacity-60 cursor-pointer transition-colors"
        >
          {finishing ? "Saving..." : "Done"}
        </button>
      </div>
      {unrecorded && <UnrecordedNotice />}
    </div>
  )
}

// ---------------------------------------------------------------- overlay

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function ThreeMinuteReset({ open, source, onClose, onCompleted, onAppendToEntry, ruminationCoaching }: ThreeMinuteResetProps) {
  const [mounted, setMounted] = React.useState(false)
  const [step, setStep] = React.useState<Step>("checkin")
  const [session, setSession] = React.useState<CalmSession | null>(null)
  const [planPending, setPlanPending] = React.useState(false)
  const [unrecorded, setUnrecorded] = React.useState(false)
  const [mindBefore, setMindBefore] = React.useState<number | null>(null)
  const [mindAfter, setMindAfter] = React.useState<number | null>(null)
  const [note, setNote] = React.useState("")
  const [finishing, setFinishing] = React.useState(false)
  const [appended, setAppended] = React.useState(false)
  const [soundOn, toggleSound] = useSoundPreference()
  const startedAtRef = React.useRef<number>(0)
  const stepsDoneRef = React.useRef(0)
  const sessionIdRef = React.useRef<string | null>(null)
  const pendingRef = React.useRef<Record<string, unknown>>({})
  const audioRef = React.useRef<AudioContext | null>(null)
  const dialogRef = React.useRef<HTMLDivElement>(null)
  const reducedMotion = usePrefersReducedMotion()

  React.useEffect(() => { setMounted(true) }, [])

  const elapsedSeconds = () => Math.max(0, Math.round((Date.now() - startedAtRef.current) / 1000))

  // Progress is patched as we go so a closed tab still leaves a record. Until the session exists
  // (the planner may take a few seconds) updates are merged and flushed once it arrives.
  const sendProgress = React.useCallback((body: Record<string, unknown>) => {
    const id = sessionIdRef.current
    if (!id) {
      pendingRef.current = { ...pendingRef.current, ...body }
      return
    }
    fetch(`/api/calm/sessions/${id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(body) }).catch(() => {})
  }, [])

  // Create the session when the overlay opens; the check-in screen gives the planner a few seconds.
  React.useEffect(() => {
    if (!open) return
    let cancelled = false
    setStep("checkin")
    setSession(null)
    setUnrecorded(false)
    setMindBefore(null)
    setMindAfter(null)
    setNote("")
    setAppended(false)
    setFinishing(false)
    stepsDoneRef.current = 0
    pendingRef.current = {}
    sessionIdRef.current = null
    startedAtRef.current = Date.now()
    setPlanPending(true)

    fetch("/api/calm/sessions", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ source }) })
      .then(res => (res.ok ? res.json() : Promise.reject(new Error(`Server error ${res.status}`))))
      .then(data => {
        if (cancelled || !data?.session) return
        setSession(data.session)
        sessionIdRef.current = data.session.id
        if (Object.keys(pendingRef.current).length > 0) {
          const body = pendingRef.current
          pendingRef.current = {}
          fetch(`/api/calm/sessions/${data.session.id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(body) }).catch(() => {})
        }
      })
      .catch(() => { if (!cancelled) setUnrecorded(true) })
      .finally(() => { if (!cancelled) setPlanPending(false) })

    return () => { cancelled = true }
  }, [open, source])

  // Dialog behaviour: lock page scroll, move focus in, give it back on close.
  React.useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    const t = window.setTimeout(() => dialogRef.current?.focus(), 0)
    return () => {
      window.clearTimeout(t)
      document.body.style.overflow = previousOverflow
      previous?.focus?.()
    }
  }, [open])

  // Release the audio context when the overlay closes.
  React.useEffect(() => {
    if (open) return
    const ctx = audioRef.current
    audioRef.current = null
    ctx?.close().catch(() => {})
  }, [open])

  const handleExit = React.useCallback(() => {
    sendProgress({ steps_completed: stepsDoneRef.current, duration_seconds: elapsedSeconds() })
    onClose()
  }, [onClose, sendProgress])

  // Escape closes (progress so far is kept); Tab stays inside the dialog.
  React.useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { handleExit(); return }
      if (e.key !== "Tab" || !dialogRef.current) return
      const focusables = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE))
      if (focusables.length === 0) return
      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      const current = document.activeElement
      if (e.shiftKey && (current === first || current === dialogRef.current)) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && current === last) { e.preventDefault(); first.focus() }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, handleExit])

  const plan = session?.plan ?? FALLBACK_PLAN

  // The audio context has to be created inside a user gesture: Begin, or the sound switch being turned on.
  // It is created regardless of the switch's current value, which is checked when a sound plays; reading the
  // switch here used the stale value from before the toggle and left the whole session silent.
  const ensureAudio = () => {
    try {
      const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (!Ctx) return
      if (!audioRef.current) audioRef.current = new Ctx()
      if (audioRef.current.state === "suspended") audioRef.current.resume().catch(() => {})
    } catch { /* no audio available */ }
  }

  const chime = (final: boolean) => {
    if (!soundOn || !audioRef.current) return
    playChime(audioRef.current, final)
  }

  const begin = () => {
    ensureAudio()
    if (mindBefore !== null) sendProgress({ mind_before: mindBefore })
    setStep("breathe")
  }

  const completeStep = (n: number, next: Step) => {
    stepsDoneRef.current = Math.max(stepsDoneRef.current, n)
    sendProgress({ steps_completed: n, duration_seconds: elapsedSeconds() })
    chime(next === "checkout")
    setStep(next)
  }

  const skipStep = () => {
    if (step === "breathe" || step === "still" || step === "visualise") chime(step === "visualise")
    if (step === "breathe") setStep("still")
    else if (step === "still") setStep("visualise")
    else if (step === "visualise") setStep("checkout")
  }

  const finish = async () => {
    setFinishing(true)
    const body: Record<string, unknown> = {
      steps_completed: stepsDoneRef.current,
      duration_seconds: elapsedSeconds(),
      completed: true,
    }
    if (mindAfter !== null) body.mind_after = mindAfter
    if (note.trim()) body.note = note.trim()
    const id = sessionIdRef.current
    if (id) {
      try {
        await fetch(`/api/calm/sessions/${id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(body) })
      } catch { /* keep going; the practice itself is what matters */ }
    }
    onCompleted?.({ mindBefore, mindAfter, note: note.trim() })
    setFinishing(false)
    onClose()
  }

  const appendToEntry = () => {
    if (!onAppendToEntry) return
    const parts = ["3-minute reset done."]
    if (mindBefore !== null && mindAfter !== null) {
      parts.push(`Mind went from ${mindLabel(mindBefore).toLowerCase()} (${mindBefore}/5) to ${mindLabel(mindAfter).toLowerCase()} (${mindAfter}/5).`)
    }
    if (note.trim()) parts.push(note.trim())
    onAppendToEntry(parts.join(" "))
    setAppended(true)
  }

  if (!open || !mounted) return null

  const timed = step === "breathe" || step === "still" || step === "visualise"

  return createPortal(
    <div
      ref={dialogRef}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-label="3-minute reset"
      className="fixed inset-0 z-[100] bg-background/95 backdrop-blur-xl text-foreground overflow-y-auto focus:outline-none"
    >
      <style>{`@keyframes calmBreathe { 0%, 100% { transform: scale(1); opacity: .7 } 50% { transform: scale(1.7); opacity: 1 } }`}</style>
      <div className="sr-only" aria-live="polite">{STEP_ANNOUNCEMENTS[step]}</div>
      <div className="min-h-full flex flex-col items-center justify-center px-4 py-10">
        <div className="w-full max-w-xl">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2 text-sky-600 dark:text-sky-400">
              <Wind className="w-5 h-5" />
              <span className="text-xs font-bold uppercase tracking-widest">3-Minute Reset</span>
            </div>
            <div className="flex items-center gap-3">
              <StepDots step={step} />
              <button
                onClick={() => {
                  const turningOn = !soundOn
                  toggleSound()
                  if (turningOn) {
                    ensureAudio()
                    if (audioRef.current) playChime(audioRef.current, false)
                  }
                }}
                aria-label={soundOn ? "Turn chime off" : "Turn chime on"}
                aria-pressed={soundOn}
                title={soundOn ? "Chime on" : "Chime off"}
                className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 text-gray-500 cursor-pointer transition-colors"
              >
                {soundOn ? <Volume2 className="w-5 h-5" /> : <VolumeX className="w-5 h-5" />}
              </button>
              <button
                onClick={handleExit}
                aria-label="Close"
                className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 text-gray-500 cursor-pointer transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          <div className="p-6 lg:p-8 rounded-2xl bg-white/60 dark:bg-black/30 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-xl">
            {step === "checkin" && (
              <CheckIn
                plan={plan}
                planPending={planPending}
                personalized={!!session?.personalized}
                unrecorded={unrecorded}
                ruminationCoaching={ruminationCoaching}
                mind={mindBefore}
                setMind={setMindBefore}
                onBegin={begin}
              />
            )}
            {step === "breathe" && <BreatheStep key="breathe" onDone={() => completeStep(1, "still")} reducedMotion={reducedMotion} />}
            {step === "still" && <StillStep key="still" onDone={() => completeStep(2, "visualise")} />}
            {step === "visualise" && <VisualiseStep key="visualise" plan={plan} onDone={() => completeStep(3, "checkout")} />}
            {step === "checkout" && (
              <CheckOut
                plan={plan}
                mindBefore={mindBefore}
                mindAfter={mindAfter}
                setMindAfter={setMindAfter}
                note={note}
                setNote={setNote}
                onFinish={finish}
                finishing={finishing}
                onAppend={appendToEntry}
                appended={appended}
                canAppend={!!onAppendToEntry}
                unrecorded={unrecorded}
              />
            )}
          </div>

          {timed && (
            <div className="flex justify-center mt-4">
              <button onClick={skipStep} className="text-sm text-gray-500 hover:text-foreground cursor-pointer flex items-center gap-1 transition-colors">
                Skip this minute <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}

          <p className="text-[11px] text-gray-400 text-center mt-6">
            Based on the 1-1-1 practice from Dr. Saloni Singh&apos;s <em>How to Stop Overthinking in 3 Minutes</em>.
          </p>
        </div>
      </div>
    </div>,
    document.body
  )
}
