"use client"
import React, { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { CircleDot, Globe2, HelpCircle } from "lucide-react"
import { InfoTooltip } from "@/components/ui/InfoTooltip"

interface EnergyItem {
  item: string
  reframe: string
}

interface CircleOfControlProps {
  controllables: EnergyItem[]
  uncontrollables: EnergyItem[]
}

export function CircleOfControl({ controllables, uncontrollables }: CircleOfControlProps) {
  const [activeChip, setActiveChip] = useState<string | null>(null)

  return (
    <div className="bg-card border rounded-2xl p-6 shadow-sm">
      <div className="mb-6">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <CircleDot className="w-5 h-5 text-primary" />
          Circle of Control
          <InfoTooltip text="A Stoic exercise to help you separate actionable factors from external events. Click on items for AI reframes." />
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Separating what you can act on from what you need to let go.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Left Column: In Your Hands */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b">
            <div className="w-3 h-3 rounded-full bg-blue-500" />
            <h3 className="font-medium">In Your Hands</h3>
          </div>
          <div className="flex flex-col gap-2">
            {controllables.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">No controllable factors detected.</p>
            ) : (
              controllables.map((itemObj, i) => {
                const isLegacy = typeof itemObj === 'string';
                const text = isLegacy ? itemObj : (itemObj as EnergyItem).item;
                const reframe = isLegacy ? null : (itemObj as EnergyItem).reframe;
                
                return (
                  <div key={i} className="flex flex-col gap-1">
                    <div 
                      className={`p-3 bg-blue-50 dark:bg-blue-900/10 border border-blue-100 dark:border-blue-900/30 rounded-xl text-sm font-medium text-blue-900 dark:text-blue-100 flex items-start justify-between group ${!isLegacy ? 'cursor-pointer hover:bg-blue-100 dark:hover:bg-blue-900/20 transition-colors' : ''}`}
                      onClick={() => !isLegacy && setActiveChip(activeChip === `c-${i}` ? null : `c-${i}`)}
                    >
                      <span>{text}</span>
                      {!isLegacy && <HelpCircle className="w-4 h-4 text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity" />}
                    </div>
                    {!isLegacy && (
                      <AnimatePresence>
                        {activeChip === `c-${i}` && (
                          <motion.div 
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                          >
                            <p className="text-xs text-blue-700 dark:text-blue-300 px-3 py-2 bg-blue-100/50 dark:bg-blue-900/20 rounded-lg border border-blue-200/50 dark:border-blue-800/30">
                              {reframe}
                            </p>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Beyond Your Hands */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b">
            <div className="w-3 h-3 rounded-full bg-slate-300 dark:bg-slate-600" />
            <h3 className="font-medium text-slate-700 dark:text-slate-300">Beyond Your Hands</h3>
          </div>
          <div className="flex flex-col gap-2">
            {uncontrollables.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">No external factors detected.</p>
            ) : (
              uncontrollables.map((itemObj, i) => {
                const isLegacy = typeof itemObj === 'string';
                const text = isLegacy ? itemObj : (itemObj as EnergyItem).item;
                const reframe = isLegacy ? null : (itemObj as EnergyItem).reframe;
                
                return (
                  <div key={i} className="flex flex-col gap-1">
                    <div 
                      className={`p-3 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-medium text-slate-600 dark:text-slate-400 flex items-start justify-between group ${!isLegacy ? 'cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors' : ''}`}
                      onClick={() => !isLegacy && setActiveChip(activeChip === `u-${i}` ? null : `u-${i}`)}
                    >
                      <span>{text}</span>
                      {!isLegacy && <Globe2 className="w-4 h-4 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />}
                    </div>
                    {!isLegacy && (
                      <AnimatePresence>
                        {activeChip === `u-${i}` && (
                          <motion.div 
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                          >
                            <p className="text-xs text-slate-500 dark:text-slate-400 px-3 py-2 bg-slate-100 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                              {reframe}
                            </p>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
