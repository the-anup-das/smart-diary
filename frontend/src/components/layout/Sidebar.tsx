"use client"
import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTheme } from "next-themes"
import { PenSquare, Calendar, BarChart2, Settings, BookHeart, Sun, Moon, ChevronLeft, ChevronRight, Target, GitMerge, BatteryCharging } from "lucide-react"
import { cn } from "@/lib/utils"

export function Sidebar() {
  const pathname = usePathname()
  const { resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
  }, [])

  const navItems = [
    { name: "Today", href: "/", icon: PenSquare },
    { name: "History", href: "/history", icon: Calendar },
    { name: "Energy", href: "/energy", icon: BatteryCharging },
    { name: "Insights", href: "/insights", icon: BarChart2 },
    { name: "Targets", href: "/targets", icon: Target },
    { name: "Decisions", href: "/decisions", icon: GitMerge },
    { name: "Settings", href: "/settings", icon: Settings },
  ]

  const [isCollapsed, setIsCollapsed] = React.useState(false)

  return (
    <aside className={cn("border-r border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.02] backdrop-blur-xl flex flex-col flex-shrink-0 transition-all duration-300 ease-in-out relative z-50 pt-4", isCollapsed ? "w-20" : "w-[260px]")}>
      {/* Brand Header */}
      <div className={cn("h-20 flex items-center border-b border-black/5 dark:border-white/5 transition-all overflow-hidden", isCollapsed ? "justify-center px-0 flex-col py-4" : "justify-between px-6")}>
        <div className="flex items-center">
          <BookHeart className={cn("text-primary shadow-primary/50 drop-shadow-lg flex-shrink-0 transition-all", isCollapsed ? "w-8 h-8 mb-3" : "w-7 h-7 mr-3")} />
          {!isCollapsed && <span className="font-serif font-bold text-xl tracking-wide text-foreground whitespace-nowrap fade-in">AI Diary</span>}
        </div>
        
        {/* Explicitly Visible Collapse Toggle */}
        <button 
          onClick={() => setIsCollapsed(!isCollapsed)} 
          className={cn("p-1.5 rounded-lg border hover:border-black/10 dark:hover:border-white/10 hover:bg-black/5 dark:hover:bg-white/5 text-gray-500 transition-all flex-shrink-0 bg-transparent cursor-pointer relative z-50", isCollapsed ? "border-black/5 dark:border-white/5" : "border-transparent")}
          title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
        >
          {isCollapsed ? <ChevronRight className="w-5 h-5 ml-0.5" /> : <ChevronLeft className="w-5 h-5 pr-0.5" />}
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 py-8 px-4 space-y-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              title={isCollapsed ? item.name : undefined}
              className={cn(
                "flex items-center py-3.5 rounded-lg text-sm font-medium transition-all group relative overflow-hidden",
                isCollapsed ? "justify-center px-0 mx-2" : "px-4 mx-0",
                isActive 
                  ? "bg-primary/10 text-primary shadow-inner disabled:pointer-events-none" 
                  : "text-gray-500 dark:text-gray-400 hover:bg-black/5 dark:hover:bg-white/5 hover:text-gray-900 dark:hover:text-gray-100"
              )}
            >
              <Icon 
                className={cn(
                  "transition-colors flex-shrink-0",
                  isCollapsed ? "w-6 h-6" : "w-5 h-5 mr-3", 
                  isActive ? "text-primary" : "text-gray-500 group-hover:text-gray-300"
                )} 
              />
              {!isCollapsed && <span className="whitespace-nowrap fade-in">{item.name}</span>}
            </Link>
          )
        })}
      </nav>

      {/* Bottom Actions */}
      <div className={cn("border-t border-black/5 dark:border-white/5 transition-all overflow-hidden", isCollapsed ? "p-3" : "p-4")}>
        <div className={cn("flex rounded-xl bg-black/5 hover:bg-black/10 dark:bg-white/5 dark:hover:bg-white/10 transition-all border border-black/5 dark:border-white/5 cursor-pointer group", isCollapsed ? "flex-col items-center py-4 space-y-4" : "items-center justify-between px-3 py-3")}>
          <div className={cn("flex items-center", isCollapsed && "justify-center")}>
            <div className={cn("rounded-full bg-gradient-to-tr from-primary to-blue-500 flex items-center justify-center text-white font-bold shadow-md flex-shrink-0 transition-all", isCollapsed ? "w-10 h-10 text-base" : "w-9 h-9 text-sm")}>
              M
            </div>
            {!isCollapsed && (
              <div className="ml-3 fade-in whitespace-nowrap overflow-hidden">
                <p className="text-sm font-medium text-foreground">My Journal</p>
                <p className="text-xs text-gray-500">Local Archive</p>
              </div>
            )}
          </div>

          {/* Minimalist Theme Switch */}
          {mounted && (
            <button
              onClick={(e) => { 
                e.preventDefault();
                setTheme(resolvedTheme === 'dark' ? 'light' : 'dark'); 
              }}
              className={`relative inline-flex flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary/50 shadow-inner \
                ${resolvedTheme === 'dark' ? 'bg-white/10' : 'bg-black/10'} \
                ${isCollapsed ? 'h-[46px] w-[26px]' : 'h-[26px] w-[46px]'}`}
              aria-label="Toggle Theme"
            >
              <span
                className={`flex h-5 w-5 transform items-center justify-center rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out \
                  ${resolvedTheme === 'dark' ? (isCollapsed ? 'translate-y-5' : 'translate-x-5') : 'translate-x-0 translate-y-0'}`}
              >
                {resolvedTheme === 'dark' ? (
                  <Moon className="h-3 w-3 text-indigo-500 transition-opacity" />
               ) : (
                  <Sun className="h-3 w-3 text-amber-500 transition-opacity" />
               )}
              </span>
            </button>
          )}
        </div>
      </div>
    </aside>
  )
}
