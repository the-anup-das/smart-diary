/**
 * Focus Reset: shared types and programme content.
 *
 * The programme follows Anna Lembke's DOPAMINE structure (Data, Objectives, Problems,
 * Abstinence, Mindfulness, Insight, Next steps, Experiment) and Cameron Sepah's
 * stimulus-control "dopamine fasting". The app measures behaviour described in the
 * person's own writing, never dopamine itself.
 */

export interface SignalBehaviour {
  behaviour: string
  category: string
  trigger: string
  timeOfDay: string
  lostControl: boolean
}

export interface SignalDay {
  date: string
  analysed: boolean
  load: number
  behaviours: SignalBehaviour[]
  afterState: string
  lowMotivation: boolean
  sleepDisrupted: boolean
  craving: boolean
  displaced: string[]
}

export interface FocusPlan {
  id: string
  behaviour: string
  category: string | null
  objectives: string | null
  problems: string | null
  abstinenceDays: number
  startDate: string
  status: "active" | "completed" | "abandoned"
  rules: string[]
  replacements: string[]
  dayNumber: number
  daysLeft: number
  finished: boolean
  cleanStreak: number
  cleanDays: number
  checkedInDays: number
  checkins: { date: string; urges: number; gaveIn: boolean; sleepOk: boolean | null; note: string | null }[]
  urges: { total: number; surfed: number; recent: { id: string; loggedAt: string | null; intensity: number | null; acted: boolean; trigger: string | null; note: string | null }[] }
  completedAt: string | null
}

export interface FocusOverview {
  success: boolean
  active: boolean
  windowDays: number
  days: SignalDay[]
  analysedDays: number
  signalDays: number
  recentSignalDays: number
  heavyDays: number
  lostControlDays: number
  lowMotivationDays: number
  sleepDisruptedDays: number
  topBehaviours: { label: string; category: string; count: number }[]
  topTriggers: { label: string; count: number }[]
  timeOfDay: Record<string, number>
  afterStates: Record<string, number>
  displaced: string[]
  plan: FocusPlan | null
  lastPlan: { behaviour: string; status: string; completedAt: string | null } | null
}

export const CATEGORY_LABELS: Record<string, string> = {
  screens: "Screens",
  social_media: "Social media",
  video: "Video",
  gaming: "Gaming",
  porn: "Porn",
  gambling: "Gambling",
  food: "Food",
  shopping: "Shopping",
  substances: "Substances",
  other: "Other",
}

/** Categories where an app is not enough and a person should be involved. */
export const NEEDS_SUPPORT = new Set(["substances", "gambling"])

export const OBJECTIVE_OPTIONS = ["boredom", "loneliness", "avoiding a task", "winding down", "falling asleep", "stress relief", "habit, no reason"]

/** Self-binding rule suggestions, in Lembke's three flavours: physical, chronological, categorical. */
export const RULE_SUGGESTIONS: Record<string, string[]> = {
  screens: ["Phone charges outside the bedroom", "No screens after 10pm", "Home screen holds only tools, no feeds", "Greyscale display after dinner"],
  social_media: ["Log out after each use, no saved password", "Apps deleted from the phone; browser only", "Two fixed check-in times a day, 10 minutes each", "Phone charges outside the bedroom"],
  video: ["Autoplay off everywhere", "Watch only at the table, never in bed", "One episode, decided before pressing play", "No screens after 10pm"],
  gaming: ["Console or client uninstalled for the window", "Play only on named days, with a timer set first", "Controller lives in a drawer in another room"],
  porn: ["Content filter on every device", "Phone charges outside the bedroom", "No devices in bed"],
  gambling: ["Self-exclusion registered with each site", "Cards and cash held by someone you trust", "Blocking software installed"],
  food: ["Trigger foods not kept in the house", "Eat only at the table, never with a screen", "A planned snack replaces the impulse one"],
  shopping: ["Cards removed from browsers and apps", "A 48-hour list before any purchase", "Unsubscribe from every sale email"],
  substances: ["None kept at home", "Tell one person the window and the rule", "Avoid the places where it happens"],
  other: ["Remove the cue from sight", "Set a fixed time and a timer", "Tell one person the rule"],
}

export const REPLACEMENT_SUGGESTIONS = ["A ten-minute walk", "A page of writing here", "Stretching", "Cold water on the face", "A call to a friend", "Reading, paper only", "A shower", "Tidying one surface"]

export const PROGRAMME_STEPS = [
  { key: "data", letter: "D", title: "Data", blurb: "What, how much, when. Your entries already tell part of this story." },
  { key: "objectives", letter: "O", title: "Objectives", blurb: "What the behaviour does for you. It always does something." },
  { key: "problems", letter: "P", title: "Problems", blurb: "What it costs, in your own words." },
  { key: "abstinence", letter: "A", title: "Abstinence", blurb: "One behaviour, one window. Long enough for the balance to reset." },
  { key: "mindfulness", letter: "M", title: "Mindfulness", blurb: "Urges peak and pass. You learn to watch one go by." },
  { key: "insight", letter: "I", title: "Insight", blurb: "Keep writing daily. The pattern shows itself." },
  { key: "next", letter: "N", title: "Next steps", blurb: "Rules that bind you in advance, when you are calm." },
  { key: "experiment", letter: "E", title: "Experiment", blurb: "Run it, track it, adjust it." },
]

export function tzOffset() {
  return -new Date().getTimezoneOffset()
}

export function localToday() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

export async function fetchOverview(): Promise<FocusOverview | null> {
  try {
    const res = await fetch(`/api/focus/overview?tz_offset=${tzOffset()}`)
    if (!res.ok) return null
    const data = await res.json()
    return data?.success ? data : null
  } catch {
    return null
  }
}
