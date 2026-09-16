"use client"
import * as React from "react"
import Link from "next/link"
import { Crosshair, Waves, Check, Flame, ShieldAlert, RefreshCw, ArrowRight } from "lucide-react"
import { UrgeSurf } from "@/components/focus/UrgeSurf"
import { MindPanel } from "@/components/focus/MindPanel"
import { ThreeMinuteReset } from "@/components/calm/ThreeMinuteReset"
import {
  fetchOverview, tzOffset, localToday, CATEGORY_LABELS, NEEDS_SUPPORT, OBJECTIVE_OPTIONS,
  RULE_SUGGESTIONS, REPLACEMENT_SUGGESTIONS, PROGRAMME_STEPS, type FocusOverview, type FocusPlan,
} from "@/lib/focus"

const LOAD_COLOUR = ["transparent", "#fbbf24", "#f97316", "#f43f5e"]
const JSON_HEADERS = { "Content-Type": "application/json" }

export default function FocusPage() {
  const [data, setData] = React.useState<FocusOverview | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [surfOpen, setSurfOpen] = React.useState(false)
  const [resetOpen, setResetOpen] = React.useState(false)
  const [notice, setNotice] = React.useState<string | null>(null)

  const reload = React.useCallback(async () => {
    const d = await fetchOverview()
    setData(d)
    setLoading(false)
  }, [])
  React.useEffect(() => { reload() }, [reload])

  const logUrge = async (acted: boolean, intensity: number, trigger?: string) => {
    await fetch("/api/focus/urges", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ acted, intensity, trigger }) }).catch(() => {})
    setNotice(acted ? "Logged. Tomorrow's entry is a good place to write what led up to it." : "Logged. One wave surfed.")
    reload()
  }

  if (loading) {
    return <div className="max-w-4xl mx-auto pt-6 text-gray-500 animate-pulse">Reading your recent entries...</div>
  }

  const plan = data?.plan ?? null
  const hasSignal = !!data && data.recentSignalDays > 0
  const mindActive = !!data?.mind?.active
  const hidden = !!data?.hidden

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-20 pt-6 fade-in">
      <header>
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-teal-500/10 rounded-xl text-teal-600 dark:text-teal-400"><Crosshair className="w-6 h-6" /></div>
          <h1 className="text-3xl font-bold font-serif">Focus Reset</h1>
        </div>
        <p className="text-gray-500 text-lg">
          For the habits that give a quick hit and take the day, and for the fog they leave behind. Pick one, step away from it for a while, learn to let urges pass, and put back what builds a sharper mind.
        </p>
      </header>

      {notice && (
        <div className="p-3 rounded-xl bg-teal-500/10 border border-teal-500/20 text-sm text-teal-800 dark:text-teal-200 flex items-center justify-between">
          <span>{notice}</span>
          <button onClick={() => setNotice(null)} className="text-xs underline cursor-pointer">dismiss</button>
        </div>
      )}

      {hidden && (
        <Card>
          <h2 className="text-lg font-semibold">Switched off in Settings</h2>
          <p className="text-sm text-gray-500 mt-1">
            Focus Reset and Mind Fitness are hidden by your preferences: nothing in the navigation, on Insights or after analysis.
            Your entries are still analysed, so everything is here when you{" "}
            <Link href="/settings" className="text-teal-700 dark:text-teal-300 hover:underline">turn them back on</Link>.
          </p>
        </Card>
      )}

      {data && <SignalPanel data={data} />}

      {!hasSignal && !plan && !mindActive && !hidden && (
        <Card>
          <h2 className="text-lg font-semibold">Nothing to work on right now</h2>
          <p className="text-sm text-gray-500 mt-1">
            Your recent entries do not mention compulsive habits, fog or heavy passive consumption, so there is no programme to run. This page comes back on its own if that changes.
          </p>
          {data?.lastPlan && (
            <p className="text-sm text-gray-500 mt-3">Last reset: {data.lastPlan.behaviour}, {data.lastPlan.status}.</p>
          )}
        </Card>
      )}

      {hidden ? null : plan ? (
        <ActivePlan plan={plan} onSurf={() => setSurfOpen(true)} onReset={() => setResetOpen(true)} onChanged={reload} onQuickLog={logUrge} />
      ) : hasSignal && data ? (
        <PlanWizard data={data} onCreated={reload} onTrySurf={() => setSurfOpen(true)} />
      ) : null}

      {data && mindActive && <MindPanel mind={data.mind} onChanged={reload} />}

      <UrgeSurf open={surfOpen} onClose={() => setSurfOpen(false)} onOutcome={(acted, intensity) => logUrge(acted, intensity)} />
      <ThreeMinuteReset open={resetOpen} source="manual" onClose={() => setResetOpen(false)} />
    </div>
  )
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`p-5 lg:p-7 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg ${className}`}>{children}</div>
}

