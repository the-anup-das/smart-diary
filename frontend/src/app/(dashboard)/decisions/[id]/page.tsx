"use client"
import * as React from "react"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, Sparkles, AlertCircle, Bot, Zap, Clock, TrendingUp, CheckCircle2 } from "lucide-react"

interface Decision {
  id: string
  topic: string
  status: "active" | "decided" | "archived"
  framework: string | null
  primary_option_id: string | null
  analysis_result: any | null
}

export default function DecisionCanvasPage() {
  const params = useParams()
  const router = useRouter()
  const [decision, setDecision] = React.useState<Decision | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [simulating, setSimulating] = React.useState(false)
  const [agentResult, setAgentResult] = React.useState<any>(null)
  const [selectedPath, setSelectedPath] = React.useState<string | null>(null)
  const [selectingPath, setSelectingPath] = React.useState(false)

  React.useEffect(() => {
    async function fetchDecision() {
      try {
        const res = await fetch(`/api/decisions/${params.id}`)
        if (res.ok) {
          const json = await res.json()
          setDecision(json)
          setSelectedPath(json.primary_option_id || null)
          // Load persisted analysis if it exists — no re-run needed
          if (json.analysis_result && json.framework) {
            setAgentResult({ framework: json.framework, data: json.analysis_result })
          }
        }
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetchDecision()
  }, [params.id])

  const handleSimulate = async () => {
    setSimulating(true)
    try {
      // Fetch the last 3 diary entries for real context
      let context = "The user has not written any diary entries yet."
      const ctxRes = await fetch('/api/entries/history')
      if (ctxRes.ok) {
        const ctxData = await ctxRes.json()
        const recentEntries = ctxData.entries?.slice(0, 3) || []
        if (recentEntries.length > 0) {
          context = recentEntries.map((e: any, i: number) =>
            `Entry ${i + 1} (${e.date}): ${e.preview}`
          ).join("\n\n")
        }
      }

      const res = await fetch(`/api/decisions/${params.id}/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context })
      })
      if (res.ok) {
        const json = await res.json()
        try {
          const parsedContent = JSON.parse(json.analysis_result)
          setAgentResult({ framework: json.framework_used, data: parsedContent })
          if (decision && json.framework_used) {
            setDecision({ ...decision, framework: json.framework_used })
          }
        } catch (e) {
          setAgentResult({ framework: json.framework_used, raw: json.analysis_result })
        }
      }
    } catch (e) {
      console.error(e)
    } finally {
      setSimulating(false)
    }
  }

  const handleChoosePath = async (pathName: string) => {
    setSelectingPath(true)
    try {
      const res = await fetch(`/api/decisions/${params.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ primary_option_id: pathName, status: pathName ? 'decided' : 'active' })
      })
      if (res.ok) {
        setSelectedPath(pathName)
        const updated = await res.json()
        setDecision(updated)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setSelectingPath(false)
    }
  }

  if (loading) return <div className="p-8 text-center animate-pulse text-gray-500">Loading Canvas...</div>
  if (!decision) return <div className="p-8 text-center text-red-500">Decision not found</div>

  return (
    <div className="flex flex-col w-full h-full min-h-screen pt-6 pb-16 px-4 lg:px-8 bg-gray-50/50 dark:bg-zinc-900/50">
      {/* Header */}
      <div className="flex items-center space-x-4 mb-8">
        <button onClick={() => router.back()} className="p-2 bg-black/5 dark:bg-white/5 rounded-full hover:bg-black/10 transition-colors">
          <ArrowLeft className="w-5 h-5 text-gray-600 dark:text-gray-300" />
        </button>
        <div>
          <div className="flex items-center space-x-2 flex-wrap gap-y-1">
            <span className="text-xs font-semibold text-indigo-500 uppercase tracking-wider">Decision Canvas</span>
            {decision.framework && (
              <span className="px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-600 text-[10px] font-bold tracking-widest uppercase">
                {decision.framework.replace(/_/g, ' ')}
              </span>
            )}
            {selectedPath && (
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 text-[10px] font-bold flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Path Chosen
              </span>
            )}
          </div>
          <h1 className="text-2xl lg:text-4xl font-serif font-bold text-gray-900 dark:text-gray-100 mt-1 line-clamp-2">
            {decision.topic}
          </h1>
          {selectedPath && (
            <p className="text-sm text-emerald-600 dark:text-emerald-400 mt-1 font-medium">→ {selectedPath}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Controls */}
        <div className="lg:col-span-1 space-y-6">
          <div className="p-6 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg">
            <div className="flex items-center space-x-2 mb-4">
              <Bot className="w-5 h-5 text-indigo-500" />
              <h2 className="font-semibold text-gray-900 dark:text-gray-100">AI Analyst</h2>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              I analyze your diary history and apply psychological frameworks to break this decision into clear paths.
            </p>

            <button
              onClick={handleSimulate}
              disabled={simulating}
              className="w-full flex items-center justify-center space-x-2 py-3 px-4 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white font-medium shadow-md shadow-indigo-500/20 hover:shadow-lg hover:shadow-indigo-500/40 transition-all disabled:opacity-50"
            >
              {simulating ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  <span>{agentResult ? "Re-run Analysis" : "Run Analysis"}</span>
                </>
              )}
            </button>
          </div>

          {/* Chosen Path Summary Card */}
          {selectedPath && (
            <div className="p-5 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 shadow-lg">
              <div className="flex items-center space-x-2 mb-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <h3 className="font-semibold text-emerald-800 dark:text-emerald-300 text-sm">Your Chosen Path</h3>
              </div>
              <p className="text-sm text-emerald-900 dark:text-emerald-200 font-medium">{selectedPath}</p>
              <button
                onClick={() => handleChoosePath("")}
                className="mt-3 text-xs text-emerald-600/70 hover:text-emerald-600 underline"
              >
                Change selection
              </button>
            </div>
          )}
        </div>

        {/* Right Column: Canvas */}
        <div className="lg:col-span-2 min-h-[500px]">
          {!agentResult && !simulating ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-10 rounded-2xl border-2 border-dashed border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.02]">
              <Zap className="w-12 h-12 text-gray-300 dark:text-gray-600 mb-4" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">Canvas is empty</h3>
              <p className="text-sm text-gray-500 max-w-md mt-2">
                Click 'Run Analysis' to have the agent break this decision into concrete paths across your key life areas.
              </p>
            </div>
          ) : simulating ? (
            <div className="h-full flex flex-col items-center justify-center p-10 rounded-2xl border border-black/5 dark:border-white/10 bg-white/50 dark:bg-black/20 backdrop-blur-xl shadow-lg">
              <div className="relative">
                <div className="absolute inset-0 bg-indigo-500 rounded-full blur-xl animate-pulse opacity-50" />
                <Bot className="w-12 h-12 text-indigo-500 relative z-10 animate-bounce" />
              </div>
              <h3 className="text-lg font-medium mt-6 text-gray-900 dark:text-gray-100">Agent is thinking...</h3>
              <p className="text-sm text-gray-500 mt-2">Searching your diary memories and loading the best framework.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Summary */}
              <div className="p-6 rounded-2xl bg-gradient-to-br from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 backdrop-blur-xl shadow-lg">
                <p className="text-lg font-serif text-indigo-900 dark:text-indigo-100 leading-relaxed italic">
                  "{agentResult.data?.summary || agentResult.raw}"
                </p>
              </div>

              {/* Weighted Matrix */}
              {agentResult.framework === "weighted_matrix" && agentResult.data?.matrix && (
                <div className="space-y-4">
                  {agentResult.data.matrix.map((row: any, i: number) => (
                    <PathCard
                      key={i}
                      name={row.option}
                      isSelected={selectedPath === row.option}
                      onChoose={() => handleChoosePath(row.option)}
                      disabled={selectingPath}
                    >
                      <div className="flex items-center justify-between mt-3 mb-4">
                        <span className="text-sm font-medium text-gray-500">Total Weighted Score</span>
                        <span className="text-3xl font-black text-indigo-600 dark:text-indigo-400">{row.total_score}</span>
                      </div>
                      {row.scores && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
                          {row.scores.map((s: any, j: number) => (
                            <div key={j} className="p-3.5 rounded-xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5">
                              <div className="flex justify-between items-center mb-2">
                                <span className="text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider">{s.domain?.replace(/_/g, ' ')}</span>
                                <div className="flex items-baseline gap-1">
                                  <span className="text-sm font-black text-indigo-500">{s.raw_score}</span>
                                  <span className="text-[10px] text-gray-400 font-medium">/5</span>
                                </div>
                              </div>
                              <div className="w-full h-1.5 bg-black/10 dark:bg-white/10 rounded-full mb-2.5 overflow-hidden">
                                <div className="h-full bg-indigo-500 rounded-full transition-all duration-1000" style={{ width: `${(s.raw_score / 5) * 100}%` }} />
                              </div>
                              <p className="text-xs text-gray-600 dark:text-gray-400 leading-snug">{s.justification}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </PathCard>
                  ))}
                </div>
              )}

              {/* 10/10/10 Rule */}
              {agentResult.framework === "10_10_10_rule" && agentResult.data?.options && (
                <div className="space-y-4">
                  {agentResult.data.options.map((opt: any, i: number) => (
                    <PathCard
                      key={i}
                      name={opt.name}
                      isSelected={selectedPath === opt.name}
                      onChoose={() => handleChoosePath(opt.name)}
                      disabled={selectingPath}
                    >
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
                        {["10_minutes", "10_months", "10_years"].map((horizon, hi) => {
                          const h = opt.horizons?.[horizon]
                          if (!h) return null
                          const labels = ["10 Minutes", "10 Months", "10 Years"]
                          return (
                            <div key={hi} className="p-3 rounded-xl bg-black/5 dark:bg-white/5">
                              <div className="text-xs font-semibold text-gray-500 flex items-center mb-2">
                                <Clock className="w-3 h-3 mr-1" />{labels[hi]}
                              </div>
                              <p className="text-xs font-medium text-gray-800 dark:text-gray-200 mb-2">{h.headline}</p>
                              {h.domains && (
                                <div className="space-y-2 mt-3">
                                  {Object.entries(h.domains).map(([domain, text]) => (
                                    <div key={domain} className="p-2 rounded-lg bg-white/50 dark:bg-black/20 border border-black/5 dark:border-white/5">
                                      <span className="block text-[10px] font-bold uppercase tracking-wider text-indigo-500/80 mb-1">{domain.replace(/_/g, ' ')}</span>
                                      <span className="text-xs text-gray-700 dark:text-gray-300 leading-snug block">{text as string}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                      {opt.emotional_truth && (
                        <p className="mt-3 text-xs text-amber-700 dark:text-amber-300 italic border-l-2 border-amber-400 pl-3">{opt.emotional_truth}</p>
                      )}
                    </PathCard>
                  ))}
                </div>
              )}

              {/* Second Order Thinking */}
              {agentResult.framework === "second_order_thinking" && agentResult.data?.options && (
                <div className="space-y-4">
                  {agentResult.data.options.map((opt: any, i: number) => (
                    <PathCard
                      key={i}
                      name={opt.name}
                      isSelected={selectedPath === opt.name}
                      onChoose={() => handleChoosePath(opt.name)}
                      disabled={selectingPath}
                    >
                      <div className="mt-4 space-y-3 relative">
                        <div className="absolute left-3.5 top-3 bottom-3 w-0.5 bg-black/10 dark:bg-white/10" />
                        <ConsequenceNode step="1" title="First Order Effect" data={opt.first_order} />
                        <ConsequenceNode step="2" title="Second Order Effect" data={opt.second_order} color="text-amber-500" bgColor="bg-amber-500/10" borderColor="border-amber-500/20" />
                        <ConsequenceNode step="3" title="Third Order Effect" data={opt.third_order} color="text-red-500" bgColor="bg-red-500/10" borderColor="border-red-500/20" />
                      </div>
                    </PathCard>
                  ))}
                  {agentResult.data.blindspots && (
                    <div className="p-5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-900 dark:text-red-200 text-sm">
                      <span className="font-bold flex items-center mb-2"><AlertCircle className="w-4 h-4 mr-2" /> Blindspots Detected</span>
                      <ul className="list-disc pl-5 space-y-1">
                        {agentResult.data.blindspots.map((b: string, i: number) => <li key={i}>{b}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Life Domain Analysis */}

              {/* Agent Recommendation */}
              {agentResult.data?.recommendation && (
                <div className="p-6 rounded-2xl bg-black dark:bg-white text-white dark:text-black shadow-xl">
                  <h3 className="font-semibold mb-2 flex items-center">
                    <TrendingUp className="w-5 h-5 mr-2" />
                    Agent Recommendation
                  </h3>
                  <p className="text-sm opacity-90">{agentResult.data.recommendation}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// --- Shared Path Card Wrapper ---
function PathCard({ name, isSelected, onChoose, disabled, children }: {
  name: string
  isSelected: boolean
  onChoose: () => void
  disabled: boolean
  children: React.ReactNode
}) {
  return (
    <div className={`p-6 rounded-2xl backdrop-blur-xl border shadow-lg transition-all ${
      isSelected
        ? "bg-emerald-500/10 border-emerald-500/30 ring-1 ring-emerald-500/30"
        : "bg-white/50 dark:bg-black/20 border-black/5 dark:border-white/10"
    }`}>
      <div className="flex items-start justify-between gap-4">
        <h3 className="font-bold text-lg text-gray-900 dark:text-gray-100">{name}</h3>
        <button
          onClick={onChoose}
          disabled={disabled}
          className={`shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all disabled:opacity-50 ${
            isSelected
              ? "bg-emerald-500 text-white shadow-md shadow-emerald-500/30"
              : "bg-black/5 dark:bg-white/10 text-gray-700 dark:text-gray-300 hover:bg-indigo-500/10 hover:text-indigo-600"
          }`}
        >
          {isSelected ? <><CheckCircle2 className="w-3.5 h-3.5" /> Chosen</> : "Choose This Path"}
        </button>
      </div>
      {children}
    </div>
  )
}

function HorizonCard({ title, data }: { title: string; data: any }) {
  if (!data) return null
  return (
    <div className="p-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5">
      <div className="text-xs font-semibold text-gray-500 uppercase flex items-center mb-2">
        <Clock className="w-3 h-3 mr-1.5" />{title}
      </div>
      <div className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-1">{data.state}</div>
      <div className="text-xs text-gray-500 leading-relaxed">{data.justification}</div>
    </div>
  )
}

function ConsequenceNode({ step, title, data, color = "text-indigo-500", bgColor = "bg-indigo-500/10", borderColor = "border-indigo-500/20" }: { step: string; title: string; data: any; color?: string; bgColor?: string; borderColor?: string }) {
  if (!data) return null
  return (
    <div className="flex items-start pl-10 relative">
      <div className={`absolute left-0 w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm bg-white dark:bg-zinc-800 shadow-sm border border-black/10 dark:border-white/10 ${color} z-10 shrink-0`}>
        {step}
      </div>
      <div className={`w-full p-4 rounded-xl ${bgColor} border ${borderColor}`}>
        <div className="flex items-center justify-between mb-2">
          <h4 className={`text-xs font-bold uppercase tracking-wider ${color}`}>{title}</h4>
          {data.domain && <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-white/50 dark:bg-black/20 ${color}`}>{data.domain.replace(/_/g, ' ')}</span>}
        </div>
        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{data.effect}</p>
        {data.justification && <p className="text-xs text-gray-600 dark:text-gray-400 mt-2 border-t border-black/5 dark:border-white/5 pt-2">{data.justification}</p>}
      </div>
    </div>
  )
}

function DomainCard({ title, data }: { title: string; data: any }) {
  if (!data) return null
  return (
    <div className="flex flex-col space-y-2 p-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5">
      <h4 className="text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider">{title}</h4>
      {data.positive && (
        <div className="flex items-start bg-green-500/10 p-2.5 rounded-lg border border-green-500/20">
          <span className="text-green-600 dark:text-green-400 font-bold mr-2 text-base leading-none shrink-0">+</span>
          <p className="text-xs text-green-800 dark:text-green-200 leading-snug">{data.positive}</p>
        </div>
      )}
      {data.negative && (
        <div className="flex items-start bg-red-500/10 p-2.5 rounded-lg border border-red-500/20">
          <span className="text-red-600 dark:text-red-400 font-bold mr-2 text-base leading-none shrink-0">-</span>
          <p className="text-xs text-red-800 dark:text-red-200 leading-snug">{data.negative}</p>
        </div>
      )}
    </div>
  )
}
