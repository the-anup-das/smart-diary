"use client"
import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { PenSquare, Calendar, BarChart2, MessageCircle, MoreHorizontal, BatteryCharging, GitMerge, Target, Settings } from "lucide-react"
import { cn } from "@/lib/utils"

const TABS = [
  { name: "Today", href: "/", icon: PenSquare },
  { name: "History", href: "/history", icon: Calendar },
  { name: "Chat", href: "/chat", icon: MessageCircle },
  { name: "Insights", href: "/insights", icon: BarChart2 },
]

const MORE_ITEMS = [
  { name: "Energy", href: "/energy", icon: BatteryCharging },
  { name: "Decisions", href: "/decisions", icon: GitMerge },
  { name: "Targets", href: "/targets", icon: Target },
  { name: "Settings", href: "/settings", icon: Settings },
]

/** Thumb-reachable tab bar replacing the sidebar on small screens. */
export function BottomNav() {
  const pathname = usePathname()
  const [moreOpen, setMoreOpen] = React.useState(false)

  React.useEffect(() => { setMoreOpen(false) }, [pathname])

  const moreActive = MORE_ITEMS.some(item =>
    item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)
  )

  return (
    <>
      {moreOpen && (
        <button
          className="fixed inset-0 z-40 md:hidden bg-black/20 backdrop-blur-[2px] cursor-default"
          aria-label="Close menu"
          onClick={() => setMoreOpen(false)}
        />
      )}

      {moreOpen && (
        <div className="fixed bottom-[calc(72px+env(safe-area-inset-bottom))] right-3 z-50 md:hidden rounded-2xl border border-black/10 dark:border-white/15 bg-white dark:bg-zinc-900 shadow-2xl p-2 w-48 fade-in" role="menu">
          {MORE_ITEMS.map(item => {
            const Icon = item.icon
            const isActive = pathname.startsWith(item.href)
            return (
              <Link
                key={item.href}
                href={item.href}
                role="menuitem"
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors",
                  isActive ? "bg-primary/10 text-primary" : "text-gray-600 dark:text-gray-300 hover:bg-black/5 dark:hover:bg-white/5"
                )}
              >
                <Icon className="w-[18px] h-[18px]" />
                {item.name}
              </Link>
            )
          })}
        </div>
      )}

      <nav
        aria-label="Primary"
        className="fixed bottom-0 inset-x-0 z-50 md:hidden border-t border-black/10 dark:border-white/10 bg-white/90 dark:bg-zinc-950/90 backdrop-blur-xl pb-[env(safe-area-inset-bottom)]"
      >
        <div className="grid grid-cols-5">
          {TABS.map(tab => {
            const Icon = tab.icon
            const isActive = tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href)
            return (
              <Link
                key={tab.href}
                href={tab.href}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "flex flex-col items-center gap-1 py-2.5 text-[10px] font-medium transition-colors",
                  isActive ? "text-primary" : "text-gray-500 dark:text-gray-400"
                )}
              >
                <Icon className="w-5 h-5" />
                {tab.name}
              </Link>
            )
          })}
          <button
            onClick={() => setMoreOpen(o => !o)}
            aria-label="More sections"
            aria-expanded={moreOpen}
            className={cn(
              "flex flex-col items-center gap-1 py-2.5 text-[10px] font-medium transition-colors cursor-pointer",
              moreActive || moreOpen ? "text-primary" : "text-gray-500 dark:text-gray-400"
            )}
          >
            <MoreHorizontal className="w-5 h-5" />
            More
          </button>
        </div>
      </nav>
    </>
  )
}
