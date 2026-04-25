"use client"
import React from "react"
import { Info } from "lucide-react"

export function InfoTooltip({ text }: { text: string }) {
  return (
    <div className="relative group inline-flex items-center ml-2">
      <Info className="w-4 h-4 text-muted-foreground/60 hover:text-muted-foreground transition-colors cursor-help" />
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-popover border text-popover-foreground text-xs font-medium rounded-xl shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all pointer-events-none z-50">
        {text}
        {/* Little triangle arrow at the bottom */}
        <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-[1px] border-solid border-t-popover border-t-8 border-x-transparent border-x-8 border-b-0" />
      </div>
    </div>
  )
}
