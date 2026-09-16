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

/** Plain-language background for each axis: what it is, why it matters, how this app measures it, where to read more. */
export interface AxisGuide {
  what: string
  why: string
  measured: string
  moves: string
  link: { label: string; href: string }
}

export const WELLBEING_AXES: Omit<WellbeingAxis, "value" | "previous">[] = [
  { key: "mood", label: "Mood", description: "Emotional state rated by the analysis, 1 to 10." },
  { key: "energy", label: "Energy", description: "The Find Your Energy battery level." },
  { key: "calm", label: "Calm", description: "The inverse of the rumination level: little overthinking scores high." },
  { key: "agency", label: "Agency", description: "Share of what you wrote about that sits within your control." },
  { key: "outward", label: "Outward focus", description: "The inverse of the self-focus score: attention on the world, not only on yourself." },
  { key: "clarity", label: "Clarity", description: "Linguistic clarity, the grammar score." },
]

export const AXIS_GUIDES: Record<string, AxisGuide> = {
  mood: {
    what: "How you were feeling, as read from the tone of the entry, on a scale from despair to euphoric.",
    why: "Mood colours attention, memory and judgement. A low mood makes problems look bigger and options fewer, so knowing where you are helps you discount the distortion.",
    measured: "The analysis rates each entry from 1 to 10; this axis is that rating as a percentage, averaged over the period.",
    moves: "Sleep, movement, daylight, contact with people you like, and finishing things you have been avoiding.",
    link: { label: "Mood (psychology), Wikipedia", href: "https://en.wikipedia.org/wiki/Mood_(psychology)" },
  },
  energy: {
    what: "Your mental battery: how much capacity the day left you with.",
    why: "Energy is the budget everything else is paid from. When it is low, small tasks cost more and self-control runs out sooner, so protecting what charges you is the highest-leverage habit there is.",
    measured: "The Find Your Energy battery: mood, the balance of chargers to drainers, how much of the entry is within your control, focus, clarity and engagement, with a bonus for completed micro-actions and resets.",
    moves: "Rest, cutting a known drainer, and doing one charging activity on purpose rather than by accident.",
    link: { label: "Vitality, Wikipedia", href: "https://en.wikipedia.org/wiki/Vitality" },
  },
  calm: {
    what: "How little your mind was looping: replaying the past or rehearsing the future without getting anywhere.",
    why: "Rumination is one of the strongest predictors of anxiety and low mood, and it feeds on itself. The skill is not stopping thoughts but noticing the loop early and stepping out of it, which is what the 3-Minute Reset practises.",
    measured: "The analysis rates rumination low, moderate or high for each entry; low scores 100, moderate 50, high 0.",
    moves: "The reset, a walk, writing the loop down once and closing it, and sleep.",
    link: { label: "Rumination (psychology), Wikipedia", href: "https://en.wikipedia.org/wiki/Rumination_(psychology)" },
  },
  agency: {
    what: "The share of what you wrote about that sits within your control, as opposed to things you can only worry about.",
    why: "People who believe their actions matter, an internal locus of control, report less stress and follow through more. The Stoic version is older: spend effort only where it can change something. Low agency days are the ones where most of the entry is about other people's choices.",
    measured: "From the Circle of Control: the number of controllable factors the analysis found, divided by all factors it found.",
    moves: "Restating a worry as the one action you could take, and letting the rest be outside your hands.",
    link: { label: "Locus of control, Wikipedia", href: "https://en.wikipedia.org/wiki/Locus_of_control" },
  },
  outward: {
    what: "How much of your attention was on the world and other people rather than only on yourself.",
    why: "Heavy self-focus travels with worry and low mood; attention that reaches outward, to people, work and surroundings, tends to lift wellbeing. It is not about ignoring yourself, only about not being trapped in the mirror.",
    measured: "The inverse of the self-focus score: an entry rated 3 out of 10 for self-focus scores 70 here.",
    moves: "Writing about someone else's day, gratitude, and doing something for another person.",
    link: { label: "Self-consciousness, Wikipedia", href: "https://en.wikipedia.org/wiki/Self-consciousness" },
  },
  clarity: {
    what: "How clearly the entry reads: sentences that hold together, grammar that does not trip.",
    why: "Clear writing and clear thinking move together. When a tangled mind produces tangled sentences, the fixes the analysis offers are a way back to the thought. Expressive writing research links putting experiences into coherent words with better health over time.",
    measured: "The grammar score from the analysis, 1 to 10, as a percentage.",
    moves: "Shorter sentences, one idea each, and reading the entry back once.",
    link: { label: "Expressive writing, Wikipedia", href: "https://en.wikipedia.org/wiki/Expressive_writing" },
  },
}

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