// ---------------------------------------------------------------- signals

function SignalPanel({ data }: { data: FocusOverview }) {
  // Only the stimulation story lives here; a writer with mind signals alone gets the Mind panel instead.
  if (!data.active || (data.signalDays === 0 && !data.plan)) return null
  const tod = Object.entries(data.timeOfDay).sort((a, b) => b[1] - a[1])[0]?.[0]
  return (
    <Card>
      <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-3">What your entries show, last four weeks</h2>
      <div className="grid grid-cols-14 gap-1.5">
        {data.days.map(d => (
          <div key={d.date} title={`${d.date}: ${d.analysed ? (d.load ? `load ${d.load}, ${d.behaviours.map(b => b.behaviour).join(", ")}` : "no signal") : "not reflected"}`}
            className={`aspect-square rounded-[3px] ${d.analysed ? "" : "border border-dashed border-black/10 dark:border-white/15"}`}
            style={{ backgroundColor: d.load ? LOAD_COLOUR[Math.min(3, d.load)] : d.analysed ? "rgba(156,163,175,0.25)" : "transparent", opacity: 0.85 }} />
        ))}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
        <Stat label="Signal days" value={`${data.signalDays}`} sub={`of ${data.analysedDays} reflected`} />
        <Stat label="Lost track of time" value={`${data.lostControlDays}`} sub="days" />
        <Stat label="Sleep cut short" value={`${data.sleepDisruptedDays}`} sub="days" />
        <Stat label="Usually" value={tod && tod !== "unknown" ? tod : "varies"} sub="time of day" />
      </div>
      {data.topBehaviours.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-4">
          {data.topBehaviours.map(b => (
            <span key={b.label} className="px-3 py-1 rounded-full bg-black/5 dark:bg-white/5 text-sm">
              {b.label} <span className="text-gray-400 font-mono text-xs">×{b.count}</span>
              <span className="text-[10px] uppercase tracking-wider text-gray-400 ml-2">{CATEGORY_LABELS[b.category] || b.category}</span>
            </span>
          ))}
        </div>
      )}
      {data.displaced.length > 0 && (
        <p className="text-sm text-gray-600 dark:text-gray-300 mt-4">
          What it pushed aside, in your words: <span className="italic">{data.displaced.slice(-4).join("; ")}</span>.
        </p>
      )}
      {data.topBehaviours.some(b => NEEDS_SUPPORT.has(b.category)) && (
        <div className="mt-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-sm text-amber-900 dark:text-amber-200 flex gap-2">
          <ShieldAlert className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>Substances and gambling are where an app is not enough on its own. This programme can sit alongside real support, and a doctor or a helpline is the right first call. The Settings page holds your support contacts.</span>
        </div>
      )}
    </Card>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="p-3 rounded-xl bg-black/[0.03] dark:bg-white/5 text-center">
      <p className="text-[10px] uppercase tracking-widest text-gray-400">{label}</p>
      <p className="text-xl font-bold mt-1 capitalize">{value}</p>
      <p className="text-[11px] text-gray-500">{sub}</p>
    </div>
  )
}

// ---------------------------------------------------------------- wizard

