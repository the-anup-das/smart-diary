"use client"
import * as React from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"

export function ResetPasswordForm({ token }: { token: string }) {
  const [password, setPassword] = React.useState("")
  const [confirm, setConfirm] = React.useState("")
  const [error, setError] = React.useState("")
  const [success, setSuccess] = React.useState(false)
  const [submitting, setSubmitting] = React.useState(false)
  const router = useRouter()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")

    if (password.length < 5) {
      setError("Password must be at least 5 characters long.")
      return
    }
    if (password.length > 71) {
      setError("Password cannot exceed 71 characters (encryption limit).")
      return
    }
    if (password !== confirm) {
      setError("Passwords do not match.")
      return
    }

    setSubmitting(true)
    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      })
      if (res.ok) {
        setSuccess(true)
        setTimeout(() => router.push("/login"), 2500)
      } else {
        const data = await res.json().catch(() => null)
        setError(data?.detail || "Reset link is invalid or has expired.")
      }
    } catch {
      setError("Could not reach the server. Please try again.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex h-screen w-full items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md shadow-2xl border-black/10 dark:border-white/5">
        <CardHeader>
          <CardTitle className="text-2xl text-center font-serif">
            Choose a new password
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!token ? (
            <p className="text-center text-sm text-gray-500">
              This reset link is missing its token. Please use the full link from
              your email or the server logs.
            </p>
          ) : success ? (
            <p className="text-center text-sm font-medium text-green-600 dark:text-green-400" role="status">
              Password updated. Redirecting you to login…
            </p>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <Input
                type="password"
                placeholder="New password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
              <Input
                type="password"
                placeholder="Confirm new password"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                autoComplete="new-password"
                required
              />
              {error && <p className="text-danger text-sm font-medium" role="alert">{error}</p>}
              <Button type="submit" className="w-full h-12 text-lg mt-2" disabled={submitting}>
                {submitting ? "Updating…" : "Update password"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
