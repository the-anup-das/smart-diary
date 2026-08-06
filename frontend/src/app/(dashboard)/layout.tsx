import * as React from "react"
import { Sidebar } from "@/components/layout/Sidebar"
import { BottomNav } from "@/components/layout/BottomNav"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex h-screen bg-background overflow-hidden selection:bg-primary/30">
      {/* Sidebar navigation (desktop) */}
      <Sidebar />

      {/* Main Content Area — bottom padding clears the mobile tab bar */}
      <main className="flex-1 overflow-y-auto relative pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">
        <div className="mx-auto max-w-5xl h-full p-4 lg:p-8">
          {children}
        </div>
      </main>

      {/* Tab bar navigation (mobile) */}
      <BottomNav />
    </div>
  )
}