function PlanWizard({ data, onCreated, onTrySurf }: { data: FocusOverview; onCreated: () => void; onTrySurf: () => void }) {
  const suggested = data.topBehaviours[0]
  const [behaviour, setBehaviour] = React.useState(suggested?.label || "")
  const [category, setCategory] = React.useState(suggested?.category || "other")
  const [objectiveTags, setObjectiveTags] = React.useState<string[]>(data.topTriggers.map(t => t.label).filter(t => OBJECTIVE_OPTIONS.includes(t)))
  const [objectives, setObjectives] = React.useState("")
  const [problems, setProblems] = React.useState(data.displaced.length ? `It pushed aside: ${data.displaced.slice(-4).join(", ")}.` : "")
  const [days, setDays] = React.useState<7 | 14 | 30>(7)
  const [rules, setRules] = React.useState<string[]>([])
  const [customRule, setCustomRule] = React.useState("")
  const [replacements, setReplacements] = React.useState<string[]>([])
  const [saving, setSaving] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const suggestions = RULE_SUGGESTIONS[category] || RULE_SUGGESTIONS.other
  const toggle = (list: string[], set: (v: string[]) => void, item: string) => set(list.includes(item) ? list.filter(i => i !== item) : [...list, item])

  const start = async () => {
    if (behaviour.trim().length < 2) { setError("Name the behaviour first."); return }
    setSaving(true)
    setError(null)
    const body = {
      behaviour: behaviour.trim(),
      category,
      objectives: [objectiveTags.join(", "), objectives.trim()].filter(Boolean).join(". "),
      problems: problems.trim(),
      abstinenceDays: days,
      startDate: localToday(),
      rules: [...rules, customRule.trim()].filter(Boolean),
      replacements,
    }
    const res = await fetch(`/api/focus/plans?tz_offset=${tzOffset()}`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body) }).catch(() => null)
    setSaving(false)
    if (!res || !res.ok) { setError("Could not save the plan. Try again."); return }
    onCreated()
  }

  const step = (key: string) => PROGRAMME_STEPS.find(s => s.key === key)!

  return (
    <Card>
      <h2 className="text-xl font-semibold">Set up your reset</h2>
      <p className="text-sm text-gray-500 mt-1">
        Eight short steps, one letter each, following Anna Lembke's DOPAMINE structure. Your entries have filled in what they can.
      </p>

      <Section step={step("data")}>
        <p className="text-sm text-gray-600 dark:text-gray-300">Pick the one behaviour to step away from. One at a time works; several at once rarely does.</p>
        <div className="flex flex-wrap gap-2 mt-3">
          {data.topBehaviours.map(b => (
            <button key={b.label} onClick={() => { setBehaviour(b.label); setCategory(b.category) }}
              className={`px-3 py-1.5 rounded-full border text-sm transition-colors cursor-pointer ${behaviour === b.label ? "bg-teal-600 border-teal-600 text-white" : "border-black/10 dark:border-white/15 hover:border-teal-500/50"}`}>
              {b.label} <span className="opacity-60 font-mono text-xs">×{b.count}</span>
            </button>
          ))}
        </div>
        <div className="flex flex-col sm:flex-row gap-2 mt-3">
          <input value={behaviour} onChange={e => setBehaviour(e.target.value)} placeholder="or name it yourself" className="flex-1 rounded-xl border border-black/10 dark:border-white/10 bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/50" />
          <select value={category} onChange={e => setCategory(e.target.value)} className="rounded-xl border border-black/10 dark:border-white/10 bg-transparent px-3 py-2 text-sm focus:outline-none">
            {Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      </Section>

      <Section step={step("objectives")}>
        <p className="text-sm text-gray-600 dark:text-gray-300">Every habit is doing a job. Naming the job is how you find something else to do it.</p>
        <div className="flex flex-wrap gap-2 mt-3">
          {OBJECTIVE_OPTIONS.map(o => (
            <button key={o} onClick={() => toggle(objectiveTags, setObjectiveTags, o)} className={`px-3 py-1.5 rounded-full border text-sm cursor-pointer transition-colors ${objectiveTags.includes(o) ? "bg-teal-600 border-teal-600 text-white" : "border-black/10 dark:border-white/15 hover:border-teal-500/50"}`}>{o}</button>
          ))}
        </div>
        <textarea value={objectives} onChange={e => setObjectives(e.target.value)} rows={2} placeholder="In your own words, what does it give you?" className="mt-3 w-full rounded-xl border border-black/10 dark:border-white/10 bg-transparent p-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/50" />
      </Section>

      <Section step={step("problems")}>
        <p className="text-sm text-gray-600 dark:text-gray-300">Its costs, as honestly as you can. Your entries mentioned some of them.</p>
        <textarea value={problems} onChange={e => setProblems(e.target.value)} rows={3} className="mt-3 w-full rounded-xl border border-black/10 dark:border-white/10 bg-transparent p-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/50" />
      </Section>

      <Section step={step("abstinence")}>
        <p className="text-sm text-gray-600 dark:text-gray-300">Lembke's clinical recommendation is four weeks, long enough for the reward balance to level out. Start with what you can actually keep, then extend.</p>
        <div className="grid grid-cols-3 gap-3 mt-3">
          {([7, 14, 30] as const).map(d => (
            <button key={d} onClick={() => setDays(d)} className={`py-3 rounded-xl border text-sm font-medium cursor-pointer transition-colors ${days === d ? "bg-teal-600 border-teal-600 text-white" : "border-black/10 dark:border-white/15 hover:border-teal-500/50"}`}>
              {d} days{d === 7 ? ", a start" : d === 30 ? ", the full reset" : ""}
            </button>
          ))}
        </div>
      </Section>

      <Section step={step("mindfulness")}>
        <p className="text-sm text-gray-600 dark:text-gray-300">
          The urge will come. Urges rise, peak and fall on their own within a couple of minutes when nothing feeds them. The practice is to watch one pass, ninety seconds, named and felt in the body, without acting. That is different from the 3-Minute Reset, which calms a looping mind; this one is for a craving.
        </p>
        <button onClick={onTrySurf} className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-teal-500/40 text-teal-700 dark:text-teal-300 text-sm font-medium hover:bg-teal-500/10 cursor-pointer transition-colors">
          <Waves className="w-4 h-4" /> Try surfing an urge now
        </button>
      </Section>

      <Section step={step("insight")}>
        <p className="text-sm text-gray-600 dark:text-gray-300">Keep writing every day. The entries are how the pattern was found and how you will see it change. Mention the urges, what triggered them and what you did instead.</p>
      </Section>

      <Section step={step("next")}>
        <p className="text-sm text-gray-600 dark:text-gray-300">Self-binding: rules you set now, while calm, so the decision is already made when the urge arrives. Physical, timed or by category.</p>
        <div className="space-y-2 mt-3">
          {suggestions.map(r => (
            <label key={r} className="flex items-center gap-3 text-sm cursor-pointer">
              <input type="checkbox" checked={rules.includes(r)} onChange={() => toggle(rules, setRules, r)} className="w-4 h-4 accent-teal-600" /> {r}
            </label>
          ))}
          <input value={customRule} onChange={e => setCustomRule(e.target.value)} placeholder="Add your own rule" className="w-full rounded-xl border border-black/10 dark:border-white/10 bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/50" />
        </div>
        <p className="text-sm text-gray-600 dark:text-gray-300 mt-5">What you will do instead when the job comes up. Pick a few.</p>
        <div className="flex flex-wrap gap-2 mt-3">
          {REPLACEMENT_SUGGESTIONS.map(r => (
            <button key={r} onClick={() => toggle(replacements, setReplacements, r)} className={`px-3 py-1.5 rounded-full border text-sm cursor-pointer transition-colors ${replacements.includes(r) ? "bg-teal-600 border-teal-600 text-white" : "border-black/10 dark:border-white/15 hover:border-teal-500/50"}`}>{r}</button>
          ))}
        </div>
      </Section>

      <Section step={step("experiment")}>
        <p className="text-sm text-gray-600 dark:text-gray-300">Run it as an experiment, not a verdict on yourself. Log urges, check in each evening, and see what the entries say at the end.</p>
        {error && <p className="text-sm text-rose-500 mt-3">{error}</p>}
        <button onClick={start} disabled={saving} className="mt-4 w-full py-3.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-semibold cursor-pointer transition-colors disabled:opacity-60">
          {saving ? "Starting..." : `Start ${days} days without ${behaviour.trim() || "it"}`}
        </button>
      </Section>
    </Card>
  )
}

