"use client"
import * as React from "react"
import { GitMerge, Plus, ArrowRight, Activity, CheckCircle2, Archive, Sparkles } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"

interface DecisionData {
  id: string
  topic: string
  status: "active" | "decided" | "archived"
  framework: string | null
  primary_option_id: string | null
  created_at: string
}

export default function DecisionsLedgerPage() {
  const router = useRouter()
  const [decisions, setDecisions] = React.useState<DecisionData[]>([])
  const [loading, setLoading] = React.useState(true)
  const [creating, setCreating] = React.useState(false)
  const [showModal, setShowModal] = React.useState(false)
  const [topic, setTopic] = React.useState("")
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  React.useEffect(() => {
    async function fetchDecisions() {
      try {
        const res = await fetch('/api/decisions')
        if (res.ok) {
          const json = await res.json()
          setDecisions(json)
        }
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetchDecisions()
  }, [])

  // Focus textarea when modal opens
  React.useEffect(() => {
    if (showModal) setTimeout(() => textareaRef.current?.focus(), 100)
  }, [showModal])

  const handleNewDecision = async () => {
    if (!topic.trim()) return
    setCreating(true)
    try {
      const res = await fetch('/api/decisions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: topic.trim() })
      })
      if (res.ok) {
        const data = await res.json()
        router.push(`/decisions/${data.id}`)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setCreating(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleNewDecision() }
    if (e.key === "Escape") { setShowModal(false); setTopic("") }
  }

  const activeDecisions = decisions.filter(d => d.status === "active")
  const decidedDecisions = decisions.filter(d => d.status === "decided")
  const archivedDecisions = decisions.filter(d => d.status === "archived")

  return (
    <div className="flex flex-col w-full pt-6 pb-16 fade-in px-2 lg:px-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-indigo-500/10 text-indigo-500 rounded-xl">
            <GitMerge className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-3xl font-serif font-bold tracking-tight text-gray-900 dark:text-gray-100">
              Decision Junction
            </h1>
            <p className="text-sm text-gray-500 mt-1">Map, simulate, and resolve your life choices.</p>
          </div>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-black dark:bg-white text-white dark:text-black rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
        >
          <Plus className="w-4 h-4" />
          <span>New Decision</span>
        </button>
      </div>

      {loading ? (
        <div className="space-y-4 animate-pulse">
          <div className="h-32 rounded-2xl bg-black/5 dark:bg-white/5" />
          <div className="h-32 rounded-2xl bg-black/5 dark:bg-white/5" />
        </div>
      ) : (
        <div className="space-y-12">
          {/* Deciding — still in analysis */}
          <Section title="Deciding" icon={Activity} count={activeDecisions.length} color="text-indigo-500">
            {activeDecisions.length === 0 ? (
              <EmptyState />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {activeDecisions.map(d => (
                  <DecisionCard key={d.id} decision={d} />
                ))}
              </div>
            )}
          </Section>

          {/* Decision Made */}
          <Section title="Decision Made" icon={CheckCircle2} count={decidedDecisions.length} color="text-emerald-500">
            {decidedDecisions.length === 0 ? (
              <p className="text-sm text-gray-500">No decisions made yet. Analyze a decision and choose a path.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {decidedDecisions.map(d => (
                  <DecisionCard key={d.id} decision={d} />
                ))}
              </div>
            )}
          </Section>

          {/* Archived */}
          <Section title="Archived" icon={Archive} count={archivedDecisions.length} color="text-gray-400">
            {archivedDecisions.length === 0 ? (
              <p className="text-sm text-gray-500">No archived decisions.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {archivedDecisions.map(d => (
                  <DecisionCard key={d.id} decision={d} />
                ))}
              </div>
            )}
          </Section>
        </div>
      )}

      {/* New Decision Modal */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
          onClick={(e) => { if (e.target === e.currentTarget) { setShowModal(false); setTopic("") } }}
        >
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />

          {/* Sheet */}
          <div className="relative w-full max-w-lg bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl border border-black/10 dark:border-white/10 p-6 space-y-5">
            <div>
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">What decision are you wrestling with?</h2>
              <p className="text-sm text-gray-500 mt-1">Be specific — the more context you give, the better the analysis.</p>
            </div>

            <textarea
              ref={textareaRef}
              value={topic}
              onChange={e => setTopic(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. Should I quit my job and start a business? Should I move cities for this relationship?"
              rows={4}
              className="w-full p-4 text-sm rounded-xl bg-black/5 dark:bg-white/5 border border-transparent focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none resize-none transition-all text-gray-900 dark:text-gray-100 placeholder:text-gray-400"
            />

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => { setShowModal(false); setTopic("") }}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleNewDecision}
                disabled={creating || !topic.trim()}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-semibold shadow-md shadow-indigo-500/20 hover:shadow-lg hover:shadow-indigo-500/30 transition-all disabled:opacity-50"
              >
                {creating ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <GitMerge className="w-4 h-4" />
                )}
                {creating ? "Opening Canvas..." : "Open Decision Canvas"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Section({ title, icon: Icon, count, color, children }: {
  title: string
  icon: any
  count: number
  color: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center space-x-2 border-b border-black/5 dark:border-white/5 pb-2">
        <Icon className={`w-5 h-5 ${color}`} />
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{title}</h2>
        <span className="px-2 py-0.5 rounded-full bg-black/5 dark:bg-white/5 text-xs font-medium text-gray-500">
          {count}
        </span>
      </div>
      {children}
    </div>
  )
}

function DecisionCard({ decision }: { decision: DecisionData }) {
  const dateLabel = new Date(decision.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

  const statusConfig = {
    active: { label: "Deciding", color: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400" },
    decided: { label: "Decision Made", color: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
    archived: { label: "Archived", color: "bg-gray-500/10 text-gray-500" },
  }
  const statusStyle = statusConfig[decision.status] ?? statusConfig.active

  return (
    <Link
      href={`/decisions/${decision.id}`}
      className="group block p-5 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 hover:border-indigo-500/30 transition-all hover:shadow-lg relative overflow-hidden"
    >
      <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 rounded-full blur-3xl -mr-10 -mt-10 group-hover:bg-indigo-500/10 transition-colors" />

      <div className="flex justify-between items-start mb-3 relative z-10">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 line-clamp-2 pr-4">{decision.topic}</h3>
        <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-indigo-500 transition-colors flex-shrink-0 mt-1" />
      </div>

      {decision.primary_option_id && (
        <p className="text-xs text-emerald-600 dark:text-emerald-400 mb-2 relative z-10 flex items-center gap-1">
          <CheckCircle2 className="w-3 h-3" />
          {decision.primary_option_id}
        </p>
      )}

      <div className="flex items-center space-x-2 text-xs relative z-10 flex-wrap gap-y-1">
        <span className="text-gray-500 font-mono">{dateLabel}</span>
        <span className={`px-2 py-0.5 rounded-md font-medium ${statusStyle.color}`}>{statusStyle.label}</span>
        {decision.framework && (
          <span className="px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 font-medium capitalize flex items-center">
            <Sparkles className="w-3 h-3 mr-1" />
            {decision.framework.replace(/_/g, ' ')}
          </span>
        )}
      </div>
    </Link>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center p-10 text-center rounded-2xl border border-dashed border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.02]">
      <GitMerge className="w-10 h-10 text-gray-300 dark:text-gray-600 mb-3" />
      <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">No active decisions</h3>
      <p className="text-xs text-gray-500 max-w-sm mt-1">
        When the AI detects you struggling with a choice in your journal, it will appear here for deep analysis.
      </p>
    </div>
  )
}
