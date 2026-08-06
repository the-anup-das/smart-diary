"use client"
import React, { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { BatteryCharging, AlertCircle } from "lucide-react"
import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"

import { HumanBattery } from "@/components/energy/HumanBattery"
import { DomainPanel } from "@/components/energy/DomainPanel"
import { OverthinkingMeter } from "@/components/energy/OverthinkingMeter"
import { CircleOfControl } from "@/components/energy/CircleOfControl"
import { MicroActions } from "@/components/energy/MicroActions"
import { TomorrowFocus } from "@/components/energy/TomorrowFocus"

export default function EnergyPage() {
  const { data: rawData, error: swrError, isLoading: loading, mutate } = useSWR("/api/energy/today", fetcher)
  
  const energyData = rawData?.success ? rawData.energy_data : null
  const error = swrError 
    ? "Could not reach the server for your energy data." 
    : (!loading && !energyData ? rawData?.detail || "No analysis available today. Write an entry to see your energy." : null)
  const isNetworkError = !!swrError

  const toggleActionState = (prev: any, id: string) => {
    const newActions = prev.micro_actions.map((a: any) =>
      a.id === id ? { ...a, completed: !a.completed } : a
    )
    const wasCompleted = prev.micro_actions.find((a: any) => a.id === id)?.completed
    const batteryChange = wasCompleted ? -3 : 3
    const newBattery = Math.min(100, Math.max(0, prev.battery_level + batteryChange))
    return { ...prev, micro_actions: newActions, battery_level: newBattery }
  }

  const handleToggleAction = async (id: string) => {
    if (!energyData) return
    const optimisticData = { ...rawData, energy_data: toggleActionState(energyData, id) }
    mutate(optimisticData, false)

    try {
      const res = await fetch(`/api/energy/actions/${id}`, { method: 'PATCH' })
      if (!res.ok) throw new Error(`status ${res.status}`)
    } catch (e) {
      console.error("Failed to toggle action", e)
      mutate()
    }
  }

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto space-y-8 pb-20 animate-pulse" aria-busy="true" aria-label="Loading energy dashboard">
        <header className="mb-8 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-black/5 dark:bg-white/5" />
            <div className="h-8 w-64 rounded-lg bg-black/5 dark:bg-white/5" />
          </div>
          <div className="h-5 w-96 max-w-full rounded bg-black/5 dark:bg-white/5" />
        </header>
        <div className="space-y-6">
          <div className="h-64 rounded-2xl bg-black/5 dark:bg-white/5" />
          <div className="h-40 rounded-2xl bg-black/5 dark:bg-white/5" />
          <div className="h-48 rounded-2xl bg-black/5 dark:bg-white/5" />
          <div className="h-40 rounded-2xl bg-black/5 dark:bg-white/5" />
        </div>
      </div>
    )
  }

  if (error || !energyData) {
    return (
      <div className="max-w-4xl mx-auto space-y-8 pb-20">
        <header className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-primary/10 rounded-xl text-primary">
              <BatteryCharging className="w-6 h-6" />
            </div>
            <h1 className="text-3xl font-bold font-serif">Find Your Energy</h1>
          </div>
        </header>
        <div className="bg-card border rounded-2xl p-12 flex flex-col items-center justify-center text-center">
          <AlertCircle className="w-12 h-12 text-muted-foreground/50 mb-4" />
          <p className="text-lg font-medium text-foreground">{error || "No data available."}</p>
          {isNetworkError ? (
            <button
              onClick={() => mutate()}
              className="mt-4 px-5 py-2 rounded-xl bg-primary text-white text-sm font-medium hover:bg-primary/90 transition-colors shadow-sm"
            >
              Try again
            </button>
          ) : (
            <p className="text-muted-foreground mt-2 max-w-md">
              Your energy battery is charged by your thoughts. Write a diary entry today and let the AI analyze your mental state to unlock this dashboard.
            </p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-20 fade-in">
      <header className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-primary/10 rounded-xl text-primary">
            <BatteryCharging className="w-6 h-6" />
          </div>
          <h1 className="text-3xl font-bold font-serif">Find Your Energy</h1>
        </div>
        <p className="text-muted-foreground text-lg">
          Visualize your mental battery and manage where your energy goes.
        </p>
      </header>

      <div className="space-y-6">
        <HumanBattery 
          level={energyData.battery_level} 
          chargers={energyData.chargers} 
          drainers={energyData.drainers} 
        />
        
        <DomainPanel />
        
        <OverthinkingMeter 
          level={energyData.rumination_level} 
          coaching={energyData.rumination_coaching} 
        />
        
        <CircleOfControl 
          controllables={energyData.controllables} 
          uncontrollables={energyData.uncontrollables} 
        />
        
        <MicroActions 
          actions={energyData.micro_actions} 
          onToggle={handleToggleAction} 
        />
        
        <TomorrowFocus focus={energyData.tomorrow_focus} />
      </div>
    </div>
  )
}