function Section({ step, children }: { step: { letter: string; title: string; blurb: string }; children: React.ReactNode }) {
  return (
    <div className="mt-6 pt-6 border-t border-black/5 dark:border-white/5">
      <div className="flex items-baseline gap-3">
        <span className="w-8 h-8 rounded-lg bg-teal-500/10 text-teal-700 dark:text-teal-300 font-bold flex items-center justify-center flex-shrink-0">{step.letter}</span>
        <div>
          <h3 className="font-semibold">{step.title}</h3>
          <p className="text-xs text-gray-500">{step.blurb}</p>
        </div>
      </div>
      <div className="mt-3 md:pl-11">{children}</div>
    </div>
  )
}

// ---------------------------------------------------------------- active plan

function ActivePlan({ plan, onSurf, onReset, onChanged, onQuickLog }: {
  plan: FocusPlan; onSurf: () => void; onReset: () => void; onChanged: () => void; onQuickLog: (acted: boolean, intensity: number, trigger?: string) => void
}) {
  const today = localToday()
  const todayCheckin = plan.checkins.find(c => c.date === today)
  const [urges, setUrges] = React.useState(todayCheckin?.urges ?? 0)
  const [gaveIn, setGaveIn] = React.useState(todayCheckin?.gaveIn ?? false)
  const [sleepOk, setSleepOk] = React.useState<boolean | null>(todayCheckin?.sleepOk ?? null)
  const [note, setNote] = React.useState(todayCheckin?.note ?? "")
  const [saving, setSaving] = React.useState(false)
  const [saved, setSaved] = React.useState(false)
  const progress = Math.min(100, ((plan.dayNumber - 1) / plan.abstinenceDays) * 100)

  const saveCheckin = async () => {
    setSaving(true)
    await fetch(`/api/focus/checkins?tz_offset=${tzOffset()}`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ date: today, urges, gaveIn, sleepOk, note: note.trim() }) }).catch(() => {})
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
    onChanged()
  }
  const patch = async (body: Record<string, unknown>) => {
    await fetch(`/api/focus/plans/${plan.id}?tz_offset=${tzOffset()}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(body) }).catch(() => {})
    onChanged()
  }

  return (
    <>
      <Card>
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-widest text-teal-600 dark:text-teal-400">Reset in progress</p>
            <h2 className="text-2xl font-serif font-bold mt-1">Without {plan.behaviour}</h2>
            <p className="text-sm text-gray-500 mt-1">
              {plan.finished ? `The ${plan.abstinenceDays}-day window is complete.` : `Day ${plan.dayNumber} of ${plan.abstinenceDays}, ${plan.daysLeft} to go.`}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={onSurf} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-sm font-medium cursor-pointer transition-colors"><Waves className="w-4 h-4" /> Surf an urge</button>
            <button onClick={onReset} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-black/10 dark:border-white/15 text-sm font-medium hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer transition-colors">3-minute reset</button>
          </div>
        </div>
        <div className="mt-5 h-2 rounded-full bg-black/5 dark:bg-white/10 overflow-hidden">
          <div className="h-full bg-teal-500 transition-all duration-700" style={{ width: `${progress}%` }} />
        </div>
        <div className="grid grid-cols-3 gap-3 mt-4">
          <Stat label="Clean streak" value={`${plan.cleanStreak}`} sub={plan.cleanStreak === 1 ? "day" : "days"} />
          <Stat label="Clean days" value={`${plan.cleanDays}`} sub={`of ${plan.checkedInDays} checked in`} />
          <Stat label="Urges surfed" value={`${plan.urges.surfed}`} sub={`of ${plan.urges.total} logged`} />
        </div>

        {plan.finished && (
          <div className="mt-5 p-4 rounded-xl bg-teal-500/10 border border-teal-500/20">
            <p className="text-sm font-medium flex items-center gap-2"><Check className="w-4 h-4 text-teal-600" /> You made it through the window.</p>
            <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">Lembke's advice for the end: notice what changed in your entries, then decide whether to extend or to bring the behaviour back on your own terms, with the rules kept.</p>
            <div className="flex flex-wrap gap-2 mt-3">
              {plan.abstinenceDays < 30 && (
                <button onClick={() => patch({ abstinenceDays: plan.abstinenceDays < 14 ? 14 : 30 })} className="px-4 py-2 rounded-xl bg-teal-600 text-white text-sm font-medium cursor-pointer">Extend to {plan.abstinenceDays < 14 ? 14 : 30} days</button>
              )}
              <button onClick={() => patch({ status: "completed" })} className="px-4 py-2 rounded-xl border border-black/10 dark:border-white/15 text-sm font-medium cursor-pointer">Finish the reset</button>
              <Link href="/insights" className="inline-flex items-center gap-1 px-4 py-2 text-sm text-teal-700 dark:text-teal-300 hover:underline">See the four-week trend <ArrowRight className="w-3.5 h-3.5" /></Link>
            </div>
          </div>
        )}
      </Card>

      <Card>
        <h3 className="font-semibold">Today's check-in</h3>
        <p className="text-xs text-gray-500 mt-1">Thirty seconds each evening. The entries carry the rest.</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
          <label className="text-sm">
            <span className="block text-xs uppercase tracking-widest text-gray-400 mb-1">Urges today</span>
            <input type="number" min={0} max={99} value={urges} onChange={e => setUrges(Math.max(0, Number(e.target.value) || 0))} className="w-full rounded-xl border border-black/10 dark:border-white/10 bg-transparent px-3 py-2 focus:outline-none focus:ring-2 focus:ring-teal-500/50" />
          </label>
          <div className="text-sm">
            <span className="block text-xs uppercase tracking-widest text-gray-400 mb-1">Did you give in?</span>
            <div className="flex gap-2">
              {[false, true].map(v => (
                <button key={String(v)} onClick={() => setGaveIn(v)} className={`flex-1 py-2 rounded-xl border cursor-pointer transition-colors ${gaveIn === v ? (v ? "bg-rose-500/15 border-rose-500/40 text-rose-700 dark:text-rose-300" : "bg-teal-600 border-teal-600 text-white") : "border-black/10 dark:border-white/15"}`}>{v ? "Yes" : "No"}</button>
              ))}
            </div>
          </div>
          <div className="text-sm">
            <span className="block text-xs uppercase tracking-widest text-gray-400 mb-1">Slept well?</span>
            <div className="flex gap-2">
              {[true, false].map(v => (
                <button key={String(v)} onClick={() => setSleepOk(v)} className={`flex-1 py-2 rounded-xl border cursor-pointer transition-colors ${sleepOk === v ? "bg-teal-600 border-teal-600 text-white" : "border-black/10 dark:border-white/15"}`}>{v ? "Yes" : "No"}</button>
              ))}
            </div>
          </div>
        </div>
        <textarea value={note} onChange={e => setNote(e.target.value)} rows={2} placeholder="One line, optional: what helped, what did not." className="mt-3 w-full rounded-xl border border-black/10 dark:border-white/10 bg-transparent p-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/50" />
        <div className="flex items-center gap-3 mt-3">
          <button onClick={saveCheckin} disabled={saving} className="px-5 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-sm font-medium cursor-pointer disabled:opacity-60">{saving ? "Saving..." : todayCheckin ? "Update check-in" : "Save check-in"}</button>
          {saved && <span className="text-sm text-teal-600 flex items-center gap-1"><Check className="w-4 h-4" /> saved</span>}
          <button onClick={() => onQuickLog(false, 3)} className="ml-auto text-xs text-gray-500 hover:text-teal-600 cursor-pointer" title="Log an urge that has already passed without surfing it">Log a passed urge</button>
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <h3 className="font-semibold">Your rules</h3>
          {plan.rules.length ? (
            <ul className="mt-3 space-y-2 text-sm">{plan.rules.map(r => <li key={r} className="flex gap-2"><Check className="w-4 h-4 text-teal-600 flex-shrink-0 mt-0.5" /> {r}</li>)}</ul>
          ) : <p className="text-sm text-gray-500 mt-2">No rules set.</p>}
          {plan.objectives && <p className="text-xs text-gray-500 mt-4"><span className="uppercase tracking-widest">It was doing:</span> {plan.objectives}</p>}
        </Card>
        <Card>
          <h3 className="font-semibold">Instead</h3>
          {plan.replacements.length ? (
            <ul className="mt-3 space-y-2 text-sm">{plan.replacements.map(r => <li key={r} className="flex gap-2"><RefreshCw className="w-4 h-4 text-teal-600 flex-shrink-0 mt-0.5" /> {r}</li>)}</ul>
          ) : <p className="text-sm text-gray-500 mt-2">No replacements chosen.</p>}
          {plan.urges.recent.length > 0 && (
            <div className="mt-4">
              <p className="text-xs uppercase tracking-widest text-gray-400 mb-2">Recent urges</p>
              <ul className="space-y-1 text-xs text-gray-600 dark:text-gray-300">
                {plan.urges.recent.slice(0, 5).map(u => (
                  <li key={u.id} className="flex items-center gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full ${u.acted ? "bg-rose-400" : "bg-teal-500"}`} />
                    {u.loggedAt ? new Date(u.loggedAt).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : ""}
                    {u.intensity ? ` · strength ${u.intensity}` : ""} · {u.acted ? "acted" : "surfed"}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>

      <p className="text-[11px] text-gray-400 text-center flex items-center justify-center gap-1">
        <Flame className="w-3 h-3" /> Structure after Anna Lembke's <em>Dopamine Nation</em> and Cameron Sepah's dopamine fasting protocol. The app reads behaviour in your writing; it does not measure dopamine.
      </p>
    </>
  )
}
