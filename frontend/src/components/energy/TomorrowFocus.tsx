"use client"
import React from "react"
import { motion } from "framer-motion"
import { Sunrise } from "lucide-react"

interface TomorrowFocusProps {
  focus: string
}

export function TomorrowFocus({ focus }: TomorrowFocusProps) {
  const displayFocus = focus || "Focus on resting and resetting for a fresh start tomorrow. Write a new entry to get personalized strategies!";

  return (
    <div className="bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-950/30 dark:to-purple-950/30 border border-indigo-100 dark:border-indigo-900/50 rounded-2xl p-6 shadow-sm relative overflow-hidden">
      {/* Decorative gradient blur */}
      <div className="absolute -top-10 -right-10 w-32 h-32 bg-purple-400/20 dark:bg-purple-600/20 blur-3xl rounded-full pointer-events-none" />
      <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-indigo-400/20 dark:bg-indigo-600/20 blur-3xl rounded-full pointer-events-none" />

      <div className="relative z-10">
        <h2 className="text-lg font-semibold flex items-center gap-2 mb-3 text-indigo-900 dark:text-indigo-100">
          <Sunrise className="w-5 h-5 text-indigo-500" />
          Tomorrow's Recharge Strategy
        </h2>
        <p className="text-indigo-800/80 dark:text-indigo-200/80 leading-relaxed font-medium">
          {displayFocus}
        </p>
      </div>
    </div>
  )
}
