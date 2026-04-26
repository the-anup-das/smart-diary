"use client"
import * as React from "react"
import { Button } from "@/components/ui/Button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"
import { Download, AlertTriangle, Upload } from "lucide-react"
import { ToggleSwitch } from "@/components/ui/ToggleSwitch"

export function DataSettings() {
  const [exporting, setExporting] = React.useState(false)
  const [importing, setImporting] = React.useState(false)
  const [deleting, setDeleting] = React.useState(false)
  const [prefs, setPrefs] = React.useState<any>(null)
  const [loading, setLoading] = React.useState(true)
  const [saving, setSaving] = React.useState(false)
  const [saveMessage, setSaveMessage] = React.useState("")
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    fetch("/api/users/me")
      .then(res => res.json())
      .then(data => {
        if (!data.detail) {
          setPrefs(data.preferences || {})
        }
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const handleUpdateDeletionPref = async (val: boolean) => {
    const newPrefs = { ...prefs, enable_deletion: val }
    setPrefs(newPrefs)
    setSaving(true)
    setSaveMessage("")
    try {
      const res = await fetch("/api/users/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preferences: newPrefs })
      })
      if (res.ok) {
        setSaveMessage("Saved")
        setTimeout(() => setSaveMessage(""), 2000)
      } else {
        setSaveMessage("Error saving")
      }
    } catch (e) {
      setSaveMessage("Error")
    }
    setSaving(false)
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await fetch("/api/users/export")
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = "journal_export.json"
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (e) {
      alert("Failed to export data")
    }
    setExporting(false)
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setImporting(true)
    try {
      const text = await file.text()
      const data = JSON.parse(text)
      
      const res = await fetch("/api/users/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      })
      
      if (res.ok) {
        const result = await res.json()
        alert(`Successfully imported ${result.entries_imported} entries and ${result.loops_imported} open loops!`)
        window.location.reload()
      } else {
        alert("Failed to import data. Please check the file format.")
      }
    } catch (e) {
      alert("Error reading file: " + (e as Error).message)
    }
    setImporting(false)
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  const handleDelete = async () => {
    const confirmed = window.confirm("Are you SURE you want to permanently delete your account and all entries? This action cannot be undone.")
    if (!confirmed) return
    
    const finalConfirm = window.prompt("Type 'DELETE' to confirm account deletion.")
    if (finalConfirm !== "DELETE") {
      alert("Deletion cancelled.")
      return
    }

    setDeleting(true)
    try {
      const res = await fetch("/api/users/me", { method: "DELETE" })
      if(res.ok) {
         window.location.href = "/login"
      } else {
         alert("Failed to delete account")
         setDeleting(false)
      }
    } catch (e) {
      alert("Failed to delete account")
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card className="glass-panel">
        <CardHeader>
          <CardTitle className="text-xl">Export Library</CardTitle>
          <p className="text-sm text-gray-500">Download a complete JSON export of all your journal entries, feedback, and open loops.</p>
        </CardHeader>
        <CardContent>
          <Button onClick={handleExport} disabled={exporting} className="flex items-center">
            <Download className="w-4 h-4 mr-2" />
            {exporting ? "Exporting..." : "Download JSON Archive"}
          </Button>
        </CardContent>
      </Card>

      <Card className="glass-panel">
        <CardHeader>
          <CardTitle className="text-xl">Import Library</CardTitle>
          <p className="text-sm text-gray-500">Restore your journal from a previously exported JSON archive. This will merge with your current data.</p>
        </CardHeader>
        <CardContent>
          <input 
            type="file" 
            accept=".json" 
            className="hidden" 
            ref={fileInputRef} 
            onChange={handleImport}
          />
          <Button 
            onClick={() => fileInputRef.current?.click()} 
            disabled={importing} 
            className="flex items-center"
            variant="outline"
          >
            <Upload className="w-4 h-4 mr-2" />
            {importing ? "Importing..." : "Restore from JSON Backup"}
          </Button>
        </CardContent>
      </Card>

      <Card className="glass-panel border-red-500/20 dark:border-red-500/30">
        <CardHeader>
          <CardTitle className="text-xl text-red-600 dark:text-red-400 flex items-center">
            <AlertTriangle className="w-5 h-5 mr-2" />
            Danger Zone
          </CardTitle>
          <p className="text-sm text-gray-500">Permanently delete your account and erase all data. This cannot be reversed.</p>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="pt-2">
            <ToggleSwitch 
              label="Enable Entry Deletion" 
              description="Allow removing individual entries from your history (with 3-month safety net)."
              checked={!!prefs?.enable_deletion} 
              onChange={handleUpdateDeletionPref} 
            />
            <div className="h-4">
              {saving && <p className="text-xs text-primary animate-pulse flex items-center"><span className="mr-1.5 w-1.5 h-1.5 rounded-full bg-primary animate-ping" /> Saving...</p>}
              {saveMessage && <p className={`text-xs ${saveMessage.includes('Error') ? 'text-red-500' : 'text-green-500'} fade-in flex items-center`}>
                {!saveMessage.includes('Error') && <span className="mr-1.5">✓</span>}
                {saveMessage}
              </p>}
            </div>
          </div>

          <div className="pt-6 border-t border-red-500/10">
            <p className="text-sm font-semibold text-red-600 dark:text-red-400 mb-2">Account Destruction</p>
            <button 
              onClick={handleDelete} 
              disabled={deleting} 
              className="inline-flex h-11 px-8 items-center justify-center rounded-md font-medium transition-all bg-red-600 text-white hover:bg-red-700 shadow-lg hover:shadow-red-500/20 hover:-translate-y-0.5 disabled:pointer-events-none disabled:opacity-50"
            >
              {deleting ? "Deleting..." : "Delete Account"}
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
