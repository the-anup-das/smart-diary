"use client"
import * as React from "react"
import { TargetsSettings } from "@/components/settings/TargetsSettings"

export default function TargetsPage() {
  return (
    <div className="max-w-4xl mx-auto h-full fade-in flex flex-col pt-4">
      <h1 className="text-3xl font-serif font-bold text-foreground mb-8">Targets</h1>
      <TargetsSettings />
    </div>
  )
}
