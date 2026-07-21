"use client"
import * as React from "react"
import { NotebookPen, HeartHandshake, Brain, Landmark, Wind, Sun, ListTodo, Feather } from "lucide-react"

interface Template {
  key: string
  name: string
  tagline: string
  tradition: string
  icon: React.ComponentType<{ className?: string }>
  html: string
}

/** Evidence-based guided structures, inserted as editable scaffolding. */
const TEMPLATES: Template[] = [
  {
    key: "three-good-things",
    name: "Three Good Things",
    tagline: "Notice what went right and why",
    tradition: "Positive psychology",
    icon: Sun,
    html:
      "<h2>Three good things</h2>" +
      "<p><strong>1.</strong> What went well: … <em>Why it happened:</em> …</p>" +
      "<p><strong>2.</strong> What went well: … <em>Why it happened:</em> …</p>" +
      "<p><strong>3.</strong> What went well: … <em>Why it happened:</em> …</p>",
  },
  {
    key: "cbt-thought-record",
    name: "Thought Record",
    tagline: "Untangle a difficult thought",
    tradition: "CBT",
    icon: Brain,
    html:
      "<h2>Thought record</h2>" +
      "<p><strong>Situation:</strong> What happened, just the facts…</p>" +
      "<p><strong>Automatic thought:</strong> What went through my mind…</p>" +
      "<p><strong>Feeling (0–100):</strong> …</p>" +
      "<p><strong>Evidence for the thought:</strong> …</p>" +
      "<p><strong>Evidence against it:</strong> …</p>" +
      "<p><strong>A more balanced thought:</strong> …</p>" +
      "<p><strong>Feeling now (0–100):</strong> …</p>",
  },
  {
    key: "stoic-evening",
    name: "Evening Review",
    tagline: "Seneca's three questions",
    tradition: "Stoic",
    icon: Landmark,
    html:
      "<h2>Evening review</h2>" +
      "<p><strong>What did I do well today?</strong> …</p>" +
      "<p><strong>Where did I stray from my values?</strong> …</p>" +
      "<p><strong>What will I do better tomorrow?</strong> …</p>",
  },
  {
    key: "morning-pages",
    name: "Morning Pages",
    tagline: "Unfiltered stream of thought",
    tradition: "Freewriting",
    icon: Feather,
    html:
      "<h2>Morning pages</h2>" +
      "<p><em>Write whatever crosses your mind, without stopping or editing. Nothing is too small or too messy.</em></p><p></p>",
  },
  {
    key: "five-minute",
    name: "Five-Minute Journal",
    tagline: "Quick morning setup",
    tradition: "Habit",
    icon: NotebookPen,
    html:
      "<h2>Five-minute journal</h2>" +
      "<p><strong>I'm grateful for…</strong></p><ul><li></li><li></li><li></li></ul>" +
      "<p><strong>What would make today great?</strong></p><ul><li></li><li></li><li></li></ul>" +
      "<p><strong>Daily affirmation:</strong> I am…</p>",
  },
  {
    key: "worry-dump",
    name: "Worry Dump",
    tagline: "Park your worries on paper",
    tradition: "Stimulus control",
    icon: ListTodo,
    html:
      "<h2>Worry dump</h2>" +
      "<p><em>List every worry circling in your head. Then mark each one: can I control it?</em></p>" +
      "<ul><li>Worry: … — <strong>In my control?</strong> yes/no — <strong>Next tiny step:</strong> …</li><li></li><li></li></ul>",
  },
  {
    key: "self-compassion",
    name: "Self-Compassion Break",
    tagline: "Talk to yourself like a friend",
    tradition: "Self-compassion",
    icon: HeartHandshake,
    html:
      "<h2>Self-compassion break</h2>" +
      "<p><strong>What's hurting right now:</strong> …</p>" +
      "<p><strong>Others feel this too:</strong> Who else might know this exact feeling? …</p>" +
      "<p><strong>What I'd tell a friend in my place:</strong> …</p>",
  },
]

export function TemplatePicker({ onInsert }: { onInsert: (html: string) => void }) {
  const [open, setOpen] = React.useState(false)

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        aria-label="Guided templates"
        aria-expanded={open}
        title="Guided templates — gratitude, CBT, Stoic review and more"
        className={`p-2 rounded-full transition-colors cursor-pointer ${open ? "bg-primary/10 text-primary" : "hover:bg-black/5 dark:hover:bg-white/5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"}`}
      >
        <NotebookPen className="w-4 h-4" />
      </button>

      {open && (
        <>
          <button
            className="fixed inset-0 z-40 cursor-default"
            aria-label="Close templates"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 top-full mt-2 z-50 w-80 max-w-[85vw] rounded-2xl border border-black/10 dark:border-white/15 bg-white dark:bg-zinc-900 shadow-2xl p-2 fade-in" role="menu">
            <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-gray-400">
              Guided templates
            </p>
            <div className="max-h-80 overflow-y-auto custom-scrollbar">
              {TEMPLATES.map(t => {
                const Icon = t.icon
                return (
                  <button
                    key={t.key}
                    role="menuitem"
                    onClick={() => { onInsert(t.html); setOpen(false) }}
                    className="w-full flex items-start gap-3 px-3 py-2.5 rounded-xl text-left hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer"
                  >
                    <Icon className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{t.name}</span>
                        <span className="text-[10px] text-gray-400 uppercase tracking-wide flex-shrink-0">{t.tradition}</span>
                      </span>
                      <span className="block text-xs text-gray-500 truncate">{t.tagline}</span>
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
