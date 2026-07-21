"use client"
import * as React from "react"
import { RefreshCw } from "lucide-react"

/**
 * Detects a new service-worker version waiting to activate and offers a
 * one-click refresh. Without this, a deployed update silently coexists with
 * the cached old app until every tab is closed — which reads as "the app is
 * broken" instead of "there's an update".
 */
export function UpdatePrompt() {
  const [updateReady, setUpdateReady] = React.useState(false)
  const [reloading, setReloading] = React.useState(false)

  React.useEffect(() => {
    const wb = (window as any).workbox
    if (!wb) return

    const onWaiting = () => setUpdateReady(true)
    const onControlling = () => window.location.reload()

    wb.addEventListener("waiting", onWaiting)
    wb.addEventListener("controlling", onControlling)
    return () => {
      wb.removeEventListener("waiting", onWaiting)
      wb.removeEventListener("controlling", onControlling)
    }
  }, [])

  if (!updateReady) return null

  return (
    <div
      role="status"
      className="fixed bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-[200] flex items-center gap-3 px-4 py-3 rounded-2xl bg-background border border-primary/30 shadow-2xl shadow-primary/10 backdrop-blur-xl fade-in"
    >
      <span className="text-sm font-medium text-foreground whitespace-nowrap">
        A new version is ready.
      </span>
      <button
        onClick={() => {
          setReloading(true)
          ;(window as any).workbox?.messageSkipWaiting()
        }}
        disabled={reloading}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary text-white text-xs font-semibold hover:bg-primary/90 transition-colors cursor-pointer disabled:opacity-60"
      >
        <RefreshCw className={`w-3.5 h-3.5 ${reloading ? "animate-spin" : ""}`} />
        {reloading ? "Updating…" : "Refresh"}
      </button>
      <button
        onClick={() => setUpdateReady(false)}
        aria-label="Dismiss update notice"
        className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-lg leading-none cursor-pointer"
      >
        &times;
      </button>
    </div>
  )
}
