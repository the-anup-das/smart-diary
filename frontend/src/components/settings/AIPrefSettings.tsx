"use client"
import * as React from "react"
import { Button } from "@/components/ui/Button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"
import { ToggleSwitch } from "@/components/ui/ToggleSwitch"


export function AIPrefSettings() {
  const [prefs, setPrefs] = React.useState<any>(null)
  const [loading, setLoading] = React.useState(true)
  const [saving, setSaving] = React.useState(false)
  const [saveMessage, setSaveMessage] = React.useState("")

  React.useEffect(() => {
    fetch("/api/users/me")
      .then(res => res.json())
      .then(data => {
        if (!data.detail) {
           setPrefs(data.preferences || {})
        }
        setLoading(false)
      })
      .catch(err => {
        console.error(err)
        setLoading(false)
      })
  }, [])

  const updatePref = (key: string, value: any) => {
    setPrefs((p: any) => ({ ...p, [key]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveMessage("")
    try {
      await fetch("/api/users/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preferences: prefs })
      })
      setSaveMessage("Preferences updated successfully!")
      setTimeout(() => setSaveMessage(""), 3000)
    } catch (e) {
      setSaveMessage("Failed to update preferences.")
      setTimeout(() => setSaveMessage(""), 3000)
    }
    setSaving(false)
  }

  if (loading) return <div className="text-gray-500 animate-pulse p-4">Loading preferences...</div>

  return (
    <Card className="glass-panel">
      <CardHeader>
        <CardTitle className="text-xl">AI Engine Configuration</CardTitle>
        <p className="text-sm text-gray-500">Fine-tune how the AI analyzes your journal.</p>
      </CardHeader>
      <CardContent className="space-y-6">
        
        <div className="space-y-1">
           <ToggleSwitch 
              label="Pause AI Analysis" 
              description="Temporarily skip OpenAI processing to save entries 100% locally." 
              checked={!!prefs?.pause_ai} 
              onChange={(val: any) => updatePref('pause_ai', val)} 
           />
        </div>

        <div className="space-y-3 pt-4 border-t border-black/5 dark:border-white/5">
          <label className="text-sm font-medium text-gray-900 dark:text-gray-100">Custom AI Persona</label>
          <p className="text-xs text-gray-500">Add an instruction for the AI like "Act as a stoic philosopher".</p>
          <textarea 
            className="w-full rounded-xl border border-black/10 dark:border-white/10 bg-transparent p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            rows={3}
            placeholder="Focus on actionable advice..."
            value={prefs?.custom_persona_prompt || ""}
            onChange={(e) => updatePref('custom_persona_prompt', e.target.value)}
          />
        </div>

        <div className="space-y-1 pt-4 border-t border-black/5 dark:border-white/5">
           <p className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-2">Widget Visibility</p>
           <ToggleSwitch 
              label="Hide Mood Score" 
              checked={!!prefs?.hide_mood} 
              onChange={(val: any) => updatePref('hide_mood', val)} 
           />
           <ToggleSwitch 
              label="Hide Grammar Fixes" 
              checked={!!prefs?.hide_grammar} 
              onChange={(val: any) => updatePref('hide_grammar', val)} 
           />
           <ToggleSwitch 
              label="Hide Cognitive Reframes" 
              checked={!!prefs?.hide_reframes} 
              onChange={(val: any) => updatePref('hide_reframes', val)} 
           />
           <ToggleSwitch 
              label="Hide Open Loops" 
              checked={!!prefs?.hide_open_loops} 
              onChange={(val: any) => updatePref('hide_open_loops', val)} 
           />
           <ToggleSwitch 
              label="Hide Word Target" 
              checked={!!prefs?.hide_word_target} 
              onChange={(val: any) => updatePref('hide_word_target', val)} 
           />
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
