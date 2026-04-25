"use client"
import * as React from "react"
import { ProfileSettings } from "@/components/settings/ProfileSettings"
import { AppearanceSettings } from "@/components/settings/AppearanceSettings"
import { AIPrefSettings } from "@/components/settings/AIPrefSettings"
import { DataSettings } from "@/components/settings/DataSettings"
import { UsageDashboard } from "@/components/settings/UsageDashboard"
import { TargetsSettings } from "@/components/settings/TargetsSettings"
import { User, Palette, Brain, Shield, Coins, Target } from "lucide-react"

export default function SettingsPage() {
  const [activeTab, setActiveTab] = React.useState("profile");

  const tabs = [
    { id: "profile", label: "Profile", icon: User },
    { id: "appearance", label: "Appearance", icon: Palette },
    { id: "ai", label: "AI Preferences", icon: Brain },
    { id: "usage", label: "Usage & Billing", icon: Coins },
    { id: "data", label: "Data & Security", icon: Shield },
  ];

  return (
    <div className="max-w-4xl mx-auto h-full fade-in flex flex-col pt-4">
      <h1 className="text-3xl font-serif font-bold text-foreground mb-8">Settings</h1>
      
      <div className="flex flex-col md:flex-row gap-8">
        <aside className="w-full md:w-64 flex-shrink-0">
          <nav className="flex flex-row md:flex-col gap-2 overflow-x-auto pb-2 md:pb-0 hide-scrollbar">
            {tabs.map(tab => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex flex-shrink-0 items-center px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                    isActive 
                      ? "bg-primary text-white shadow-md" 
                      : "text-gray-600 dark:text-gray-400 hover:bg-black/5 dark:hover:bg-white/5"
                  }`}
                >
                  <Icon className={`w-5 h-5 mr-3 ${isActive ? "text-white" : "text-gray-500"}`} />
                  {tab.label}
                </button>
              )
            })}
          </nav>
        </aside>
        
        <main className="flex-1 min-h-[500px]">
          {activeTab === "profile" && <ProfileSettings />}
          {activeTab === "appearance" && <AppearanceSettings />}
          { activeTab === "ai" && <AIPrefSettings /> }
          { activeTab === "usage" && <UsageDashboard /> }
          { activeTab === "data" && <DataSettings /> }
        </main>
      </div>
    </div>
  )
}
