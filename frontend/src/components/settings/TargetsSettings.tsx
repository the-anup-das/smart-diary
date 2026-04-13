"use client"
import * as React from "react"
import { Button } from "@/components/ui/Button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"
import { Input } from "@/components/ui/Input"

export function TargetsSettings() {
  const [targets, setTargets] = React.useState<any>({
    daily_words: 200,
    max_daily_words: 1000,
    target_mood: 7,
    max_target_mood: 10,
    weekly_vocab: 10,
    max_weekly_vocab: 50,
    consistency_streak: 5,
    max_consistency_streak: 30,
    weekly_loops: 3,
    max_weekly_loops: 10,
    weekly_reframes: 3,
    max_weekly_reframes: 10,
    sentiment_diversity: 3,
    max_sentiment_diversity: 5
  })
  
  const [loading, setLoading] = React.useState(true)
  const [saving, setSaving] = React.useState(false)
  const [saveMessage, setSaveMessage] = React.useState("")

  React.useEffect(() => {
    fetch("/api/users/me")
      .then(res => res.json())
      .then(data => {
        if (!data.detail && data.preferences?.targets) {
           setTargets({ ...targets, ...data.preferences.targets })
        }
        setLoading(false)
      })
      .catch(err => {
        console.error(err)
        setLoading(false)
      })
  }, [])

  const updateTarget = (key: string, value: number) => {
    setTargets((t: any) => ({ ...t, [key]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveMessage("")
    try {
      const meRes = await fetch("/api/users/me")
      const meData = await meRes.json()
      const existingPrefs = meData.preferences || {}
      const newPrefs = { ...existingPrefs, targets }
      
      await fetch("/api/users/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preferences: newPrefs })
      })
      setSaveMessage("Targets updated successfully!")
      setTimeout(() => setSaveMessage(""), 3000)
    } catch (e) {
      setSaveMessage("Failed to update targets.")
      setTimeout(() => setSaveMessage(""), 3000)
    }
    setSaving(false)
  }

  if (loading) return <div className="text-gray-500 animate-pulse p-4">Loading core targets...</div>

  const TargetRow = ({ label, targetKey, maxKey, min = 1, step = 1, unit = "" }: any) => (
    <div className="space-y-3 p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.02] border border-black/5 dark:border-white/5 shadow-sm">
      <div className="flex justify-between items-center">
        <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">{label}</span>
        <div className="flex items-center space-x-3">
          <div className="flex flex-col items-end">
             <span className="text-[10px] text-gray-400 uppercase font-bold">Goal</span>
             <span className="text-primary font-bold">{targets[targetKey]}{unit}</span>
          </div>
          <div className="h-6 w-px bg-black/10 dark:bg-white/10" />
          <div className="flex flex-col items-start min-w-[60px]">
             <span className="text-[10px] text-gray-400 uppercase font-bold">Max</span>
             <input 
               type="number" 
               value={targets[maxKey]} 
               onChange={e => updateTarget(maxKey, parseInt(e.target.value) || 1)}
               className="w-full text-xs bg-transparent border-none p-0 focus:ring-0 text-gray-500 font-mono"
             />
          </div>
        </div>
      </div>
      <input 
        type="range" 
        min={min} 
        max={targets[maxKey]} 
        step={step} 
        value={targets[targetKey]} 
        onChange={e => updateTarget(targetKey, parseInt(e.target.value))} 
        className="w-full h-1.5 accent-primary bg-black/10 dark:bg-white/10 rounded-lg appearance-none cursor-pointer" 
      />
    </div>
  )

  return (
    <Card className="glass-panel overflow-hidden border-none shadow-2xl">
      <CardHeader className="bg-gradient-to-r from-primary/5 to-transparent pb-6 border-b border-black/5 dark:border-white/5">
        <CardTitle className="text-2xl font-serif">Goal Management</CardTitle>
        <p className="text-sm text-gray-500">Customize your limits and milestones. Adjust the "Max" values to expand the control ranges.</p>
      </CardHeader>
      <CardContent className="space-y-8 pt-8">
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <TargetRow label="Daily Word Count" targetKey="daily_words" maxKey="max_daily_words" min={50} step={50} />
          <TargetRow label="Target Minimum Mood" targetKey="target_mood" maxKey="max_target_mood" min={1} step={1} unit="/10" />
          <TargetRow label="Weekly New Vocabulary" targetKey="weekly_vocab" maxKey="max_weekly_vocab" min={1} step={1} />
          <TargetRow label="Consistency Streak" targetKey="consistency_streak" maxKey="max_consistency_streak" min={2} step={1} unit="d" />
        </div>
        
        <div className="pt-4 pb-2">
          <h3 className="text-sm font-bold text-gray-400 uppercase tracking-[0.2em] mb-4">AI-Driven Behavioral Goals</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <TargetRow label="Open Loops Resolved" targetKey="weekly_loops" maxKey="max_weekly_loops" />
            <TargetRow label="Cognitive Reframes" targetKey="weekly_reframes" maxKey="max_weekly_reframes" />
            <TargetRow label="Sentiment Diversity" targetKey="sentiment_diversity" maxKey="max_sentiment_diversity" />
          </div>
        </div>

        <div className="pt-6 border-t border-black/5 dark:border-white/5 flex justify-end items-center">
          {saveMessage && <span className={`text-sm mr-4 ${saveMessage.includes('Failed') ? 'text-red-500' : 'text-green-500'} animate-in slide-in-from-right-4`}>{saveMessage}</span>}
          <Button onClick={handleSave} disabled={saving} className="px-8 py-6 rounded-2xl shadow-lg hover:shadow-primary/20 transition-all font-bold">
            {saving ? "Updating..." : "Save Configuration"}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
