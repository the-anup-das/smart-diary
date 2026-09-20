import * as React from "react"
import { useRouter } from "next/navigation"
import { CheckCircle2, ShieldAlert, Sparkles, BrainCircuit, PenTool, Hash, GitMerge, ArrowRight, Wind, Timer, Activity } from "lucide-react"
import { getMoodTier, getSentimentStyle } from "@/lib/mood"
import { HelpfulnessVote } from "@/components/ui/HelpfulnessVote"
import { SupportCard } from "@/components/wellbeing/SupportCard"
import { BreathingExercise } from "@/components/wellbeing/BreathingExercise"
import { ThreeMinuteReset } from "@/components/calm/ThreeMinuteReset"
import { WellbeingRadar } from "@/components/insights/WellbeingRadar"
import { profileFromFeedback, hasProfile } from "@/lib/wellbeing"
import Link from "next/link"
import { Crosshair, Brain } from "lucide-react"
import { BUILDER_LABELS } from "@/lib/focus"

export function FeedbackDashboard({ feedback, preferences = {}, onClose, arrivalMood = null, onInsertTemplate, onAppendToEntry, onResetCompleted }: { feedback: any, preferences?: any, onClose?: () => void, arrivalMood?: number | null, onInsertTemplate?: (key: string) => void, onAppendToEntry?: (text: string) => void, onResetCompleted?: () => void }) {
  const router = useRouter()
  const [creatingDecision, setCreatingDecision] = React.useState(false)
  const [supportDismissed, setSupportDismissed] = React.useState(false)
  const [showReset, setShowReset] = React.useState(false)

  if (!feedback) return null;

  // Acute distress: lead with support, not analysis. The reflection stays one
  // tap away — never locked, never forced.
  if (feedback.distressFlag && !supportDismissed) {
    return (
      <div className="mt-8 max-w-4xl mx-auto w-full pb-20 px-2 lg:px-6 fade-in">
        <SupportCard
          region={preferences?.support_region || "international"}
          customHelpline={preferences?.support_custom || ""}
          onDismiss={() => setSupportDismissed(true)}
        />
      </div>
    )
  }

  const todayProfile = profileFromFeedback(feedback)

  const handleStartDecision = async () => {
    if (!feedback.detectedDecision) return
    setCreatingDecision(true)
    try {
      const res = await fetch('/api/decisions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: feedback.detectedDecision })
      })
      if (res.ok) {
        const newDecision = await res.json()
        router.push(`/decisions/${newDecision.id}`)
      }
    } catch (e) {
      console.error(e)
      setCreatingDecision(false)
    }
  }

  return (
    <div className="mt-8 space-y-6 fade-in max-w-4xl mx-auto w-full pb-20 px-2 lg:px-6 relative">
      
      {/* State Dismantling Action */}
      {feedback.model?.name && (
        <p className="text-[11px] text-gray-400 px-2 -mb-3" title={feedback.model.promptVersion ? `prompt ${feedback.model.promptVersion}` : undefined}>
          Analysed by {feedback.model.name}
          {feedback.model.provider === "local" ? " on your local server" : feedback.model.provider === "cloud" ? " in the cloud" : ""}
          {feedback.model.fallbackUsed ? ", after the local model failed" : ""}
        </p>
      )}
      {onClose && (
        <div className="flex justify-between items-end mb-2">
          <h2 className="text-2xl font-serif font-bold text-gray-900 dark:text-gray-100 px-2">AI Insights</h2>
          <button onClick={onClose} className="text-sm px-5 py-2 bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 rounded-full font-medium text-gray-600 dark:text-gray-300 transition-colors flex items-center space-x-2">
            <span>Close Analysis</span>
            <span className="text-xl leading-none">&times;</span>
          </button>
        </div>
      )}

      {/* Detected Decision CTA */}
      {!preferences?.hide_decisions && feedback.detectedDecision && (
        <div className="p-6 rounded-2xl bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/30 backdrop-blur-xl shadow-lg relative overflow-hidden group">
          <div className="absolute -right-10 -top-10 w-40 h-40 bg-indigo-500/10 rounded-full blur-3xl group-hover:bg-indigo-500/20 transition-all" />
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
            <div>
              <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 flex items-center">
                <GitMerge className="w-5 h-5 mr-2 text-indigo-500" />
                Looming Decision Detected
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-300 mt-1 max-w-md">
                "{feedback.detectedDecision}"
              </p>
              <p className="text-xs text-gray-500 mt-2">
                Our AI noticed you're struggling with this. Let's break it down logically.
              </p>
            </div>
            <button 
              onClick={handleStartDecision}
              disabled={creatingDecision}
              className="flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50 whitespace-nowrap flex-shrink-0"
            >
              {creatingDecision ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
              ) : null}
              <span>Resolve This Decision</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Overthinking Reset CTA (rumination detected by the energy analysis) */}
      {!preferences?.hide_calm_reset && ["moderate", "high"].includes(String(feedback.energyData?.rumination_level || "").toLowerCase()) && (
        <div className="p-6 rounded-2xl bg-gradient-to-r from-sky-500/10 to-teal-500/10 border border-sky-500/30 backdrop-blur-xl shadow-lg relative overflow-hidden group">
          <div className="absolute -right-10 -top-10 w-40 h-40 bg-sky-500/10 rounded-full blur-3xl group-hover:bg-sky-500/20 transition-all" />
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
            <div>
              <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 flex items-center">
                <Wind className="w-5 h-5 mr-2 text-sky-500" />
                Your mind is looping today
              </h3>
              {feedback.energyData?.rumination_coaching && (
                <p className="text-sm text-gray-600 dark:text-gray-300 mt-1 max-w-md">{feedback.energyData.rumination_coaching}</p>
              )}
              <p className="text-xs text-gray-500 mt-2">
                Three minutes: one of breathing, one of stillness, one of picturing today going calmly. Nothing to solve.
              </p>
            </div>
            <button
              onClick={() => setShowReset(true)}
              className="flex items-center space-x-2 px-5 py-2.5 bg-sky-600 text-white rounded-xl font-medium hover:bg-sky-700 transition-colors whitespace-nowrap flex-shrink-0 cursor-pointer"
            >
              <Timer className="w-4 h-4" />
              <span>Take a 3-minute reset</span>
            </button>
          </div>
        </div>
      )}
      <ThreeMinuteReset
        open={showReset}
        source="entry"
        onClose={() => setShowReset(false)}
        onCompleted={onResetCompleted}
        onAppendToEntry={onAppendToEntry}
        ruminationCoaching={feedback.energyData?.rumination_coaching}
      />

      {/* Stimulation spike: only when this entry mentions a compulsive habit with real cost */}
      {!preferences?.hide_focus && (feedback.stimulation?.load ?? 0) >= 2 && (
        <div className="p-5 rounded-2xl bg-gradient-to-r from-teal-500/10 to-emerald-500/10 border border-teal-500/30 backdrop-blur-xl shadow-lg">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 flex items-center">
                <Crosshair className="w-5 h-5 mr-2 text-teal-500" />
                A stimulation spike in today's entry
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-300 mt-1 max-w-lg">
                {(feedback.stimulation.behaviours || []).map((b: any) => b.behaviour).filter(Boolean).join(", ") || "A habit that gives a quick hit"}
                {feedback.stimulation.afterState && feedback.stimulation.afterState !== "none" ? `, followed by feeling ${feedback.stimulation.afterState}` : ""}
                {feedback.stimulation.displaced?.length ? `. It pushed aside: ${feedback.stimulation.displaced.slice(0, 3).join(", ")}` : ""}.
              </p>
              <p className="text-xs text-gray-500 mt-2">One entry is a data point, not a verdict. If it keeps showing up, the Focus Reset is a structured way out.</p>
            </div>
            <Link href="/focus" className="flex items-center space-x-2 px-5 py-2.5 bg-teal-600 text-white rounded-xl font-medium hover:bg-teal-700 transition-colors whitespace-nowrap flex-shrink-0">
              <span>Open Focus Reset</span>
            </Link>
          </div>
        </div>
      )}

      {/* Fog and passive consumption: only when this entry says so */}
      {!preferences?.hide_focus && (feedback.cognition?.brainRotLoad ?? 0) >= 2 && (
        <div className="p-5 rounded-2xl bg-gradient-to-r from-violet-500/10 to-indigo-500/10 border border-violet-500/30 backdrop-blur-xl shadow-lg">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 flex items-center">
                <Brain className="w-5 h-5 mr-2 text-violet-500" />
                Fog in today's entry
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-300 mt-1 max-w-lg">
                {feedback.cognition.attentionNote ? `"${String(feedback.cognition.attentionNote).replace(/[.\s]+$/, "")}". ` : ""}
                {feedback.cognition.shortFormVideo ? "Short-form video came up" : ""}
                {feedback.cognition.passiveConsumptionMinutes ? `${feedback.cognition.shortFormVideo ? ", with" : "You mentioned"} about ${feedback.cognition.passiveConsumptionMinutes} minutes of passive scrolling` : ""}
                {feedback.cognition.shortFormVideo || feedback.cognition.passiveConsumptionMinutes ? ". " : ""}
                {feedback.cognition.builders?.length ? `On the other side of the ledger: ${feedback.cognition.builders.map((b: string) => (BUILDER_LABELS[b] || b).toLowerCase()).join(", ")}.` : ""}
              </p>
              <p className="text-xs text-gray-500 mt-2">One foggy day is a day. If it keeps coming back, Mind fitness on the Focus page has a four-week guide.</p>
            </div>
            <Link href="/focus#mind" className="flex items-center space-x-2 px-5 py-2.5 bg-violet-600 text-white rounded-xl font-medium hover:bg-violet-700 transition-colors whitespace-nowrap flex-shrink-0">
              <span>Open Mind fitness</span>
            </Link>
          </div>
        </div>
      )}

      {/* Top Level Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {!preferences?.hide_mood && (
          <GlassCard>
            <div className="flex items-center space-x-3 mb-2">
              <Sparkles className="w-5 h-5 text-primary" />
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">Emotional Resonance</h3>
            </div>
            <div className="flex items-end justify-between">
              <div>
                <p className={`text-3xl font-bold ${getMoodTier(feedback.moodScore).color}`}>{getMoodTier(feedback.moodScore).label}</p>
                <p className="text-xs text-gray-400 font-mono mt-1">{feedback.moodScore}/10</p>
              </div>
              {(() => {
                const style = getSentimentStyle(feedback.sentiment)
                return (
                  <div className={`px-3 py-1.5 rounded-full ${style.bg} ${style.glow} border border-current/10`}>
                    <span className={`text-sm font-medium ${style.color}`}>{feedback.sentiment}</span>
                  </div>
                )
              })()}
            </div>
            <ProgressBar value={feedback.moodScore * 10} moodScore={feedback.moodScore} />
            {Array.isArray(feedback.emotionLabels) && feedback.emotionLabels.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 mt-4">
                <span className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold mr-1">Feelings named</span>
                {feedback.emotionLabels.map((label: string) => (
                  <span key={label} className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium border border-primary/20 capitalize">
                    {label}
                  </span>
                ))}
              </div>
            )}
            {arrivalMood != null && feedback.moodScore != null && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
                You arrived at {arrivalMood}/10 — your writing reads as {feedback.moodScore}/10.{" "}
                {feedback.moodScore > arrivalMood
                  ? "A little lighter for having written."
                  : feedback.moodScore === arrivalMood
                  ? "Steady — and showing up counts."
                  : "A heavy one. Putting it into words still counts."}
              </p>
            )}
        </GlassCard>
        )}

        {!preferences?.hide_grammar && (
          <GlassCard>
            <div className="flex items-center space-x-3 mb-2">
              <ShieldAlert className="w-5 h-5 text-blue-500" />
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">Linguistic Clarity</h3>
            </div>
            <div className="flex items-end justify-between">
              <p className="text-4xl font-bold text-gray-900 dark:text-gray-100">{feedback.grammarScore}<span className="text-xl text-gray-500">/10</span></p>
              {Array.isArray(feedback.grammarFixes) && feedback.grammarFixes.length > 0 ? (
                <button
                  onClick={() => document.getElementById("grammar-polish")?.scrollIntoView({ behavior: "smooth", block: "start" })}
                  title="Jump to the suggested fixes"
                  className="px-3 py-1 bg-black/5 dark:bg-white/5 hover:bg-primary/10 hover:text-primary rounded-full text-sm font-medium text-gray-600 dark:text-gray-300 transition-colors cursor-pointer underline-offset-2 hover:underline"
                >
                  {feedback.grammarFixes.length} {feedback.grammarFixes.length === 1 ? "fix" : "fixes"} ↓
                </button>
              ) : (
                <div className="px-3 py-1 bg-black/5 dark:bg-white/5 rounded-full text-sm font-medium text-gray-600 dark:text-gray-300">Perfect</div>
              )}
            </div>
            <ProgressBar value={feedback.grammarScore * 10} />
          </GlassCard>
        )}
      </div>

      {feedback.moodScore != null && feedback.moodScore <= 4 && !feedback.distressFlag && (
        <LowMoodSupport onInsertTemplate={onInsertTemplate} onCloseDashboard={onClose} />
      )}

      {/* Wellbeing Profile for this entry (period averages live on the Insights page) */}
      {!preferences?.hide_wellbeing && hasProfile(todayProfile) && (
        <GlassCard>
          <h3 className="font-semibold mb-1 text-gray-900 dark:text-gray-100 flex items-center"><Activity className="w-5 h-5 mr-2 text-primary" /> Today's Wellbeing Profile</h3>
          <p className="text-xs text-gray-500 mb-5">Six capacities from this entry on one scale, higher is better. Your averages over time are on the Insights page.</p>
          <WellbeingRadar axes={todayProfile} />
        </GlassCard>
      )}

      {/* Grammar Corrections */}
      {!preferences?.hide_grammar && Array.isArray(feedback.grammarFixes) && feedback.grammarFixes.length > 0 && (
        <GlassCard>
          <h3 id="grammar-polish" className="font-semibold mb-4 text-gray-900 dark:text-gray-100 flex items-center scroll-mt-28"><CheckCircle2 className="w-4 h-4 mr-2 text-green-500" /> Grammar Polish</h3>
          <div className="space-y-3">
            {feedback.grammarFixes.map((fix: any, i: number) => (
              <div key={i} className="p-3 rounded-lg bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5">
                <p className="text-sm line-through text-red-500/80 mb-1">{fix.original}</p>
                <p className="text-sm font-medium text-green-600 dark:text-green-400 mb-2">{fix.correction}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">{fix.explanation}</p>
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      {/* Cognitive Reframes */}
      {!preferences?.hide_reframes && Array.isArray(feedback.cognitiveReframes) && feedback.cognitiveReframes.length > 0 && (
        <GlassCard>
          <h3 className="font-semibold mb-4 text-gray-900 dark:text-gray-100 flex items-center"><BrainCircuit className="w-5 h-5 mr-2 text-primary" /> Cognitive Reframing</h3>
          <div className="space-y-4">
            {feedback.cognitiveReframes.map((item: any, i: number) => (
              <div key={i} className="p-4 rounded-xl border border-primary/20 bg-primary/5">
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-3 blockquote relative pl-4 border-l-2 border-primary/30 italic">
                  "{item.negativeThought}"
                </p>
                <div className="flex items-start">
                  <div className="mt-1 mr-3 text-xl">✨</div>
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100 leading-relaxed">
                    {item.reframe}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      {/* Open Loops */}
      {!preferences?.hide_open_loops && Array.isArray(feedback.openLoops) && feedback.openLoops.length > 0 && (
        <GlassCard>
          <h3 className="font-semibold mb-4 text-gray-900 dark:text-gray-100">Unresolved Open Loops</h3>
          <ul className="space-y-2">
            {feedback.openLoops.map((loop: string, i: number) => (
              <li key={i} className="flex items-start text-sm text-gray-700 dark:text-gray-300">
                <span className="mr-2 text-primary mt-0.5">•</span>
                <span>{loop}</span>
              </li>
            ))}
          </ul>
        </GlassCard>
      )}

      {/* Writing Perspective */}
      {feedback.selfFocusFeedback && (
        <GlassCard>
          <h3 className="font-semibold mb-4 text-gray-900 dark:text-gray-100 flex items-center"><PenTool className="w-5 h-5 mr-2 text-indigo-500" /> Writing Perspective</h3>
          <div className="p-4 rounded-xl border border-indigo-500/20 bg-indigo-500/5">
            <p className="text-sm text-gray-700 dark:text-gray-300">
              {feedback.selfFocusFeedback}
            </p>
          </div>
        </GlassCard>
      )}

      {/* Vocabulary Echoes */}
      {feedback.repetitiveWording && Array.isArray(feedback.repetitiveWording.words) && feedback.repetitiveWording.words.length > 0 && (
        <GlassCard>
          <h3 className="font-semibold mb-4 text-gray-900 dark:text-gray-100 flex items-center"><Hash className="w-5 h-5 mr-2 text-amber-500" /> Vocabulary Echoes</h3>
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {feedback.repetitiveWording.words.map((word: string, i: number) => (
                <span key={i} className="px-3 py-1.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 text-sm font-medium">
                  {word}
                </span>
              ))}
            </div>
            {feedback.repetitiveWording.feedback && (
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-2 italic">
                {feedback.repetitiveWording.feedback}
              </p>
            )}
          </div>
        </GlassCard>
      )}

      <HelpfulnessVote kind="reflection" className="justify-center py-2" />
    </div>
  )
}

/** Shown on low-mood days (never during acute distress — SupportCard owns that):
 *  a past bright spot to revisit, gentler templates, and a one-minute breather. */
function LowMoodSupport({ onInsertTemplate, onCloseDashboard }: { onInsertTemplate?: (key: string) => void, onCloseDashboard?: () => void }) {
  const [brightSpot, setBrightSpot] = React.useState<any>(null)
  const [breathing, setBreathing] = React.useState(false)

  React.useEffect(() => {
    fetch("/api/entries/bright-spot")
      .then(res => (res.ok ? res.json() : null))
      .then(data => { if (data?.found) setBrightSpot(data) })
      .catch(() => {})
  }, [])

  const suggestTemplate = (key: string) => {
    onInsertTemplate?.(key)
    onCloseDashboard?.()
  }

  return (
    <GlassCard>
      {breathing && <BreathingExercise onClose={() => setBreathing(false)} />}
      <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">Be extra gentle with yourself today</h3>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Heavy days happen. A few things that tend to help:
      </p>

      {brightSpot && (
        <button
          onClick={() => (window.location.href = `/history?date=${brightSpot.date}`)}
          className="w-full text-left p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 hover:border-amber-500/40 transition-colors cursor-pointer mb-3"
        >
          <span className="text-[10px] uppercase tracking-wide text-amber-600 dark:text-amber-400 font-semibold">
            A good day worth revisiting · {brightSpot.displayDate}
          </span>
          <p className="text-sm text-gray-700 dark:text-gray-300 mt-1.5 line-clamp-2 italic">"{brightSpot.snippet}…"</p>
        </button>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setBreathing(true)}
          className="px-3.5 py-2 rounded-xl bg-sky-500/10 text-sky-700 dark:text-sky-300 text-xs font-medium hover:bg-sky-500/20 transition-colors cursor-pointer"
        >
          60-second breather
        </button>
        {onInsertTemplate && (
          <>
            <button
              onClick={() => suggestTemplate("self-compassion")}
              className="px-3.5 py-2 rounded-xl bg-black/5 dark:bg-white/5 text-gray-600 dark:text-gray-300 text-xs font-medium hover:bg-black/10 dark:hover:bg-white/10 transition-colors cursor-pointer"
            >
              Add a Self-Compassion Break
            </button>
            <button
              onClick={() => suggestTemplate("worry-dump")}
              className="px-3.5 py-2 rounded-xl bg-black/5 dark:bg-white/5 text-gray-600 dark:text-gray-300 text-xs font-medium hover:bg-black/10 dark:hover:bg-white/10 transition-colors cursor-pointer"
            >
              Park worries in a Worry Dump
            </button>
          </>
        )}
      </div>
    </GlassCard>
  )
}

function GlassCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="p-5 lg:p-7 rounded-2xl bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-lg relative overflow-hidden transition-all duration-300">
      {children}
    </div>
  )
}

function ProgressBar({ value, moodScore }: { value: number, moodScore?: number }) {
  const tier = moodScore ? getMoodTier(moodScore) : null
  return (
    <div className="w-full h-2 bg-black/10 dark:bg-white/10 rounded-full overflow-hidden mt-4">
      <div 
        className="h-full transition-all duration-1000 ease-out rounded-full bg-gradient-to-r from-red-500 via-amber-500 to-emerald-500" 
        style={{ width: `${value}%` }} 
      />
    </div>
  )
}
