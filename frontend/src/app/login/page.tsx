"use client"
import * as React from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"

export default function LoginPage() {
  const [email, setEmail] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [isRegistering, setIsRegistering] = React.useState(false)
  const [error, setError] = React.useState("")
  const router = useRouter()

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
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name: "Test User" }),
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
            {isRegistering ? "Create your Journal" : "Unlock your Journal"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
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
            {error && <p className="text-danger text-sm font-medium">{error}</p>}
            <Button type="submit" className="w-full h-12 text-lg mt-2">
              {isRegistering ? "Register" : "Login"}
            </Button>
          </form>
          <p className="mt-8 text-center text-sm text-gray-500">
            {isRegistering ? "Already have an account? " : "Don't have an account? "}
            <button 
              onClick={() => setIsRegistering(!isRegistering)} 
              className="text-primary hover:text-primary-hover hover:underline transition-colors font-medium"
            >
              {isRegistering ? "Login here" : "Create one"}
            </button>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
