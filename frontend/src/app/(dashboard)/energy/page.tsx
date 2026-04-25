"use client"
import React, { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { BatteryCharging, AlertCircle } from "lucide-react"

import { HumanBattery } from "@/components/energy/HumanBattery"
import { DomainPanel } from "@/components/energy/DomainPanel"
import { OverthinkingMeter } from "@/components/energy/OverthinkingMeter"
import { CircleOfControl } from "@/components/energy/CircleOfControl"
import { MicroActions } from "@/components/energy/MicroActions"
import { TomorrowFocus } from "@/components/energy/TomorrowFocus"

export default function EnergyPage() {
  const [loading, setLoading] = useState(true)
  const [energyData, setEnergyData] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchEnergyData() {
      try {
        const res = await fetch("/api/energy/today")
        const data = await res.json()
        if (data.success && data.energy_data) {
          setEnergyData(data.energy_data)
        } else {
          setError(data.detail || "No analysis available today. Write an entry to see your energy.")
        }
      } catch (err) {
        setError("Failed to load energy data.")
      } finally {
        setLoading(false)
      }
    }
    fetchEnergyData()
  }, [])

  const handleToggleAction = async (id: string) => {
    // Optimistic UI Update
    setEnergyData((prev: any) => {
      const newActions = prev.micro_actions.map((a: any) => 
        a.id === id ? { ...a, completed: !a.completed } : a
      )
      
      const wasCompleted = prev.micro_actions.find((a: any) => a.id === id)?.completed
      const batteryChange = wasCompleted ? -3 : 3
      const newBattery = Math.min(100, Math.max(0, prev.battery_level + batteryChange))
      
      return {
        ...prev,
        micro_actions: newActions,
        battery_level: newBattery
      }
    })

    // Persist
    try {
      await fetch(`/api/energy/actions/${id}`, { method: 'PATCH' })
    } catch (e) {
      console.error("Failed to toggle action", e)
    }
  }

  if (loading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <BatteryCharging className="w-12 h-12 text-primary animate-pulse" />
          <p className="text-gray-500 font-medium">Calibrating your energy...</p>
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
          <p className="text-muted-foreground mt-2 max-w-md">
            Your energy battery is charged by your thoughts. Write a diary entry today and let the AI analyze your mental state to unlock this dashboard.
          </p>
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
