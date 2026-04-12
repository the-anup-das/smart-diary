import * as React from "react"
import { Sidebar } from "@/components/layout/Sidebar"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex h-screen bg-background overflow-hidden selection:bg-primary/30">
      {/* Sidebar Navigation */}
      <Sidebar />
      
      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto relative">
        <div className="mx-auto max-w-5xl h-full p-4 lg:p-8">
          {children}
        </div>
      </main>
    </div>
  )
}
