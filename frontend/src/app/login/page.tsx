"use client"
import * as React from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"

export default function LoginPage() {
  const [email, setEmail] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [name, setName] = React.useState("")
  const [isRegistering, setIsRegistering] = React.useState(false)
  const [isForgotMode, setIsForgotMode] = React.useState(false)
  const [error, setError] = React.useState("")
  const [notice, setNotice] = React.useState("")
  const router = useRouter()

  async function handleForgotPassword(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setNotice("")
    try {
      const res = await fetch('/api/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      if (res.ok) {
        setNotice("If that account exists, a reset link has been sent. No email server configured? The link is printed in the backend logs.")
      } else {
        const data = await res.json().catch(() => null)
        setError(data?.detail || "Could not request a reset link. Please try again.")
      }
    } catch {
      setError("Could not reach the server. Please try again.")
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")

    if (isRegistering) {
      if (password.length < 5) {
        setError("Password must be at least 5 characters long.")
        return
      }
      if (password.length > 71) {
        setError("Password cannot exceed 71 characters (encryption limit).")
        return
      }
    }
    
    const endpoint = isRegistering ? '/api/auth/register' : '/api/auth/login'
    const body = isRegistering 
      ? { email, password, name } 
      : { email, password }

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    
    if (res.ok) {
      router.push('/')
      router.refresh()
    } else {
      try {
        const data = await res.json()
        setError(data.error || "Authentication failed")
      } catch (err) {
        setError("Server failed to respond correctly (Status: " + res.status + ")")
      }
    }
  }

  return (
    <div className="flex h-screen w-full items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md shadow-2xl border-black/10 dark:border-white/5">
        <CardHeader>
          <CardTitle className="text-2xl text-center font-serif">
            {isForgotMode ? "Reset your password" : isRegistering ? "Create your Journal" : "Unlock your Journal"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isForgotMode ? (
            <>
              <form onSubmit={handleForgotPassword} className="space-y-5">
                <Input
                  type="email"
                  placeholder="Email address"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                />
                {error && <p className="text-danger text-sm font-medium" role="alert">{error}</p>}
                {notice && <p className="text-sm font-medium text-green-600 dark:text-green-400" role="status">{notice}</p>}
                <Button type="submit" className="w-full h-12 text-lg mt-2">
                  Send reset link
                </Button>
              </form>
              <p className="mt-8 text-center text-sm text-gray-500">
                Remembered it?{" "}
                <button
                  onClick={() => { setIsForgotMode(false); setError(""); setNotice("") }}
                  className="text-primary hover:text-primary-hover hover:underline transition-colors font-medium"
                >
                  Back to login
                </button>
              </p>
            </>
          ) : (
          <>
          <form onSubmit={handleSubmit} className="space-y-5">
            {isRegistering && (
              <Input 
                type="text" 
                placeholder="Full Name" 
                value={name} 
                onChange={e => setName(e.target.value)} 
                required 
              />
            )}
            <Input 
              type="email" 
              placeholder="Email address" 
              value={email} 
              onChange={e => setEmail(e.target.value)} 
              required 
            />
            <Input 
              type="password" 
              placeholder="Password" 
              value={password} 
              onChange={e => setPassword(e.target.value)} 
              required 
            />
            {error && <p className="text-danger text-sm font-medium" role="alert">{error}</p>}
            <Button type="submit" className="w-full h-12 text-lg mt-2">
              {isRegistering ? "Register" : "Login"}
            </Button>
          </form>
          {!isRegistering && (
            <p className="mt-4 text-center text-sm">
              <button
                onClick={() => { setIsForgotMode(true); setError("") }}
                className="text-gray-500 hover:text-primary hover:underline transition-colors"
              >
                Forgot password?
              </button>
            </p>
          )}
          <p className="mt-8 text-center text-sm text-gray-500">
            {isRegistering ? "Already have an account? " : "Don't have an account? "}
            <button
              onClick={() => setIsRegistering(!isRegistering)}
              className="text-primary hover:text-primary-hover hover:underline transition-colors font-medium"
            >
              {isRegistering ? "Login here" : "Create one"}
            </button>
          </p>
          </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
