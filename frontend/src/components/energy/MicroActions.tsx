"use client"
import React, { useState } from "react"
import { CheckCircle2, Circle, Activity } from "lucide-react"
import { InfoTooltip } from "@/components/ui/InfoTooltip"

interface Action {
  id: string
  text: string
  completed: boolean
}

interface MicroActionsProps {
  actions: Action[]
  onToggle: (id: string) => void
}

export function MicroActions({ actions, onToggle }: MicroActionsProps) {
  if (!actions || actions.length === 0) return null

  return (
    <div className="bg-card border rounded-2xl p-6 shadow-sm">
      <div className="mb-6">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Activity className="w-5 h-5 text-primary" />
          Add Some Juice
          <InfoTooltip text="Personalized small steps to help you recover energy based on today's diary entry. Completing them will boost your battery!" />
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Small, actionable steps to recharge your energy today.
        </p>
      </div>

      <div className="space-y-3">
        {actions.map((action) => (
          <div 
            key={action.id}
            onClick={() => onToggle(action.id)}
            className={`flex items-start gap-4 p-4 rounded-xl border cursor-pointer transition-all ${
              action.completed 
                ? 'bg-secondary/50 border-secondary opacity-70' 
                : 'bg-card border-border hover:border-primary/50 hover:bg-primary/5'
            }`}
          >
            <div className="mt-0.5 flex-shrink-0">
              {action.completed ? (
                <CheckCircle2 className="w-5 h-5 text-green-500" />
              ) : (
                <Circle className="w-5 h-5 text-muted-foreground" />
              )}
            </div>
            <div className="flex-1">
              <p className={`text-sm ${action.completed ? 'line-through text-muted-foreground' : 'text-foreground'}`}>
                {action.text}
              </p>
            </div>
            <div className="flex-shrink-0">
              <span className={`text-xs font-medium px-2 py-1 rounded-md ${
                action.completed 
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' 
                  : 'bg-primary/10 text-primary'
              }`}>
                {action.completed ? '✓ +3%' : '+3% Energy'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
