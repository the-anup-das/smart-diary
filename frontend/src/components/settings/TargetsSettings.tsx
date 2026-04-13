"use client"
import * as React from "react"
import { Button } from "@/components/ui/Button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"
import { Input } from "@/components/ui/Input"

export function TargetsSettings() {
  const [targets, setTargets] = React.useState<any>({
    daily_words: 200,
    target_mood: 7,
    weekly_vocab: 10,
    consistency_streak: 5,
    weekly_loops: 3,
    weekly_reframes: 3,
    sentiment_diversity: 3
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
      // First fetch existing preferences to not overwrite other settings
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

  return (
    <Card className="glass-panel">
      <CardHeader>
        <CardTitle className="text-xl">Goal Tracking</CardTitle>
        <p className="text-sm text-gray-500">Define personal milestones to track on your Insights dashboard.</p>
      </CardHeader>
      <CardContent className="space-y-6">
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-900 dark:text-gray-100 flex justify-between">
              <span>Daily Word Count</span>
              <span className="text-primary">{targets.daily_words}</span>
            </label>
            <input type="range" min="50" max="1000" step="50" value={targets.daily_words} onChange={e => updateTarget('daily_words', parseInt(e.target.value))} className="w-full accent-primary" />
            <p className="text-xs text-gray-500">Aim for a minimum number of words each day.</p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-900 dark:text-gray-100 flex justify-between">
              <span>Target Minimum Mood</span>
              <span className="text-primary">{targets.target_mood}/10</span>
            </label>
            <input type="range" min="1" max="10" step="1" value={targets.target_mood} onChange={e => updateTarget('target_mood', parseInt(e.target.value))} className="w-full accent-primary" />
            <p className="text-xs text-gray-500">The emotional baseline you want to maintain.</p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-900 dark:text-gray-100 flex justify-between">
              <span>Weekly New Vocabulary</span>
              <span className="text-primary">{targets.weekly_vocab}</span>
            </label>
            <input type="range" min="1" max="50" step="1" value={targets.weekly_vocab} onChange={e => updateTarget('weekly_vocab', parseInt(e.target.value))} className="w-full accent-primary" />
            <p className="text-xs text-gray-500">Number of new words discovered per week.</p>
          </div>
          
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-900 dark:text-gray-100 flex justify-between">
              <span>Consistency Streak (Days)</span>
              <span className="text-primary">{targets.consistency_streak}</span>
            </label>
            <input type="range" min="2" max="30" step="1" value={targets.consistency_streak} onChange={e => updateTarget('consistency_streak', parseInt(e.target.value))} className="w-full accent-primary" />
            <p className="text-xs text-gray-500">How many consecutive days you plan to write.</p>
          </div>
          
        </div>
        
        <h3 className="pt-6 pb-2 text-sm font-semibold text-gray-900 dark:text-gray-100 border-b border-black/5 dark:border-white/5">AI-Driven Behavioral Goals</h3>
        
        <div className="grid grid-cols-1 gap-6 pt-2">
           <div className="space-y-2">
            <label className="text-sm font-medium text-gray-900 dark:text-gray-100 flex justify-between">
              <span>Open Loops Resolved (Weekly)</span>
              <span className="text-primary">{targets.weekly_loops}</span>
            </label>
            <input type="range" min="1" max="10" step="1" value={targets.weekly_loops} onChange={e => updateTarget('weekly_loops', parseInt(e.target.value))} className="w-full md:w-1/2 accent-primary" />
            <p className="text-xs text-gray-500">Proactively clear out mental baggage tracked by the AI.</p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-900 dark:text-gray-100 flex justify-between">
              <span>Cognitive Reframes (Weekly)</span>
              <span className="text-primary">{targets.weekly_reframes}</span>
            </label>
            <input type="range" min="1" max="10" step="1" value={targets.weekly_reframes} onChange={e => updateTarget('weekly_reframes', parseInt(e.target.value))} className="w-full md:w-1/2 accent-primary" />
            <p className="text-xs text-gray-500">Write through anxieties to trigger positive reframing from the AI.</p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-900 dark:text-gray-100 flex justify-between">
              <span>Sentiment Diversity</span>
              <span className="text-primary">{targets.sentiment_diversity}</span>
            </label>
            <input type="range" min="1" max="5" step="1" value={targets.sentiment_diversity} onChange={e => updateTarget('sentiment_diversity', parseInt(e.target.value))} className="w-full md:w-1/2 accent-primary" />
            <p className="text-xs text-gray-500">Number of distinct core sentiments to hit in a week for emotional range.</p>
          </div>
        </div>

        <div className="pt-4 border-t border-black/5 dark:border-white/5 flex justify-end items-center">
          {saveMessage && <span className={`text-sm mr-4 ${saveMessage.includes('Failed') ? 'text-red-500' : 'text-green-500'} animate-in fade-in`}>{saveMessage}</span>}
          <Button onClick={handleSave} disabled={saving} className="px-6">
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
