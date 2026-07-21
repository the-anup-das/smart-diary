"use client"
import * as React from "react"
import { HeartHandshake, Phone, Wind } from "lucide-react"
import { BreathingExercise } from "./BreathingExercise"

interface Helpline {
  name: string
  contact: string
}

const HELPLINES: Record<string, Helpline[]> = {
  india: [
    { name: "Tele-MANAS (Govt. of India, 24/7, free)", contact: "14416" },
    { name: "KIRAN Mental Health Helpline (24/7)", contact: "1800-599-0019" },
  ],
  us: [
    { name: "988 Suicide & Crisis Lifeline (24/7)", contact: "Call or text 988" },
    { name: "Crisis Text Line", contact: "Text HOME to 741741" },
  ],
  uk: [
    { name: "Samaritans (24/7, free)", contact: "116 123" },
  ],
  international: [],
}

/**
 * Shown when an entry carries acute-distress signals. Deliberately calm: warm
 * colors (never alarm-red), no "we detected" surveillance framing, dismissible,
 * and it never blocks writing.
 */
export function SupportCard({
  region = "international",
  customHelpline = "",
  onDismiss,
}: {
  region?: string
  customHelpline?: string
  onDismiss?: () => void
}) {
  const [breathing, setBreathing] = React.useState(false)
  const lines = HELPLINES[region] || []

  return (
    <div className="p-6 rounded-2xl bg-gradient-to-br from-sky-500/10 to-violet-500/10 border border-sky-500/25 shadow-lg fade-in" role="region" aria-label="Support resources">
      {breathing && <BreathingExercise onClose={() => setBreathing(false)} />}

      <div className="flex items-start gap-3">
        <div className="p-2.5 rounded-xl bg-sky-500/15 text-sky-600 dark:text-sky-400 flex-shrink-0">
          <HeartHandshake className="w-5 h-5" />
        </div>
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
            Some of what you wrote sounds really heavy.
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-300 mt-1 leading-relaxed">
            Thank you for putting it into words — that takes courage. You don't have to
            carry this alone: talking to someone often helps more than it feels like it will.
          </p>

          <ul className="mt-4 space-y-2">
            {customHelpline && (
              <li className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
                <Phone className="w-3.5 h-3.5 text-sky-500 flex-shrink-0" />
                <span>{customHelpline}</span>
              </li>
            )}
            {lines.map(line => (
              <li key={line.name} className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
                <Phone className="w-3.5 h-3.5 text-sky-500 flex-shrink-0" />
                <span>
                  {line.name} — <strong className="font-semibold">{line.contact}</strong>
                </span>
              </li>
            ))}
            <li className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
              <Phone className="w-3.5 h-3.5 text-sky-500 flex-shrink-0" />
              <span>
                Anywhere in the world:{" "}
                <a href="https://findahelpline.com" target="_blank" rel="noopener noreferrer" className="underline decoration-sky-400 underline-offset-2 hover:text-sky-600 dark:hover:text-sky-300">
                  findahelpline.com
                </a>
              </span>
            </li>
          </ul>

          <div className="flex flex-wrap items-center gap-3 mt-5">
            <button
              onClick={() => setBreathing(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-sky-500/15 text-sky-700 dark:text-sky-300 text-sm font-medium hover:bg-sky-500/25 transition-colors cursor-pointer"
            >
              <Wind className="w-4 h-4" /> Breathe with me for a minute
            </button>
            {onDismiss && (
              <button
                onClick={onDismiss}
                className="text-xs font-medium text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer"
              >
                I'm okay — show my reflection
              </button>
            )}
          </div>
          <p className="text-[11px] text-gray-400 mt-4">
            This journal is a companion, not a replacement for professional care.
          </p>
        </div>
      </div>
    </div>
  )
}
