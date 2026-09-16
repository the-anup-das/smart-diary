"use client"
import * as React from "react"
import { Brain, Check, ChevronDown, ChevronUp, BookOpen, Square, Sparkles } from "lucide-react"
import { BUILDERS, MIND_GUIDE_WEEKS, BRAIN_ROT_NOTES, GUIDE_DAYS, localToday, tzOffset, type MindSummary } from "@/lib/focus"

const ROT_COLOUR = ["transparent", "#c4b5fd", "#8b5cf6", "#5b21b6"]
const JSON_HEADERS = { "Content-Type": "application/json" }

function Card({ children, className = "", id }: { children: React.ReactNode; className?: string; id?: string }) {
  return <div id={id} className={`p-5 lg:p-7 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg ${className}`}>{children}</div>
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="p-3 rounded-xl bg-black/[0.03] dark:bg-white/5 text-center">
      <p className="text-[10px] uppercase tracking-widest text-gray-400">{label}</p>
      <p className="text-xl font-bold mt-1">{value}</p>
      <p className="text-[11px] text-gray-500">{sub}</p>
    </div>
  )
}

/**
 * Mind fitness: what the entries say about fog, attention and passive consumption, the ten
 * activities that build a sharper mind, and a four-week guide. Rendered by the Focus page only
 * while the entries carry a signal or the guide is running.
 */
