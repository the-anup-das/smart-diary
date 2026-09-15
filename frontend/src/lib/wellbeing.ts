/**
 * Wellbeing Profile: six capacities on one 0-100 scale, higher is always better.
 * Mirrors backend/wellbeing.py so a single entry's profile can be drawn straight from
 * the feedback payload, while period averages come from GET /api/insights.
 */

export interface WellbeingAxis {
  key: string
  label: string
  description: string
  value: number | null
  previous?: number | null
}

export const WELLBEING_AXES: Omit<WellbeingAxis, "value" | "previous">[] = [
  { key: "mood", label: "Mood", description: "Emotional state rated by the analysis, 1 to 10." },
  { key: "energy", label: "Energy", description: "The Find Your Energy battery level." },
  { key: "calm", label: "Calm", description: "The inverse of the rumination level: little overthinking scores high." },
  { key: "agency", label: "Agency", description: "Share of what you wrote about that sits within your control." },
  { key: "outward", label: "Outward focus", description: "The inverse of the self-focus score: attention on the world, not only on yourself." },
  { key: "clarity", label: "Clarity", description: "Linguistic clarity, the grammar score." },
]

const RUMINATION_TO_CALM: Record<string, number> = { low: 100, moderate: 50, high: 0 }

const clamp = (v: number) => Math.max(0, Math.min(100, v))
const pct10 = (v: unknown) => (typeof v === "number" ? clamp((v / 10) * 100) : null)
const round1 = (v: number) => Math.round(v * 10) / 10

/** Profile of one analysed entry, from the feedback object the analyze endpoint returns. */
export function profileFromFeedback(feedback: any): WellbeingAxis[] {
  const energy = feedback?.energyData || {}
  const controllables = Array.isArray(energy.controllables) ? energy.controllables.length : 0
  const uncontrollables = Array.isArray(energy.uncontrollables) ? energy.uncontrollables.length : 0
  const total = controllables + uncontrollables
  const rumination = typeof energy.rumination_level === "string" ? energy.rumination_level.toLowerCase() : null

  const values: Record<string, number | null> = {
    mood: pct10(feedback?.moodScore),
    energy: typeof energy.battery_level === "number" ? clamp(energy.battery_level) : null,
    calm: rumination !== null && rumination in RUMINATION_TO_CALM ? RUMINATION_TO_CALM[rumination] : null,
    agency: total > 0 ? (controllables / total) * 100 : null,
    outward: typeof feedback?.selfFocusScore === "number" ? clamp(((10 - feedback.selfFocusScore) / 10) * 100) : null,
    clarity: pct10(feedback?.grammarScore),
  }

  return WELLBEING_AXES.map(axis => {
    const v = values[axis.key]
    return { ...axis, value: v === null || v === undefined ? null : round1(v) }
  })
}

/** Enough signals to be worth drawing (a radar with one or two points is misleading). */
export function hasProfile(axes: WellbeingAxis[]): boolean {
  return axes.filter(a => a.value !== null).length >= 3
}
