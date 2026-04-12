import * as React from "react"
import { CheckCircle2, ShieldAlert, Sparkles, BrainCircuit } from "lucide-react"
import { getMoodTier, getSentimentStyle } from "@/lib/mood"

export function FeedbackDashboard({ feedback, onClose }: { feedback: any, onClose?: () => void }) {
  if (!feedback) return null;

  return (
    <div className="mt-8 space-y-6 fade-in max-w-4xl mx-auto w-full pb-20 px-2 lg:px-6 relative">
      
      {/* State Dismantling Action */}
      {onClose && (
        <div className="flex justify-between items-end mb-2">
          <h2 className="text-2xl font-serif font-bold text-gray-900 dark:text-gray-100 px-2">AI Insights</h2>
          <button onClick={onClose} className="text-sm px-5 py-2 bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 rounded-full font-medium text-gray-600 dark:text-gray-300 transition-colors flex items-center space-x-2">
            <span>Close Analysis</span>
            <span className="text-xl leading-none">&times;</span>
          </button>
        </div>
      )}

      {/* Top Level Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
        </GlassCard>

        <GlassCard>
            <div className="flex items-center space-x-3 mb-2">
              <ShieldAlert className="w-5 h-5 text-blue-500" />
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">Linguistic Clarity</h3>
            </div>
            <div className="flex items-end justify-between">
              <p className="text-4xl font-bold text-gray-900 dark:text-gray-100">{feedback.grammarScore}<span className="text-xl text-gray-500">/10</span></p>
              <div className="px-3 py-1 bg-black/5 dark:bg-white/5 rounded-full text-sm font-medium text-gray-600 dark:text-gray-300">
                {Array.isArray(feedback.grammarFixes) && feedback.grammarFixes.length === 0 ? "Perfect" : `${feedback.grammarFixes?.length || 0} Fixes`}
              </div>
            </div>
            <ProgressBar value={feedback.grammarScore * 10} />
        </GlassCard>
      </div>

      {/* Grammar Corrections */}
      {Array.isArray(feedback.grammarFixes) && feedback.grammarFixes.length > 0 && (
        <GlassCard>
          <h3 className="font-semibold mb-4 text-gray-900 dark:text-gray-100 flex items-center"><CheckCircle2 className="w-4 h-4 mr-2 text-green-500" /> Grammar Polish</h3>
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
      {Array.isArray(feedback.cognitiveReframes) && feedback.cognitiveReframes.length > 0 && (
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
      {Array.isArray(feedback.openLoops) && feedback.openLoops.length > 0 && (
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
    </div>
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
