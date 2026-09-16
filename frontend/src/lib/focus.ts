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
  // mind fitness
  fog: boolean
  fogNote: string
  minutes: number
  shortForm: boolean
  builders: string[]
  rot: number
}

export interface MindDay {
  date: string
  analysed: boolean
  rot: number
  fog: boolean
  shortForm: boolean
  minutes: number
  builders: string[]
  manual: string[]
}

export interface MindGuide {
  startDate: string
  day: number
  week: number
  finished: boolean
}

export interface MindSummary {
  active: boolean
  fogDays: number
  recentFogDays: number
  shortFormDays: number
  rotDays: number
  heavyRotDays: number
  avgMinutes: number | null
  totalMinutes: number
  notes: string[]
  builders: Record<string, { weekDays: number; monthDays: number; target: number }>
  weekScore: number
  weekBuilderDays: number
  days: MindDay[]
  guide: MindGuide | null
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
  mind: MindSummary
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

// ---------------------------------------------------------------- mind fitness

export const GUIDE_DAYS = 28

/** Brain-building activities, with how many days a week each is worth aiming for. Order is display order. */
export const BUILDERS: { key: string; label: string; target: number; example: string; why: string }[] = [
  { key: "sleep", label: "Slept enough", target: 5, example: "Seven hours or more", why: "Sleep is when the day's memories are filed. Short nights show up first as poor attention." },
  { key: "deep_reading", label: "Read long-form", target: 4, example: "Twenty minutes of a book or a long article, no skimming", why: "Sustained reading trains the same attention that feeds wear down, a fragment at a time." },
  { key: "deep_work", label: "Deep work block", target: 3, example: "One task, no tabs, twenty-five to fifty minutes", why: "Focus is a capacity. Single-task blocks rebuild it the way sets rebuild a muscle." },
  { key: "exercise", label: "Moved hard", target: 3, example: "A run, a lift, a fast walk", why: "Exercise raises BDNF, a growth factor for neurons, and reliably improves memory and executive function." },
  { key: "rest", label: "Real rest", target: 3, example: "Boredom, a nap, staring out of a window, no feed", why: "Unfilled minutes let the mind wander, which is where consolidation and new ideas happen." },
  { key: "nature", label: "Time outdoors", target: 2, example: "A walk somewhere green", why: "Attention Restoration Theory: natural settings let directed attention recover." },
  { key: "learning", label: "Learned something hard", target: 2, example: "A language, an instrument, a proof, a recipe from scratch", why: "Effortful learning builds new connections and cognitive reserve; easy content builds nothing." },
  { key: "conversation", label: "Real conversation", target: 2, example: "Face to face, or a proper call", why: "Live conversation works memory, attention and empathy at the same time." },
  { key: "creating", label: "Made something", target: 1, example: "Wrote, drew, built, cooked, played music", why: "Making reverses the direction of the habit: output instead of intake." },
  { key: "play", label: "Played", target: 1, example: "A board game, a sport, a puzzle with someone", why: "Play is problem-solving at low stakes; it keeps thinking flexible." },
]

export const BUILDER_LABELS: Record<string, string> = Object.fromEntries(BUILDERS.map(b => [b.key, b.label]))

/** Four weeks, one theme each: subtract, rebuild, feed, keep. Everything here is something to do, nothing to buy. */
export const MIND_GUIDE_WEEKS: { week: number; title: string; theme: string; why: string; practices: string[]; prompt: string }[] = [
  {
    week: 1, title: "Notice and subtract", theme: "See how much of the day is passive, and take the worst of it away.",
    why: "The research on short-form video and attention is young but consistent: heavier use goes with poorer attention control and working memory, and the association weakens when use drops. Week one is measurement and one subtraction.",
    practices: [
      "Write the minutes of passive scrolling into each entry, even roughly. The app keeps the number.",
      "Turn off autoplay everywhere and move short-video apps off the home screen, or delete them for the month.",
      "The phone charges outside the bedroom. Nothing on it in the first thirty minutes after waking.",
      "Once a day, wait somewhere without the phone: a queue, a lift, a kettle. Let it be boring.",
    ],
    prompt: "When did the fog come today, and what had I just been doing?",
  },
  {
    week: 2, title: "Rebuild attention", theme: "Train the capacity directly, and restore it between sessions.",
    why: "Attention responds to training. Long-form reading and single-task blocks rebuild it; sleep and green space restore it. None of this needs equipment.",
    practices: [
      "Twenty minutes of a paper book or a long article every day, no skimming, phone in another room.",
      "One deep-work block of twenty-five minutes: one task, notifications off. Add five minutes each day it goes well.",
      "A walk somewhere green, twice this week, without earphones.",
      "Seven hours in bed on five nights of the seven. Sleep is where the day gets filed.",
    ],
    prompt: "Where did my attention go today without being pulled?",
  },
  {
    week: 3, title: "Feed the brain", theme: "Put in the inputs with the best evidence, and make instead of consume.",
    why: "Exercise, effortful learning and live conversation carry the strongest evidence for memory and executive function. Making something reverses the intake habit.",
    practices: [
      "Move hard three times: a run, a lift, anything that leaves you breathing.",
      "Pick one hard thing to learn and give it twenty minutes on two days: an instrument, a language, a skill by hand.",
      "One real conversation, face to face or a proper call, with no screen in it.",
      "Make one thing this week instead of consuming: write, draw, cook from scratch, build.",
    ],
    prompt: "What did I make or learn today that did not exist this morning?",
  },
  {
    week: 4, title: "Make it stick", theme: "Let the environment do the work, so the habits hold without willpower.",
    why: "Habits last when the cue is gone and the replacement is easy. This week compares week one's entries with now and turns what helped into rules.",
    practices: [
      "Read the entries from week one. Count the fog days then and now.",
      "Choose a daily passive-consumption budget you can keep, and one time of day when feeds are fine.",
      "Keep the three builders that made the biggest difference; drop the rest without guilt.",
      "Write the rules into an entry, as if to a friend who is starting week one.",
    ],
    prompt: "What has changed in how my mind feels, and what do I keep?",
  },
]

export const BRAIN_ROT_NOTES = [
  "\"Brain rot\" was Oxford's word of the year for 2024: the supposed deterioration of a person's mental or intellectual state from overconsumption of trivial online content. It is a description, not a diagnosis.",
  "What the studies show so far: heavier short-form video use goes with poorer attention control, working memory and learning, and the association weakens when use drops. The work is recent and mostly correlational, so read it as a strong hint rather than a verdict.",
  "The reverse is better established. Sleep, exercise, long-form reading, effortful learning, time in nature and live conversation each have decades of evidence behind them for attention and memory. That is why the builders are what they are.",
  "This app reads what you write about your attention. It does not test your brain. Fog that is persistent, heavy or new is a conversation for a doctor, not an app.",
]
