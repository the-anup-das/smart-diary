"use client"
import * as React from "react"
import { useTheme } from "next-themes"
import { Button } from "@/components/ui/Button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"

export function AppearanceSettings() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = React.useState(false)
  const [typography, setTypography] = React.useState("sans")
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
    fetch("/api/users/me")
      .then(res => res.json())
      .then(data => {
        if (!data.detail && data.preferences?.typography) {
           setTypography(data.preferences.typography)
        }
      })
      .catch(err => console.error(err))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await fetch("/api/users/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preferences: { typography } })
      })
      alert("Appearance preferences updated successfully")
    } catch (e) {
      alert("Failed to update preferences")
    }
    setSaving(false)
  }

  if (!mounted) return null

  return (
    <Card className="glass-panel">
      <CardHeader>
        <CardTitle className="text-xl">Appearance</CardTitle>
        <p className="text-sm text-gray-500">Customize how the application looks and feels.</p>
      </CardHeader>
      <CardContent className="space-y-6">
        
        <div className="space-y-3">
          <label className="text-sm font-medium text-gray-900 dark:text-gray-100">Color Theme</label>
          <div className="grid grid-cols-3 gap-4">
            {["light", "dark", "system"].map((t) => (
              <button
                key={t}
                onClick={() => setTheme(t)}
                className={`py-3 px-4 rounded-xl border flex items-center justify-center text-sm font-medium capitalize transition-all ${
                  theme === t 
                    ? "border-primary bg-primary/10 text-primary" 
                    : "border-black/10 dark:border-white/10 hover:border-black/20 dark:hover:border-white/20 text-gray-600 dark:text-gray-300"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-3 pt-4 border-t border-black/5 dark:border-white/5">
          <label className="text-sm font-medium text-gray-900 dark:text-gray-100">Editor Typography</label>
          <div className="grid grid-cols-2 gap-4">
            <button
              onClick={() => setTypography("sans")}
              className={`py-6 px-4 rounded-xl border flex flex-col items-center justify-center transition-all ${
                typography === "sans" 
                  ? "border-primary bg-primary/10 text-primary" 
                  : "border-black/10 dark:border-white/10 hover:border-black/20 dark:hover:border-white/20 text-gray-600 dark:text-gray-300"
              }`}
            >
              <span className="font-sans text-xl mb-1">Ag</span>
              <span className="text-sm font-medium font-sans">Modern Sans</span>
            </button>
            <button
              onClick={() => setTypography("serif")}
              className={`py-6 px-4 rounded-xl border flex flex-col items-center justify-center transition-all ${
                typography === "serif" 
                  ? "border-primary bg-primary/10 text-primary" 
                  : "border-black/10 dark:border-white/10 hover:border-black/20 dark:hover:border-white/20 text-gray-600 dark:text-gray-300"
              }`}
            >
              <span className="font-serif text-xl mb-1">Ag</span>
              <span className="text-sm font-medium font-serif">Classic Serif</span>
            </button>
          </div>
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
