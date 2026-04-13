"use client"
import * as React from "react"
import { Button } from "@/components/ui/Button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"

function ToggleSwitch({ checked, onChange, label, description }: any) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <p className="font-medium text-sm text-gray-900 dark:text-gray-100">{label}</p>
        {description && <p className="text-xs text-gray-500">{description}</p>}
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary/50 ${checked ? 'bg-primary' : 'bg-gray-200 dark:bg-gray-700'}`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${checked ? 'translate-x-5' : 'translate-x-0'}`}
        />
      </button>
    </div>
  )
}

export function AIPrefSettings() {
  const [prefs, setPrefs] = React.useState<any>(null)
  const [loading, setLoading] = React.useState(true)
  const [saving, setSaving] = React.useState(false)

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
    try {
      await fetch("/api/users/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preferences: prefs })
      })
      alert("AI Preferences updated successfully")
    } catch (e) {
      alert("Failed to update preferences")
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
        </div>

        <div className="pt-4 border-t border-black/5 dark:border-white/5 flex justify-end">
          <Button onClick={handleSave} disabled={saving} className="px-6">
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
