"use client"
import * as React from "react"
import { Button } from "@/components/ui/Button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"
import { Download, AlertTriangle } from "lucide-react"

export function DataSettings() {
  const [exporting, setExporting] = React.useState(false)
  const [deleting, setDeleting] = React.useState(false)

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

      <Card className="glass-panel border-red-500/20 dark:border-red-500/30">
        <CardHeader>
          <CardTitle className="text-xl text-red-600 dark:text-red-400 flex items-center">
            <AlertTriangle className="w-5 h-5 mr-2" />
            Danger Zone
          </CardTitle>
          <p className="text-sm text-gray-500">Permanently delete your account and erase all data. This cannot be reversed.</p>
        </CardHeader>
        <CardContent>
          <button 
             onClick={handleDelete} 
             disabled={deleting} 
             className="inline-flex h-11 px-8 items-center justify-center rounded-md font-medium transition-all bg-red-600 text-white hover:bg-red-700 shadow-lg hover:shadow-red-500/20 hover:-translate-y-0.5 disabled:pointer-events-none disabled:opacity-50"
          >
            {deleting ? "Deleting..." : "Delete Account"}
          </button>
        </CardContent>
      </Card>
    </div>
  )
}
