"use client"
import * as React from "react"
import { WifiOff, RefreshCw } from "lucide-react"

export default function OfflineFallbackPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[100dvh] bg-background text-foreground px-4 text-center">
      <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center mb-6">
        <WifiOff className="w-10 h-10 text-primary" />
      </div>
      
      <h1 className="text-3xl font-serif font-bold mb-3 tracking-tight">
        You're Offline
      </h1>
      
      <p className="text-gray-500 dark:text-gray-400 max-w-sm mb-8 leading-relaxed">
        It looks like you've lost your internet connection. 
        Smart Diary needs to be online to load this specific page for the first time.
      </p>
      
      <button 
        onClick={() => window.location.reload()}
        className="flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground font-medium rounded-xl hover:opacity-90 active:scale-95 transition-all shadow-lg shadow-primary/20"
      >
        <RefreshCw className="w-4 h-4" />
        Try Again
      </button>
      
      <a 
        href="/"
        className="mt-6 text-sm font-medium text-gray-500 hover:text-primary transition-colors"
      >
        Return to Home
      </a>
    </div>
  )
}
