"use client"
import * as React from "react"
import { X } from "lucide-react"

const PHASES = [
  { label: "Breathe in", seconds: 4, scale: 1.45 },
  { label: "Hold", seconds: 4, scale: 1.45 },
  { label: "Breathe out", seconds: 4, scale: 1.0 },
  { label: "Hold", seconds: 4, scale: 1.0 },
] as const

/** 60-second box-breathing overlay. Calm by construction: no timers shown
 *  counting down, no score, close anytime. */
export function BreathingExercise({ onClose }: { onClose: () => void }) {
  const [phaseIndex, setPhaseIndex] = React.useState(0)
  const [cycles, setCycles] = React.useState(0)

  React.useEffect(() => {
    const phase = PHASES[phaseIndex]
    const timer = setTimeout(() => {
      const next = (phaseIndex + 1) % PHASES.length
      setPhaseIndex(next)
      if (next === 0) setCycles(c => c + 1)
    }, phase.seconds * 1000)
    return () => clearTimeout(timer)
  }, [phaseIndex])

  React.useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [onClose])

  const phase = PHASES[phaseIndex]

  return (
    <div
      className="fixed inset-0 z-[180] flex flex-col items-center justify-center bg-background/95 backdrop-blur-sm fade-in"
      role="dialog"
      aria-modal="true"
      aria-label="Breathing exercise"
    >
      <button
        onClick={onClose}
        aria-label="Close breathing exercise"
        className="absolute top-6 right-6 p-2.5 rounded-full text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer"
      >
        <X className="w-5 h-5" />
      </button>

      <div className="relative flex items-center justify-center w-64 h-64">
        <div
          className="absolute w-40 h-40 rounded-full bg-primary/15 border border-primary/25"
          style={{
            transform: `scale(${phase.scale})`,
            transition: `transform ${phase.seconds}s ease-in-out`,
          }}
        />
        <div
          className="absolute w-28 h-28 rounded-full bg-primary/25"
          style={{
            transform: `scale(${phase.scale})`,
            transition: `transform ${phase.seconds}s ease-in-out`,
          }}
        />
        <span className="relative z-10 text-lg font-medium text-gray-700 dark:text-gray-200" aria-live="polite">
          {phase.label}
        </span>
      </div>

      <p className="mt-10 text-sm text-gray-500 dark:text-gray-400">
        {cycles === 0 ? "Follow the circle. In… hold… out… hold." : cycles < 3 ? "You're doing fine. Stay with it." : "Whenever you're ready, come back."}
      </p>
      <button
        onClick={onClose}
        className="mt-6 text-xs font-medium text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors cursor-pointer"
      >
        I'm done
      </button>
    </div>
  )
}
