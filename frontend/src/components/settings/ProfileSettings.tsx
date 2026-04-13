"use client"
import * as React from "react"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"

export function ProfileSettings() {
  const [profile, setProfile] = React.useState({ name: "", email: "" })
  const [loading, setLoading] = React.useState(true)
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    fetch("/api/users/me")
      .then(res => res.json())
      .then(data => {
        if (!data.detail) {
           setProfile({ name: data.name || "", email: data.email || "" })
        }
        setLoading(false)
      })
      .catch(err => {
        console.error(err)
        setLoading(false)
      })
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await fetch("/api/users/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile)
      })
      alert("Profile updated successfully")
    } catch (e) {
      alert("Failed to update profile")
    }
    setSaving(false)
  }

  if (loading) return <div className="text-gray-500 animate-pulse p-4">Loading profile...</div>

  return (
    <Card className="glass-panel">
      <CardHeader>
        <CardTitle className="text-xl">Profile Details</CardTitle>
        <p className="text-sm text-gray-500">Update your personal information.</p>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Name</label>
          <Input 
            value={profile.name} 
            onChange={(e) => setProfile({...profile, name: e.target.value})} 
            placeholder="Your Name" 
            className="w-full md:w-2/3"
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Email Address</label>
          <Input 
            type="email" 
            value={profile.email} 
            onChange={(e) => setProfile({...profile, email: e.target.value})} 
            placeholder="you@example.com" 
            className="w-full md:w-2/3"
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