export function MindPanel({ mind, onChanged }: { mind: MindSummary; onChanged: () => void }) {
  const today = localToday()
  const todayDay = mind.days.find(d => d.date === today)
  const [busy, setBusy] = React.useState<string | null>(null)
  const [showNotes, setShowNotes] = React.useState(false)
  const [showWhy, setShowWhy] = React.useState(false)
  const [openWeek, setOpenWeek] = React.useState<number | null>(null)
  const [guideBusy, setGuideBusy] = React.useState(false)
  const guide = mind.guide
  const currentWeek = guide && !guide.finished ? MIND_GUIDE_WEEKS[Math.min(4, Math.max(1, guide.week)) - 1] : null
  const dayWord = (n: number) => (n === 1 ? "day" : "days")

  const toggleBuilder = async (key: string) => {
    if (busy) return
    const done = !todayDay?.manual.includes(key)
    setBusy(key)
    await fetch(`/api/focus/mind/builders?tz_offset=${tzOffset()}`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ date: today, builder: key, done }) }).catch(() => {})
    setBusy(null)
    onChanged()
  }
  const setGuide = async (action: "start" | "stop") => {
    setGuideBusy(true)
    await fetch(`/api/focus/mind/guide?tz_offset=${tzOffset()}`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ action }) }).catch(() => {})
    setGuideBusy(false)
    onChanged()
  }

  return (
    <>
      <Card id="mind">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-violet-500/10 rounded-xl text-violet-600 dark:text-violet-400"><Brain className="w-5 h-5" /></div>
          <div className="min-w-0">
            <h2 className="text-xl font-semibold">Mind fitness</h2>
            <p className="text-sm text-gray-500 mt-0.5">Fog, attention and passive consumption, read from your entries over the last four weeks. Shown only while there is something to work on.</p>
          </div>
        </div>

        <div className="grid grid-cols-14 gap-1.5 mt-5" aria-label="Last four weeks, fog and passive consumption by day">
          {mind.days.map(d => (
            <div key={d.date}
              title={`${d.date}: ${d.analysed ? (d.rot ? `fog level ${d.rot}` : "clear") : "not reflected"}${d.shortForm ? ", short-form video" : ""}${d.minutes ? `, ${d.minutes} min passive` : ""}${d.builders.length ? `; built: ${d.builders.join(", ")}` : ""}`}
              className={`aspect-square rounded-[3px] relative ${d.analysed ? "" : "border border-dashed border-black/10 dark:border-white/15"}`}
              style={{ backgroundColor: d.rot ? ROT_COLOUR[Math.min(3, d.rot)] : d.analysed ? "rgba(156,163,175,0.25)" : "transparent", opacity: 0.9 }}>
              {d.builders.length > 0 && <span className="absolute inset-x-0 bottom-0 h-1 bg-emerald-400 rounded-b-[3px]" />}
            </div>
          ))}
        </div>
        <p className="text-[11px] text-gray-400 mt-1.5">Violet: fog or passive consumption, darker is heavier. Green edge: a builder happened that day.</p>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
          <Stat label="Fog or focus trouble" value={`${mind.fogDays}`} sub={`${dayWord(mind.fogDays)}, ${mind.recentFogDays} in the last two weeks`} />
          <Stat label="Short-form video" value={`${mind.shortFormDays}`} sub={dayWord(mind.shortFormDays)} />
          <Stat label="Passive scrolling" value={mind.avgMinutes != null ? `~${mind.avgMinutes} min` : "not timed"} sub={mind.avgMinutes != null ? "per day it was mentioned" : "write the minutes down"} />
          <Stat label="Builder days" value={`${mind.weekBuilderDays}`} sub="of the last 7" />
        </div>

        {mind.notes.length > 0 && (
          <p className="text-sm text-gray-600 dark:text-gray-300 mt-4">
            In your words: <span className="italic">{mind.notes.slice(-3).join("; ")}</span>.
          </p>
        )}

        <button onClick={() => setShowNotes(v => !v)} className="mt-4 text-xs text-violet-700 dark:text-violet-300 flex items-center gap-1 cursor-pointer hover:underline" aria-expanded={showNotes}>
          {showNotes ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />} What brain rot is, and what it is not
        </button>
        {showNotes && (
          <div className="mt-2 space-y-2 text-sm text-gray-600 dark:text-gray-300 border-l-2 border-violet-500/30 pl-3">
            {BRAIN_ROT_NOTES.map((n, i) => <p key={i}>{n}</p>)}
          </div>
        )}
      </Card>

      <Card>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="font-semibold">Today&apos;s builders</h3>
            <p className="text-xs text-gray-500 mt-1">Ten things that build a sharper mind. Entries count on their own; tick the rest.</p>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-2xl font-bold text-violet-600 dark:text-violet-400">{mind.weekScore}%</p>
            <p className="text-[10px] uppercase tracking-widest text-gray-400">of this week&apos;s targets</p>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-4">
          {BUILDERS.map(b => {
            const done = !!todayDay?.builders.includes(b.key)
            const fromEntry = done && !todayDay?.manual.includes(b.key)
            return (
              <button key={b.key} onClick={() => !fromEntry && toggleBuilder(b.key)} disabled={fromEntry || busy === b.key} aria-pressed={done}
                title={fromEntry ? "Counted from today's entry" : b.example}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-sm text-left cursor-pointer transition-colors disabled:cursor-default ${done ? "bg-violet-600 border-violet-600 text-white" : "border-black/10 dark:border-white/15 hover:border-violet-500/50"}`}>
                {done ? <Check className="w-4 h-4 flex-shrink-0" /> : <Square className="w-4 h-4 flex-shrink-0 opacity-40" />}
                <span className="min-w-0">
                  <span className="block leading-tight">{b.label}</span>
                  {fromEntry && <span className="block text-[10px] opacity-75">from today&apos;s entry</span>}
                </span>
              </button>
            )
          })}
        </div>

        <div className="mt-5 space-y-2">
          {BUILDERS.map(b => {
            const s = mind.builders[b.key] || { weekDays: 0, monthDays: 0, target: b.target }
            const pct = Math.min(100, (s.weekDays / Math.max(1, s.target)) * 100)
            return (
              <div key={b.key} className="flex items-center gap-3 text-sm">
                <span className="w-36 md:w-44 flex-shrink-0 truncate text-gray-600 dark:text-gray-300" title={b.why}>{b.label}</span>
                <div className="flex-1 h-2 rounded-full bg-black/5 dark:bg-white/10 overflow-hidden">
                  <div className={`h-full transition-all duration-500 ${s.weekDays >= s.target ? "bg-emerald-500" : "bg-violet-500"}`} style={{ width: `${pct}%` }} />
                </div>
                <span className="w-16 text-right font-mono text-xs text-gray-500">{s.weekDays} of {s.target}</span>
              </div>
            )
          })}
        </div>
        <button onClick={() => setShowWhy(v => !v)} className="mt-4 text-xs text-violet-700 dark:text-violet-300 flex items-center gap-1 cursor-pointer hover:underline" aria-expanded={showWhy}>
          {showWhy ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />} Why these ten
        </button>
        {showWhy && (
          <ul className="mt-2 space-y-1.5 text-sm text-gray-600 dark:text-gray-300 border-l-2 border-violet-500/30 pl-3">
            {BUILDERS.map(b => <li key={b.key}><span className="font-medium text-gray-800 dark:text-gray-100">{b.label}.</span> {b.why} <span className="text-gray-400">{b.example}.</span></li>)}
          </ul>
        )}
      </Card>

      <Card>
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div>
            <h3 className="font-semibold flex items-center gap-2"><BookOpen className="w-4 h-4 text-violet-500" /> Four-week guide: sharpen your mind</h3>
            <p className="text-xs text-gray-500 mt-1">
              {guide
                ? guide.finished ? "Four weeks complete." : `Day ${guide.day} of ${GUIDE_DAYS}, week ${guide.week}: ${currentWeek?.title}.`
                : "One theme a week: subtract, rebuild, feed, keep. Four practices each. All of them things to do, none of them things to buy."}
            </p>
          </div>
          {guide ? (
            <div className="flex gap-2 flex-shrink-0">
              {guide.finished && (
                <button onClick={() => setGuide("start")} disabled={guideBusy} className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium cursor-pointer disabled:opacity-60">Run it again</button>
              )}
              <button onClick={() => setGuide("stop")} disabled={guideBusy} className="px-4 py-2 rounded-xl border border-black/10 dark:border-white/15 text-sm font-medium hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer disabled:opacity-60">
                {guide.finished ? "Close the guide" : "Stop the guide"}
              </button>
            </div>
          ) : (
            <button onClick={() => setGuide("start")} disabled={guideBusy} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium cursor-pointer disabled:opacity-60 flex-shrink-0">
              <Sparkles className="w-4 h-4" /> Start the four-week guide
            </button>
          )}
        </div>

        {guide && (
          <div className="mt-4 h-2 rounded-full bg-black/5 dark:bg-white/10 overflow-hidden">
            <div className="h-full bg-violet-500 transition-all duration-700" style={{ width: `${Math.min(100, ((Math.min(guide.day, GUIDE_DAYS + 1) - 1) / GUIDE_DAYS) * 100)}%` }} />
          </div>
        )}

        {guide?.finished && (
          <div className="mt-4 p-4 rounded-xl bg-violet-500/10 border border-violet-500/20 text-sm">
            <p className="font-medium flex items-center gap-2"><Check className="w-4 h-4 text-violet-600" /> You ran the four weeks.</p>
            <p className="text-gray-600 dark:text-gray-300 mt-1">
              Fog or focus trouble showed up on {mind.fogDays} of the last 28 {dayWord(mind.fogDays)}. Read the entries from the first week next to this week&apos;s, keep the builders that moved the needle, and write the rules down while they are fresh.
            </p>
          </div>
        )}

        {currentWeek && <WeekBlock week={currentWeek} current />}

        <div className="mt-4 divide-y divide-black/5 dark:divide-white/5 border-t border-black/5 dark:border-white/5">
          {MIND_GUIDE_WEEKS.filter(w => w.week !== currentWeek?.week).map(w => (
            <div key={w.week}>
              <button onClick={() => setOpenWeek(openWeek === w.week ? null : w.week)} aria-expanded={openWeek === w.week}
                className="w-full flex items-center justify-between py-3 text-left text-sm cursor-pointer">
                <span><span className="text-gray-400 font-mono text-xs mr-2">Week {w.week}</span><span className="font-medium">{w.title}</span> <span className="text-gray-500">· {w.theme}</span></span>
                {openWeek === w.week ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
              </button>
              {openWeek === w.week && <div className="pb-4"><WeekBlock week={w} /></div>}
            </div>
          ))}
        </div>
      </Card>

      <p className="text-[11px] text-gray-400 text-center">
        The app reads what you write about your attention; it does not test your brain. Fog that is persistent, heavy or new is a conversation for a doctor.
      </p>
    </>
  )
}

function WeekBlock({ week, current = false }: { week: (typeof MIND_GUIDE_WEEKS)[number]; current?: boolean }) {
  return (
    <div className={current ? "mt-4 p-4 rounded-xl bg-violet-500/5 border border-violet-500/20" : ""}>
      {current && <p className="text-xs uppercase tracking-widest text-violet-600 dark:text-violet-400">This week · {week.title}</p>}
      <p className={`text-sm ${current ? "mt-1 font-medium" : "text-gray-600 dark:text-gray-300"}`}>{week.theme}</p>
      <p className="text-sm text-gray-600 dark:text-gray-300 mt-2">{week.why}</p>
      <ul className="mt-3 space-y-2 text-sm">
        {week.practices.map(p => <li key={p} className="flex gap-2"><Check className="w-4 h-4 text-violet-500 flex-shrink-0 mt-0.5" /> {p}</li>)}
      </ul>
      <p className="text-sm text-gray-500 mt-3">Ask your entry: <span className="italic">{week.prompt}</span></p>
    </div>
  )
}
