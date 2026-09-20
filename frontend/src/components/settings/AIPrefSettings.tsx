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
  const [config, setConfig] = React.useState<any>(null)

  const loadConfig = React.useCallback(() => {
    fetch("/api/ai/config")
      .then(res => (res.ok ? res.json() : null))
      .then(setConfig)
      .catch(() => {})
  }, [])

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
    loadConfig()
  }, [loadConfig])

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
      loadConfig()
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
        <p className="text-sm text-gray-500">Choose which model reads your journal, and fine-tune how it analyses it.</p>
      </CardHeader>
      <CardContent className="space-y-6">

        <ModelPanel prefs={prefs} updatePref={updatePref} config={config} />

        <div className="space-y-1">
           <ToggleSwitch
              label="Pause AI Analysis"
              description="Temporarily skip AI processing and keep entries as plain text only."
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
           <ToggleSwitch
              label="Hide Decision Junction"
              checked={!!prefs?.hide_decisions}
              onChange={(val: any) => updatePref('hide_decisions', val)}
           />
           <ToggleSwitch
              label="Hide 3-Minute Reset prompts"
              description="Hides the reset suggestions in the editor and after analysis. The practice stays available on the Energy page."
              checked={!!prefs?.hide_calm_reset}
              onChange={(val: any) => updatePref('hide_calm_reset', val)}
           />
           <ToggleSwitch
              label="Hide Wellbeing Profile"
              description="Hides the six-axis profile radar in the entry feedback and on Insights."
              checked={!!prefs?.hide_wellbeing}
              onChange={(val: any) => updatePref('hide_wellbeing', val)}
           />
           <ToggleSwitch
              label="Hide Focus Reset and Mind Fitness"
              description="Hides the Focus page, the Insights card and the cards after analysis. Entries are still analysed, so nothing is lost."
              checked={!!prefs?.hide_focus}
              onChange={(val: any) => updatePref('hide_focus', val)}
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

const inputClass = "w-full rounded-xl border border-black/10 dark:border-white/10 bg-transparent px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/50"

/**
 * Cloud or local model. Local means an OpenAI-compatible server you run yourself (llama.cpp
 * llama-server, vLLM, LM Studio, Ollama). Every AI feature follows the choice; the fallback
 * toggle lets the cloud model step in when the local one fails or returns unusable output.
 */
function ModelPanel({ prefs, updatePref, config }: { prefs: any; updatePref: (k: string, v: any) => void; config: any }) {
  const [testing, setTesting] = React.useState(false)
  const [result, setResult] = React.useState<any>(null)
  const defaults = config?.server_defaults || {}
  const mode: "cloud" | "local" = prefs?.ai_mode || (defaults.use_local ? "local" : "cloud")
  const baseUrl = prefs?.local_llm_base_url ?? ""
  const model = prefs?.local_llm_model ?? ""
  const fallback = prefs?.local_llm_fallback ?? (defaults.fallback ?? true)

  const runTest = async () => {
    setTesting(true)
    setResult(null)
    try {
      const body = mode === "local"
        ? { mode: "local", base_url: baseUrl || defaults.local_base_url, model: model || defaults.local_model }
        : { mode: "cloud" }
      const res = await fetch("/api/ai/test", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      setResult(await res.json())
    } catch {
      setResult({ ok: false, error: "Could not reach the backend." })
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.02] p-4 space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">AI model</p>
          {config ? (
            <p className="text-xs text-gray-500 font-mono mt-0.5">
              now: {config.host} · {config.chat_model}
              {config.is_local && <span className="ml-2 px-1.5 py-0.5 rounded bg-green-500/10 text-green-600 text-[10px] font-sans font-semibold">local</span>}
              {config.is_local && config.fallback_to_cloud && <span className="ml-1 px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[10px] font-sans font-semibold">cloud fallback on</span>}
            </p>
          ) : (
            <p className="text-xs text-gray-400 mt-0.5">Loading…</p>
          )}
        </div>
        <div className="flex rounded-xl border border-black/10 dark:border-white/15 overflow-hidden text-sm" role="radiogroup" aria-label="AI model location">
          {(["cloud", "local"] as const).map(m => (
            <button key={m} role="radio" aria-checked={mode === m} onClick={() => updatePref("ai_mode", m)}
              className={`px-4 py-1.5 cursor-pointer transition-colors ${mode === m ? "bg-primary text-white" : "hover:bg-black/5 dark:hover:bg-white/5"}`}>
              {m === "cloud" ? "Cloud" : "Local"}
            </button>
          ))}
        </div>
      </div>

      {mode === "local" ? (
        <div className="space-y-3">
          <label className="block text-xs text-gray-500">
            Server URL
            <input className={`${inputClass} mt-1`} value={baseUrl} placeholder={defaults.local_base_url || "http://localhost:8080/v1"}
              onChange={e => updatePref("local_llm_base_url", e.target.value)} spellCheck={false} />
          </label>
          <label className="block text-xs text-gray-500">
            Model name, as the server lists it
            <input className={`${inputClass} mt-1`} value={model} placeholder={defaults.local_model || "smart-diary-slm"}
              onChange={e => updatePref("local_llm_model", e.target.value)} spellCheck={false} />
          </label>
          <ToggleSwitch
            label="Fall back to the cloud model"
            description={config?.cloud_available === false
              ? "No cloud model is configured on this server, so there is nothing to fall back to."
              : `When the local model fails or returns unusable output, the same request is sent to ${config?.cloud_model || "the cloud model"}.`}
            checked={!!fallback}
            onChange={(val: any) => updatePref("local_llm_fallback", val)}
          />
        </div>
      ) : (
        <p className="text-xs text-gray-500">
          Analyses, chat, weekly reviews, reset scripts and decisions use the cloud model configured on the server
          {config?.cloud_model ? <> (<span className="font-mono">{config.cloud_model}</span>)</> : null}.
        </p>
      )}

      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="secondary" onClick={runTest} disabled={testing || !config}>
          {testing ? "Testing…" : "Test connection"}
        </Button>
        {result && (
          <p className={`text-xs font-medium fade-in ${result.ok ? "text-success" : "text-danger"}`} role="status">
            {result.ok
              ? `✓ ${result.served_model || result.model} answered in ${result.latency_ms}ms` +
                (result.json_schema === true ? " · JSON schema supported" : result.json_schema === false ? " · JSON schema not supported, JSON mode with repair will be used" : "") +
                (result.model_found === false ? " · the model name is not in the server's list" : "")
              : `✗ ${result.error || "no answer"}`}
          </p>
        )}
      </div>
      {result?.ok && result.models_listed?.length > 0 && (
        <p className="text-[11px] text-gray-400 font-mono truncate" title={result.models_listed.join(", ")}>
          server lists: {result.models_listed.slice(0, 6).join(", ")}{result.models_listed.length > 6 ? ", …" : ""}
        </p>
      )}
      <p className="text-[11px] text-gray-400 leading-relaxed">
        A local server is anything that speaks the OpenAI API: <code className="font-mono bg-black/5 dark:bg-white/10 px-1 rounded">docker compose --profile local-ai up llm-server</code> starts
        the bundled llama.cpp server with the fine-tuned model; LM Studio, Ollama and vLLM work the same way. Save to apply.
      </p>
    </div>
  )
}
